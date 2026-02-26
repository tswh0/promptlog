---
title: Wie dieser Blog entstand – ein minimaler Python-Blogserver
date: 2026-02-26
description: Kein CMS, kein Framework – nur Python, Markdown und Caddy. Wie ich in unter einer Stunde einen schlanken Blog gebaut habe.
---

# Wie dieser Blog entstand – ein minimaler Python-Blogserver

Manchmal ist weniger mehr. Statt WordPress, Ghost oder einem anderen CMS zu installieren, wollte ich etwas Einfaches: Markdown-Dateien ablegen, fertig. Kein Admin-Panel, keine Datenbank, kein Overhead.

Das Ergebnis ist dieser Blog – gebaut von meinem KI-Assistenten **nanobot** in unter einer Stunde.

## Die Idee

Das Konzept ist denkbar simpel:

1. Blogbeiträge werden als `.md`-Dateien im Ordner `posts/` abgelegt
2. Ein Python-Server liest diese Dateien, parst sie und rendert sie zu HTML
3. Caddy stellt den Blog unter `blog.twh0.de` mit HTTPS bereit

Keine Datenbank. Keine Build-Pipeline. Kein Deployment-Prozess. Einfach eine neue `.md`-Datei erstellen – und der Artikel ist live.

## Der Aufbau

### Verzeichnisstruktur

```
blog/
├── server.py        # Der Python-Webserver
└── posts/           # Hier kommen die Markdown-Artikel rein
    ├── hallo-welt.md
    └── wie-dieser-blog-entstand.md
```

### Frontmatter

Jeder Artikel beginnt mit einem YAML-Frontmatter-Block, der Metadaten enthält:

```markdown
---
title: Mein Artikel
date: 2026-02-26
description: Eine kurze Beschreibung für die Übersicht.
---

# Mein Artikel

Hier beginnt der eigentliche Inhalt...
```

Der Server parst diesen Block mit einem einfachen Regex und trennt ihn vom Markdown-Body.

### Der Python-Server

Der Server basiert auf dem eingebauten `http.server`-Modul – keine externen Web-Frameworks nötig. Er lauscht auf `127.0.0.1:2346` und ist damit nur lokal erreichbar (Caddy übernimmt den öffentlichen Zugang).

Die wichtigsten Komponenten:

**Frontmatter-Parser** – liest `title`, `date` und `description` aus dem YAML-Header:

```python
def parse_frontmatter(text):
    meta = {"title": "Untitled", "date": "", "description": ""}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    return meta, body
```

**Markdown-Renderer** – nutzt die `markdown`-Bibliothek mit nützlichen Extensions:

```python
MD = markdown.Markdown(extensions=[
    "extra",           # Tabellen, Fußnoten, etc.
    "smarty",          # Typografische Anführungszeichen
    FencedCodeExtension(),   # Code-Blöcke mit ```
    CodeHiliteExtension(),   # Syntax-Highlighting via Pygments
    TocExtension(permalink=True),  # Inhaltsverzeichnis
])
```

**Request-Handler** – zwei Routen:
- `/` → Übersicht aller Artikel (sortiert nach Datum, neueste zuerst)
- `/<slug>` → Einzelner Artikel, geladen aus `posts/<slug>.md`

Das HTML-Template ist direkt im Python-Code als f-String definiert – mit Tailwind CSS (via CDN) für das Styling und einem dunklen Design.

### systemd-Service

Der Blog-Server läuft als systemd-Service und startet automatisch beim Booten:

```ini
[Unit]
Description=twh0.de Blog Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/root/.nanobot/workspace/projects/blog
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Caddy als Reverse Proxy

Caddy übernimmt TLS (Wildcard-Zertifikat via Cloudflare DNS-Challenge), HTTPS-Weiterleitung, Security-Header und leitet Anfragen an `blog.twh0.de` an den lokalen Python-Server weiter. Wie man Caddy installiert und ein Wildcard-Zertifikat einrichtet, erkläre ich ausführlich in [diesem Artikel](/caddy-wildcard-cert-cloudflare).

```
@blog host blog.twh0.de
handle @blog {
    reverse_proxy 127.0.0.1:2346
}
```

Das Wildcard-Zertifikat für `*.twh0.de` wird automatisch von Caddy über die Cloudflare API bezogen und erneuert – kein manuelles Zertifikatsmanagement nötig.

## Einen neuen Artikel schreiben

So einfach geht's:

```bash
nano /root/.nanobot/workspace/projects/blog/posts/mein-artikel.md
```

Frontmatter einfügen, Markdown schreiben, speichern – fertig. Der Artikel ist sofort unter `blog.twh0.de/mein-artikel` erreichbar, ohne Neustart oder Build-Schritt.

## Fazit

Das ganze System besteht aus einer einzigen Python-Datei (~250 Zeilen) und einem Ordner mit Markdown-Dateien. Es ist schnell, wartungsarm und vollständig unter Kontrolle – kein Drittanbieter-CMS, das Updates braucht oder Sicherheitslücken mitbringt.

Manchmal ist die einfachste Lösung die beste. ✌️
