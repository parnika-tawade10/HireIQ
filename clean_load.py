"""
Reads raw Adzuna JSON files, cleans them into a flat table, extracts
skills mentioned in each job description using a keyword dictionary,
flags onsite vs remote, and loads everything into a local SQLite DB.

Run this after fetch_adzuna.py.
"""
import os
import re
import json
import glob
import sqlite3
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "raw_data")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "jobs.db")

# --- Skill dictionary -------------------------------------------------
# Keep this list editable -- it's the "AI/analysis" backbone for now.
# Longer/more specific terms should come first so matching is cleaner.
SKILLS = [
    "power bi", "tableau", "machine learning", "deep learning",
    "python", "sql", "excel", "r", "java", "javascript", "aws",
    "azure", "gcp", "docker", "kubernetes", "spark", "hadoop",
    "airflow", "snowflake", "postgres", "mysql", "mongodb",
    "git", "linux", "pandas", "numpy", "tensorflow", "pytorch",
    "nlp", "etl", "api", "rest", "django", "flask", "react",
    "node.js", "scikit-learn", "statistics", "a/b testing",
]

REMOTE_PATTERNS = re.compile(r"\b(remote|work from home|wfh|hybrid)\b", re.I)


def load_raw_files():
    records = []
    for path in glob.glob(os.path.join(RAW_DIR, "*.json")):
        with open(path) as f:
            data = json.load(f)
        for job in data.get("results", []):
            records.append(job)
    return records


def flatten(records):
    rows = []
    for job in records:
        rows.append({
            "job_id": job.get("id"),
            "title": job.get("title", "").strip(),
            "company": (job.get("company") or {}).get("display_name"),
            "city": (job.get("location") or {}).get("display_name"),
            "description": job.get("description", ""),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "created": job.get("created"),
            "category": (job.get("category") or {}).get("label"),
            "redirect_url": job.get("redirect_url"),
        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["job_id"])
    return df


def add_remote_flag(df):
    df["work_mode"] = df["description"].apply(
        lambda d: "remote_or_hybrid" if REMOTE_PATTERNS.search(d or "") else "onsite"
    )
    return df


def extract_skills(df):
    """Returns a long-format DataFrame: job_id, skill"""
    rows = []
    for job_id, desc in zip(df["job_id"], df["description"]):
        desc_lower = (desc or "").lower()
        for skill in SKILLS:
            if skill in desc_lower:
                rows.append({"job_id": job_id, "skill": skill})
    return pd.DataFrame(rows)


def main():
    records = load_raw_files()
    if not records:
        raise SystemExit(
            f"No raw JSON found in {RAW_DIR}. Run fetch_adzuna.py first."
        )

    df = flatten(records)
    df = add_remote_flag(df)
    skills_df = extract_skills(df)

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    df.to_sql("jobs", conn, if_exists="replace", index=False)
    skills_df.to_sql("job_skills", conn, if_exists="replace", index=False)

    conn.close()

    print(f"Loaded {len(df)} jobs and {len(skills_df)} skill mentions into {DB_PATH}")
    print("\nWork mode breakdown:")
    print(df["work_mode"].value_counts())


if __name__ == "__main__":
    main()
