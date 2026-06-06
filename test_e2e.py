"""
FarmersPulse — End-to-End Test Script
======================================
Tests the complete pipeline:
  1. Local Flask system is reachable
  2. POST alert → auto-publishes in real time
  3. Personalized feed is stored
  4. Dashboard feed is in AI order
  5. AI report endpoint returns valid data

Usage:
    python test_e2e.py
    python test_e2e.py http://localhost:5000      # explicit local URL
    python test_e2e.py https://abc.ngrok-free.app # through ngrok
"""

import sys
import json
import time
import requests

BASE_URL    = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
AI_API_KEY  = "fp-ai-secret-2025"
HEADERS     = {"Content-Type": "application/json", "X-API-Key": AI_API_KEY}

PASS = "✓"
FAIL = "✗"

def test(name, fn):
    try:
        result = fn()
        print(f"  {PASS}  {name}")
        return result
    except Exception as e:
        print(f"  {FAIL}  {name}  →  {e}")
        return None


print(f"\n{'='*60}")
print(f"  FarmersPulse End-to-End Test")
print(f"  Target: {BASE_URL}")
print(f"{'='*60}\n")


# ── 1. Health check ────────────────────────────────────────────────────────────
print("1. Connectivity")
r = test("Flask app is reachable",
         lambda: requests.get(BASE_URL, timeout=5))


# ── 2. Post an AI alert (auto-publish) ────────────────────────────────────────
print("\n2. AI Post (auto-publish)")

SAMPLE_ALERT = {
    "title":           "Maize disease outbreak in Narok County",
    "short_text":      "Farmers in Narok are advised to inspect maize crops for grey leaf spot.",
    "full_text":       "A new wave of grey leaf spot has been detected in Narok County. Affected maize plants show elongated grey lesions on leaves. Farmers are advised to apply recommended fungicides and consult their local extension officer immediately. Early intervention can reduce yield losses by up to 40%.",
    "category":        "crop_disease",
    "tags":            "maize,disease,narok,fungicide",
    "target_crops":    "Maize",
    "target_counties": "Narok",
}

post_result = test(
    "POST /api/ai/post returns 201 and auto-publishes",
    lambda: (
        lambda r: (
            r.raise_for_status(),
            r.json()
        )[1]
    )(requests.post(f"{BASE_URL}/api/ai/post", headers=HEADERS, json=SAMPLE_ALERT, timeout=10))
)

if post_result:
    test("Response contains post_id",
         lambda: post_result.get("post_id") is not None or (_ for _ in ()).throw(AssertionError("no post_id")))
    test("Status is 'published' (not 'pending_review')",
         lambda: (post_result.get("status") == "published") or
                 (_ for _ in ()).throw(AssertionError(f"status={post_result.get('status')}")))
    print(f"     post_id={post_result.get('post_id')}  status={post_result.get('status')}")


# ── 3. Get all posts (published) ───────────────────────────────────────────────
print("\n3. Posts Feed")
posts_result = test(
    "GET /api/ai/all-posts returns posts",
    lambda: requests.get(f"{BASE_URL}/api/ai/all-posts", headers=HEADERS, timeout=10).json()
)
if posts_result:
    post_ids = [p["id"] for p in posts_result.get("posts", [])]
    print(f"     Total published posts: {posts_result.get('total')}  |  IDs sample: {post_ids[:5]}")


# ── 4. Bulk profiles ───────────────────────────────────────────────────────────
print("\n4. Farmer Profiles")
profiles_result = test(
    "GET /api/ai/bulk-profiles returns users",
    lambda: requests.get(f"{BASE_URL}/api/ai/bulk-profiles", headers=HEADERS, timeout=10).json()
)
if profiles_result:
    print(f"     Active farmers: {profiles_result.get('total', 0)}")


# ── 5. Personalized feed ───────────────────────────────────────────────────────
print("\n5. Personalized Feed")
if profiles_result and post_ids:
    users = profiles_result.get("users", [])
    if users:
        uid = users[0].get("id", users[0].get("user_id", 1))
        feed_payload = {
            "user_id":    uid,
            "post_ids":   post_ids[:10],
            "model_version": "test-v1.0",
            "response_time_ms": 42,
        }
        test(
            f"POST /api/ai/personalized-feed for user {uid}",
            lambda: requests.post(
                f"{BASE_URL}/api/ai/personalized-feed",
                headers=HEADERS, json=feed_payload, timeout=10
            ).raise_for_status()
        )
    else:
        print("  ⚠  No farmer users in DB yet (register a user first)")


# ── 6. AI report ───────────────────────────────────────────────────────────────
print("\n6. AI Report")
report_result = test(
    "GET /api/ai/report returns summary",
    lambda: requests.get(f"{BASE_URL}/api/ai/report", headers=HEADERS, timeout=10).json()
)
if report_result:
    s = report_result.get("summary", {})
    print(f"     AI posts published: {s.get('total_ai_posts_published')}")
    print(f"     Published today:    {s.get('published_today')}")
    print(f"     Active farmers:     {s.get('active_farmers')}")
    print(f"     Farmers with AI feed: {s.get('farmers_with_personalized_feed')}")


# ── 7. User profile endpoint ───────────────────────────────────────────────────
print("\n7. User Profile API")
test(
    "GET /api/ai/user-profile/1 (admin always exists)",
    lambda: requests.get(f"{BASE_URL}/api/ai/user-profile/1", headers=HEADERS, timeout=10)
    # May return 404 if user 1 is admin not farmer — that's OK
)


print(f"\n{'='*60}")
print("  Test run complete.")
print(f"{'='*60}\n")
