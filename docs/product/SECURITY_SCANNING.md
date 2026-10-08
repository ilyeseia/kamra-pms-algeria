# Security scanning

What is scanned automatically, what is not, and who is responsible for the
gap. `.github/workflows/security.yml` implements the first part; this document
exists because the second part is the one that gets forgotten.

---

## 1. What runs, and when

| Scan | Covers | Runs | Fails the build |
| --- | --- | --- | --- |
| **gitleaks** | Every commit in the full history | push, PR, Monday 06:00 UTC | **Yes** |
| **npm audit** | `frontend/` — 5 runtime, 9 dev dependencies, from the lockfile | push, PR, weekly | On **high or critical in a SHIPPED dependency** |
| **pip-audit** | The installed bench environment (frappe and its tree) | push, PR, weekly | No — reported as a warning |

The weekly run is not redundant. An advisory published tonight makes
yesterday's green build unsafe without anyone touching the code, and that is
the case a push-triggered scan cannot catch.

---

## 2. Why not everything fails the build

A scan that fails on every transitive advisory is switched off within a week,
and then the one that mattered is missed too. This is the same reasoning
`kamra/monitoring.py` is built on, applied to a different alarm.

- **A committed secret fails, always.** There is no triage to do and no
  severity to weigh: a credential in git history is published, and rotating it
  is the only remedy.
- **Dependency advisories are reported in full and gate on high or critical
  in something that is actually shipped.** Every run uploads the complete JSON
  as an artifact for 30 days, so a finding below the gate is readable without
  being one.

### The measurement that set the gate

This was decided by running the scan, not by picking a threshold. On
2026-10-08 the frontend had **two high advisories, and both are
devDependencies**:

| Package | Severity | Where | Runs on a hotel's server |
| --- | --- | --- | --- |
| `sharp` | high | devDependency, direct | No — build-time image resizing |
| `source-map-js` | high | devDependency, transitive | No — source map parsing |

A gate on `--audit-level=high` alone would have failed this build on the day
it was added, for code that is not in the product. That gate gets switched
off, and the one that mattered goes with it.

So the gate is `--audit-level=high --omit=dev`. Development advisories still
run on a developer's machine and in CI, so they are reported as a warning
annotation rather than dropped.

---

## 3. What is NOT scanned, and whose job it is

### 3.1 The container image — the real gap

**There is no Containerfile in this repository.** `deploy/install.sh` clones
`frappe/frappe_docker` on the customer's own server and builds the image there
at install time, pinned to a commit SHA.

So there is nothing here for a container scanner to read. Adding one would
produce a passing check that means nothing, which is worse than an absent one,
because a green tick is read as "scanned".

**The gap is real and belongs to whoever runs the install.** The image carries
Debian, Python, Node and nginx, and those accumulate advisories whether or not
this repository changes. On the host that built it:

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image --severity HIGH,CRITICAL kamra:v1.0.0
```

Run it after every image build, and before an image goes to a hotel. Nothing
in CI can do this for you.

### 3.2 The frappe_docker pin

`deploy/install.sh` pins frappe_docker to a SHA. That is correct for
reproducibility and it means the build does not pick up upstream fixes either.
Reviewing the pin is a human task at each release, not a scan.

### 3.3 MariaDB and Redis images

`deploy/linux/docker-compose.yml` pins `mariadb:11.8` and a Redis tag. Same
position as 3.1: scanned on the host, not here.

### 3.4 What the scans cannot see at all

- Logic flaws. `semgrep` rules exist for two Frappe-specific patterns
  (`frappe-setuser`, `frappe-manual-commit`) and are enforced by
  `kamra/scripts/marketplace_install_check.py`, but that is a narrow net.
- Prompt injection against the agents. Mitigated in code
  (`kamra/assistant.py`, `kamra/agent_guest.py`) and untestable by a scanner.
- Anything about how a hotel runs its own server.

---

## 4. When a scan fails

**gitleaks found a secret**

1. Treat it as published. Rotate the credential first, before anything else.
2. Then remove it from history. Rewriting published history is disruptive;
   rotating is not optional either way.
3. Record what was exposed and for how long.

**npm or pip reports high or critical**

1. Read the advisory, not only the severity. A vulnerability in a build-time
   dependency that never runs in production is not the same as one in a
   runtime path.
2. If a fixed version exists, take it and run CI.
3. If it does not, record the decision — what is exposed, why the risk is
   acceptable for now, and what would change that.

A finding that is accepted should be accepted in writing. An advisory silently
ignored twice becomes an advisory nobody reads.

---

## 5. History

The full git history was scanned for GitHub tokens, OpenAI keys, AWS access
keys and PEM private keys on 2026-10-08, before this workflow was added. It
was clean. The workflow exists to keep it that way, not to clean it up.
