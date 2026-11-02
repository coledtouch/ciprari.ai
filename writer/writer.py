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
import os, sys, json, re, html, datetime, subprocess, urllib.request, urllib.error
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


def recent_catalog(n=30):
    lines = []
    for p in ALL[-n:]:
        kind = " (rollout)" if p.get("rollout") else ""
        lines.append(f'- {p["slug"]} | {p["version"]} | {p["date"]}{kind} | {p["title"]}')
    return "\n".join(lines)


def _example_body(body, limit=5200):
    """The example's body without <cite>/<strong> tags, cut at a paragraph end (prompt copy only)."""
    b = re.sub(r"(?i)</?(?:cite|strong|b)\b[^>]*>", "", body).strip()
    if len(b) <= limit:
        return b
    end = b.rfind("</p>", 0, limit)
    return b[:end + 4] if end > 0 else b[:limit]


def style_example(mode):
    pool = [p for p in ALL if bool(p.get("rollout")) == (mode == "rollout")]
    p = pool[-1]
    return json.dumps({
        "title": p["title"], "desc": p["desc"], "keywords": p["keywords"],
        "svg_alt": p["svg_alt"], "svg_caption": p["svg_caption"],
        "body_html": _example_body(p["body"]),
    }, indent=1)


# ---------------------------------------------------------------- prompt
def build_prompt(mode, version, date_str):
    weekday = today_et().strftime("%A, %B %d, %Y")
    kind = ("the weekly Sunday Rollout Report — a roundup of THIS week's biggest AI/tech "
            "news (3–5 stories), each tied to something concrete in a system Cole runs"
            ) if mode == "rollout" else (
            "a regular post — pick ONE fresh AI/tech news story or development from the last "
            "few days and write an opinionated post that ties it to specific things in the "
            "production systems Cole runs")

    system = f"""You are the ghostwriter for changelog.ciprari.ai, the engineering blog of Cole
Ciprari — a Business Systems Architect in Worcester, MA who has shipped 15 production platforms
solo: a 120-route construction ERP at coenconstruction.com; estimate.pro, a multi-tenant
estimating SaaS for 25+ trades; curbscript.com, an AI SaaS for real-estate agents; The Punchlist
(thepunchlist.vercel.app), an AI automation consultancy; JetDesk.AI (jetdesk.ai), an
offline-first flight-planning PWA for a PA-46 turboprop; north.construction; valhalla-k9.com;
hiremariaelena.com; Show It With Words (showitwithwords.com), his mother's handmade-jewelry
storefront where every product is drawn live; PermitSketch (permitsketch.com), deck and porch
permit drawings from a phone; Atelier (atelier.ciprari.ai), his personal AI studio with models
from seven providers, open to LinkedIn testers on a metered allowance; Keep Fix Cut
(keepfixcut.com), a free AI teardown of dating profiles on one Cloudflare Worker that stores
nothing; and three Base44 apps.
He runs this blog as version-numbered releases of himself.

VOICE — non-negotiable:
- First person, dry, funny, concrete. A working operator talking shop. Short declarative
  sentences land the jokes. No hype words, no "delve", no "game-changer", no exclamation points.
- Ground claims in the two or three of Cole's systems the story actually touches, and stay
  with them; don't walk the whole list or restate each one's description. The pool: the ERP,
  the estimating SaaS, the dog-training site, the flight-planning PWA, the permit-drawing app,
  Atelier (his multi-model AI studio and its metered LinkedIn tester tier), the dating-profile
  teardown, payroll, Twilio dialers, D1 databases, review gates. Facts about his systems come
  only from this prompt: never invent counts, numbers, features, customers or incidents for
  them. You may say what you would check or change in one of them, framed as yours to do.
- Exactly one <blockquote> with a single dry one-liner of 16 words or fewer, placed in the
  last third. No slogans.
- End with a short kicker paragraph: one last concrete detail or a dry joke. Never a recap.

HUMANIZER — non-negotiable. Applies to every field you write: title, desc, svg_caption, body.
Write like a smart human with skin in the game, sending a message to one sharp reader.
1. No importance sentences. Nothing about impact, legacy, significance or broader trends.
   Say what happened and what it changes in a system Cole runs.
2. Banned words: pivotal, crucial, enhance, underscore, landscape, vibrant, testament, foster,
   delve, showcase, intricate, evolving, and their cousins (seamless, tapestry, transformative,
   groundbreaking, realm, paradigm).
3. No contrast structures anywhere: title, caption, art text, blockquote, link text, body.
   No "It's not X, it's Y." No "Not A. Not B. But C." No "Despite this." No two-beat lines
   that set one thing against another to score a point: "X shipped. Y did not.", "I can X.
   I cannot Y.", "X, not Y.", or any pair whose second sentence only undercuts the first.
   Make the point once.
4. No vague authority: no "experts say", "industry reports", "many believe", "analysts",
   "observers", "reportedly". Cut the line, or name a source you found in search and link it.
5. No summary endings: no "In conclusion", "Overall", "Ultimately", "At the end of the day",
   "The lesson", "N stories, one pattern". No neat wrap-up.
6. Specifics over general claims. If a line says something "improves results", say how,
   with the number from your source. If there is no proof, cut the line.
7. No sentence over 16 words. Split a long one into two full sentences. Keep a normal mix of
   lengths, with no runs of fragments. The desc is two or three short sentences.
8. If a sentence could appear in a post about 1,000 other topics, delete it.
9. No motivational tone. No TED Talk energy. No preaching. No calls to action.
10. Make it sound like a message sent to one person, not a stage speech.
No bold and no formatting tricks: no <strong>, no italics for emphasis, no ALL-CAPS emphasis.

RESEARCH — non-negotiable:
- Use web_search to find REAL, CURRENT news (today is {weekday}). Never invent stories,
  numbers, model names, or URLs. Every story must carry an outbound <a href="..."> link to a
  real source you found in search results. Rollout Reports need 3-5 stories, each with at
  least one source link; regular posts need at least 2 source links.
- Say what a source reported in your own short sentences and link it. Never paste
  search-result text, and never use <cite> tags.
- If search gives you nothing solid on a topic, pick a different story — never pad.

FORM:
- Title: one sentence, short, dry and specific. A rollout title is 'Rollout Report: ' plus one
  concrete image from the week in a single clause.
- Body is HTML: <p>, <h3> section heads (rollouts: one <h3> per story with a wry title),
  <a href>, <em> (only for titles of papers, books or shows), one <blockquote>. No <strong>,
  <b> or <cite>, no <script>, no <img>, no inline styles.
- 600–1100 words for a regular post, 800–1200 for a rollout. Stop when the facts run out;
  never pad to reach a count.
- Crosslink 2–4 older posts inline using EXACTLY this macro: {{link:slug|anchor text}}. The
  anchor is a 2–6 word phrase inside your own sentence, never a whole sentence or an old
  title. Only slugs from the catalog provided; the build hard-fails on unknown slugs.
- Header art: phosphor CRT line-art, 640x300 viewBox, on a dark background the wrapper
  provides. Use ONLY these colors: {G} (green, primary), {D} (dim green), {A} (amber accent),
  {M} (muted). Simple geometric/monospace-text scenes with one visual joke, matching the
  established style. Provide inner SVG elements only (no outer <svg> tag). Use
  font-family="monospace" for any <text>. Include a small caption-style <text> at the bottom
  that repeats svg_caption word for word.

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

    user = f"""Write {kind}.

