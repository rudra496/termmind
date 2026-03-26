"""Tests for the slash commands module."""

import os
from unittest.mock import MagicMock, patch, PropertyMock
from io import StringIO

import pytest
from rich.console import Console

from termind.commands import handle_command, cmd_help, cmd_version, cmd_quit, cmd_clear


@pytest.fixture
def mock_console():
    return Console(file=StringIO(), force_terminal=False)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.provider = "ollama"
    client.model = "llama3.2"
    client.total_tokens.return_value = 0
    client.get_cost.return_value = 0.0
    client.usage = {"prompt_tokens": 0, "completion_tokens": 0}
    return client


@pytest.fixture
def messages():
    return []


@pytest.fixture
def ctx_files():
    return []


@pytest.fixture
def tmp_cwd(tmp_path):
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir("/")


class TestCommandParsing:
    def test_handle_unknown(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        result = handle_command("unknown_command", "unknown_command", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert result is True

    def test_handle_help(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        result = handle_command("help", "help", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert result is True

    def test_handle_quit_raises(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with pytest.raises(SystemExit):
            handle_command("quit", "quit", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_handle_q_alias(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with pytest.raises(SystemExit):
            handle_command("q", "q", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_handle_exit_alias(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with pytest.raises(SystemExit):
            handle_command("exit", "exit", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)


class TestFileCommands:
    def test_cmd_files(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        handle_command("files", "files", messages, mock_client, mock_console, str(tmp_path), ctx_files)

    def test_cmd_tree(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        (tmp_path / "a.py").write_text("# a")
        handle_command("tree", "tree --depth 1", messages, mock_client, mock_console, str(tmp_path), ctx_files)

    def test_cmd_add(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("add", "add myfile.py", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert "myfile.py" in ctx_files

    def test_cmd_add_dir(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("a")
        handle_command("add", f"add --dir {tmp_path}/src", messages, mock_client, mock_console, str(tmp_path), ctx_files)
        assert len(ctx_files) > 0

    def test_cmd_remove(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        ctx_files.append("myfile.py")
        handle_command("remove", "remove myfile.py", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert "myfile.py" not in ctx_files

    def test_cmd_edit_no_args(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("edit", "edit", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)


class TestSessionCommands:
    def test_cmd_clear(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        messages.append({"role": "user", "content": "hi"})
        ctx_files.append("a.py")
        handle_command("clear", "clear", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert len(messages) == 0
        assert len(ctx_files) == 0

    def test_cmd_version(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("version", "version", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_cost(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        mock_client.total_tokens.return_value = 500
        mock_client.get_cost.return_value = 0.001
        handle_command("cost", "cost", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_status(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("status", "status", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_compact_few_messages(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        messages.append({"role": "user", "content": "hi"})
        handle_command("compact", "compact", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert len(messages) == 1  # Not enough to compact

    def test_cmd_compact_many_messages(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        for i in range(10):
            messages.append({"role": "user", "content": f"msg {i}"})
            messages.append({"role": "assistant", "content": f"resp {i}"})
        initial = len(messages)
        handle_command("compact", "compact", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
        assert len(messages) < initial


class TestProviderCommands:
    def test_cmd_model_show(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("model", "model", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_model_switch(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with patch("termind.commands.save_config"):
            handle_command("model", "model gpt-4o", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_models(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("models", "models", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_provider_show(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("provider", "provider", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_providers(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with patch("termind.commands.load_config", return_value={"provider": "ollama", "api_key": ""}):
            handle_command("providers", "providers", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_provider_switch(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with patch("termind.commands.save_config"):
            handle_command("provider", "provider ollama", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_provider_invalid(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("provider", "provider invalid_provider", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)


class TestThemeCommands:
    def test_cmd_theme_show(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        with patch("termind.commands.load_config", return_value={"theme": "dark"}):
            handle_command("theme", "theme", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_themes(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("themes", "themes", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)


class TestGitCommands:
    def test_cmd_git_no_repo(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        handle_command("git", "git status", messages, mock_client, mock_console, str(tmp_path), ctx_files)

    def test_cmd_git_in_repo(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=str(tmp_path), capture_output=True)
        (tmp_path / "a.txt").write_text("hello")
        handle_command("git", "git status", messages, mock_client, mock_console, str(tmp_path), ctx_files)


class TestSearchCommands:
    def test_cmd_search_no_args(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("search", "search", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_search(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        (tmp_path / "test.py").write_text("def hello(): pass")
        handle_command("search", "search hello", messages, mock_client, mock_console, str(tmp_path), ctx_files)

    def test_cmd_grep_no_args(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("grep", "grep", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_cmd_grep(self, tmp_path, mock_console, mock_client, messages, ctx_files):
        (tmp_path / "test.py").write_text("import os")
        handle_command("grep", "grep import", messages, mock_client, mock_console, str(tmp_path), ctx_files)


class TestRunCommand:
    def test_run_no_args(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("run", "run", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_run_command(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("run", "run echo hello", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_run_with_timeout(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("run", "run --timeout 5 echo hello", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)


class TestUndoCommands:
    def test_undo_empty(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("undo", "undo", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_undo_all_empty(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("undo", "undo --all", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)

    def test_diff_no_changes(self, mock_console, mock_client, messages, tmp_cwd, ctx_files):
        handle_command("diff", "diff", messages, mock_client, mock_console, str(tmp_cwd), ctx_files)
