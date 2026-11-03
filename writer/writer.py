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
import os, sys, json, re, html, hashlib, datetime, subprocess, urllib.request, urllib.error
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
# changes, change this sheet first.
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
  airport ships inside the app. METAR/TAF, winds aloft and crowd-shared fuel prices.
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
  The usage ledger records cost and time per request and never holds prompts or answers. The
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
- Atelier logs no prompts or answers; its ledger holds cost and time only. Keep Fix Cut saves
  no uploads or reports.
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


def _colors(svg):
    """Every fill, stroke and stop-color value in the art's tags, attribute or inline style,
    lowercased. Text between tags ("DISK FILL: 92%") is not ink."""
    return [(a or b).strip().lower() for tag in re.findall(r"<[^>]+>", svg or "") for _, a, b in
            re.findall(rf"""(?i){INK}(?:\s*=\s*(["'])(.*?)\1|\s*:\s*([^;"']+))""", tag)]


def _nearest_ink(hexcolor):
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    h = hexcolor if len(hexcolor) == 7 else "#" + "".join(c * 2 for c in hexcolor[1:])
    return min((G, D, A, M, "#04120a"), key=lambda ink: sum((x - y) ** 2 for x, y in zip(rgb(h), rgb(ink))))


NAMED_INK = {"white": "#ffffff", "red": "#ff0000", "green": "#008000", "lime": "#00ff00", "yellow": "#ffff00",
             "orange": "#ffa500", "gold": "#ffd700", "gray": "#808080", "grey": "#808080", "silver": "#c0c0c0"}


def repair_svg(svg):
    """Mechanical art fixes before validate(), on the writer's drafts and revisions and on
    staged posts: a <line> drawn with x/y gets x1/y1, and an off-palette ink (hex, rgb() or a
    common name) moves to the nearest palette ink. Only tags change, never the text."""
    def line(m):
        t = m.group(0)
        return t if re.search(r"(?i)\sx1\s*=", t) else re.sub(r"(?i)\s(x|y)(\s*=)", r" \g<1>1\2", t)

    def ink(m):
        c = m.group(2).lower().replace(" ", "")
        rgb = re.fullmatch(r"rgba?\((\d{1,3}),(\d{1,3}),(\d{1,3})(?:,[\d.]+%?)?\)", c)
        if c in PALETTE or c.startswith("url(#"):
            return m.group(0)
        new = ("none" if c == "transparent" else "#000" if c == "black" else
               _nearest_ink(NAMED_INK[c]) if c in NAMED_INK else
               _nearest_ink("#%02x%02x%02x" % tuple(min(255, int(v)) for v in rgb.groups())) if rgb else
               _nearest_ink(c) if re.fullmatch(r"#(?:[0-9a-f]{3}){1,2}", c) else None)
        return m.group(0) if new is None else m.group(1) + new
    svg = re.sub(r"(?i)<line\b[^>]*>", line, svg)
    return re.sub(r"<[^>]+>", lambda t: re.sub(
        rf"""(?i)({INK}\s*(?:=\s*["']|:\s*))(rgba?\([^)]*\)|[^;"'\s>]*)""", ink, t.group(0)), svg)


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
# A rollout title that runs two clauses together: "... through DNS and auditors found ...".
AND_CLAUSE = re.compile(
    r"\band (?:(?:the|a|an|its|their|his|her|one|two|three|four|five|six|\d+) )?(?:(?!that\b|which\b|who\b)"
    r"[\w'.-]+ ){1,2}(?:\w+ed|is|are|was|were|has|have|had|did|does|found|saw|got|went|took|made|said|ran|left|"
    r"kept|lost|won|hit|cut|set|put|sent|built|paid|fell|rose|grew|came|became|began|broke|shut|sold|bought|"
    r"told|wrote|stole|opens|closes|ships|wins|loses|gets|goes|says|finds|takes|makes)\b", re.I)
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


def _sentences(text):
    out = []
    for block in text.split("\n"):
        for s in re.split(r"(?:(?<=[.?!])|(?<=[.?!][\"'”)]))\s+", block):
            s = " ".join(s.split())
            if s:
                out.append(s)
    return out