This will publish as version {version} dated {date_str}.
{"The title MUST start with 'Rollout Report: '." if mode == "rollout" else ""}

Catalog of recent posts (for crosslinks and the related list — use only these slugs):
{recent_catalog()}
Most titles above use the retired two-sentence "X. Y did not." shape. Don't echo it in your
title, h3s, caption, blockquote or link text.

Style example — the most recent {"rollout" if mode == "rollout" else "regular"} post. It may
predate the HUMANIZER rules. Match its voice (first person, dry, grounded in Cole's
systems), its structure and its art style. Don't reuse its topic, jokes or imagery. Don't copy
its long sentences, contrast pairs, sentence-long link text, wrap-ups, advice aimed at
"operators", or anything it says about Cole's systems; the system prompt is the only source
for those. Never open with a platform count like "I run ten production platforms."
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
    off = sorted({c for c in _colors(post["svg_inner"]) if c not in PALETTE})
    if off:
        errs.append(f"svg_inner: fill and stroke must come from {sorted(PALETTE)}, not {off}")
    if mode == "rollout" and not post["title"].startswith("Rollout Report:"):
        errs.append("rollout title must start with 'Rollout Report: '")
    if not (80 <= len(post["desc"]) <= 200):
        errs.append("desc must be 140-160 chars (hard bounds 80-200)")
    wc = len(re.sub(r"<[^>]+>", " ", body).split())
    if wc < 450:
        errs.append(f"body too short ({wc} words)")
    return errs


