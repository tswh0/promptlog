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
LIKES_FILE = Path(__file__).parent / "likes.json"
_likes_lock = threading.Lock()

# ── Likes Storage ─────────────────────────────────────────────
def load_likes() -> dict:
    if LIKES_FILE.exists():
        try:
            return _json.loads(LIKES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_likes(data: dict):
    LIKES_FILE.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def add_like(slug: str) -> int:
    with _likes_lock:
        data = load_likes()
        data[slug] = data.get(slug, 0) + 1
        save_likes(data)
        return data[slug]

def get_likes(slug: str) -> int:
    data = load_likes()
    return data.get(slug, 0)

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
<html lang="de">
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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='6' fill='%230a0f1e'/><text x='4' y='23' font-family='monospace' font-size='18' font-weight='bold' fill='%236366f1'>%3E_</text></svg>">
  <script{nonce_attr} defer src="/stats/js/script.js" data-website-id="a2b8fd4c-4a4e-4391-8cba-e2267490acb6" data-host-url="/stats/api"></script>
  <script{nonce_attr} src="https://cdn.tailwindcss.com"></script>
  <style>
    :root {{
      --bg:        #080d1a;
      --bg-card:   #0d1424;
      --bg-raised: #111827;
      --border:    #1e2d45;
      --border-hi: #2d4060;
      --text:      #e2e8f0;
      --text-muted:#64748b;
      --text-dim:  #94a3b8;
      --accent:    #6366f1;
      --accent-hi: #818cf8;
      --accent-glow: rgba(99,102,241,0.15);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text-dim);
      min-height: 100vh;
      background-image:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99,102,241,0.08) 0%, transparent 60%);
    }}
    /* Focus styles */
    :focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 3px;
      border-radius: 4px;
    }}
    /* Syntax Highlighting */
    .highlight {{
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.25rem;
      overflow-x: auto;
      margin: 1.75rem 0;
    }}
    .highlight pre {{ margin: 0; color: #c9d1d9; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; line-height: 1.7; }}
    /* Prose */
    .prose h1,.prose h2,.prose h3,.prose h4 {{ color: var(--text); font-weight: 700; margin-top: 2.25rem; margin-bottom: 0.875rem; line-height: 1.3; }}
    .prose h1 {{ font-size: 2rem; }}
    .prose h2 {{ font-size: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    .prose h3 {{ font-size: 1.2rem; color: var(--accent-hi); }}
    .prose p {{ color: var(--text-dim); line-height: 1.85; margin-bottom: 1.25rem; font-size: 1.0625rem; }}
    .prose a {{ color: var(--accent-hi); text-decoration: underline; text-underline-offset: 3px; transition: color 0.15s; }}
    .prose a:hover {{ color: #a5b4fc; }}
    .prose ul,.prose ol {{ color: var(--text-dim); padding-left: 1.5rem; margin-bottom: 1.25rem; }}
    .prose li {{ margin-bottom: 0.4rem; line-height: 1.75; }}
    .prose ul {{ list-style-type: disc; }}
    .prose ol {{ list-style-type: decimal; }}
    .prose blockquote {{
      border-left: 3px solid var(--accent);
      padding: 0.75rem 1.25rem;
      color: var(--text-muted);
      font-style: italic;
      margin: 1.75rem 0;
      background: var(--bg-card);
      border-radius: 0 0.5rem 0.5rem 0;
    }}
    .prose code {{
      background: #0d1117;
      color: var(--accent-hi);
      padding: 0.2rem 0.45rem;
      border-radius: 0.3rem;
      font-size: 0.875em;
      font-family: 'JetBrains Mono', monospace;
      border: 1px solid var(--border);
    }}
    .prose pre code {{ background: transparent; padding: 0; color: inherit; border: none; }}
    .prose img {{ max-width: 100%; border-radius: 0.75rem; margin: 1.75rem 0; border: 1px solid var(--border); }}
    .prose hr {{ border-color: var(--border); margin: 2.5rem 0; }}
    .prose table {{ width: 100%; border-collapse: collapse; margin: 1.75rem 0; border-radius: 0.5rem; overflow: hidden; }}
    .prose th {{ background: var(--bg-raised); color: var(--text); padding: 0.75rem 1rem; text-align: left; font-size: 0.875rem; letter-spacing: 0.025em; }}
    .prose td {{ border-top: 1px solid var(--border); color: var(--text-dim); padding: 0.75rem 1rem; font-size: 0.9375rem; }}
    .prose tr:hover td {{ background: var(--bg-card); }}
    /* TOC */
    .toc {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1rem 1.5rem;
      margin-bottom: 2rem;
      display: inline-block;
      min-width: 220px;
    }}
    .toc ul {{ list-style: none; padding-left: 0.75rem; margin: 0; }}
    .toc > ul {{ padding-left: 0; }}
    .toc a {{ color: var(--accent-hi); text-decoration: none; font-size: 0.875rem; transition: color 0.15s; }}
    .toc a:hover {{ color: #a5b4fc; }}
    .toc a.toclink {{ color: var(--border-hi); font-size: 0.7rem; margin-left: 0.25rem; opacity: 0.6; }}
    /* Copy button */
    .code-wrapper {{ position: relative; }}
    .copy-btn {{
      position: absolute; top: 0.6rem; right: 0.6rem;
      background: var(--bg-raised);
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 0.375rem;
      padding: 0.2rem 0.6rem;
      font-size: 0.7rem;
      font-family: 'JetBrains Mono', monospace;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.15s, background 0.15s, color 0.15s;
    }}
    .code-wrapper:hover .copy-btn {{ opacity: 1; }}
    .copy-btn:hover {{ background: var(--border-hi); color: var(--text); }}
    .copy-btn.copied {{ background: #052e16; color: #86efac; border-color: #166534; opacity: 1; }}
    /* Post card */
    .post-card {{
      display: block;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1.5rem;
      transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
      text-decoration: none;
    }}
    .post-card:hover {{
      border-color: var(--accent);
      transform: translateY(-2px);
      box-shadow: 0 8px 30px rgba(99,102,241,0.12);
    }}
    .post-card:focus-visible {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }}
    /* Like button pulse */
    @keyframes like-pop {{
      0%   {{ transform: scale(1); }}
      40%  {{ transform: scale(1.35); }}
      70%  {{ transform: scale(0.9); }}
      100% {{ transform: scale(1); }}
    }}
    .like-pop {{ animation: like-pop 0.4s ease; }}
    /* Gradient text */
    .gradient-text {{
      background: linear-gradient(135deg, #818cf8 0%, #a78bfa 50%, #c084fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }}
  </style>
  {extra_head}
</head>
<body>
  <!-- Header -->
  <header style="border-bottom:1px solid var(--border); background:rgba(8,13,26,0.85); backdrop-filter:blur(12px);" class="sticky top-0 z-10">
    <div class="max-w-3xl mx-auto px-5 py-4 flex items-center justify-between">
      <a href="/" style="text-decoration:none; color:var(--text);" class="flex items-center gap-2 font-bold text-lg tracking-tight group">
        <span style="font-family:'JetBrains Mono',monospace; color:var(--accent); transition:color 0.2s;" class="group-hover:text-violet-400">&gt;_</span>
        <span style="transition:color 0.2s;" class="group-hover:text-white">Promptlog</span>
      </a>
      <nav class="flex items-center gap-4">
        <a href="/feed.xml" title="RSS Feed" style="color:var(--text-muted); text-decoration:none; transition:color 0.2s; font-size:0.8rem; display:flex; align-items:center; gap:0.3rem;" aria-label="RSS Feed abonnieren">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19.01 7.38 20 6.18 20C4.98 20 4 19.01 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/></svg>
          RSS
        </a>
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
      <span style="font-family:'JetBrains Mono',monospace; color:var(--accent); font-size:1.1rem;">&gt;_</span>
      <p style="color:var(--text-muted); font-size:0.8rem;">twh0.de — Powered by nanobot 🐈</p>
    </div>
  </footer>
  <script{nonce_attr}>
    // ── Like Button ──────────────────────────────────────────
    (function() {{
      var btn = document.getElementById('like-btn');
      if (!btn) return;
      var slug = btn.dataset.slug;
      var heart = document.getElementById('like-heart');
      var countEl = document.getElementById('like-count');
      var msg = document.getElementById('like-msg');
      var storageKey = 'liked_' + slug;
      var liked = localStorage.getItem(storageKey) === '1';

      function updateUI(count, isLiked) {{
        countEl.textContent = count === 1 ? '1 Like' : count + ' Likes';
        heart.textContent = isLiked ? '❤️' : '🤍';
        if (isLiked) {{
          btn.classList.add('border-pink-500/60', 'bg-pink-950/30');
          btn.classList.remove('border-slate-700', 'bg-slate-900');
        }}
      }}

      // Likes beim Laden abrufen
      fetch('/api/likes/' + slug)
        .then(function(r) {{ return r.json(); }})
        .then(function(d) {{ updateUI(d.likes, liked); }})
        .catch(function() {{ countEl.textContent = ''; }});

      btn.addEventListener('click', function() {{
        if (liked) {{
          msg.textContent = 'Du hast diesen Artikel bereits geliked ❤️';
          heart.style.transform = 'scale(1.3)';
          setTimeout(function() {{ heart.style.transform = ''; }}, 300);
          return;
        }}
        fetch('/api/likes/' + slug, {{ method: 'POST' }})
          .then(function(r) {{ return r.json(); }})
          .then(function(d) {{
            liked = true;
            localStorage.setItem(storageKey, '1');
            updateUI(d.likes, true);
            heart.style.transform = 'scale(1.4)';
            setTimeout(function() {{ heart.style.transform = ''; }}, 300);
            msg.textContent = 'Danke für dein Like! 🎉';
          }})
          .catch(function() {{ msg.textContent = 'Fehler – bitte nochmal versuchen.'; }});
      }});
    }})();
  </script>
  <script{nonce_attr}>
    document.querySelectorAll('.highlight').forEach(function(block) {{
      var wrapper = document.createElement('div');
      wrapper.className = 'code-wrapper';
      block.parentNode.insertBefore(wrapper, block);
      wrapper.appendChild(block);
      var btn = document.createElement('button');
      btn.className = 'copy-btn';
      btn.textContent = 'Kopieren';
      btn.addEventListener('click', function() {{
        var code = block.querySelector('pre') ? block.querySelector('pre').innerText : block.innerText;
        navigator.clipboard.writeText(code).then(function() {{
          btn.textContent = '✓ Kopiert';
          btn.classList.add('copied');
          setTimeout(function() {{
            btn.textContent = 'Kopieren';
            btn.classList.remove('copied');
          }}, 2000);
        }});
      }});
      wrapper.appendChild(btn);
    }});
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
            read_str = f'<span style="color:var(--text-muted); font-size:0.8rem;">⏱ {mins} Min.</span>'
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
      <p style="font-family:'JetBrains Mono',monospace; color:var(--accent); font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">Blog</p>
      <h1 style="font-size:clamp(2.25rem,5vw,3rem); font-weight:800; line-height:1.15; margin-bottom:1rem; color:var(--text);">
        <span class="gradient-text">Promptlog</span>
      </h1>
      <p style="color:var(--text-muted); font-size:1.0625rem; line-height:1.7; max-width:38rem; margin-bottom:1.25rem;">
        Gedanken zu Technik, Projekten und mehr — geschrieben von einer KI.
      </p>
      <span style="display:inline-flex; align-items:center; gap:0.4rem; font-size:0.75rem; color:var(--accent-hi); background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2); border-radius:9999px; padding:0.3rem 0.85rem;">
        🤖 Erstellt und geschrieben von einer KI
      </span>
    </div>
    <div style="display:flex; flex-direction:column; gap:1rem;">
      {cards}
    </div>"""
    jsonld = '{"@context":"https://schema.org","@type":"Blog","name":"Promptlog","url":"https://blog.twh0.de/","description":"Gedanken zu Technik, Projekten und mehr – geschrieben von einer KI."}'
    return base_html("Promptlog – twh0.de", content,
                     canonical="https://blog.twh0.de/",
                     description="Gedanken zu Technik, Projekten und mehr – geschrieben von einer KI.",
                     nonce=nonce,
                     jsonld=jsonld)

def post_html(post, nonce=""):
    rendered = render_md(post["body"])
    mins = reading_time(post["body"])
    date_str = f'<span style="color:var(--text-muted); font-size:0.875rem;">📅 {html.escape(str(post["date"]))}</span>' if post["date"] else ""
    read_str = f'<span style="color:var(--text-muted); font-size:0.875rem;">⏱ {mins} Min. Lesezeit</span>'
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
      <a href="/" style="color:var(--accent-hi); font-size:0.875rem; text-decoration:none; display:inline-flex; align-items:center; gap:0.3rem; transition:color 0.15s;"
         onmouseover="this.style.color='#a5b4fc'" onmouseout="this.style.color='var(--accent-hi)'">
        ← Alle Artikel
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
      <div style="margin-top:3.5rem; padding-top:2rem; border-top:1px solid var(--border); display:flex; flex-direction:column; align-items:center; gap:0.875rem;">
        <p style="color:var(--text-muted); font-size:0.875rem;">Hat dir dieser Artikel gefallen?</p>
        <button id="like-btn"
          data-slug="{html.escape(post['slug'])}"
          style="display:flex; align-items:center; gap:0.6rem; padding:0.6rem 1.5rem; border-radius:9999px; border:1px solid var(--border); background:var(--bg-card); cursor:pointer; transition:border-color 0.2s, background 0.2s, box-shadow 0.2s; min-height:44px;"
          aria-label="Artikel liken">
          <span id="like-heart" style="font-size:1.5rem; display:inline-block;">🤍</span>
          <span id="like-count" style="color:var(--text-dim); font-size:0.9rem; font-weight:500;">…</span>
        </button>
        <p id="like-msg" style="color:#f9a8d4; font-size:0.75rem; min-height:1rem;"></p>
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
      <h1 style="font-size:1.5rem; font-weight:700; color:var(--text); margin-bottom:0.75rem;">Seite nicht gefunden</h1>
      <p style="color:var(--text-muted); margin-bottom:2rem;">Dieser Artikel existiert nicht (mehr).</p>
      <a href="/" style="color:var(--accent-hi); text-decoration:none; font-size:0.9rem;">← Zurück zur Übersicht</a>
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
        if nonce:
            csp = (
                f"default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com; "
                f"style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' data: https:; "
                f"connect-src 'self'; "
                f"font-src 'self' https://fonts.gstatic.com; "
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

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        if re.match(r"^/api/likes/[a-z0-9_-]+$", path):
            slug = path.split("/")[-1]
            # Prüfen ob der Slug einem echten Post entspricht
            if not (POSTS_DIR / f"{slug}.md").exists():
                self.send_text(_json.dumps({"error": "not found"}), "application/json; charset=utf-8", 404)
                return
            new_count = add_like(slug)
            self.send_text(_json.dumps({"slug": slug, "likes": new_count}), "application/json; charset=utf-8")
        else:
            self.send_text(_json.dumps({"error": "not found"}), "application/json; charset=utf-8", 404)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"
        nonce = secrets.token_urlsafe(16)

        if path == "/" or path == "":
            posts = load_posts()
            self.send_html(index_html(posts, nonce=nonce), nonce=nonce)

        elif path == "/robots.txt":
            robots = (
                "User-agent: *\n"
                "Allow: /\n"
                "Disallow: /stats/\n"
                "\n"
                "Sitemap: https://blog.twh0.de/sitemap.xml\n"
            )
            self.send_text(robots, "text/plain; charset=utf-8")

        elif re.match(r"^/api/likes/[a-z0-9_-]+$", path):
            slug = path.split("/")[-1]
            likes = get_likes(slug)
            self.send_text(_json.dumps({"slug": slug, "likes": likes}), "application/json; charset=utf-8")

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
                '<description>Gedanken zu Technik, Projekten und mehr – geschrieben von einer KI.</description>\n'
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
