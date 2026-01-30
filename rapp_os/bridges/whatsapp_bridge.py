#!/usr/bin/env python3
"""
RAPP WhatsApp Bridge - Cross-platform messaging interface

Uses WhatsApp Business API or WhatsApp Web integration to enable
users to interact with RAPP via WhatsApp messages.

Architecture:
    WhatsApp → Webhook/Polling → Brain Stem → WhatsApp Reply

Setup Options:
1. WhatsApp Business API (recommended for production)
2. WhatsApp Web via baileys/whatsapp-web.js (for personal use)
"""

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import threading
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whatsapp_bridge")

# Configuration
RAPP_HOME = Path.home() / ".rapp"
BRIDGE_CONFIG = RAPP_HOME / "whatsapp_bridge.json"


class WhatsAppBridge:
    """
    Bridge between WhatsApp and RAPP Brain Stem.

    Supports both WhatsApp Business API and webhook mode.
    """

    def __init__(
        self,
        phone_number_id: str = None,
        access_token: str = None,
        verify_token: str = None,
        webhook_port: int = 7072,
        prefix: str = "",
        allowed_numbers: List[str] = None
    ):
        """
        Initialize the WhatsApp bridge.

        Args:
            phone_number_id: WhatsApp Business phone number ID
            access_token: WhatsApp Business API access token
            verify_token: Webhook verification token
            webhook_port: Port for webhook server
            prefix: Optional command prefix (empty = respond to all)
            allowed_numbers: Phone numbers allowed to send commands
        """
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token or "rapp_verify_token"
        self.webhook_port = webhook_port
        self.prefix = prefix
        self.allowed_numbers = allowed_numbers or []

        self.running = False
        self.process_callback: Optional[Callable] = None
        self.webhook_server = None

        # Load config
        self._load_config()

        # WhatsApp API base URL
        self.api_base = "https://graph.facebook.com/v18.0"

    def _load_config(self):
        """Load configuration from disk."""
        if BRIDGE_CONFIG.exists():
            try:
                config = json.loads(BRIDGE_CONFIG.read_text())
                self.phone_number_id = config.get("phone_number_id", self.phone_number_id)
                self.access_token = config.get("access_token", self.access_token)
                self.verify_token = config.get("verify_token", self.verify_token)
                self.webhook_port = config.get("webhook_port", self.webhook_port)
                self.prefix = config.get("prefix", self.prefix)
                self.allowed_numbers = config.get("allowed_numbers", self.allowed_numbers)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

    def _save_config(self):
        """Save configuration to disk."""
        BRIDGE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        BRIDGE_CONFIG.write_text(json.dumps({
            "phone_number_id": self.phone_number_id,
            "verify_token": self.verify_token,
            "webhook_port": self.webhook_port,
            "prefix": self.prefix,
            "allowed_numbers": self.allowed_numbers
            # Note: access_token not saved for security
        }, indent=2))

    def add_allowed_number(self, number: str):
        """Add a phone number to the whitelist."""
        # Normalize number (remove spaces, dashes, ensure + prefix)
        number = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not number.startswith("+"):
            number = "+" + number

        if number not in self.allowed_numbers:
            self.allowed_numbers.append(number)
            self._save_config()
            logger.info(f"Added allowed number: {number}")

    def _is_allowed(self, sender: str) -> bool:
        """Check if sender is in whitelist."""
        if not self.allowed_numbers:
            return True  # No whitelist = allow all

        sender_normalized = sender.replace(" ", "").replace("-", "")
        for allowed in self.allowed_numbers:
            allowed_normalized = allowed.replace(" ", "").replace("-", "")
            # Compare last 10 digits
            if sender_normalized[-10:] == allowed_normalized[-10:]:
                return True
        return False

    def send_message(self, to: str, message: str) -> bool:
        """Send a WhatsApp message."""
        if not self.phone_number_id or not self.access_token:
            logger.error("WhatsApp credentials not configured")
            return False

        url = f"{self.api_base}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        # Truncate long messages
        if len(message) > 4096:
            message = message[:4093] + "..."

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": message}
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Sent message to {to}")
                return True
            else:
                logger.error(f"Failed to send message: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def _process_incoming_message(self, sender: str, text: str):
        """Process an incoming WhatsApp message."""
        # Check whitelist
        if not self._is_allowed(sender):
            logger.warning(f"Blocked message from {sender}")
            return

        # Check prefix if set
        if self.prefix:
            if text.lower().startswith(self.prefix.lower()):
                text = text[len(self.prefix):].strip()
            else:
                return  # Not a command

        logger.info(f"Processing message from {sender}: {text[:50]}...")

        # Route to brain stem
        if self.process_callback:
            try:
                response = self.process_callback(
                    user_input=text,
                    user_guid=f"whatsapp_{sender.replace('+', '')}",
                    context_guid="whatsapp"
                )

                reply = response.get("response", "Sorry, I couldn't process that.")
                self.send_message(sender, reply)

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                self.send_message(sender, f"Error: {str(e)[:100]}")

    def set_processor(self, callback: Callable):
        """Set the callback for processing messages."""
        self.process_callback = callback

    def _create_webhook_handler(self):
        """Create HTTP handler for WhatsApp webhook."""
        bridge = self

        class WebhookHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                """Handle webhook verification."""
                from urllib.parse import urlparse, parse_qs

                query = parse_qs(urlparse(self.path).query)
                mode = query.get("hub.mode", [""])[0]
                token = query.get("hub.verify_token", [""])[0]
                challenge = query.get("hub.challenge", [""])[0]

                if mode == "subscribe" and token == bridge.verify_token:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(challenge.encode())
                    logger.info("Webhook verified")
                else:
                    self.send_response(403)
                    self.end_headers()

            def do_POST(self):
                """Handle incoming messages."""
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode()

                try:
                    data = json.loads(body)

                    # Extract messages from webhook payload
                    if "entry" in data:
                        for entry in data["entry"]:
                            for change in entry.get("changes", []):
                                value = change.get("value", {})
                                messages = value.get("messages", [])

                                for msg in messages:
                                    if msg.get("type") == "text":
                                        sender = msg.get("from", "")
                                        text = msg.get("text", {}).get("body", "")

                                        # Process in thread to not block webhook
                                        threading.Thread(
                                            target=bridge._process_incoming_message,
                                            args=(sender, text)
                                        ).start()

                except Exception as e:
                    logger.error(f"Error processing webhook: {e}")

                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                pass  # Suppress logging

        return WebhookHandler

    def start_webhook_server(self):
        """Start the webhook server."""
        handler = self._create_webhook_handler()
        self.webhook_server = HTTPServer(("0.0.0.0", self.webhook_port), handler)

        logger.info(f"WhatsApp webhook server started on port {self.webhook_port}")
        self.webhook_server.serve_forever()

    def start(self):
        """Start the WhatsApp bridge."""
        self.running = True
        self._save_config()

        logger.info(f"WhatsApp bridge starting...")
        logger.info(f"Webhook port: {self.webhook_port}")
        logger.info(f"Allowed numbers: {self.allowed_numbers or 'ALL'}")
        logger.info(f"Command prefix: '{self.prefix}' (empty = respond to all)")

        # Start webhook server
        self.start_webhook_server()

    def stop(self):
        """Stop the bridge."""
        self.running = False
        if self.webhook_server:
            self.webhook_server.shutdown()
        self._save_config()


def create_whatsapp_context():
    """Create a WhatsApp-specific context in RAPP."""
    try:
        from brain_stem import get_brain_stem

        brain = get_brain_stem()

        if "whatsapp" not in brain.context_manager.contexts:
            brain.context_manager.create_context(
                name="WhatsApp",
                agents=["*"],
                skills=["*"],
                description="Context for WhatsApp commands",
                system_prompt="""You are RAPP, responding via WhatsApp.
Keep responses concise (under 500 chars when possible).
Be helpful and friendly. The user is messaging you via WhatsApp.
You can use emojis sparingly to be friendly.
Available commands are handled by your agents."""
            )
            # Set GUID to "whatsapp"
            ctx = brain.context_manager.contexts.pop(list(brain.context_manager.contexts.keys())[-1])
            ctx.guid = "whatsapp"
            brain.context_manager.contexts["whatsapp"] = ctx

    except Exception as e:
        logger.warning(f"Could not create WhatsApp context: {e}")


def setup_whatsapp():
    """Interactive setup for WhatsApp Business API."""
    print("=" * 50)
    print("RAPP WhatsApp Bridge Setup")
    print("=" * 50)
    print("\nTo use WhatsApp Business API, you need:")
    print("1. A Meta Developer account")
    print("2. A WhatsApp Business App")
    print("3. A phone number registered with WhatsApp Business")
    print("\nGet these from: https://developers.facebook.com/apps/")
    print()

    phone_id = input("Enter Phone Number ID: ").strip()
    access_token = input("Enter Access Token: ").strip()
    verify_token = input("Enter Verify Token (or press Enter for default): ").strip() or "rapp_verify_token"

    config = {
        "phone_number_id": phone_id,
        "access_token": access_token,
        "verify_token": verify_token,
        "webhook_port": 7072,
        "prefix": "",
        "allowed_numbers": []
    }

    BRIDGE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    BRIDGE_CONFIG.write_text(json.dumps(config, indent=2))

    print(f"\nConfiguration saved to {BRIDGE_CONFIG}")
    print(f"\nWebhook URL for Meta: http://YOUR_PUBLIC_IP:7072/webhook")
    print("Use a service like ngrok to expose your local server.")


def main():
    """Run the WhatsApp bridge."""
    import argparse

    parser = argparse.ArgumentParser(description="RAPP WhatsApp Bridge")
    parser.add_argument("--setup", action="store_true", help="Run interactive setup")
    parser.add_argument("--port", type=int, default=7072, help="Webhook port")
    args = parser.parse_args()

    if args.setup:
        setup_whatsapp()
        return

    # Load config
    if not BRIDGE_CONFIG.exists():
        print("WhatsApp not configured. Run with --setup first.")
        return

    from brain_stem import process_request

    # Create WhatsApp context
    create_whatsapp_context()

    # Initialize bridge
    bridge = WhatsAppBridge(webhook_port=args.port)
    bridge.set_processor(lambda **kwargs: process_request(**kwargs))

    print("=" * 50)
    print("RAPP WhatsApp Bridge")
    print("=" * 50)
    print(f"Webhook URL: http://0.0.0.0:{bridge.webhook_port}/")
    print(f"Verify Token: {bridge.verify_token}")
    print(f"Allowed numbers: {bridge.allowed_numbers or 'ALL'}")
    print("\nPress Ctrl+C to stop")
    print("=" * 50)

    try:
        bridge.start()
    except KeyboardInterrupt:
        bridge.stop()


if __name__ == "__main__":
    main()