def _words(s):
    return sum(1 for w in s.split() if re.search(r"\w", w))


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
                if m.group(0)[0].isupper() and s[:m.start()].strip(" \"'“‘(["):
                    continue  # a name mid-sentence: "the Foster report", "Crucial SSDs"
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
    if full_title.startswith("Rollout Report:") and AND_CLAUSE.search(title):
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
# the rest of its paragraph), a crime stated as fact. drop_high_risk() cuts any that are
# still there after the revisions. Checks run clause by clause, so a trailing "so I would
# check..." never excuses the clause before it.
SYSTEMS = [(name, re.compile(rx, re.I)) for name, rx in (
    ("Coen ERP", r"\bCoen\b|coenconstruction\.com|\bthe construction ERP\b|\b(?:my|our|his) (?:construction )?ERP\b"),
    ("estimate.pro", r"\bestimate\.pro\b|\bthe estimating (?:SaaS|tool|suite|platform|app)\b"),
    ("CurbScript", r"\bcurbscript\b"),
    ("The Punchlist", r"(?-i:\bPunchlist\b)|\bthepunchlist\b"),
    ("JetDesk", r"\bjetdesk\b|\bthe flight[- ]plann(?:er|ing (?:PWA|app|desk|tool))\b"),
    ("North Point", r"\bNorth Point Construction\b|\bnorth\.construction\b"),
    ("Valhalla K9", r"(?-i:\bValhalla\b)|\bvalhalla-k9\b|\bthe dog[- ]training (?:site|platform|company|business)\b"),
    ("Hire Mariaelena", r"\bhire ?mariaelena\b|\bthe (?:freelancer|résumé|resume) (?:portfolio|site|page)\b"),
    ("Show It With Words", r"(?-i:Show It With Words)|\bshowitwithwords\b|\bthe jewelry (?:site|storefront|store|shop)\b"),
    ("PermitSketch", r"\bpermitsketch\b|\bthe permit(?:[- ]drawing)? (?:app|tool)\b"),
    ("Atelier", r"(?-i:\bAtelier\b)|\batelier\.ciprari\.ai\b"),
    ("Keep Fix Cut", r"\bkeep ?fix ?cut\b|\bthe dating[- ]profile (?:teardown|tool|app)\b"),
    ("Base44 apps", r"(?-i:(?<!Amazon )(?<!AWS )\bAurora\b(?! (?:DB|Serverless|PostgreSQL|MySQL|Innovation)))|"
                    r"\bNorthern Hardy Honey\b|\bMari' Cosmetics\b|\bthe (?:three )?Base44 (?:apps|stack)\b|"
                    r"\bthe (?:honey|cosmetics) (?:shop|store|storefront|site)\b"),
)]
NO_AI = {"Valhalla K9", "Hire Mariaelena", "Show It With Words"}
# A bare "the ERP" is Cole's only when the post names his ERP and no vendor's. Otherwise it
# counts for the soft labels alone: a news line about SAP's ERP is never cut.
BARE_ERP = re.compile(r"\bthe ERP\b(?! (?:vendors?|makers?|market|industry|sector)\b)", re.I)
ERP_VENDOR = re.compile(r"\b(?:SAP|Oracle|NetSuite|Workday|Dynamics|Infor|Epicor|Sage|Odoo|Acumatica|Dolibarr|"
                        r"Deltek|Syspro|Unit4|IFS|JD Edwards|PeopleSoft|Procore|Viewpoint)\b")
# "It" or "The table" right after a sentence about a system is still about that system.
CARRY = re.compile(r"^(?:It|Its|They|Their|This|That|These|Those|Both|All three|The others|The (?:D1 )?(?:table|"
                   r"log|logs|ledger|database|router|worker|app|studio|tool|platform|session|token|cookie|codebase|"
                   r"stack|server|site|teardown|planner|module|suite))\b")