def _colors(svg):
    """Every fill and stroke value in the art, attribute or inline style, lowercased."""
    return [(a or b).strip().lower() for _, a, b in
            re.findall(r"""(?i)\b(?:fill|stroke)(?:\s*=\s*(["'])(.*?)\1|\s*:\s*([^;"']+))""", svg or "")]


def _nearest_ink(hexcolor):
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    h = hexcolor if len(hexcolor) == 7 else "#" + "".join(c * 2 for c in hexcolor[1:])
    return min((G, D, A, M, "#04120a"), key=lambda ink: sum((x - y) ** 2 for x, y in zip(rgb(h), rgb(ink))))


def repair_svg(svg):
    """Mechanical art fixes on the writer's own draft, before validate(): a <line> drawn with
    x/y gets x1/y1, and an off-palette hex ink moves to the nearest palette ink."""
    def line(m):
        t = m.group(0)
        return t if re.search(r"(?i)\sx1\s*=", t) else re.sub(r"(?i)\s(x|y)(\s*=)", r" \g<1>1\2", t)

    def ink(m):
        c = m.group(2).lower()
        if c in PALETTE or not re.fullmatch(r"#(?:[0-9a-f]{3}){1,2}", c):
            return m.group(0)
        return m.group(1) + _nearest_ink(c)
    svg = re.sub(r"(?i)<line\b[^>]*>", line, svg)
    return re.sub(r"""(?i)(\b(?:fill|stroke)\s*(?:=\s*["']|:\s*))([^;"'\s>]*)""", ink, svg)


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
    return sorted(probs, key=lambda p: (not p.startswith(MUST_FIX), "-word sentence" in p))


# ---------------------------------------------------------------- claims
# Facts about Cole's systems come only from SYSTEM_FACTS. A sentence that names one of them
# (or follows one with "It"/"The table"/...) and states a stack, host, storage, logging,
# headcount, permission or past action goes back for revision. A few claims must never ship
# at all: Atelier keeping prompts or answers, a stack/version/exposure/patch claim, a
# first-person leaked-credentials story, a crime stated as fact. drop_high_risk() cuts any
# that are still there after the revisions.
SYSTEMS = [(name, re.compile(rx, re.I)) for name, rx in (
    ("Coen ERP", r"\bCoen\b|coenconstruction\.com|\b(?:the|my|our|his) (?:construction )?ERP\b"),
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
TECH = re.compile(r"(?-i:\bPHP\b|\bPython\b|\bVPS\b)|\bv?\d+\.\d+\.\d+\b|\bversion \d+(?:\.\d+)*\b|\bexposed\b|"
                  r"\b(?:un)?patched\b|\bvulnerable\b", re.I)
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
                     r"\b(?:never|not|no)\b[^.?!]{0,30}?\b(?:prompts?|answers?|uploads?|reports?|frames?)\b|"
                     r"n't\b[^.?!]{0,30}?\b(?:prompts?|answers?|uploads?|reports?|frames?)\b|"
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
    r"\bhundreds of times\b", re.I)
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
                   r"removed|turned|wrote|pinned|installed)\b", re.I)
INFRA = re.compile(r"\b(?:logs?|keys?|firewall|servers?|database|tables?|cron|repo|repository|branch|builds?|"
                   r"credentials|secrets?|migrations?|deploys?|deployments?|endpoints?|webhooks?|stack|codebase|"
                   r"session store|tickets?|patch(?:es)?|backups?|alerts?|dashboards?|dependenc(?:y|ies)|"
                   r"package\.json|tests?|versions?)\b|\.env\b|\blast (?:year|month|week|spring|summer|fall|winter|"
                   r"quarter)\b", re.I)
CRIME_LABEL = "a crime stated as fact"
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


