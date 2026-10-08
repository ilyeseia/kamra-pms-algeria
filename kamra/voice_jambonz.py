# Copyright (c) 2026 Ilyes Keskas (Algeria)
# Part of the ZIRI PMS Algeria distribution of Kamra PMS.
# SPDX-License-Identifier: AGPL-3.0-or-later
# See NOTICE for the upstream authorship this builds on.
"""The hotel's phone line, answered by ZIRI's own agent.

WHAT THIS REPLACES

A hotel that wanted AI on its phone line bought it from an outside provider.
The audit for that replacement found two things: ZIRI's own agent is already
open source and already has the tools, and the provider seam in
kamra/agents_channels.py was never the thing missing - it is a webhook
contract that already accepts Twilio, Retell, Vapi and Meta. What was missing
was a path for someone who is not signed in, which kamra/agent_guest.py now
is, and an adapter that speaks a telephony platform's language. This is that
adapter, for jambonz.

WHY JAMBONZ AND WHAT IT COSTS

jambonz is MIT, runs on the hotel's own server or air-gapped, and speaks SIP
to any carrier. Its webhook contract is a synchronous one per call leg: it
POSTs to an application URL and the application answers with a JSON array of
verbs - say, gather, listen, dial, hangup - executed in order. That maps onto
one Frappe endpoint per hook and no new service in this app.

It is not free of cost, and the commit that added it should say so rather than
let a hotelier discover it: a phone number and a carrier are a monthly bill
whatever the software licence, and jambonz itself is a telecom stack - SBC,
feature server, its own MySQL and Redis - that runs BESIDE this application,
never inside it. Nothing here adds a dependency to ZIRI.

THE ARABIC PROBLEM, STATED IN THE CODE AND NOT ONLY IN A REPORT

Published results put fine-tuned Whisper on Algerian Darija between roughly
25% and 35% word error. A caller giving a room number or a surname down a
phone line, with one word in three or four misheard, is not a concierge - it
is a complaint generator. The adapter therefore does two things rather than
pretend otherwise: it never acts on a transcript it was not confident about,
and it hands off to a human on anything it cannot answer. A hotel running this
in Darija should measure it on its own recordings before trusting it, and the
honest default is French or Modern Standard Arabic.

WHAT THIS CANNOT DO

Nothing that changes state. The guest agent has no such tool, so a caller
cannot book, amend or cancel through the phone - the adapter offers to take a
message and pass it to the desk. That is a deliberate first version, not a
limitation waiting to be lifted quietly.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import frappe

# How many words a transcript must carry before it is worth sending to a model.
# A one-word transcript from a noisy line is usually the STT guessing.
_MIN_WORDS = 2

# Below this, the transcript is treated as not understood and the caller is
# asked again rather than answered from a guess. jambonz reports confidence per
# alternative; vendors that do not report one send None, which is accepted -
# refusing those would silence the whole call.
_MIN_CONFIDENCE = 0.5

# A conversation is held in the call's own state, not in a doctype: it lives
# for the length of one call and holding guests' spoken words longer than the
# call needs is a privacy cost with no operational return.
_MAX_TURNS = 12


def _verbs(*items) -> list[dict]:
	return [i for i in items if i]


def _say(text: str, lang: str | None = None) -> dict:
	v = {"verb": "say", "text": text}
	if lang:
		v["synthesizer"] = {"language": lang}
	return v


def _gather(prompt: str, action_url: str, lang: str | None = None) -> dict:
	"""Speak, then listen. Nested so the caller can interrupt the prompt."""
	g = {
		"verb": "gather",
		"input": ["speech"],
		"actionHook": action_url,
		"timeout": 8,
		"say": {"text": prompt},
	}
	if lang:
		g["recognizer"] = {"language": lang}
		g["say"]["synthesizer"] = {"language": lang}
	return g


def _hangup() -> dict:
	return {"verb": "hangup"}


def _hook_url(method: str) -> str:
	return f"{frappe.utils.get_url()}/api/method/kamra.voice_jambonz.{method}"


def _called_number(payload: dict) -> str:
	"""The property line this call arrived on.

	jambonz names it `to`; the seam in agents_channels.py and its documented
	contract name it phone_number. Both are accepted so one Channel Provider
	Connection serves a jambonz call hook and a provider posting the existing
	contract, without the hotel maintaining two rows for one line.
	"""
	for key in ("to", "called", "phone_number"):
		v = (payload.get(key) or "").strip()
		if v:
			return v
	return ""


def _connection(phone_number: str):
	"""The Channel Provider Connection this call arrived on.

	Routing by the property's own line, exactly as agents_channels.py does, so
	one deployment can answer for more than one property and a call can never
	be answered with another hotel's data.
	"""
	if not phone_number:
		return None
	# Same filter agents_channels.py uses, field for field. The first version
	# of this looked up external_account_id and filtered on a "disabled" field
	# that does not exist on this doctype - which matches nothing, so every
	# call would have been answered "this number is not in service".
	name = frappe.db.get_value(
		"Channel Provider Connection",
		{"channel": "Voice", "phone_number": phone_number, "active": 1},
		"name")
	return frappe.get_doc("Channel Provider Connection", name) if name else None


def _authentic(raw: bytes, signature: str, secret: str) -> bool:
	"""HMAC-SHA256 over the raw body, same contract as agents_channels.py.

	A call hook is allow_guest - it has to be, jambonz is not a logged-in user
	- so the signature is the only thing standing between the public internet
	and an endpoint that spends the hotel's model credits. compare_digest
	rather than ==, because a timing oracle on a signature is a real one.
	"""
	if not secret or not signature:
		return False
	expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature.strip().lower())


def _guard(secret: str) -> bool:
	raw = frappe.request.get_data() if frappe.request else b""
	sig = (frappe.get_request_header("X-Kamra-Signature") or "")
	return _authentic(raw, sig, secret)


def _lang_of(conn) -> str | None:
	"""The language jambonz should recognise and speak in.

	Taken from the connection rather than guessed per call: a hotel's line has
	one language policy, and switching recognisers mid-call on a guess is how
	an Arabic caller gets transcribed as French.

	meta_language is the field this doctype already carries for exactly this -
	the language a channel speaks. There is no `language` field on it, which
	the first version of this function assumed and would have silently read as
	None, leaving every call on the recogniser's default.
	"""
	return (getattr(conn, "meta_language", None) or "").strip() or None


@frappe.whitelist(allow_guest=True, methods=["POST"])
def call_hook():
	"""jambonz has answered a call. Greet, then listen.

	Returns the verb array jambonz executes. Every failure path still returns
	verbs: a 500 here is dead air on a real guest's call, so an unreadable
	request is answered with an apology and a hangup rather than an exception.
	"""
	try:
		payload = json.loads(frappe.request.get_data() or b"{}")
	except ValueError:
		return _verbs(_say("Sorry, we could not take your call."), _hangup())

	conn = _connection(_called_number(payload))
	if not conn:
		# An unrecognised line is not this hotel's call to answer.
		return _verbs(_say("This number is not in service."), _hangup())
	if not _guard(conn.get_password("webhook_secret", raise_exception=False) or ""):
		frappe.log_error(title="[SECURITY-001] jambonz call hook: bad signature")
		return _verbs(_say("Sorry, we could not take your call."), _hangup())

	lang = _lang_of(conn)
	greeting = frappe.db.get_value("Property", conn.property, "property_name") or "the hotel"
	return _verbs(_gather(
		f"Thank you for calling {greeting}. How can I help?",
		_hook_url("speech_hook"), lang))


@frappe.whitelist(allow_guest=True, methods=["POST"])
def speech_hook():
	"""The caller said something. Answer it, or hand them to the desk."""
	try:
		payload = json.loads(frappe.request.get_data() or b"{}")
	except ValueError:
		return _verbs(_say("Sorry, something went wrong."), _hangup())

	conn = _connection(_called_number(payload))
	if not conn:
		return _verbs(_hangup())
	if not _guard(conn.get_password("webhook_secret", raise_exception=False) or ""):
		frappe.log_error(title="[SECURITY-001] jambonz speech hook: bad signature")
		return _verbs(_hangup())

	lang = _lang_of(conn)
	transcript, confidence = _best_alternative(payload)

	if not _usable(transcript, confidence):
		# Not answered from a guess. See the module docstring on Darija.
		return _verbs(_gather(
			"Sorry, I did not catch that. Could you say it again?",
			_hook_url("speech_hook"), lang))

	from kamra.agent_guest import answer

	history = _history(payload) + [{"role": "user", "content": transcript}]
	out = answer(conn.property, history, lang=lang)
	reply = (out.get("reply") or "").strip()

	if not reply:
		# The agent could not answer - no key, no provider, out of rounds. A
		# caller gets a person, not an error.
		return _verbs(
			_say("Let me put you through to the front desk.", lang),
			_hangup())

	if len(history) >= _MAX_TURNS:
		return _verbs(_say(reply, lang),
		              _say("I will pass the rest to the desk.", lang),
		              _hangup())
	return _verbs(_gather(reply, _hook_url("speech_hook"), lang))


def _best_alternative(payload: dict) -> tuple[str, float | None]:
	"""jambonz reports speech under `speech`, with ranked alternatives."""
	speech = payload.get("speech") or {}
	alts = (speech.get("alternatives") or [])
	if not alts:
		return "", None
	top = alts[0] or {}
	conf = top.get("confidence")
	return (top.get("transcript") or "").strip(), conf


def _usable(transcript: str, confidence: float | None) -> bool:
	"""Is this transcript worth sending to a model?

	Two gates, both cheap, both there because of the error rates on Algerian
	Arabic. A vendor that reports no confidence passes the second - refusing
	those would make the adapter silent with half the recognisers jambonz
	supports - but never the first.
	"""
	if len(transcript.split()) < _MIN_WORDS:
		return False
	if confidence is not None and confidence < _MIN_CONFIDENCE:
		return False
	return True


def _history(payload: dict) -> list[dict]:
	"""Conversation so far, as jambonz hands it back.

	jambonz does not carry application state between hooks, so the adapter
	keeps it in the call's customerData if the platform returns it, and starts
	fresh otherwise. A dropped history costs a repeated question; storing
	callers' speech in the database to avoid that would cost their privacy.
	"""
	raw = (payload.get("customerData") or {}).get("ziri_history")
	if not isinstance(raw, list):
		return []
	out = []
	for m in raw[-(_MAX_TURNS * 2):]:
		if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
			content = str(m.get("content") or "")[:2000]
			out.append({"role": m["role"], "content": content})
	return out