WOULD = re.compile(r"(?-i:\bI)(?:'d|'ll| would| will| might| could| should| want to| plan to)\b|\bif I\b|"
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
STORE = re.compile(r"\b(?:log(?:s|ged|ging)?|stor(?:e|es|ed|ing)|retain(?:s|ed|ing)?|keep(?:s|ing)?|kept|"
                   r"sav(?:e|es|ed|ing)|record(?:s|ed|ing)?|hold(?:s|ing)?|held|writes?|wrote|tables?|database)\b|"
                   r"(?-i:\bD1\b)", re.I)
CONTENT = re.compile(r"\b(?:prompts?|answers?|responses?|conversations?|exchanges?|chats?|messages?|transcripts?|"
                     r"what (?:the |a |each )?(?:users?|testers?|person) (?:asked|typed|sent|wrote)|"
                     r"what the model (?:returned|said|answered|wrote))\b", re.I)
LOCAL = re.compile(r"\b(?:browser|IndexedDB|on (?:the|your|my) (?:device|phone|laptop)|locally|local-first|"
                   r"opt-in|sync)\b", re.I)
SERVER = re.compile(r"(?-i:\bD1\b)|\b(?:tables?|databases?|servers?)\b", re.I)
# The negation has to govern the keeping: "does not log", "never stores", "logs no prompts".
# "logs each prompt, not the answer" and "stores every prompt and never deletes it" keep them.
KEEPS_NONE = re.compile(r"(?:\b(?:not|never|no)\b|n't\b)[^,.;]{0,20}?\b(?:log|stor|keep|kept|sav|record|hold|held|"
                        r"retain|writ)\w*|\b(?:log|stor|keep|kept|sav|record|hold|held|retain|writ)\w*\s+"
                        r"(?:no|none|nothing|neither)\b", re.I)
# A sentence's clauses. Each is checked on its own, so "X, so I would check Y" still answers for X.
CLAUSE = re.compile(r",\s*(?:so|and|but|then|because)\b|;|:(?!\d)", re.I)
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
Act Street Journal Times Post News Wall Silicon Valley White Washington York Bay Area""".split())
# soft: back to the model
FACT_OK = re.compile(r"\b(?:runs? on |on |behind |served by |in )?(?:one|a single) Cloudflare Worker\b|"
                     r"\bCloudflare Pages(?: Functions)?\b|\b(?:runs? on |on |built on |is a )?(?:Base44|Vercel)\b|"
                     r"\brole-based (?:team )?permissions\b|\bhealth monitoring\b|\bhuman review gate\b|"
                     r"(?:\b(?:logs?|stores?|keeps?|saves?|holds?|records?)\s+)?(?:\b(?:never|not|no)\b|n't\b)"
                     r"[^.?!]{0,30}?\b(?:prompts?|answers?|uploads?|reports?|frames?)\b|"
                     r"\b(?:opt-in|private) (?:thread )?sync\b|\b(?:expires? (?:after|in) )?(?:30|thirty)[- ]days?\b|"
                     r"\bIndexedDB\b|\bin (?:the|your) browser\b|\bon (?:the|your) device\b|"
                     r"\busage (?:ledger|analytics)\b|\bhashed session id\b|\bpage memory\b|"
                     r"\b(?:no|not|never)\b[^.?!]{0,20}?(?-i:\bPHP\b|\bPython\b|\bVPS\b|\bS3\b)", re.I)
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
HIGH_FIX = "cut it, or say what you would check instead"
CRIME_FIX = 'attribute it ("prosecutors say", "the complaint alleges") or cut it'
CLAIM_FIX = "say only what SYSTEM FACTS says, or what you would check, or cut it"


def _systems(text):
    return {name for name, rx in SYSTEMS if rx.search(text or "")}


def _people(text):
    """A pattern for a named person (full name or surname) followed closely by a crime verb."""
    names = set()
    for m in FULL_NAME.finditer(text or ""):
        if m.group(1) not in NOT_A_NAME and m.group(2) not in NOT_A_NAME:
            names |= {m.group(0), m.group(2)}
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(rf"\b(?:{alt})\b(?:[\s,]+[\w'’.-]+){{0,6}}?[\s,]+{CRIME}")


def _claim(s, named, story, people, loose=frozenset(), context=frozenset()):
    """(soft label, must-not-ship label, story) for one sentence. named: the Cole systems it is
    about; loose: ones it may be about (soft labels only); story: an earlier sentence in this
    paragraph told a first-person story about them; context: systems the paragraph named before
    it. Each clause answers for itself: only a clause that says "I would" is let off."""
    if s.endswith("?"):
        return None, None, story
    high = soft = None
    told = False
    for c in CLAUSE.split(s):
        if c.strip() and not WOULD.search(c):
            h, so, t = _clause(c, named, story or told, people, loose, context)
            high, soft, told = high or h, soft or so, told or t
    return soft, high, story or told


def _clause(c, named, story, people, loose, context):
    high = soft = None
    rest = FACT_OK.sub(" ", c)
    if people and people.search(c) and not ATTRIBUTED.search(c):
        high = CRIME_LABEL
    elif ("Atelier" in named and STORE.search(c) and CONTENT.search(c) and not KEEPS_NONE.search(c)
          and not (LOCAL.search(c) and not SERVER.search(c))):
        high = ATELIER_LABEL
    elif (named or MY_SYSTEMS.search(c) or GENERIC.search(c) or (context and RUNS_ON.search(c))) and TECH.search(rest):
        high = TECH_LABEL
    elif KEY.search(c) and LEAK.search(c) and not HYPO.search(c) and (named or FIRST.search(c) or story):
        high = LEAK_LABEL
    told = bool(STORY.search(c) and (named or loose or GENERIC.search(c) or INFRA.search(c)))
    if told and not high and any(INFRA.search(c, m.end(), m.end() + 60) or KEY.search(c, m.end(), m.end() + 60)
                                 for m in STORY.finditer(c)):
        high = STORY_LABEL  # the prompt bans these outright: "I checked the logs", "I rotated the keys"
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
    return high, soft, told


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
    starts = [0] + [m.end() for m in re.finditer(r"(?:(?<=[.?!])|(?<=[.?!][\"'”)]))\s+", plain)]
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
    """Post-wide context for _scan(): the named-person pattern, and whether a bare "the ERP"
    is Cole's (the post names his ERP and no vendor's)."""
    return _people(text), bool(SYSTEMS[0][1].search(text or "")) and not ERP_VENDOR.search(text or "")


def _scan(fragment, people=None, strip=None, erp=False):
    """Read an HTML fragment sentence by sentence. Returns (fragment, rows), one row per
    sentence: text, named and loose (Cole systems), soft and high (claim labels or None). A
    sentence for which strip(row) is true is cut from the fragment; its tags stay, emptied, then
    tidied. Once a paragraph tells a first-person story about his logs, keys or stack, a later
    sentence there that reads like more of it (first person, "It", a system, logs, keys) is
    must-not-ship too, unless it says what he would check or carries a source link."""
    out, rows, cut = [], [], False
    for i, piece in enumerate(_BLOCK_TAG.split(fragment or "")):
        if i % 2:
            out.append(piece)
            continue
        prev, story, context, tale = set(), False, set(), False
        for sent in _split(piece):
            text = " ".join("".join(p for _, p in sent).split())
            if not text:
                out.append("".join(t for t, _ in sent))
                continue
            named, loose = _systems(text) or (set(prev) if CARRY.match(text) else set()), set()
            if "Coen ERP" not in named and BARE_ERP.search(text) and not ERP_VENDOR.search(text):
                if erp or "Coen ERP" in context:
                    named = named | {"Coen ERP"}
                else:
                    loose = {"Coen ERP"}
            soft, high, story = _claim(text, named, story, people, loose, context)
            linked = any(re.match(r"(?i)<a\s", t) for t, _ in sent)
            if tale and not high and not linked and not WOULD.search(text) and (
                    named or loose or CARRY.match(text) or FIRST.search(text) or GENERIC.search(text)
                    or INFRA.search(text) or KEY.search(text) or LEAK.search(text) or CLAIM.search(text)):
                high = TALE_LABEL
            tale = tale or high in (STORY_LABEL, LEAK_LABEL) or bool(high == TECH_LABEL and STORY.search(text))
            row = {"text": text, "named": named, "loose": loose, "soft": soft, "high": high}
            rows.append(row)
            prev, context = named, context | named
            if strip and strip(row):
                cut = True
                out.append("".join(t for t, p in sent if t[0] == "<" and not p))
            else:
                out.append("".join(t for t, _ in sent))
    return (_tidy("".join(out)) if cut else fragment), rows


def claim_problems(post):
    """Claims about Cole's systems (and named people) for the revision to fix."""
    fields = [(k, post.get(k) or "") for k in ("title", "desc", "svg_caption", "body_html")]
    people, erp = _context(" ".join(_plain(v) for _, v in fields))
    probs = []
    for name, raw in fields:
        for r in _scan(raw, people, erp=erp)[1]:
            if r["high"]:
                fix = CRIME_FIX if r["high"] == CRIME_LABEL else HIGH_FIX
                probs.append(f'{name}: must not ship, {r["high"]}; {fix}: "{_clip(r["text"])}"')
            elif r["soft"]:
                probs.append(f'{name}: {r["soft"]}; {CLAIM_FIX}: "{_clip(r["text"])}"')
    named = _systems(" ".join(_plain(v) for _, v in fields))
    if len(named) > 3:
        probs.append(f"body_html: names {len(named)} of Cole's systems ({', '.join(sorted(named))}); "
                     "keep the two or three the story touches")
    return probs


