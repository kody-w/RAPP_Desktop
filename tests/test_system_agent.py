#!/usr/bin/env python3
"""
Tests for RAPP System and File Agents

Run: pytest tests/test_system_agent.py -v
"""

import os
import sys
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Add rapp_os to path
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os" / "agents"))
sys.path.insert(0, str(Path(__file__).parent.parent / "rapp_os"))


class TestSystemAgent:
    """Tests for SystemAgent class."""

    def test_agent_initialization(self):
        """Test SystemAgent initializes correctly."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        assert agent.name == "System"
        assert "description" in agent.metadata
        assert "parameters" in agent.metadata

    def test_function_definition(self):
        """Test get_function_definition returns valid schema."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        func_def = agent.get_function_definition()

        assert func_def["name"] == "System"
        assert "description" in func_def
        assert "parameters" in func_def
        assert func_def["parameters"]["type"] == "object"

    def test_unknown_action(self):
        """Test handling of unknown action."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        result = agent.perform(action="unknown_action")
        assert "Unknown action" in result

    @patch('subprocess.run')
    def test_open_app_macos(self, mock_run):
        """Test opening an application on macOS."""
        from system_agent import SystemAgent

        mock_run.return_value = MagicMock(returncode=0)

        with patch('sys.platform', 'darwin'):
            agent = SystemAgent()
            result = agent.perform(action="open_app", app_name="Safari")

            mock_run.assert_called_with(["open", "-a", "Safari"], check=True)
            assert "Opened Safari" in result

    def test_open_app_missing_name(self):
        """Test open_app requires app_name."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        result = agent.perform(action="open_app")
        assert "Error" in result
        assert "app_name required" in result

    @patch('subprocess.run')
    def test_send_notification_macos(self, mock_run):
        """Test sending notification on macOS."""
        from system_agent import SystemAgent

        with patch('sys.platform', 'darwin'):
            agent = SystemAgent()
            result = agent.perform(
                action="notify",
                title="Test Title",
                message="Test message"
            )

            mock_run.assert_called_once()
            assert "Notification sent" in result

    @patch('subprocess.run')
    def test_clipboard_read_macos(self, mock_run):
        """Test reading clipboard on macOS."""
        from system_agent import SystemAgent

        mock_run.return_value = MagicMock(stdout="Clipboard content")

        with patch('sys.platform', 'darwin'):
            agent = SystemAgent()
            result = agent.perform(action="clipboard_read")

            mock_run.assert_called_with(["pbpaste"], capture_output=True, text=True)
            assert "Clipboard content" in result

    @patch('subprocess.run')
    def test_clipboard_write_macos(self, mock_run):
        """Test writing to clipboard on macOS."""
        from system_agent import SystemAgent

        with patch('sys.platform', 'darwin'):
            agent = SystemAgent()
            result = agent.perform(action="clipboard_write", text="Copy this")

            mock_run.assert_called_once()
            assert "Copied to clipboard" in result

    def test_clipboard_write_missing_text(self):
        """Test clipboard_write requires text."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        result = agent.perform(action="clipboard_write")
        assert "Error" in result
        assert "text required" in result

    def test_send_imessage_missing_params(self):
        """Test send_imessage requires recipient and message."""
        from system_agent import SystemAgent

        agent = SystemAgent()

        result = agent.perform(action="send_imessage")
        assert "Error" in result

        result = agent.perform(action="send_imessage", recipient="+15551234567")
        assert "Error" in result

    @patch('subprocess.run')
    def test_run_shortcut_macos(self, mock_run):
        """Test running a Shortcuts app shortcut."""
        from system_agent import SystemAgent

        mock_run.return_value = MagicMock(returncode=0, stdout="Success")

        with patch('sys.platform', 'darwin'):
            agent = SystemAgent()
            result = agent.perform(action="run_shortcut", shortcut_name="My Shortcut")

            mock_run.assert_called_once()
            assert "Ran shortcut" in result

    def test_run_shortcut_missing_name(self):
        """Test run_shortcut requires shortcut_name."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        result = agent.perform(action="run_shortcut")
        assert "Error" in result
        assert "shortcut_name required" in result

    def test_get_system_info(self):
        """Test getting system information."""
        from system_agent import SystemAgent

        agent = SystemAgent()
        result = agent.perform(action="get_info")

        # Result should be valid JSON
        info = json.loads(result)
        assert "platform" in info
        assert "python" in info
        assert "user" in info
        assert "home" in info


