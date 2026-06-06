"""
FarmersPulse — Alert Feeder (alert_feeder.py)
=============================================
Place this file inside local_system/ next to app.py.
Run it AFTER Flask and the Colab tunnel are both running.

  python alert_feeder.py

HOW IT WORKS:
  1. Sends alerts one-by-one to Colab /process
  2. Colab embeds each alert with DistilBERT, matches farmers
     via FAISS, then auto-posts it to Flask
  3. After every 10 alerts, calls /personalize-all so every
     farmer's dashboard re-ranks to match their profile
  4. Every hour calls /rebuild-index so newly registered
     farmers are automatically included in matching
  5. Loops forever — all 10000 sent then restarts

INSTALL:
  pip install requests schedule
"""

import requests, json, time, os, schedule
from datetime import datetime

# ──────────────────────────────────────────────────────────────
# CONFIG — paste your Colab URL here each session
# ──────────────────────────────────────────────────────────────
COLAB_MODEL_URL = os.environ.get(
    "COLAB_MODEL_URL",
    "https://communist-footwear-coordinated-strategic.trycloudflare.com"
).rstrip("/")

MODEL_API_KEY = "model-secret-2025"
HEADERS = {"Content-Type": "application/json", "X-API-Key": MODEL_API_KEY}

ALERTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.json")

def load_alerts():
    if not os.path.exists(ALERTS_FILE):
        raise FileNotFoundError(f"alerts.json not found at {ALERTS_FILE}")
    with open(ALERTS_FILE) as f:
        return json.load(f)                                                                        

def check_health():
    try:
        r = requests.get(f"{COLAB_MODEL_URL}/health", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f"[HEALTH OK] device={d.get('device')} | faiss_farmers={d.get('faiss_farmers')} | ids={d.get('farmer_ids')}")
            return True
        print(f"[HEALTH] Status {r.status_code}")
        return False
    except Exception as e:
        print(f"[HEALTH FAIL] {e}")
        return False

def send_alert(alert):
    payload = {
        "title":           alert["title"],
        "description":     alert["description"],
        "category":        alert.get("category", "advisory"),
        "tags":            alert.get("tags", ""),
        "target_crops":    alert.get("target_crops", ""),
        "target_counties": alert.get("target_counties", ""),
        "top_k":           10,
        "sim_threshold":   0.3,
        "auto_post":       True
    }
    try:
        r = requests.post(f"{COLAB_MODEL_URL}/process", json=payload, headers=HEADERS, timeout=25)
        r.raise_for_status()
        result = r.json()
        print(
            f"  [{alert['aid']:>3}] {alert['category']:<14} | "
            f"post_id={str(result.get('post_id','?')):<5}| "
            f"matched={result.get('total_matched',0)} farmers | "
            f"{result.get('inference_ms',0)}ms | "
            f"\"{alert['title'][:50]}\""
        )
        return True
    except requests.exceptions.ConnectionError:
        print(f"  [CONN ERROR] Cannot reach {COLAB_MODEL_URL} — is Cell 8 running?")
        return False
    except requests.exceptions.HTTPError as e:
        print(f"  [HTTP {e.response.status_code}] {e.response.text[:80]}")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False

def trigger_personalization():
    try:
        r = requests.post(f"{COLAB_MODEL_URL}/personalize-all", headers=HEADERS, timeout=30)
        r.raise_for_status()
        result = r.json()
        print(f"\n  [PERSONALIZED] {result.get('personalized',0)} farmer feeds updated")
        for u in result.get("users", []):
            print(f"    user_id={u['user_id']} | county={u.get('county','?')} | ranked={u.get('ranked',0)} posts")
        print()
    except Exception as e:
        print(f"  [PERSONALIZE ERROR] {e}")

def rebuild_faiss_index():
    try:
        r = requests.post(f"{COLAB_MODEL_URL}/rebuild-index", headers=HEADERS, timeout=30)
        r.raise_for_status()
        result = r.json()
        print(f"\n[FAISS REBUILT] {result.get('message')} | ids={result.get('farmer_ids')}\n")
    except Exception as e:
        print(f"[REBUILD ERROR] {e}")

def run():
    alerts = load_alerts()
    total  = len(alerts)

    print("=" * 65)
    print("  FarmersPulse Alert Feeder")
    print(f"  Colab URL    : {COLAB_MODEL_URL}")
    print(f"  Total alerts : {total}")
    print(f"  Interval     : 8s per alert | personalize every 10 | rebuild every 60min")
    print("=" * 65)

    if not check_health():
        print("\n⚠  Colab not reachable. Check Cell 8 is running and URL is correct.\n")

    schedule.every(60).minutes.do(rebuild_faiss_index)

    loop_count = 0
    total_sent = 0
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting feed...\n")

    while True:
        loop_count += 1
        if loop_count > 1:
            print(f"\n{'─'*65}\n[LOOP {loop_count}] Restarting — keeps dashboards fresh\n{'─'*65}\n")

        for i, alert in enumerate(alerts):
            schedule.run_pending()
            if send_alert(alert):
                total_sent += 1
            if (i + 1) % 10 == 0:
                trigger_personalization()
            time.sleep(1)

        print(f"\n[LOOP {loop_count} COMPLETE] {total_sent} total sent\n")
        time.sleep(30)

if __name__ == "__main__":
    run()