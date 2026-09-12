"""Duplicate detection and conflict resolution.

Replaces the legacy silent ``groupby('country').first()`` behaviour.
Every duplicate group is examined: when duplicated records disagree on a
field, the disagreement is recorded as a :class:`ConflictRecord` together
with the value that was selected and the policy that selected it.

Resolution policies:
  - ``keep_first_non_null``: merge a group by taking the first non-null
    value per column (audited superset of the legacy behaviour),
  - ``keep_first_row``: keep the first physical row of each group.
"""

from __future__ import annotations

import pandas as pd

from data_harmonizer.logging_config import get_logger
from data_harmonizer.schemas import ConflictRecord, TransformationRecord, TransformationType

logger = get_logger(__name__)


def detect_duplicates(df: pd.DataFrame, key_columns: list[str]) -> tuple[int, int]:
    """Return ``(number_of_duplicate_groups, number_of_duplicate_rows)``."""
    mask = df.duplicated(subset=key_columns, keep=False)
    dup_df = df[mask]
    if dup_df.empty:
        return 0, 0
    groups = dup_df.groupby(key_columns, sort=False).ngroups
    rows = int(mask.sum())
    return groups, rows


def resolve_duplicates(
    df: pd.DataFrame,
    key_columns: list[str],
    value_columns: list[str],
    policy: str = "keep_first_non_null",
    source_dataset: str = "",
    records: list[TransformationRecord] | None = None,
    conflicts: list[ConflictRecord] | None = None,
) -> tuple[pd.DataFrame, list[ConflictRecord], int, int]:
    """Deduplicate ``df`` on ``key_columns`` with conflict auditing.

    Returns ``(deduped_df, conflict_records, groups_found, rows_removed)``.
    """
    records = records if records is not None else []
    conflicts = conflicts if conflicts is not None else []
    rows_before = len(df)

    if rows_before == 0:
        return df, conflicts, 0, 0

    key = key_columns[0] if len(key_columns) == 1 else key_columns

    if policy == "keep_first_non_null":
        aggregated = df.groupby(key, sort=False, as_index=False).first()
    elif policy == "keep_first_row":
        aggregated = df.drop_duplicates(subset=key_columns, keep="first").reset_index(drop=True)
    else:
        raise ValueError(f"Unknown conflict policy: {policy}")

    for grouped_key, group in df.groupby(key, sort=False):
        if len(group) <= 1:
            continue
        for col in value_columns:
            if col not in group.columns:
                continue
            distinct = group[col].dropna().unique().tolist()
            if len(distinct) > 1:
                selected = None
                if policy == "keep_first_non_null":
                    selected = group[col].dropna().iloc[0] if group[col].notna().any() else None
                else:
                    selected = group[col].iloc[0]
                conflicts.append(
                    ConflictRecord(
                        key_field=key if isinstance(key, str) else "+".join(key),
                        key_value=grouped_key,
                        field=col,
                        values=[v for v in distinct],
                        selected_value=selected,
                        policy=policy,
                        reason="Duplicate records disagreed on this field; value selected by policy",
                    )
                )
                if selected is not None:
                    records.append(
                        TransformationRecord(
                            source_dataset=source_dataset,
                            source_column=col,
                            row_index=0,
                            original_value=distinct,
                            transformed_value=selected,
                            transformation_type=TransformationType.DUPLICATE_RESOLUTION,
                            reason=f"Conflict on '{col}' for key {grouped_key}; policy={policy}",
                        )
                    )

    rows_removed = rows_before - len(aggregated)
    groups_found = int(df.duplicated(subset=key_columns, keep=False).sum() // 2) if policy == "keep_first_non_null" else 0

    # More accurate group count: number of keys with >1 member
    group_sizes = df.groupby(key, sort=False).size()
    groups_found = int((group_sizes > 1).sum())

    logger.info("Deduplicated rows: %s -> %s (conflicts=%s)", rows_before, len(aggregated), len(conflicts))
    return aggregated.reset_index(drop=True), conflicts, groups_found, rows_removed