#!/usr/bin/env python3
"""
Tests for RAPP WhatsApp Bridge

Run: pytest tests/test_whatsapp_bridge.py -v
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer
import threading
import requests
import time

# Add rapp_os to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os" / "bridges"))
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os"))


class TestWhatsAppBridgeInit:
    """Tests for WhatsAppBridge initialization."""

    def test_default_initialization(self, tmp_path):
        """Test bridge initializes with defaults."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            assert bridge.webhook_port == 7072
            assert bridge.prefix == ""
            assert bridge.allowed_numbers == []
            assert bridge.running is False

    def test_custom_initialization(self, tmp_path):
        """Test bridge with custom parameters."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(
                phone_number_id="123456",
                access_token="test_token",
                verify_token="my_verify",
                webhook_port=8080,
                prefix="/rapp",
                allowed_numbers=["+15551234567"]
            )
            assert bridge.phone_number_id == "123456"
            assert bridge.verify_token == "my_verify"
            assert bridge.webhook_port == 8080
            assert bridge.prefix == "/rapp"
            assert len(bridge.allowed_numbers) == 1


class TestAllowedNumbers:
    """Tests for phone number whitelist functionality."""

    def test_add_allowed_number(self, tmp_path):
        """Test adding a phone number to whitelist."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            bridge.add_allowed_number("555-123-4567")
            assert "+15551234567" in bridge.allowed_numbers

    def test_add_number_with_plus(self, tmp_path):
        """Test adding number that already has + prefix."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            bridge.add_allowed_number("+15551234567")
            assert "+15551234567" in bridge.allowed_numbers

    def test_is_allowed_empty_whitelist(self, tmp_path):
        """Test that empty whitelist allows all."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            assert bridge._is_allowed("+15559999999") is True

    def test_is_allowed_with_whitelist(self, tmp_path):
        """Test whitelist filtering."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(allowed_numbers=["+15551234567"])
            assert bridge._is_allowed("+15551234567") is True
            assert bridge._is_allowed("+15559999999") is False

    def test_is_allowed_partial_match(self, tmp_path):
        """Test partial number matching (last 10 digits)."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(allowed_numbers=["+15551234567"])
            # Different country code but same last 10 digits
            assert bridge._is_allowed("5551234567") is True


class TestConfigPersistence:
    """Tests for configuration save/load."""

    def test_save_config(self, tmp_path):
        """Test configuration is saved correctly."""
        from whatsapp_bridge import WhatsAppBridge

        config_path = tmp_path / "config.json"
        with patch('whatsapp_bridge.BRIDGE_CONFIG', config_path):
            bridge = WhatsAppBridge(
                phone_number_id="123",
                verify_token="verify123",
                prefix="/cmd"
            )
            bridge._save_config()

            assert config_path.exists()
            saved = json.loads(config_path.read_text())
            assert saved["phone_number_id"] == "123"
            assert saved["verify_token"] == "verify123"
            assert saved["prefix"] == "/cmd"

    def test_load_config(self, tmp_path):
        """Test configuration is loaded correctly."""
        from whatsapp_bridge import WhatsAppBridge

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "phone_number_id": "loaded_id",
            "verify_token": "loaded_verify",
            "webhook_port": 9000,
            "prefix": "/test",
            "allowed_numbers": ["+15551111111"]
        }))

        with patch('whatsapp_bridge.BRIDGE_CONFIG', config_path):
            bridge = WhatsAppBridge()
            assert bridge.phone_number_id == "loaded_id"
            assert bridge.verify_token == "loaded_verify"
            assert bridge.webhook_port == 9000
            assert bridge.prefix == "/test"
            assert "+15551111111" in bridge.allowed_numbers


