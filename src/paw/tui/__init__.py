"""PAW TUI — Textual-based interactive terminal UI for the PAW chat runtime.

Provides a 3-panel layout: conversation | sidebar (inspections) | input,
with token-by-token streaming of model output.
"""

from __future__ import annotations

from .app import PawTuiApp, run_tui

__all__ = ["PawTuiApp", "run_tui"]
