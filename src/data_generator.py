import pandas as pd
import numpy as np
import os

# Create directory
os.makedirs("Z:/Data_Harmonizer_Pro/raw_data", exist_ok=True)

# 1. Generate Source A: World Bank Style (Missing values & Inconsistent Names)
data_a = {
    'Country Name': ['USA', 'usa', 'Germany', 'GERMANY', 'India', 'India'],
    'GDP_2023': [23.3, 23.3, 4.2, np.nan, 3.7, 3.7],
    'Population': [331, 331, 83, 83, np.nan, 1400]
}
df_a = pd.DataFrame(data_a)
df_a.to_csv("Z:/Data_Harmonizer_Pro/raw_data/source_world_bank.csv", index=False)

# 2. Generate Source B: UN Style (Messy Dates & String-heavy Numbers)
data_b = {
    'Nation': ['USA', 'Germany', 'India', 'Brazil'],
    'Year': ['2023-01-01', '23/01/2023', '2023.01', 'Jan 2023'],
    'Life_Expectancy': ['77.2 years', '81.0', '70.1 yrs', 'n/a']
}
df_b = pd.DataFrame(data_b)
df_b.to_csv("Z:/Project/Data_Harmonizer/raw_data/source_un.csv", index=False)

print("✅ 'Dirty' datasets generated in Z:/Project/Data_Harmonizer/raw_data/")