---
title: Installing Caddy & Wildcard Certificate via Cloudflare
date: 2026-02-26
description: How to set up Caddy as a web server, install the Cloudflare DNS plugin, and obtain an automatic wildcard TLS certificate for *.example.com.
---

# Installing Caddy & Wildcard Certificate via Cloudflare

Caddy is a modern web server that automatically obtains and renews TLS certificates via Let's Encrypt. For **wildcard certificates** (`*.example.com`), however, a DNS challenge is required – and that's exactly what the official Cloudflare plugin is for.

In this article I'll show you how to install Caddy on a Debian/Ubuntu server, add the Cloudflare DNS module, and set up a wildcard certificate.

## Prerequisites

- A server running Debian 12 / Ubuntu 22.04+
- A domain whose DNS is managed via **Cloudflare**
- A Cloudflare **API token** with `Zone:Read` and `DNS:Edit` permissions

### Creating a Cloudflare API Token

1. Cloudflare Dashboard → **My Profile** → **API Tokens** → *Create Token*
2. Template: select **Edit zone DNS**
3. Zone Resources: select the desired domain
4. Create the token and store it securely

## Installing Caddy

Caddy is installed via the official APT repository. Important: you must use the **beta version**, since the `caddy add-package` command (for loading additional modules) is not yet available in the stable release.

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-testing-archive-keyring.gpg

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-testing.list

apt update && apt install caddy
```

Check the version:

```bash
caddy version
# v2.11.1 h1:...
```

## Installing the Cloudflare DNS Plugin

The standard Caddy binary does not include the Cloudflare module. It needs to be added afterwards – Caddy automatically builds a new binary for this via the official build service:

```bash
caddy add-package github.com/caddy-dns/cloudflare
```

Caddy downloads the new binary and replaces the old one. Then restart the service:

```bash
systemctl restart caddy
```

Verify the module:

```bash
caddy list-modules | grep cloudflare
# dns.providers.cloudflare
```

## Configuring the Caddyfile

The configuration lives at `/etc/caddy/Caddyfile`. Here's a complete example for a wildcard domain with Cloudflare DNS challenge:

```caddy
{
    # Global options
    email your@email.com
}

# Wildcard certificate for *.example.com and example.com
(tls_wildcard) {
    tls {
        dns cloudflare YOUR_CLOUDFLARE_API_TOKEN
        resolvers 1.1.1.1
    }
}

*.example.com example.com {
    import tls_wildcard

    # Routing by subdomain
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

The `(tls_wildcard)` snippet is a **Caddy snippet** (a reusable block) that gets included with `import tls_wildcard`. This way the TLS configuration only needs to be defined once.

### What Happens on First Start?

Caddy detects that a wildcard certificate is needed and automatically initiates the **ACME DNS challenge**:

1. Caddy generates a challenge token
2. The Cloudflare plugin creates a `_acme-challenge` TXT record in the DNS zone
3. Let's Encrypt verifies the record
4. Caddy receives the wildcard certificate and stores it locally
5. The TXT record is deleted again

All of this happens fully automatically – including renewal every 60 days.

## Verifying the Certificate

```bash
# Caddy status
systemctl status caddy

# Show stored certificates
ls /var/lib/caddy/.local/share/caddy/certificates/
```

Or simply in the browser: the padlock icon at `https://blog.example.com` shows a valid certificate for `*.example.com`.

## Security Extras

A few recommended additions to the global Caddy configuration:

```caddy
{
    servers {
        # TLS 1.2+ only
        protocols tls1.2 tls1.3

        # Cloudflare IPs as trusted proxies (automatically updated)
        trusted_proxies cloudflare {
            interval 12h
            timeout 15s
        }
        client_ip_headers X-Forwarded-For CF-Connecting-IP
    }
}
```

```caddy
# Security headers snippet
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

Caddy makes TLS certificates effortless. With the Cloudflare plugin, a wildcard certificate covering all subdomains is set up in minutes – fully automatic, with no manual renewal. For anyone running multiple services under one domain, this is the most elegant solution.