def _claim(s, named, story, people):
    """(soft label, must-not-ship label, story) for one sentence. named: the Cole systems it is
    about; story: an earlier sentence in this paragraph told a first-person story about them."""
    if WOULD.search(s) or s.endswith("?"):
        return None, None, story
    high = soft = None
    rest = FACT_OK.sub(" ", s)
    if people and people.search(s) and not ATTRIBUTED.search(s):
        high = CRIME_LABEL
    elif "Atelier" in named and STORE.search(s) and CONTENT.search(s) and not NEG.search(s) and not LOCAL.search(s):
        high = "Atelier never stores or logs prompts or answers"
    elif (named or MY_SYSTEMS.search(s)) and TECH.search(rest):
        high = "a stack, version, exposure or patch claim about Cole's systems"
    elif KEY.search(s) and LEAK.search(s) and not HYPO.search(s) and (named or FIRST.search(s) or story):
        high = "a first-person leaked-credentials story"
    told = bool(STORY.search(s) and (named or GENERIC.search(s) or INFRA.search(s)))
    about = named or ME.search(s) or GENERIC.search(s)
    if "Atelier" in named and NOT_ATELIER_PROVIDER.search(s):
        soft = "a provider Atelier does not use (its nine are in SYSTEM FACTS)"
    elif "Atelier" in named and ATELIER_DETAIL.search(rest):
        soft = "an Atelier detail outside SYSTEM FACTS"
    elif about and (DOES_NOT.search(rest) or (named & NO_AI and AI_WORDS.search(s))):
        soft = "something SYSTEM FACTS says it does not do"
    elif told:
        soft = "a first-person story about Cole's systems"
    elif about and CLAIM.search(rest):
        soft = "a claim about Cole's systems outside SYSTEM FACTS"
    return soft, high, story or told


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


def _scan(fragment, people=None, strip=None):
    """Read an HTML fragment sentence by sentence. Returns (fragment, rows), one row per
    sentence: text, named (Cole systems), soft and high (claim labels or None). A sentence for
    which strip(row) is true is cut from the fragment; its tags stay, emptied, then tidied."""
    out, rows, cut = [], [], False
    for i, piece in enumerate(_BLOCK_TAG.split(fragment or "")):
        if i % 2:
            out.append(piece)
            continue
        prev, story = set(), False
        for sent in _split(piece):
            text = " ".join("".join(p for _, p in sent).split())
            if not text:
                out.append("".join(t for t, _ in sent))
                continue
            named = _systems(text) or (set(prev) if CARRY.match(text) else set())
            soft, high, story = _claim(text, named, story, people)
            row = {"text": text, "named": named, "soft": soft, "high": high}
            rows.append(row)
            prev = named
            if strip and strip(row):
                cut = True
                out.append("".join(t for t, p in sent if t[0] == "<" and not p))
            else:
                out.append("".join(t for t, _ in sent))
    return (_tidy("".join(out)) if cut else fragment), rows


def claim_problems(post):
    """Claims about Cole's systems (and named people) for the revision to fix."""
    fields = [(k, post.get(k) or "") for k in ("title", "desc", "svg_caption", "body_html")]
    people = _people(" ".join(_plain(v) for _, v in fields))
    probs = []
    for name, raw in fields:
        for r in _scan(raw, people)[1]:
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
    people = _people(" ".join(_plain(post.get(k)) for k in fields))
    out, cut = dict(post), []
    for k in fields:
        if isinstance(out.get(k), str):
            out[k], rows = _scan(out[k], people, strip=lambda r: r["high"])
            cut += [(k, r["text"], r["high"]) for r in rows if r["high"]]
    return out, cut


HUMANIZE_ASK = (
    "A lint pass found the HUMANIZER problems listed below. Fix each one by editing only the "
    "sentence or field it names. Split a long sentence at a natural joint into two full sentences "
    "and keep every fact. Fix a contrast pair by stating the point once, in one plain sentence; "
    "don't swap in another pair such as 'X takes a month. Y takes longer.' Web search is off for this step: add no new facts, numbers, names, quotes "
    "or links, and where a rule wants a source you don't have, cut the line. If a flagged phrase "
    "sits inside quotation marks, don't edit the quoted words: paraphrase without the quotes, quote "
    "fewer words, or cut it. Keep every crosslink (shorten its anchor text if needed), every source "
    "link, the headings, the related list and the art. If you change svg_caption, change the "
    "caption <text> in svg_inner to the same words. If you change the title, update slug_words to "
    "match. Return ONLY the corrected ```json block.")


