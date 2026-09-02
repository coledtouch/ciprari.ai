# coleos-changelog — the self-writing blog

This repo writes, builds and ships changelog.ciprari.ai **entirely from GitHub's servers**.
No desktop app, no laptop. The machine can be off.

## How it works

1. **Every morning around 9:17 AM ET** (Sundays write the Rollout Report), GitHub Actions wakes up.
2. `writer/writer.py` calls the Claude API — with its built-in web search — to research real,
   current news and write the post in the established voice, art included.
3. The post is validated (crosslinks, source links, format), appended to
   `changelog-src/posts_b.py`, and the static site is built by `build_blog.py`.
4. `wrangler` deploys the built site to the `changelog` Cloudflare Worker, IndexNow is pinged,
   and the new post is committed back to this repo.
5. Downstream (already live, unchanged): the coleos-api Cloudflare cron sees the new post in
   the RSS feed within 30 minutes and sends the branded newsletter + posts to LinkedIn with a
   thumbnail. Fully serverless end to end.

## One-time setup

1. Create this repo on GitHub (private is fine), upload these files.
2. Repo → Settings → Secrets and variables → Actions → New repository secret:
   - `ANTHROPIC_API_KEY` — create at console.anthropic.com → API keys
   - `CLOUDFLARE_API_TOKEN` — the same scoped token used by deploy.sh
     (Workers Scripts: Edit only)
3. Repo → Settings → Actions → General → Workflow permissions → **Read and write**.
4. Test without publishing: Actions → write-and-publish → Run workflow → mode: `stub`
   (writes a throwaway post, builds, validates, deploys **nothing**).
5. Real test: Run workflow → mode: `auto`. It will research, write, deploy and commit.

## Important

- **This repo is now the source of truth for posts.** Edit posts here (or let the writer
  commit them); don't edit a local copy in parallel or they'll drift.
- Cron times are UTC: `13:00 UTC` = 9 AM EDT. In winter (EST) posts land at 8 AM — adjust
  to `14:00` in November if you care.
- The writer never invents news: it must cite real URLs found via web search, and the build
  hard-fails on broken crosslinks. If validation fails twice, the run fails loudly and
  nothing is published.
- Cost: roughly a few cents per post (Claude Sonnet + a handful of web searches).

## Posts staged from the ColeOS Root Console

The Adviser in ciprari.ai's admin console can write a post too (`add_post`) — a project
launch, a build note, a rollout. It lands in a review queue on the `coleos-api` worker, and
Cole's **Publish post** button dispatches `publish-staged.yml` here, which runs
`writer/apply_staged.py`: pull the queue, validate with the same rules as `writer.py`,
append to `posts_b.py`, build, deploy, commit back. Needs two more secrets:

- on this repo: `COLEOS_ADMIN_TOKEN` (the worker's admin bearer token, so the Action can read the queue)
- on the worker: `GH_DISPATCH_TOKEN_CHANGELOG` (fine-grained GitHub token, this repo only, Actions: Read and write)

## Files

- `writer/writer.py` — research + writing via Claude API, validation, version bumping
- `writer/apply_staged.py` — publishes posts staged from the Root Console (reuses writer.py's rules)
- `changelog-src/` — `posts_a.py`, `posts_b.py` (the catalog), `build_blog.py` (static build)
- `.github/workflows/publish.yml` — the daily schedule and pipeline
- `.github/workflows/deploy-on-push.yml` — merge to main = rebuild + deploy
- `.github/workflows/publish-staged.yml` — console-dispatched publish of staged posts
- `wrangler.jsonc` — assets-only deploy of `changelog-site/` (built, gitignored)
