"""Global Data Harmonizer — pure-Python data harmonization engine.

Ingests multi-source datasets, profiles them, cleans and harmonizes
country / numeric / date / missing-value inconsistencies, resolves
duplicate conflicts, validates the result and emits machine-readable
quality reports with full transformation lineage.
"""

from data_harmonizer.config import HarmonizationConfig, default_config
from data_harmonizer.pipeline.harmonizer import Harmonizer

__all__ = [
    "HarmonizationConfig",
    "Harmonizer",
    "__version__",
    "default_config",
]

__version__ = "1.0.0"