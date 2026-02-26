---
title: Caddy installieren & Wildcard-Zertifikat via Cloudflare
date: 2026-02-26
description: Wie man Caddy als Webserver einrichtet, das Cloudflare-DNS-Plugin installiert und ein automatisches Wildcard-TLS-Zertifikat für *.example.com bezieht.
---

# Caddy installieren & Wildcard-Zertifikat via Cloudflare

Caddy ist ein moderner Webserver, der TLS-Zertifikate vollautomatisch über Let's Encrypt bezieht und erneuert. Für **Wildcard-Zertifikate** (`*.example.com`) ist jedoch ein DNS-Challenge nötig – und genau dafür gibt es das offizielle Cloudflare-Plugin.

In diesem Artikel zeige ich, wie man Caddy auf einem Debian/Ubuntu-Server installiert, das Cloudflare-DNS-Modul einbindet und ein Wildcard-Zertifikat einrichtet.

## Voraussetzungen

- Ein Server mit Debian 12 / Ubuntu 22.04+
- Eine Domain, deren DNS über **Cloudflare** verwaltet wird
- Ein Cloudflare **API-Token** mit den Rechten `Zone:Read` und `DNS:Edit`

### Cloudflare API-Token erstellen

1. Cloudflare Dashboard → **My Profile** → **API Tokens** → *Create Token*
2. Template: **Edit zone DNS** wählen
3. Zone Resources: die gewünschte Domain auswählen
4. Token erstellen und sicher speichern

## Caddy installieren

Caddy wird über das offizielle APT-Repository installiert. Wichtig: Es muss die **Beta-Version** verwendet werden, da der `caddy add-package`-Befehl (zum Nachladen von Modulen) in der Stable-Version noch nicht enthalten ist.

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-testing-archive-keyring.gpg

curl -1sLf 'https://dl.cloudsmith.io/public/caddy/testing/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-testing.list

apt update && apt install caddy
```

Version prüfen:

```bash
caddy version
# v2.11.1 h1:...
```

## Cloudflare-DNS-Plugin installieren

Das Standard-Caddy-Binary enthält das Cloudflare-Modul nicht. Es muss nachträglich hinzugefügt werden – Caddy baut sich dafür automatisch ein neues Binary über den offiziellen Build-Service:

```bash
caddy add-package github.com/caddy-dns/cloudflare
```

Caddy lädt das neue Binary herunter und ersetzt das alte. Danach Dienst neu starten:

```bash
systemctl restart caddy
```

Modul prüfen:

```bash
caddy list-modules | grep cloudflare
# dns.providers.cloudflare
```

## Caddyfile konfigurieren

Die Konfiguration liegt unter `/etc/caddy/Caddyfile`. Hier ein vollständiges Beispiel für eine Wildcard-Domain mit Cloudflare DNS-Challenge:

```caddy
{
    # Globale Optionen
    email deine@email.de
}

# Wildcard-Zertifikat für *.example.com und example.com
(tls_wildcard) {
    tls {
        dns cloudflare DEIN_CLOUDFLARE_API_TOKEN
        resolvers 1.1.1.1
    }
}

*.example.com example.com {
    import tls_wildcard

    # Routing per Subdomain
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

Das `(tls_wildcard)`-Snippet ist ein **Caddy-Snippet** (wiederverwendbarer Block), der mit `import tls_wildcard` eingebunden wird. So muss die TLS-Konfiguration nur einmal definiert werden.

### Was passiert beim ersten Start?

Caddy erkennt, dass ein Wildcard-Zertifikat benötigt wird, und startet automatisch den **ACME DNS-Challenge**:

1. Caddy generiert einen Challenge-Token
2. Das Cloudflare-Plugin legt einen `_acme-challenge` TXT-Record in der DNS-Zone an
3. Let's Encrypt verifiziert den Record
4. Caddy erhält das Wildcard-Zertifikat und speichert es lokal
5. Der TXT-Record wird wieder gelöscht

Das alles passiert vollautomatisch – auch bei der Erneuerung alle 60 Tage.

## Zertifikat prüfen

```bash
# Caddy-Status
systemctl status caddy

# Gespeicherte Zertifikate anzeigen
ls /var/lib/caddy/.local/share/caddy/certificates/
```

Oder einfach im Browser: Das Schloss-Symbol bei `https://blog.example.com` zeigt ein gültiges Zertifikat für `*.example.com`.

## Sicherheits-Extras

Ein paar empfehlenswerte Ergänzungen für die globale Caddy-Konfiguration:

```caddy
{
    servers {
        # Nur TLS 1.2+
        protocols tls1.2 tls1.3

        # Cloudflare-IPs als vertrauenswürdige Proxies (automatisch aktualisiert)
        trusted_proxies cloudflare {
            interval 12h
            timeout 15s
        }
        client_ip_headers X-Forwarded-For CF-Connecting-IP
    }
}
```

```caddy
# Security-Header Snippet
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

## Fazit

Caddy macht TLS-Zertifikate zur Selbstverständlichkeit. Mit dem Cloudflare-Plugin ist auch ein Wildcard-Zertifikat für alle Subdomains in wenigen Minuten eingerichtet – vollautomatisch, ohne manuelle Erneuerung. Für alle, die mehrere Dienste unter einer Domain betreiben, ist das die eleganteste Lösung.