def _body_words(p):
    return len(re.sub(r"<[^>]+>", " ", p.get("body_html") or "").split())


def _sources(p):
    return set(re.findall(r'href="(https://[^"]+)"', p.get("body_html") or ""))


def _shape_loss(post, rev):
    """Why a revision lost or invented material the draft had (None when it kept everything)."""
    if _sources(rev) != _sources(post):
        return "it changed the source links"
    if _body_words(rev) < 0.8 * _body_words(post):
        return f"it cut the body from {_body_words(post)} to {_body_words(rev)} words"
    for mark, what in (("{link:", "crosslinks"), ("<h3>", "headings")):
        if rev["body_html"].count(mark) < post["body_html"].count(mark):
            return f"it dropped {what}"
    return None


def humanize(post, mode, messages, system):
    """One revision pass for the lint's findings. Keeps the draft unless the revision validates,
    keeps its sources and shape, and has fewer problems; a failed revision never costs the post."""
    try:
        return _humanize(post, mode, messages, system)
    except (Exception, SystemExit) as e:  # network, timeout, odd JSON types: keep the draft
        print(f"humanizer: skipped ({type(e).__name__}: {str(e)[:200]}); keeping the draft")
        return post


def _humanize(post, mode, messages, system):
    probs = humanizer_problems(post)
    print(f"humanizer: {len(probs)} problem(s) in the draft")
    if not probs:
        return post
    shown = probs[:40] + ([f"...and {len(probs) - 40} more like these"] if len(probs) > 40 else [])
    msgs = messages + [
        {"role": "assistant", "content": "```json\n" + json.dumps(post, ensure_ascii=False) + "\n```"},
        {"role": "user", "content": HUMANIZE_ASK + "\n- " + "\n- ".join(shown)}]
    try:
        rev = extract_json(call_claude(msgs, system, search=False))
    except (ValueError, json.JSONDecodeError, SystemExit) as e:
        print(f"humanizer: revision unusable ({str(e)[:200]}); keeping the draft")
        return post
    if not isinstance(rev, dict):
        print("humanizer: revision was not a JSON object; keeping the draft")
        return post
    rev = dict(rev, **{k: post[k] for k in ("related", "keywords", "svg_alt") if k in post})
    if isinstance(rev.get("body_html"), str):
        rev["body_html"] = STRIP_TAGS.sub("", rev["body_html"])
    if not all(isinstance(rev.get(k), str) for k in ("slug_words", "title", "desc", "svg_caption",
                                                       "svg_inner", "body_html")):
        print("humanizer: revision has a non-text field; keeping the draft")
        return post
    errs = validate(rev, mode)
    if errs:
        print(f"humanizer: revision failed validation ({'; '.join(errs)}); keeping the draft")
        return post
    lost = _shape_loss(post, rev)
    if lost:
        print(f"humanizer: revision refused because {lost}; keeping the draft")
        return post
    left = humanizer_problems(rev)
    if len(left) >= len(probs):
        print(f"humanizer: revision not cleaner ({len(left)} problem(s)); keeping the draft")
        return post
    print(f"humanizer: revision accepted, {len(left)} problem(s) left")
    return rev


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
    print(f"mode={mode} version={version} date={date_str} model={MODEL} stub={stub}")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not stub and already_published(date_str):
        print(f"already published for {date_str} — nothing to do")
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
                messages += [{"role": "assistant", "content": raw[-4000:]},
                             {"role": "user", "content": f"Your output failed to parse: {e}. "
                              "Return ONLY the corrected ```json block."}]
                continue
            if isinstance(post, dict) and isinstance(post.get("svg_inner"), str):
                post["svg_inner"] = repair_svg(post["svg_inner"])
            errs = validate(post, mode)
            if errs:
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
            for field, text, label in cut:
                print(f'claims: cut from {field} ({label}): "{_clip(text, 160)}"', flush=True)
            errs = validate(post, mode) if cut else []
            if errs:  # exit non-zero: nothing is appended, and the next scheduled run writes again
                raise SystemExit("claims: cutting must-not-ship sentences broke the post: " + "; ".join(errs))

        slug, entry = compose_entry(post, mode, version, date_str)
        append_post(entry)
        ok, log = try_build()
        if ok:
            print(f"published-ready: {slug}\n{log[-400:]}")
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
