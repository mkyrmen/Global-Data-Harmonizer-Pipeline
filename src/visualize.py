import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def create_dashboard():
    db_path = "Z:/Project/Data_Harmonizer/processed_data/harmonized_data.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM socio_economic_stats", conn)
    conn.close()

    # Drop rows where GDP is missing (like Brazil in our sample)
    plot_df = df.dropna(subset=['gdp']).sort_values('gdp', ascending=False)

    # Set Visual Style
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 7))

    # Create Bar Plot
    ax = sns.barplot(data=plot_df, x='country', y='gdp', palette='magma')

    # Add Data Labels (Life Expectancy) on top of bars
    for i, p in enumerate(ax.patches):
        life_exp = plot_df.iloc[i]['life_expectancy']
        label = f"Life Exp: {life_exp}y" if not pd.isna(life_exp) else "No Data"
        ax.annotate(label, 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha = 'center', va = 'center', 
                    xytext = (0, 9), 
                    textcoords = 'offset points',
                    fontweight='bold')

    plt.title('Global Economic Snapshot: GDP & Life Expectancy', fontsize=16, pad=20)
    plt.ylabel('GDP (Trillions USD)', fontsize=12)
    plt.xlabel('Country', fontsize=12)
    
    plt.tight_layout()
    plt.savefig("Z:/Project/Data_Harmonizer/processed_data/final_analytics_chart.png")
    print("📈 New coherent chart saved to processed_data/final_analytics_chart.png")
    plt.show()

if __name__ == "__main__":
    create_dashboard()