# Plushie Rush 🐾

A 3D plushie runner where you trade the actual stock market open hour. Each lane is a position (LEFT = short, MIDDLE = flat, RIGHT = long). Beat the optimal path. Top 20 globally + biggest losers leaderboard. Daily Stock-of-the-Day Wordle-style challenge.

Built for [Cursor Vibe Jam 2026](https://vibej.am/2026/). 100% AI-written.

## Play

- Live: deploy below
- Local: `python -m http.server 8088` then open http://localhost:8088/

## Controls

- ←/→ — switch lane (lane = position)
- ↑ — jump to BUY lane
- ↓ — jump to SELL lane
- Space — flatten (close to neutral)
- Esc / P — pause (with 💾 Save & Quit option)

## Deploy

### Option A — Netlify Drop (fastest, no GitHub needed)

1. Open https://app.netlify.com/drop in a browser
2. Drag this entire `plushies/` folder onto the page
3. Live URL appears in ~10 seconds (e.g. `https://crisp-otter-12345.netlify.app/`)
4. That URL is the jam submission link

### Option B — GitHub Desktop → Netlify (better for ongoing iteration)

1. Open GitHub Desktop → File → Add local repository → select this folder
2. Publish repository (private if you prefer; Netlify works with both)
3. Open https://app.netlify.com → Add new site → Import existing project
4. Pick the GitHub repo, default settings, Deploy
5. Future commits via GitHub Desktop auto-redeploy

The `.gitignore` in this folder excludes Blender source files, older variants, and internal handoff docs so only what's needed at runtime gets pushed.

## What's in here

| File | Purpose |
|---|---|
| `index.html` | Redirects to `game_001.html` (so the root URL works) |
| `game_001.html` | The actual game — single-file HTML, all CSS/JS inline |
| `config.json` | Alpaca paper API keys (paper01) |
| `data/bars_*.json` | Pre-fetched morning-hour OHLCV bars (~30 days × 3 symbols) |
| `sprites/`, `pano/` | Plushie character art and panoramic backgrounds |

## Submit to the jam

1. Deploy via Option A or B above → get a URL
2. Confirm `https://YOUR-URL/` loads the game (not 404)
3. Confirm the Vibe Jam tracker pings (DevTools → Network → look for `widget.js`)
4. Submit URL at https://vibej.am/2026/ before May 1, 2026 @ 13:37 UTC

## Tech

- No build step, no bundler, no npm
- Pre-fetched bars + Binance/Yahoo fallbacks → game is playable without keys
- Firebase Realtime DB (REST) for global leaderboard + visit tracking
- TraderVue / IBKR Flex CSV export of trade history
