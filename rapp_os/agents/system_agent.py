#!/usr/bin/env python3
"""
System Agent - Local system integration for RAPP OS

Provides agents that can interact with the local computer:
- Send/receive iMessages
- Open applications
- Read/write files
- Control clipboard
- Send notifications
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add parent path for BasicAgent
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from rapp_os.core.brain_stem import RAPP_HOME
except:
    RAPP_HOME = Path.home() / ".rapp"


class BasicAgent:
    """Base agent class (inline for standalone use)."""
    def __init__(self, name, metadata):
        self.name = name
        self.metadata = metadata

    def get_function_definition(self):
        return {
            "name": self.metadata.get("name", self.name),
            "description": self.metadata.get("description", ""),
            "parameters": self.metadata.get("parameters", {"type": "object", "properties": {}})
        }


class SystemAgent(BasicAgent):
    """
    Agent for local system operations.

    macOS focused with fallbacks for other platforms.
    """

    def __init__(self):
        self.name = "System"
        self.metadata = {
            "name": self.name,
            "description": "Interact with the local computer - open apps, send notifications, manage clipboard, send iMessages",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action: 'open_app', 'notify', 'clipboard_read', 'clipboard_write', 'send_imessage', 'run_shortcut', 'get_info'",
                        "enum": ["open_app", "notify", "clipboard_read", "clipboard_write", "send_imessage", "run_shortcut", "get_info"]
                    },
                    "app_name": {"type": "string", "description": "Application name to open"},
                    "title": {"type": "string", "description": "Notification title"},
                    "message": {"type": "string", "description": "Notification message or iMessage text"},
                    "text": {"type": "string", "description": "Text for clipboard write"},
                    "recipient": {"type": "string", "description": "Phone number or email for iMessage"},
                    "shortcut_name": {"type": "string", "description": "Shortcuts app shortcut name"}
                },
                "required": ["action"]
            }
        }
        super().__init__(self.name, self.metadata)

    def perform(self, **kwargs) -> str:
        action = kwargs.get("action")

        if action == "open_app":
            return self._open_app(kwargs.get("app_name", ""))
        elif action == "notify":
            return self._send_notification(kwargs.get("title", "RAPP"), kwargs.get("message", ""))
        elif action == "clipboard_read":
            return self._clipboard_read()
        elif action == "clipboard_write":
            return self._clipboard_write(kwargs.get("text", ""))
        elif action == "send_imessage":
            return self._send_imessage(kwargs.get("recipient", ""), kwargs.get("message", ""))
        elif action == "run_shortcut":
            return self._run_shortcut(kwargs.get("shortcut_name", ""))
        elif action == "get_info":
            return self._get_system_info()
        else:
            return f"Unknown action: {action}"

    def _open_app(self, app_name: str) -> str:
        """Open an application."""
        if not app_name:
            return "Error: app_name required"

        if sys.platform == "darwin":
            try:
                subprocess.run(["open", "-a", app_name], check=True)
                return f"Opened {app_name}"
            except subprocess.CalledProcessError:
                return f"Could not open {app_name}"
        else:
            return "open_app only supported on macOS"

    def _send_notification(self, title: str, message: str) -> str:
        """Send a system notification."""
        if sys.platform == "darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
            return f"Notification sent: {title}"
        else:
            return "Notifications only supported on macOS"

    def _clipboard_read(self) -> str:
        """Read from clipboard."""
        if sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True)
            content = result.stdout[:1000]  # Limit length
            return f"Clipboard contents:\n{content}"
        else:
            return "Clipboard read only supported on macOS"

    def _clipboard_write(self, text: str) -> str:
        """Write to clipboard."""
        if not text:
            return "Error: text required"

        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return f"Copied to clipboard: {text[:50]}..."
        else:
            return "Clipboard write only supported on macOS"

    def _send_imessage(self, recipient: str, message: str) -> str:
        """Send an iMessage."""
        if not recipient or not message:
            return "Error: recipient and message required"

        if sys.platform != "darwin":
            return "iMessage only available on macOS"

        # Escape for AppleScript
        message = message.replace('"', '\\"')
        recipient = recipient.replace('"', '\\"')

        script = f'''
        tell application "Messages"
            set targetService to 1st account whose service type = iMessage
            set targetBuddy to participant "{recipient}" of targetService
            send "{message}" to targetBuddy
        end tell
        '''

        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return f"iMessage sent to {recipient}"
        except subprocess.CalledProcessError as e:
            return f"Failed to send iMessage: {e}"

    def _run_shortcut(self, name: str) -> str:
        """Run a Shortcuts app shortcut."""
        if not name:
            return "Error: shortcut_name required"

        if sys.platform != "darwin":
            return "Shortcuts only available on macOS"

        try:
            result = subprocess.run(
                ["shortcuts", "run", name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return f"Ran shortcut: {name}\nOutput: {result.stdout[:500]}"
            else:
                return f"Shortcut failed: {result.stderr}"
        except subprocess.TimeoutExpired:
            return f"Shortcut timed out: {name}"
        except Exception as e:
            return f"Error running shortcut: {e}"

    def _get_system_info(self) -> str:
        """Get basic system information."""
        info = {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "user": os.getenv("USER", "unknown"),
            "home": str(Path.home()),
            "rapp_home": str(RAPP_HOME),
            "time": datetime.now().isoformat()
        }

        if sys.platform == "darwin":
            try:
                result = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
                info["macos_version"] = result.stdout.strip()
            except:
                pass

        return json.dumps(info, indent=2)


class FileAgent(BasicAgent):
    """Agent for file system operations."""

    def __init__(self):
        self.name = "Files"
        self.metadata = {
            "name": self.name,
            "description": "Read, write, and manage files on the local system",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "exists", "delete"]
                    },
                    "path": {"type": "string", "description": "File or directory path"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["action", "path"]
            }
        }
        super().__init__(self.name, self.metadata)

    def perform(self, **kwargs) -> str:
        action = kwargs.get("action")
        path = kwargs.get("path", "")

        if not path:
            return "Error: path required"

        # Expand ~ and resolve
        path = Path(path).expanduser().resolve()

        # Security: only allow access within home directory
        home = Path.home()
        try:
            path.relative_to(home)
        except ValueError:
            return f"Error: Access denied outside home directory"

        if action == "read":
            return self._read_file(path)
        elif action == "write":
            return self._write_file(path, kwargs.get("content", ""))
        elif action == "list":
            return self._list_dir(path)
        elif action == "exists":
            return f"Exists: {path.exists()}"
        elif action == "delete":
            return self._delete_file(path)
        else:
            return f"Unknown action: {action}"

    def _read_file(self, path: Path) -> str:
        if not path.exists():
            return f"File not found: {path}"
        if not path.is_file():
            return f"Not a file: {path}"
        try:
            content = path.read_text()[:5000]  # Limit
            return f"Contents of {path.name}:\n{content}"
        except Exception as e:
            return f"Error reading file: {e}"

    def _write_file(self, path: Path, content: str) -> str:
        if not content:
            return "Error: content required"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return f"Written to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _list_dir(self, path: Path) -> str:
        if not path.exists():
            return f"Directory not found: {path}"
        if not path.is_dir():
            return f"Not a directory: {path}"
        try:
            items = list(path.iterdir())[:50]  # Limit
            listing = "\n".join(
                f"{'[DIR]' if p.is_dir() else '[FILE]'} {p.name}"
                for p in sorted(items)
            )
            return f"Contents of {path}:\n{listing}"
        except Exception as e:
            return f"Error listing directory: {e}"

    def _delete_file(self, path: Path) -> str:
        if not path.exists():
            return f"File not found: {path}"
        try:
            if path.is_file():
                path.unlink()
                return f"Deleted: {path}"
            else:
                return "Error: Can only delete files, not directories"
        except Exception as e:
            return f"Error deleting file: {e}"


# Make agents available for loading
__all__ = ["SystemAgent", "FileAgent"]
