---
title: How this blog was built – a minimal Python blog server
date: 2026-02-26
description: No CMS, no framework – just Python, Markdown, and Caddy. How I built a lean blog in under an hour.
---

# How this blog was built – a minimal Python blog server

I wanted something simple: drop in Markdown files, done. No admin panel, no database, no WordPress to update every three weeks.

The result is this blog, built by my AI assistant **nanobot** in under an hour.

## The idea

1. Blog posts live as `.md` files in the `posts/` directory
2. A Python server reads them, parses them, and renders HTML
3. Caddy serves the blog at `blog.twh0.de` with HTTPS

No database. No build pipeline. Create a `.md` file – the article is live.

## The architecture

### Directory structure

```
blog/
├── server.py        # The Python web server
└── posts/           # Markdown articles go here
    └── how-this-blog-was-built.md
```

### Frontmatter

Every article starts with a YAML frontmatter block:

```markdown
---
title: My Article
date: 2026-02-26
description: A short description for the overview page.
---

# My Article

Content starts here...
```

The server parses this with a regex and separates it from the Markdown body.

### The Python server

Built on Python's built-in `http.server` – no web framework needed. It listens on `127.0.0.1:2346`, local-only (Caddy handles the public side).

Frontmatter parser:

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

Markdown renderer with syntax highlighting:

```python
MD = markdown.Markdown(extensions=[
    "extra",
    "smarty",
    FencedCodeExtension(),
    CodeHiliteExtension(),
    TocExtension(permalink=True),
])
```

Two routes:
- `/` → article list, sorted by date
- `/<slug>` → single article from `posts/<slug>.md`

The HTML template is an f-string in Python, styled with Tailwind CSS.

### systemd service

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

### Caddy as reverse proxy

Caddy handles TLS, HTTPS redirects, and security headers, then forwards `blog.twh0.de` to the local server. How to set up the wildcard certificate is covered in [this article](/caddy-wildcard-cert-cloudflare).

```
@blog host blog.twh0.de
handle @blog {
    reverse_proxy 127.0.0.1:2346
}
```

## Writing a new article

```bash
nano /root/.nanobot/workspace/projects/blog/posts/my-article.md
```

Add frontmatter, write Markdown, save. The article is live at `blog.twh0.de/my-article` immediately – no restart, no build step.

## Conclusion

The whole thing is one Python file (~250 lines) and a folder of Markdown files. Fast, low-maintenance, no third-party CMS to babysit.

Sometimes the boring solution is the right one. ✌️
