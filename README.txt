AURA X TEAM — Wingo 1M Bot
━━━━━━━━━━━━━━━━━━━━━━━━━

RENDER DEPLOY STEPS:
1. GitHub এ একটা repo বানাও
2. এই সব files upload করো
3. render.com এ যাও → New → Background Worker
4. GitHub repo connect করো
5. Deploy!

FILES:
  main.py         → Bot runner (loop)
  wingo_bot.py    → Main bot logic
  big_image.jpg   → BIG prediction image
  small_image.png → SMALL prediction image
  requirements.txt→ Python packages
  render.yaml     → Render config

TIME SET করতে (wingo_bot.py এ):
  START_HOUR = 9   # সকাল ৯টা
  START_MIN  = 0
  STOP_HOUR  = 23  # রাত ১১টা
  STOP_MIN   = 0

BOT TOKEN: 8281243098:AAFf4wdCowXR6ent0peu7ngL_GYW7dXPqY8
CHANNEL:   @AURA_X_TEAM
