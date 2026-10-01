# Self-hosting on Hostinger

Best path for a cheap VPS. The software stays free; Hostinger bills you
for the server.

## 1. Create the server

Open **[hostinger.com](https://www.hostinger.com/)**, go to **VPS** and
pick **KVM 2**
(2 vCPU / 8 GB). For the operating system choose
**Ubuntu 24.04 with Docker** (plain Ubuntu 24.04 also works — the installer
adds Docker). Set a root password or SSH key and note the IP.

## 2. Point your domain

**A record** for `pms.yourhotel.com` → the server IP. (Cloudflare: DNS only
while issuing SSL.)

## 3. Install ZIRI (one paste)

In hPanel open the VPS → **Browser terminal** (or `ssh root@<server-ip>`)
and paste:

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=develop
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/develop/deploy/install.sh | bash
```

Answer three prompts: **site domain**, **admin email**, **admin password**.
There is no default password. The installer builds ZIRI on the VPS —
allow 20–45 minutes the first time.

## 4. TLS + sign in

Put nginx (or Hostinger's proxy) in front of port `8080`, then:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Open `https://pms.yourhotel.com/kamra`, sign in as **Administrator** with the
password you set, then **`/kamra/setup`**.

Updating later: `sudo /opt/kamra/install.sh update`.

Full detail: [Quickstart](/quickstart) · [production checklist](/self-hosting/#after-install-production-checklist).
