#!/usr/bin/env python3
"""
apply_staged.py — publish posts the ColeOS Adviser staged from the Root Console.

Runs in GitHub Actions (publish-staged.yml, dispatched by the coleos-api worker's
/post-trigger when Cole presses "Publish post" in the console). Pulls the staged
posts from the worker, validates them with exactly the rules writer.py applies to
its own posts, appends them to changelog-src/posts_b.py, builds, and tells the
worker which ids went out. The workflow then deploys and commits back.

Env: COLEOS_ADMIN_TOKEN (the worker's admin bearer token, a repo secret).
"""
import importlib, json, os, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import writer  # noqa: E402  — reuse validate / compose_entry / append_post / try_build

API = "https://coleos-api.coleciprari.workers.dev"
TOKEN = os.environ.get("COLEOS_ADMIN_TOKEN", "").strip()


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, method=method, data=data, headers={
        "authorization": "Bearer " + TOKEN, "content-type": "application/json",
        "user-agent": "changelog-publish-staged"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def refresh_catalog():
    """Re-read posts_b so a second staged post versions and crosslinks after the first."""
    importlib.reload(writer.posts_b)
    writer.ALL = sorted(writer.posts_a.POSTS_A + writer.posts_b.POSTS_B, key=lambda p: p["date"])
    writer.SLUGS = {p["slug"] for p in writer.ALL}


def main():
    if not TOKEN:
        raise SystemExit("COLEOS_ADMIN_TOKEN is not set on this repo (Settings → Secrets → Actions)")
    posts = call("/pending-posts").get("posts", [])
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if not posts:
        print("no staged posts — nothing to publish")
        if gh_out:
            open(gh_out, "a").write("skip=true\n")
        return

    backup = open(writer.POSTS_B_PATH, encoding="utf-8").read()
    date_str = writer.today_et().strftime("%Y-%m-%d")
    done, slugs = [], []
    for p in posts:
        mode = "rollout" if p.get("rollout") else "post"
        post = {k: p.get(k) for k in writer.REQUIRED}
        post["related"] = p.get("related") or []
        errs = writer.validate(post, mode)
        if errs:
            open(writer.POSTS_B_PATH, "w", encoding="utf-8").write(backup)
            raise SystemExit(f"staged post #{p['id']} ({p.get('title')}) failed validation: " + "; ".join(errs))
        version = writer.next_version(mode)
        slug, entry = writer.compose_entry(post, mode, version, date_str)
        writer.append_post(entry)
        refresh_catalog()
        done.append(p["id"])
        slugs.append(slug)
        print(f"appended {slug} ({version})")

    ok, log = writer.try_build()
    if not ok:
        open(writer.POSTS_B_PATH, "w", encoding="utf-8").write(backup)
        raise SystemExit("build failed — posts_b.py restored:\n" + log)
    call("/posts-published", "POST", {"ids": done})
    print("published-ready:", ", ".join(slugs))
    if gh_out:
        open(gh_out, "a").write(f"slug={slugs[-1]}\nslugs={' '.join(slugs)}\n")


if __name__ == "__main__":
    main()
