---
title: How This Blog Was Built – A Minimal Python Blog Server
date: 2026-02-26
description: No CMS, no framework – just Python, Markdown, and Caddy. How I built a lean blog in under an hour.
---

# How This Blog Was Built – A Minimal Python Blog Server

Sometimes less is more. Instead of installing WordPress, Ghost, or another CMS, I wanted something simple: drop in Markdown files, done. No admin panel, no database, no overhead.

The result is this blog – built by my AI assistant **nanobot** in under an hour.

## The Idea

The concept is straightforward:

1. Blog posts are stored as `.md` files in the `posts/` directory
2. A Python server reads these files, parses them, and renders them to HTML
3. Caddy serves the blog at `blog.twh0.de` with HTTPS

No database. No build pipeline. No deployment process. Just create a new `.md` file – and the article is live.

## The Architecture

### Directory Structure

```
blog/
├── server.py        # The Python web server
└── posts/           # Markdown articles go here
    ├── hallo-welt.md
    └── how-this-blog-was-built.md
```

### Frontmatter

Every article starts with a YAML frontmatter block containing metadata:

```markdown
---
title: My Article
date: 2026-02-26
description: A short description for the overview page.
---

# My Article

The actual content starts here...
```

The server parses this block with a simple regex and separates it from the Markdown body.

### The Python Server

The server is built on Python's built-in `http.server` module – no external web frameworks needed. It listens on `127.0.0.1:2346` and is only accessible locally (Caddy handles public access).

The key components:

**Frontmatter parser** – reads `title`, `date`, and `description` from the YAML header:

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

**Markdown renderer** – uses the `markdown` library with useful extensions:

```python
MD = markdown.Markdown(extensions=[
    "extra",           # Tables, footnotes, etc.
    "smarty",          # Typographic quotes
    FencedCodeExtension(),   # Code blocks with ```
    CodeHiliteExtension(),   # Syntax highlighting via Pygments
    TocExtension(permalink=True),  # Table of contents
])
```

**Request handler** – two routes:
- `/` → Overview of all articles (sorted by date, newest first)
- `/<slug>` → Single article, loaded from `posts/<slug>.md`

The HTML template is defined directly in Python as an f-string – with Tailwind CSS for styling and a dark design.

### systemd Service

The blog server runs as a systemd service and starts automatically on boot:

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

### Caddy as Reverse Proxy

Caddy handles TLS (wildcard certificate via Cloudflare DNS challenge), HTTPS redirects, security headers, and forwards requests for `blog.twh0.de` to the local Python server. I explain how to install Caddy and set up a wildcard certificate in detail in [this article](/caddy-wildcard-cert-cloudflare).

```
@blog host blog.twh0.de
handle @blog {
    reverse_proxy 127.0.0.1:2346
}
```

The wildcard certificate for `*.twh0.de` is automatically obtained and renewed by Caddy via the Cloudflare API – no manual certificate management needed.

## Writing a New Article

It's this simple:

```bash
nano /root/.nanobot/workspace/projects/blog/posts/my-article.md
```

Add frontmatter, write Markdown, save – done. The article is immediately available at `blog.twh0.de/my-article`, with no restart or build step required.

## Conclusion

The entire system consists of a single Python file (~250 lines) and a folder of Markdown files. It's fast, low-maintenance, and fully under control – no third-party CMS that needs updates or brings security vulnerabilities.

Sometimes the simplest solution is the best one. ✌️
