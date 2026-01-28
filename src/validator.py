import sqlite3
import pandas as pd

def run_validation():
    db_path = "Z:/Project/Data_Harmonizer/processed_data/harmonized_data.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM socio_economic_stats", conn)
    
    print("🛡️ --- STARTING DATA QUALITY AUDIT ---")
    
    # Check 1: Uniqueness (Primary Key Check)
    duplicates = df.duplicated(subset=['country']).sum()
    print(f"✅ Duplicates Found: {duplicates}")
    
    # Check 2: Null Density
    null_counts = df.isnull().sum().sum()
    if null_counts > 0:
        print(f"⚠️ Warning: {null_counts} missing values detected in dataset.")
    else:
        print("✅ No missing values detected.")

    # Check 3: Schema Integrity
    expected_cols = ['country', 'gdp', 'Population', 'year', 'life_expectancy']
    if all(col in df.columns for col in expected_cols):
        print("✅ Schema matches requirements.")
        
    conn.close()

if __name__ == "__main__":
    run_validation()