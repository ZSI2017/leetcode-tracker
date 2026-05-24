#!/usr/bin/env python3
"""Fetch LeetCode study plan problem list via GraphQL API.

Usage:
    python3 fetch_plan.py                           # fetch top-interview-150
    python3 fetch_plan.py --plan top-interview-150  # specify plan slug
    python3 fetch_plan.py --list                    # list known plans
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# ------ Config ------
DATA_DIR = Path(__file__).parent / "data"
LEETCODE_GRAPHQL = "https://leetcode.cn/graphql"
# International: "https://leetcode.com/graphql"

KNOWN_PLANS = {
    "top-interview-150":     "面试经典 150 题",
    "top-100-liked":          "热题 100",
    "leetcode-75":            "LeetCode 75",
    "binary-search":          "二分查找",
    "dynamic-programming":    "动态规划",
    "graph-theory":           "图论",
}

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://leetcode.cn/",
    "Origin": "https://leetcode.cn",
    "Accept": "application/json",
}


def graphql_query(query: str, variables: dict) -> dict:
    """Send a GraphQL query to LeetCode."""
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(LEETCODE_GRAPHQL, data=payload, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"❌ GraphQL request failed: {e}")
        sys.exit(1)


def fetch_study_plan(plan_slug: str) -> dict:
    """Fetch all problems from a study plan."""
    query = """
    query studyPlanDetail($slug: String!) {
      studyPlanV2Detail(planSlug: $slug) {
        name
        planSubGroups {
          name
          slug
          questions {
            titleSlug
            translatedTitle
            questionFrontendId
            difficulty
            status
            topicTags { name slug }
          }
        }
      }
    }
    """

    result = graphql_query(query, {"slug": plan_slug})
    data = result.get("data", {})

    plan = data.get("studyPlanV2Detail")
    if not plan:
        print(f"❌ Study plan '{plan_slug}' not found.")
        print(f"   Response: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
        sys.exit(1)

    # Flatten the structure
    problems = []
    total = 0
    for group in plan.get("planSubGroups", []):
        group_name = group.get("name", "Unknown")
        for q in group.get("questions", []):
            total += 1
            problems.append({
                "id": q["questionFrontendId"],
                "titleSlug": q["titleSlug"],
                "title": q.get("translatedTitle") or q.get("title", ""),
                "difficulty": q.get("difficulty", "Unknown"),
                "status": q.get("status", "NOT_STARTED"),
                "category": group_name,
                "tags": [t.get("name", "") for t in q.get("topicTags", [])],
            })

    plan_data = {
        "slug": plan_slug,
        "name": plan.get("name", plan_slug),
        "total": total,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "problems": problems,
    }

    return plan_data


def save_plan(plan_slug: str, plan_data: dict):
    """Save plan to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / f"{plan_slug}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved {plan_data['total']} problems to {filepath}")


def list_plans():
    """List known study plans."""
    print("Known study plans:\n")
    for slug, name in KNOWN_PLANS.items():
        cached = "📦" if (DATA_DIR / f"{slug}.json").exists() else "  "
        print(f"  {cached} {slug:30s} → {name}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch LeetCode study plan")
    parser.add_argument("--plan", default="top-interview-150", help="Study plan slug")
    parser.add_argument("--list", action="store_true", help="List known plans")
    args = parser.parse_args()

    if args.list:
        list_plans()
        return

    plan_slug = args.plan
    name = KNOWN_PLANS.get(plan_slug, plan_slug)
    print(f"📥 Fetching: {name} ({plan_slug}) ...")

    plan_data = fetch_study_plan(plan_slug)
    save_plan(plan_slug, plan_data)

    # Quick summary
    by_diff = {}
    for p in plan_data["problems"]:
        d = p["difficulty"]
        by_diff[d] = by_diff.get(d, 0) + 1
    print(f"   Difficulty: {by_diff}")


if __name__ == "__main__":
    main()
