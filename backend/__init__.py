"""FastAPI backend for the Global Data Harmonizer platform."""

from __future__ import annotations


def version() -> str:
    from data_harmonizer import __version__

    return __version__