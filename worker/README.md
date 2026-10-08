# pgr-random — Cloudflare Worker

Serves a **random wallpaper** from this repo as real image bytes, metadata, or a redirect — always GitHub-hosted (this archive's own copies), never the game CDN.

**Host:** the live host is whatever zone has routes pointed at this worker — see `worker.baseUrl` in `config.jsonc` (single source of truth). The paths below work on any host serving this worker; examples use the RFC 2606 reserved `wallpapers.example.com`.

## Endpoints

| Path | Returns |
|---|---|
| `/wallpapers` | random image, any category |
| `/desktop` | random **desktop** wallpaper |
| `/mobile` | random **mobile** wallpaper |

Default response is the image **bytes** proxied from `raw.githubusercontent.com` (Content-Type derived from the filename — the CDN occasionally mislabels images as `application/octet-stream`).

## Query params

### `?server=cn|jp|global|tw|kr`

Restrict the pick to one region's wallpapers. Combines with every other param.

```bash
curl -L -o w.jpg "https://wallpapers.example.com/wallpapers?server=jp"
```

### `?preview=1`

Serve the lightweight JPEG preview (a few dozen KB, from the `preview` branch) instead of the full image — handy for thumbnails and slow links.

### `?redirect=1`

Answer with an HTTP **302** straight to `raw.githubusercontent.com` instead of proxying bytes — the client then downloads directly from GitHub's CDN (Fastly). Fastest option for browsers and `wget`; strict tools that cannot follow redirects should use the default bytes mode.

### `?format=json`

Return **metadata** instead of image bytes — for scripts and bots. Fields: `filename`, `category`, `server`, `resolution`, `size` (human string from Kuro's index), `url` (full image), `previewUrl` (small JPEG), plus `seed` if one was given.

```bash
curl -s "https://wallpapers.example.com/wallpapers?format=json"
```

```json
{
  "filename": "fmh6a1xqn6cfp2wrzl-1636445166881官网图片 (9).jpg",
  "category": "desktop",
  "server": "cn",
  "url": "https://raw.githubusercontent.com/…/wallpapers/desktop/fmh6….jpg",
  "previewUrl": "https://raw.githubusercontent.com/…/preview/previews/fmh6….jpg",
  "resolution": "1920x1080",
  "size": "1.12 MB"
}
```

### `?count=N`

`N` **distinct** random picks as a JSON array (implies `format=json`). Clamped to **1–20** and to the size of the matching pool.

```bash
curl -s "https://wallpapers.example.com/mobile?count=3&server=cn"
```

### `?seed=<anything>`

**Deterministic** pick: the same seed returns the same wallpaper for as long as the index snapshot is unchanged (it is rebuilt on every archive batch, so long-term stability is not promised). The hash mixes in category and server, so `?seed=x` on `/desktop` and `/mobile` give different results. Random mode adds a per-attempt salt internally.

### `HEAD`

Headers only — `Content-Type` and `X-Random-Source` (the raw URL a GET would have served) with **no body and no upstream fetch**. Cheap probe for uptime checks:

```bash
curl -I "https://wallpapers.example.com/wallpapers"
```

## Errors

| Status | Meaning |
|---|---|
| `404` | unknown path, or no wallpapers match the filter combo |
| `405` | method other than GET/HEAD |
| `502` | index or upstream unavailable after retry |

## Caching

The wallpaper index (`docs/index-data.json`) is cached in-isolate and at the edge for **5 minutes** each — content or schema changes propagate automatically; there is no version to bump. The random pick itself is per-request.

## Auto-deploy from this repo

`.github/workflows/deploy-worker.yml` deploys `worker/worker.js` via `wrangler` on every push that touches `worker/**`. One-time setup:

1. **API token** — Cloudflare dashboard → My Profile → API Tokens → Create Token → *Edit Cloudflare Workers* template. Copy the token.
2. **Account ID** — Cloudflare dashboard (any Workers page) → right sidebar.
3. **Repo secrets** — GitHub repo → Settings → Secrets and variables → Actions → add:
   - `CLOUDFLARE_API_TOKEN` = token from step 1
   - `CLOUDFLARE_ACCOUNT_ID` = ID from step 2

## Putting the worker on your own host (optional)

To serve both the gallery (GitHub Pages) and the random API on one hostname:

1. **DNS**: `CNAME <host> → <owner>.github.io`, **proxied** (orange cloud).
2. **GitHub Pages**: Settings → Pages → Custom domain → `<host>`. "Enforce HTTPS" stays unavailable while the record is proxied — TLS is terminated by Cloudflare Universal SSL, which is fine.
3. **Worker routes** on the zone (not *Custom Domain* — that would hijack the whole hostname from Pages): `<host>/wallpapers*`, `/desktop*`, `/mobile*` → this worker. Routes survive every deploy.

## Manual fallback (dashboard paste)

Worker overview → Edit code → paste `worker.js` → Deploy, then add the `REPO` var (`owner/repo`) under Settings → Variables — the index URL is built from it at request time. Auto-deploys set it automatically.
