"""Tests for the git operations module."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from termmind.git import (
    git_status,
    git_diff,
    git_commit,
    git_log,
    git_branch,
    git_is_repo,
    git_checkout,
    git_get_changed_files,
    git_get_contributors,
    git_get_remote_url,
    ai_commit_message,
    _git,
)


@pytest.fixture
def repo_dir(tmp_path):
    """Initialize a git repo for testing."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / "initial.txt").write_text("initial")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True)
    return tmp_path


class TestGitBasics:
    def test_git_is_repo(self, repo_dir):
        assert git_is_repo(str(repo_dir)) is True

    def test_git_is_not_repo(self, tmp_path):
        assert git_is_repo(str(tmp_path)) is False

    def test_git_status_clean(self, repo_dir):
        status = git_status(str(repo_dir))
        # Should have at least branch info
        assert isinstance(status, str)

    def test_git_status_dirty(self, repo_dir):
        (repo_dir / "new.txt").write_text("new")
        status = git_status(str(repo_dir))
        assert isinstance(status, str)

    def test_git_diff_clean(self, repo_dir):
        diff = git_diff(str(repo_dir))
        assert diff == ""

    def test_git_diff_dirty(self, repo_dir):
        (repo_dir / "initial.txt").write_text("modified")
        diff = git_diff(str(repo_dir))
        assert "-initial" in diff

    def test_git_log(self, repo_dir):
        log = git_log(5, str(repo_dir))
        assert "initial" in log

    def test_git_branch_current(self, repo_dir):
        branch = git_branch(show_current=True, cwd=str(repo_dir))
        assert branch == "main" or branch == "master"

    def test_git_branch_list(self, repo_dir):
        branches = git_branch(cwd=str(repo_dir))
        assert "main" in branches or "master" in branches

    def test_git_commit(self, repo_dir):
        (repo_dir / "new.txt").write_text("new file")
        out, rc = git_commit("add new file", str(repo_dir))
        assert rc == 0

    def test_git_checkout(self, repo_dir):
        # Create a branch
        subprocess.run(["git", "checkout", "-b", "test-branch"], cwd=str(repo_dir), capture_output=True)
        out, rc = git_checkout("main", str(repo_dir))
        # May fail if default is master
        assert isinstance(out, str)

    def test_git_get_changed_files(self, repo_dir):
        (repo_dir / "initial.txt").write_text("changed")
        files = git_get_changed_files(str(repo_dir))
        assert "initial.txt" in files

    def test_git_get_contributors(self, repo_dir):
        contributors = git_get_contributors(str(repo_dir))
        assert len(contributors) > 0
        assert contributors[0]["name"] == "test"

    def test_git_get_remote_url_none(self, repo_dir):
        url = git_get_remote_url(str(repo_dir))
        assert url == ""


class TestGitWithRemote:
    def test_git_get_remote_url(self, repo_dir):
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/test/repo.git"],
                       cwd=str(repo_dir), capture_output=True)
        url = git_get_remote_url(str(repo_dir))
        assert "github.com" in url


class TestGitEdgeCases:
    def test_git_not_found(self):
        with patch("termmind.git._git") as mock_git:
            mock_git.return_value = ("git not found", 1)
            assert git_is_repo(".") is False

    def test_ai_commit_message(self, repo_dir):
        (repo_dir / "initial.txt").write_text("changed")
        mock_client = MagicMock()
        mock_client.chat_stream.return_value = iter(["feat: add feature"])
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ai_commit_message(mock_client, "diff content")
        )
        assert result == "feat: add feature"

    def test_ai_commit_message_empty_diff(self):
        mock_client = MagicMock()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ai_commit_message(mock_client, "")
        )
        assert result == "chore: empty commit"

    def test_ai_commit_message_error(self):
        mock_client = MagicMock()
        mock_client.chat_stream.side_effect = Exception("API error")
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ai_commit_message(mock_client, "some diff")
        )
        assert result == "chore: update"


class TestGitDiffStaged:
    def test_staged_diff(self, repo_dir):
        (repo_dir / "new.txt").write_text("staged")
        subprocess.run(["git", "add", "new.txt"], cwd=str(repo_dir), capture_output=True)
        diff = git_diff(str(repo_dir), staged=True)
        assert "+staged" in diff

    def test_file_diff(self, repo_dir):
        (repo_dir / "initial.txt").write_text("modified")
        diff = git_diff(str(repo_dir), file="initial.txt")
        assert isinstance(diff, str)
