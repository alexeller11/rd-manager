import os
from http.server import BaseHTTPRequestHandler, HTTPServer


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8080"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","mode":"stdlib"}')
            return

        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"message":"stdlib server running"}')
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"detail":"not found"}')

    def log_message(self, format, *args):
        print("[HTTP]", format % args, flush=True)


if __name__ == "__main__":
    print(f"Starting stdlib server on {HOST}:{PORT}", flush=True)
    httpd = HTTPServer((HOST, PORT), Handler)
    httpd.serve_forever()
