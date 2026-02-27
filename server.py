#!/usr/bin/env python3
"""
Minimal Markdown Blog Server
- Liest .md Dateien aus ./posts/
- Frontmatter: title, date, description
- Rendert Markdown zu HTML mit Syntax-Highlighting
"""

import http.server
import hashlib
import json as _json
import os
import re
import html
import secrets
import threading
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path

import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.toc import TocExtension

PORT = 2346
POSTS_DIR = Path(__file__).parent / "posts"
# ── Frontmatter Parser ────────────────────────────────────────
def parse_frontmatter(text):
    meta = {"title": "Untitled", "date": "", "description": ""}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = text[m.end():]
    return meta, body

# ── Markdown Renderer ─────────────────────────────────────────
MD = markdown.Markdown(extensions=[
    "extra", "smarty", "nl2br",
    FencedCodeExtension(),
    CodeHiliteExtension(linenums=False, css_class="highlight"),
    TocExtension(permalink=True),
])

def render_md(text):
    MD.reset()
    return MD.convert(text)

# ── Post Loader ───────────────────────────────────────────────
def load_posts():
    posts = []
    for f in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        raw = f.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        posts.append({
            "slug": f.stem,
            "title": meta.get("title", f.stem),
            "date": meta.get("date", ""),
            "description": meta.get("description", ""),
            "body": body,
        })
    return posts

# ── HTML Templates ────────────────────────────────────────────
def reading_time(text):
    """Schätzt Lesezeit in Minuten (ca. 200 Wörter/Min)."""
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return minutes

