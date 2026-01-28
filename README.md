# Global Socio-Economic Data Harmonization Platform

## 📌 Project Overview
A robust Data Engineering platform designed to ingest, clean, and harmonize disparate socio-economic datasets. The system transforms "dirty" multi-source data (CSV/API outputs) into a unified, relational "Source of Truth" ready for downstream analytics and machine learning.

## 🛠️ Technical Stack
* **Core:** Python 3.12+
* **Data Manipulation:** Pandas, NumPy
* **Extraction/Parsing:** Regex (Regular Expressions)
* **Persistence:** SQLite3
* **Validation:** Automated QA Auditing

## 🚀 Key Engineering Features
* **Multi-Source Unification:** Standardized inconsistent schemas from different global organizations into a single, cohesive relational structure.
* **Fuzzy Data Normalization:** Implemented Case-Normalization and Regex-based string cleaning to resolve naming conflicts (e.g., 'USA' vs 'usa') and unit inconsistencies (e.g., '77.2 years' to float).
* **Deterministic Deduplication:** Engineered a grouped aggregation layer to merge partial, redundant records into unique, high-integrity entries.
* **Quality Assurance Layer:** Integrated an automated Data Validator to audit datasets for schema drift, null density, and primary key uniqueness.

## 📊 Data Quality Audit Result
The system successfully processed the ingestion pipeline with the following validation metrics:
* **Duplicate Records:** 0 (Resolved via Aggregation Layer)
* **Schema Integrity:** 100% Match
* **Missing Value Detection:** Automatic warning system for incomplete records (e.g., Brazil dataset gap).

## ⚙️ How to Run
1. **Prepare Raw Data:** Run `python src/generator.py` to create the simulated "dirty" datasets.
2. **Execute Harmonizer:** Run `python src/harmonizer.py` to process and load data into SQLite.
3. **Audit Results:** Run `python src/validator.py` to perform the data quality check.