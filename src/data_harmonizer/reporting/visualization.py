"""Static reporting visualization (preserved from the legacy Seaborn chart).

Kept as an optional Python-side deliverable; the web application renders
interactive charts with Recharts from the same JSON reports.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def render_summary_plot(df: pd.DataFrame, output_path: str | Path) -> Path:
    """Render a GDP-by-country bar chart annotated with life expectancy
    (legacy chart preserved), saving to ``output_path``."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    plot_df = df.dropna(subset=["gdp"]).sort_values("gdp", ascending=False)
    plt.figure(figsize=(12, 7))
    sns.set_theme(style="whitegrid")
    ax = sns.barplot(data=plot_df, x="country_name", y="gdp", hue="country_name", palette="magma", legend=False)  # type: ignore[call-overload]

    for i, p in enumerate(ax.patches):
        life_exp = plot_df.iloc[i].get("life_expectancy")
        label = f"Life Exp: {life_exp:g}y" if pd.notna(life_exp) else "No Data"
        ax.annotate(
            label,
            (p.get_x() + p.get_width() / 2.0, p.get_height()),
            ha="center",
            va="center",
            xytext=(0, 9),
            textcoords="offset points",
            fontweight="bold",
            fontsize=8,
        )

    ax.set_title("Harmonized GDP & Life Expectancy", fontsize=16, pad=20)
    ax.set_ylabel("GDP (Trillions USD)")
    ax.set_xlabel("Country")
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()
    return out