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
import os, sys, json, re, datetime, subprocess, urllib.request, urllib.error
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


def style_example(mode):
    pool = [p for p in ALL if bool(p.get("rollout")) == (mode == "rollout")]
    p = pool[-1]
    return json.dumps({
        "title": p["title"], "desc": p["desc"], "keywords": p["keywords"],
        "svg_alt": p["svg_alt"], "svg_caption": p["svg_caption"],
        "body_html": p["body"].strip()[:5200],
    }, indent=1)


# ---------------------------------------------------------------- prompt
def build_prompt(mode, version, date_str):
    weekday = today_et().strftime("%A, %B %d, %Y")
    kind = ("the weekly Sunday Rollout Report — a roundup of THIS week's most consequential "
            "AI/tech news (3–5 stories), each examined for what it means for people running "
            "real business systems"
            ) if mode == "rollout" else (
            "a regular post — pick ONE fresh AI/tech news story or development from the last "
            "few days and write an opinionated essay connecting it to the realities of running "
            "production business systems")

    system = f"""You are the ghostwriter for changelog.ciprari.ai, the engineering blog of Cole
Ciprari — a Business Systems Architect in Worcester, MA who has shipped 10 production platforms
solo (a 120-route construction ERP at coenconstruction.com, estimate.pro, curbscript.com,
thepunchlist.ai, north.construction, valhalla-k9.com, hiremariaelena.com, and three Base44 apps) and runs this blog
as version-numbered releases of himself.

VOICE — non-negotiable:
- First person, dry, funny, concrete. A working operator, not a pundit. Short declarative
  sentences land the jokes. No hype words, no "delve", no "game-changer", no exclamation points.
- Every abstract claim gets grounded in something Cole actually runs: the ERP, the estimating
  SaaS, the dog-training site, payroll, Twilio dialers, D1 databases, review gates.
- Exactly one <blockquote> with a single quotable one-liner, placed in the last third.
- End with a short kicker paragraph, not a summary.

RESEARCH — non-negotiable:
- Use web_search to find REAL, CURRENT news (today is {weekday}). Never invent stories,
  numbers, model names, or URLs. Every story must carry an outbound <a href="..."> link to a
  real source you found in search results. Rollout Reports need 3-5 stories, each with at
  least one source link; regular posts need at least 2 source links.
- If search gives you nothing solid on a topic, pick a different story — never pad.

FORM:
- Body is HTML: <p>, <h3> section heads (rollouts: one <h3> per story with a wry title),
  <a href>, <em>, <strong>, one <blockquote>. No <script>, no <img>, no inline styles.
- 700–1100 words for a regular post, 800–1200 for a rollout.
- Crosslink 2–4 older posts inline using EXACTLY this macro: {{link:slug|anchor text}} —
  only slugs from the catalog provided. The build hard-fails on unknown slugs.
- Header art: phosphor CRT line-art, 640x300 viewBox, on a dark background the wrapper
  provides. Use ONLY these colors: {G} (green, primary), {D} (dim green), {A} (amber accent),
  {M} (muted). Simple geometric/monospace-text scenes with one visual joke, matching the
  established style. Provide inner SVG elements only (no outer <svg> tag). Use
  font-family="monospace" for any <text>. Include a small caption-style <text> at the bottom.

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

Style example — the most recent {"rollout" if mode == "rollout" else "regular"} post
(match its voice, structure and art style; do NOT reuse its topic, jokes, or imagery):
{style_example(mode)}

Research the news first. Then return the single ```json block."""
    return system, user


# ---------------------------------------------------------------- API
def call_claude(messages, system):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 16000,
        "system": system,
        "messages": messages,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
    }).encode()
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
    if mode == "rollout" and not post["title"].startswith("Rollout Report:"):
        errs.append("rollout title must start with 'Rollout Report: '")
    if not (80 <= len(post["desc"]) <= 200):
        errs.append("desc must be 140-160 chars (hard bounds 80-200)")
    wc = len(re.sub(r"<[^>]+>", " ", body).split())
    if wc < 450:
        errs.append(f"body too short ({wc} words)")
    return errs


# ---------------------------------------------------------------- emit
def compose_entry(post, mode, version, date_str):
    ver_slug = version.replace("v", "v").replace(".", "-")
    if mode == "rollout":
        slug = f"{ver_slug}-rollout-report-{today_et().strftime('%b-%d').lower()}"
    else:
        slug = f"{ver_slug}-{slugify(post['slug_words'])[:48]}".rstrip("-")
    if slug in SLUGS:
        slug += "-b"
    body = post["body_html"].strip().replace('"""', '”””')
    svg = post["svg_inner"].strip().replace("'''", "")
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
                 f'<text x="320" y="165" fill="{A}" font-family="monospace" font-size="42" text-anchor="middle">STUB</text>',
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
            errs = validate(post, mode)
            if errs:
                if attempt == 2:
                    raise SystemExit("validation failed twice: " + "; ".join(errs))
                messages += [{"role": "assistant", "content": raw[-4000:]},
                             {"role": "user", "content": "Fix these problems and return ONLY the "
                              "corrected ```json block:\n- " + "\n- ".join(errs)}]
                continue

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