def drop_high_risk(post):
    """Cut every must-not-ship sentence still in the title, desc, caption or body. Runs after the
    revisions; returns (post, [(field, sentence, label)])."""
    fields = ("title", "desc", "svg_caption", "body_html")
    people, erp = _context(" ".join(_plain(post.get(k)) for k in fields if isinstance(post.get(k), str)))
    out, cut = dict(post), []
    for k in fields:
        if isinstance(out.get(k), str):
            out[k], rows = _scan(out[k], people, strip=lambda r: r["high"], erp=erp)
            cut += [(k, r["text"], r["high"]) for r in rows if r["high"]]
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


def trace(kind, **data):
    """Append one JSON line to WRITER_TRACE (when set): drafts, revisions and what was kept.
    The repo is public and so is the artifact, so no must-not-ship sentence goes in it."""
    if not TRACE_PATH:
        return
    row = {"at": datetime.datetime.now(ET).isoformat(timespec="seconds"), "kind": kind,
           **{k: _public(k, v) for k, v in data.items()}}
    try:
        with open(TRACE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"trace: could not write {TRACE_PATH} ({e})", flush=True)


def _public(key, value):
    """A trace value without its must-not-ship text: cut from drafts and raw output, a word
    count in place of the quote in a problem, a short hash in place of a cut sentence."""
    if key in ("post", "revision") and isinstance(value, dict):
        return drop_high_risk(value)[0]
    if key == "raw" and isinstance(value, str):
        people, erp = _context(_plain(value))
        return _scan(value, people, strip=lambda r: r["high"], erp=erp)[0]
    if key == "problems" and isinstance(value, list):
        return [_public_problem(p) for p in value]
    if key == "cut":
        return [{"field": f, "label": label, "words": _words(t), "sha256": hashlib.sha256(t.encode()).hexdigest()[:12]}
                for f, t, label in value]
    return value


