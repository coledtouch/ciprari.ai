#!/usr/bin/env python3
"""
changelog.ciprari.ai generator — v2
Git-commit-timeline homepage, CRT-framed art, newsletter, full SEO.
Posts live in posts_a.py (back-catalog) and posts_b.py (recent).
Run:  python3 build_blog.py
"""
import os, sys, html, datetime, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from posts_a import POSTS_A
from posts_b import POSTS_B

OUT  = os.environ.get("BLOG_OUT", os.path.join(os.path.dirname(HERE), "changelog-site"))
BASE = "https://changelog.ciprari.ai"
API  = "https://coleos-api.coleciprari.workers.dev"

POSTS = sorted(POSTS_A + POSTS_B, key=lambda p: p["date"], reverse=True)
BY_SLUG = {p["slug"]: p for p in POSTS}

def esc(s): return html.escape(s, quote=False)

def crosslink(body):
    """{link:slug|text} -> <a href="/slug">text</a> (clean URL), validated."""
    def rep(m):
        slug, text = m.group(1), m.group(2)
        if slug not in BY_SLUG:
            raise SystemExit(f"BROKEN CROSSLINK: {slug}")
        return f'<a href="/{slug}">{text}</a>'
    return re.sub(r"\{link:([a-z0-9\-]+)\|([^}]+)\}", rep, body)

