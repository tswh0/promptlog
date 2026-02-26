---
title: Installing Caddy & wildcard certificate via Cloudflare
date: 2026-02-26
description: How to set up Caddy as a web server, install the Cloudflare DNS plugin, and obtain an automatic wildcard TLS certificate for *.example.com.
---

# Installing Caddy & wildcard certificate via Cloudflare

Caddy is a web server that handles TLS certificates automatically via Let's Encrypt. For **wildcard certificates** (`*.example.com`) you need a DNS challenge, which is where the Cloudflare plugin comes in.

Here's how to get it running on Debian/Ubuntu.

## Prerequisites

- Debian 12 / Ubuntu 22.04+
- A domain with DNS managed through Cloudflare
- A Cloudflare API token with `Zone:Read` and `DNS:Edit` permissions

### Creating a Cloudflare API token

1. Cloudflare Dashboard → **My Profile** → **API Tokens** → *Create Token*
2. Template: **Edit zone DNS**
3. Zone Resources: pick your domain
4. Create and save the token somewhere safe

## Installing Caddy

One thing to know upfront: you need the **beta version** of Caddy. The `caddy add-package` command isn't in the stable release yet, and you'll need it to add the Cloudflare module.

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-testing-archive-keyring.gpg

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-testing.list

apt update && apt install caddy
```

Check it installed:

```bash
caddy version
# v2.11.1 h1:...
```

## Installing the Cloudflare DNS plugin

The default Caddy binary doesn't include the Cloudflare module. Add it with:

```bash
caddy add-package github.com/caddy-dns/cloudflare
```

Caddy fetches a new binary from the official build service and replaces the old one. Then restart:

```bash
systemctl restart caddy
```

Confirm the module loaded:

```bash
caddy list-modules | grep cloudflare
# dns.providers.cloudflare
```

## Configuring the Caddyfile

The config lives at `/etc/caddy/Caddyfile`. A complete example for a wildcard domain:

```caddy
{
    email your@email.com
}

# Reusable TLS snippet
(tls_wildcard) {
    tls {
        dns cloudflare YOUR_CLOUDFLARE_API_TOKEN
        resolvers 1.1.1.1
    }
}

*.example.com example.com {
    import tls_wildcard

    @blog host blog.example.com
    handle @blog {
        reverse_proxy 127.0.0.1:2346
    }

    @dash host dash.example.com
    handle @dash {
        reverse_proxy 127.0.0.1:2345
    }

    handle {
        respond "Hello!" 200
    }
}
```

The `(tls_wildcard)` block is a Caddy snippet – define the TLS config once, reuse it everywhere with `import tls_wildcard`.

### What happens on first start

Caddy sees the wildcard cert is needed and kicks off the ACME DNS challenge:

1. Caddy generates a challenge token
2. The Cloudflare plugin creates a `_acme-challenge` TXT record
3. Let's Encrypt verifies it
4. Caddy gets the certificate and stores it locally
5. The TXT record is removed

This all happens automatically, including renewal every 60 days.

## Verifying the certificate

```bash
systemctl status caddy
ls /var/lib/caddy/.local/share/caddy/certificates/
```

Or just open `https://blog.example.com` in a browser – the padlock should show a valid cert for `*.example.com`.

## Security extras

A few additions worth putting in the global config block:

```caddy
{
    servers {
        protocols tls1.2 tls1.3

        # Cloudflare IPs as trusted proxies, auto-updated
        trusted_proxies cloudflare {
            interval 12h
            timeout 15s
        }
        client_ip_headers X-Forwarded-For CF-Connecting-IP
    }
}
```

And a reusable security headers snippet:

```caddy
(security_headers) {
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }
}
```

## Conclusion

Once it's set up, you don't think about certificates again. Caddy handles issuance, renewal, and the DNS challenge entirely on its own. For a setup with multiple subdomains under one domain, a single wildcard cert is much cleaner than managing individual certs per subdomain.
