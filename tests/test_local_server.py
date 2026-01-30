#!/usr/bin/env python3
"""
Tests for RAPP Local Server

Run: pytest tests/test_local_server.py -v
"""

import os
import sys
import json
import pytest
import tempfile
import threading
import time
import requests
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add rapp_os to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os"))


@pytest.fixture
def mock_brain_stem(tmp_path):
    """Create a mock brain stem for testing."""
    with patch('local_server.RAPP_HOME', tmp_path):
        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        yield


class TestRappLocalServer:
    """Tests for RappLocalServer class."""

    def test_server_initialization(self):
        """Test server initializes with correct defaults."""
        from local_server import RappLocalServer

        server = RappLocalServer()
        assert server.port == 7071
        assert server.server is None
        assert server.thread is None

    def test_server_custom_port(self):
        """Test server with custom port."""
        from local_server import RappLocalServer

        server = RappLocalServer(port=8080)
        assert server.port == 8080


class TestServerEndpoints:
    """Tests for HTTP endpoints."""

    @pytest.fixture
    def running_server(self, tmp_path):
        """Start a server for testing."""
        from local_server import RappLocalServer

        with patch('local_server.process_request') as mock_process:
            mock_process.return_value = {
                "response": "Test response",
                "voice_response": "",
                "agent_logs": [],
                "agents_used": [],
                "session_guid": "test_session",
                "context_guid": "default"
            }

            with patch('local_server.get_brain_stem') as mock_brain:
                mock_brain_instance = MagicMock()
                mock_brain_instance.agent_registry.list_agents.return_value = []
                mock_brain_instance.context_manager.list_contexts.return_value = []
                mock_brain.return_value = mock_brain_instance

                server = RappLocalServer(port=7999)
                server.start()
                time.sleep(0.2)  # Wait for server to start

                yield server, mock_process

                server.stop()

    def test_health_endpoint(self, running_server):
        """Test /health endpoint returns OK."""
        server, _ = running_server
        response = requests.get(f"http://127.0.0.1:{server.port}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "rapp-brain-stem"

    def test_agents_endpoint(self, running_server):
        """Test /agents endpoint returns agent list."""
        server, _ = running_server
        response = requests.get(f"http://127.0.0.1:{server.port}/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data

    def test_contexts_endpoint(self, running_server):
        """Test /contexts endpoint returns context list."""
        server, _ = running_server
        response = requests.get(f"http://127.0.0.1:{server.port}/contexts")
        assert response.status_code == 200
        data = response.json()
        assert "contexts" in data

    def test_reload_endpoint(self, running_server):
        """Test /reload endpoint triggers reload."""
        server, _ = running_server
        response = requests.get(f"http://127.0.0.1:{server.port}/reload")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reloaded"

    def test_not_found_endpoint(self, running_server):
        """Test unknown endpoint returns 404."""
        server, _ = running_server
        response = requests.get(f"http://127.0.0.1:{server.port}/unknown")
        assert response.status_code == 404

    def test_chat_endpoint(self, running_server):
        """Test /api/rapp chat endpoint."""
        server, mock_process = running_server
        response = requests.post(
            f"http://127.0.0.1:{server.port}/api/rapp",
            json={"user_input": "Hello"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        mock_process.assert_called()

    def test_chat_endpoint_missing_input(self, running_server):
        """Test chat endpoint requires user_input."""
        server, _ = running_server
        response = requests.post(
            f"http://127.0.0.1:{server.port}/api/rapp",
            json={}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_chat_with_message_key(self, running_server):
        """Test chat endpoint accepts 'message' as alternative key."""
        server, mock_process = running_server
        response = requests.post(
            f"http://127.0.0.1:{server.port}/api/rapp",
            json={"message": "Hello via message key"}
        )
        assert response.status_code == 200

    def test_chat_with_all_params(self, running_server):
        """Test chat endpoint with all parameters."""
        server, mock_process = running_server
        response = requests.post(
            f"http://127.0.0.1:{server.port}/api/chat",
            json={
                "user_input": "Hello",
                "user_guid": "test_user",
                "session_guid": "test_session",
                "context_guid": "test_context",
                "conversation_history": [
                    {"role": "user", "content": "Previous message"}
                ]
            }
        )
        assert response.status_code == 200

        # Verify all params were passed
        call_kwargs = mock_process.call_args[1]
        assert call_kwargs["user_input"] == "Hello"
        assert call_kwargs["user_guid"] == "test_user"
        assert call_kwargs["session_guid"] == "test_session"
        assert call_kwargs["context_guid"] == "test_context"


class TestCORS:
    """Tests for CORS headers."""

    @pytest.fixture
    def running_server(self):
        """Start a server for CORS testing."""
        from local_server import RappLocalServer

        with patch('local_server.process_request') as mock_process:
            mock_process.return_value = {
                "response": "OK",
                "voice_response": "",
                "agent_logs": [],
                "agents_used": [],
                "session_guid": "",
                "context_guid": ""
            }

            with patch('local_server.get_brain_stem') as mock_brain:
                mock_brain.return_value = MagicMock()

                server = RappLocalServer(port=7998)
                server.start()
                time.sleep(0.2)

                yield server

                server.stop()

    def test_cors_headers_present(self, running_server):
        """Test CORS headers are present in response."""
        response = requests.get(f"http://127.0.0.1:{running_server.port}/health")
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_options_preflight(self, running_server):
        """Test OPTIONS preflight request."""
        response = requests.options(f"http://127.0.0.1:{running_server.port}/api/rapp")
        assert response.status_code == 200
        assert "Access-Control-Allow-Methods" in response.headers


class TestContextCreation:
    """Tests for context creation endpoint."""

    @pytest.fixture
    def running_server(self):
        """Start a server for context testing."""
        from local_server import RappLocalServer

        with patch('local_server.get_brain_stem') as mock_brain:
            mock_context = MagicMock()
            mock_context.guid = "new_context_id"
            mock_context.name = "Test Context"

            mock_brain_instance = MagicMock()
            mock_brain_instance.context_manager.create_context.return_value = mock_context
            mock_brain.return_value = mock_brain_instance

            server = RappLocalServer(port=7997)
            server.start()
            time.sleep(0.2)

            yield server, mock_brain_instance

            server.stop()

    def test_create_context_endpoint(self, running_server):
        """Test /api/context/create endpoint."""
        server, mock_brain = running_server
        response = requests.post(
            f"http://127.0.0.1:{server.port}/api/context/create",
            json={
                "name": "Test Context",
                "agents": ["agent1"],
                "description": "Test description"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "guid" in data
        assert "name" in data


class TestInvalidJSON:
    """Tests for invalid JSON handling."""

    @pytest.fixture
    def running_server(self):
        """Start a server for JSON testing."""
        from local_server import RappLocalServer

        with patch('local_server.get_brain_stem') as mock_brain:
            mock_brain.return_value = MagicMock()

            server = RappLocalServer(port=7996)
            server.start()
            time.sleep(0.2)

            yield server

            server.stop()

    def test_invalid_json_body(self, running_server):
        """Test handling of invalid JSON in request body."""
        response = requests.post(
            f"http://127.0.0.1:{running_server.port}/api/rapp",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Invalid JSON" in data["error"]


class TestServerLifecycle:
    """Tests for server start/stop lifecycle."""

    def test_server_start_stop(self):
        """Test server can be started and stopped."""
        from local_server import RappLocalServer

        with patch('local_server.get_brain_stem') as mock_brain:
            mock_brain.return_value = MagicMock()

            server = RappLocalServer(port=7995)
            server.start()
            time.sleep(0.2)

            # Verify server is running
            try:
                response = requests.get(f"http://127.0.0.1:{server.port}/health", timeout=1)
                assert response.status_code == 200
            except requests.exceptions.ConnectionError:
                pytest.fail("Server did not start")

            # Stop server
            server.stop()
            time.sleep(0.2)

            # Verify server is stopped
            with pytest.raises(requests.exceptions.ConnectionError):
                requests.get(f"http://127.0.0.1:{server.port}/health", timeout=1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
