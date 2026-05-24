#!/usr/bin/env python3
"""Simple HTTP server to serve the dashboard and data files.

Usage:
    python3 serve.py              # Start on port 8080
    python3 serve.py --port 9999  # Custom port
"""

import http.server
import json
import socketserver
import sys
from pathlib import Path

PORT = 8080
ROOT = Path(__file__).parent

# Import tracker functions
sys.path.insert(0, str(ROOT))
import tracker


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/config":
            config = tracker.load_config()
            self._send_json(config)
        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}

        if self.path == "/api/review":
            result = self._handle_review(body)
            self._send_json(result)
        elif self.path == "/api/sync":
            result = self._handle_sync(body)
            self._send_json(result)
        elif self.path == "/api/config":
            result = self._handle_config(body)
            self._send_json(result)
        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _handle_review(self, data):
        """Handle review completion from dashboard."""
        problem_id = data.get("id")
        if not problem_id:
            return {"error": "Missing problem id"}

        from datetime import date
        import time as time_mod

        progress_path = ROOT / "data" / "progress.json"
        if not progress_path.exists():
            return {"error": "progress.json not found"}

        with open(progress_path, "r", encoding="utf-8") as f:
            progress = json.load(f)

        p = progress["problems"].get(problem_id)
        if not p:
            return {"error": f"Problem {problem_id} not found"}

        today = date.today()
        done = None
        REVIEW_LABELS = ["R1", "R2", "R3", "R4", "R5"]
        for label in REVIEW_LABELS:
            due_str = p.get("reviews", {}).get(label)
            if due_str and due_str != "DONE" and date.fromisoformat(due_str) <= today:
                done = label
                break

        if done is None:
            return {"error": "No review due today"}

        p["reviews"][done] = "DONE"
        p["mastery"] = min(p.get("mastery", 0) + 1, 5)
        if p["mastery"] >= 4:
            p["status"] = "MASTERED"

        progress["updated_at"] = time_mod.strftime("%Y-%m-%d %H:%M:%S")

        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        return {
            "ok": True,
            "review": done,
            "mastery": p["mastery"],
            "status": p["status"],
        }

    def _handle_sync(self, data):
        """Sync solved problems from LeetCode."""
        username = data.get("username")
        if not username:
            username = tracker.get_username()
        if not username:
            return {"ok": False, "error": "No username set", "synced": 0}

        # Set username if provided
        if data.get("username"):
            tracker.set_username(data["username"])

        return tracker.sync_from_leetcode(username=username)

    def _handle_config(self, data):
        """Update config (username)."""
        if "username" in data:
            tracker.set_username(data["username"])
            return {"ok": True, "username": data["username"]}
        return {"ok": False, "error": "Missing username"}


def main():
    port = PORT
    if len(sys.argv) > 1 and sys.argv[1] == "--port":
        port = int(sys.argv[2])

    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}"
        print(f"🚀 Dashboard: {url}")
        print(f"   Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Bye!")


if __name__ == "__main__":
    main()
