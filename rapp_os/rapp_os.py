#!/usr/bin/env python3
"""
RAPP OS - Main Entry Point

Unified local AI operating system that:
1. Runs the brain stem (single endpoint, GUID routing)
2. Manages system bridges (iMessage, etc.)
3. Provides local API for RAPP Desktop
"""

import os
import sys
import json
import signal
import threading
import argparse
from pathlib import Path
from typing import Optional

# Add paths
RAPP_OS_DIR = Path(__file__).parent
sys.path.insert(0, str(RAPP_OS_DIR / "core"))
sys.path.insert(0, str(RAPP_OS_DIR / "bridges"))

from core.brain_stem import get_brain_stem, process_request, RappBrainStem
from core.local_server import RappLocalServer

# Optional bridges
try:
    from bridges.imessage_bridge import iMessageBridge, create_imessage_context
    HAS_IMESSAGE = sys.platform == "darwin"
except ImportError:
    HAS_IMESSAGE = False

RAPP_HOME = Path.home() / ".rapp"
CONFIG_FILE = RAPP_HOME / "rapp_os.json"


class RappOS:
    """
    RAPP Operating System - Local AI Integration Layer

    Manages:
    - Brain Stem (unified agent endpoint)
    - Local HTTP Server
    - System Bridges (iMessage, etc.)
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or self._load_config()

        # Components
        self.brain_stem: Optional[RappBrainStem] = None
        self.local_server: Optional[RappLocalServer] = None
        self.imessage_bridge: Optional[iMessageBridge] = None

        # State
        self.running = False
        self.threads = []

    def _load_config(self) -> dict:
        """Load configuration."""
        default_config = {
            "server": {
                "enabled": True,
                "port": 7071
            },
            "imessage": {
                "enabled": False,
                "prefix": "/rapp",
                "allowed_numbers": []
            }
        }

        if CONFIG_FILE.exists():
            try:
                loaded = json.loads(CONFIG_FILE.read_text())
                # Merge with defaults
                for key in default_config:
                    if key in loaded:
                        default_config[key].update(loaded[key])
                return default_config
            except:
                pass

        return default_config

    def _save_config(self):
        """Save configuration."""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.config, indent=2))

    def initialize(self):
        """Initialize all components."""
        print("Initializing RAPP OS...")

        # Initialize brain stem
        self.brain_stem = get_brain_stem()
        print(f"  Brain Stem: {len(self.brain_stem.agent_registry.agents)} agents loaded")
        print(f"  Contexts: {len(self.brain_stem.context_manager.contexts)} contexts")

        # Initialize local server
        if self.config["server"]["enabled"]:
            port = self.config["server"]["port"]
            self.local_server = RappLocalServer(port=port)
            print(f"  Local Server: port {port}")

        # Initialize iMessage bridge
        if HAS_IMESSAGE and self.config["imessage"]["enabled"]:
            create_imessage_context()
            self.imessage_bridge = iMessageBridge(
                prefix=self.config["imessage"]["prefix"],
                allowed_numbers=self.config["imessage"]["allowed_numbers"]
            )
            self.imessage_bridge.set_processor(
                lambda **kwargs: process_request(**kwargs)
            )
            print(f"  iMessage Bridge: enabled (prefix: {self.config['imessage']['prefix']})")

    def start(self):
        """Start all services."""
        self.running = True

        # Start local server
        if self.local_server:
            self.local_server.start()

        # Start iMessage bridge in background thread
        if self.imessage_bridge:
            t = threading.Thread(target=self.imessage_bridge.start, daemon=True)
            t.start()
            self.threads.append(t)

        self._save_config()

    def stop(self):
        """Stop all services."""
        self.running = False

        if self.local_server:
            self.local_server.stop()

        if self.imessage_bridge:
            self.imessage_bridge.stop()

    def run(self):
        """Run RAPP OS (blocking)."""
        self.initialize()
        self.start()

        print("\n" + "=" * 50)
        print("RAPP OS Running")
        print("=" * 50)
        print(f"API: http://127.0.0.1:{self.config['server']['port']}/api/rapp")
        print("Press Ctrl+C to stop")
        print("=" * 50 + "\n")

        # Handle shutdown
        def signal_handler(sig, frame):
            print("\nShutting down RAPP OS...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep alive
        while self.running:
            try:
                threading.Event().wait(1)
            except KeyboardInterrupt:
                break

        self.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RAPP OS - Local AI Operating System")
    parser.add_argument("--port", type=int, default=7071, help="Server port")
    parser.add_argument("--imessage", action="store_true", help="Enable iMessage bridge")
    parser.add_argument("--no-server", action="store_true", help="Disable HTTP server")

    args = parser.parse_args()

    config = {
        "server": {
            "enabled": not args.no_server,
            "port": args.port
        },
        "imessage": {
            "enabled": args.imessage,
            "prefix": "/rapp",
            "allowed_numbers": []
        }
    }

    rapp_os = RappOS(config)
    rapp_os.run()


if __name__ == "__main__":
    main()
