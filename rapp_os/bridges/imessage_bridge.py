#!/usr/bin/env python3
"""
RAPP iMessage Bridge - Connect RAPP to iMessage

Allows controlling RAPP via natural language text messages.
Monitors iMessage database for incoming messages and routes to brain stem.

macOS only - requires Full Disk Access permission.

Architecture:
    iMessage → SQLite Monitor → Brain Stem → AppleScript → iMessage Reply
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable
import logging

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("imessage_bridge")

# iMessage database path
IMESSAGE_DB = Path.home() / "Library/Messages/chat.db"

# Configuration
RAPP_HOME = Path.home() / ".rapp"
BRIDGE_CONFIG = RAPP_HOME / "imessage_bridge.json"


class iMessageBridge:
    """
    Bridge between iMessage and RAPP Brain Stem.

    Monitors incoming messages and routes commands to RAPP.
    """

    def __init__(self, allowed_numbers: List[str] = None, prefix: str = "/rapp"):
        """
        Initialize the bridge.

        Args:
            allowed_numbers: Phone numbers allowed to send commands (whitelist)
            prefix: Command prefix (e.g., "/rapp help")
        """
        self.allowed_numbers = allowed_numbers or []
        self.prefix = prefix
        self.running = False
        self.last_message_id = 0
        self.process_callback: Optional[Callable] = None

        # Load config
        self._load_config()

    def _load_config(self):
        """Load configuration from disk."""
        if BRIDGE_CONFIG.exists():
            try:
                config = json.loads(BRIDGE_CONFIG.read_text())
                self.allowed_numbers = config.get("allowed_numbers", self.allowed_numbers)
                self.prefix = config.get("prefix", self.prefix)
                self.last_message_id = config.get("last_message_id", 0)
            except:
                pass

    def _save_config(self):
        """Save configuration to disk."""
        BRIDGE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        BRIDGE_CONFIG.write_text(json.dumps({
            "allowed_numbers": self.allowed_numbers,
            "prefix": self.prefix,
            "last_message_id": self.last_message_id
        }, indent=2))

    def add_allowed_number(self, number: str):
        """Add a phone number to the whitelist."""
        # Normalize number
        number = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not number.startswith("+"):
            number = "+1" + number  # Assume US

        if number not in self.allowed_numbers:
            self.allowed_numbers.append(number)
            self._save_config()
            logger.info(f"Added allowed number: {number}")

    def remove_allowed_number(self, number: str):
        """Remove a phone number from the whitelist."""
        number = number.replace(" ", "").replace("-", "")
        if number in self.allowed_numbers:
            self.allowed_numbers.remove(number)
            self._save_config()

    def _check_permissions(self) -> bool:
        """Check if we have permission to read iMessage database."""
        if not IMESSAGE_DB.exists():
            logger.error("iMessage database not found")
            return False

        try:
            conn = sqlite3.connect(f"file:{IMESSAGE_DB}?mode=ro", uri=True)
            conn.execute("SELECT 1 FROM message LIMIT 1")
            conn.close()
            return True
        except sqlite3.OperationalError as e:
            logger.error(f"Cannot access iMessage database: {e}")
            logger.error("Grant Full Disk Access to Terminal/Python in System Preferences > Privacy & Security")
            return False

    def _get_new_messages(self) -> List[Dict]:
        """Get new messages since last check."""
        messages = []

        try:
            conn = sqlite3.connect(f"file:{IMESSAGE_DB}?mode=ro", uri=True)
            cursor = conn.cursor()

            # Query for new messages
            query = """
                SELECT
                    m.ROWID,
                    m.text,
                    m.is_from_me,
                    m.date,
                    h.id as handle_id,
                    h.service
                FROM message m
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                WHERE m.ROWID > ?
                    AND m.is_from_me = 0
                    AND m.text IS NOT NULL
                ORDER BY m.ROWID ASC
                LIMIT 100
            """

            cursor.execute(query, (self.last_message_id,))
            rows = cursor.fetchall()

            for row in rows:
                msg_id, text, is_from_me, date, handle_id, service = row

                # Update last message ID
                if msg_id > self.last_message_id:
                    self.last_message_id = msg_id

                messages.append({
                    "id": msg_id,
                    "text": text,
                    "from": handle_id,
                    "service": service,
                    "date": date
                })

            conn.close()

        except Exception as e:
            logger.error(f"Error reading messages: {e}")

        return messages

    def _send_imessage(self, to: str, message: str) -> bool:
        """Send an iMessage via AppleScript."""
        # Escape quotes in message
        message = message.replace('"', '\\"').replace("'", "\\'")

        script = f'''
        tell application "Messages"
            set targetService to 1st account whose service type = iMessage
            set targetBuddy to participant "{to}" of targetService
            send "{message}" to targetBuddy
        end tell
        '''

        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=10
            )
            logger.info(f"Sent message to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    def _is_allowed(self, sender: str) -> bool:
        """Check if sender is in whitelist."""
        if not self.allowed_numbers:
            return True  # No whitelist = allow all

        # Normalize and check
        sender_normalized = sender.replace(" ", "").replace("-", "")
        for allowed in self.allowed_numbers:
            allowed_normalized = allowed.replace(" ", "").replace("-", "")
            if sender_normalized.endswith(allowed_normalized[-10:]):
                return True
        return False

    def _process_message(self, message: Dict):
        """Process an incoming message."""
        text = message.get("text", "").strip()
        sender = message.get("from", "")

        # Check whitelist
        if not self._is_allowed(sender):
            logger.warning(f"Blocked message from {sender}")
            return

        # Check for command prefix
        if self.prefix:
            if text.lower().startswith(self.prefix.lower()):
                text = text[len(self.prefix):].strip()
            else:
                return  # Not a command

        logger.info(f"Processing command from {sender}: {text[:50]}...")

        # Route to brain stem
        if self.process_callback:
            try:
                response = self.process_callback(
                    user_input=text,
                    user_guid=f"imessage_{sender.replace('+', '')}",
                    context_guid="imessage"
                )

                # Send response
                reply = response.get("response", "Sorry, I couldn't process that.")

                # Truncate if too long for SMS
                if len(reply) > 1500:
                    reply = reply[:1500] + "... (truncated)"

                self._send_imessage(sender, reply)

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                self._send_imessage(sender, f"Error: {str(e)[:100]}")

    def set_processor(self, callback: Callable):
        """Set the callback for processing messages."""
        self.process_callback = callback

    def start(self):
        """Start monitoring for messages."""
        if not self._check_permissions():
            return False

        self.running = True
        self._save_config()

        logger.info(f"iMessage bridge started (prefix: {self.prefix})")
        logger.info(f"Allowed numbers: {self.allowed_numbers or 'ALL'}")

        # Monitoring loop
        while self.running:
            try:
                messages = self._get_new_messages()
                for msg in messages:
                    self._process_message(msg)
                    self._save_config()

                time.sleep(2)  # Check every 2 seconds

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)

        return True

    def stop(self):
        """Stop monitoring."""
        self.running = False
        self._save_config()


def create_imessage_context():
    """Create an iMessage-specific context in RAPP."""
    from brain_stem import get_brain_stem

    brain = get_brain_stem()

    # Check if context exists
    if "imessage" not in brain.context_manager.contexts:
        brain.context_manager.create_context(
            name="iMessage",
            agents=["*"],
            skills=["*"],
            description="Context for iMessage commands",
            system_prompt="""You are RAPP, responding via iMessage.
Keep responses concise (under 500 chars when possible).
Be helpful and friendly. The user is texting you commands.
Available commands are handled by your agents."""
        )
        # Manually set the GUID to "imessage"
        ctx = brain.context_manager.contexts.pop(list(brain.context_manager.contexts.keys())[-1])
        ctx.guid = "imessage"
        brain.context_manager.contexts["imessage"] = ctx


def main():
    """Run the iMessage bridge."""
    from brain_stem import process_request

    # Create iMessage context
    create_imessage_context()

    # Initialize bridge
    bridge = iMessageBridge(
        prefix="/rapp"  # Messages must start with /rapp
    )

    # Set processor
    bridge.set_processor(lambda **kwargs: process_request(**kwargs))

    print("=" * 50)
    print("RAPP iMessage Bridge")
    print("=" * 50)
    print(f"Prefix: {bridge.prefix}")
    print(f"Allowed numbers: {bridge.allowed_numbers or 'ALL (no whitelist)'}")
    print("\nTo add allowed number:")
    print("  Edit ~/.rapp/imessage_bridge.json")
    print("\nPress Ctrl+C to stop")
    print("=" * 50)

    # Start monitoring
    bridge.start()


if __name__ == "__main__":
    main()
