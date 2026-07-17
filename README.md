# Card Tracker — Goodra & Dragonite

Collection tracker web app: owned/missing checklist, live market prices (TCGplayer via
the Pokémon TCG API + Cardmarket trends), PSA graded estimates, portfolio P/L, deal
watch, budget planner, trade binder, and view-only share links.

- **Live app:** served from `/docs` via GitHub Pages
- `tracker_template.html` — single source of truth for the UI (artifact + web builds)
- `build.py` — builds the self-contained artifact version (embedded data + images)
- `fetch_data.py` — refreshes prices from api.pokemontcg.io, appends history, detects new cards
- `export_web.py` — emits `web/data.json` (external images, live-price annotations)
- `web_build.py` — transforms the template into the hosted app (`web/index.html`)
- Collections sync to Supabase via security-definer RPCs; the anon key in the page is
  public by design. Edit keys never leave the owner's browser.

Data sources: pokemontcg.io (TCGplayer + Cardmarket prices), Pokellector, and the
owner's Dragonite collection spreadsheet.