CSS = """
:root{--bg:#070d0a;--panel:#0a120d;--bezel:#131c15;--ink:#8fffc4;--dim:#4fae7c;--mut:#2d6b4a;
--hot:#33ff66;--amber:#ffd75e;--line:#123c28;--panel2:#0c1710;--mono:'Cascadia Code','JetBrains Mono',Consolas,'SF Mono',Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg);scroll-behavior:smooth}
body{font-family:var(--mono);color:var(--ink);line-height:1.75;font-size:15px;
background:radial-gradient(1200px 500px at 50% -10%,rgba(var(--glow),.06),transparent 60%),
repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 3px),var(--bg);min-height:100vh}
.wrap{max-width:920px;margin:0 auto;padding:34px 20px 80px}
a{color:var(--hot);text-decoration:none}a:hover{text-decoration:underline}
.crumb{color:var(--mut);font-size:12.5px;margin-bottom:26px;display:flex;gap:14px;flex-wrap:wrap}
.crumb a{color:var(--dim)}
header.masthead{border:1px solid var(--line);background:var(--panel);padding:22px 24px;margin-bottom:30px;position:relative}
header.masthead:before{content:"● ● ●";position:absolute;top:8px;right:14px;color:var(--mut);font-size:10px;letter-spacing:3px}
.prompt{color:var(--mut);font-size:13px}
h1.site{font-size:30px;color:var(--hot);letter-spacing:1px;margin:6px 0 4px;text-shadow:0 0 18px rgba(var(--glow),.35)}
.tag{color:var(--dim);font-size:13.5px}
.cur{display:inline-block;width:9px;height:17px;background:var(--hot);vertical-align:-2px;animation:bl 1.1s steps(1) infinite}
@keyframes bl{50%{opacity:0}}
/* ---- CRT monitor frame ---- */
.crt{display:block;background:var(--bezel);border:1px solid var(--line);border-radius:8px;padding:10px 10px 6px;position:relative;box-shadow:0 4px 24px rgba(0,0,0,.5)}
.crt .screen{display:block;background:#04120a;border:1px solid #0c2417;border-radius:4px;overflow:hidden;position:relative}
.crt .screen svg{display:block;width:100%;height:auto}
.crt .screen svg{display:block;width:100%;height:auto}
.crt .screen:after{content:"";position:absolute;inset:0;pointer-events:none;
background:repeating-linear-gradient(0deg,rgba(0,0,0,.22) 0 1px,transparent 1px 3px)}
.crt .chin{display:flex;justify-content:space-between;align-items:center;padding:5px 4px 1px;color:var(--mut);font-size:9.5px;letter-spacing:1.5px}
.crt .led{width:6px;height:6px;border-radius:50%;background:var(--hot);box-shadow:0 0 6px var(--hot);animation:bl 3.5s steps(1) infinite}
.caption{color:var(--mut);font-size:11.5px;margin-top:8px;font-style:italic}
/* ---- commit timeline (homepage) ---- */
.timeline{position:relative;padding:10px 0}
.timeline:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:2px;
background:linear-gradient(var(--line),var(--hot),var(--line));box-shadow:0 0 10px rgba(var(--glow),.35)}
.commit{position:relative;width:calc(50% - 34px);margin-bottom:34px}
.commit:nth-child(odd){margin-left:0}
.commit:nth-child(even){margin-left:calc(50% + 34px)}
.commit .node{position:absolute;top:26px;width:14px;height:14px;border-radius:50%;
background:var(--bg);border:3px solid var(--hot);box-shadow:0 0 12px rgba(var(--glow),.6);z-index:2}
.commit:nth-child(odd) .node{right:-42px}
.commit:nth-child(even) .node{left:-42px}
.commit .wire{position:absolute;top:31px;height:2px;width:28px;background:var(--line)}
.commit:nth-child(odd) .wire{right:-28px}
.commit:nth-child(even) .wire{left:-28px}
.card{display:block;border:1px solid var(--line);background:var(--panel);padding:16px 18px;color:var(--ink);transition:border-color .15s}
.card:hover{border-color:var(--hot);text-decoration:none}
.card .vd{font-size:11.5px;color:var(--mut);display:flex;gap:10px;flex-wrap:wrap}
.card .vd b{color:var(--amber)}
.card .vd .sun{color:#7ec8ff}
.card h2{font-size:16.5px;color:var(--hot);margin:7px 0 8px;line-height:1.45}
.card p{color:var(--dim);font-size:13px}
.card .crt{margin:10px 0 10px}
.card .more{color:var(--hot);font-size:12.5px;margin-top:9px;display:inline-block}
/* ---- article ---- */
article h1{font-size:25px;color:var(--hot);line-height:1.35;margin:4px 0 6px;text-shadow:0 0 16px rgba(var(--glow),.3)}
article .meta{color:var(--mut);font-size:12.5px;margin-bottom:20px}
article .meta b{color:var(--amber)}
article .hero{margin:0 0 26px;max-width:640px}
article p{margin:0 0 18px}
article h2{color:var(--amber);font-size:16.5px;margin:30px 0 12px}
article em{color:var(--amber);font-style:normal}
article strong{color:var(--hot)}
article blockquote{border-left:3px solid var(--line);padding:4px 0 4px 16px;color:var(--dim);margin:0 0 18px}
article ul{margin:0 0 18px 20px}
article li{margin-bottom:8px}
article code{color:var(--amber);background:#0d1a12;padding:1px 6px;border:1px solid var(--line);font-size:13px}
hr.sig{border:0;border-top:1px dashed var(--line);margin:34px 0 16px}
.sig-line{color:var(--dim);font-size:13px}.sig-line b{color:var(--hot)}
/* ---- archive search + surprise me ---- */
.findbar{display:flex;gap:8px;align-items:center;margin:26px 0 6px;flex-wrap:wrap}
.findbar .fw{flex:1;min-width:200px;display:flex;align-items:center;gap:8px;
  border:1px solid var(--line);background:var(--panel);padding:9px 12px}
.findbar .fico{color:var(--mut);font-size:13px;flex:none}
.findbar input{flex:1;min-width:0;background:none;border:0;outline:0;color:var(--ink);
  font-family:var(--mono);font-size:13.5px}
.findbar input::placeholder{color:var(--mut)}
.findbar .fw:focus-within{border-color:var(--hot);box-shadow:0 0 12px rgba(var(--glow),.16)}
.fbtn{flex:none;border:1px solid var(--line);background:var(--panel);color:var(--dim);cursor:pointer;
  font-family:var(--mono);font-size:12.5px;padding:9px 14px;letter-spacing:.5px}
.fbtn:hover{color:var(--hot);border-color:var(--hot)}
.findmsg{color:var(--mut);font-size:12px;min-height:17px;margin-bottom:4px}

/* ---- reactions ---- */
.react{border:1px solid var(--line);background:var(--panel);padding:15px 17px;margin-top:26px}
.react .rh{color:var(--mut);font-size:11px;letter-spacing:2px;margin-bottom:11px}
.rbtns{display:flex;gap:9px;flex-wrap:wrap}
.rb{flex:1;min-width:135px;display:flex;flex-direction:column;gap:2px;align-items:flex-start;
  border:1px solid var(--line);background:var(--panel2);color:var(--dim);cursor:pointer;
  font-family:var(--mono);padding:10px 12px;position:relative;transition:border-color .15s,color .15s}
.rb b{color:var(--ink);font-size:13px;font-weight:normal}
.rb span{font-size:10.5px;color:var(--mut)}
.rb .rn{position:absolute;right:10px;top:9px;font-style:normal;font-size:12px;color:var(--hot)}
.rb:hover{border-color:var(--hot)}
.rb.on{border-color:var(--hot);background:rgba(var(--glow),.07)}
.rb.on b{color:var(--hot)}
.rb.wait{opacity:.55}
.rnote{color:var(--mut);font-size:10.5px;margin-top:9px}

.related{border:1px solid var(--line);background:var(--panel);padding:16px 18px;margin-top:28px}
.related .rh{color:var(--mut);font-size:11px;letter-spacing:2px;margin-bottom:10px}
.related a{display:block;font-size:13.5px;margin-bottom:7px}
.related a b{color:var(--amber)}
.nextrel{border:1px dashed var(--line);padding:14px 18px;margin-top:22px;font-size:13px;color:var(--dim)}
/* ---- newsletter ---- */
.nl{border:1px solid var(--line);background:linear-gradient(180deg,var(--panel2),var(--panel));padding:18px 20px;margin:30px 0 6px}
.nl .nh{color:var(--amber);font-size:14px;margin-bottom:4px}
.nl .nd{color:var(--dim);font-size:12.5px;margin-bottom:12px}
.nl form{display:flex;gap:8px;flex-wrap:wrap}
.nl input[type=email]{flex:1;min-width:210px;background:#04120a;border:1px solid var(--line);color:var(--ink);
font-family:var(--mono);font-size:13.5px;padding:10px 12px;outline:none}
.nl input[type=email]:focus{border-color:var(--hot);box-shadow:0 0 10px rgba(var(--glow),.25)}
.nl button{background:var(--hot);color:#04120a;border:0;font-family:var(--mono);font-weight:700;
font-size:13.5px;padding:10px 18px;cursor:pointer}
.nl button:hover{box-shadow:0 0 14px rgba(var(--glow),.5)}
.nl .msg{width:100%;font-size:12.5px;color:var(--amber);min-height:18px;margin-top:6px}
.nl .hp{position:absolute;left:-9999px;opacity:0}
footer{margin-top:46px;border-top:1px solid var(--line);padding-top:18px;color:var(--mut);font-size:12.5px;display:flex;gap:16px;flex-wrap:wrap}
footer a{color:var(--dim)}
/* ---- visitor-selectable phosphor themes (tiny, persisted) ---- */
:root{--glow:51,255,102}
html[data-theme=amber]{--hot:#ffb000;--ink:#ffd9a0;--dim:#c98f3f;--mut:#7a5a2a;--line:#3c2a10;--glow:255,176,0}
html[data-theme=cyan]{--hot:#33e0ff;--ink:#aaeeff;--dim:#4fa9c9;--mut:#2a5a7a;--line:#10303c;--glow:51,224,255}
html[data-theme=violet]{--hot:#c479ff;--ink:#e2c6ff;--dim:#9a6fc9;--mut:#5a3a7a;--line:#2c1040;--glow:196,121,255}
html[data-theme=amber]{--bg:#0d0905;--panel:#130d06;--panel2:#171005;--bezel:#1c1508}
html[data-theme=cyan]{--bg:#050b0e;--panel:#071216;--panel2:#05161c;--bezel:#0c1a20}
html[data-theme=violet]{--bg:#0a060e;--panel:#0e0913;--panel2:#120a19;--bezel:#170f20}
/* ---- honour the OS reduced-motion setting: keep the look, drop the movement ---- */
@media (prefers-reduced-motion: reduce){{
  *,*:before,*:after{{animation-duration:.001ms !important;animation-iteration-count:1 !important;
    transition-duration:.001ms !important;scroll-behavior:auto !important}}
  .cur{{animation:none !important;opacity:1 !important}}
}}
/* ---- floating hue knob: a CRT brightness knob that changes the phosphor ---- */
.hueknob{position:fixed;right:16px;bottom:16px;z-index:9000}
.hueknob .knob{width:46px;height:46px;border-radius:50%;cursor:pointer;padding:0;
border:2px solid var(--line);position:relative;
background:radial-gradient(circle at 34% 30%,rgba(var(--glow),.9),rgba(var(--glow),.25) 42%,#050505 78%);
box-shadow:0 0 16px rgba(var(--glow),.55),inset 0 2px 6px rgba(0,0,0,.7);
transition:transform .25s}
.hueknob .knob:before{content:"";position:absolute;left:50%;top:4px;width:3px;height:12px;
margin-left:-1.5px;border-radius:2px;background:rgba(255,255,255,.75)}
.hueknob .knob:hover{transform:rotate(24deg)}
.hueknob.open .knob{transform:rotate(90deg)}
.hueknob .lbl{position:absolute;right:54px;bottom:12px;color:var(--mut);font-size:10px;
letter-spacing:2px;white-space:nowrap;opacity:0;transition:.2s;pointer-events:none}
.hueknob:hover .lbl{opacity:1}
.hueknob .fan{position:absolute;bottom:56px;right:6px;display:flex;flex-direction:column;gap:9px;
opacity:0;pointer-events:none;transform:translateY(10px);transition:.2s}
.hueknob.open .fan{opacity:1;pointer-events:auto;transform:none}
.hueknob .fan button{width:30px;height:30px;border-radius:50%;cursor:pointer;padding:0;
border:2px solid rgba(255,255,255,.28);box-shadow:0 0 12px currentColor;transition:transform .15s}
.hueknob .fan button:hover{transform:scale(1.18)}
.hueknob .fan button.on{outline:2px solid #fff;outline-offset:2px}
@media print{.hueknob{display:none}}

/* Long URLs and inline code must wrap, not push the page sideways. */
html{-webkit-text-size-adjust:100%}
article p,article li,.card p,.card h2{overflow-wrap:break-word}
article a,.related a{overflow-wrap:anywhere}
article code{overflow-wrap:break-word;word-break:break-word}
@media(max-width:660px){body{font-size:14px}h1.site{font-size:23px}article h1{font-size:20px;font-size:clamp(18px,5.6vw,20px)}
.wrap{padding:20px 14px 56px}
header.masthead{padding:18px 16px}
header.masthead:before{top:6px;right:10px}
.crumb{gap:10px;margin-bottom:20px}
.timeline:before{left:8px}
.commit,.commit:nth-child(even){width:calc(100% - 30px);margin-left:30px;margin-bottom:26px}
.commit .node,.commit:nth-child(odd) .node{left:-28px;right:auto;width:12px;height:12px}
.commit .wire,.commit:nth-child(odd) .wire{left:-16px;right:auto;width:14px}
.card{padding:14px 14px}
.card h2{font-size:15px}
article .hero{max-width:100%}
article h2{font-size:15.5px}
/* 16px stops iOS Safari from zooming the page when the email field is focused;
   full-width input + button read as one stacked control instead of a skinny pair. */
.nl{padding:16px 14px}
.nl form{gap:10px}
.nl input[type=email]{min-width:100%;font-size:16px;padding:12px 12px}
.nl button{width:100%;padding:13px 18px;font-size:15px}
.related{padding:14px 14px}
.related a{margin-bottom:10px;padding:2px 0}
footer{gap:12px;font-size:12px}}
@media(max-width:380px){h1.site{font-size:20px}.crt{padding:7px 7px 4px}}
"""