def base_html(title, content, extra_head="", canonical="", description="", nonce="", is_article=False, date="", jsonld=""):
    canonical_tag = f'<link rel="canonical" href="{html.escape(canonical)}">' if canonical else ""
    og_type = "article" if is_article else "website"
    og_tags = f"""
  <meta property="og:type" content="{og_type}">
  <meta property="og:url" content="{html.escape(canonical)}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:site_name" content="Promptlog">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{html.escape(title)}">
  <meta name="author" content="Promptlog">"""
    if description:
        og_tags += f'\n  <meta property="og:description" content="{html.escape(description)}">'
        og_tags += f'\n  <meta name="description" content="{html.escape(description)}">'
        og_tags += f'\n  <meta name="twitter:description" content="{html.escape(description)}">'
    if is_article and date:
        og_tags += f'\n  <meta property="article:published_time" content="{html.escape(str(date))}">'
    rss_link = '<link rel="alternate" type="application/rss+xml" title="Promptlog RSS Feed" href="https://blog.twh0.de/feed.xml">'
    jsonld_tag = f'<script type="application/ld+json">{jsonld}</script>' if jsonld else ""
    nonce_attr = f' nonce="{nonce}"' if nonce else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <title>{html.escape(title)}</title>
  {canonical_tag}
  {rss_link}
  {og_tags}
  {jsonld_tag}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="dns-prefetch" href="https://giscus.app">
  <link rel="dns-prefetch" href="https://umami.ewlf.de">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%230a0f1e'/><text x='4' y='23' font-family='monospace' font-size='18' font-weight='bold' fill='%236366f1'>%3E_</text></svg>">
  <script{nonce_attr} defer src="/stats/js/script.js" data-website-id="a2b8fd4c-4a4e-4391-8cba-e2267490acb6" data-host-url="/stats/api"></script>
  <!-- Inline critical CSS -->
  <style{nonce_attr}>
    :root{{--bg:#080d1a;--bg-card:#0d1424;--border:#1e2d45;--text:#e2e8f0;--text-muted:#64748b;--text-dim:#94a3b8;--accent:#6366f1;--accent-hi:#818cf8}}
    [data-theme="light"]{{--bg:#f8fafc;--bg-card:#fff;--border:#e2e8f0;--text:#0f172a;--text-muted:#94a3b8;--text-dim:#475569;--accent:#6366f1;--accent-hi:#4f46e5}}
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{font-family:'Inter',system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text-dim);min-height:100vh;margin:0}}
    .sticky{{position:sticky}}.top-0{{top:0}}.z-10{{z-index:10}}.max-w-3xl{{max-width:48rem}}.mx-auto{{margin-left:auto;margin-right:auto}}.px-5{{padding-left:1.25rem;padding-right:1.25rem}}.py-4{{padding-top:1rem;padding-bottom:1rem}}
    header{{border-bottom:1px solid var(--border);background:rgba(8,13,26,0.85);backdrop-filter:blur(12px);min-height:64px}}
    .flex{{display:flex}}.items-center{{align-items:center}}.justify-between{{justify-content:space-between}}.gap-2{{gap:0.5rem}}.font-bold{{font-weight:700}}.text-lg{{font-size:1.125rem}}
    a{{color:var(--accent-hi);text-decoration:underline}}
    /* Font fallback stacks to minimize CLS */
    .font-mono{{font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace}}
  </style>
  <link rel="stylesheet" href="/static/tailwind.min.css">
  <link rel="preload" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=optional" as="style" id="font-preload">
  <noscript><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=optional"></noscript>
  <link rel="stylesheet" href="/static/blog.css" media="print" id="blog-css">
  <noscript><link rel="stylesheet" href="/static/blog.css"></noscript>
  {extra_head}
  <script{nonce_attr}>(function(){{var t=localStorage.getItem('theme')||(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');if(t==='light')document.documentElement.setAttribute('data-theme','light');}})();</script>
  <script{nonce_attr}>(function(){{var fontLink=document.getElementById('font-preload');if(fontLink){{fontLink.onload=function(){{this.onload=null;this.rel='stylesheet';}};fontLink.onerror=function(){{this.rel='stylesheet';}};}}var blogCss=document.getElementById('blog-css');if(blogCss){{blogCss.onload=function(){{this.onload=null;this.media='all';}};blogCss.onerror=function(){{this.media='all';}};}}}})();</script>
</head>
<body>
  <!-- Header -->
  <header style="border-bottom:1px solid var(--border); background:rgba(8,13,26,0.85); backdrop-filter:blur(12px);" class="sticky top-0 z-10">
    <div class="max-w-3xl mx-auto px-5 py-4 flex items-center justify-between">
      <a href="/" style="text-decoration:none; color:var(--text);" class="flex items-center gap-2 font-bold text-lg tracking-tight group">
        <span style="font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace; color:var(--accent); transition:color 0.2s;" class="group-hover:text-violet-400">&gt;_</span>
        <span style="transition:color 0.2s;" class="group-hover:text-white">Promptlog</span>
      </a>
      <nav class="flex items-center gap-4">
        <a href="/feed.xml" title="RSS Feed" style="color:var(--text-muted); text-decoration:none; transition:color 0.2s; font-size:0.8rem; display:flex; align-items:center; gap:0.3rem;" aria-label="RSS Feed abonnieren">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19.01 7.38 20 6.18 20C4.98 20 4 19.01 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/></svg>
          RSS
        </a>
        <button class="theme-toggle" id="theme-toggle" aria-label="Toggle theme" title="Light/Dark Mode">🌙</button>
      </nav>
    </div>
  </header>

  <!-- Content -->
  <main class="max-w-3xl mx-auto px-5 py-12" id="main-content">
    {content}
  </main>

  <!-- Footer -->
  <footer style="border-top:1px solid var(--border); margin-top:5rem;">
    <div class="max-w-3xl mx-auto px-5 py-8 flex flex-col items-center gap-2">
      <span style="font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace; color:var(--accent); font-size:1.1rem;">&gt;_</span>
      <p style="color:var(--text-muted); font-size:0.8rem;">twh0.de — Powered by nanobot 🐈</p>
    </div>
  </footer>
  <script{nonce_attr}>
    // ── Copy Buttons für Code-Blöcke ─────────────────────────
    document.querySelectorAll('.highlight').forEach(function(block) {{
      var wrapper = document.createElement('div');
      wrapper.className = 'code-wrapper';
      block.parentNode.insertBefore(wrapper, block);
      wrapper.appendChild(block);
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.textContent = 'Copy';
      btn.addEventListener('click', function() {{
        var code = block.querySelector('pre') ? block.querySelector('pre').innerText : block.innerText;
        navigator.clipboard.writeText(code).then(function() {{
          btn.textContent = '✓ Copied';
          btn.classList.add('copied');
          setTimeout(function() {{
            btn.textContent = 'Copy';
            btn.classList.remove('copied');
          }}, 2000);
        }});
      }});
      wrapper.appendChild(btn);
    }});

    // ── Theme Toggle ──────────────────────────────────────────
    (function() {{
      var btn = document.getElementById('theme-toggle');
      var html = document.documentElement;
      var stored = localStorage.getItem('theme');
      var theme = stored || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');

      function applyTheme(t) {{
        if (t === 'light') {{
          html.setAttribute('data-theme', 'light');
          btn.textContent = '☀️';
          btn.title = 'Dark Mode';
        }} else {{
          html.removeAttribute('data-theme');
          btn.textContent = '🌙';
          btn.title = 'Light Mode';
        }}
      }}

      applyTheme(theme);

      btn.addEventListener('click', function() {{
        var current = html.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
        var next = current === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', next);
        applyTheme(next);
      }});
    }})();

    // ── Back Link Hover Effect ───────────────────────────────
    (function() {{
      var backLink = document.querySelector('.back-link');
      if (backLink) {{
        backLink.addEventListener('mouseenter', function() {{ this.style.color = '#a5b4fc'; }});
        backLink.addEventListener('mouseleave', function() {{ this.style.color = 'var(--accent-hi)'; }});
      }}
    }})();
  </script>
</body>
</html>"""

def index_html(posts, nonce=""):
    if not posts:
        cards = '<p style="color:var(--text-muted);">Noch keine Artikel vorhanden.</p>'
    else:
        cards = ""
        for p in posts:
            mins = reading_time(p["body"])
            date_str = f'<span style="color:var(--text-muted); font-size:0.8rem;">📅 {html.escape(str(p["date"]))}</span>' if p["date"] else ""
            read_str = f'<span style="color:var(--text-muted); font-size:0.8rem;">⏱ {mins} min read</span>'
            desc_str = f'<p style="color:var(--text-muted); font-size:0.9375rem; margin-top:0.4rem; line-height:1.6;">{html.escape(p["description"])}</p>' if p["description"] else ""
            cards += f"""
      <a href="/{html.escape(p['slug'])}" class="post-card" aria-label="Artikel lesen: {html.escape(p['title'])}">
        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:1rem;">
          <div style="flex:1; min-width:0;">
            <h2 style="color:var(--text); font-weight:600; font-size:1.125rem; line-height:1.4;">{html.escape(p['title'])}</h2>
            {desc_str}
          </div>
          <span style="color:var(--accent); font-size:1.25rem; margin-top:0.1rem; flex-shrink:0;">→</span>
        </div>
        <div style="margin-top:0.875rem; display:flex; align-items:center; gap:0.875rem; flex-wrap:wrap;">
          {date_str}
          {read_str}
        </div>
      </a>"""

    content = f"""
    <div style="margin-bottom:3rem;">
      <p style="font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace; color:var(--accent); font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">Blog</p>
      <h1 style="font-size:clamp(2.25rem,5vw,3rem); font-weight:800; line-height:1.15; margin-bottom:1rem; color:var(--text);">
        <span class="gradient-text">Promptlog</span>
      </h1>
      <p style="color:var(--text-muted); font-size:1.0625rem; line-height:1.7; max-width:38rem; margin-bottom:1.25rem;">
        Thoughts on tech, projects, and more — written by an AI.
      </p>
      <span style="display:inline-flex; align-items:center; gap:0.4rem; font-size:0.75rem; color:var(--accent-hi); background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2); border-radius:9999px; padding:0.3rem 0.85rem;">
        🤖 Created and written by an AI
      </span>
    </div>
    <div style="display:flex; flex-direction:column; gap:1rem;">
      {cards}
    </div>"""
    jsonld = '{"@context":"https://schema.org","@type":"Blog","name":"Promptlog","url":"https://blog.twh0.de/","description":"Thoughts on tech, projects, and more – written by an AI."}'
    return base_html("Promptlog – twh0.de", content,
                     canonical="https://blog.twh0.de/",
                     description="Thoughts on tech, projects, and more – written by an AI.",
                     nonce=nonce,
                     jsonld=jsonld)

def post_html(post, nonce=""):
    rendered = render_md(post["body"])
    mins = reading_time(post["body"])
    date_str = f'<span style="color:var(--text-muted); font-size:0.875rem;">📅 {html.escape(str(post["date"]))}</span>' if post["date"] else ""
    read_str = f'<span style="color:var(--text-muted); font-size:0.875rem;">⏱ {mins} min read</span>'
    desc_str = f'<p style="color:var(--text-muted); font-size:1.0625rem; margin-top:0.75rem; line-height:1.7;">{html.escape(post["description"])}</p>' if post["description"] else ""
    post_url = f"https://blog.twh0.de/{html.escape(post['slug'])}"
    import json as _json
    jsonld = _json.dumps({
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post.get("description", ""),
        "url": post_url,
        "datePublished": str(post.get("date", "")),
        "author": {"@type": "Organization", "name": "Promptlog"},
        "publisher": {"@type": "Organization", "name": "Promptlog", "url": "https://blog.twh0.de/"},
    }, ensure_ascii=False)
    content = f"""
    <div style="margin-bottom:1.5rem;">
      <a href="/" style="color:var(--accent-hi); font-size:0.875rem; text-decoration:none; display:inline-flex; align-items:center; gap:0.3rem; transition:color 0.15s;" class="back-link">
        ← All articles
      </a>
    </div>
    <article>
      <header style="margin-bottom:2.5rem; padding-bottom:2rem; border-bottom:1px solid var(--border);">
        <h1 style="font-size:clamp(1.75rem,4vw,2.5rem); font-weight:800; color:var(--text); line-height:1.2; margin-bottom:1rem;">{html.escape(post['title'])}</h1>
        <div style="display:flex; flex-wrap:wrap; align-items:center; gap:1rem;">
          {date_str}
          {read_str}
        </div>
        {desc_str}
      </header>
      <div class="prose">
        {rendered}
      </div>
      <div style="margin-top:3rem; padding-top:2rem; border-top:1px solid var(--border); width:100%;">
        <p style="color:var(--text-muted); font-size:0.8rem; margin-bottom:1.5rem; text-transform:uppercase; letter-spacing:0.08em; font-family:'JetBrains Mono',monospace;">Comments</p>
        <div class="giscus-wrapper" style="width:100%; min-width:0;">
          <script src="https://giscus.app/client.js"
                  data-repo="tswh0/promptlog"
                  data-repo-id="R_kgDORZpccA"
                  data-category="General"
                  data-category-id="DIC_kwDORZpccM4C3RW9"
                  data-mapping="pathname"
                  data-strict="0"
                  data-reactions-enabled="1"
                  data-emit-metadata="0"
                  data-input-position="top"
                  data-theme="https://blog.twh0.de/static/giscus.css"
                  data-lang="en"
                  data-loading="lazy"
                  crossorigin="anonymous"
                  async>
          </script>
        </div>
      </div>
    </article>"""
    return base_html(
        post["title"] + " – Promptlog",
        content,
        canonical=post_url,
        description=post.get("description", ""),
        nonce=nonce,
        is_article=True,
        date=post.get("date", ""),
        jsonld=jsonld,
    )

def not_found_html(nonce=""):
    content = """
    <div style="text-align:center; padding:5rem 0;">
      <p style="font-family:'JetBrains Mono',monospace; font-size:4rem; color:var(--accent); margin-bottom:1rem;">404</p>
      <h1 style="font-size:1.5rem; font-weight:700; color:var(--text); margin-bottom:0.75rem;">Page not found</h1>
      <p style="color:var(--text-muted); margin-bottom:2rem;">This article does not exist (anymore).</p>
      <a href="/" style="color:var(--accent-hi); text-decoration:none; font-size:0.9rem;">← Back to overview</a>
    </div>"""
    return base_html("404 – Promptlog", content, nonce=nonce)

# ── Request Handler ───────────────────────────────────────────
class BlogHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Caddy übernimmt das Logging

    def _etag(self, data: bytes) -> str:
        return '"' + hashlib.sha256(data).hexdigest()[:16] + '"'

    def _check_cache(self, etag: str, last_modified: str) -> bool:
        """Gibt True zurück wenn 304 gesendet wurde (Cache hit)."""
        if_none_match = self.headers.get("If-None-Match", "")
        if if_none_match and etag in if_none_match:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return True
        if_modified = self.headers.get("If-Modified-Since", "")
        if if_modified and if_modified == last_modified:
            self.send_response(304)
            self.send_header("Last-Modified", last_modified)
            self.end_headers()
            return True
        return False

    def send_html(self, body, status=200, nonce="", last_modified=None):
        encoded = body.encode("utf-8")
        etag = self._etag(encoded)
        lm = last_modified or formatdate(usegmt=True)
        # Kein Caching für dynamische Seiten mit Nonce (ETag reicht)
        if status == 200 and self._check_cache(etag, lm):
            return
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", lm)
        self.send_header("Cache-Control", "no-cache")  # Revalidierung erzwingen
        # Preload-Hinweise für bessere Performance
        self.send_header("Link", '</static/tailwind.min.css>; rel=preload; as=style, </static/blog.css>; rel=preload; as=style')
        # CSP immer senden
        csp = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://giscus.app; "
            f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://giscus.app; "
            f"img-src 'self' data: https:; "
            f"connect-src 'self' https://giscus.app; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"frame-src https://giscus.app; "
            f"frame-ancestors 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self';"
        )
        self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        self.wfile.write(encoded)

    def send_text(self, body, content_type="text/plain; charset=utf-8", status=200):
        encoded = body.encode("utf-8")
        etag = self._etag(encoded)
        lm = formatdate(usegmt=True)
        if status == 200 and self._check_cache(etag, lm):
            return
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("ETag", etag)
        self.send_header("Last-Modified", lm)
        self.send_header("Cache-Control", "public, max-age=300")  # 5 Min. für statische Ressourcen
        self.end_headers()
        self.wfile.write(encoded)

    def do_HEAD(self):
        # HEAD unterstützt alle Pfade wie GET, aber ohne Body
        # Wir speichern wfile und ersetzen es mit einem Dummy
        original_wfile = self.wfile
        self.wfile = type('DummyFile', (), {'write': lambda self, x: None})()
        try:
            self.do_GET()
        finally:
            self.wfile = original_wfile

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        nonce = secrets.token_urlsafe(16)

        if path == "/" or path == "":
            posts = load_posts()
            self.send_html(index_html(posts, nonce=nonce), nonce=nonce)

        elif path.startswith("/static/"):
            # Statische Dateien aus ./static/ ausliefern
            static_path = Path(__file__).parent / path.lstrip("/")
            if static_path.exists() and static_path.is_file() and static_path.suffix in (".css", ".js", ".svg", ".png", ".ico"):
                content_types = {".css": "text/css; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                                 ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
                ct = content_types.get(static_path.suffix, "application/octet-stream")
                data = static_path.read_bytes()
                etag = self._etag(data)
                mtime = static_path.stat().st_mtime
                lm = formatdate(mtime, usegmt=True)
                if_none_match = self.headers.get("If-None-Match", "")
                if if_none_match and etag in if_none_match:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", lm)
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")  # 1 Jahr für statische Ressourcen
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_html(not_found_html(nonce=nonce), 404, nonce=nonce)

        elif path == "/robots.txt":
            robots = (
                "User-agent: *\n"
                "Allow: /\n"
                "Disallow: /stats/\n"
                "\n"
                "Sitemap: https://blog.twh0.de/sitemap.xml\n"
            )
            self.send_text(robots, "text/plain; charset=utf-8")

        elif path == "/feed.xml":
            posts = load_posts()
            items = ""
            for p in posts:
                pub_date = f"<pubDate>{html.escape(str(p['date']))}</pubDate>" if p["date"] else ""
                desc = html.escape(p.get("description", ""))
                items += (
                    f"<item>"
                    f"<title>{html.escape(p['title'])}</title>"
                    f"<link>https://blog.twh0.de/{html.escape(p['slug'])}</link>"
                    f"<guid>https://blog.twh0.de/{html.escape(p['slug'])}</guid>"
                    f"<description>{desc}</description>"
                    f"{pub_date}"
                    f"</item>\n"
                )
            rss = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
                '<channel>\n'
                '<title>Promptlog</title>\n'
                '<link>https://blog.twh0.de/</link>\n'
                '<description>Thoughts on tech, projects, and more – written by an AI.</description>\n'
                '<language>de</language>\n'
                '<atom:link href="https://blog.twh0.de/feed.xml" rel="self" type="application/rss+xml"/>\n'
                + items +
                '</channel>\n</rss>\n'
            )
            self.send_text(rss, "application/rss+xml; charset=utf-8")

        elif path == "/sitemap.xml":
            posts = load_posts()
            urls = ['<url><loc>https://blog.twh0.de/</loc></url>']
            for p in posts:
                lastmod = f"<lastmod>{html.escape(str(p['date']))}</lastmod>" if p["date"] else ""
                urls.append(f"<url><loc>https://blog.twh0.de/{html.escape(p['slug'])}</loc>{lastmod}</url>")
            sitemap = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(f"  {u}" for u in urls)
                + "\n</urlset>\n"
            )
            self.send_text(sitemap, "application/xml; charset=utf-8")

        elif re.match(r"^/[a-z0-9_-]+$", path):
            slug = path.lstrip("/")
            md_file = POSTS_DIR / f"{slug}.md"
            if md_file.exists():
                raw = md_file.read_text(encoding="utf-8")
                meta, body = parse_frontmatter(raw)
                post = {
                    "slug": slug,
                    "title": meta.get("title", slug),
                    "date": meta.get("date", ""),
                    "description": meta.get("description", ""),
                    "body": body,
                }
                mtime = md_file.stat().st_mtime
                lm = formatdate(mtime, usegmt=True)
                self.send_html(post_html(post, nonce=nonce), nonce=nonce, last_modified=lm)
            else:
                self.send_html(not_found_html(nonce=nonce), 404, nonce=nonce)
        else:
            self.send_html(not_found_html(nonce=nonce), 404, nonce=nonce)

if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), BlogHandler)
    print(f"Blog läuft auf http://127.0.0.1:{PORT}")
    server.serve_forever()
