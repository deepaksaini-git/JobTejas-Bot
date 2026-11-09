# Sarkari Job Alert (free, deviceless)

GitHub Actions har 30 min me sources check karta hai, naye updates `jobs.json` me save karta hai
aur Telegram par bhejta hai. `alerts.html` wahi `jobs.json` dikhata hai.

## Setup (10 min)
1. GitHub par naya repo banao (ya apni `sarkariresult-git.github.io` repo use karo) aur ye saari files upload karo
   (`.github` folder bhi, hidden hota hai).
2. **Telegram bot:** Telegram me @BotFather -> `/newbot` -> token copy karo.
3. **Chat ID:** bot ko ya apne channel ko message bhejo. Channel ho to bot ko channel me Admin banao.
   Phir @userinfobot (personal) se ID lo, ya channel ke liye `@channelname` use karo.
4. Repo -> Settings -> Secrets and variables -> Actions -> New secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Repo -> Settings -> Actions -> General -> Workflow permissions -> **Read and write**.
6. Actions tab -> "Job Updates" -> **Run workflow**. Pehli run sirf data save karti hai (Telegram spam nahi hota),
   uske baad naye updates aate rahenge.
7. Website: Settings -> Pages se enable karo; `https://<user>.github.io/<repo>/alerts.html` khulega.

## Source add karna
`sources.json` me line jodo. `rss` (feed URL) ya `html` (page jisme notification links hon).
