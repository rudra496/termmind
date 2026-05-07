"""Shared test configuration for TermMind tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def mock_config():
    with patch("termmind.api.load_config") as mc, \
         patch("termmind.api.get_provider_info") as mp:
        mc.return_value = {
            "provider": "ollama",
            "api_key": "",
            "model": "llama3.2",
            "max_tokens": 4096,
            "temperature": 0.7,
            "system_prompt": "",
        }
        mp.return_value = {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.2",
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
        }
        yield mc, mp


@pytest.fixture
def sample_python_file(tmp_dir):
    f = tmp_dir / "sample.py"
    f.write_text('''"""Sample module."""

def add(a, b):
    return a + b

class Calculator:
    def __init__(self):
        self.value = 0

    def add(self, x):
        self.value += x
        return self

    def result(self):
        return self.value
''')
    return f
