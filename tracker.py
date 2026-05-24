#!/usr/bin/env python3
"""LeetCode progress tracker with spaced repetition.

Manages a progress.json file that tracks:
- Solved date for each problem
- Review schedule (1, 3, 7, 15, 30 days after solving)
- Mastery level (1-5)

Usage:
    python3 tracker.py status top-interview-150         # show stats
    python3 tracker.py done top-interview-150 1          # mark #1 as solved
    python3 tracker.py undo top-interview-150 1          # mark #1 as unsolved
    python3 tracker.py review top-interview-150 1        # complete a review
    python3 tracker.py due top-interview-150             # list problems due for review
    python3 tracker.py calendar top-interview-150        # show review calendar
    python3 tracker.py config username                   # show current username
    python3 tracker.py config username leetcode          # set username
    python3 tracker.py sync                              # sync solved from LeetCode
"""

import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ROOT_DIR = Path(__file__).parent

# Spaced repetition intervals (days after solved)
REVIEW_INTERVALS = [1, 3, 7, 15, 30]
REVIEW_LABELS = ["R1", "R2", "R3", "R4", "R5"]

GRAPHQL_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://leetcode.com/",
    "Origin": "https://leetcode.com",
}


def load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_progress(plan_slug: str) -> dict:
    """Load progress.json or initialize from plan data."""
    path = DATA_DIR / "progress.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            progress = json.load(f)
        # Merge with plan data if plan has new problems
        plan = load_json(f"{plan_slug}.json")
        return _merge_progress(progress, plan)
    else:
        plan = load_json(f"{plan_slug}.json")
        return _init_progress(plan)


def _init_progress(plan: dict) -> dict:
    """Initialize progress from a plan."""
    problems = {}
    for p in plan["problems"]:
        key = p["id"]
        problems[key] = {
            "id": p["id"],
            "titleSlug": p["titleSlug"],
            "title": p["title"],
            "difficulty": p["difficulty"],
            "category": p["category"],
            "tags": p["tags"],
            "status": "PENDING",  # PENDING | SOLVED | MASTERED
            "solved_date": None,
            "mastery": 0,  # 0-5
            "reviews": {},   # {"R1": "2026-04-27", "R2": null, ...}
            "notes": "",
        }
    return {
        "plan_name": plan.get("name", ""),
        "plan_slug": plan.get("slug", ""),
        "total": len(problems),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "problems": problems,
    }


