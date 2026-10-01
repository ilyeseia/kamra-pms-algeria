# Self-hosting on DigitalOcean

## Marketplace 1-Click (preferred)

When the ZIRI listing is live on the
[DigitalOcean Marketplace](https://marketplace.digitalocean.com/):

1. Create Droplet → search **ZIRI**.
2. Enter **site domain**, **admin email**, **admin password**.
3. Open `/kamra` → `/kamra/setup`.

Vendor / Packer notes live in the repo at `deploy/digitalocean/`.

## Manual (same result)

### 1. Create the server

**Droplet** → Ubuntu 24.04 → **Basic / 4 GB / 2 vCPU** (~$24/mo; 8 GB builds faster) → region near
the hotel → SSH key.

### 2. Point your domain

**A record** for `pms.yourhotel.com` → droplet IP.

### 3. Install

```bash
ssh root@<server-ip>
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=develop
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/develop/deploy/install.sh | bash
```

Three prompts: site domain, admin email, admin password. No default password.

### 4. TLS

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d pms.yourhotel.com
```

Then `/kamra/setup`. See [Quickstart](/quickstart).
