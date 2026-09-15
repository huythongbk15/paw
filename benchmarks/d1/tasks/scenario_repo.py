"""
D1 — Create the disposable scenario repository.

This script generates a small, unfamiliar Python project with:
  - src/config_loader.py  — loads config from INI format
  - src/app.py            — uses the config loader
  - tests/test_app.py     — tests the app
  - config.ini            — INI-format config file

The task is to Migrate the config from INI → YAML format and update all
source code references. This is a multi-step engineering operation with
at least 3 side-effect-producing steps.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def create_scenario_repo() -> Path:
    """Create a disposable repo and return its path."""
    repo_path = Path(tempfile.mkdtemp(prefix="d1_scenario_"))

    # --- Git init ---
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "benchmark@test.local"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Benchmark"], cwd=repo_path, check=True)

    # --- config.ini (INI format, old layout) ---
    (repo_path / "config.ini").write_text(
        "[database]\n"
        "host = localhost\n"
        "port = 5432\n"
        "name = appdb\n"
        "\n"
        "[server]\n"
        "host = 0.0.0.0\n"
        "port = 8080\n"
        "debug = true\n"
        "\n"
        "[cache]\n"
        "enabled = true\n"
        "ttl = 300\n"
    )

    # --- src/config_loader.py (INI-based) ---
    (repo_path / "src").mkdir()
    (repo_path / "src" / "__init__.py").write_text("")

    (repo_path / "src" / "config_loader.py").write_text(
        '"""Config loader using INI format."""\n'
        "import configparser\n"
        "from typing import Any\n"
        "\n"
        "\n"
        "class ConfigLoader:\n"
        '    """Loads configuration from INI files."""\n\n'
        "    def __init__(self, config_path: str):\n"
        "        self.config = configparser.ConfigParser()\n"
        "        self.config.read(config_path)\n"
        "\n"
        "    def get(self, section: str, key: str) -> Any:\n"
        "        return self.config.get(section, key)\n"
        "\n"
        "    def getint(self, section: str, key: str) -> int:\n"
        "        return self.config.getint(section, key)\n"
        "\n"
        "    def getboolean(self, section: str, key: str) -> bool:\n"
        "        return self.config.getboolean(section, key)\n"
        "\n"
        "    def get_database_url(self) -> str:\n"
        "        host = self.get('database', 'host')\n"
        "        port = self.getint('database', 'port')\n"
        "        name = self.get('database', 'name')\n"
        "        return f'postgresql://{host}:{port}/{name}'\n"
        "\n"
        "    def get_server_config(self) -> dict[str, Any]:\n"
        "        return {\n"
        "            'host': self.get('server', 'host'),\n"
        "            'port': self.getint('server', 'port'),\n"
        "            'debug': self.getboolean('server', 'debug'),\n"
        "        }\n"
        "\n"
        "    def get_cache_config(self) -> dict[str, Any]:\n"
        "        return {\n"
        "            'enabled': self.getboolean('cache', 'enabled'),\n"
        "            'ttl': self.getint('cache', 'ttl'),\n"
        "        }\n"
    )

    # --- src/app.py ---
    (repo_path / "src" / "app.py").write_text(
        '"""Application that uses the config loader."""\n'
        "from src.config_loader import ConfigLoader\n"
        "from typing import Any\n"
        "\n"
        "\n"
        "class App:\n"
        '    """Simple app that reads configuration."""\n\n'
        "    def __init__(self, config_path: str):\n"
        "        self.loader = ConfigLoader(config_path)\n"
        "\n"
        "    def database_url(self) -> str:\n"
        "        return self.loader.get_database_url()\n"
        "\n"
        "    def server_settings(self) -> dict[str, Any]:\n"
        "        return self.loader.get_server_config()\n"
        "\n"
        "    def cache_settings(self) -> dict[str, Any]:\n"
        "        return self.loader.get_cache_config()\n"
    )

    # --- tests/test_app.py ---
    (repo_path / "tests").mkdir()
    (repo_path / "tests" / "__init__.py").write_text("")

    (repo_path / "tests" / "test_app.py").write_text(
        "import os\n"
        "import tempfile\n"
        "from src.app import App\n"
        "from src.config_loader import ConfigLoader\n"
        "\n"
        "\n"
        "def _write_config(content: str) -> str:\n"
        "    f = tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False)\n"
        "    f.write(content)\n"
        "    f.close()\n"
        "    return f.name\n"
        "\n"
        "\n"
        "CONFIG_CONTENT = \"\"\"[database]\n"
        "host = localhost\n"
        "port = 5432\n"
        "name = appdb\n"
        "\n"
        "[server]\n"
        "host = 0.0.0.0\n"
        "port = 8080\n"
        "debug = true\n"
        "\n"
        "[cache]\n"
        "enabled = true\n"
        "ttl = 300\n"
        "\"\"\"\n"
        "\n"
        "\n"
        "def test_database_url():\n"
        "    path = _write_config(CONFIG_CONTENT)\n"
        "    app = App(path)\n"
        "    assert app.database_url() == 'postgresql://localhost:5432/appdb'\n"
        "    os.unlink(path)\n"
        "\n"
        "\n"
        "def test_server_settings():\n"
        "    path = _write_config(CONFIG_CONTENT)\n"
        "    app = App(path)\n"
        "    settings = app.server_settings()\n"
        "    assert settings['port'] == 8080\n"
        "    assert settings['debug'] is True\n"
        "    os.unlink(path)\n"
        "\n"
        "\n"
        "def test_cache_settings():\n"
        "    path = _write_config(CONFIG_CONTENT)\n"
        "    app = App(path)\n"
        "    cache = app.cache_settings()\n"
        "    assert cache['enabled'] is True\n"
        "    assert cache['ttl'] == 300\n"
        "    os.unlink(path)\n"
    )

    # --- .gitignore ---
    (repo_path / ".gitignore").write_text("__pycache__/\n*.pyc\n.pytest_cache/\n")

    # --- Initial commit ---
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "Initial project with INI config"],
        cwd=repo_path, check=True,
    )

    return repo_path


def cleanup_scenario_repo(repo_path: Path) -> None:
    """Remove the scenario repo."""
    shutil.rmtree(repo_path, ignore_errors=True)
