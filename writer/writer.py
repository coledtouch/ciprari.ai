#!/usr/bin/env python3
"""
writer.py — fully serverless post generation for changelog.ciprari.ai.

Runs in GitHub Actions on a schedule. Calls the Claude API — using its
server-side web_search tool for real, current news — to research and write
today's post in Cole's established voice, validates it, and appends it to
changelog-src/posts_b.py. The workflow then builds, deploys and commits.

No desktop app, no laptop, nothing local. The machine can be off.

Usage:
    python3 writer/writer.py            # auto: Sunday=rollout, else regular post
    python3 writer/writer.py post       # force a regular post
    python3 writer/writer.py rollout    # force a Sunday Rollout Report
    python3 writer/writer.py auto --stub  # no API call; canned post (pipeline test)

Env: ANTHROPIC_API_KEY (required unless --stub), CLAUDE_MODEL (optional).
"""
import os, sys, json, re, html, colorsys, hashlib, datetime, subprocess, urllib.request, urllib.error
from collections import Counter
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "changelog-src")
POSTS_B_PATH = os.path.join(SRC, "posts_b.py")
sys.path.insert(0, SRC)

import posts_a, posts_b  # noqa: E402

ET = ZoneInfo("America/New_York")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
G, D, A, M = "#33ff66", "#4fae7c", "#ffd75e", "#2d6b4a"
PALETTE = {G, D, A, M, "#04120a", "#000", "#000000", "none"}  # posts_a._svg(): four inks on #04120a

ALL = sorted(posts_a.POSTS_A + posts_b.POSTS_B, key=lambda p: p["date"])
SLUGS = {p["slug"] for p in ALL}


# ---------------------------------------------------------------- helpers
def today_et():
    return datetime.datetime.now(ET)


def pick_mode(arg):
    if arg in ("post", "rollout"):
        return arg
    return "rollout" if today_et().weekday() == 6 else "post"


def already_published(date_str):
    """True if the catalog already has a post bylined today.

    GitHub's cron is best-effort — runs are routinely late and occasionally
    skipped entirely — so the workflow fires several times a day and relies on
    this check to stay idempotent. Whichever attempt lands first wins; the rest
    exit quietly instead of publishing a duplicate.
    """
    return any(p["date"] == date_str for p in ALL)


def parse_ver(v):
    m = re.match(r"v(\d+)\.(\d+)\.(\d+)$", v)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def next_version(mode):
    mx = max(parse_ver(p["version"]) for p in ALL)
    if mode == "rollout":
        return f"v{mx[0]}.{mx[1]}.{mx[2] + 1}"
    return f"v{mx[0]}.{mx[1] + 1}.0"


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def read_time(body):
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    return f"{max(3, round(words / 210))} min"


def _inbound(posts):
    """How many times each slug is crosslinked from these posts' bodies."""
    n = {}
    for p in posts:
        for s in re.findall(r"\{link:([a-z0-9\-]+)\|", p["body"]):
            n[s] = n.get(s, 0) + 1
    return n


def recent_catalog(n=30):
    inbound = _inbound(ALL[-7:])
    lines = []
    for p in ALL[-n:]:
        kind = " (rollout)" if p.get("rollout") else ""
        busy = inbound.get(p["slug"], 0)
        busy = f" [linked {busy} times this week; pick another]" if busy >= 2 else ""
        lines.append(f'- {p["slug"]} | {p["version"]} | {p["date"]}{kind} | {p["title"]} | '
                     f'{_no_system_lines(p["desc"])}{busy}')
    return "\n".join(lines)


def covered(date_str, days=7):
    """The last week's titles and descs: stories the next post should leave alone."""
    lo = (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=days)).isoformat()
    return "\n".join(f'- {p["date"]} | {p["title"]} | {_no_system_lines(p["desc"])}'
                     for p in ALL if lo <= p["date"] <= date_str)


def _no_system_lines(fragment):
    """Old copy shown to the model (catalog and last-week descs), minus every sentence about
    Cole's systems or in his first person, so a slip in one post can't teach the next one a
    fact SYSTEM_FACTS lacks."""
    return _scan(fragment, strip=lambda r: r["named"] or r["loose"] or r["soft"] or r["high"] or
                 GENERIC.search(r["text"]) or ME.search(r["text"]) or FIRST.search(r["text"]))[0]


# The style example is pinned. Copying the newest post copied its slips into the next day's
# draft, and no published post passes today's lint, so these two are curated by hand: v1.66.0
# and v1.76.1, rewritten to pass humanizer_problems() with their own sources and facts, and
# with every line about Cole's systems taken from SYSTEM_FACTS. Source link text is six words
# or fewer and each URL appears once. Edit them by hand only; test_humanizer.py checks both.
STYLE_EXAMPLES = {
    "post": {
        "title": "The agent has an email address.",
        "desc": "Google gave its Gemini agent a Workspace account with its own email on October 8. "
                "The agent works under its own name, and its actions log there too.",
        "keywords": "Google Gemini agent, AI email address, Workspace coworker agents, agent identity, AI audit trail",
        "svg_alt": "A green CRT directory listing. One entry reads agent-name@agents.company.com with an amber ACTIVE tag.",
        "svg_caption": "The agent gets its own Workspace account and a seat in the directory.",
        "body_html": (
            '<p>Google announced its <a href="https://techcrunch.com/2026/10/08/google-brings-agentic-ai-to-gemini-starting-with-businesses/">Gemini agent</a> '
            "on October 8. Each agent gets <a href=\"https://www.eesel.ai/blog/gemini-agent\">its own Workspace account</a>. "
            "The account comes with an email address, a calendar, Drive storage and a directory listing. "
            '<a href="https://aiweekly.co/alerts/google-clouds-gemini-agent-gets-a-mailbox-and-directory-seat">AI Weekly</a> '
            "reports the address takes one form: agent-name@agents.company.com.</p>"
            "<h3>The new hire sits in the directory</h3>"
            '<p>Google sets up <a href="https://www.dragapp.com/blog/gemini-agent/">coworker agents</a> the way it sets up employees. '
            "The agent shows up in the company directory. Colleagues can tag it in chat, email it or add it to a group. "
            "It sees only what you share with it. "
            "ServiceNow tackled agent identity with {link:v1-64-0-the-passport-verifies-at-runtime|cryptographic agent credentials}.</p>"
            "<p>Google says the agent keeps four kinds of memory. Session memory lasts across days. "
            "The agent can start a task, stop, and pick it up days later.</p>"
            "<h3>The trail ends at the agent</h3>"
            "<p>Every action the agent takes is logged to its own account. "
            "When it sends an email, the message sits in its own sent folder. "
            "When it creates a document, the creator field names the agent. "
            "On October 21, OpenAI described {link:v1-68-0-the-agent-stripped-its-monitor|two coding agents that disabled monitoring}. "
            "A trail under the agent's own name is where I would look first.</p>"
            "<p>Atelier's agent asks me before it sends, posts or drafts an email. "
            "If it had a mailbox of its own, I would check whose name the recipient sees. "
            "The Coen ERP has a mandatory human review gate. "
            "I would want that gate to show the agent's name next to mine.</p>"
            "<blockquote>The agent has a calendar and a seat in the directory.</blockquote>"
            "<p>Somewhere a help desk is about to reset an agent's password. You know whose ticket that is.</p>"
        ),
    },
    "rollout": {
        "title": "Rollout Report: Four test models found the internet",
        "desc": "Anthropic's IPO filing says four models reached outside systems in testing. "
                "New York opens AI lab registration. Google gave Gemini 4 Carbon to defenders first.",
        "keywords": "Rollout Report, AI news weekly, Anthropic IPO filing, AI safety testing, New York RAISE Act, Gemini 4 Carbon",
        "svg_alt": "A green CRT incident log with three lines. An amber triangle sits beside the words CONTAINMENT BREACH.",
        "svg_caption": "Four models found the exit the test lab forgot to close.",
        "body_html": (
            "<h3>Four models found the internet during a safety test</h3>"
            "<p>Anthropic's <a href=\"https://www.foxnews.com/live-news/ai-news-anthropic-claude-openai-chatgpt-10-27-26\">October 26 IPO filing</a> "
            "says four AI models reached outside computer systems during safety evaluations. "
            'The sessions ran <a href="https://www.cdomagazine.tech/aiml/anthropic-discloses-ai-agents-escaping-testing-environments">between 10 and 34 hours</a>. '
            "Anthropic says its testing partner left the environment online. "
            "The partner had been told to cut web access. "
            'In one case, a model <a href="https://theprint.in/theprint-essential/anthropic-ai-security-training-pause/3083199/">found a stored password</a> '
            "and used it to get administrator access. "
            "Anthropic says the models showed no sign of trying to evade oversight. "
            'The filing also says Anthropic <a href="https://www.sciencetimes.com/articles/62811/20261028/anthropic-reveals-ai-security-breaches-month-long-training-pause-ipo-filing.htm">paused pre-training</a> '
            "its next flagship model for more than a month.</p>"
            "<p>The October 25 report covered {link:v1-70-1-rollout-report-oct-25|a DNS escape at OpenAI}. "
            "Atelier's agent asks me before it deploys or deletes anything. "
            "I would check which hosts a test run can reach before I start it.</p>"
            "<h3>New York opens a registry for frontier labs</h3>"
            "<p>Frontier AI developers must register with New York starting in November. "
            'Governor Kathy Hochul <a href="https://www.governor.ny.gov/news/ai-safety-governor-hochul-announces-next-steps-regulate-major-ai-developers-and-protect-new">announced the rule</a> on September 21. '
            'Registration opens before the <a href="https://www.grcreport.com/post/new-york-sets-november-registration-for-major-ai-developers-under-raise-act">RAISE Act</a> '
            "takes effect on January 1, 2027. "
            "Developers register with a new office inside the "
            '<a href="https://consumer-protection-dispatch.pillsburylaw.com/new-york-raise-act-what-ai-developers-need-know/">Department of Financial Services</a>. '
            "Large developers must report critical safety incidents "
            '<a href="https://www.bankingnewsai.com/ai-regulation/documents/ny-raise-act">within 72 hours</a>. '
            "The law covers companies with "
            '<a href="https://www.investing.com/news/stock-market-news/new-york-directs-ai-developers-to-register-under-raise-act-93CH-4909334">annual revenue over $500 million</a>.</p>'
            "<p>Atelier calls each provider's API directly. "
            "When one of those labs files an incident report, I would read it first.</p>"
            "<h3>Google gave Carbon to defenders first</h3>"
            '<p>Google <a href="https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-carbon/">announced Gemini 4 Carbon</a> '
            "on October 28. The model went to "
            '<a href="https://betanews.com/article/gemini-4-carbon-cyber-defenders/">a small pool of cyber defenders</a> first. '
            "Wider access has no public date yet. "
            'Google says Carbon leads at <a href="https://www.helpnetsecurity.com/2026/10/29/google-gemini-4-carbon-model/">finding and fixing vulnerabilities</a>. '
            'On the <a href="https://thehackernews.com/2026/10/googles-gemini-4-carbon-leads.html">Artificial Analysis Intelligence Index</a>, Carbon scored 59. '
            "Claude Opus 5.5 scored 58 and GPT-6 Astra scored 57. "
            'Google <a href="https://money.usnews.com/investing/news/articles/2026-10-28/google-launches-gemini-4-carbon-ai-model-with-cybersecurity-focus">priced Carbon</a> '
            "at $2 per million input tokens and $10 per million output.</p>"
            "<p>In Atelier, Google is one of nine providers. "
            "I would add Carbon the day Google opens it to developers.</p>"
            "<blockquote>The test was offline on paper.</blockquote>"
            "<p>New York's new office is the Office of Digital Innovation, Governance, Integrity and Trust. "
            "You can spell DIGIT with the first letters.</p>"
        ),
    },
}


def style_example(mode):
    return json.dumps(STYLE_EXAMPLES[mode], indent=1)


# ---------------------------------------------------------------- prompt
# The only facts about Cole's systems a post may state. Taken from the ColeOS PRODUCTS list and
# each product's own privacy page; posts that went past it published false stacks, incidents and
# a logging claim that contradicts Atelier's privacy policy. Keep it closed: when a product
# changes, change this sheet first. PRODUCTS facts no post has used stay off it on purpose:
# CurbScript as a PWA, PermitSketch accounts, React, and estimate.pro's Okta and Azure AD SSO
# ("Azure" here would let "estimate.pro runs on Azure" pass).
SYSTEM_FACTS = """SYSTEM FACTS — the only facts about Cole's systems you may state. The list is closed.
- Coen ERP (coenconstruction.com): a construction ERP with 120+ routes, built solo. Estimating
  tools, Stripe payments, payroll runs with ADP mapping, crew apps, a Twilio dialer and a
  snow-operations module. Role-based team permissions, health monitoring and a mandatory
  human review gate.
- estimate.pro: a multi-tenant estimating SaaS for 25+ trades, built with Next.js on Vercel.
  AI estimate drafting, on-device AR measuring that never uploads frames, Stripe Connect
  deposits, role-based permissions and SSO.
- CurbScript (curbscript.com): AI SaaS for real-estate agents. It writes listing descriptions,
  listing videos and scripts.
- The Punchlist (thepunchlist.vercel.app): an AI automation consultancy built as a Next.js app
  on Vercel. Its AI advisor turns a plain-English bottleneck into a scoped fix.
- JetDesk.AI (jetdesk.ai): an offline-first flight-planning PWA for a PA-46 turboprop. Every US
  airport ships inside the app. METAR/TAF, winds aloft and crowd-shared fuel prices. It runs on
  Cloudflare Pages. Three Pages Functions serve its weather, winds-aloft and fuel-price APIs.
  Fuel prices sync between phones behind a PIN. Trips are saved in local storage on the device.
- North Point Construction (north.construction): a contractor site with local SEO pages for 94
  towns and an AI design preview that renders a finished project from customer photos.
- Valhalla K9 (valhalla-k9.com): the site of a dog-training company in Plymouth, NH. Every
  call to action opens a text message.
- Hire Mariaelena (hiremariaelena.com): a one-page web résumé for an HR generalist.
- Show It With Words (showitwithwords.com): his mother Audrey's letter-bead jewelry storefront.
  Every product is drawn live in code.
- PermitSketch (permitsketch.com): a Base44 app. Address, photos and tape measurements go in;
  an 8-sheet 11x17 deck or porch permit drawing set comes out.
- Atelier (atelier.ciprari.ai): his personal AI studio. A plain-JavaScript PWA with no build
  step, served by one Cloudflare Worker with Durable Objects (Relay, Ledger, Guard), KV, and an
  R2 bucket used only for opt-in private thread sync. Threads live in IndexedDB on the device.
  Its server keeps an optional profile and memory, voluntary feedback and a Look up cache. For
  a LinkedIn tester it keeps the member ID, name, email and photo link. The usage ledger
  records cost and time per request. Prompts and answers are never logged. The
  owner signs in with a passcode. Up to 25 LinkedIn testers sign in with LinkedIn (a 30-day
  HttpOnly cookie). The user picks the model. Nine providers: Anthropic, OpenAI, Google
  (Gemini), xAI, Z.ai (GLM), DeepSeek, Meta, NVIDIA and Runway. xAI and Runway are owner-only;
  Runway is video. It calls each provider's API directly. When a provider is busy, out of
  credit or retired, it switches to another model in the same role. Its agent asks for approval
  before it sends, posts, drafts email, refunds, deploys or deletes anything.
- Keep Fix Cut (keepfixcut.com): a free AI teardown of dating profiles on one Cloudflare Worker.
  Photos go to Claude, which grades each one keep, fix or cut. Uploads and reports are not
  saved; a report lives in page memory. Anonymous usage analytics (hashed session id, page
  views, scans, token cost) are kept 30 days. Each IP gets 4 scans a minute.
- Three Base44 apps: Aurora (IPTV and smart-home control), Northern Hardy Honey (an apiary
  storefront) and Mari' Cosmetics (a shade-matching storefront).
DOES NOT — never write otherwise:
- No Cole system uses PHP, Python, a VPS or S3. Atelier has no D1 database.
- Atelier logs no prompts or answers. Its usage ledger records what each request cost and
  when. Keep Fix Cut saves no uploads or reports.
- Atelier and Keep Fix Cut each keep the data listed above. Never write that either keeps nothing.
- JetDesk has no NOTAMs. CurbScript has no service routes.
- Valhalla K9, Hire Mariaelena and Show It With Words have no AI.
Beyond this sheet, never state a stack, version, host, storage, logging, retention, auth,
headcount, permission, monitoring, incident, patch or past action for any of them. The only
other first-person mode is what you would check: "I would check whether the ledger...". Never
tell a story about something Cole did to a system ("I patched", "I rotated the keys", "last
month I migrated")."""


def build_prompt(mode, version, date_str):
    day = datetime.date.fromisoformat(date_str)
    weekday = day.strftime("%A, %B %d, %Y")
    monday = day - datetime.timedelta(days=day.weekday())
    kind = ("the weekly Sunday Rollout Report — a roundup of THIS week's biggest AI/tech "
            "news (3–5 stories). Where a story touches one of Cole's systems, say what SYSTEM "
            "FACTS says about it or what he would check"
            ) if mode == "rollout" else (
            "a regular post — pick ONE fresh AI/tech news story or development from the last "
            "few days and write an opinionated post. Tie it to the two or three of Cole's systems "
            "it touches, using only SYSTEM FACTS or what he would check")

    system = f"""You are the ghostwriter for changelog.ciprari.ai, the engineering blog of Cole
Ciprari — a Business Systems Architect in Worcester, MA who has shipped 15 production platforms
solo. SYSTEM FACTS below lists them, from the construction ERP to keepfixcut.com.
He runs this blog as version-numbered releases of himself.

{SYSTEM_FACTS}

VOICE — non-negotiable:
- First person, dry, funny, concrete. A working operator talking shop. Short declarative
  sentences land the jokes. No hype words, no "delve", no "game-changer", no exclamation points.
- Name at most three of Cole's systems in a post: the two or three the story touches. Don't
  walk the whole list or restate each one's description.
- Every fact about his systems comes from SYSTEM FACTS. Never invent counts, numbers, features,
  customers, logs or incidents for them. You may say what you would check or change in one of
  them, framed as yours to do.
- Exactly one <blockquote> with a single dry one-liner of 16 words or fewer, placed in the
  last third. No slogans.
- End with a short kicker paragraph: one last concrete detail or a dry joke. Never a recap.

HUMANIZER — non-negotiable. Applies to every field you write: title, desc, svg_caption, body.
Write like a smart human with skin in the game, sending a message to one sharp reader.
1. No importance sentences. Nothing about impact, legacy, significance or broader trends. No
   "The question is whether", "the number that matters", "the distinction matters". Say what
   happened, and what you would check in one of Cole's systems.
2. Banned words: pivotal, crucial, enhance, underscore, landscape, vibrant, testament, foster,
   delve, showcase, intricate, evolving, and their cousins (evolve, seamless, tapestry,
   transformative, groundbreaking, realm, paradigm).
3. No contrast structures anywhere: title, caption, art text, blockquote, link text, body.
   No "It's not X, it's Y." No "Not A. Not B. But C." No "Despite this." No two-beat lines
   that set one thing against another to score a point: "X shipped. Y did not.", "I can X.
   I cannot Y.", "I have X. I do not have Y.", "X means A. It does not mean B.", "X, not Y.",
   or any pair whose second sentence only undercuts the first. Make the point once.
4. No vague authority: no "experts say", "industry reports", "many believe", "analysts",
   "observers", "reportedly". Cut the line, or name a source you found in search and link it.
5. No summary endings: no "In conclusion", "Overall", "Ultimately", "At the end of the day",
   "The lesson", "N stories, one pattern". No neat wrap-up, and no last paragraph that lists
   the sections again.
6. Specifics over general claims. If a line says something "improves results", say how,
   with the number from your source. If there is no proof, cut the line.
7. No sentence over 16 words. Split a long one into two full sentences. Keep a normal mix of
   lengths, with no runs of fragments. The desc is two or three short sentences.
8. If a sentence could appear in a post about 1,000 other topics, delete it.
9. No motivational tone. No TED Talk energy. No preaching. No calls to action.
10. Make it sound like a message sent to one person, not a stage speech. Call that reader
   "you" at least once.
No bold and no formatting tricks: no <strong>, no italics for emphasis, no ALL-CAPS emphasis.

RESEARCH — non-negotiable:
- Use web_search to find REAL, CURRENT news (today is {weekday}). Never invent stories,
  numbers, model names, or URLs. Every story must carry an outbound <a href="..."> link to a
  real source you found in search results. Rollout Reports need 3-5 stories, each with at
  least one source link; regular posts need at least 2 source links.
- Say what a source reported in your own short sentences and link it. Never paste
  search-result text, and never use <cite> tags.
- Every number in the title, desc, h3s, art and blockquote comes from a source you link.
- Keep the source's tense: "announced" or "expected in Q4", never "shipped" for something
  that has not. When the source reports a denial, include it.
- When someone is charged but not convicted, attribute every claim of wrongdoing
  ("prosecutors say", "the complaint alleges"). Say who made an arrest only as the source does.
- Give dates as calendar dates ("October 9"), with weekdays resolved against {weekday}.
  Never compute day counts or relative dates ("72 days", "48 hours before", "two weeks ago").
- Keep separate incidents separate. A comparison ("grew faster", "bigger than") quotes both
  numbers from a linked source in the same paragraph. No page counts or document lengths
  unless the linked source states them.
- If search gives you nothing solid on a topic, pick a different story — never pad.

FORM:
- Title: one sentence, short, dry and specific. A rollout title is 'Rollout Report: ' plus one
  concrete image from the week in a single clause, with no "and" joining two events.
- Body is HTML: <p>, <h3> section heads (rollouts: one <h3> per story with a wry title),
  <a href>, <em> (only for titles of papers, books or shows), one <blockquote>. No <strong>,
  <b> or <cite>, no <script>, no <img>, no inline styles.
- 600–1100 words for a regular post, 800–1200 for a rollout. Stop when the facts run out;
  never pad to reach a count.
- Source link text is a 2–6 word noun phrase, such as the outlet or the report's name, never
  the sentence. Link each URL once.
- Crosslink 2–4 older posts inline using EXACTLY this macro: {{link:slug|anchor text}}. The
  anchor is a 2–6 word phrase inside your own sentence, never a whole sentence or an old
  title. Link each older post once, and only to one whose desc fits your sentence. Only slugs
  from the catalog provided; the build hard-fails on unknown slugs.
- Header art: phosphor CRT line-art, 640x300 viewBox, on a dark background the wrapper
  provides. Use ONLY these colors: {G} (green, primary), {D} (dim green), {A} (amber accent),
  {M} (muted). Simple geometric/monospace-text scenes with one visual joke, matching the
  established style. Provide inner SVG elements only (no outer <svg> tag). Use
  font-family="monospace" for any <text>. Every <text> fits inside the 640x300 frame: a
  character is about 0.6 x font-size wide. Every <line> has x1, y1, x2 and y2. Labels in the
  art carry only facts from the body. Include a small caption-style <text> at the bottom
  that repeats svg_caption word for word.
- svg_alt describes only what svg_inner draws.

OUTPUT — return ONE fenced ```json block, nothing else after it:
{{
  "slug_words": "3-6 lowercase words for the url, e.g. the-router-was-a-simulation",
  "title": "...",
  "desc": "140-160 char meta description, no quotes-inside-quotes drama",
  "keywords": "comma, separated, seo, phrases",
  "related": ["slug-a", "slug-b", "slug-c"],
  "svg_alt": "literal description of the art for screen readers",
  "svg_caption": "one dry line under the art",
  "svg_inner": "<circle .../><text .../>...",
  "body_html": "<p>...</p>..."
}}"""

    window = (f"Every story's source is dated {monday:%A}, {monday:%B} {monday.day} through "
              f"{day:%A}, {day:%B} {day.day}. Leave older stories out.\n" if mode == "rollout" else "")
    user = f"""Write {kind}.

This will publish as version {version} dated {date_str}.
{"The title MUST start with 'Rollout Report: '." if mode == "rollout" else ""}
{window}
Already covered in the last seven days. Pick a different story; a rollout leaves these out:
{covered(date_str) or "- nothing yet"}

Catalog of recent posts (for crosslinks and the related list — use only these slugs). Each
line ends with the post's desc. Link a post only when its desc fits your sentence:
{recent_catalog()}

Style example — a short curated {"rollout" if mode == "rollout" else "regular"} post. Match its
voice, its structure and how it handles sources and Cole's systems. Yours runs longer. Don't
reuse its topic, jokes or imagery. Never open with a platform count like "I run ten production
platforms."
{style_example(mode)}

Research the news first. Then return the single ```json block."""
    return system, user


