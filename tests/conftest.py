"""Shared pytest fixtures. No legacy Z:/ paths anywhere."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
RAW = Path(__file__).resolve().parent.parent / "raw_data"
GOLDEN = FIXTURES / "golden"


@pytest.fixture(scope="session")
def source_a_df() -> pd.DataFrame:
    return pd.read_csv(RAW / "source_world_bank.csv")


@pytest.fixture(scope="session")
def source_b_df() -> pd.DataFrame:
    return pd.read_csv(RAW / "source_un.csv")


@pytest.fixture(scope="session")
def golden_expected() -> pd.DataFrame:
    return pd.read_csv(GOLDEN / "expected_harmonized.csv")


@pytest.fixture(scope="session")
def harmonizer():
    from data_harmonizer.config import default_config
    from data_harmonizer.pipeline.harmonizer import Harmonizer

    return Harmonizer(default_config())