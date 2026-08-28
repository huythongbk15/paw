"""
Phase 0 Tests — Foundation verification
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.parent


class TestPhase0Foundation:
    """Verify Phase 0 acceptance criteria."""

    def test_paw_help(self):
        """paw --help must work."""
        result = subprocess.run(
            [sys.executable, "-m", "paw", "--help"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            check=False,
        )
        assert result.returncode == 0
        assert "PAW" in result.stdout
        assert "Personal Agent Workstation" in result.stdout

    def test_paw_version(self):
        """paw --version must work."""
        result = subprocess.run(
            [sys.executable, "-m", "paw", "--version"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            check=False,
        )
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_paw_doctor_before_init(self, tmp_path):
        """paw doctor should report not initialized before init."""
        env = os.environ.copy()
        env["PAW_PAW_HOME"] = str(tmp_path / ".paw")

        result = subprocess.run(
            [sys.executable, "-m", "paw", "doctor"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )
        # Doctor returns 1 when not initialized
        assert result.returncode == 1
        assert "NOT INITIALIZED" in result.stdout or "MISSING" in result.stdout

    def test_paw_init(self, tmp_path):
        """paw init should create database and directories."""
        env = os.environ.copy()
        env["PAW_PAW_HOME"] = str(tmp_path / ".paw")

        result = subprocess.run(
            [sys.executable, "-m", "paw", "init"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert "initialized successfully" in result.stdout

        # Verify directories created
        paw_home = tmp_path / ".paw"
        assert paw_home.exists()
        assert (paw_home / "skills").exists()
        assert (paw_home / "knowledge").exists()
        assert (paw_home / "artifacts").exists()
        assert (paw_home / "cache").exists()
        assert (paw_home / "logs").exists()

        # Verify database created
        db_path = paw_home / "paw.db"
        assert db_path.exists()

    def test_paw_doctor_after_init(self, tmp_path):
        """paw doctor should pass after init."""
        env = os.environ.copy()
        env["PAW_PAW_HOME"] = str(tmp_path / ".paw")

        # First init
        subprocess.run(
            [sys.executable, "-m", "paw", "init"],
            capture_output=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )

        # Then doctor
        result = subprocess.run(
            [sys.executable, "-m", "paw", "doctor"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert "All checks passed" in result.stdout

    def test_paw_config(self, tmp_path):
        """paw config should show configuration."""
        env = os.environ.copy()
        env["PAW_PAW_HOME"] = str(tmp_path / ".paw")

        subprocess.run(
            [sys.executable, "-m", "paw", "init"],
            capture_output=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )

        result = subprocess.run(
            [sys.executable, "-m", "paw", "config"],
            capture_output=True,
            text=True,
            cwd=WORKSPACE_ROOT,
            env=env,
            check=False,
        )
        assert result.returncode == 0
        assert "PAW Configuration" in result.stdout
        assert "Database" in result.stdout
        assert "Skills Dir" in result.stdout


class TestNoProhibitedDependencies:
    """Verify no prohibited dependencies in runtime code."""

    def test_no_qwenpaw_import(self):
        """No QwenPaw imports in paw/ package."""
        paw_dir = Path(__file__).parent.parent / "paw"
        for py_file in paw_dir.rglob("*.py"):
            content = py_file.read_text()
            # Allow in tests and docs
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            assert "qwenpaw" not in content.lower(), f"QwenPaw reference in {py_file}"

    def test_no_deepseek_harness_import(self):
        """No DeepSeek Harness imports in paw/ package."""
        paw_dir = Path(__file__).parent.parent / "paw"
        for py_file in paw_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "deepseek" not in content.lower() or "model" in content.lower(), \
                f"DeepSeek reference in {py_file}"

    def test_no_notebooklm_import(self):
        """No NotebookLM imports in paw/ package."""
        paw_dir = Path(__file__).parent.parent / "paw"
        for py_file in paw_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "notebooklm" not in content.lower(), f"NotebookLM reference in {py_file}"

    def test_no_antigravity_import(self):
        """No Antigravity imports in paw/ package."""
        paw_dir = Path(__file__).parent.parent / "paw"
        for py_file in paw_dir.rglob("*.py"):
            if "test_" in py_file.name or "__pycache__" in str(py_file):
                continue
            content = py_file.read_text()
            assert "antigravity" not in content.lower(), f"Antigravity reference in {py_file}"