class TestMessageSending:
    """Tests for sending WhatsApp messages."""

    def test_send_message_no_credentials(self, tmp_path):
        """Test send_message fails gracefully without credentials."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            result = bridge.send_message("+15551234567", "Hello")
            assert result is False

    @patch('requests.post')
    def test_send_message_success(self, mock_post, tmp_path):
        """Test successful message sending."""
        from whatsapp_bridge import WhatsAppBridge

        mock_post.return_value.status_code = 200

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(
                phone_number_id="123456",
                access_token="test_token"
            )
            result = bridge.send_message("+15551234567", "Hello")
            assert result is True
            mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_message_truncation(self, mock_post, tmp_path):
        """Test long messages are truncated."""
        from whatsapp_bridge import WhatsAppBridge

        mock_post.return_value.status_code = 200

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(
                phone_number_id="123456",
                access_token="test_token"
            )
            long_message = "x" * 5000
            bridge.send_message("+15551234567", long_message)

            # Check the message was truncated
            call_args = mock_post.call_args
            sent_body = call_args[1]["json"]["text"]["body"]
            assert len(sent_body) <= 4096
            assert sent_body.endswith("...")


class TestMessageProcessing:
    """Tests for processing incoming messages."""

    def test_process_message_blocked_number(self, tmp_path, caplog):
        """Test messages from non-whitelisted numbers are blocked."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(allowed_numbers=["+15551234567"])
            bridge._process_incoming_message("+15559999999", "Hello")
            # Should be blocked, no processing

    def test_process_message_with_prefix(self, tmp_path):
        """Test message prefix filtering."""
        from whatsapp_bridge import WhatsAppBridge

        callback_called = []

        def mock_callback(**kwargs):
            callback_called.append(kwargs)
            return {"response": "OK"}

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(prefix="/rapp")
            bridge.set_processor(mock_callback)

            # Message without prefix - should be ignored
            bridge._process_incoming_message("+15551234567", "Hello")
            assert len(callback_called) == 0

            # Message with prefix - should be processed
            with patch.object(bridge, 'send_message', return_value=True):
                bridge._process_incoming_message("+15551234567", "/rapp Hello")
            assert len(callback_called) == 1
            assert callback_called[0]["user_input"] == "Hello"

    def test_process_message_extracts_command(self, tmp_path):
        """Test command extraction from message."""
        from whatsapp_bridge import WhatsAppBridge

        received_input = []

        def mock_callback(**kwargs):
            received_input.append(kwargs.get("user_input"))
            return {"response": "OK"}

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(prefix="/cmd")
            bridge.set_processor(mock_callback)

            with patch.object(bridge, 'send_message', return_value=True):
                bridge._process_incoming_message("+15551234567", "/cmd what is the weather")

            assert received_input[0] == "what is the weather"


class TestWebhookHandler:
    """Tests for webhook HTTP handler."""

    def test_webhook_verification(self, tmp_path):
        """Test webhook verification endpoint."""
        from whatsapp_bridge import WhatsAppBridge

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge(verify_token="test_token", webhook_port=7999)

            # Start server in thread
            handler = bridge._create_webhook_handler()
            server = HTTPServer(("127.0.0.1", 7999), handler)
            thread = threading.Thread(target=server.handle_request)
            thread.start()

            time.sleep(0.1)

            # Test verification
            response = requests.get(
                "http://127.0.0.1:7999/",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": "test_token",
                    "hub.challenge": "challenge123"
                }
            )

            thread.join(timeout=2)
            assert response.status_code == 200
            assert response.text == "challenge123"


class TestUserGuidGeneration:
    """Tests for user GUID generation from phone numbers."""

    def test_user_guid_format(self, tmp_path):
        """Test user GUID is generated correctly from phone number."""
        from whatsapp_bridge import WhatsAppBridge

        received_guids = []

        def mock_callback(**kwargs):
            received_guids.append(kwargs.get("user_guid"))
            return {"response": "OK"}

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            bridge.set_processor(mock_callback)

            with patch.object(bridge, 'send_message', return_value=True):
                bridge._process_incoming_message("+15551234567", "Hello")

            assert received_guids[0] == "whatsapp_15551234567"


class TestContextGuid:
    """Tests for context GUID assignment."""

    def test_whatsapp_context_guid(self, tmp_path):
        """Test messages use 'whatsapp' context GUID."""
        from whatsapp_bridge import WhatsAppBridge

        received_context = []

        def mock_callback(**kwargs):
            received_context.append(kwargs.get("context_guid"))
            return {"response": "OK"}

        with patch('whatsapp_bridge.BRIDGE_CONFIG', tmp_path / "config.json"):
            bridge = WhatsAppBridge()
            bridge.set_processor(mock_callback)

            with patch.object(bridge, 'send_message', return_value=True):
                bridge._process_incoming_message("+15551234567", "Hello")

            assert received_context[0] == "whatsapp"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