class TestFileAgent:
    """Tests for FileAgent class."""

    def test_agent_initialization(self):
        """Test FileAgent initializes correctly."""
        from system_agent import FileAgent

        agent = FileAgent()
        assert agent.name == "Files"
        assert "description" in agent.metadata

    def test_function_definition(self):
        """Test get_function_definition returns valid schema."""
        from system_agent import FileAgent

        agent = FileAgent()
        func_def = agent.get_function_definition()

        assert func_def["name"] == "Files"
        assert "parameters" in func_def

    def test_path_required(self):
        """Test that path is required for all actions."""
        from system_agent import FileAgent

        agent = FileAgent()
        result = agent.perform(action="read")
        assert "Error" in result
        assert "path required" in result

    def test_security_outside_home(self):
        """Test that access outside home directory is denied."""
        from system_agent import FileAgent

        agent = FileAgent()
        result = agent.perform(action="read", path="/etc/passwd")
        assert "Error" in result
        assert "Access denied" in result

    def test_read_file(self, tmp_path):
        """Test reading a file."""
        from system_agent import FileAgent

        # Create test file in home directory subdirectory
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(action="read", path=str(test_file))
            assert "Test content" in result

    def test_read_nonexistent_file(self, tmp_path):
        """Test reading a file that doesn't exist."""
        from system_agent import FileAgent

        with patch.object(Path, 'home', return_value=tmp_path):
            agent = FileAgent()
            result = agent.perform(action="read", path=str(tmp_path / "nonexistent.txt"))
            assert "not found" in result.lower()

    def test_write_file(self, tmp_path):
        """Test writing a file."""
        from system_agent import FileAgent

        test_file = tmp_path / "new_file.txt"

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(
                action="write",
                path=str(test_file),
                content="New content"
            )

            assert "Written to" in result
            assert test_file.read_text() == "New content"

    def test_write_file_missing_content(self, tmp_path):
        """Test write requires content."""
        from system_agent import FileAgent

        with patch.object(Path, 'home', return_value=tmp_path):
            agent = FileAgent()
            result = agent.perform(action="write", path=str(tmp_path / "file.txt"))
            assert "Error" in result
            assert "content required" in result

    def test_list_directory(self, tmp_path):
        """Test listing a directory."""
        from system_agent import FileAgent

        # Create some files
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "subdir").mkdir()

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(action="list", path=str(tmp_path))

            assert "[FILE]" in result
            assert "[DIR]" in result
            assert "file1.txt" in result
            assert "subdir" in result

    def test_exists_true(self, tmp_path):
        """Test exists returns true for existing file."""
        from system_agent import FileAgent

        test_file = tmp_path / "exists.txt"
        test_file.touch()

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(action="exists", path=str(test_file))
            assert "True" in result

    def test_exists_false(self, tmp_path):
        """Test exists returns false for non-existing file."""
        from system_agent import FileAgent

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(
                action="exists",
                path=str(tmp_path / "nonexistent.txt")
            )
            assert "False" in result

    def test_delete_file(self, tmp_path):
        """Test deleting a file."""
        from system_agent import FileAgent

        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("Delete me")

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(action="delete", path=str(test_file))

            assert "Deleted" in result
            assert not test_file.exists()

    def test_delete_directory_fails(self, tmp_path):
        """Test that deleting directories is not allowed."""
        from system_agent import FileAgent

        test_dir = tmp_path / "dir_to_delete"
        test_dir.mkdir()

        with patch.object(Path, 'home', return_value=tmp_path.parent):
            agent = FileAgent()
            result = agent.perform(action="delete", path=str(test_dir))

            assert "Error" in result
            assert test_dir.exists()

    def test_unknown_action(self, tmp_path):
        """Test handling of unknown action."""
        from system_agent import FileAgent

        with patch.object(Path, 'home', return_value=tmp_path):
            agent = FileAgent()
            result = agent.perform(action="unknown", path=str(tmp_path))
            assert "Unknown action" in result


class TestBasicAgent:
    """Tests for BasicAgent base class."""

    def test_basic_agent_function_definition(self):
        """Test BasicAgent generates function definition."""
        from system_agent import BasicAgent

        agent = BasicAgent("TestAgent", {
            "name": "TestAgent",
            "description": "Test description",
            "parameters": {"type": "object", "properties": {}}
        })

        func_def = agent.get_function_definition()
        assert func_def["name"] == "TestAgent"
        assert func_def["description"] == "Test description"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