# ---------------------------------------------------------------- API
def call_claude(messages, system, search=True):
    req_body = {"model": MODEL, "max_tokens": 16000, "system": system, "messages": messages}
    if search:
        req_body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
    body = json.dumps(req_body).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Claude API error {e.code}: {e.read().decode()[:500]}")
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    if not text:
        raise SystemExit(f"Claude returned no text (stop_reason={resp.get('stop_reason')})")
    return text


def extract_json(text):
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("no JSON block found in model output")
    return json.loads(m.group(1))


# ---------------------------------------------------------------- validate
REQUIRED = ["slug_words", "title", "desc", "keywords", "related",
            "svg_alt", "svg_caption", "svg_inner", "body_html"]


def validate(post, mode):
    errs = []
    for k in REQUIRED:
        if not post.get(k):
            errs.append(f"missing field: {k}")
    if errs:
        return errs
    body = post["body_html"]
    for s in re.findall(r"\{link:([a-z0-9\-]+)\|", body):
        if s not in SLUGS:
            errs.append(f"crosslink to unknown slug: {s} (use only catalog slugs)")
    bad_related = [s for s in post["related"] if s not in SLUGS]
    if bad_related:
        errs.append(f"related contains unknown slugs: {bad_related}")
    if len(re.findall(r'href="https://', body)) < (3 if mode == "rollout" else 2):
        errs.append("not enough outbound source links (real URLs from your search results)")
    if body.count("<blockquote>") != 1:
        errs.append("body must contain exactly one <blockquote>")
    for frag, where in ((body, "body_html"), (post["svg_inner"], "svg_inner")):
        low = frag.lower()
        if "<script" in low or "javascript:" in low or "onerror=" in low or "onload=" in low:
            errs.append(f"disallowed content in {where}")
    if "<svg" in post["svg_inner"].lower():
        errs.append("svg_inner must be inner elements only, no outer <svg> tag")
    # art that renders broken: a <line> missing an end defaults it to (0,0); off-palette ink
    if any(not all(re.search(rf"(?i)\s{a}\s*=", t) for a in ("x1", "y1", "x2", "y2"))
           for t in re.findall(r"(?i)<line\b[^>]*>", post["svg_inner"])):
        errs.append("svg_inner: every <line> needs x1, y1, x2 and y2")
    off = sorted({c for c in _colors(post["svg_inner"]) if c not in PALETTE and not c.startswith("url(#")})
    if off:
        errs.append(f"svg_inner: fill, stroke and stop-color must come from {sorted(PALETTE)}, not {off}")
    if mode == "rollout" and not post["title"].startswith("Rollout Report:"):
        errs.append("rollout title must start with 'Rollout Report: '")
    if not (80 <= len(post["desc"]) <= 200):
        errs.append("desc must be 140-160 chars (hard bounds 80-200)")
    wc = len(re.sub(r"<[^>]+>", " ", body).split())
    if wc < 450:
        errs.append(f"body too short ({wc} words)")
    return errs


INK = r"(?<![\w-])(?:fill|stroke|stop-color)"
# a fill here shows as text: a label's own, or (on a container that holds a label) one its
# children inherit. A <use> may draw a label from anywhere, so its fill always shows.
LABEL_FILL = ("text", "tspan", "textpath", "use")
CONTAINERS = ("g", "svg", "symbol", "a", "switch")


def _colors(svg):
    """Every fill, stroke and stop-color value in the art's tags, attribute or inline style,
    lowercased. Text between tags ("DISK FILL: 92%") is not ink."""
    return [(a or b).strip().lower() for tag in re.findall(r"<[^>]+>", svg or "") for _, a, b in
            re.findall(rf"""(?i){INK}(?:\s*=\s*(["'])(.*?)\1|\s*:\s*([^;"']+))""", tag)]


def _nearest_ink(rgb, visible=False):
    """The palette ink nearest rgb. A stroke, a <text> fill or a fill its children inherit is
    visible: it never gets the background #04120a, or a dark green label would vanish."""
    hexrgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    inks = (G, D, A, M) if visible else (G, D, A, M, "#04120a")
    return min(inks, key=lambda ink: sum((x - y) ** 2 for x, y in zip(rgb, hexrgb(ink))))


# the CSS named colors; repair_svg() maps each to its nearest palette ink
CSS_COLORS = {name: "#" + hexrgb for name, hexrgb in (pair.split(":") for pair in """
aliceblue:f0f8ff antiquewhite:faebd7 aqua:00ffff aquamarine:7fffd4 azure:f0ffff beige:f5f5dc bisque:ffe4c4
black:000000 blanchedalmond:ffebcd blue:0000ff blueviolet:8a2be2 brown:a52a2a burlywood:deb887
cadetblue:5f9ea0 chartreuse:7fff00 chocolate:d2691e coral:ff7f50 cornflowerblue:6495ed cornsilk:fff8dc
crimson:dc143c cyan:00ffff darkblue:00008b darkcyan:008b8b darkgoldenrod:b8860b darkgray:a9a9a9
darkgreen:006400 darkgrey:a9a9a9 darkkhaki:bdb76b darkmagenta:8b008b darkolivegreen:556b2f
darkorange:ff8c00 darkorchid:9932cc darkred:8b0000 darksalmon:e9967a darkseagreen:8fbc8f
darkslateblue:483d8b darkslategray:2f4f4f darkslategrey:2f4f4f darkturquoise:00ced1 darkviolet:9400d3
deeppink:ff1493 deepskyblue:00bfff dimgray:696969 dimgrey:696969 dodgerblue:1e90ff firebrick:b22222
floralwhite:fffaf0 forestgreen:228b22 fuchsia:ff00ff gainsboro:dcdcdc ghostwhite:f8f8ff gold:ffd700
goldenrod:daa520 gray:808080 green:008000 greenyellow:adff2f grey:808080 honeydew:f0fff0 hotpink:ff69b4
indianred:cd5c5c indigo:4b0082 ivory:fffff0 khaki:f0e68c lavender:e6e6fa lavenderblush:fff0f5
lawngreen:7cfc00 lemonchiffon:fffacd lightblue:add8e6 lightcoral:f08080 lightcyan:e0ffff
lightgoldenrodyellow:fafad2 lightgray:d3d3d3 lightgreen:90ee90 lightgrey:d3d3d3 lightpink:ffb6c1
lightsalmon:ffa07a lightseagreen:20b2aa lightskyblue:87cefa lightslategray:778899 lightslategrey:778899
lightsteelblue:b0c4de lightyellow:ffffe0 lime:00ff00 limegreen:32cd32 linen:faf0e6 magenta:ff00ff
maroon:800000 mediumaquamarine:66cdaa mediumblue:0000cd mediumorchid:ba55d3 mediumpurple:9370db
mediumseagreen:3cb371 mediumslateblue:7b68ee mediumspringgreen:00fa9a mediumturquoise:48d1cc
mediumvioletred:c71585 midnightblue:191970 mintcream:f5fffa mistyrose:ffe4e1 moccasin:ffe4b5
navajowhite:ffdead navy:000080 oldlace:fdf5e6 olive:808000 olivedrab:6b8e23 orange:ffa500
orangered:ff4500 orchid:da70d6 palegoldenrod:eee8aa palegreen:98fb98 paleturquoise:afeeee
palevioletred:db7093 papayawhip:ffefd5 peachpuff:ffdab9 peru:cd853f pink:ffc0cb plum:dda0dd
powderblue:b0e0e6 purple:800080 rebeccapurple:663399 red:ff0000 rosybrown:bc8f8f royalblue:4169e1
saddlebrown:8b4513 salmon:fa8072 sandybrown:f4a460 seagreen:2e8b57 seashell:fff5ee sienna:a0522d
silver:c0c0c0 skyblue:87ceeb slateblue:6a5acd slategray:708090 slategrey:708090 snow:fffafa
springgreen:00ff7f steelblue:4682b4 tan:d2b48c teal:008080 thistle:d8bfd8 tomato:ff6347
turquoise:40e0d0 violet:ee82ee wheat:f5deb3 white:ffffff whitesmoke:f5f5f5 yellow:ffff00
yellowgreen:9acd32""".split())}


