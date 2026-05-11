"""
AURA X TEAM Wingo Bot — Render Runner
Checks every 15 seconds for new period
"""
import time, sys, os
from wingo_bot import run

print("🚀 AURA X TEAM Bot started on Render!")
print("📡 Checking every 15 seconds...")

while True:
    try:
        run()
    except Exception as e:
        print(f"❌ Error: {e}")
    time.sleep(15)