NL_JS = f"""
<script>
document.querySelectorAll('form.nlf').forEach(function(f){{
  f.addEventListener('submit',function(e){{
    e.preventDefault();
    var em=f.querySelector('input[type=email]').value.trim();
    var hp=f.querySelector('.hp input');
    var msg=f.querySelector('.msg');
    if(hp&&hp.value) return;
    if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(em)){{msg.textContent='that email looks off — try again?';return;}}
    msg.textContent='subscribing…';
    fetch('{API}/subscribe',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify({{email:em}})}})
    .then(function(r){{return r.json().catch(function(){{return {{}};}});}})
    .then(function(j){{
      if(j&&j.ok){{msg.textContent='subscribed. new releases will find you. ✓';f.querySelector('input[type=email]').value='';}}
      else{{msg.textContent=(j&&j.error)?('error: '+j.error):'something broke — email cole@ciprari.ai and blame the robot.';}}
    }})
    .catch(function(){{msg.textContent='network error — the robot accepts full responsibility.';}});
  }});
}});
</script>"""

def newsletter(compact=False):
    head = "SUBSCRIBE TO THE CHANGELOG" if not compact else "GET THE NEXT RELEASE"
    return f"""
<div class="nl">
  <div class="nh">▚▞ {head}</div>
  <div class="nd">New releases Monday, Wednesday and Friday, plus the Sunday <b>Rollout Report</b> —
  the week's AI and tech news, summarized by a human with production access. No spam. Unsubscribe by
  emailing a mildly disappointed <a href="mailto:cole@ciprari.ai">cole@ciprari.ai</a>.</div>
  <form class="nlf" novalidate>
    <label class="hp">leave this empty<input type="text" name="website" tabindex="-1" autocomplete="off"></label>
    <input type="email" name="email" placeholder="you@example.com" required aria-label="Email address">
    <button type="submit">subscribe</button>
    <div class="msg" role="status" aria-live="polite"></div>
  </form>
</div>"""

