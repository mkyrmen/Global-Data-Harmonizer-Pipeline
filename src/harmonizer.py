import pandas as pd
import numpy as np
import sqlite3
import re

class DataHarmonizer:
    def __init__(self):
        self.db_path = "Z:/Project/Data_Harmonizer/processed_data/harmonized_data.db"
        
    def clean_source_a(self, path):
        df = pd.read_csv(path)
        # Standardize Country Names (Title Case) and Drop Duplicates
        df['Country Name'] = df['Country Name'].str.title()
        df = df.drop_duplicates()
        # Rename for Unification
        df = df.rename(columns={'Country Name': 'country', 'GDP_2023': 'gdp'})
        return df

    def clean_source_b(self, path):
        df = pd.read_csv(path)
        # Fix messy dates using pd.to_datetime with fuzzy matching
        df['year'] = pd.to_datetime(df['Year'], errors='coerce').dt.year
        
        # Clean numeric strings (e.g., '77.2 years' -> 77.2)
        df['life_expectancy'] = df['Life_Expectancy'].apply(
            lambda x: re.findall(r"[-+]?\d*\.\d+|\d+", str(x))[0] if re.findall(r"\d+", str(x)) else np.nan
        ).astype(float)
        
        df = df.rename(columns={'Nation': 'country'})
        return df[['country', 'year', 'life_expectancy']]

    def execute_pipeline(self):
        # 1. Extract & Initial Clean
        df_wb = self.clean_source_a("Z:/Data_Harmonizer_Pro/raw_data/source_world_bank.csv")
        df_un = self.clean_source_b("Z:/Data_Harmonizer_Pro/raw_data/source_un.csv")
        
        # 2. Harmonize (Merge)
        final_df = pd.merge(df_wb, df_un, on='country', how='outer')

        # --- MASTER LEVEL DATA GOVERNANCE ---
        # A. Case Normalization (Fixes 'USA' vs 'Usa')
        final_df['country'] = final_df['country'].str.upper()

        # B. Grouped Aggregation (Fixes Duplicate Rows by merging data)
        # We group by country and take the 'first' non-null value for each column
        final_df = final_df.groupby('country').first().reset_index()

        # C. Fill remaining missing values with a placeholder or mean
        final_df['year'] = final_df['year'].fillna(2023).astype(int)
        # ------------------------------------
        
        # 3. Load
        conn = sqlite3.connect(self.db_path)
        final_df.to_sql('socio_economic_stats', conn, if_exists='replace', index=False)
        conn.close()
        
        print("\n🏆 FINAL CLEANED & HARMONIZED DATASET:")
        print(final_df)

if __name__ == "__main__":
    harmonizer = DataHarmonizer()
    harmonizer.execute_pipeline()