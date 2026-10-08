# pgr-random — Cloudflare Worker

Serves a **random wallpaper as real image bytes** from this repo (GitHub-hosted, never the game CDN).

## Official endpoints

Domain `pgr-wallpapers.tungvuthanh.com` also hosts the gallery (GitHub Pages at `/`); the Worker owns the three random paths:

| Path | Returns |
|---|---|
| `https://pgr-wallpapers.tungvuthanh.com/wallpapers` | random image, any category |
| `https://pgr-wallpapers.tungvuthanh.com/desktop` | random desktop wallpaper |
| `https://pgr-wallpapers.tungvuthanh.com/mobile` | random mobile wallpaper |

Query params: `?server=cn|jp|global|tw|kr` · `?preview=1` (small JPEG) · `?redirect=1` (302 to raw instead of streaming) · `?format=json` (metadata for scripts/bots) · `?count=1-20` (JSON array of distinct picks) · `?seed=...` (deterministic pick — stable only while the index snapshot is unchanged) · `HEAD` (headers only, no upstream fetch).

The workers.dev URL (`https://pgr-random.tungvt1912.workers.dev/...`) and the old blog paths (`blog.tungvuthanh.com/pgr-wallpaper-archive/...`) also work — same Worker.

## Auto-deploy from this repo

`.github/workflows/deploy-worker.yml` deploys `worker/worker.js` via `wrangler` on every push that touches `worker/**`. One-time setup:

1. **API token** — Cloudflare dashboard → My Profile → API Tokens → Create Token → *Edit Cloudflare Workers* template. Copy the token.
2. **Account ID** — Cloudflare dashboard (any Workers page) → right sidebar.
3. **Repo secrets** — GitHub repo → Settings → Secrets and variables → Actions → add:
   - `CLOUDFLARE_API_TOKEN` = token from step 1
   - `CLOUDFLARE_ACCOUNT_ID` = ID from step 2

Until the secrets exist the workflow skips with a visible warning (validated on Actions).

## Domain wiring (already live, kept here for reference)

- DNS: `pgr-wallpapers` CNAME → `SilverKnightKMA.github.io`, **proxied** (orange cloud).
- GitHub Pages custom domain: `pgr-wallpapers.tungvuthanh.com` ("Enforce HTTPS" stays greyed behind the proxy — TLS is terminated by Cloudflare Universal SSL, same as the blog).
- Worker routes on the zone: `pgr-wallpapers.tungvuthanh.com/wallpapers*`, `/desktop*`, `/mobile*` → `pgr-random`. Routes survive every deploy; no need to touch them again.

## Manual fallback (dashboard paste)

Worker overview → Edit code → paste `worker.js` → Deploy. Always pulls the live index from `docs/index-data.json` on `main` (edge-cached 6 h).