def crt(p, hero=False):
    cap = f'<div class="caption">{esc(p["svg_caption"])}</div>' if p.get("svg_caption") else ""
    return f"""
<figure class="crt{' hero' if hero else ''}" role="img" aria-label="{html.escape(p['svg_alt'])}">
  <div class="screen">{p["svg"]}</div>
  <div class="chin"><span>CIPRARI CRT-95</span><span class="led"></span></div>
  {f'<figcaption class="caption">{esc(p["svg_caption"])}</figcaption>' if p.get("svg_caption") else ''}
</figure>""" if hero else f"""
<span class="crt" role="img" aria-label="{html.escape(p['svg_alt'])}">
  <span class="screen">{p["svg"]}</span>
  <span class="chin"><span>CIPRARI CRT-95</span><span class="led"></span></span>
</span>"""

def page(title, desc, path, body, og_img, og_type="article", keywords="", extra_head=""):
    kw = f'\n<meta name="keywords" content="{html.escape(keywords)}">' if keywords else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{html.escape(desc)}">{kw}
<meta name="author" content="Cole Ciprari">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{BASE}{path}">
<link rel="icon" href="/favicon.ico">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="changelog">
<link rel="alternate" type="application/rss+xml" title="changelog.ciprari.ai" href="{BASE}/feed.xml">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{BASE}{path}">
<meta property="og:site_name" content="changelog.ciprari.ai">
<meta property="og:image" content="{BASE}{og_img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}">
<meta name="twitter:image" content="{BASE}{og_img}">
<meta name="theme-color" content="#070d0a">
{extra_head}
<style>{CSS}</style>
<script>(function(){{var t=localStorage.getItem("phos");if(t)document.documentElement.setAttribute("data-theme",t);}})();</script>
</head>
<body>
<div class="wrap">
<nav class="crumb" aria-label="Site">
  <a href="/">changelog.ciprari.ai</a>
  <a href="https://ciprari.ai" target="_blank" rel="noopener">boot ciprari.ai →</a>
  <a href="https://www.linkedin.com/in/coleos" target="_blank" rel="noopener">linkedin</a>
  <a href="/feed.xml">rss</a>
