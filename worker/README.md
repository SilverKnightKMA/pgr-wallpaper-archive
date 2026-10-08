# pgr-random — Cloudflare Worker

Serves a **random wallpaper** from this repo as real image bytes, metadata, or a redirect — always GitHub-hosted (this archive's own copies), never the game CDN.

## Endpoints

| Path | Returns |
|---|---|
| `…/wallpapers` | random image, any category |
| `…/desktop` | random **desktop** wallpaper |
| `…/mobile` | random **mobile** wallpaper |

Official host: `https://pgr-wallpapers.tungvuthanh.com` (Routes on the zone; the workers.dev URL and the old blog paths hit the same Worker). Default response is the image **bytes** proxied from `raw.githubusercontent.com` (Content-Type derived from the filename — the CDN occasionally mislabels images as `application/octet-stream`).

## Query params

### `?server=cn|jp|global|tw|kr`

Restrict the pick to one region's wallpapers. Combines with every other param.

```bash
curl -L -o w.jpg "https://pgr-wallpapers.tungvuthanh.com/wallpapers?server=jp"
```

### `?preview=1`

Serve the lightweight JPEG preview (a few dozen KB, from the `preview` branch) instead of the full image — handy for thumbnails and slow links.

### `?redirect=1`

Answer with an HTTP **302** straight to `raw.githubusercontent.com` instead of proxying bytes — the client then downloads directly from GitHub's CDN (Fastly). Fastest option for browsers and `wget`; strict tools that cannot follow redirects should use the default bytes mode.

### `?format=json`

Return **metadata** instead of image bytes — for scripts and bots. Fields: `filename`, `category`, `server`, `resolution`, `size` (human string from Kuro's index), `url` (full image), `previewUrl` (small JPEG), plus `seed` if one was given.

```bash
curl -s "https://pgr-wallpapers.tungvuthanh.com/wallpapers?format=json"
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
curl -s "https://pgr-wallpapers.tungvuthanh.com/mobile?count=3&server=cn"
```

### `?seed=<anything>`

**Deterministic** pick: the same seed returns the same wallpaper for as long as the index snapshot is unchanged (it is rebuilt on every archive batch, so long-term stability is not promised). The hash mixes in category and server, so `?seed=x` on `/desktop` and `/mobile` give different results. Random mode adds a per-attempt salt internally.

### `HEAD`

Headers only — `Content-Type` and `X-Random-Source` (the raw URL a GET would have served) with **no body and no upstream fetch**. Cheap probe for uptime checks:

```bash
curl -I "https://pgr-wallpapers.tungvuthanh.com/wallpapers"
```

## Errors

| Status | Meaning |
|---|---|
| `404` | unknown path, or no wallpapers match the filter combo |
| `405` | method other than GET/HEAD |
| `502` | index or upstream unavailable after retry |

## Auto-deploy from this repo

`.github/workflows/deploy-worker.yml` deploys `worker/worker.js` via `wrangler` on every push that touches `worker/**`. One-time setup:

1. **API token** — Cloudflare dashboard → My Profile → API Tokens → Create Token → *Edit Cloudflare Workers* template. Copy the token.
2. **Account ID** — Cloudflare dashboard (any Workers page) → right sidebar.
3. **Repo secrets** — GitHub repo → Settings → Secrets and variables → Actions → add:
   - `CLOUDFLARE_API_TOKEN` = token from step 1
   - `CLOUDFLARE_ACCOUNT_ID` = ID from step 2

## Domain wiring (already live, kept here for reference)

- DNS: `pgr-wallpapers` CNAME → `SilverKnightKMA.github.io`, **proxied** (orange cloud).
- GitHub Pages custom domain: `pgr-wallpapers.tungvuthanh.com` ("Enforce HTTPS" stays greyed behind the proxy — TLS is terminated by Cloudflare Universal SSL).
- Worker routes on the zone: `pgr-wallpapers.tungvuthanh.com/wallpapers*`, `/desktop*`, `/mobile*` → `pgr-random`. Routes survive every deploy.

## Manual fallback (dashboard paste)

Worker overview → Edit code → paste `worker.js` → Deploy. Always pulls the live index from `docs/index-data.json` on `main` (edge-cached 6 h; the URL is versioned `?v=2` — bump it when the item schema changes).