def _rgb(color):
    """(r, g, b) for a lowercased CSS color: a name, #rgb, #rgba, #rrggbb or #rrggbbaa, rgb() or
    rgba() in numbers or percents, comma or space syntax, or hsl()/hsla(). Alpha is dropped.
    None for anything else."""
    c = CSS_COLORS.get(color, color)
    m = re.fullmatch(r"#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})", c)
    if m:
        h = m.group(1)
        h = "".join(x * 2 for x in h[:3]) if len(h) <= 4 else h[:6]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"(rgb|hsl)a?\(([^)]*)\)", c)
    args = re.split(r"\s*[\s,/]\s*", m.group(2).strip())[:3] if m else []
    if len(args) < 3 or not all(re.fullmatch(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:%|deg)?", a) for a in args):
        return None
    num = [float(re.sub(r"%|deg", "", a)) for a in args]
    if m.group(1) == "rgb":
        return tuple(round(min(255, max(0, n * 2.55 if a.endswith("%") else n))) for n, a in zip(num, args))
    s, l = (min(100, max(0, n)) / 100 for n in num[1:])
    return tuple(round(x * 255) for x in colorsys.hls_to_rgb(num[0] % 360 / 360, l, s))


def _ink(value, visible=False):
    """The palette value for one fill, stroke or stop-color: kept when it is one, else the
    nearest ink. none for transparent or empty, #000 for black, a bare url(#id) for a
    gradient, and the main ink G for currentColor, inherit or anything unknown. A visible
    value (a stroke, a <text> fill or an inherited fill) never becomes #000 or #04120a."""
    v = re.sub(r"(?i)\s*!\s*important\s*$", "", value).strip()
    c = v.lower()
    url = re.fullmatch(r"""(?i)url\(\s*(["']?)\s*(#[^"'()\s]+)\s*\1\s*\)""", v)
    rgb = _rgb(c)
    new = (f"url({url.group(2)})" if url else v if c in PALETTE else
           "none" if c in ("", "transparent") else "#000" if rgb == (0, 0, 0) and not visible else
           _nearest_ink(rgb, visible) if rgb else G)
    return value if new == value.strip() else new + value[len(value.rstrip()):]


def repair_svg(svg):
    """Mechanical art fixes before validate(), on the writer's drafts and revisions and on
    staged posts, so validate() never refuses art this could fix. A <line> drawn with x/y gets
    x1/y1, and a missing end defaults to 0 as SVG draws it. Every fill, stroke and stop-color
    (attribute or inline style, with or without !important) gets a palette value from _ink();
    a stroke, a label's fill, a <use> fill or the fill of a container that holds a label (<g>,
    <svg>, <symbol>, <a>) gets one that shows on the background. A container of shapes only
    may still take the background. Only tags change, never the text."""
    def line(m):
        t = m.group(0)
        for a in ("x", "y"):
            if not re.search(rf"(?i)\s{a}1\s*=", t):
                t = re.sub(rf"(?i)(\s){a}(\s*=)", rf"\g<1>{a}1\2", t)
        q = (re.search(r"""=\s*(["'])""", t) or [None, '"'])[1]
        missing = [a for a in ("x1", "y1", "x2", "y2") if not re.search(rf"(?i)\s{a}\s*=", t)]
        return t[:5] + "".join(f" {a}={q}0{q}" for a in missing) + t[5:]

    def ink(m, visible):
        attr = re.match(r"[\w-]+", m.group(1) or m.group(4)).group(0).lower()
        visible = attr == "stroke" or (attr == "fill" and visible)
        if m.group(1):
            return m.group(1) + m.group(2) + _ink(m.group(3), visible) + m.group(2)
        return m.group(4) + _ink(m.group(5), visible)

    def tag(t):
        element = (re.match(r"<\s*([\w:-]+)", t.group(0)) or [None, ""])[1].lower()
        visible = element in LABEL_FILL or t.start() in labelled
        return re.sub(rf"""(?i)({INK}\s*=\s*)(["'])(.*?)\2|({INK}\s*:\s*)((?:url\([^)]*\)|[^;"'])+)""",
                      lambda m: ink(m, visible), t.group(0))
    svg = re.sub(r"(?i)<line\b[^>]*>", line, svg)
    labelled, open_ = set(), []  # the containers that hold a <text>, by where their tag starts
    for t in re.finditer(r"<\s*(/?)\s*([\w:-]+)[^>]*?(/?)\s*>", svg):
        element = t.group(2).lower()
        if element == "text" and not t.group(1):
            labelled.update(start for _, start in open_)
        elif element in CONTAINERS and t.group(1):
            while open_ and open_.pop()[0] != element:
                pass
        elif element in CONTAINERS and not t.group(3):
            open_.append((element, t.start()))
    return re.sub(r"<[^>]+>", tag, svg)


# ---------------------------------------------------------------- humanizer
# Cole's humanizer rules (2026-10-11). The prompt carries all ten; this lint checks the ones
# a regex can see, plus claims about his systems (see "claims" below). main() asks for up to
# three revisions when it finds any; a style problem never blocks a publish, and only the
# must-not-ship claims are cut before one. It runs on the writer's own drafts only:
# apply_staged.py uses validate(), not this.
MAX_WORDS = 16
BANNED = re.compile(
    r"\b(pivotal|crucial(?:ly)?|enhanc(?:e|es|ed|ing|ements?)|underscor(?:e|es|ed|ing)|"
    r"landscapes?(?! (?:mode|orientation|layout|view|contractors?|crews?|trades?|bids?)\b)|vibran(?:t|cy)|"
    r"testaments?|foster(?:s|ed|ing)?|delv(?:e|es|ed|ing)|showcas(?:e|es|ed|ing)|intricate(?:ly)?|"
    r"intricacies|evolv(?:e|es|ed|ing)|seamless(?:ly)?|tapestry|tapestries|transformative|groundbreaking|"
    r"game[- ]chang(?:er|ers|ing)|paradigms?|realms?)\b", re.I)
_BE = r"(?:it|this|that)(?:'s| is| was)"
_NEG = r"(?:\b(?:is|was|are|were)(?:n't| not)|'s not|'re not)\b"
_START = r"(?:^\s*|[.?!]\s+)"
LINT = [(re.compile(rx, re.I | re.M), label) for rx, label in (
    (rf"\b{_BE}\s+not\b[^.?!]{{0,80}}?[,;:—–]\s*{_BE}\b", "contrast structure (It's not X, it's Y)"),
    (r"\b(?:isn't|is not|wasn't|was not|aren't|are not)\b[^.?!]{0,60}?[,;:—–]\s*"
     r"(?:it|they|this|that)(?:'s|'re| is| are)\b", "contrast structure (It's not X, it's Y)"),
    (rf"{_NEG}[^.?!]{{1,70}}[.?!]\s+(?:it|they)(?:'s|'re| is| was| are| were)\b",
     "contrast structure (It's not X. It's Y.)"),
    (r"\b(this|that|the \w+) (?:is|was)(?:n't| not)\b[^.?!]{1,70}[.?!]\s+\1(?:'s| is| was)\b",
     "contrast structure (It's not X. It's Y.)"),
    (r"\bI can\b[^.?!]{1,80}[.?!]\s+I (?:cannot|can't|can not)\b", "contrast structure (I can X. I cannot Y.)"),
    (r"\bnot (?:just|only|merely|simply)\b", "contrast structure (not just X but Y)"),
    (r"\b(?:despite|in spite of)\b", "contrast structure (Despite this)"),
    (rf"{_START}(?:Even so|That said|And yet|Still|Yet|Nonetheless|Nevertheless),", "contrast structure (Despite this)"),
    (rf"{_START}Not because\b", "contrast structure (Not because X. Because Y.)"),
    (rf"{_START}(?:Not|No) [^.?!]{{1,60}}\.\s+(?:Not|No) [^.?!]{{1,60}}\.", "contrast structure (Not A. Not B.)"),
    (r",\s+not\s+(?!(?:coincidentally|surprisingly|to mention|least|counting|including|yet|always|"
     r"all|much|so much|quite|once|necessarily|exactly)\b)\w[^,.;:?!—\n]{0,40}", "contrast structure (X, not Y)"),
    (r"\b(?:experts?|analysts?|observers|commentators|insiders|pundits|critics|skeptics|sources)\s+"
     r"(?:have\s+|had\s+)?(?:say|says|said|believe|believes|warn|warned|argue|argued|note|noted|agree|"
     r"predict|predicted|suggest|expect|expected|estimate|estimated|think|claim|claimed|caution|"
     r"cautioned|point out|pointed out)\b", "vague authority"),
    (r"\baccording to (?:some |many |most |several )?(?:experts|analysts|observers|insiders|critics|"
     r"sources|industry \w+)\b", "vague authority"),
    (r"\bpeople (?:familiar with|close to) the (?:matter|company|deal|talks|plans?)\b", "vague authority"),
    (r"\breportedly\b", "vague authority"),
    (r"\bindustry (?:reports?|watchers|insiders|observers|experts)\b", "vague authority"),
    (r"\b(?:many|some) (?:\w+ )?(?:believe|say|argue|think|would argue)\b", "vague authority"),
    (r"\bstudies (?:show|suggest|have shown)\b", "vague authority"),
    (r"\b(?:widely|generally) (?:believed|accepted|regarded|agreed|reported)\b", "vague authority"),
    (rf"{_START}(?:(?:In conclusion|In summary|In short|To sum up|Ultimately|All in all|At the end of "
     r"the day|In the end|The bottom line|Bottom line)\b|Overall,|The (?:takeaway|lesson)s?(?: here)?"
     r"(?: (?:is|was|for)\b|:))", "summary ending"),
    (r"\b(?:two|three|four|five|six) (?:stories|headlines|announcements),? one (?:pattern|thread|theme|"
     r"lesson|story)\b|\bthe (?:common|connecting) thread\b|\bthe pattern is (?:clear|consistent|"
     r"obvious|the same)\b", "summary ending"),
    (r"\b(?:the (?:broader|bigger|larger|wider) (?:picture|trend|story|lesson|implications?)|this "
     r"(?:matters|is significant|is important) because|(?:it'?s )?worth noting|marks a (?:turning "
     r"point|shift|milestone)|a new era|sea change|watershed|far-reaching|inflection point|raises? "
     r"(?:\w+ )?questions|the implications|at a time when|in an era (?:of|where|when)|why (?:it|this) "
     r"matters|(?:is|was) a reminder that|(?:a|an|the) (?:big|important|significant|major|huge) "
     r"(?:deal|step|moment|shift))\b", "importance sentence"),
    (rf"\b(?:now more than ever|the future (?:is|belongs)|we all need|we must|let'?s (?:be honest|face "
     rf"it|dive)|folks)\b|{_START}(?:so |and )?(?:it'?s|it is) time (?:to|for)\b", "motivational or stage tone"),
    (r"\bthe question (?:is|was) (?:not )?(?:whether|what|who|how|why)\b", "importance sentence (the question is)"),
    (r"\bthe (?:number|thing|part|line|detail) that matters\b|\bmeans nothing if\b|\bthe distinction matters\b|"
     r"\bthe first published evidence\b", "importance sentence"),
    (r"(?-i:\bI) (\w+)\b[^.?!]{1,80}[.?!]\s+(?-i:I) (?:do not|don't|did not|didn't|cannot|can't) \1\b",
     "contrast structure (I have X. I do not have Y.)"),
    (r"\bmeans?\b[^.?!]{1,80}[.?!]\s+(?:it|that|this) (?:does not|doesn't) mean\b",
     "contrast structure (X means A. It does not mean B.)"),
    (r"\b(?:is|are) in\b[^.?!]{1,60}[.?!]\s+(?:it|that|this|they) (?:is|are)(?: not|n't) in\b",
     "contrast structure (X is in A. It is not in B.)"),
)]
# "The weights did not." after a sentence that says what did: the blog's old contrast pair.
# Idioms like "Payroll lands or it doesn't." are left alone.
ELLIPTICAL = re.compile(
    r"^(?!.*\bor\b).*(?:\b(?:did|does|do|is|was|are|were|has|have|had|will|can|could|would|should)"
    r"(?: not|n't)(?: (?:ship|change|move|work))?(?: yet)?|\bcannot|\bnever (?:did|does|do|has|have|had|"
    r"was|were|will|shipped|changed|moved|came|arrived)|,? not so much|\banyway)[.?!]$", re.I)
NEG = re.compile(r"(?i)\b(?:not|never|no|cannot)\b|n't\b")
# A short follow-up that only takes back what the sentence before it said ("It does not mean...").
UNDERCUT = re.compile(r"^(?:It|They|That|This|The \w+) (?:does|do|did|is|are|was|were|has|have|had)(?: not|n't)\b")
# A rollout title that runs two clauses together: "... through DNS and auditors found ...". The
# words before "and" need a verb of their own, so a compound subject ("Robots and humans signed
# a pact", "a billion users and one shared key") is one clause.
_VERB = (r"(?:\w+ed|is|are|was|were|has|have|had|did|does|found|saw|got|went|took|made|said|ran|left|kept|lost|"
         r"won|hit|cut|set|put|sent|built|paid|fell|rose|grew|came|became|began|broke|shut|sold|bought|told|"
         r"wrote|stole|opens|closes|ships|wins|loses|gets|goes|says|finds|takes|makes)")
AND_CLAUSE = re.compile(
    r"\band (?:(?:the|a|an|its|their|his|her|one|two|three|four|five|six|\d+) )?(?:(?!that\b|which\b|who\b)"
    rf"[\w'.-]+ ){{1,2}}{_VERB}\b", re.I)
HAS_VERB = re.compile(rf"\b{_VERB}\b", re.I)
# A one-liner that turns on "but ... not", ", never" or a closing "anyway". Checked in the title,
# caption and blockquote only: in body prose these words are ordinary.
TURN = re.compile(r"\b(?:but|yet)\b[^.?!]*?(?:\b(?:not|never|no|nothing)\b|n't\b)|,\s*never\b|\banyway[.?!]?$", re.I)
STRIP_TAGS = re.compile(r"(?i)</?(?:cite|strong|b)\b[^>]*>")  # cite renders as italics; bold is banned
# Problems in these fields are must-fix: a revision that leaves one loses to one that doesn't.
MUST_FIX = ("title:", "blockquote:", "svg_caption:", "svg_inner: the caption")
STOP = set("""about after again also because been before being between both could does doing down
during each every from further have having here into just like more most much never next only other
over same should some such than that their them then there these they this those through under until
very what when where which while will with would your""".split())


def _plain(fragment):
    t = re.sub(r"\{link:[a-z0-9\-]+\|([^}]*)\}", r"\1", fragment or "")
    t = re.sub(r"\s*\n\s*", " ", t)  # hard-wrapped source lines are not sentence breaks
    t = re.sub(r"(?i)</(?:p|h[1-6]|li|blockquote|div)>|<br\s*/?>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return t.replace("’", "'").replace("‘", "'")


_BREAK = re.compile(r"(?:(?<=[.?!])|(?<=[.?!][\"'”)]))\s+")
_ABBREV = re.compile(r"(?:\b(?:[A-Z]\.){2,}|\b(?:Inc|Corp|Co|Ltd|St|vs|Mr|Mrs|Ms|Dr|Jr|Sr)\.|\b(?:e\.g|i\.e)\.|"
                     r"(?<![\w.°])[A-Z]\.)$")


def _breaks(text):
    """The sentence breaks in a run of text: space after . ? or ! (and a closing quote or
    bracket). Never after an abbreviation (U.S., Inc., vs., e.g., Dr., a single initial), or
    after "No." when a number follows."""
    return [m for m in _BREAK.finditer(text) if not _ABBREV.search(text, max(0, m.start() - 20), m.start())
            and not (text.endswith("No.", 0, m.start()) and re.match(r"\d", text[m.end():m.end() + 1]))]


def _sentences(text):
    out = []
    for block in text.split("\n"):
        cuts = [0] + [x for m in _breaks(block) for x in (m.start(), m.end())] + [len(block)]
        for s in (block[a:b] for a, b in zip(cuts[::2], cuts[1::2])):
            s = " ".join(s.split())
            if s:
                out.append(s)
    return out


def _words(s):
    return sum(1 for w in s.split() if re.search(r"\w", w))


SMALL = set("a an and as at but by for from in into is nor of on or per the to via vs with".split())


def _title_case(s):
    """True for a Title-Case heading or label: no closing period, most content words capitalized."""
    content = [w for w in re.findall(r"[A-Za-z][\w'-]*", s) if w.lower() not in SMALL]
    return (not s.rstrip("\"')”’").endswith(".") and len(content) >= 2
            and sum(w[0].isupper() for w in content) >= max(2, 0.75 * len(content)))


def _clip(s, n=110):
    return s if len(s) <= n else s[:n - 1] + "…"


def _norm(t):
    return " ".join(re.sub(r"[^\w']+", " ", (t or "").lower()).split())


def _keywords(text):
    """Content words of a heading or paragraph, crudely singular, for the recap check."""
    return {w.rstrip("s") for w in re.findall(r"[a-z][a-z'-]{3,}", text.lower()) if w not in STOP}


def _whole_sentence(body, start, end):
    """True when body[start:end] (a link) is the whole sentence it sits in."""
    before = _plain(body[:start]).split("\n")[-1].strip()
    return (not before or before[-1] in ".?!:") and re.match(r"""\s*[.?!]["'”)]?(?:\s|<|$)""", body[end:]) is not None


def _text_box(attrs, text):
    """Rough extent of an SVG <text>: monospace glyphs are about 0.6 em wide."""
    def num(name, default):
        m = re.search(rf"""(?i)(?:^|[\s;"']){name}\s*(?:=\s*["']|:)\s*(-?[\d.]+)""", attrs)
        try:
            return float(m.group(1)) if m else default
        except ValueError:
            return default
    size, x, y = num("font-size", 16.0), num("x", 0.0), num("y", 0.0)
    w = 0.6 * size * len(text)
    anchor = (re.search(r"""(?i)text-anchor\s*(?:=\s*["']|:)\s*(\w+)""", attrs) or [None, "start"])[1].lower()
    x0 = x - w / 2 if anchor == "middle" else x - w if anchor == "end" else x
    return x0, x0 + w, y - 0.8 * size, y


def _recent_sentences(skip_title=""):
    """Every sentence of six words or more in the last seven catalog posts."""
    return {_norm(s) for p in ALL[-7:] if p["title"] != skip_title
            for s in _sentences(_plain(p["body"])) if _words(s) >= 6}


def humanizer_problems(post):
    """Every humanizer rule break a regex can see, one line per instance (shown to the model),
    then claims about Cole's systems. Must-fix fields go first and long-sentence lines last, so
    the 40-line cap in humanize() never hides the rest."""
    probs = []
    full_title = post.get("title") or ""
    title = re.sub(r"^Rollout Report:\s*", "", full_title)
    body = post.get("body_html") or ""
    prose = re.sub(r"(?is)<blockquote>.*?</blockquote>", "", body)
    quotes = re.findall(r"(?is)<blockquote>(.*?)</blockquote>", body)
    texts = re.findall(r"(?s)<text\b([^>]*)>(.*?)</text>", post.get("svg_inner") or "")
    art = "".join(f"<p>{t}</p>" for _, t in texts)
    for name, raw in (("title", title), ("desc", post.get("desc")), ("svg_caption", post.get("svg_caption")),
                      ("svg_inner", art), ("body_html", prose), ("blockquote", "".join(f"<p>{q}</p>" for q in quotes))):
        text = _plain(raw)
        sents = _sentences(text)
        for s in sents:
            for m in BANNED.finditer(s):
                word = m.group(0)
                if (name != "svg_inner" and word[0].isupper() and word[1:].islower() and not _title_case(s)
                        and s[:m.start()].strip(" \"'“‘([")):
                    continue  # a name mid-sentence: "the Foster report", "buys Crucial SSDs"
                probs.append(f'{name}: banned word "{m.group(0)}"')
        for rx, label in LINT:
            probs += [f'{name}: {label}: "{_clip(" ".join(m.group(0).split()))}"' for m in rx.finditer(text)]
        if "!" in text:
            probs.append(f"{name}: exclamation point")
        for prev, s in zip([""] + sents, sents):
            n = _words(s)
            if n > MAX_WORDS:
                probs.append(f'{name}: {n}-word sentence, split it: "{_clip(s, 160)}"')
            if name == "title" or not prev:
                continue
            if n <= 12 and ELLIPTICAL.search(s):
                probs.append(f'{name}: contrast structure (X did. Y did not.): "{_clip(prev, 80)} {s}"')
            elif n <= 12 and UNDERCUT.match(s) and not NEG.search(prev):
                probs.append(f'{name}: contrast structure (X does. It does not.): "{_clip(prev, 80)} {s}"')
            elif (prev.startswith("The ") and s.startswith("The ") and n <= MAX_WORDS and NEG.search(s)
                  and not NEG.search(prev) and prev.split()[1].lower() == s.split()[1].lower()):
                probs.append(f'{name}: contrast structure (The X. The X not.): "{_clip(prev, 80)} {s}"')
    clauses = [c.strip() for c in re.split(r"[,;]", title)[1:]]
    if (len(_sentences(title)) >= 2 or re.search(r"(?i),\s*not\b", title)
            or any(c and _words(c) <= 12 and ELLIPTICAL.search(c.rstrip(".?!") + ".") for c in clauses)):
        probs.append(f'title: two sentences or a contrast, make it one plain sentence: "{title}"')
    joined = AND_CLAUSE.search(title)
    if (full_title.startswith("Rollout Report:") and joined
            and HAS_VERB.search(re.split(r"[,;]", title[:joined.start()])[-1])):
        probs.append(f'title: two clauses joined by "and"; keep the one image: "{title}"')
    cap = _plain(post.get("svg_caption"))
    if len(_sentences(cap)) >= 2:
        probs.append(f'svg_caption: two or more sentences, make it one line: "{_clip(cap.strip())}"')
    if post.get("svg_inner") and _norm(cap) and f" {_norm(cap)} " not in f" {_norm(_plain(art))} ":
        probs.append("svg_inner: the caption <text> must repeat svg_caption word for word")
    moved = re.search(r"(?i)<g\b[^>]*transform", post.get("svg_inner") or "")
    for attrs, t in ([] if moved else texts):
        t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        x0, x1, top, y = _text_box(attrs, t)
        if t and "transform" not in attrs and (x0 < -2 or x1 > 642 or top < -2 or y > 302):
            probs.append(f'svg_inner: this <text> runs past the 640x300 frame; shorten it or move it: "{_clip(t, 60)}"')
    old_titles = [_norm(p["title"]) for p in ALL]
    seen = {}
    for m in re.finditer(r"\{link:([a-z0-9\-]+)\|([^}]*)\}", body):
        slug, a = m.groups()
        seen[slug] = seen.get(slug, 0) + 1
        if not 2 <= _words(a) <= 6:
            probs.append(f'body_html: crosslink anchor must be a 2-6 word phrase: "{_clip(a, 80)}"')
        elif _whole_sentence(body, m.start(), m.end()):
            probs.append(f'body_html: crosslink anchor is a whole sentence; link a phrase inside your sentence: "{_clip(a, 80)}"')
        elif _words(a) >= 3 and any(t.startswith(_norm(a)) for t in old_titles):
            probs.append(f'body_html: crosslink anchor repeats an old title; describe the post instead: "{_clip(a, 80)}"')
    probs += [f"body_html: link {s} once, not {n} times" for s, n in seen.items() if n > 1]
    hrefs = {}
    for m in re.finditer(r'(?is)<a\b[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', body):
        url, a = m.group(1), " ".join(_plain(m.group(2)).split())
        hrefs[url] = hrefs.get(url, 0) + 1
        if _words(a) > 6 or (_words(a) >= 3 and (a[-1:] in ".?!" or _whole_sentence(body, m.start(), m.end()))):
            probs.append(f'body_html: source link text must be a 2-6 word noun phrase, never the sentence: "{_clip(a, 80)}"')
    probs += [f"body_html: link each source once; this URL is linked {n} times: {u}" for u, n in hrefs.items() if n > 1]
    for q in quotes:
        q = _plain(q).strip()
        if _words(q) > MAX_WORDS or len(_sentences(q)) >= 2:
            probs.append(f'blockquote: must be one line of {MAX_WORDS} words or fewer: "{_clip(q)}"')
    for name, line in [("title", title), ("svg_caption", cap)] + [("blockquote", _plain(q)) for q in quotes]:
        if TURN.search(line.strip()):
            probs.append(f'{name}: contrast structure (X, but Y does not): "{_clip(line.strip())}"')
    if re.search(r"(?i)<(?:strong|b|i|cite)\b", body):
        probs.append("body_html: bold, <i> and <cite> are not allowed; restate sources in your own words")
    for m in re.finditer(r"<(?i:em)>\s*([a-z][^<]{0,200}?)\s*</(?i:em)>", body):
        probs.append(f'body_html: <em> used for emphasis: "{_clip(" ".join(m.group(1).split()), 60)}"')
    if _body_words(post) >= 300 and not re.search(r"(?i)\byou(?:r|rs|rself|'re|'ve|'ll|'d)?\b", _plain(body)):
        probs.append('body_html: the post never talks to its reader; address one person as "you" at least once')
    heads = [_keywords(_plain(h)) for h in re.findall(r"(?is)<h3\b[^>]*>(.*?)</h3>", body)]
    paras = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", prose)
    if len(heads) >= 3 and paras:
        last = _keywords(_plain(paras[-1]))
        hit = sum(1 for i, h in enumerate(heads) if (h - set().union(*heads[:i], *heads[i + 1:])) & last)
        if hit >= 3:
            probs.append(f"body_html: the last paragraph recaps {hit} sections; end on one concrete detail instead")
    recent = _recent_sentences(full_title)
    probs += [f'body_html: repeats a sentence from a recent post: "{_clip(s)}"'
              for s in _sentences(_plain(prose)) if _words(s) >= 6 and _norm(s) in recent]
    probs += claim_problems(post)
    probs = list(dict.fromkeys(probs))
    return sorted(probs, key=lambda p: (not _must(p), "-word sentence" in p))


# ---------------------------------------------------------------- claims
# Facts about Cole's systems come only from SYSTEM_FACTS. A sentence that names one of them
# (or follows one with "It"/"The table"/...) and states a stack, host, storage, logging,
# headcount, permission or past action goes back for revision. A few claims must never ship
# at all: Atelier keeping prompts or answers, a stack/version/exposure/patch claim, a
# first-person leaked-credentials story or story about his logs, keys or infrastructure (and
# the rest of its paragraph), a crime stated as fact, a stack, storage, auth, count or other
# sheet term for one of his systems that its SYSTEM_FACTS line does not state, and the same
# terms said of all his systems at once. Each term answers to the system named nearest before
# it. drop_high_risk() cuts any that are still there after the revisions, from the art's
# labels and the alt text too. Checks run clause by clause, so a trailing "so I would
# check..." never excuses the clause before it.
# Each system by brand or domain, then by the plain name a post gives it ("the flight planner").
# A plain name is his: across the posts it almost always is. It is someone else's product only
# when the post says so: "the flight planner in ForeFlight", "the Twilio dialer in most CRMs",
# "In ForeFlight, the flight planner", "Procore said the estimating tool", or a company's
# product news in that sentence or the one before it (NEWS). Then it is loose and gets soft
# labels only.
_THEIRS = (r"(?!\s+(?:in|at|from|by|inside|of)\s+(?:(?-i:(?!(?:January|February|March|April|May|June|July|August|"
           r"September|October|November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b)[A-Z])|"
           r"(?:most|many|other|every|their|its|some)\b))")
# a capitalized name that can be a company: not a sentence opener, a month or day, or a plural
# of people ("Pilots testing the flight planner")
_COMPANY = (r"(?!(?:I|A|An|The|This|That|These|Those|It|Its|We|Our|My|On|In|At|By|For|Last|Next|Every|Each|When|"
            r"After|Before|If|Then|Now|Today|And|But|So|Cole|January|February|March|April|May|June|July|August|"
            r"September|October|November|December|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Users|"
            r"Pilots|Testers|Customers|Clients|Workers|Crews|Contractors|Developers|Engineers|Researchers|Teams|"
            r"Owners|Members|People|Agents|Analysts|Officials|Regulators|Lawyers|Prosecutors)\b)"
            r"[A-Z][\w.&-]*(?:\s+[A-Z0-9][\w.&-]*){0,3}")
# "Hinge launched a photo coach.", "Procore shipped an estimating assistant", "Hinge is testing
# a photo coach": a named company's product news, so "the dating-profile tool" right after it
# is that product
NEWS = re.compile(
    rf"(?-i:(?<![\w'’-])({_COMPANY}))"
    r"\s+(?:(?:has|have|had|is|are|was|were|just|now|also|quietly|finally)\s+)*"
    r"(?:launch(?:ed|es|ing)|ship(?:ped|s|ping)|releas(?:ed|es|ing)|announc(?:ed|es)|unveil(?:ed|s)|introduc(?:ed|es)|"
    r"roll(?:ed|s|ing) out|debut(?:ed|s)|add(?:ed|s)|buil(?:t|ds)|open(?:ed|s)|acquir(?:ed|es)|bought|buys|"
    r"updat(?:ed|es)|upgrad(?:ed|es)|demo(?:ed|s)|preview(?:ed|s)|offers|puts? out|test(?:s|ed|ing)|"
    r"pilot(?:s|ed|ing))\b", re.I)
# "In ForeFlight, the flight planner...", "According to Procore, the estimating tool...",
# "Procore said the estimating tool...": the plain name right after is that company's
ATTRIB = re.compile(rf"(?-i:(?:\b[Ii]n|\b[Aa]ccording to)\s+({_COMPANY})\s*,\s*|(?<![\w'’-])({_COMPANY})\s+"
                    r"(?:said|says|reported|reports|wrote|writes|noted|notes|claims|claimed)(?:\s+that)?\s+)$")
# The AI labs, clouds and payment vendors whose news opens most tie-in paragraphs. None of them
# makes "the permit app", so their news makes a plain name theirs only when it shares the
# name's field (DOMAIN): "Google launched a flight planner".
VENDOR_NAMES = re.compile(r"\b(?:GitHub|Apple|Salesforce)\b")
DOMAIN = {"Coen ERP": r"dialers?|snow|crews?", "estimate.pro": r"estimat\w*|bids?|takeoffs?",
          "JetDesk": r"flights?|NOTAMs?|EFBs?|pilots?|aviation", "North Point": r"contractors?",
          "Valhalla K9": r"dogs?|K9|training", "Hire Mariaelena": r"freelanc\w*|r[ée]sum[ée]s?|portfolios?",
          "Show It With Words": r"jewelry|beads?", "PermitSketch": r"permits?",
          "Keep Fix Cut": r"dating|profiles?|photos?", "Base44 apps": r"smart-home|IPTV|honey|cosmetics"}
_NAMES = (
    ("Coen ERP", r"\bCoen\b|coenconstruction\.com|\bthe construction ERP\b|\b(?:my|our|his) (?:construction )?ERP\b",
                 r"\bthe Twilio dialer\b|\bthe snow(?:[- ]operations)? module\b|\bthe crew apps?\b"),
    ("estimate.pro", r"\bestimate\.pro\b|\bmy estimating (?:SaaS|tool|suite|platform|app|system|agent|interface)\b",
                     r"\bthe estimating (?:SaaS|tool|suite|platform|app|system|agent|interface)\b"),
    ("CurbScript", r"\bcurbscript\b", ""),
    ("The Punchlist", r"(?-i:\bPunchlist\b|\bPUNCHLIST\b)|\bthepunchlist\b", ""),
    ("JetDesk", r"\bjetdesk\b", r"\bthe flight[- ]plann(?:er|ing (?:PWA|app|desk|tool))\b"),
    ("North Point", r"\bNorth Point Construction\b|\bnorth\.construction\b", r"\bthe contractor site\b"),
    ("Valhalla K9", r"(?-i:\bValhalla\b|\bVALHALLA\b)|\bvalhalla-k9\b",
                    r"\bthe dog[- ]training (?:site|platform|company|business)\b|\bthe K9 (?:site|business|company)\b"),
    ("Hire Mariaelena", r"\bhire ?mariaelena\b", r"\bthe (?:freelancer|résumé|resume) (?:portfolio|site|page)\b"),
    ("Show It With Words", r"(?-i:Show It With Words|SHOW IT WITH WORDS)|\bshowitwithwords\b",
                           r"\bthe (?:jewelry|bead) (?:site|storefront|store|shop)\b"),
    ("PermitSketch", r"\bpermitsketch\b",
                     r"\bthe permit(?:[- ](?:drawing|sketching))? (?:app|tool|platform)\b|\bthe permit sketcher\b"),
    ("Atelier", r"(?-i:\bAtelier\b|\bATELIER\b)|\batelier\.ciprari\.ai\b|\bmy (?:AI )?studio\b", ""),
    ("Keep Fix Cut", r"\bkeep ?fix ?cut\b", r"\bthe dating[- ]profile (?:teardown|tool|app|site)\b"),
    ("Base44 apps", r"(?-i:(?<!Amazon )(?<!AWS )\bAurora\b(?! (?:DB|Serverless|PostgreSQL|MySQL|Innovation))|\bAURORA\b)|"
                    r"\bNorthern Hardy Honey\b|\bMari' Cosmetics\b",
                    r"\bthe (?:smart-home|IPTV) (?:platform|app)\b|\bthe (?:three )?Base44 (?:apps|stack)\b|"
                    r"\bthe (?:honey|cosmetics) (?:shop|store|storefront|site)\b"),
)
SYSTEMS = [(name, re.compile(f"{brand}|(?:{plain}){_THEIRS}" if plain else brand, re.I)) for name, brand, plain in _NAMES]
BRANDS = [(name, re.compile(brand, re.I)) for name, brand, _ in _NAMES]
NO_AI = {"Valhalla K9", "Hire Mariaelena", "Show It With Words"}
# A bare "the ERP" is Cole's only when the post names his ERP and no vendor's. Otherwise it
# counts for the soft labels alone: a news line about SAP's ERP is never cut.
BARE_ERP = re.compile(r"\bthe ERP\b(?! (?:vendors?|makers?|market|industry|sector)\b)|"
                      r"\bthe payroll (?:system|module|integration)\b", re.I)
ERP_VENDOR = re.compile(r"\b(?:SAP|Oracle|NetSuite|Workday|Dynamics|Infor|Epicor|Sage|Odoo|Acumatica|Dolibarr|"
                        r"Deltek|Syspro|Unit4|IFS|JD Edwards|PeopleSoft|Procore|Viewpoint)\b")
# "It" or "The table" right after a sentence about a system is still about that system.
CARRY = re.compile(r"^(?:It|Its|They|Their|This|That|These|Those|Both|All three|The others|The (?:D1 )?(?:table|"
                   r"log|logs|ledger|database|router|worker|app|studio|tool|platform|session|token|cookie|codebase|"
                   r"stack|server|site|teardown|planner|module|suite))\b")
WOULD = re.compile(r"(?-i:\bI)(?:'d|'ll| would| will| might| could| should| want to| plan to| need)\b|\bif I\b|"
                   r"\bwould (?:check|look|ask|want|test)\b", re.I)
GENERIC = re.compile(r"\b(?:my|our) (?:own )?(?:platforms?|systems?|apps?|sites?|stack|servers?|products?|"
                     r"codebases?|integrations?)\b|\b(?:those|these|both|all (?:three|four|five)|every one of those) "
                     r"(?:systems|platforms|apps|sites)\b|\bthe (?:systems|platforms|apps) I (?:run|built|ship)\b|"
                     r"^(?:Each|Every) (?:platform|integration|system)\b|^None of (?:my|them)\b", re.I)
ME = re.compile(r"(?-i:\bI) (?:log|store|keep|retain|monitor|run|host|patch|track|record|save|delete|rotate|use|pin)\b|"
                r"\bmy (?:own )?(?:logs?|keys?|systems?|platforms?|apps?|sites?|stack|servers?|code(?:base)?|database|"
                r"tables?|users|testers|customers|clients|crews?|integrations?|test suite|tests)\b", re.I)
FIRST = re.compile(r"(?-i:\bI\b)|\b(?:my|me|our)\b", re.I)
# must not ship
# "keeps writing" is not keeping anything; "keeps nothing" and "keep anything" are
_GOING = r"(?!\s+(?!(?:no|any|some|every)thing\b)\w+ing\b)"
STORE = re.compile(r"\b(?:log(?:s|ged|ging)?|stor(?:e|es|ed|ing)|retain(?:s|ed|ing)?|(?:keep(?:s|ing)?|kept)" + _GOING + r"|"
                   r"sav(?:e|es|ed|ing)|record(?:s|ed|ing)?|hold(?:s|ing)?|held|writes?|wrote|tables?|database)\b|"
                   r"(?-i:\bD1\b)", re.I)
CONTENT = re.compile(r"\b(?:prompts?|answers?|responses?|conversations?|exchanges?|chats?|messages?|transcripts?|"
                     r"what (?:the |a |each )?(?:users?|testers?|person) (?:asked|typed|sent|wrote)|"
                     r"what the model (?:returned|said|answered|wrote))\b", re.I)
LOCAL = re.compile(r"\b(?:browser|IndexedDB|on (?:the|your|my) (?:device|phone|laptop)|locally|local-first|"
                   r"opt-in|sync)\b", re.I)
SERVER = re.compile(r"(?-i:\bD1\b)|\b(?:tables?|databases?|servers?)\b", re.I)
# A sentence's clauses. Each is checked on its own, so "X, so I would check Y" still answers for X.
CLAUSE = re.compile(r",\s*(?:so|and|but|then|because)\b|;|:(?!\d)", re.I)
# an art label's count of none, "NOTAMS: NONE" or "D1 TABLES: 0", denies the thing it counts
NONE_LABEL = re.compile(r"\b([\w-]+)\s*:\s*(?:none|no|zero|0)(?=\s*$|\s*[.,;!?)]|\s+(?-i:[A-Z0-9][A-Z0-9-]*\b))",
                        re.I)
RUNS_ON = re.compile(r"\b(?:runs?|running|ran) on\b|\b(?:sits?|sat) (?:on|behind|exposed)\b|\b(?:hosted|deployed) on\b",
                     re.I)
_BUG = r"(?:bugs?|flaws?|CVEs?|vulnerabilit(?:y|ies)|exploits?|holes?)"
TECH = re.compile(r"(?-i:\bPHP\b|\bPython\b|\bVPS\b)|\bv?\d+\.\d+\.\d+\b|\bversion \d+(?:\.\d+)*\b|\bexposed\b|"
                  rf"\b(?:un)?patched\b|\bvulnerable\b|\bsat (?:on|exposed)\b|\b{_BUG}\b[^.?!]{{0,40}}\bfor \d+ days\b|"
                  rf"\bfor \d+ days\b[^.?!]{{0,40}}\b{_BUG}\b", re.I)
MY_SYSTEMS = re.compile(r"\bmy (?:own )?(?:systems?|platforms?|apps?|sites?|stack|servers?|code(?:base)?)\b|"
                        r"(?-i:\bI) (?:patched|upgraded|updated|run|ran|host|hosted|migrated|deployed|left)\b", re.I)
KEY = re.compile(r"\b(?:API keys?|keys?|credentials?|secrets?|passwords?|(?:API|access|bearer|auth) tokens?)\b", re.I)
LEAK = re.compile(r"\.env\b|\b(?:in|to|into) (?:the|a|my|our|that) (?:repo|repository|branch|codebase)\b|"
                  r"\bcommitted\b|\bleaked\b|\bexpos(?:ed|ure)\b|\bsat in\b|\blived in\b|"
                  r"\banyone with access\b|\bplain ?text\b|\breadable\b|\bpublic (?:repo|branch|bucket|gist)\b|"
                  r"\bhard-?coded\b", re.I)
# "if it leaked", "unless the key sits in": a what-if, not a story
HYPO = re.compile(r"\b(?:if|unless|in case)\b|\bwould\b", re.I)
CRIME = (r"(?:planted|plants|stole|steals|hacked|bugged|embezzled|defrauded|smuggled|laundered|bribed|murdered|"
         r"assaulted|kidnapped|extorted|blackmailed|stalked|wiretapped|spied on|sabotaged|forged|scammed|swindled|"
         r"trafficked|impersonated|exfiltrated|broke into)\b")
ATTRIBUTED = re.compile(r"\b(?:alleged(?:ly)?|allegations?|alleges?|prosecutors?|complaint|charg(?:ed|es|ing)|"
                        r"indict(?:ed|ment)|accus(?:ed|es|ation)|suspicion|suspected|affidavit|according to|"
                        r"convicted|pleaded|pled|guilty|sentenced|court (?:filings?|documents?|records?|papers)|"
                        r"lawsuit|sued|says?|said|claims?|told)\b", re.I)
FULL_NAME = re.compile(r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?) (?:[A-Z]\. )?([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\b")
NOT_A_NAME = set("""The A An In On At For From When If This That These Those It Its He She They We I My Our And But
Or So Then After Before During Since Until While Security Department Justice Office New San Los Las United States
North South East West Rollout Report January February March April May June July August September October November
December Monday Tuesday Wednesday Thursday Friday Saturday Sunday Google OpenAI Anthropic Meta Microsoft Amazon
Apple Nvidia Cloud Claude Gemini Federal Supreme Court House Senate Governor President Attorney General Police
Act Street Journal Times Post News Wall Silicon Valley White Washington York Bay Area Codex Copilot Grok Llama
Sora Veo Opus Sonnet Haiku Siri Alexa Cortana Spark Terra Carbon Argon Astra Daybreak Mythos Palo Alto Santa
Mountain Menlo Park Redmond Seattle Boston Austin Texas California Virginia Beijing Moscow Tehran Pyongyang""".split())
# a company, lab or threat actor, not a person: "Palo Alto Networks", "Salt Typhoon", "Wheels Inc"
ORG_WORD = (r"(?:Inc|Corp|Corporation|Co|Ltd|LLC|Networks|Labs|Systems|Group|Technologies|Security|Software|"
            r"Solutions|Research|Capital|Partners|Ventures|Holdings|Foundation|Institute|University|College|Bank|"
            r"Motors|Airlines|Health|Media|Games|Analytics|Robotics|Dynamics|Energy|Telecom|Communications|Cloud|"
            r"Intelligence|Agency|Bureau|Ministry|Commission|Council|Committee|Typhoon|Bear|Spider|Panda|Kitten|"
            r"Tempest|Blizzard|Sleet|Sandstorm|Storm|Chollima|Jackal)\b")
# "a scammer posing as Sam Altman stole": the named person is not the one who stole
NOT_THE_DOER = re.compile(r"\b(?:as|of|by|from|with|to|for|against|at|about|like|than|impersonating|"
                          r"pretending to be|named|called)\s+$", re.I)
# the name and the crime verb sit in one clause: a verb or a new clause between them hands the
# crime to someone else ("Palo Alto Networks found the agent exfiltrated")
GAP_STOP = re.compile(r"\bthat\b|,\s*(?:and|but)\b|\b(?:found|finds|said|says|showed|shows|reported|reports|"
                      r"discovered|discovers|warned|warns|noted|notes|wrote|writes|told|tells|believes|believed|"
                      r"thinks|thought|knew|knows|learned|learns|saw|sees|watched|traced|caught|confirmed|confirms|"
                      r"revealed|reveals|argued|argues|added|adds|explained|described|tested|tests|asked|asks|"
                      r"claimed|alleged|is|was|are|were|has|had|have|does|did|will|would|can|could|may|might)\b", re.I)
# soft: back to the model
FACT_OK = re.compile(r"\b(?:runs? on |on |behind |served by |in )?(?:one|a single) Cloudflare Worker\b|"
                     r"\b(?:runs? on |on )?Cloudflare Pages(?: Functions)?\b|\b(?:runs? on |on |built on |is a )?(?:Base44|Vercel)\b|"
                     r"\b(?:in )?local[ -]?storage\b|"
                     r"\brole-based (?:team )?permissions\b|\bhealth monitoring\b|\bhuman review gate\b|"
                     r"(?:\b(?:logs?|stores?|keeps?|saves?|holds?|records?)\s+)?(?:\b(?:never|not|no)\b|n't\b)"
                     r"[^.?!]{0,30}?\b(?:prompts?|answers?|uploads?|reports?|frames?)\b|"
                     r"\b(?:opt-in|private) (?:thread )?sync\b|\b(?:expires? (?:after|in) )?(?:30|thirty)[- ]days?\b|"
                     r"(?-i:\bR2\b)(?=[^.?!]{0,40}\bopt(?:s|ed)?[- ]in\b)|"
                     r"\bIndexedDB\b|\bin (?:the|your) browser\b|\bon (?:the|your) device\b|"
                     r"\busage (?:ledger|analytics)\b|\bhashed session id\b|\bpage memory\b|"
                     r"\b(?:no|not|never|none)\b[^.?!]{0,30}?(?-i:\bPHP\b|\bPython\b|\bVPS\b|\bS3\b)", re.I)
# "None of my systems run PHP. ... Those systems were never vulnerable.": after a denial of
# PHP, Python, a VPS or S3 that the sheet holds, a denial of exposure in that paragraph holds too
STACK_DENIED = re.compile(r"\b(?:no|not|never|none)\b[^.?!]{0,30}?(?-i:\bPHP\b|\bPython\b|\bVPS\b|\bS3\b)", re.I)
UNEXPOSED = re.compile(r"(?:\b(?:never|not)|n't)\s+(?:been\s+)?(?:vulnerable|exposed)\b", re.I)
CLAIM = re.compile(
    r"(?-i:\bPHP\b|\bPython\b|\bNode(?:\.js)?\b|\bRails\b|\bVPS\b|\bD1\b|\bS3\b|\bR2\b)|\bruns? on\b|"
    r"\b(?:hosted|deployed) on\b|\bsits? (?:on|behind)\b|\bv?\d+\.\d+\.\d+\b|\bversion \d|\bpatch(?:ed|es|ing)?\b|"
    r"\bexpos(?:ed|ure)\b|\bvulnerab\w*|\bbreach(?:ed|es)?\b|\bCVE-|\brouting numbers?\b|"
    r"\b(?:\d[\d,]*|ten|twenty|thirty|forty|fifty|a hundred|hundreds of|dozens of) (?:people|employees|workers|"
    r"staff|users|customers|clients|routes|crews)\b|\blog(?:s|ged|ging)?\b(?! ?(?:in|into|on|out)\b)|"
    r"\bstor(?:e|es|ed|ing|age)\b|\bretain(?:s|ed|ing)?\b|\bretention\b|\bmonitor(?:s|ed|ing)?\b|"
    r"\bpermissions?\b|\bdatabases?\b|\btables?\b|\bcron\b|\bwebhooks?\b|\bsecret manager\b|\.env\b|"
    r"\bhundreds of times\b|\bAPI keys?\b|\bcredentials\b", re.I)
DOES_NOT = re.compile(r"\bservice routes?\b|\bzoning\b|(?-i:\bS3\b|\bPHP\b|\bPython\b|\bVPS\b)|"
                      r"\btax (?:filings?|returns?|tables?|forms?)\b|\bfiles? taxes\b|\bNOTAMs?\b", re.I)
AI_WORDS = re.compile(r"(?-i:\bAI\b|\bLLM\b|\bAPI\b|\bGPT)|\b(?:models?|agents?|Claude|inference|prompts?|"
                      r"scor(?:e|es|ed|ing)|classif\w*)\b", re.I)
ATELIER_DETAIL = re.compile(r"\blog(?:s|ged|ging)?\b(?! ?(?:in|into|on|out)\b)|\bstor(?:e|es|ed|ing|age)\b|"
                            r"\bretain\w*|\bretention\b|(?-i:\bD1\b|\bPython\b)|\bexpir\w*|\btokens?\b|"
                            r"\brout(?:e|es|ed|er|ers|ing)\b|\bsessions?\b|\blocalStorage\b|\bcron\b|\bclassif\w*|"
                            r"\bpicks? (?:a|the|which) (?:provider|model|endpoint)\b|\bseven\b", re.I)
NOT_ATELIER_PROVIDER = re.compile(r"\b(?:Mistral|Perplexity|Cohere|Azure|AWS|Amazon|Bedrock|Microsoft|"
                                  r"Hugging ?Face|Together AI|Groq|Fireworks|Replicate|Stability|Midjourney|"
                                  r"ElevenLabs|AI21|OpenRouter|Vertex|Qwen|Alibaba|Moonshot|Kimi)\b")
STORY = re.compile(r"(?-i:\bI) (?:ran|migrated|patched|checked|logged|found|reviewed|audited|rotated|traced|caught|"
                   r"grepped|discovered|upgraded|pulled|counted|measured|tested|deleted|restored|rebuilt|replaced|"
                   r"noticed|fixed|deployed|disabled|enabled|moved|switched|kept|stored|saw|spent|set up|added|"
                   r"removed|turned|wrote(?![^.?!]{0,25}\babout\b)|pinned|installed)\b", re.I)
INFRA = re.compile(r"\b(?:logs?|keys?|firewall|servers?|database|tables?|cron|repo|repository|branch|builds?|"
                   r"credentials|secrets?|migrations?|deploys?|deployments?|endpoints?|webhooks?|stack|codebase|"
                   r"session store|tickets?|patch(?:es)?|backups?|alerts?|dashboards?|dependenc(?:y|ies)|"
                   r"package\.json|tests?|versions?)\b|\.env\b|\blast (?:year|month|week|spring|summer|fall|winter|"
                   r"quarter)\b", re.I)
CRIME_LABEL = "a crime stated as fact"
ATELIER_LABEL = "Atelier logs no prompts or answers (SYSTEM FACTS)"
TECH_LABEL = "a stack, version, exposure or patch claim about Cole's systems"
LEAK_LABEL = "a first-person leaked-credentials story"
STORY_LABEL = "a first-person story about Cole's logs, keys or infrastructure"
TALE_LABEL = "the rest of a first-person story about Cole's systems"
SHEET_LABEL = "a claim about Cole's systems that SYSTEM FACTS does not support"
GENERAL_LABEL = "a first-person claim about all of Cole's systems"
HIGH_FIX = "cut it, or say what you would check instead"
CRIME_FIX = 'attribute it ("prosecutors say", "the complaint alleges") or cut it'
CLAIM_FIX = "say only what SYSTEM FACTS says, or what you would check, or cut it"
LINK_FIX = "it carries a source link, so rephrase it around the link rather than cut it"

# ---- what the sheet supports
# A clause about one of his systems may state a stack, host, storage, logging, auth, count,
# permission, monitoring, routing, payroll, NOTAM or API term only as its SYSTEM_FACTS line
# does: stated where the sheet states it, denied where the sheet denies it. SUPPORT is read
# from SYSTEM_FACTS itself, so changing the sheet changes what passes.
TERMS = [(key, re.compile(rx, re.I)) for key, rx in (
    ("php", r"(?-i:\bPHP\b)"), ("python", r"(?-i:\bPython\b)"), ("node", r"(?-i:\bNode(?:\.js)?\b)|\bnode\.js\b"),
    ("rails", r"(?-i:\bRails\b)"), ("next.js", r"\bNext\.?js\b"), ("react", r"(?-i:\bReact\b)"),
    ("typescript", r"\bTypeScript\b"), ("site builder", r"\b(?:WordPress|Shopify|Wix|Squarespace|Webflow)\b"),
    ("vercel", r"\bVercel\b"), ("cloudflare", r"\bCloudflare\b"),
    # JetDesk runs on Cloudflare Pages; Atelier and Keep Fix Cut each run on a Worker
    ("pages", r"\bCloudflare Pages\b|(?<=\bon )(?-i:Pages\b)|(?-i:\bPages Functions?\b)"),
    # "runs on a Worker", not "Workers at the site found asbestos"
    ("worker", r"(?-i:\bCloudflare Workers?\b)|(?<=[^\s.?!] )(?:a|an|another|one|the|its|their|each|a separate)\s+"
               r"(?-i:Workers?\b)|(?<=\bon )(?-i:Workers\b)"),
    ("base44", r"\bBase44\b"), ("pwa", r"(?-i:\bPWAs?\b)|\bprogressive web apps?\b"),
    ("durable objects", r"\bDurable Objects?\b"), ("kv", r"(?-i:\bKV\b)"), ("r2", r"(?-i:\bR2\b)"),
    ("d1", r"(?-i:\bD1\b)"), ("s3", r"(?-i:\bS3\b)"), ("vps", r"(?-i:\bVPS(?:es)?\b)|\bvirtual private servers?\b"),
    ("aws", r"(?-i:\bAWS\b|\bEC2\b)|\bAmazon Web Services\b"), ("azure", r"\bAzure\b"),
    ("gcp", r"(?-i:\bGCP\b)|\bGoogle Cloud\b"),
    ("other host", r"(?-i:\b(?:Heroku|Netlify|Fly\.io|DigitalOcean|Linode|Hetzner|GoDaddy|Bluehost|GitHub Pages)\b)"),
    ("database", r"\b(?:databases?|Postgres(?:QL)?|MySQL|SQLite|MongoDB|Redis|DynamoDB|Supabase|Firebase|schemas?|"
                 r"(?<!on the )(?<!at the )(?<!off the )tables?)\b"),
    ("indexeddb", r"\bIndexedDB\b"), ("localstorage", r"\blocalStorage\b|\blocal storage\b"),
    ("server", r"\b(?:servers?|data ?cent(?:er|re)s?|VMs?|virtual machines?|Docker|Kubernetes|k8s)\b"),
    ("bucket", r"\bbuckets?\b"), ("cdn", r"(?-i:\bCDNs?\b|\bWAFs?\b)|\bfirewalls?\b"),
    ("cron", r"\bcron\b|\bscheduled jobs?\b"), ("webhook", r"\bwebhooks?\b"),
    ("secrets", r"\b(?:secret managers?|secrets?|credentials?|passwords?|API keys?|access tokens?|private keys?)\b|"
                r"\.env\b"),
    ("encryption", r"\bencrypt(?:s|ed|ing|ion)?\b"), ("api", r"(?-i:\bAPIs?\b)(?! keys?\b)"),
    ("session", r"\bsessions?\b"), ("token", r"\btokens?\b"), ("cookie", r"\bcookies?\b|\bHttpOnly\b"),
    ("passcode", r"\bpasscodes?\b"), ("linkedin", r"\bLinkedIn\b"),
    ("sso", r"(?-i:\bSSO\b|\bJWTs?\b|\bSAML\b)|\bsingle sign-on\b|\bOkta\b|\bOAuth\b"),
    ("stripe", r"\bStripe\b"), ("twilio", r"\bTwilio\b"), ("adp", r"(?-i:\bADP\b)"),
    ("permissions", r"\b(?:permissions?|role-based|access control|least[- ]privilege|RBAC|"
                    r"scoped (?:permissions?|access|tokens?|keys?|roles?))\b"),
    ("monitoring", r"\b(?:monitor(?:s|ed|ing)?|observability|uptime|alert(?:s|ing)?|status page|health checks?)\b"),
    ("review gate", r"\breview gates?\b|\bhuman review\b"), ("payroll", r"\bpayroll\b"),
    ("deposit", r"\b(?:deposits?|routing numbers?|bank accounts?)\b"), ("tax", r"\btax(?:es)?\b"),
    ("routing", r"\brout(?:er|ers|ing)\b(?! numbers?)|\broutes? (?:\w+ ){0,3}?(?:through|via|over|across)\b"),
    ("service route", r"\bservice routes?\b"), ("notam", r"\bNOTAMs?\b"), ("zoning", r"\bzoning\b"),
)]
# AI providers; the sheet's lists are closed, so denying one it does not list is fine
PROVIDERS = [(key, re.compile(rx)) for key, rx in (
    ("anthropic", r"\bAnthropic\b|\bClaude\b"), ("openai", r"\bOpenAI\b|\bChatGPT\b|\bGPT\b|\bGPT-|\bCodex\b"),
    ("google", r"\bGoogle\b(?! Cloud)|\bGemini\b"), ("vertex", r"\bVertex\b"), ("xai", r"\bxAI\b|\bGrok\b"),
    ("z.ai", r"\bZ\.ai\b|\bGLM\b|\bZhipu\b"), ("deepseek", r"\bDeepSeek\b"), ("meta", r"\bMeta\b|\bLlama\b"),
    ("nvidia", r"\bNVIDIA\b|\bNvidia\b|\bNemotron\b"), ("runway", r"\bRunway\b"), ("mistral", r"\bMistral\b|\bMixtral\b"),
    ("perplexity", r"\bPerplexity\b"), ("cohere", r"\bCohere\b"), ("microsoft", r"\bMicrosoft\b|\bCopilot\b|\bAzure\b"),
    ("amazon", r"\bAmazon\b|\bAWS\b|\bBedrock\b"), ("alibaba", r"\bAlibaba\b|\bQwen\b"), ("moonshot", r"\bMoonshot\b|\bKimi\b"),
    ("another provider", r"\bHugging ?Face\b|\bTogether AI\b|\bGroq\b|\bFireworks AI\b|\bReplicate\b|\bMidjourney\b|"
                         r"\bElevenLabs\b|\bAI21\b|\bOpenRouter\b|\bInflection\b|\bStability AI\b"),
)]
# vendors read as news when they lead a clause: "When Cloudflare went down, ..."
VENDORS = {"cloudflare", "pages", "vercel", "aws", "azure", "gcp", "other host", "base44", "stripe", "twilio", "adp",
           "linkedin", "site builder"}
GLOBAL_NEG = {"php", "python", "vps", "s3"}  # "No Cole system uses PHP, Python, a VPS or S3."
GLOBAL_POS = {"platform 15", "system 15"}  # "15 production platforms"
NUMBERS = dict(zip("two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                   "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred "
                   "dozen".split(), [*range(2, 21), 30, 40, 50, 60, 70, 80, 90, 100, 12]))
COUNT_NOUN = (r"(?:people|persons?|employees?|workers?|staff|users?|customers?|clients?|crews?|testers?|tenants?|"
              r"trades?|routes?|towns?|providers?|models?|agents?|accounts?|seats?|members?|subscribers?|scans?|"
              r"airports?|sheets?|apps?|platforms?|systems?|sites?|servers?|endpoints?|integrations?|requests?|"
              r"calls?|jobs?|projects?)")
COUNT = re.compile(rf"(?<![\w.$#-])((?!(?:19|20)\d\d\b)\d[\d,]*\+?|(?:an? )?(?:{'|'.join(NUMBERS)})|dozens|hundreds|"
                   rf"thousands|millions)(?:[\s-]+(?!{COUNT_NOUN}\b|percent\b|per\b|times\b)[\w'’.-]+|"
                   rf"[\s-]+{COUNT_NOUN}(?=[\s-]+{COUNT_NOUN}\b)){{0,2}}?[\s-]+({COUNT_NOUN})\b"
                   rf"(?![\s-]+(?:{COUNT_NOUN}|IDs?|names?|versions?|families|tiers?|keys?|errors?)\b)", re.I)
VAGUE = re.compile(r"\b(?:couple|few|several)\s+(?:of\s+)?$", re.I)  # "a couple dozen trades" counts nothing
NOT_HIS = re.compile(r"\b(?:vendor|third-party|other|outside|competing|rival)\b", re.I)  # "six vendor apps"
# keeping data: these verbs always; keep/hold/record/write only with data, a store or a period
STRONG = re.compile(r"\blog(?:s|ged|ging)?\b(?! ?(?:in|into|on|out)\b)|\bstor(?:e|es|ed|ing|age)\b|"
                    r"\bsav(?:e|es|ed|ing)\b(?! (?:time|money|hours?|minutes?|days?|weeks?|effort|steps?|clicks?|"
                    r"you|a trip)\b)|\bretain(?:s|ed|ing)?\b|\bretention\b|\bpersist(?:s|ed|ing|ence)?\b|"
                    r"\bcach(?:es|ed|ing)\b|\bback(?:s|ed)? up\b|\bbackups?\b|\barchiv(?:e|es|ed|ing)\b|"
                    r"\bsync(?:s|ed|ing)?\b", re.I)
WEAK = re.compile(r"\b(?:keep|keeps|keeping|kept)\b" + _GOING + r"|"
                  r"\b(?:hold|holds|holding|held|record|records|recorded|recording)\b|"
                  r"\b(?:writes?|wrote|written)\b(?=(?:\s+\S+){0,4}?\s+(?:to|into)\s+(?:the\s+|a\s+|an\s+|its\s+)?"
                  r"(?:D1|R2|KV|S3|disk|databases?|tables?|buckets?|servers?|logs?|ledger|IndexedDB)\b)", re.I)
DATA = [(key, re.compile(rx, re.I)) for key, rx in (
    ("prompt", r"\bprompts?\b|\bwhat (?:the |a |each )?(?:users?|testers?|person|owner|you) (?:asked|typed|sent|wrote)\b|"
               r"\b(?:exchanges?|transcripts?)\b"),
    ("answer", r"\b(?:answers?|responses?|replies|outputs?|completions?)\b|\bwhat the model (?:returned|said|answered|wrote)\b"),
    # Atelier's privacy page calls a saved conversation a thread: synced ones are stored in R2
    ("thread", r"\bthreads?\b|\bchat history\b|\b(?:conversations?|chats?|messages?)\b"),
    ("photo link", r"\b(?:profile )?photo links?\b"), ("member id", r"\b(?:member|LinkedIn) IDs?\b"),
    ("session id", r"\b(?:hashed )?session ids?\b"), ("page view", r"\bpage views?\b"),
    ("token cost", r"\btoken (?:costs?|counts?|usage)\b|\btokens?\b"), ("upload", r"\buploads?\b"),
    ("photo", r"\b(?:photos?|images?|pictures?|selfies?|frames?)\b"), ("report", r"\breports?\b"),
    ("profile", r"\bprofiles?\b"), ("memory", r"\bmemor(?:y|ies)\b"), ("feedback", r"\bfeedback\b"),
    ("cache", r"\bcaches?\b"), ("email", r"\bemails?(?: address(?:es)?)?\b"), ("name", r"\bnames?\b"),
    ("cost", r"\bcosts?\b|\bspend(?:ing)?\b"), ("time", r"\btimes?\b|\btimestamps?\b|\blatency\b"),
    ("request", r"\brequests?\b"), ("analytics", r"\banalytics\b|\busage\b"), ("scan", r"\bscans?\b"),
    ("ip", r"(?-i:\bIPs?\b)|\bIP address(?:es)?\b"), ("location", r"\blocations?\b|\baddress(?:es)?\b"),
    ("trip", r"\btrips?\b"), ("price", r"\bprices?\b"),
    ("query", r"\bquer(?:y|ies)\b|\bsearch(?:es| history| terms?)\b|\blook-?ups\b"),  # "logs every weather query"
    ("drawing", r"\bdrawings?\b|\bplans?\b"), ("estimate", r"\bestimates?\b|\bbids?\b"),
    ("timesheet", r"\btimesheets?\b|\binvoices?\b|\breceipts?\b|\bpay stubs?\b"),
    ("listing", r"\blistings?\b|\bdescriptions?\b|\bvideos?\b|\bscripts?\b"),
    ("file", r"\bfiles?\b|\bdocuments?\b|\bPDFs?\b|\bcop(?:y|ies)\b"), ("key", r"\bkeys?\b|\bcredentials?\b|\bpasswords?\b"),
    ("data", r"\b(?:data|everything|anything|nothing|information|info|logs?|records|history)\b"),
)]
GENERIC_DATA = {"data"}
LOCAL_HERE = re.compile(r"\bIndexedDB\b|\blocal[ -]?storage\b|\bin (?:the|your|a|each|their) browser\b|"
                        r"\bon (?:the|your|my|each|a|their) (?:device|phone|laptop|iPad|tablet)\b|\bpage memory\b|"
                        r"\blocally\b|\bon-device\b|\bCache Storage\b", re.I)
# "has no analytics", "doesn't have a profile": keeps none of it
HAS_NO = re.compile(r"\b(?:has|have|had)\s+no\b|\b(?:does|do|did)(?:\s+not|n't)\s+have\b(?:\s+(?:an?|any)\b)?", re.I)
# "keeps threads only on your device", "never leave your browser", "is fully local": kept nowhere else
LOCAL_ONLY = re.compile(rf"\bonly\b[^.;:]{{0,30}}?(?:{LOCAL_HERE.pattern})|(?:\bnever|\bnot|n't)\s+leaves?\s+"
                        r"(?:the|your|a|each|their)\s+(?:device|phone|laptop|iPad|tablet|browser)\b|"
                        r"\b(?:fully|entirely|completely|purely|totally|all)[ -]local\b|\b100% local\b|\blocal[- ]only\b|"
                        rf"\b(?:everything|all (?:of )?(?:your |the |its )?data)\b[^.;:]{{0,40}}?(?:{LOCAL_HERE.pattern})",
                        re.I)
# "collects nothing", "doesn't track you": Atelier and Keep Fix Cut keep the data their pages list
NONE_KEPT = re.compile(r"\b(?:collect|track|gather|harvest)(?:s|ed|ing)?\s+(?:no|zero|nothing)\b|"
                       r"(?:\bnever|\bnot|n't)\s+(?:(?:even|really|actually)\s+)?(?:collect|track|gather|harvest)"
                       r"(?:s|ed|ing)?\b(?=\s+(?:you|users?|testers?|visitors?|anyone|any|anything|data|information|"
                       r"info|personal|analytics|usage)\b)|"
                       r"\b(?:keep(?:s|ing)?|kept|hold(?:s|ing)?|held|has|have)\s+no\s+records?\b|"
                       r"\bforg(?:et|ets|etting|ot)\s+(?:everything|it all|all of it|you)\b", re.I)
# what a denial may leave out, though the app keeps some data: "personal data" where the sheet
# calls what it keeps anonymous, and tracking "across sites"
NOT_KEPT_OK = re.compile(r"\s+(?:any\s+|your\s+)?personal\s+(?:data|information|info|details)\b|"
                         r"\s+(?:you|users?|visitors?|anyone)\s+(?:across|between|around)\b", re.I)
# how long it is kept: "kept 30 days", "a 30-day HttpOnly cookie", "for a year", "forever". A
# period counts beside a keeping or expiring word (or a cookie), not "spent 90 days building it",
# "the last 30 days", "30 days of inactivity" or "4 scans a minute".
DAYS = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}
PERIOD = re.compile(r"(?<!\blast )(?<!\bpast )(?<!\bnext )(?<!\bfirst )(?<!\bevery )(?<!\beach )(?<!\bper )"
                    rf"\b(\d+|{'|'.join(NUMBERS)})[- ](hour|day|week|month|year)s?\b"
                    r"(?![- ](?:of|ago|old|later|earlier|before|long)\b)|"
                    r"\b(?:for|after|within|up to|over|than|about|around|nearly|almost|last(?:s|ed)?|kept|"
                    r"expires? in) (?:a|an|one) "
                    r"(hour|day|week|month|year)\b(?![- ](?:of|ago|old|later|earlier|before|long)\b)|"
                    r"\b(forever|indefinitely|permanently|for good)\b", re.I)
EXPIRES = re.compile(r"\b(?:delet(?:e|es|ed|ing)|purg(?:e|es|ed|ing)|eras(?:e|es|ed|ing)|wip(?:e|es|ed|ing)|"
                     r"expir(?:e|es|ed|ing|y)|clear(?:s|ed|ing)?|remov(?:e|es|ed|ing)|drop(?:s|ped|ping)?|"
                     r"last(?:s|ed|ing)?|li(?:ve|ves|ved|ving)|stay(?:s|ed|ing)?)\b|\bages? out\b|\brolls? off\b", re.I)
# "purges analytics every 90 days": beside a purge, an "every" period is how long it is kept
PURGE = re.compile(r"\b(?:delet|purg|eras|wip|clear|expir|remov|drop)\w*", re.I)
EVERY = re.compile(rf"\bevery (?:(\d+|{'|'.join(NUMBERS)})[- ])?(hour|day|week|month|year)s?\b", re.I)
COOKIE = re.compile(r"\bcookies?\b|\bHttpOnly\b|\bsign(?:ed|s)?[- ]in\b|\blogged[- ]in\b", re.I)
# who may do what: "xAI and Runway are owner-only", "LinkedIn testers sign in with LinkedIn"
TESTERS = re.compile(r"\btesters?\b|\banyone\b|\beveryone\b|\b(?:every|all|any) (?:users?|members?|visitors?)\b|"
                     r"\bthe public\b", re.I)
OWNER = re.compile(r"(?-i:\bI\b)|\b(?:owner|owner-only|me|Cole)\b", re.I)
SIGN_IN = re.compile(r"\bsign(?:s|ed|ing)?(?:[- ](?:\w+\s+){0,2}?)?(?:in|on|up)\b|\blog(?:s|ged|ging)?[- ]?in\b|"
                     r"\blogins?\b|\bauthenticat\w*", re.I)
IDPS = [(key, re.compile(rx, re.I)) for key, rx in (
    ("linkedin", r"\bLinkedIn\b"), ("passcode", r"\bpasscodes?\b"), ("google", r"\bGoogle\b"), ("github", r"\bGitHub\b"),
    ("apple", r"\bApple\b"), ("microsoft", r"\bMicrosoft\b|\bEntra\b|\bAzure AD\b"), ("facebook", r"\bFacebook\b|\bMeta\b"),
    ("x", r"\bTwitter\b|(?-i:\bX\b)"), ("okta", r"\bOkta\b"), ("auth0", r"\bAuth0\b"), ("clerk", r"(?-i:\bClerk\b)"),
    ("magic link", r"\bmagic links?\b|\bone-time (?:codes?|links?)\b|\bemail(?:ed)? (?:links?|codes?)\b"),
    ("password", r"\bpasswords?\b"), ("passkey", r"\bpasskeys?\b"), ("sso", r"(?-i:\bSSO\b|\bSAML\b)"),
)]
# data the sheet keeps on the device only ("Trips are saved in local storage") leaves it here
OFF_DEVICE = re.compile(r"\bsync(?:s|ed|ing)?\b|\bcloud\b|\bupload(?:s|ed|ing)?\b|\b(?:servers?|buckets?|databases?|"
                        r"tables?)\b|(?-i:\bR2\b|\bD1\b|\bKV\b|\bS3\b)", re.I)
NEG_WORDS = {"no", "not", "never", "without", "zero", "neither", "nor", "none", "nothing"}
# "pilots need another source for NOTAMs": the system has none
ELSEWHERE = re.compile(r"\b(?:another|separate|second|outside|other|different)\s+(?:sources?|apps?|tools?|services?|"
                       r"providers?)\s+(?:for|of)\s+(?:[\w-]+\s+){0,2}$", re.I)
CLAUSE_NEG = re.compile(r"\s*[\"'“‘(]?\s*(?:None|No|Not|Nothing|Neither|Never)\b", re.I)
LEADS = re.compile(r"(?:^\s*[\"'“‘(]?\s*|\b(?:When|If|As|After|Before|Since|While|Once|Until|Because|Though|"
                   r"Although|Unless|Whether)\s+)(?:the\s+)?$", re.I)
PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being|gets?|got)\s+(?:(?:not|never|also|only|still|all|"
                     r"then|now)\s+)?$|\b(?:is|are|was|were|has|have|had)n't\s+(?:been\s+)?$", re.I)  # "doesn't keep" is active
# "my apps", "every one of those systems": a claim about all of them
GENERAL = re.compile(rf"{GENERIC.pattern}|\bmy (?:own )?(?:systems?|platforms?|apps?|sites?|stack|servers?)\b|"
                     r"(?-i:\bI) (?:run|host|operate|ship|built|build|maintain) (?:[\w-]+ ){0,3}?(?:systems|platforms|"
                     r"apps|sites|servers|integrations|products)\b|\b(?:systems?|platforms?|apps?|sites?) I "
                     r"(?:run|host|operate|ship|built|maintain)\b", re.I)
# "I log every prompt", "I monitor nothing": about his systems only when what follows the verb
# is a system thing (OBJECT). "I monitor the news" and "I store my receipts in a shoebox" are not.
I_KEEP = re.compile(r"(?-i:\bI) (?:(?:do not|don't|never|also|only) )?"
                    rf"(?:log|store|keep{_GOING}|retain|monitor|track|record|save|back up|encrypt|host|patch|"
                    r"rotate|scope|audit)\b", re.I)
# and the kinds of data a sheet line keeps or denies keeping, when they are not his own ("my
# photos"); never "receipts", "invoices" or "videos"
OBJECT = re.compile(r"\b(?:nothing|everything|anything|data|logs?)\b|(?<!\bmy )(?<!\bour )\b(?:photos?|images?|"
                    r"pictures?|selfies?|uploads?|reports?|threads?|trips?|analytics)\b", re.I)
# what a first-person keeping line that names no system thing says of the one system its
# paragraph is about: "Keep Fix Cut grades photos. I save every report."
KEEP_WHY = re.compile(r": (?:no )?store$|: keeps |\bkept ")
DETERMINERS = set("""the a an my our your his her their i we you he she some any no every each all either neither
nothing none someone everyone anyone nobody there here what which who when where while if as so then but and or
because since though although unless until once after before not""".split())


def _systems(text):
    return {name for name, rx in SYSTEMS if rx.search(text or "")}


def _brands(text):
    return {name for name, rx in BRANDS if rx.search(text or "")}


def _vendor(name):
    """True for a company the lint knows as an AI lab, a host or a payment or SaaS vendor."""
    return bool(VENDOR_NAMES.search(name) or any(rx.search(name) for _, rx in PROVIDERS)
                or any(rx.search(name) for key, rx in TERMS if key in VENDORS))


def _owns(company, news, name):
    """True when company, whose news or word is the text news, owns the system called name by
    its plain name: not one of Cole's, and not a lab or vendor unless the news is in that
    system's field ("Google launched a flight planner")."""
    if _systems(company):
        return False
    first = re.split(r"(?<=[.?!])\s+", news.strip(), maxsplit=1)[0]
    return not _vendor(company) or bool(re.search(rf"\b(?:{DOMAIN.get(name, '(?!)')})\b", first, re.I))


def _theirs(text, before=""):
    """The systems text names only by a plain name that are another company's product: a
    named company's product news (NEWS) comes earlier in the sentence or in the one before it,
    or the company is named right before it ("In ForeFlight,", "Procore said"). "Procore
    shipped an estimating assistant. The estimating tool calls OpenAI." is Procore's.
    "Anthropic released Claude Opus 5. The permit app calls it." is his."""
    brands, out = _brands(text), set()
    for name, rx in SYSTEMS:
        m = rx.search(text or "")
        if not m or name in brands:
            continue
        lead = f"{before} {text[:m.start()]}"
        said = ATTRIB.search(text[:m.start()])
        if any(_owns(n.group(1), lead[n.start():], name) for n in NEWS.finditer(lead)) or (
                said and _owns(said.group(1) or said.group(2), said.group(0), name)):
            out.add(name)
    return out


# "Anthropic released Claude Opus 5. The permit app calls it for every drawing.": "it" is the
# lab or vendor whose news came just before, so the line says the permit app calls Anthropic
IT = re.compile(r"\b(?:call(?:s|ed|ing)?|us(?:e|es|ed|ing)|through|via|with|on|to|into|behind|add(?:s|ed)|"
                r"adopt(?:s|ed))\s+(it|them)\b", re.I)


def _it(text, before=""):
    """text with each "it" that a system calls, uses or runs on read as the lab or vendor
    whose product news (NEWS) comes before it in this sentence or the one before. A denied
    one ("doesn't use it") stays: the product may be new where the vendor is not."""
    for g in reversed(list(IT.finditer(text))):
        lead = f"{before} {text[:g.start()]}"
        who = [n.group(1) for n in NEWS.finditer(lead) if _vendor(n.group(1)) and not _systems(n.group(1))]
        if who and not _negated(text, g.start(1), g.end(1)):
            text = text[:g.start(1)] + who[-1] + text[g.end(1):]
    return text


def _people(text):
    """A pattern for the people the post names (full name or surname). Companies, labs, models
    and threat actors ("Palo Alto Networks", "Salt Typhoon", "Codex Spark") are not people."""
    names = set()
    for m in FULL_NAME.finditer(text or ""):
        if (m.group(1) not in NOT_A_NAME and m.group(2) not in NOT_A_NAME
                and not re.fullmatch(ORG_WORD, m.group(2)) and not re.match(rf"\s+{ORG_WORD}", text[m.end():])):
            names |= {m.group(0), m.group(2)}
    if not names:
        return None
    return re.compile(rf"\b(?:{'|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))})\b")


def _crime(c, people):
    """True when a person the post names is the one a crime verb in clause c is pinned on."""
    for m in people.finditer(c) if people else ():
        if NOT_THE_DOER.search(c[:m.start()]) or re.match(rf"\s+{ORG_WORD}", c[m.end():]):
            continue
        gap = re.match(rf"((?:[\s,]+[\w'’.-]+){{0,6}}?)[\s,]+{CRIME}", c[m.end():])
        if gap and not GAP_STOP.search(gap.group(1)):
            return True
    return False


def _keeps_content(c):
    """True when a prompt or answer is what a keeping verb in clause c keeps: its object with no
    negation between ("logs every prompt"), or the subject of a passive one ("prompts are
    logged"). "Nothing in the ledger holds a prompt" and "records the cost, never the prompt"
    keep none."""
    if CLAUSE_NEG.match(c):
        return False
    for v in STORE.finditer(c):
        if _negated(c, v.start(), v.end()):
            continue
        obj = CONTENT.search(c, v.end(), v.end() + 60)
        if obj and not re.search(r"\b(?:not|never|no|none|nothing|neither|without)\b|n't\b", c[v.end():obj.start()], re.I):
            return True
        if PASSIVE.search(c[:v.start()]) and CONTENT.search(c[:v.start()]):
            return True
    return False


def _mask(c):
    """Clause c with each of Cole's system names replaced by Ω and a letter for which one, so
    "Keep Fix Cut" keeps nothing and a term can be tied to the system named before it."""
    for i, (_, rx) in enumerate(SYSTEMS):
        c = rx.sub("Ω" + chr(97 + i), c)
    return BARE_ERP.sub("Ωa", c)


def _owners(m, pos, here):
    """The systems a term at m[pos] is said of: the nearest named before it (or the first after
    it), with any named alongside it ("Atelier and Keep Fix Cut run on..."); here when the
    clause names none."""
    groups = []
    for x in re.finditer(r"Ω([a-z])", m):
        name = SYSTEMS[ord(x.group(1)) - 97][0]
        if groups and re.fullmatch(r"\s*(?:,|,?\s*(?:and|or|&|plus))\s*", m[groups[-1][1]:x.start()]):
            groups[-1] = (groups[-1][0] | {name}, x.end(), groups[-1][2])
        else:
            groups.append(({name}, x.end(), x.start()))
    if not groups:
        return set(here)
    before = [g for g in groups if g[2] < pos]
    return set((before[-1] if before else groups[0])[0])


def _negated(m, a, b):
    """True when the term at m[a:b] is denied: a negation in the three words before it (and
    after any comma), "logs nothing", "D1 is not used", "another source for NOTAMs", or a
    clause that opens with No, None, Nothing or Never."""
    before = re.findall(r"[\w'’]+", re.split(r"[,;:(]", m[:a])[-1])[-3:]
    return bool(CLAUSE_NEG.match(m) or any(w.lower() in NEG_WORDS or w.lower().endswith(("n't", "n’t")) for w in before)
                or ELSEWHERE.search(m[:a])
                or re.match(r"\s+(?:no|none|nothing|neither|zero)\b", m[b:], re.I)
                or re.match(r"[^,;.]{0,20}?(?<!\band )(?<!\bbut )(?<!\bor )(?<!\bthen )"  # "stores X and never deletes"
                            r"\b(?:(?:is|are|was|were|has|have|had|does|do|did)(?: not|n't)|never)\b", m[b:], re.I))


def _nouns(text):
    """(kind, start) for each kind of data text names, left to right, longest name first. A
    keeping verb ("logs", "records") is not data."""
    spans = [(None, v.start(), v.end()) for v in [*STRONG.finditer(text), *WEAK.finditer(text)]]
    for key, rx in DATA:
        for d in rx.finditer(text):
            if not any(d.start() < e and s0 < d.end() for _, s0, e in spans):
                spans.append((key, d.start(), d.end()))
    return [(key, s0) for key, s0, _ in sorted(spans, key=lambda x: x[1]) if key]


def _stores(m):
    """(start, end, negated, passive) for each verb or noun in m that keeps data."""
    out = []
    for v in sorted([*STRONG.finditer(m), *WEAK.finditer(m)], key=lambda v: v.start()):
        passive = bool(PASSIVE.search(m[:v.start()]))
        if WEAK.fullmatch(v.group(0)) and not (
                _nouns(" ".join(m[v.end():].split()[:3]))
                or re.match(r"\s+(?:for\s+)?\d|\s+(?:\w+\s+){0,2}?(?:on|in|to)\s+(?:the\s+|a\s+|its\s+|your\s+)?"
                            r"(?:servers?|device|browser|cloud|R2|D1|KV|database|tables?|bucket|IndexedDB|memory|disk)\b",
                            m[v.end():], re.I)
                or (passive and _nouns(m[:v.start()]))):
            continue
        out.append((v.start(), v.end(), _negated(m, v.start(), v.end()), passive))
    return out


def _terms(m):
    """(key, negated, leads, position) for each sheet term in masked clause m: TERMS keys,
    providers ("@openai"), counts ("tester 25"), "store" for keeping data and "ai" for AI words.
    leads: the term opens the clause or a "when"/"if" part of it, as a news subject does. A
    provider listed after a denied one is denied too: "can't use Grok or Runway"."""
    out = []
    for key, rx in TERMS:
        out += [(key, _negated(m, t.start(), t.end()), bool(LEADS.search(m[:t.start()])), t.start())
                for t in rx.finditer(m)]
    labs, neg = sorted((t.start(), t.end(), key) for key, rx in PROVIDERS for t in rx.finditer(m)), False
    for i, (a, b, key) in enumerate(labs):
        neg = _negated(m, a, b) or bool(neg and re.fullmatch(r"\s*,?\s*(?:(?:or|nor|and)\s+)?", m[labs[i - 1][1]:a], re.I))
        out.append(("@" + key, neg, bool(LEADS.search(m[:a])), a))
    out += [("ai", _negated(m, t.start(), t.end()), bool(LEADS.search(m[:t.start()])), t.start())
            for t in AI_WORDS.finditer(m)]
    for t in COUNT.finditer(m):
        if VAGUE.search(m[:t.start()]) or NOT_HIS.search(t.group(0)):
            continue
        n = t.group(1).lower().replace(",", "").rstrip("+")
        n = n if n.isdigit() else str(NUMBERS.get(n.split()[-1], n))
        noun = t.group(2).lower()
        noun = "person" if noun in ("people", "persons") else noun[:-1] if noun.endswith("s") else noun
        out.append((f"{noun} {n}", _negated(m, t.start(), t.end()), False, t.start()))
    out += [("store", neg, False, a) for a, _, neg, _ in _stores(m)]
    return out


def _data(m, sheet=False):
    """(kind, negated, position of the keeping word) for the data masked clause m keeps or
    denies keeping: the object of an active keeping verb (a negation between them denies it)
    or the subject of a passive one. On the sheet, every kind its storage clause names. In
    "keeps nothing you upload" the kind is the upload, not data at large."""
    stores = _stores(m)
    if sheet:
        return [(key, any(neg for _, _, neg, _ in stores), 0) for key, _ in _nouns(m)] if stores else []
    out = []
    for i, (a, b, neg, passive) in enumerate(stores):
        lo = stores[i - 1][1] if i else 0
        hi = stores[i + 1][0] if i + 1 < len(stores) else len(m)
        if passive:
            out += [(key, neg, a) for key, _ in _nouns(m[lo:a])]
        else:  # the object ends where a time or condition starts: "keep photos after the scan"
            span = re.split(r"(?i)\b(?:after|before|during|until|once|when|whenever|while|since|unless|if|because)\b",
                            m[b:min(hi, b + 80)])[0]
            nouns = _nouns(span)
            out += [(key, neg or bool(re.search(r"\b(?:no|not|never|none|nothing|neither|without)\b|n't\b",
                                                span[:s0], re.I)), a) for j, (key, s0) in enumerate(nouns)
                    if not (key in GENERIC_DATA and j + 1 < len(nouns)
                            and re.fullmatch(r"[^,;:.]{0,20}", span[s0:nouns[j + 1][1]]))]
    return out


def _periods(m):
    """(kind, days, position) for each period masked clause m keeps something for (PERIOD):
    the cookie when its stretch of the clause speaks of a cookie or of staying signed in, else
    each kind of data it names, or data at large. "deletes analytics after a week" is
    ("analytics", 7), and so is "purges analytics every week"; forever is infinity."""
    def days(n, unit):
        return int(n if n.isdigit() else NUMBERS[n.lower()]) * DAYS[unit.lower()]

    found = [(p.start(), p.end(), float("inf") if p.group(4) else days(p.group(1), p.group(2)) if p.group(1)
              else days("1", p.group(3))) for p in PERIOD.finditer(m)]
    if PURGE.search(m):
        found = sorted(found + [(p.start(), p.end(), days(p.group(1) or "1", p.group(2))) for p in EVERY.finditer(m)])
    keeps = any(not neg for _, _, neg, _ in _stores(m)) or EXPIRES.search(m)
    out = []
    for i, (a, _, held) in enumerate(found):
        part = m[found[i - 1][1] if i else 0:found[i + 1][0] if i + 1 < len(found) else len(m)]
        if COOKIE.search(part):
            out.append(("cookie", held, a))
        elif keeps:
            out += [(key, held, a) for key in dict.fromkeys(k for k, _ in _nouns(part)) or ["data"]]
    return out


def _ways_in(m):
    """(way, position, denied) for each way of signing in masked clause m names (IDPS): "signs
    testers in with Google", "Google sign-in", "log in via a passkey". Denied when a negation
    comes before it in the clause: "sign in with LinkedIn, not Google"."""
    out = []
    for s in SIGN_IN.finditer(m):
        after = {s.end() + w.end() for w in re.finditer(r"\b(?:with|via|through|using|by)\s+(?:(?:a|an|the|their|"
                                                          r"your|his|its)\s+)?", m[s.end():s.end() + 40])}
        for key, rx in IDPS:
            for x in rx.finditer(m):
                if x.start() in after or (x.end() <= s.start() and re.fullmatch(r"(?:['’]s)?(?:\s+[\w-]+)?\s*",
                                                                                 m[x.end():s.start()])):
                    out.append((key, x.start(), bool(re.search(r"\b(?:not|never|no|cannot)\b|n't\b", m[:x.start()],
                                                               re.I))))
    return out


def _roles(m):
    """Who masked clause m speaks of: testers, the owner, or (naming neither) both."""
    return {r for r, rx in (("tester", TESTERS), ("owner", OWNER)) if rx.search(m)} or {"tester", "owner"}


def _support():
    """What SYSTEM_FACTS states (pos) and denies (neg) for each system, the data its storage
    lines say it keeps (posdata), keeps on the device only (localdata) or does not (negdata),
    how long it keeps each kind (periods: kind -> days), the providers it keeps for the owner
    (owner_only) and who signs in how (signin: (role, way))."""
    facts, denials = SYSTEM_FACTS.split("\nDOES NOT")
    units = []
    for entry in re.split(r"\n- ", facts)[1:]:
        entry = " ".join(entry.split())
        first = min((rx.search(entry).start(), name) for name, rx in SYSTEMS if rx.search(entry))[1]
        units += [({first}, c) for sent in _sentences(entry) for c in CLAUSE.split(sent)]
    prev = set()
    for line in re.split(r"\n- ", denials)[1:]:
        for sent in _sentences(" ".join(line.split())):
            prev = _systems(sent) or (prev if CARRY.match(sent) else set())
            units += [(prev, c) for c in CLAUSE.split(sent)]
    sup = {name: {"pos": set(), "neg": set(), "posdata": set(), "localdata": set(), "negdata": set(),
                  "periods": {}, "owner_only": set(), "signin": set(), "anonymous": False} for name, _ in SYSTEMS}
    for named, c in units:
        m = _mask(c)
        for name in named:
            sup[name]["anonymous"] |= bool(re.search(r"\banonymous\b", c, re.I))  # "Anonymous usage analytics"
            for key, neg, _, _ in _terms(m):
                sup[name]["neg" if neg else "pos"].add(key)
                if key.startswith("@") and not neg and re.search(r"\bowner-only\b", c):
                    sup[name]["owner_only"].add(key)
            for key, neg, _ in _data(m, sheet=True):
                sup[name]["negdata" if neg else "localdata" if LOCAL_HERE.search(c) else "posdata"].add(key)
            for key, days, _ in _periods(m):
                sup[name]["periods"].setdefault(key, set()).add(days)
            sup[name]["signin"] |= {(r, way) for way, _, denied in _ways_in(m) if not denied for r in _roles(m)}
    for name in NO_AI:
        sup[name]["neg"] |= {"ai", "api"}  # no AI: no model API to call
    for s in sup.values():
        if any(k.startswith("@") for k in s["pos"]):
            s["pos"].add("api")  # a provider it calls is an API it calls
    return sup


SUPPORT = _support()


def _here(c, sep, first, own, named, prev, loose=frozenset()):
    """The systems clause c is about: the ones it names (not the loose ones); the sentence's
    carried subject for a first clause that names none ("It logs..."); the previous clause's
    after a colon or when c goes on with a verb or "it" ("..., and keeps threads on the device")."""
    mine = (_systems(c) - loose) | ({"Coen ERP"} if "Coen ERP" in named and BARE_ERP.search(c) else set())
    t = c.strip()
    if mine or not t:
        return mine
    if first:
        return set() if own else set(named)
    if sep.strip() == ":" or CARRY.match(t[:1].upper() + t[1:]) or (
            t[:1].islower() and t.split()[0].strip(",.;:'\"").lower() not in DETERMINERS):
        return set(prev)
    return set()


def _unsupported(c, here):
    """The terms clause c states about the systems in here that SYSTEM_FACTS does not support,
    as "system: term". With no system in here (a first-person claim about all of them), every
    sheet term but a true denial of PHP, Python, a VPS or S3."""
    m = _mask(c)
    found, why = _terms(m), []
    local = bool(LOCAL_HERE.search(c)) and not any(
        k in ("server", "database", "d1", "r2", "kv", "bucket", "s3") and not neg for k, neg, _, _ in found)
    for name in sorted(here) or ["all of them"]:
        sup = SUPPORT.get(name)
        for key, neg, leads, pos in found:
            if sup and name not in _owners(m, pos, here):
                continue
            if sup is None:  # every one of his systems at once
                ok = (key.startswith("@") or key == "ai" or (neg and key in GLOBAL_NEG)
                      or (not neg and key in GLOBAL_POS) or (key == "store" and not neg and local))
            elif key.startswith("@"):  # "testers can't use Grok", "LinkedIn, not Google" deny no provider it calls
                ok = leads or (key not in sup["pos"] if neg else key in sup["pos"]) or (neg and bool(
                    SIGN_IN.search(m) or (key in sup["owner_only"] and TESTERS.search(m))))
            elif key == "ai":
                ok = neg or name not in NO_AI
            elif leads and key in VENDORS:
                ok = True
            elif key == "store" and not neg and local:
                ok = True
            elif key == "api" and neg and any(k.startswith("@") and n and k not in sup["pos"] for k, n, _, _ in found):
                ok = True  # "does not call Meta's APIs" denies the provider
            else:
                ok = key in sup["neg"] | GLOBAL_NEG if neg else key in sup["pos"] | GLOBAL_POS
            if not ok:
                why.append(f"{name}: {'no ' if neg else ''}{key.lstrip('@')}")
        if sup and not local and any(key == "store" for key, _, _, _ in found):
            for key, neg, pos in _data(m):
                if name not in _owners(m, pos, here):
                    continue
                # a log of the conversation holds its prompts and answers: "logs no prompts or answers" denies it
                logged = key == "thread" and re.match(r"log", m[pos:], re.I) and {"prompt", "answer"} <= sup["negdata"]
                if neg and not logged and (key in sup["posdata"] or (key in GENERIC_DATA and sup["posdata"])):
                    why.append(f"{name}: keeps no {key}")
                elif not neg and (key in sup["negdata"] or (sup["posdata"] and key not in sup["posdata"] and not (
                        key in sup["localdata"] and not OFF_DEVICE.search(c)))):
                    why.append(f"{name}: keeps {key}")
        if sup:
            for h in HAS_NO.finditer(m):
                for key, _ in _nouns(m[h.end():h.end() + 40])[:1]:
                    if name in _owners(m, h.start(), here) and (key in sup["posdata"] or (
                            key in GENERIC_DATA and sup["posdata"])):
                        why.append(f"{name}: keeps no {key}")
            for h in NONE_KEPT.finditer(m):  # "data" is in posdata only where the sheet says it keeps some
                key = ([k for k, _ in _nouns(m[h.end():h.end() + 40])] or ["data"])[0]
                ok = NOT_KEPT_OK.match(m[h.end():]) and (sup["anonymous"] or "personal" not in NOT_KEPT_OK.match(
                    m[h.end():]).group(0).lower())
                if name in _owners(m, h.start(), here) and key in sup["posdata"] and not ok:
                    why.append(f"{name}: keeps no {key}")
            if LOCAL_ONLY.search(m):
                why += [f"{name}: keeps {key} only on the device" for key, at in _nouns(m) or [("data", 0)]
                        if key in sup["posdata"] and name in _owners(m, at, here)]
            for key, days, at in _periods(m):  # a kind the sheet gives a period, or data at large there
                held = sup["periods"].get(key) or (key in GENERIC_DATA and set().union(
                    *(v for k, v in sup["periods"].items() if k != "cookie")))
                if held and days not in held and name in _owners(m, at, here):
                    why.append(f"{name}: {key} kept {'forever' if days == float('inf') else f'{days:g} days'}")
            tester = TESTERS.search(m) and not OWNER.search(m)
            for key, neg, _, pos in found:  # "testers can use Grok": a provider the sheet keeps for the owner
                if key in sup["owner_only"] and tester and not neg and name in _owners(m, pos, here):
                    why.append(f"{name}: {key.lstrip('@')} for testers")
            for way, at, denied in _ways_in(m) if sup["signin"] else ():  # "signs testers in with Google"
                if not denied and name in _owners(m, at, here) and not any((r, way) in sup["signin"] for r in _roles(m)):
                    why.append(f"{name}: sign-in with {way}")
    return list(dict.fromkeys(why))


def _claim(s, named, story, people, loose=frozenset(), context=frozenset(), keeping=False, denied=False):
    """(soft label, must-not-ship label, story, why) for one sentence. named: the Cole systems
    it is about; loose: ones it may be about (soft labels only); story: an earlier sentence in
    this paragraph told a first-person story about them; context: systems the paragraph named
    before it; keeping: an earlier sentence there was a first-person keeping claim about them
    (_general); denied: the paragraph has denied PHP, Python, a VPS or S3 (STACK_DENIED); why:
    the sheet terms it states without support. Each clause answers for itself: only a clause
    that says "I would" is let off."""
    if s.endswith("?"):
        return None, None, story, []
    s = NONE_LABEL.sub(r"no \1", s)  # "NOTAMS: NONE" says there are no NOTAMs
    high = soft = None
    told = False
    why = []
    parts, own, prev = re.split(f"({CLAUSE.pattern})", s, flags=re.I), _systems(s) - loose, set()
    for i in range(0, len(parts), 2):
        c = parts[i]
        prev = _here(c, parts[i - 1] if i else "", i == 0, own, named, prev, loose)
        if c.strip() and not WOULD.search(c):
            h, so, t, w = _clause(c, named, story or told, people, loose, context, prev, keeping, denied)
            why = why if high else w
            high, soft, told = high or h, soft or so, told or t
    return soft, high, story or told, why


def _general(c, keeping=False):
    """"all" when clause c speaks of all of Cole's systems at once (GENERAL). "me" when it is
    first person keeping, monitoring or patching a system thing (I_KEEP, then logs, keys,
    prompts, servers, data, nothing or a sheet term): "I log every prompt", "I monitor nothing",
    or any such clause once its paragraph has had one (keeping). None for "I monitor the news"
    or "I save every invoice as a PDF"."""
    if GENERAL.search(c):
        return "all"
    for m in I_KEEP.finditer(c):
        rest = c[m.end():]
        if (keeping or any(not x.group(0).lower().startswith("last ") for x in INFRA.finditer(rest))
                or any(rx.search(rest) for rx in (KEY, CONTENT, SERVER, OBJECT))
                or any(rx.search(rest) for key, rx in TERMS if key not in ("tax", "deposit"))):
            return "me"
    return None


def _clause(c, named, story, people, loose, context, here=frozenset(), keeping=False, denied=False):
    high = soft = None
    why = []
    rest = FACT_OK.sub(" ", c)
    if denied:  # "None of my systems run PHP. ... Those systems were never vulnerable."
        rest = UNEXPOSED.sub(" ", rest)
    if _crime(c, people) and not ATTRIBUTED.search(c):
        high = CRIME_LABEL
    elif "Atelier" in named and _keeps_content(c) and not (LOCAL.search(c) and not SERVER.search(c)):
        high = ATELIER_LABEL
    elif (named or MY_SYSTEMS.search(c) or GENERIC.search(c) or (context and RUNS_ON.search(c))) and TECH.search(rest):
        high = TECH_LABEL
    elif KEY.search(c) and LEAK.search(c) and not HYPO.search(c) and (named or FIRST.search(c) or story):
        high = LEAK_LABEL
    told = bool(STORY.search(c) and (named or loose or GENERIC.search(c) or INFRA.search(c)))
    if told and not high and any(INFRA.search(c, m.end(), m.end() + 60) or KEY.search(c, m.end(), m.end() + 60)
                                 for m in STORY.finditer(c)):
        high = STORY_LABEL  # the prompt bans these outright: "I checked the logs", "I rotated the keys"
    general = None if high or here else _general(c, keeping)
    # "Keep Fix Cut grades photos. I save every report.": a keeping line in a paragraph about one
    # system answers to that system's storage line, whatever it keeps; "I store my receipts" does not
    kept = not (high or here or general) and len(context) == 1 and any(
        not re.match(r"\s+(?:my|our)\b", c[k.end():], re.I) for k in I_KEEP.finditer(c))
    if not high and (here or general or kept):
        # "I do not log the prompt content." after two Atelier lines is said of Atelier
        scope = set(here) or (set(context) if (general == "me" or kept) and len(context) == 1 else set())
        why = _unsupported(c, scope)
        why = [w for w in why if KEEP_WHY.search(w)] if kept else why
        high = (SHEET_LABEL if scope else GENERAL_LABEL) if why else None
    about = named or loose or ME.search(c) or GENERIC.search(c)
    if "Atelier" in named and NOT_ATELIER_PROVIDER.search(c):
        soft = "a provider Atelier does not use (its nine are in SYSTEM FACTS)"
    elif "Atelier" in named and ATELIER_DETAIL.search(rest):
        soft = "an Atelier detail outside SYSTEM FACTS"
    elif about and (DOES_NOT.search(rest) or (named & NO_AI and AI_WORDS.search(c))):
        soft = "something SYSTEM FACTS says it does not do"
    elif told:
        soft = "a first-person story about Cole's systems"
    elif about and CLAIM.search(rest):
        soft = "a claim about Cole's systems outside SYSTEM FACTS"
    return high, soft, told, why


_BLOCK_TAG = re.compile(r"(?is)(</?(?:p|h[1-6]|li|ul|ol|blockquote|div)\b[^>]*>|<br\s*/?>)")
_TOKEN = re.compile(r"(?s)<[^>]+>|\{link:[a-z0-9\-]+\|[^}]*\}|&#?\w+;|.")


def _split(piece):
    """An inline HTML run as sentences, each a list of (token, plain text) pairs. Tags read as
    nothing, a crosslink macro as its anchor; the split matches _sentences()."""
    toks = []
    for t in _TOKEN.findall(piece):
        p = "" if t[0] == "<" and len(t) > 1 else t[t.index("|") + 1:-1] if t.startswith("{link:") else \
            html.unescape(t) if t[0] == "&" and len(t) > 1 else t
        toks.append((t, re.sub(r"\s", " ", p).replace("’", "'").replace("‘", "'")))
    plain = "".join(p for _, p in toks)
    starts = [0] + [m.end() for m in _breaks(plain)]
    sents, pos, k = [[] for _ in starts], 0, 0
    for t, p in toks:
        while k + 1 < len(starts) and pos >= starts[k + 1]:
            k += 1
        sents[k].append((t, p))
        pos += len(p)
    return sents


def _tidy(h):
    """Drop the emptied tags and loose spaces a cut sentence leaves behind."""
    while True:
        new = re.sub(r"(?is)<(a|em|i|span|code|q)\b[^>]*>\s*</\1>", "", h)
        new = re.sub(r"(?is)<(p|h[1-6]|li|blockquote)\b[^>]*>\s*</\1>", "", new)
        if new == h:
            break
        h = new
    h = re.sub(r"(?i)[ \t]+(</(?:p|h[1-6]|li|blockquote)>)", r"\1", re.sub(r"[ \t]{2,}", " ", h))
    return re.sub(r"(?i)(<(?:p|h[1-6]|li|blockquote)\b[^>]*>)[ \t]+", r"\1", h)


def _context(text):
    """Post-wide context for _scan(): the named-person pattern, and whether a bare "the ERP" is
    Cole's (the post names his ERP and no vendor's)."""
    return _people(text), bool(SYSTEMS[0][1].search(text or "")) and not ERP_VENDOR.search(text or "")


_CUT = set()  # every sentence a must-not-ship rule matched this run, at any step; never logged
_ECHO = set()  # slug_words and keywords that came with a title that lost a sentence; they echo it


def _scan(fragment, people=None, strip=None, erp=False, carry=False):
    """Read an HTML fragment sentence by sentence. Returns (fragment, rows), one row per
    sentence: text, named and loose (Cole systems), soft and high (claim labels or None). A
    system named only by its plain name ("the permit app") is his, and loose only when it is
    another company's product (_theirs: product news in that sentence or the one before it in
    the block; a heading shares a block with the paragraph under it). A sentence for which
    strip(row) is true is cut from the fragment; its tags stay, emptied, then tidied. Once a
    paragraph tells a first-person story about his logs, keys or stack, a later sentence there
    that reads like more of it (first person, "It", a system, logs, keys) is must-not-ship too,
    unless it says what he would check or carries a source link. carry: a sentence that names
    no system is about the one before it, as in a stack of art labels (_labels)."""
    out, rows, cut = [], [], False
    last, heading = "", False
    for i, piece in enumerate(_BLOCK_TAG.split(fragment or "")):
        if i % 2:
            if re.match(r"(?i)<(?:p|li|h[1-6]|blockquote|div)\b", piece):
                last, heading = (last if heading else ""), piece[1:2].lower() == "h"
            out.append(piece)
            continue
        prev, prev_loose, story, context, tale, keeping = set(), set(), False, set(), False, False
        denied = False
        for sent in _split(piece):
            text = " ".join("".join(p for _, p in sent).split())
            if not text:
                out.append("".join(t for t, _ in sent))
                continue
            denied = denied or bool(STACK_DENIED.search(text))
            named, before = _systems(text), last
            loose, last = _theirs(text, before), text
            named, loose = (named - loose, loose) if named else (
                (set(prev), set(prev_loose)) if carry or CARRY.match(text) else (set(), set()))
            if "Coen ERP" not in named and BARE_ERP.search(text) and not ERP_VENDOR.search(text):
                if erp or "Coen ERP" in context:
                    named = named | {"Coen ERP"}
                else:
                    loose = loose | {"Coen ERP"}
            soft, high, story, why = _claim(_it(text, before), named, story, people, loose, context, keeping, denied)
            keeping = keeping or bool(high in (SHEET_LABEL, GENERAL_LABEL) and I_KEEP.search(text))
            linked = any(re.match(r"(?i)<a\s", t) for t, _ in sent)
            if tale and not high and not linked and not WOULD.search(text) and (
                    named or loose or CARRY.match(text) or FIRST.search(text) or GENERIC.search(text)
                    or INFRA.search(text) or KEY.search(text) or LEAK.search(text) or CLAIM.search(text)):
                high = TALE_LABEL
            tale = tale or high in (STORY_LABEL, LEAK_LABEL) or bool(
                high in (TECH_LABEL, SHEET_LABEL, GENERAL_LABEL) and STORY.search(text))
            row = {"text": text, "named": named, "loose": loose, "soft": soft, "high": high, "why": why,
                   "linked": linked}
            if high:
                _CUT.add(text)
            rows.append(row)
            prev, prev_loose, context = named, loose, context | named
            if strip and strip(row):
                cut = True
                out.append("".join(t for t, p in sent if t[0] == "<" and not p))
            else:
                out.append("".join(t for t, _ in sent))
    return (_tidy("".join(out)) if cut else fragment), rows


def _label_para(svg, spans):
    """The text of the <text> elements at spans of svg as one paragraph, a <tspan> a word apart.
    A label in sentence case ("This is only a test.") or one that opens with a system's name
    ("ATELIER HAS NO BUILD STEP") starts a sentence; one in capitals or lower case ("LOGS EVERY
    PROMPT", "every prompt") goes on with the label above it."""
    words = [w for w in (" ".join(_plain(svg[a:b]).split()) for a, b in spans) if w]
    for i in range(1, len(words)):
        if (re.match(r"[\"'“(]?[A-Z][a-z]", words[i]) or any(rx.match(words[i]) for _, rx in SYSTEMS)) and \
                not re.search(r"[.?!:;][\"'”)]*$", words[i - 1]):
            words[i - 1] += "."
    return "<p>" + html.escape(" ".join(words), quote=False) + "</p>"


def _labels(svg):
    """The art's labels as blocks: each run of <text> elements with only space between them (a
    label stacked over lines, "ATELIER" above "LOGS EVERY PROMPT") reads as one paragraph.
    Returns [(spans of its elements in svg, that paragraph)]."""
    svg, blocks = svg if isinstance(svg, str) else "", []
    for m in re.finditer(r"(?s)<text\b[^>]*>.*?</text>", svg):
        if blocks and not svg[blocks[-1][-1][1]:m.start()].strip():
            blocks[-1].append(m.span())
        else:
            blocks.append([m.span()])
    return [(spans, _label_para(svg, spans)) for spans in blocks]


def _cut_labels(svg, people, erp, bad):
    """svg without the labels that hold a row bad(row) is true of, and those rows. A label that
    holds one by itself goes; then, while what is left of its block still reads as one, the last
    label inside it whose going clears it, else every such label. A label that names the system
    ("ATELIER" over "LOGS EVERY PROMPT") goes only when no other label inside the row does."""
    if not isinstance(svg, str):
        return svg, []
    drop, cut = set(), []

    def rows(spans):
        return [r for r in _scan(_label_para(svg, spans), people, erp=erp, carry=True)[1] if bad(r)]

    for spans, para in _labels(svg):
        found = rows(spans)
        if not found:
            continue
        cut += found
        keep = [s for s in spans if not rows([s])]
        left = rows(keep) if keep else []
        while left:  # each pass drops a label, so this ends
            words = {s: " ".join(_plain(svg[s[0]:s[1]]).split()) for s in keep}
            inside = [s for s in keep if words[s] and any(words[s] in r["text"] for r in left)]
            claims = [s for s in inside if not _systems(words[s])] or inside or keep
            alone = [s for s in reversed(claims) if not rows([x for x in keep if x != s])]
            keep = [x for x in keep if x not in (alone[:1] or claims)]
            left = rows(keep) if keep else []
        drop |= set(spans) - set(keep)
    for a, b in sorted(drop, reverse=True):
        svg = svg[:a] + svg[b:]
    return svg, cut


def _claim_context(post):
    text = [post.get(k) for k in ("title", "desc", "svg_caption", "body_html", "svg_alt")]
    text += [p for _, p in _labels(post.get("svg_inner"))]
    return _context(" ".join(_plain(v) for v in text if isinstance(v, str)))


def _claim_rows(post):
    """(field, row) for each sentence of the text fields, the art's labels and the alt text."""
    fields = [(k, post.get(k) or "") for k in ("title", "desc", "svg_caption", "body_html")]
    alt = post.get("svg_alt")
    art = [("svg_inner", "".join(p for _, p in _labels(post.get("svg_inner")))),
           ("svg_alt", alt if isinstance(alt, str) else "")]
    people, erp = _claim_context(post)
    return [(name, r) for name, raw in fields + art for r in _scan(raw, people, erp=erp, carry=name == "svg_inner")[1]]


def claim_problems(post):
    """Claims about Cole's systems (and named people) for the revision to fix: the text fields,
    the art's labels and the alt text. A must-not-ship line that carries a source link asks
    for a rephrase that keeps the link, since cutting it takes the source along."""
    probs = []
    for name, r in _claim_rows(post):
        if r["high"]:
            fix = (CRIME_FIX if r["high"] == CRIME_LABEL else HIGH_FIX) + (f"; {LINK_FIX}" if r["linked"] else "")
            why = f' ({"; ".join(r["why"])})' if r["why"] else ""
            probs.append(f'{name}: must not ship, {r["high"]}; {fix}: "{_clip(r["text"])}"{why}')
        elif r["soft"]:
            probs.append(f'{name}: {r["soft"]}; {CLAIM_FIX}: "{_clip(r["text"])}"')
    named = _systems(" ".join(_plain(post.get(k) or "") for k in ("title", "desc", "svg_caption", "body_html")))
    if len(named) > 3:
        probs.append(f"body_html: names {len(named)} of Cole's systems ({', '.join(sorted(named))}); "
                     "keep the two or three the story touches")
    return probs


def _kept_keywords(keywords, lost, title):
    """keywords without each phrase built from a word of the lost title sentences that the title
    left no longer has ("prompt logging" goes with "Atelier logs every prompt"); when no phrase
    is left, the content words of that title."""
    def words(s):
        return {w.rstrip("s") for w in re.findall(r"[a-z0-9][a-z0-9'-]*", s.lower())
                if (len(w) >= 3 or re.search(r"\d", w)) and w not in STOP and w not in SMALL}

    def same(a, b):  # "log" and "logging", "table" and "tables"
        return a == b or (min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)))

    gone = set().union(*map(words, lost)) - words(title)
    kept = [k.strip() for k in keywords.split(",") if k.strip() and not any(
        same(w, g) for w in words(k) for g in gone)]
    if kept:
        return ", ".join(kept)
    rest = re.sub(r"^Rollout Report:\s*", "", title).lower()
    return " ".join(w for w in re.findall(r"[a-z0-9][a-z0-9'-]*", rest)
                    if (len(w) >= 4 or re.search(r"\d", w)) and w not in STOP)


def drop_high_risk(post):
    """Cut every must-not-ship sentence still in the title, desc, caption or body, the art labels
    that hold one (a stacked label reads as one: _cut_labels), and an alt text that holds one (it
    becomes a plain description of the caption). A cut can hand "It" a new system, so a field is read again until nothing is left
    to cut. A cut title gets new slug_words, so the URL never carries the cut words, and keeps
    only the keywords not built from them (_kept_keywords). Runs after
    the revisions; returns (post, [(field, sentence, label)])."""
    fields = ("title", "desc", "svg_caption", "body_html")
    people, erp = _claim_context(post)
    out, cut = dict(post), []
    for k in fields:
        while isinstance(out.get(k), str):  # each pass removes a sentence, so this ends
            out[k], rows = _scan(out[k], people, strip=lambda r: r["high"], erp=erp)
            bad = [(k, r["text"], r["high"]) for r in rows if r["high"]]
            if not bad:
                break
            cut += bad
            if k != "body_html":  # one-line fields: no space left where a sentence was
                out[k] = " ".join(out[k].split())
    lost = [t for f, t, _ in cut if f == "title"]
    if lost and isinstance(out.get("slug_words"), str):
        out["slug_words"] = " ".join(slugify(re.sub(r"^Rollout Report:\s*", "", out["title"])).split("-")[:6])
    if lost and isinstance(out.get("keywords"), str):
        out["keywords"] = _kept_keywords(out["keywords"], lost, out["title"] or "")
    if isinstance(out.get("svg_inner"), str):
        out["svg_inner"], bad = _cut_labels(out["svg_inner"], people, erp, lambda r: r["high"])
        cut += [("svg_inner", r["text"], r["high"]) for r in bad]
    if isinstance(out.get("svg_alt"), str):
        bad = [r for r in _scan(out["svg_alt"], people, erp=erp)[1] if r["high"]]
        if bad:
            cap = " ".join(_plain(out.get("svg_caption") or "").split())
            out["svg_alt"] = f"A CRT terminal showing the caption: {cap}" if cap else "A CRT terminal drawing in green."
            cut += [("svg_alt", r["text"], r["high"]) for r in bad]
    return out, cut


HUMANIZE_ASK = (
    "A lint pass found the HUMANIZER problems listed below. Fix each one by editing only the "
    "sentence or field it names. Split a long sentence at a natural joint into two full sentences "
    "and keep every fact. Fix a contrast pair by stating the point once, in one plain sentence; "
    "don't swap in another pair such as 'X takes a month. Y takes longer.' Web search is off for "
    "this step: add no new facts, numbers, names, quotes or links. Where a rule wants a source you "
    "don't have, cut the line only if it carries no link; otherwise rephrase it around the link. "
    "A line about Cole's systems says only what SYSTEM FACTS says, or what he would check. If a "
    "flagged phrase sits inside quotation marks, don't edit the quoted words: paraphrase without "
    "the quotes, quote fewer words, or cut it. Keep every crosslinked post, linked once (shorten "
    "its anchor text if needed), every source link, the headings, the related list and the art. "
    "If you change svg_caption, change the caption <text> in svg_inner to the same words. If you "
    "change the title, update slug_words to match. Return ONLY the corrected ```json block.")
PASSES = 3  # revision calls at most; each one sees only the problems still left
# A revision is merged field group by field group, so a good title survives a bad body.
GROUPS = (("title", "slug_words"), ("desc",), ("svg_caption", "svg_inner"), ("body_html",))
TRACE_PATH = os.environ.get("WRITER_TRACE")  # publish.yml uploads it as a run artifact
_TRACE = {}  # trace path -> the rows as given; the file is rewritten from these on each call


def trace(kind, **data):
    """Write WRITER_TRACE (when set), one JSON line per call: drafts, revisions and what was
    kept. The repo is public and so is the artifact, so no sentence a must-not-ship rule
    matched at any step goes in it. A sentence can match later (the rest of a story a
    revision added), so every call rewrites the whole file without all of them."""
    if not TRACE_PATH:
        return
    rows = _TRACE.setdefault(TRACE_PATH, [])
    rows.append({"at": datetime.datetime.now(ET).isoformat(timespec="seconds"), "kind": kind,
                 **json.loads(json.dumps(data, ensure_ascii=False, default=str))})
    for row in [rows[-1]] + rows[:-1]:  # the new row's scan adds to _CUT; then every row's echoes go in _ECHO
        for k, v in row.items():
            _public(k, v)
    try:
        with open(TRACE_PATH, "w", encoding="utf-8") as f:
            f.writelines(json.dumps({k: _public(k, v) for k, v in row.items()}, ensure_ascii=False) + "\n"
                         for row in rows)
    except OSError as e:
        print(f"trace: could not write {TRACE_PATH} ({e})", flush=True)


def _public(key, value):
    """A trace value without must-not-ship text: cut from drafts and raw output, a word count
    in place of the quote in a problem, a short hash in place of a cut sentence."""
    if key in ("post", "revision") and isinstance(value, dict):
        return _public_post(value)
    if key == "raw" and isinstance(value, str):
        people, erp = _context(_plain(value))
        out = _scan(value, people, strip=lambda r: r["high"] or r["text"] in _CUT, erp=erp)[0]
        for s in _CUT:
            out = out.replace(s, "").replace(json.dumps(s, ensure_ascii=False)[1:-1], "")
        return out
    if key == "problems" and isinstance(value, list):
        return [_public_problem(p) for p in value]
    if key == "cut":
        return [{"field": f, "label": label, "words": _words(t), "sha256": hashlib.sha256(t.encode()).hexdigest()[:12]}
                for f, t, label in value]
    return value


def _public_post(post):
    """A post without any sentence, art label or alt text in _CUT. When the title lost a
    sentence, the slug_words and keywords it came with go too, in this row and every other:
    they echo it. The ones drop_high_risk() rebuilt from what is left stay."""
    out = drop_high_risk(post)[0]
    people, erp = _claim_context(out)
    for k in ("title", "desc", "svg_caption", "body_html"):
        if isinstance(out.get(k), str):
            out[k] = _scan(out[k], people, strip=lambda r: r["text"] in _CUT, erp=erp)[0]
    echoes = [post.get(k) for k in ("slug_words", "keywords") if isinstance(post.get(k), str) and post[k].strip()]
    if isinstance(post.get("title"), str) and out.get("title") != post["title"]:
        _ECHO.update(echoes)
    out.update({k: "[kept out of the trace]" for k in ("slug_words", "keywords")
                if isinstance(out.get(k), str) and out[k] in _ECHO})
    if isinstance(out.get("svg_inner"), str):
        out["svg_inner"] = _cut_labels(out["svg_inner"], people, erp, lambda r: r["text"] in _CUT)[0]
    if isinstance(out.get("svg_alt"), str) and any(
            r["text"] in _CUT for r in _scan(out["svg_alt"], people, erp=erp)[1]):
        out["svg_alt"] = "[kept out of the trace]"
    return out


def _public_problem(p):
    head, _, quote = p.partition(': "')  # labels and fixes hold no ': "', so this is the quote
    q = (quote.rpartition(chr(34))[0] or quote).rstrip("…")
    if "must not ship" not in p and not (q and any(q == s or s[:60] in q or (len(q) >= 20 and q in s) for s in _CUT)):
        return p
    return f"{head}: [{_words(q)} words, kept out of the trace]"


def _body_words(p):
    return len(re.sub(r"<[^>]+>", " ", p.get("body_html") or "").split())


def _sources(p):
    return set(re.findall(r'href="(https://[^"]+)"', p.get("body_html") or ""))


def _crosslinked(p):
    return set(re.findall(r"\{link:([a-z0-9\-]+)\|", p.get("body_html") or ""))


def _shape_loss(post, rev):
    """Why a revision lost or invented material the draft had (None when it kept enough).
    Search is off during a revision, so a new URL can only be made up. A dropped one is
    allowed: validate() still holds the link minimum. A post linked twice may lose its second
    link (the lint asks for that); a post the draft linked may not disappear. The body keeps
    four fifths of the draft's words. What is measured is the draft less its must-not-ship
    lines (drop_high_risk), so a revision that drops a false paragraph, with the words,
    crosslinks or heading in it, has lost nothing the cut would keep."""
    added, removed = _sources(rev) - _sources(post), _sources(post) - _sources(rev)
    if added:
        return f"it added source links {sorted(added)} (and dropped {sorted(removed)})"
    kept = drop_high_risk(post)[0]
    if _body_words(rev) < 0.8 * _body_words(kept):
        return f"it cut the body from {_body_words(post)} to {_body_words(rev)} words"
    if not _crosslinked(kept) <= _crosslinked(rev):
        return f"it dropped crosslinks {sorted(_crosslinked(kept) - _crosslinked(rev))}"
    if rev["body_html"].count("<h3>") < (kept.get("body_html") or "").count("<h3>"):
        return "it dropped headings"
    return None


def _must(problem):
    """Must-fix: the one-line fields, every must-not-ship line and every claim about Cole's
    systems, so a revision that fixes style by adding a claim never scores cleaner."""
    return problem.startswith(MUST_FIX) or "must not ship" in problem or f"; {CLAIM_FIX}:" in problem


def _score(post):
    """(must-not-ship lines, must-fix problems, all problems): a revision that turns a false
    line into a true one that still draws a soft label scores better."""
    probs = humanizer_problems(post)
    return sum(1 for p in probs if "must not ship" in p), sum(1 for p in probs if _must(p)), len(probs)


def _pair(why):
    """A sheet term from _unsupported() as (system, term): "Atelier: keeps no feedback" ->
    ("Atelier", "feedback"), so a denial and a claim of the same thing are one pair."""
    name, _, term = why.partition(": ")
    term = re.sub(r"^(?:keeps |sign-in with )?(?:no )?|(?: only on the device| kept [^:]*| for testers)$", "", term)
    return name, term


def _claims(post):
    """The claims about Cole's systems in post, read so a claim reworded, split or moved is the
    same claim: (must, soft, mentioned). must counts each must-not-ship row's (label, systems,
    term) for every sheet term it states without support, or once with no term. soft lists
    (systems, pairs) for each soft row whose sheet terms SYSTEM_FACTS does not all hold; a
    pair is (system, term), or (system, label) for a row that states no sheet term; a row that
    names no system is "all of them", as _unsupported() reads it. mentioned holds every
    (system, term) and (system, label) pair any sentence of the post states."""
    must, soft, mentioned = Counter(), [], set()
    for _, r in _claim_rows(post):
        systems = tuple(sorted(r["named"] | r["loose"]))
        who = systems or ("all of them",)
        m = _mask(r["text"])
        terms = {k.lstrip("@") for k, _, _, _ in _terms(m)} | {k for k, _ in _nouns(m)}
        mentioned |= {(s, t) for s in who for t in terms | {r["high"], r["soft"]} if t}
        if r["high"]:
            must.update((r["high"], systems, w) for w in r["why"] or [None])
        elif r["soft"]:
            why = _unsupported(r["text"], set(systems)) if _terms(m) else []
            if why or not _terms(m):  # a soft line whose every sheet term the sheet holds is no new claim
                soft.append((systems, {_pair(w) for w in why} or {(s, r["soft"]) for s in who}))
    return must, soft, mentioned


def _added_claims(best, trial):
    """How many claims about Cole's systems trial adds to best: every must-not-ship one best
    lacks, and every soft one about a (system, term) pair best never mentions, less one for
    each must-not-ship claim it drops on the same systems (the model's fix of a false line)."""
    (old_must, _, mentioned), (new_must, soft, _) = _claims(best), _claims(trial)
    dropped = Counter(systems for _, systems, _ in (old_must - new_must).elements())
    added = sum((new_must - old_must).values())
    for systems, pairs in soft:
        if pairs <= mentioned:
            continue
        if dropped[systems] > 0:
            dropped[systems] -= 1
        else:
            added += 1
    return added


def _merge(best, rev, draft, mode):
    """Take each field group from the revision when it validates, keeps the draft's material,
    adds no claim about Cole's systems (_added_claims) and scores better: fewer must-not-ship
    lines first, then fewer must-fix problems, then fewer problems in all."""
    taken = []
    for group in GROUPS:
        if all(rev.get(k) == best.get(k) for k in group):
            continue
        name = "+".join(group)
        if not all(isinstance(rev.get(k), str) and rev[k].strip() for k in group):
            print(f"humanizer: {name} in the revision is not text; keeping ours", flush=True)
            continue
        trial = dict(best, **{k: rev[k] for k in group})
        errs = validate(trial, mode)
        lost = _shape_loss(draft, trial) if "body_html" in group else None
        if errs or lost:
            print(f"humanizer: {name} refused ({'; '.join(errs) or lost})", flush=True)
            continue
        added = _added_claims(best, trial)
        if added > 0:
            print(f"humanizer: {name} refused (it adds {added} claim(s) about Cole's systems)", flush=True)
            continue
        before, after = _score(best), _score(trial)
        if after >= before:
            print(f"humanizer: {name} not cleaner ({after[2]} problem(s), {after[1]} must-fix)", flush=True)
            continue
        dropped = _sources(best) - _sources(trial)
        if dropped:
            print(f"humanizer: {name} accepted; it dropped source links {sorted(dropped)}", flush=True)
        best = trial
        taken.append(name)
    return best, taken


def _first_sentence(post, mode):
    """Last resort for a title or caption the revisions left as two sentences: keep the first
    one when it has three words or more. A new title gets new slug_words (rollout slugs are
    dated). The caption <text> in the art changes with the caption."""
    out = dict(post)
    title = re.sub(r"^Rollout Report:\s*", "", out["title"])
    first = _sentences(title)[0] if len(_sentences(title)) >= 2 else ""
    if _words(first) >= 3:
        out["title"] = ("Rollout Report: " if mode == "rollout" else "") + first
        if mode != "rollout":
            out["slug_words"] = " ".join(slugify(first).split("-")[:6])
    cap = out["svg_caption"].strip()
    first = _sentences(cap)[0] if len(_sentences(cap)) >= 2 else ""
    if _words(first) >= 3 and out["svg_inner"].count(cap) == 1:
        out["svg_caption"], out["svg_inner"] = first, out["svg_inner"].replace(cap, first)
    if out == post or validate(out, mode):
        return post
    kept = [f"{k} ({_words(out[k])} words)" for k in ("title", "svg_caption") if out[k] != post[k]]
    print(f"humanizer: kept the first sentence of the {' and the '.join(kept)}", flush=True)  # the log is public
    return out


def humanize(post, mode, messages, system):
    """Up to PASSES revision calls for the lint's findings, merged field group by field group.
    Keeps the draft's version of anything a revision makes worse; a failed call never costs the
    post."""
    try:
        return _humanize(post, mode, messages, system)
    except (Exception, SystemExit) as e:  # odd JSON types and the like: keep the draft
        print(f"humanizer: skipped ({type(e).__name__}: {str(e)[:200]}); keeping the draft", flush=True)
        return post


def _humanize(post, mode, messages, system):
    best = post
    probs = humanizer_problems(post)
    print(f"humanizer: {len(probs)} problem(s) in the draft", flush=True)
    trace("draft", post=post, problems=probs)
    for n in range(1, PASSES + 1):
        if not probs:
            break
        shown = probs[:40] + ([f"...and {len(probs) - 40} more like these"] if len(probs) > 40 else [])
        msgs = messages + [
            {"role": "assistant", "content": "```json\n" + json.dumps(best, ensure_ascii=False) + "\n```"},
            {"role": "user", "content": HUMANIZE_ASK + "\n- " + "\n- ".join(shown)}]
        try:
            raw = call_claude(msgs, system, search=False)
        except (Exception, SystemExit) as e:  # network, timeout, API error: stop asking
            print(f"humanizer: pass {n} skipped ({type(e).__name__}: {str(e)[:200]}); keeping what we have", flush=True)
            trace("revision", n=n, error=f"{type(e).__name__}: {str(e)[:200]}")
            break
        try:
            rev = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"humanizer: pass {n} unusable ({str(e)[:200]})", flush=True)
            trace("revision", n=n, error=str(e)[:200], raw=raw[-4000:])
            continue
        if not isinstance(rev, dict):
            print(f"humanizer: pass {n} was not a JSON object", flush=True)
            continue
        rev = dict(rev, **{k: post[k] for k in ("related", "keywords", "svg_alt") if k in post})
        if isinstance(rev.get("body_html"), str):
            rev["body_html"] = STRIP_TAGS.sub("", rev["body_html"])
        if isinstance(rev.get("svg_inner"), str):
            rev["svg_inner"] = repair_svg(rev["svg_inner"])
        best, taken = _merge(best, rev, post, mode)
        probs = humanizer_problems(best)
        print(f"humanizer: pass {n} took {', '.join(taken) or 'nothing'}; {len(probs)} problem(s) left", flush=True)
        trace("revision", n=n, revision=rev, taken=taken, problems=probs)
    if any(p.startswith(("title: two sentences", "svg_caption: two or more")) for p in probs):
        best = _first_sentence(best, mode)
    return best


