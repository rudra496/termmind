"""Tests for the API client module."""

from unittest.mock import MagicMock, patch

import pytest

from termmind.api import APIClient, APIError


@pytest.fixture
def mock_config():
    with patch("termmind.api.load_config") as mc, patch("termmind.api.get_provider_info") as mp, patch("termmind.api.get_provider") as m_gp:
        mc.return_value = {
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-4o-mini",
            "max_tokens": 4096,
            "temperature": 0.7,
        }
        mp.return_value = {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
            "cost_per_1k_input": 0.00015,
            "cost_per_1k_output": 0.0006,
        }

        mock_provider_instance = MagicMock()
        mock_provider_instance.estimate_cost.return_value = 0.00045
        m_gp.return_value = mock_provider_instance

        yield mc, mp, m_gp, mock_provider_instance


class TestAPIClient:
    def test_init_defaults(self, mock_config):
        client = APIClient()
        assert client.provider_name == "openai"
        assert client.api_key == "test-key"
        assert client.model == "gpt-4o-mini"
        assert client.max_tokens == 4096
        assert client.temperature == 0.7
        assert client.usage == {"prompt_tokens": 0, "completion_tokens": 0}

    def test_init_with_overrides(self, mock_config):
        client = APIClient(
            provider="ollama", api_key="", model="llama3.2", max_tokens=2048, temperature=0.5
        )
        assert client.provider_name == "ollama"
        assert client.api_key == ""
        assert client.model == "llama3.2"
        assert client.max_tokens == 2048
        assert client.temperature == 0.5

    def test_build_messages_with_system_prompt(self, mock_config):
        mock_config[0].return_value["system_prompt"] = "You are helpful."
        client = APIClient()
        msgs = client._build_messages(
            [{"role": "user", "content": "hi"}], system_prompt="Be brief."
        )
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Be brief."
        assert len(msgs) == 2

    def test_build_messages_without_system(self, mock_config):
        mock_config[0].return_value["system_prompt"] = ""
        client = APIClient()
        msgs = client._build_messages([{"role": "user", "content": "hi"}])
        assert all(m["role"] != "system" for m in msgs)

    def test_estimate_tokens(self, mock_config):
        client = APIClient()
        assert client._estimate_tokens("hello world") == len("hello world") // 4
        assert client._estimate_tokens("") == 0

    def test_total_tokens(self, mock_config):
        client = APIClient()
        client.usage = {"prompt_tokens": 100, "completion_tokens": 50}
        assert client.total_tokens() == 150

    def test_get_cost(self, mock_config):
        client = APIClient()
        client.usage = {"prompt_tokens": 1000, "completion_tokens": 500}
        cost = client.get_cost()
        assert abs(cost - 0.00045) < 1e-10

    def test_chat_success(self, mock_config):
        _, _, _, mock_provider = mock_config
        mock_provider.send_message.return_value = (chunk for chunk in ["Hello! This is a longer string so tokens > 0."])

        client = APIClient()
        result = client.chat([{"role": "user", "content": "hello world! this is a long prompt to ensure tokens > 0"}])

        assert result == "Hello! This is a longer string so tokens > 0."
        assert client.usage["completion_tokens"] > 0
        assert client.usage["prompt_tokens"] > 0

    def test_chat_api_error(self, mock_config):
        _, _, _, mock_provider = mock_config
        mock_provider.send_message.side_effect = Exception("API error 401: Unauthorized")

        client = APIClient()
        with pytest.raises(APIError, match="401"):
            client.chat([{"role": "user", "content": "hi"}])

    def test_chat_stream_success(self, mock_config):
        _, _, _, mock_provider = mock_config
        mock_provider.send_message.return_value = (chunk for chunk in ["Hello ", "world this is longer."])

        client = APIClient()
        result = list(client.chat_stream([{"role": "user", "content": "hello world! this is a long prompt to ensure tokens > 0"}]))

        assert result == ["Hello ", "world this is longer."]
        assert client.usage["completion_tokens"] > 0
        assert client.usage["prompt_tokens"] > 0

    def test_chat_stream_error(self, mock_config):
        _, _, _, mock_provider = mock_config
        mock_provider.send_message.side_effect = Exception("API error 500: Server error")

        client = APIClient()
        with pytest.raises(APIError, match="500"):
            list(client.chat_stream([{"role": "user", "content": "hi"}]))

    def test_chat_empty_response(self, mock_config):
        _, _, _, mock_provider = mock_config
        mock_provider.send_message.return_value = (chunk for chunk in ["   "])

        client = APIClient()
        result = client.chat([{"role": "user", "content": "hi"}])
        assert result == ""

