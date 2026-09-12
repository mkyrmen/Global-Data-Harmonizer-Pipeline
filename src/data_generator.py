"""Legacy wrapper — generate the demo 'dirty' datasets.

Kept for backwards compatibility with the original project; delegates to the
refactored engine via project-relative paths.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"

# 1. Source A: World Bank style (missing values & inconsistent names)
data_a = {
    "Country Name": ["USA", "usa", "Germany", "GERMANY", "India", "India"],
    "GDP_2023": [23.3, 23.3, 4.2, None, 3.7, 3.7],
    "Population": [331, 331, 83, 83, None, 1400],
}
df_a = pd.DataFrame(data_a)
RAW.mkdir(parents=True, exist_ok=True)
df_a.to_csv(RAW / "source_world_bank.csv", index=False)

# 2. Source B: UN style (messy dates & string-heavy numbers)
data_b = {
    "Nation": ["USA", "Germany", "India", "Brazil"],
    "Year": ["2023-01-01", "23/01/2023", "2023.01", "Jan 2023"],
    "Life_Expectancy": ["77.2 years", "81.0", "70.1 yrs", "n/a"],
}
df_b = pd.DataFrame(data_b)
df_b.to_csv(RAW / "source_un.csv", index=False)

print(f"'Dirty' datasets generated in {RAW}")