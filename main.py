"""
main.py — Background worker + HTTP server (Render free plan compatible)
"""

import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


# ====== HTTP SERVER (keep-alive for Render) ======
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - worker running")

    def log_message(self, format, *args):
        return


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), KeepAliveHandler)
    print(f"[http] Listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()


# ====== BACKGROUND WORKER ======
def run_worker():
    print("[worker] Started", flush=True)
    while True:
        try:
            # TODO: apnar actual kaj ekhane
            print("[worker] tick", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"[worker] error: {e}", flush=True)
            time.sleep(5)


# ====== ENTRYPOINT ======
def main():
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    run_worker()


if __name__ == "__main__":
    main()