def _merge_progress(progress: dict, plan: dict) -> dict:
    """Add new problems from plan to existing progress."""
    existing = progress.get("problems", {})
    for p in plan["problems"]:
        key = p["id"]
        if key not in existing:
            existing[key] = {
                "id": p["id"],
                "titleSlug": p["titleSlug"],
                "title": p["title"],
                "difficulty": p["difficulty"],
                "category": p["category"],
                "tags": p["tags"],
                "status": p.get("status", "PENDING"),
                "solved_date": None,
                "mastery": 0,
                "reviews": {},
                "notes": "",
            }
    progress["total"] = len(existing)
    progress["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return progress


# ---------- Actions ----------

def mark_solved(plan_slug: str, problem_id: str):
    """Mark a problem as solved and schedule reviews."""
    progress = load_progress(plan_slug)
    p = progress["problems"].get(problem_id)
    if not p:
        print(f"❌ Problem {problem_id} not found in plan")
        sys.exit(1)

    today = date.today().isoformat()
    p["status"] = "SOLVED"
    p["solved_date"] = p.get("solved_date") or today  # preserve original date
    p["mastery"] = max(p.get("mastery", 0), 1)

    # Schedule reviews (reset all, starting from today)
    p["reviews"] = {}
    for i, (label, days) in enumerate(zip(REVIEW_LABELS, REVIEW_INTERVALS)):
        p["reviews"][label] = (date.today() + timedelta(days=days)).isoformat()

    progress["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json("progress.json", progress)
    print(f"✅ Marked #{problem_id} '{p['title']}' as SOLVED")
    print(f"   Reviews: {', '.join(f'{l}: {d}' for l, d in p['reviews'].items())}")


def mark_unsolved(plan_slug: str, problem_id: str):
    """Reset a problem to unsolved."""
    progress = load_progress(plan_slug)
    p = progress["problems"].get(problem_id)
    if not p:
        print(f"❌ Problem {problem_id} not found in plan")
        sys.exit(1)

    p["status"] = "PENDING"
    p["solved_date"] = None
    p["mastery"] = 0
    p["reviews"] = {}
    progress["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json("progress.json", progress)
    print(f"🔄 Reset #{problem_id} '{p['title']}' to PENDING")


def complete_review(plan_slug: str, problem_id: str):
    """Mark a review as done (based on today's date)."""
    progress = load_progress(plan_slug)
    p = progress["problems"].get(problem_id)
    if not p:
        print(f"❌ Problem {problem_id} not found in plan")
        sys.exit(1)

    today = date.today()

    # Find which review level is due
    done = None
    for label in REVIEW_LABELS:
        due_str = p["reviews"].get(label)
        if due_str and date.fromisoformat(due_str) <= today:
            done = label
            break

    if done is None:
        print(f"ℹ️  No review due today for #{problem_id} '{p['title']}'")
        return

    # Mark this review as done (set to DONE)
    p["reviews"][done] = "DONE"
    p["mastery"] = min(p.get("mastery", 0) + 1, 5)
    if p["mastery"] >= 4:
        p["status"] = "MASTERED"

    progress["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json("progress.json", progress)
    print(f"✅ Review {done} done for #{problem_id} '{p['title']}' → mastery {p['mastery']}/5")


def list_due(plan_slug: str):
    """List problems due for review today."""
    progress = load_progress(plan_slug)
    today = date.today()
    due_today = []
    overdue = []

    for pid, p in progress["problems"].items():
        if p["status"] not in ("SOLVED", "MASTERED"):
            continue
        for label, due_str in p.get("reviews", {}).items():
            if due_str == "DONE":
                continue
            if not due_str:
                continue
            due_date = date.fromisoformat(due_str)
            if due_date == today:
                due_today.append((pid, p, label))
            elif due_date < today:
                overdue.append((pid, p, label, due_date))

    total_due = len(due_today) + len(overdue)
    if total_due == 0:
        print("🎉 No reviews due today!")
        return

    print(f"📋 Reviews Due: {total_due} problems\n")

    if overdue:
        print("🔴 OVERDUE:")
        for pid, p, label, d in overdue:
            days = (today - d).days
            print(f"  #{pid:>4s} {label} (overdue {days}d) — {p['title'][:40]} [{p['difficulty']}]")

    if due_today:
        print("\n🟡 TODAY:")
        for pid, p, label in due_today:
            print(f"  #{pid:>4s} {label} — {p['title'][:40]} [{p['difficulty']}]")

    print(f"\nUse: python3 tracker.py review {plan_slug} <id>")


def show_status(plan_slug: str):
    """Show progress statistics."""
    progress = load_progress(plan_slug)
    total = len(progress["problems"])
    solved = sum(1 for p in progress["problems"].values() if p["status"] in ("SOLVED", "MASTERED"))
    mastered = sum(1 for p in progress["problems"].values() if p["status"] == "MASTERED")
    pending = total - solved

    today = date.today()
    due_count = 0
    overdue_count = 0
    for p in progress["problems"].values():
        if p["status"] not in ("SOLVED", "MASTERED"):
            continue
        for label, due_str in p.get("reviews", {}).items():
            if due_str == "DONE" or not due_str:
                continue
            d = date.fromisoformat(due_str)
            if d <= today:
                if d == today:
                    due_count += 1
                else:
                    overdue_count += 1
                break

    # Per category
    cat_stats = {}
    for p in progress["problems"].values():
        cat = p.get("category", "Uncategorized")
        if cat not in cat_stats:
            cat_stats[cat] = {"total": 0, "solved": 0}
        cat_stats[cat]["total"] += 1
        if p["status"] in ("SOLVED", "MASTERED"):
            cat_stats[cat]["solved"] += 1

    # Per difficulty
    diff_stats = {}
    for p in progress["problems"].values():
        d = p.get("difficulty", "Unknown")
        if d not in diff_stats:
            diff_stats[d] = {"total": 0, "solved": 0}
        diff_stats[d]["total"] += 1
        if p["status"] in ("SOLVED", "MASTERED"):
            diff_stats[d]["solved"] += 1

    print(f"\n📊 {progress.get('plan_name', plan_slug)}")
    print(f"   Total: {total} | Solved: {solved} ({solved*100//total if total else 0}%) | Mastered: {mastered}")
    print(f"   Pending: {pending} | Due reviews: {due_count} | Overdue: {overdue_count}")

    print("\n📂 By Category:")
    for cat, stats in cat_stats.items():
        pct = f"{stats['solved']*100//stats['total']}%" if stats['total'] else "0%"
        bar = "█" * stats['solved'] + "░" * (stats['total'] - stats['solved'])
        print(f"   {cat:20s} {bar} {stats['solved']}/{stats['total']}")

    print("\n🎯 By Difficulty:")
    for diff in ["Easy", "Medium", "Hard", "Unknown"]:
        if diff in diff_stats:
            s = diff_stats[diff]
            pct = f"{s['solved']*100//s['total']}%" if s['total'] else "0%"
            print(f"   {diff:8s} {s['solved']}/{s['total']} ({pct})")


def show_calendar(plan_slug: str):
    """Show review calendar for next 7 days."""
    progress = load_progress(plan_slug)
    today = date.today()

    print(f"\n📅 Review Calendar (next 7 days)")
    for offset in range(8):
        d = today + timedelta(days=offset)
        label = "TODAY" if offset == 0 else d.strftime("%a %m/%d")
        count = 0
        for p in progress["problems"].values():
            if p["status"] not in ("SOLVED", "MASTERED"):
                continue
            for due_str in p.get("reviews", {}).values():
                if due_str == "DONE" or not due_str:
                    continue
                if date.fromisoformat(due_str) == d:
                    count += 1
                    break
        marker = " ⬅️" if count > 0 and offset == 0 else ""
        print(f"   {label:14s} {count} problems{marker}")


# ---------- Config ----------

CONFIG_PATH = ROOT_DIR / "config.json"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def get_username() -> str:
    config = load_config()
    return config.get("username", "")

def set_username(username: str):
    config = load_config()
    config["username"] = username
    save_config(config)
    print(f"✅ Username set to: {username}")


# ---------- Sync ----------

def graphql(query: str, variables: dict, endpoint: str = "https://leetcode.com/graphql") -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(endpoint, data=payload, headers=GRAPHQL_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def sync_from_leetcode(plan_slug: str = None, username: str = None):
    """Sync solved problems from LeetCode.com profile."""
    if username is None:
        username = get_username()
    if not username:
        print("❌ No username set. Use: python3 tracker.py config username <your-username>")
        return {"ok": False, "error": "No username set", "synced": 0}

    print(f"🔍 Fetching submissions for: {username} ...")

    # Query 1: recent AC submissions (up to 100)
    query_ac = """
    query recentAc($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        titleSlug
      }
    }
    """
    result = graphql(query_ac, {"username": username, "limit": 100})
    ac_slugs = set()

    if not result.get("error"):
        ac_list = result.get("data", {}).get("recentAcSubmissionList", [])
        for item in ac_list:
            ac_slugs.add(item.get("titleSlug", ""))
        print(f"   Recent AC submissions found: {len(ac_slugs)}")
    else:
        print(f"   ⚠️  Could not fetch recent submissions: {result['error']}")

    # Also try user profile for stats
    query_profile = """
    query userProfile($username: String!) {
      matchedUser(username: $username) {
        submitStats { acSubmissionNum { difficulty count } }
      }
    }
    """
    profile = graphql(query_profile, {"username": username})
    stats = None
    if not profile.get("error"):
        matched = profile.get("data", {}).get("matchedUser")
        if matched:
            stats = matched.get("submitStats", {}).get("acSubmissionNum", [])
            for s in stats:
                print(f"   {s['difficulty']}: {s['count']} solved")

    if not ac_slugs:
        print("   ℹ️  No recent AC submissions found from public API.")
        print("   The LeetCode public API only returns recent submissions (last ~20).")
        if stats:
            print(f"   Your profile shows solved problems, but individual problem list requires authentication.")
        return {"ok": True, "synced": 0, "stats": stats, "note": "Only recent AC found"}

    # Cross-reference with progress
    progress_path = DATA_DIR / "progress.json"
    if not progress_path.exists():
        print("   ⚠️  No progress.json yet. Run 'python3 tracker.py status' first.")
        return {"ok": False, "error": "No progress.json", "synced": 0}

    with open(progress_path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    synced = 0
    for pid, p in progress["problems"].items():
        if p["status"] != "PENDING":
            continue
        if p.get("titleSlug", "") in ac_slugs:
            today_str = date.today().isoformat()
            p["status"] = "SOLVED"
            p["solved_date"] = p.get("solved_date") or today_str
            p["mastery"] = max(p.get("mastery", 0), 1)
            # Schedule reviews
            p["reviews"] = {}
            for label, days in zip(REVIEW_LABELS, REVIEW_INTERVALS):
                p["reviews"][label] = (date.today() + timedelta(days=days)).isoformat()
            synced += 1

    progress["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    progress["leetcode_username"] = username

    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

    print(f"✅ Synced: {synced} problems marked as SOLVED")
    return {"ok": True, "synced": synced, "stats": stats}


# ---------- CLI ----------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "status":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        show_status(plan)

    elif cmd == "done":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        pid = sys.argv[3]
        mark_solved(plan, pid)

    elif cmd == "undo":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        pid = sys.argv[3]
        mark_unsolved(plan, pid)

    elif cmd == "review":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        pid = sys.argv[3]
        complete_review(plan, pid)

    elif cmd == "due":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        list_due(plan)

    elif cmd == "calendar":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        show_calendar(plan)

    elif cmd == "config":
        if len(sys.argv) < 3:
            config = load_config()
            print(json.dumps(config, ensure_ascii=False, indent=2))
        elif sys.argv[2] == "username":
            if len(sys.argv) > 3:
                set_username(sys.argv[3])
            else:
                print(f"Username: {get_username() or '(not set)'}")

    elif cmd == "sync":
        plan = sys.argv[2] if len(sys.argv) > 2 else "top-interview-150"
        sync_from_leetcode(plan)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
