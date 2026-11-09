# Job bot for sarkariresult-git.github.io

Har 30 min: naye updates -> Telegram + `_data/updates.json` (live board) + `_posts/` me draft posts (`published: false`).

## Setup
1. In files ko apni site repo (sarkariresult-git.github.io) ke root me upload karo (`.github`, `_includes`, `_data`, `scripts` folders ke saath).
2. Index page me jahan board chahiye wahan ye line likho: `{% include updates-board.html %}`
3. `_config.yml` me exclude jodo, taaki ye files site par na dikhein:
   `exclude: [scripts, sources.json, JOB-BOT-README.md]`
4. Repo -> Settings -> Secrets -> Actions: `TELEGRAM_BOT_TOKEN` aur `TELEGRAM_CHAT_ID` (is repo me dobara daalne honge).
5. Settings -> Actions -> General -> Workflow permissions -> Read and write.
6. Purani JobTejas-Bot repo ka "Job Updates" workflow **Disable** karo, warna Telegram par double message aayenge.
7. Actions -> Job Updates -> Run workflow. Pehli run silent hai (board bharta hai, draft/Telegram nahi).
8. `.github/workflows/jobs.yml` me `POST_LAYOUT` ko apni site ke post layout ke naam se match karo.

## Drafts publish karna
`_posts/` me file kholo -> content likho -> `published: false` ko `true` karo -> commit.
