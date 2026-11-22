"""Self-contained HTML content for LightMq's built-in new-tab page."""

PRIVATE_START_URL="lightmq://incognito/"


def new_tab_html() -> str:
    """Return the offline new-tab page with search and common site shortcuts."""
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>New Tab - LightMq</title>
  <style>
    :root { color-scheme: dark; font-family: "Segoe UI", Arial, sans-serif; }
    * { box-sizing: border-box; }
    body {
      min-height: 100vh; margin: 0; color: #f4f6fb;
      background: radial-gradient(ellipse at 50% 38%, #203342 0, #151d26 45%, #101318 100%);
      display: grid; place-items: center; padding: 32px 20px;
    }
    main { width: min(760px, 100%); text-align: center; transform: translateY(-4vh); }
    .brand { margin: 0 0 10px; font-size: clamp(34px, 6vw, 54px); font-weight: 650; letter-spacing: -2px; }
    .brand span { color: #82aaff; }
    .subtitle { color: #aab5c4; margin: 0 0 38px; font-size: 15px; }
    .search {
      display: flex; align-items: center; gap: 12px; padding: 8px 10px 8px 20px;
      background: rgba(24, 28, 34, .94); border: 1px solid #414a57; border-radius: 18px;
      box-shadow: 0 16px 45px rgba(0, 0, 0, .28); transition: border-color .15s, box-shadow .15s;
    }
    .search:focus-within { border-color: #829cff; box-shadow: 0 0 0 3px rgba(103, 130, 255, .17), 0 16px 45px rgba(0,0,0,.28); }
    .search-icon { color: #aab5c4; font-size: 22px; }
    input { flex: 1; min-width: 0; color: #f4f6fb; background: transparent; border: 0; outline: 0; font-size: 16px; padding: 13px 0; }
    input::placeholder { color: #8792a0; }
    .search button { border: 0; border-radius: 12px; color: #111722; background: #a9c7ff; padding: 12px 19px; font-size: 14px; font-weight: 650; cursor: pointer; }
    .search button:hover { background: #c4d8ff; }
    .shortcuts { display: grid; grid-template-columns: repeat(4, minmax(90px, 1fr)); gap: 18px; max-width: 570px; margin: 38px auto 0; }
    .shortcut { color: #e9edf4; text-decoration: none; display: grid; justify-items: center; gap: 10px; padding: 12px 8px; border-radius: 16px; }
    .shortcut:hover { background: rgba(255,255,255,.08); }
    .icon { width: 54px; height: 54px; border-radius: 17px; display: grid; place-items: center; font-size: 21px; font-weight: 700; background: #293443; box-shadow: inset 0 1px rgba(255,255,255,.12); }
    .google { color: #8ab4f8; } .youtube { color: #ff6666; } .github { color: #f4f6fb; } .wiki { color: #e8edf5; }
    .label { font-size: 13px; }
    @media (max-width: 520px) { .shortcuts { grid-template-columns: repeat(2, 1fr); max-width: 330px; } main { transform: none; } }
  </style>
</head>
<body>
  <main>
    <h1 class="brand">Light<span>Mq</span></h1>
    <p class="subtitle">A fresh start for wherever you’re going.</p>
    <form class="search" onsubmit="return submitSearch(event)">
      <span class="search-icon" aria-hidden="true">⌕</span>
      <input name="q" type="search" placeholder="Search the web or enter an address" aria-label="Search the web" autofocus>
      <button type="submit">Search</button>
    </form>
    <nav class="shortcuts" aria-label="Quick links">
      <a class="shortcut" href="https://www.google.com/"><span class="icon google">G</span><span class="label">Google</span></a>
      <a class="shortcut" href="https://www.youtube.com/"><span class="icon youtube">▶</span><span class="label">YouTube</span></a>
      <a class="shortcut" href="https://github.com/"><span class="icon github">⌘</span><span class="label">GitHub</span></a>
      <a class="shortcut" href="https://www.wikipedia.org/"><span class="icon wiki">W</span><span class="label">Wikipedia</span></a>
    </nav>
  </main>
  <script>
    function submitSearch(event) {
      event.preventDefault();
      const field = event.currentTarget.elements.q;
      const value = field.value.trim();
      if (!value) return false;
      const isAddress = !/\s/.test(value) && (
        /^(https?:\/\/|localhost(?::\d+)?(?:\/|$)|127\.0\.0\.1(?::\d+)?(?:\/|$))/i.test(value) ||
        /^[\w-]+(?:\.[\w-]+)+(?:[/:?#].*)?$/i.test(value)
      );
      window.location.href = isAddress
        ? (/^https?:\/\//i.test(value) ? value : `https://${value}`)
        : `https://www.google.com/search?q=${encodeURIComponent(value)}`;
      return false;
    }
  </script>
</body>
</html>"""


def private_start_html() -> str:
    """Return an offline Incognito landing page with accurate privacy limits."""
    return r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Incognito - LightMq</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#202124;color:#e8eaed;font:16px 'Segoe UI',sans-serif;padding:24px;box-sizing:border-box}main{max-width:680px}h1{font-size:32px}p{line-height:1.6;color:#c4c7c5}.badge{color:#bdc1c6;background:#303134;border-radius:20px;padding:8px 14px;display:inline-block}.search{margin:24px 0}input{width:min(480px,65vw);padding:14px;border-radius:10px;border:1px solid #5f6368;background:#303134;color:white;font-size:16px}button{padding:14px 18px;border:0;border-radius:10px;background:#8ab4f8;color:#202124;font-weight:700}</style></head><body><main><span class="badge">◉ Incognito browsing</span><h1>You’re browsing privately</h1><p>LightMq won’t save pages you visit in this Incognito session to regular browsing history, and this session’s cookies and site storage are kept separate from normal browsing.</p><form class="search" onsubmit="event.preventDefault();let q=this.q.value.trim();if(q)location.href=/\s/.test(q)?'https://www.google.com/search?q='+encodeURIComponent(q):(/^https?:\/\//i.test(q)?q:'https://'+q)"><input name="q" placeholder="Search or enter an address" aria-label="Search or enter an address"><button>Go</button></form><p><strong>Downloads and bookmarks you choose to save remain on this device.</strong></p><p>Private browsing does not hide activity from websites, your internet provider, or an employer or network administrator. It does not provide VPN or Tor anonymity.</p></main></body></html>"""
