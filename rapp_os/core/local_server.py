#!/usr/bin/env python3
"""
RAPP Local Server - HTTP endpoint for brain stem

Runs locally and provides REST API for RAPP Desktop and external integrations.
"""

import json
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any
import threading

from brain_stem import process_request, get_brain_stem

DEFAULT_PORT = 7071


class RappRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for RAPP local server."""

    def _set_cors_headers(self):
        """Set CORS headers for cross-origin requests."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, data: Dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/health':
            self._send_json({"status": "ok", "service": "rapp-brain-stem"})

        elif path == '/agents':
            brain = get_brain_stem()
            agents = brain.agent_registry.list_agents()
            self._send_json({"agents": agents})

        elif path == '/contexts':
            brain = get_brain_stem()
            contexts = brain.context_manager.list_contexts()
            self._send_json({"contexts": contexts})

        elif path == '/reload':
            brain = get_brain_stem()
            brain.reload()
            self._send_json({"status": "reloaded"})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length else '{}'

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        if path in ['/api/rapp', '/api/chat', '/api/process']:
            # Main RAPP endpoint
            user_input = data.get('user_input', data.get('message', ''))
            if not user_input:
                self._send_json({"error": "user_input required"}, 400)
                return

            result = process_request(
                user_input=user_input,
                user_guid=data.get('user_guid', 'default'),
                session_guid=data.get('session_guid', ''),
                context_guid=data.get('context_guid', 'default'),
                conversation_history=data.get('conversation_history', [])
            )
            self._send_json(result)

        elif path == '/api/context/create':
            # Create new context
            brain = get_brain_stem()
            ctx = brain.context_manager.create_context(
                name=data.get('name', 'New Context'),
                agents=data.get('agents', ['*']),
                skills=data.get('skills', ['*']),
                description=data.get('description', ''),
                system_prompt=data.get('system_prompt', '')
            )
            self._send_json({
                "guid": ctx.guid,
                "name": ctx.name
            })

        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class RappLocalServer:
    """Local HTTP server for RAPP brain stem."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start the server in a background thread."""
        self.server = HTTPServer(('127.0.0.1', self.port), RappRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"RAPP Brain Stem running at http://127.0.0.1:{self.port}")

    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
            self.server = None


def main():
    """Run the local server."""
    import signal

    server = RappLocalServer()
    server.start()

    print("Press Ctrl+C to stop")

    def signal_handler(sig, frame):
        print("\nShutting down...")
        server.stop()
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep main thread alive
    while True:
        try:
            threading.Event().wait(1)
        except KeyboardInterrupt:
            break

    server.stop()


if __name__ == "__main__":
    main()