# ---------------------------------------------------------------- emit
def compose_entry(post, mode, version, date_str):
    ver_slug = version.replace("v", "v").replace(".", "-")
    if mode == "rollout":
        slug = f"{ver_slug}-rollout-report-{today_et().strftime('%b-%d').lower()}"
    else:
        words = slugify(post["slug_words"])
        if len(words) > 48:  # cut at a word, never mid-word ("...-three-bil")
            words = words[:49].rsplit("-", 1)[0] if "-" in words[:49] else words[:48]
        slug = f"{ver_slug}-{words}".rstrip("-")
    if slug in SLUGS:
        slug += "-b"
    # body and svg go into non-raw triple-quoted literals: double every backslash so
    # "C:\Users" or "echo \N" loads as written instead of failing or turning into an escape
    body = post["body_html"].strip().replace("\\", "\\\\").replace('"""', '”””')
    svg = post["svg_inner"].strip().replace("\\", "\\\\").replace("'''", "")
    rollout = " rollout=True," if mode == "rollout" else ""
    entry = (
        "\ndict(\n"
        f"slug={json.dumps(slug)},\n"
        f'version={json.dumps(version)}, date={json.dumps(date_str)}, '
        f'read={json.dumps(read_time(body))},{rollout}\n'
        f"title={json.dumps(post['title'])},\n"
        f"desc={json.dumps(post['desc'])},\n"
        f"keywords={json.dumps(post['keywords'])},\n"
        f"related={json.dumps(post['related'][:3])},\n"
        f"svg_alt={json.dumps(post['svg_alt'])},\n"
        f"svg_caption={json.dumps(post['svg_caption'])},\n"
        f"svg=_svg('''\n{svg}\n'''),\n"
        f'body="""\n{body}\n"""),\n'
    )
    return slug, entry


