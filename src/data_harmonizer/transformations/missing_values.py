"""Missing-value handling.

Missing values are preserved as NULL unless an explicit, configurable
imputation policy is enabled. Whenever an imputation IS applied, a
MISSING_VALUE lineage record is created so the user can always see which
values were inferred rather than observed.
"""

from __future__ import annotations

import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import TransformationRecord, TransformationType

logger = get_logger(__name__)


def impute_column(
    series: pd.Series,
    policy: str = "none",
    fill_value: float | None = None,
    source_dataset: str = "",
    source_column: str = "",
    records: list[TransformationRecord] | None = None,
) -> tuple[pd.Series, list[TransformationRecord]]:
    """Apply a missing-value policy to a single numeric column.

    Policies:
      - "none":        leave missing values untouched (default)
      - "constant":    fill with ``fill_value``
      - "column_mean": fill with the column mean

    Every imputed cell produces a MISSING_VALUE lineage record.
    """
    records = records if records is not None else []
    missing_mask = series.isna()
    if not missing_mask.any() or policy == "none":
        return series, records

    filled = series.copy()
    if policy == "constant" and fill_value is not None:
        values = [fill_value] * int(missing_mask.sum())
    elif policy == "column_mean":
        mean = series.mean()
        if pd.isna(mean):
            return series, records
        values = [mean] * int(missing_mask.sum())
    else:
        return series, records

    filled.loc[missing_mask] = values
    for idx in series.index[missing_mask]:
        records.append(
            TransformationRecord(
                source_dataset=source_dataset,
                source_column=source_column,
                row_index=int(idx),
                original_value=None,
                transformed_value=values[0],
                transformation_type=TransformationType.MISSING_VALUE,
                reason=f"Missing value imputed using policy='{policy}'",
            )
        )
    logger.info("Imputed %s missing values in %s (policy=%s)", int(missing_mask.sum()), source_column, policy)
    return filled, records