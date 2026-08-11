#!/usr/bin/env python3
"""Simple HTTP server for the production build with CORS headers."""
import http.server
import socketserver
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/dist')

class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress log output

with socketserver.TCPServer(("", 3000), CORSHandler) as httpd:
    httpd.serve_forever()