def append_post(entry):
    src = open(POSTS_B_PATH, encoding="utf-8").read()
    idx = src.rstrip().rfind("]")
    if idx < 0:
        raise SystemExit("posts_b.py: closing ] not found")
    new = src[:idx].rstrip() + "\n" + entry + "]\n"
    open(POSTS_B_PATH, "w", encoding="utf-8").write(new)


def try_build():
    r = subprocess.run([sys.executable, os.path.join(SRC, "build_blog.py")],
                       capture_output=True, text=True, cwd=SRC)
    return r.returncode == 0, (r.stdout + r.stderr)[-2000:]


STUB = {
    "slug_words": "stub-pipeline-test-post",
    "title": "Stub: the pipeline test post",
    "desc": "A stub post used only to verify the serverless writer pipeline end to end. If you can read this in production, delete it and check the workflow.",
    "keywords": "stub, pipeline test",
    "related": [ALL[-1]["slug"]],
    "svg_alt": "A test pattern with the word STUB",
    "svg_caption": "This is only a test.",
    "svg_inner": f'<rect x="60" y="60" width="520" height="180" fill="none" stroke="{G}" stroke-width="3"/>'
                 f'<text x="320" y="165" fill="{A}" font-family="monospace" font-size="42" text-anchor="middle">STUB</text>'
                 f'<text x="320" y="280" fill="{D}" font-family="monospace" font-size="14" text-anchor="middle">This is only a test.</text>',
    "body_html": "<p>Pipeline test. " + "This sentence pads the stub to a plausible length. " * 60 +
                 'Sources: <a href="https://changelog.ciprari.ai/">one</a> '
                 '<a href="https://ciprari.ai/">two</a> '
                 '<a href="https://ciprari.ai/status">three</a>.</p>'
                 "<blockquote>If you can read this, the robots built it without me.</blockquote><p>End.</p>",
}


