#!/usr/bin/env python3
"""Simple HTTP server for the production build with CORS + API proxy."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
import os
import sys
import json
import urllib.request
import urllib.error

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/dist')

API_PROXY = 'http://localhost:8000'

class CORSHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        # Proxy /api/* requests to FastAPI on port 8000
        if self.path.startswith('/api/'):
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length else b''
                
                req = urllib.request.Request(
                    f'{API_PROXY}{self.path}',
                    data=body,
                    method='POST'
                )
                req.add_header('Content-Type', self.headers.get('Content-Type', ''))
                
                with urllib.request.urlopen(req, timeout=120) as resp:
                    response_data = resp.read()
                    self.send_response(200)
                    self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                    self.send_header('Content-Length', str(len(response_data)))
                    self.end_headers()
                    self.wfile.write(response_data)
            except Exception as e:
                sys.stderr.write(f"API proxy error: {e}\n")
                sys.stderr.flush()
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        
        # Default: serve static files
        super().do_POST()

    def log_message(self, format, *args):
        sys.stderr.write(f"{self.address_string()} - {format % args}\n")
        sys.stderr.flush()

class ReusableHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

print("Starting frontend server on port 3000 (API proxy: localhost:8000)...", file=sys.stderr, flush=True)
with ReusableHTTPServer(("", 3000), CORSHandler) as httpd:
    print("Serving on port 3000", file=sys.stderr, flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    print("Server stopped", file=sys.stderr, flush=True)