</nav>
{body}
<footer>
  <span>© {datetime.date.today().year} Cole Ciprari</span>
  <a href="mailto:cole@ciprari.ai">cole@ciprari.ai</a>
  <a href="https://ciprari.ai" target="_blank" rel="noopener">ciprari.ai</a>
  <a href="https://ciprari.ai/resume" target="_blank" rel="noopener">resume</a>
  <a href="https://ciprari.ai/ask/" target="_blank" rel="noopener">Q&amp;A</a>
  <a href="https://ciprari.ai/status.html" target="_blank" rel="noopener">status</a>
  <a href="https://www.linkedin.com/in/coleos" target="_blank" rel="noopener">linkedin.com/in/coleos</a>
  <span>written by me, shipped by my agents — reviewed at the gate</span>
  </footer>
</div>
<div class="hueknob" id="huek">
<span class="lbl">PHOSPHOR</span>
<div class="fan" role="group" aria-label="Theme color">
<button data-t="" style="background:#33ff66;color:#33ff66" aria-label="green phosphor" title="green"></button>
<button data-t="amber" style="background:#ffb000;color:#ffb000" aria-label="amber phosphor" title="amber"></button>
<button data-t="cyan" style="background:#33e0ff;color:#33e0ff" aria-label="cyan phosphor" title="cyan"></button>
<button data-t="violet" style="background:#c479ff;color:#c479ff" aria-label="violet phosphor" title="violet"></button>
</div>
<button class="knob" aria-label="Change theme color" title="change the phosphor"></button>
</div>
{NL_JS}
<script>if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js");</script>
<script>(function(){{
var k=document.getElementById("huek"); if(!k) return;
var knob=k.querySelector(".knob"), cur=localStorage.getItem("phos")||"";
function mark(){{k.querySelectorAll(".fan button").forEach(function(x){{x.classList.toggle("on",(x.dataset.t||"")===cur);}});}}
mark();
knob.addEventListener("click",function(e){{e.stopPropagation();k.classList.toggle("open");}});
document.addEventListener("click",function(e){{if(!k.contains(e.target))k.classList.remove("open");}});
k.querySelectorAll(".fan button").forEach(function(b){{
b.addEventListener("click",function(e){{e.stopPropagation();
cur=b.dataset.t||"";
if(cur)localStorage.setItem("phos",cur);else localStorage.removeItem("phos");
if(cur)document.documentElement.setAttribute("data-theme",cur);else document.documentElement.removeAttribute("data-theme");
mark();setTimeout(function(){{k.classList.remove("open");}},250);}});}});
}})();</script>

<script>(function(){{try{{
if(navigator.doNotTrack==="1")return;
var s="";try{{s=new URL(location.href).searchParams.get("utm_source")||"";}}catch(e){{}}
var p=JSON.stringify({{event:"blog",path:location.pathname,ref:document.referrer||"",
meta:s?("utm:"+s.slice(0,30)):""}});
var ep="https://coleos-api.coleciprari.workers.dev/track";
/* text/plain keeps the beacon a simple request — no CORS preflight to lose */
if(navigator.sendBeacon){{navigator.sendBeacon(ep,new Blob([p],{{type:"text/plain"}}));}}
else{{fetch(ep,{{method:"POST",body:p,keepalive:true}}).catch(function(){{}});}}
}}catch(e){{}}}})();</script>

</body>
</html>"""

def sig():
    return """<hr class="sig">
<div class="sig-line"><b>— Cole Ciprari</b> · Business Systems Architect · Worcester, MA<br>
my résumé is an operating system → <a href="https://ciprari.ai" target="_blank" rel="noopener">ciprari.ai</a> ·
<a href="https://www.linkedin.com/in/coleos" target="_blank" rel="noopener">linkedin.com/in/coleos</a> ·
<a href="mailto:cole@ciprari.ai">cole@ciprari.ai</a></div>"""

def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%B %d, %Y").replace(" 0", " ")

def related_block(p):
    rel = [BY_SLUG[s] for s in p.get("related", []) if s in BY_SLUG]
    if not rel: return ""
    rows = "".join(f'<a href="/{r["slug"]}"><b>{r["version"]}</b> — {esc(r["title"])}</a>' for r in rel)
    return f'<div class="related"><div class="rh">RELATED RELEASES</div>{rows}</div>'

def reactions(p):
    """One tap, no account, no comment thread to moderate. Tapping again undoes it."""
    return f"""
<div class="react" data-slug="{p['slug']}">
  <div class="rh">WAS THIS ANY GOOD?</div>
  <div class="rbtns">
    <button class="rb" data-k="shipped"><b>Ships</b><span>useful in practice</span><i class="rn"></i></button>
    <button class="rb" data-k="useful"><b>Learned something</b><span>new to me</span><i class="rn"></i></button>
    <button class="rb" data-k="funny"><b>Made me laugh</b><span>worth the read</span><i class="rn"></i></button>
  </div>
  <div class="rnote">Anonymous, one tap, no account. Tap again to undo.</div>