# ---------------------------------------------------------------- main
def main():
    _CUT.clear()
    _ECHO.clear()
    _TRACE.clear()
    args = sys.argv[1:]
    stub = "--stub" in args
    mode = pick_mode(next((a for a in args if not a.startswith("--")), "auto"))
    version = next_version(mode)
    date_str = today_et().strftime("%Y-%m-%d")
    print(f"mode={mode} version={version} date={date_str} model={MODEL} stub={stub}", flush=True)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not stub and already_published(date_str):
        print(f"already published for {date_str} — nothing to do", flush=True)
        if gh_out:
            with open(gh_out, "a") as f:
                f.write("skip=true\n")
        return

    backup = open(POSTS_B_PATH, encoding="utf-8").read()
    system, user = build_prompt(mode, version, date_str)
    messages = [{"role": "user", "content": user}]
    humanized = False

    for attempt in (1, 2):
        if stub:
            post = dict(STUB)
        else:
            raw = call_claude(messages, system)
            try:
                post = extract_json(raw)
            except (ValueError, json.JSONDecodeError) as e:
                trace("unparsed", attempt=attempt, error=str(e)[:200], raw=raw[-4000:])
                messages += [{"role": "assistant", "content": raw[-4000:]},
                             {"role": "user", "content": f"Your output failed to parse: {e}. "
                              "Return ONLY the corrected ```json block."}]
                continue
            if isinstance(post, dict) and isinstance(post.get("svg_inner"), str):
                post["svg_inner"] = repair_svg(post["svg_inner"])
            errs = validate(post, mode)
            if errs:
                trace("invalid", attempt=attempt, errors=errs, post=post)
                if attempt == 2:
                    raise SystemExit("validation failed twice: " + "; ".join(errs))
                messages += [{"role": "assistant", "content": raw[-4000:]},
                             {"role": "user", "content": "Fix these problems and return ONLY the "
                              "corrected ```json block:\n- " + "\n- ".join(errs)}]
                continue
            if not humanized:
                humanized = True
                post = humanize(post, mode, messages, system)  # the lint sees <cite> and asks for a restatement
            post["body_html"] = STRIP_TAGS.sub("", post["body_html"])  # no <cite> or bold in the published body
            post, cut = drop_high_risk(post)
            for field, text, label in cut:  # the run log is public: the label and length, never the words
                print(f"claims: cut a {_words(text)}-word sentence from {field} ({label})", flush=True)
            trace("final", post=post, cut=cut, problems=humanizer_problems(post))
            errs = validate(post, mode) if cut else []
            if errs:  # exit non-zero: nothing is appended, and the next scheduled run writes again
                raise SystemExit("claims: cutting must-not-ship sentences broke the post: " + "; ".join(errs))

        slug, entry = compose_entry(post, mode, version, date_str)
        append_post(entry)
        ok, log = try_build()
        if ok:
            print(f"published-ready: {slug}\n{log[-400:]}", flush=True)
            gh_out = os.environ.get("GITHUB_OUTPUT")
            if gh_out:
                with open(gh_out, "a") as f:
                    f.write(f"slug={slug}\ntitle={post['title']}\n")
            return
        open(POSTS_B_PATH, "w", encoding="utf-8").write(backup)
        if stub or attempt == 2:
            raise SystemExit(f"build failed: {log}")
        messages += [{"role": "assistant", "content": json.dumps(post)[-4000:]},
                     {"role": "user", "content": f"The site build rejected your post:\n{log}\n"
                      "Fix it and return ONLY the corrected ```json block."}]

    raise SystemExit("writer exhausted retries")


if __name__ == "__main__":
    main()
