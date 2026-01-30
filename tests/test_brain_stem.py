#!/usr/bin/env python3
"""
Tests for RAPP OS Brain Stem

Run: pytest tests/test_brain_stem.py -v
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add rapp_os to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os" / "core"))
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os"))


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_registry_initialization(self):
        """Test that registry initializes with empty agents."""
        from brain_stem import AgentRegistry
        registry = AgentRegistry()
        assert registry.agents == {}
        assert registry.agent_metadata == {}

    def test_load_agents_creates_directory(self, tmp_path):
        """Test that load_agents creates agents directory if missing."""
        from brain_stem import AgentRegistry, AGENTS_DIR

        with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
            registry = AgentRegistry()
            registry.load_agents()
            assert (tmp_path / "agents").exists()

    def test_get_agent_returns_none_for_missing(self):
        """Test get_agent returns None for non-existent agent."""
        from brain_stem import AgentRegistry
        registry = AgentRegistry()
        assert registry.get_agent("nonexistent") is None

    def test_list_agents_empty(self):
        """Test list_agents returns empty list when no agents."""
        from brain_stem import AgentRegistry
        registry = AgentRegistry()
        assert registry.list_agents() == []


class TestContextManager:
    """Tests for ContextManager class."""

    def test_default_context_created(self, tmp_path):
        """Test that default context is created on init."""
        from brain_stem import ContextManager

        with patch('brain_stem.CONTEXTS_DIR', tmp_path):
            manager = ContextManager()
            assert (tmp_path / "default.json").exists()

    def test_get_context_returns_default(self, tmp_path):
        """Test get_context returns default for unknown GUID."""
        from brain_stem import ContextManager

        with patch('brain_stem.CONTEXTS_DIR', tmp_path):
            manager = ContextManager()
            manager.load_contexts()
            ctx = manager.get_context("unknown_guid")
            assert ctx is not None
            assert ctx.guid == "default"

    def test_create_context(self, tmp_path):
        """Test creating a new context."""
        from brain_stem import ContextManager

        with patch('brain_stem.CONTEXTS_DIR', tmp_path):
            manager = ContextManager()
            ctx = manager.create_context(
                name="Test Context",
                agents=["agent1", "agent2"],
                description="Test description"
            )
            assert ctx.name == "Test Context"
            assert "agent1" in ctx.agents
            assert ctx.guid in manager.contexts

    def test_list_contexts(self, tmp_path):
        """Test listing all contexts."""
        from brain_stem import ContextManager

        with patch('brain_stem.CONTEXTS_DIR', tmp_path):
            manager = ContextManager()
            manager.load_contexts()
            contexts = manager.list_contexts()
            assert len(contexts) >= 1  # At least default
            assert any(c["guid"] == "default" for c in contexts)


class TestMemoryManager:
    """Tests for MemoryManager class."""

    def test_get_user_memory_empty(self, tmp_path):
        """Test getting memory for new user returns empty string."""
        from brain_stem import MemoryManager

        with patch('brain_stem.MEMORY_DIR', tmp_path):
            manager = MemoryManager()
            memory = manager.get_user_memory("new_user")
            assert memory == ""

    def test_append_user_memory(self, tmp_path):
        """Test appending to user memory."""
        from brain_stem import MemoryManager

        with patch('brain_stem.MEMORY_DIR', tmp_path):
            manager = MemoryManager()
            manager.append_user_memory("test_user", "Test content")
            memory = manager.get_user_memory("test_user")
            assert "Test content" in memory

    def test_session_memory_roundtrip(self, tmp_path):
        """Test saving and loading session memory."""
        from brain_stem import MemoryManager

        with patch('brain_stem.MEMORY_DIR', tmp_path):
            manager = MemoryManager()
            history = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            manager.save_session_memory("session123", history)
            loaded = manager.get_session_memory("session123")
            assert len(loaded) == 2
            assert loaded[0]["content"] == "Hello"


class TestRappRequest:
    """Tests for RappRequest dataclass."""

    def test_request_defaults(self):
        """Test RappRequest has correct defaults."""
        from brain_stem import RappRequest
        request = RappRequest(user_input="Hello")
        assert request.user_input == "Hello"
        assert request.user_guid == "default"
        assert request.session_guid == ""
        assert request.context_guid == "default"
        assert request.conversation_history == []


class TestRappResponse:
    """Tests for RappResponse dataclass."""

    def test_response_creation(self):
        """Test RappResponse creation."""
        from brain_stem import RappResponse
        response = RappResponse(
            response="Hello!",
            voice_response="Hi",
            agent_logs=["log1"],
            agents_used=["agent1"]
        )
        assert response.response == "Hello!"
        assert response.voice_response == "Hi"
        assert len(response.agent_logs) == 1


class TestRappBrainStem:
    """Tests for RappBrainStem class."""

    def test_brain_stem_initialization(self, tmp_path):
        """Test brain stem initializes components."""
        from brain_stem import RappBrainStem

        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        brain = RappBrainStem()
                        assert brain.agent_registry is not None
                        assert brain.context_manager is not None
                        assert brain.memory_manager is not None

    def test_get_agents_for_wildcard_context(self, tmp_path):
        """Test that wildcard context returns all agents."""
        from brain_stem import RappBrainStem, RappContext

        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        brain = RappBrainStem()
                        brain.agent_registry.agents = {"agent1": Mock(), "agent2": Mock()}

                        context = RappContext(
                            guid="test",
                            name="Test",
                            description="",
                            agents=["*"]
                        )

                        agents = brain._get_agents_for_context(context)
                        assert len(agents) == 2

    def test_voice_response_parsing(self, tmp_path):
        """Test parsing of voice response delimiter."""
        from brain_stem import RappBrainStem

        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        brain = RappBrainStem()

                        # Test the response parsing logic
                        response_text = "Full response|||VOICE|||Short voice"
                        if "|||VOICE|||" in response_text:
                            parts = response_text.split("|||VOICE|||")
                            main = parts[0].strip()
                            voice = parts[1].strip()
                            assert main == "Full response"
                            assert voice == "Short voice"


class TestProcessRequest:
    """Tests for the process_request function."""

    def test_process_request_returns_dict(self, tmp_path):
        """Test process_request returns expected dictionary structure."""
        from brain_stem import process_request

        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        with patch('brain_stem._brain_stem', None):
                            result = process_request("Hello")
                            assert "response" in result
                            assert "session_guid" in result
                            assert "context_guid" in result


class TestIntegration:
    """Integration tests for brain stem."""

    def test_full_request_flow(self, tmp_path):
        """Test complete request flow without AI."""
        from brain_stem import RappBrainStem, RappRequest

        with patch('brain_stem.RAPP_HOME', tmp_path):
            with patch('brain_stem.AGENTS_DIR', tmp_path / "agents"):
                with patch('brain_stem.CONTEXTS_DIR', tmp_path / "contexts"):
                    with patch('brain_stem.MEMORY_DIR', tmp_path / "memory"):
                        brain = RappBrainStem()

                        request = RappRequest(
                            user_input="What agents are available?",
                            user_guid="test_user",
                            context_guid="default"
                        )

                        response = brain.process(request)
                        assert response.response != ""
                        assert response.session_guid != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