</div>
<script>(function(){{
var box=document.querySelector(".react"); if(!box) return;
var slug=box.getAttribute("data-slug"),
    api="https://coleos-api.coleciprari.workers.dev/react",
    btns=[].slice.call(box.querySelectorAll(".rb")),busy=false;
function paint(d){{
  var c=(d&&d.counts)||{{}},mine=d&&d.mine;
  btns.forEach(function(b){{
    var k=b.getAttribute("data-k"),n=c[k]||0;
    b.querySelector(".rn").textContent=n?n:"";
    b.classList.toggle("on",mine===k);
  }});
}}
fetch(api+"?slug="+encodeURIComponent(slug)).then(function(r){{return r.json();}}).then(paint).catch(function(){{}});
btns.forEach(function(b){{
  b.addEventListener("click",function(){{
    if(busy) return; busy=true; b.classList.add("wait");
    fetch(api,{{method:"POST",headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{slug:slug,kind:b.getAttribute("data-k")}})}})
      .then(function(r){{return r.json();}}).then(paint)
      .catch(function(){{}}).then(function(){{ busy=false; b.classList.remove("wait"); }});
  }});
}});
}})();</script>"""

def build():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(OUT + "/og", exist_ok=True)

    # ---------- posts ----------
    for i, p in enumerate(POSTS):
        older = POSTS[i+1] if i+1 < len(POSTS) else None
        newer = POSTS[i-1] if i > 0 else None
        navs = []
        if newer: navs.append(f'next release: <a href="/{newer["slug"]}">{newer["version"]} — {esc(newer["title"])}</a>')
        if older: navs.append(f'previous release: <a href="/{older["slug"]}">{older["version"]} — {esc(older["title"])}</a>')
        nextrel = f'<div class="nextrel">{"<br>".join(navs)}</div>' if navs else ""
        body = f"""
<header class="masthead">
  <div class="prompt">C:\\CHANGELOG&gt; type {p["slug"]}.md<span class="cur"></span></div>
</header>
<article itemscope itemtype="https://schema.org/BlogPosting">
  <div class="meta"><b itemprop="version">{p["version"]}</b> · released
  <time itemprop="datePublished" datetime="{p["date"]}">{nice_date(p["date"])}</time> ·
  {p["read"]} read · by <span itemprop="author">Cole Ciprari</span></div>
  <h1 itemprop="headline">{esc(p["title"])}</h1>
  <div class="hero">{crt(p, hero=True)}</div>
  <div itemprop="articleBody">{crosslink(p["body"])}</div>
  {sig()}
  {reactions(p)}
  {related_block(p)}
  {newsletter(compact=True)}
  {nextrel}
</article>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BlogPosting","headline":{p["title"]!r},
"datePublished":"{p["date"]}","dateModified":"{p["date"]}",
"url":"{BASE}/{p["slug"]}",
"image":"{BASE}/og/{p["slug"]}.png",
"keywords":{p.get("keywords","")!r},
"author":{{"@type":"Person","@id":"https://ciprari.ai/#cole","name":"Cole Ciprari","url":"https://ciprari.ai/","sameAs":["https://www.linkedin.com/in/coleos"]}},
"publisher":{{"@type":"Person","@id":"https://ciprari.ai/#cole","name":"Cole Ciprari","url":"https://ciprari.ai/"}},
"mainEntityOfPage":"{BASE}/{p["slug"]}",
"description":{p["desc"]!r}}}
</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
{{"@type":"ListItem","position":1,"name":"changelog","item":"{BASE}/"}},
{{"@type":"ListItem","position":2,"name":{p["version"]!r},"item":"{BASE}/{p["slug"]}"}}]}}
</script>"""
        with open(f"{OUT}/{p['slug']}.html", "w", encoding="utf-8") as f:
            f.write(page(f'{p["title"]} — changelog.ciprari.ai', p["desc"], f"/{p['slug']}",
                         body, f"/og/{p['slug']}.png", keywords=p.get("keywords","")))

    # ---------- index: commit timeline ----------
    commits = ""
    for p in POSTS:
        d = datetime.date.fromisoformat(p["date"])
        sun = '<span class="sun">☀ rollout report</span>' if p.get("rollout") else ""
        hay = esc(" ".join([p["title"], p["desc"], p.get("keywords", ""), p["version"],
                            d.strftime("%b %Y"), "rollout" if p.get("rollout") else ""]).lower())
        commits += f"""
<div class="commit" data-find="{hay}" data-slug="{p['slug']}">
  <span class="node" aria-hidden="true"></span><span class="wire" aria-hidden="true"></span>
  <a class="card" href="/{p["slug"]}">
    <div class="vd"><b>{p["version"]}</b><span>{d.strftime("%b %d, %Y")}</span><span>{p["read"]}</span>{sun}</div>
    <h2>{esc(p["title"])}</h2>
    {crt(p)}
    <p>{esc(p["desc"])}</p>
    <span class="more">git show {p["version"]} →</span>
  </a>
</div>"""

    index_body = f"""