def _public_problem(p):
    if "must not ship" not in p:
        return p
    head, _, quote = p.partition(': "')  # labels and fixes hold no ': "', so this is the quote
    return f"{head}: [{_words(quote)} words, kept out of the trace]"


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
    link (the lint asks for that); a post the draft linked may not disappear."""
    added, removed = _sources(rev) - _sources(post), _sources(post) - _sources(rev)
    if added:
        return f"it added source links {sorted(added)} (and dropped {sorted(removed)})"
    if _body_words(rev) < 0.8 * _body_words(post):
        return f"it cut the body from {_body_words(post)} to {_body_words(rev)} words"
    if not _crosslinked(post) <= _crosslinked(rev):
        return f"it dropped crosslinks {sorted(_crosslinked(post) - _crosslinked(rev))}"
    if rev["body_html"].count("<h3>") < post["body_html"].count("<h3>"):
        return "it dropped headings"
    return None


def _must(problem):
    return problem.startswith(MUST_FIX) or "must not ship" in problem


def _score(post):
    probs = humanizer_problems(post)
    return sum(1 for p in probs if _must(p)), len(probs)


def _merge(best, rev, draft, mode):
    """Take each field group from the revision when it validates, keeps the draft's material
    and scores better: fewer must-fix problems first, then fewer problems in all."""
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
        before, after = _score(best), _score(trial)
        if after >= before:
            print(f"humanizer: {name} not cleaner ({after[1]} problem(s), {after[0]} must-fix)", flush=True)
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
    print(f'humanizer: kept the first sentence: "{out["title"]}" / "{out["svg_caption"]}"', flush=True)
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