<header class="masthead">
  <div class="prompt">C:\\&gt; git log --graph --all --funny</div>
  <h1 class="site">CHANGELOG<span class="cur"></span></h1>
  <p class="tag">release notes from <strong>Cole Ciprari</strong> — Business Systems Architect.
  AI that survives contact with real operations, odd tech news, and dispatches from a résumé that
  ships updates. The résumé itself boots at
  <a href="https://ciprari.ai" target="_blank" rel="noopener">ciprari.ai</a>.
  New releases Mon · Wed · Fri, and the <strong>Rollout Report</strong> every Sunday.</p>
</header>
{newsletter()}
<div class="findbar">
  <label class="fw"><span class="fico" aria-hidden="true">&#9906;</span>
    <input id="find" type="search" placeholder="Search {len(POSTS)} releases — try 'agents', 'payroll', 'rollout'"
      aria-label="Search releases" autocomplete="off"></label>
  <button id="lucky" class="fbtn" title="Open a release at random">Surprise me</button>
</div>
<div id="findmsg" class="findmsg" role="status" aria-live="polite"></div>
<div class="timeline">{commits}</div>
<script>(function(){{
var q=document.getElementById("find"),msg=document.getElementById("findmsg"),
    rows=[].slice.call(document.querySelectorAll(".commit"));
if(!q) return;
function apply(){{
  var v=q.value.trim().toLowerCase(),n=0;
  rows.forEach(function(r){{
    var hit=!v||(r.getAttribute("data-find")||"").indexOf(v)>-1;
    r.style.display=hit?"":"none"; if(hit)n++;
  }});
  msg.textContent=v?(n?n+" release"+(n===1?"":"s")+" match \\u201c"+q.value.trim()+"\\u201d"
                      :"Nothing matches \\u201c"+q.value.trim()+"\\u201d — try a broader word."):"";
}}
q.addEventListener("input",apply);
q.addEventListener("keydown",function(e){{ if(e.key==="Escape"){{ q.value=""; apply(); }} }});
document.getElementById("lucky").addEventListener("click",function(){{
  var pool=rows.filter(function(r){{return r.style.display!=="none";}});
  if(!pool.length) pool=rows;
  var pick=pool[Math.floor(Math.random()*pool.length)];
  if(pick) location.href="/"+pick.getAttribute("data-slug");
}});
/* deep link: /?q=agents pre-filters the archive */
try{{ var pre=new URL(location.href).searchParams.get("q");
  if(pre){{ q.value=pre; apply(); }} }}catch(e){{}}
}})();</script>
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Blog","name":"changelog.ciprari.ai",
"url":"{BASE}/","description":"Release notes from Cole Ciprari — Business Systems Architect.",
"author":{{"@type":"Person","name":"Cole Ciprari","url":"https://ciprari.ai/","sameAs":["https://www.linkedin.com/in/coleos"]}},
"blogPost":[{",".join(f'{{"@type":"BlogPosting","headline":{p["title"]!r},"url":"{BASE}/{p["slug"]}","datePublished":"{p["date"]}"}}' for p in POSTS)}]}}
</script>"""
    with open(f"{OUT}/index.html", "w", encoding="utf-8") as f:
        f.write(page("changelog.ciprari.ai — release notes from Cole Ciprari",
                     "Release notes from Cole Ciprari, Business Systems Architect: agentic AI in real operations, odd tech news, funny dispatches. New posts Mon/Wed/Fri + the Sunday Rollout Report.",
                     "/", index_body, "/og/og-home.png", og_type="website",
                     keywords="Cole Ciprari, changelog, AI blog, agentic AI, business systems architect, tech news"))

    # ---------- rss ----------
    items = ""
    for p in POSTS:
        d = datetime.date.fromisoformat(p["date"])
        items += f"""
  <item>
    <title>{html.escape(p["version"] + " — " + p["title"])}</title>
    <link>{BASE}/{p["slug"]}</link>
    <guid>{BASE}/{p["slug"]}</guid>
    <pubDate>{d.strftime("%a, %d %b %Y 12:00:00 GMT")}</pubDate>
    <description>{html.escape(p["desc"])}</description>
  </item>"""
    with open(f"{OUT}/feed.xml", "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>changelog.ciprari.ai</title>
  <link>{BASE}/</link>
  <description>Release notes from Cole Ciprari — Business Systems Architect.</description>
  <language>en-us</language>{items}
</channel></rss>""")

    # ---------- robots + sitemap ----------
    with open(f"{OUT}/robots.txt", "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")

    # IndexNow key file — public by design; the API verifies ownership by
    # fetching this from the site root. Must match the worker's INDEXNOW key.
    with open(f"{OUT}/c01e0s1ndexn0w2026ciprari.txt", "w") as f:
        f.write("c01e0s1ndexn0w2026ciprari")
    urls = f"<url><loc>{BASE}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>" + "".join(
        f"<url><loc>{BASE}/{p['slug']}</loc><lastmod>{p['date']}</lastmod><priority>0.8</priority></url>" for p in POSTS)
    with open(f"{OUT}/sitemap.xml", "w") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')

    # ---------- og images ----------
    try:
        from PIL import Image, ImageDraw, ImageFont
        def font(sz, bold=True):
            pth = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono%s.ttf" % ("-Bold" if bold else "")
            try: return ImageFont.truetype(pth, sz)
            except Exception: return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", sz)
        def og_card(path, version, title, sub):
            im = Image.new("RGB", (1200, 630), (7, 13, 10))
            dr = ImageDraw.Draw(im)
            for y in range(0, 630, 4): dr.line([(0, y), (1200, y)], fill=(5, 10, 8))
            dr.rectangle([40, 40, 1160, 590], outline=(18, 60, 40), width=2)
            dr.text((70, 66), "C:\\> git show " + version, font=font(28), fill=(45, 107, 74))
            # wrap title
            words, lines, cur = title.split(), [], ""
            for w in words:
                t = (cur + " " + w).strip()
                if dr.textlength(t, font=font(56)) > 1020: lines.append(cur); cur = w
                else: cur = t
            lines.append(cur)
            y = 150
            for ln in lines[:5]:
                dr.text((70, y), ln, font=font(56), fill=(51, 255, 102)); y += 74
            dr.text((70, y + 16), sub, font=font(26), fill=(255, 215, 94))
            dr.text((70, 540), "changelog.ciprari.ai — release notes from Cole Ciprari", font=font(24), fill=(79, 174, 124))
            im.save(path)
        og_card(f"{OUT}/og/og-home.png", "HEAD", "CHANGELOG", "release notes from a résumé that ships updates")
        for p in POSTS:
            og_card(f"{OUT}/og/{p['slug']}.png", p["version"], p["title"], nice_date(p["date"]) + " · Cole Ciprari")
        print("og images:", len(POSTS) + 1)
    except Exception as e:
        print("og generation skipped:", e)

    # ---------- PWA: manifest + service worker + icons ----------
    with open(f"{OUT}/manifest.webmanifest", "w", encoding="utf-8") as f:
        f.write("""{
  "name": "the changelog — ciprari.ai",
  "short_name": "changelog",
  "description": "Release notes from Cole Ciprari — AI, tech and shipping notes from ColeOS.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "background_color": "#070d0a",
  "theme_color": "#070d0a",
  "icons": [
    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    {"src": "/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
  ]
}""")

    # Network-first for pages (a blog should be fresh), cache-first for art.
    # Visited pages become readable offline; navigations fall back to home.
    with open(f"{OUT}/sw.js", "w", encoding="utf-8") as f:
        f.write("""const C = "changelog-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(C).then((c) => c.addAll(["/"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== C).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  const isArt = u.pathname.startsWith("/og/") || /\\.(png|ico|webmanifest)$/.test(u.pathname);
  if (isArt) {
    e.respondWith(caches.open(C).then((c) => c.match(e.request).then(
      (r) => r || fetch(e.request).then((n) => { c.put(e.request, n.clone()); return n; }))));
    return;
  }
  e.respondWith(fetch(e.request).then((n) => {
    if (n.ok) { const cl = n.clone(); caches.open(C).then((c) => c.put(e.request, cl)); }
    return n;
  }).catch(() => caches.match(e.request).then((r) => r || caches.match("/"))));
});
""")

    # Icons: the blog's diagonal-checker glyph on a phosphor-dark tile.
    try:
        from PIL import Image, ImageDraw
        def icon(path, size, pad_ratio=0.0):
            im = Image.new("RGB", (size, size), (7, 13, 10))
            dr = ImageDraw.Draw(im)
            pad = int(size * (0.18 + pad_ratio))
            cell = (size - 2 * pad) // 2
            g, d = (51, 255, 102), (18, 60, 40)
            # scanlines
            for y in range(0, size, max(3, size // 64)):
                dr.line([(0, y), (size, y)], fill=(5, 10, 8))
            # ▚▞ checker: TL+BR hot green, TR+BL dim
            dr.rectangle([pad, pad, pad + cell, pad + cell], fill=g)
            dr.rectangle([pad + cell, pad + cell, pad + 2 * cell, pad + 2 * cell], fill=g)
            dr.rectangle([pad + cell, pad, pad + 2 * cell, pad + cell], fill=d)
            dr.rectangle([pad, pad + cell, pad + cell, pad + 2 * cell], fill=d)
            # amber cursor accent
            ch = max(3, size // 24)
            dr.rectangle([pad + 2 * cell + ch, pad + 2 * cell - ch * 2, pad + 2 * cell + ch * 2, pad + 2 * cell],
                         fill=(255, 215, 94))
            im.save(path)
        icon(f"{OUT}/icon-192.png", 192)
        icon(f"{OUT}/icon-512.png", 512)
        icon(f"{OUT}/icon-512-maskable.png", 512, pad_ratio=0.08)
        icon(f"{OUT}/icon-180.png", 180)
        print("pwa: manifest + sw + 4 icons")
    except Exception as e:
        print("pwa icons skipped:", e)

    print("posts:", len(POSTS))
    print("files:", len(os.listdir(OUT)), "top-level;", len(os.listdir(OUT + '/og')), "og images")

if __name__ == "__main__":
    build()
