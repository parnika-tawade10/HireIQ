"""
Job Market Analytics Dashboard
Run with: streamlit run app.py
"""
import os
import re
import sqlite3
import hashlib
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
from sklearn.linear_model import LinearRegression
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "jobs.db")

st.set_page_config(
    page_title="HireIQ",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# Styling — warm charcoal/amber palette, no default Streamlit blue.
# ---------------------------------------------------------------------
ACCENT = "#C98B3F"       # muted amber
ACCENT_SOFT = "#E0A85C"
SECONDARY = "#8A7A66"    # warm taupe, used as a secondary chart color
BG = "#161513"
CARD_BG = "#1F1D19"
BORDER = "#33302A"
TEXT_MUTED = "#B8AFA2"

st.markdown(f"""
<style>
    #MainMenu, footer {{visibility: hidden;}}
    header {{background-color: transparent !important;}}

    /* Keep the sidebar collapse/expand arrow visible and clickable */
    button[data-testid="stSidebarCollapseButton"] {{
        visibility: visible !important;
        opacity: 1 !important;
    }}
    div[data-testid="collapsedControl"] {{
        visibility: visible !important;
        opacity: 1 !important;
    }}

    .stApp {{
        background-color: {BG};
    }}

    div[data-testid="stMetric"] {{
        background: linear-gradient(135deg, {CARD_BG}, #24211c);
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 18px 20px;
    }}
    div[data-testid="stMetric"] label {{
        color: {TEXT_MUTED} !important;
    }}
    div[data-testid="stMetricValue"] {{
        color: {ACCENT_SOFT} !important;
    }}

    section[data-testid="stSidebar"] {{
        background-color: #131210;
        border-right: 1px solid {BORDER};
    }}

    .login-card {{
        background: linear-gradient(135deg, {CARD_BG}, #201e1a);
        border: 1px solid {BORDER};
        border-radius: 16px;
        padding: 40px 36px;
        margin-top: 40px;
    }}

    h1, h2, h3 {{
        letter-spacing: -0.3px;
        color: #EDE7DD;
    }}

    .stButton > button {{
        border-radius: 8px;
        font-weight: 600;
        background-color: {ACCENT};
        color: #1a1815;
        border: none;
    }}
    .stButton > button:hover {{
        background-color: {ACCENT_SOFT};
        color: #1a1815;
    }}

    div[role="radiogroup"] label {{
        padding: 6px 4px;
    }}
</style>
""", unsafe_allow_html=True)

# Chart color sequences — warm, non-blue palette used throughout.
WARM_SEQUENCE = ["#C98B3F", "#8A7A66", "#B25C4A", "#D9B26A", "#6B7A5E", "#A65D3E"]
WARM_SCALE = "Oranges"


@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def run_query(sql, params=()):
    return pd.read_sql_query(sql, get_conn(), params=params)


# ---------------------------------------------------------------------
# Simple username/password auth (demo-grade — passwords are hashed with
# SHA-256 and stored in the same SQLite DB, no salting/sessions/tokens.
# Fine for a portfolio project; NOT how you'd do auth in production).
# ---------------------------------------------------------------------
def init_users_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username: str, password: str) -> bool:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    return bool(row) and row[0] == hash_password(password)


init_users_table()

# ---------------------------------------------------------------------
# Skills dictionary — kept in sync with etl/clean_load.py. Used here for
# the resume matcher feature.
# ---------------------------------------------------------------------
SKILLS = [
    "power bi", "tableau", "machine learning", "deep learning",
    "python", "sql", "excel", "r", "java", "javascript", "aws",
    "azure", "gcp", "docker", "kubernetes", "spark", "hadoop",
    "airflow", "snowflake", "postgres", "mysql", "mongodb",
    "git", "linux", "pandas", "numpy", "tensorflow", "pytorch",
    "nlp", "etl", "api", "rest", "django", "flask", "react",
    "node.js", "scikit-learn", "statistics", "a/b testing",
]


def init_alerts_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT,
            city TEXT,
            email TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


init_alerts_table()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None


def login_page():
    st.markdown(
        "<h1 style='text-align:center; margin-top:60px;'>HireIQ</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='text-align:center; color:{TEXT_MUTED};'>Sign in to explore live hiring trends</p>",
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

        with tab_login:
            u = st.text_input("Username", key="login_user")
            p = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if verify_user(u, p):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        with tab_signup:
            nu = st.text_input("Choose a username", key="signup_user")
            np_ = st.text_input("Choose a password", type="password", key="signup_pass")
            if st.button("Create Account", use_container_width=True):
                if not nu or not np_:
                    st.warning("Fill in both fields.")
                elif create_user(nu, np_):
                    st.success("Account created — go to the Login tab to sign in.")
                else:
                    st.error("That username is already taken.")
        st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.logged_in:
    login_page()
    st.stop()


# ---------------------------------------------------------------------
# Schema description given to the LLM for text-to-SQL. Keep in sync
# with the actual tables created in etl/clean_load.py.
# ---------------------------------------------------------------------
SCHEMA_DESCRIPTION = """
Table: jobs
  job_id (text), title (text), company (text), city (text),
  description (text), salary_min (real), salary_max (real),
  created (text, ISO date), category (text),
  work_mode (text: 'onsite' or 'remote_or_hybrid'), redirect_url (text)

Table: job_skills
  job_id (text), skill (text)
  -- one row per (job, skill) mention. Join to jobs on job_id.
"""

SYSTEM_PROMPT = f"""You are a SQL generator for a SQLite database of US job postings.

Schema:
{SCHEMA_DESCRIPTION}

Rules:
- Output ONLY a single valid SQLite SELECT statement. No explanation, no markdown, no semicolon-separated multiple statements.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, or PRAGMA.
- Always add a LIMIT of 200 or fewer unless the user asks for an aggregate (COUNT, AVG, etc.) that returns few rows.
- Use the job_skills table for any question about skills.
"""


def is_safe_select(sql: str) -> bool:
    lowered = sql.strip().lower()
    if not lowered.startswith("select"):
        return False
    forbidden = ["insert", "update", "delete", "drop", "alter", "pragma", ";--", " attach "]
    return not any(word in lowered for word in forbidden) and lowered.count(";") <= 1


def ask_chatbot(question: str, api_key: str):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    # Step 1: ask the model to write SQL
    sql_response = model.generate_content(question)
    sql_text = sql_response.text.strip()
    sql_text = sql_text.replace("```sql", "").replace("```", "").strip()

    if not is_safe_select(sql_text):
        return sql_text, None, "Generated query failed the safety check and was not run."

    try:
        result_df = run_query(sql_text)
    except Exception as e:
        return sql_text, None, f"Query execution error: {e}"

    # Step 2: ask the model to phrase the answer in plain language
    summary_model = genai.GenerativeModel("gemini-2.5-flash")
    summary_response = summary_model.generate_content(
        f"Question: {question}\n\n"
        f"SQL used: {sql_text}\n\n"
        f"Result (as CSV, truncated to first 30 rows):\n"
        f"{result_df.head(30).to_csv(index=False)}\n\n"
        "Answer the question in 2-4 plain-language sentences based on this result."
    )
    answer = summary_response.text.strip()
    return sql_text, result_df, answer


# ---------------------------------------------------------------------
# Sidebar navigation + global filters
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### Welcome, {st.session_state.username}")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        [
            "Overview", "Skills Demand", "Salary Trends", "Hiring by City",
            "Hiring Trend", "Compare Cities", "Salary Predictor",
            "Resume Matcher", "Job Alerts", "AI Chatbot",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("#### Filters")
    st.caption("Applied to Overview, Skills, Salary, City, and Trend pages")

    _all_cities = run_query("SELECT DISTINCT city FROM jobs ORDER BY city")["city"].dropna().tolist()
    _all_titles = run_query("SELECT DISTINCT title FROM jobs ORDER BY title")["title"].dropna().tolist()

    filter_cities = st.multiselect("City", _all_cities)
    filter_titles = st.multiselect("Job Title", _all_titles)
    filter_mode = st.selectbox("Work Mode", ["All", "onsite", "remote_or_hybrid"])

    st.markdown("---")
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.rerun()


def build_filter_clause(alias="jobs"):
    """Returns (where_sql, params) built from the sidebar filters."""
    conditions, params = [], []
    if filter_cities:
        conditions.append(f"{alias}.city IN ({','.join(['?'] * len(filter_cities))})")
        params += filter_cities
    if filter_titles:
        conditions.append(f"{alias}.title IN ({','.join(['?'] * len(filter_titles))})")
        params += filter_titles
    if filter_mode != "All":
        conditions.append(f"{alias}.work_mode = ?")
        params.append(filter_mode)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


st.title("HireIQ — Job Market Analytics")
# ---------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------
if page == "Overview":
    where, params = build_filter_clause("jobs")

    total_jobs = run_query(f"SELECT COUNT(*) as n FROM jobs {where}", tuple(params))["n"][0]
    total_cities = run_query(f"SELECT COUNT(DISTINCT city) as n FROM jobs {where}", tuple(params))["n"][0]
    onsite_pct_df = run_query(
        f"SELECT ROUND(100.0 * SUM(CASE WHEN work_mode='onsite' THEN 1 ELSE 0 END) / COUNT(*), 1) as pct FROM jobs {where}",
        tuple(params),
    )
    onsite_pct = onsite_pct_df["pct"][0] if total_jobs else 0
    total_companies = run_query(f"SELECT COUNT(DISTINCT company) as n FROM jobs {where}", tuple(params))["n"][0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Jobs", f"{total_jobs:,}")
    c2.metric("Cities Covered", total_cities)
    c3.metric("Companies", f"{total_companies:,}")
    c4.metric("% Onsite", f"{onsite_pct}%")

    st.markdown("### ")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Work Mode Split")
        mode_df = run_query(f"SELECT work_mode, COUNT(*) as n FROM jobs {where} GROUP BY work_mode", tuple(params))
        fig_pie = px.pie(mode_df, names="work_mode", values="n", hole=0.45,
                          color_discrete_sequence=WARM_SEQUENCE)
        fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10),
                               paper_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        st.subheader("Top 5 Job Titles by Postings")
        title_df = run_query(f"""
            SELECT title, COUNT(*) as n FROM jobs {where}
            GROUP BY title ORDER BY n DESC LIMIT 5
        """, tuple(params))
        fig_pie2 = px.pie(title_df, names="title", values="n", hole=0.45,
                           color_discrete_sequence=WARM_SEQUENCE)
        fig_pie2.update_layout(margin=dict(t=10, b=10, l=10, r=10),
                                paper_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
        st.plotly_chart(fig_pie2, use_container_width=True)

    st.subheader("Raw data sample")
    st.dataframe(
        run_query(f"SELECT title, company, city, work_mode, salary_min, salary_max FROM jobs {where} LIMIT 50", tuple(params)),
        use_container_width=True,
    )

# ---------------------------------------------------------------------
# Skills Demand
# ---------------------------------------------------------------------
elif page == "Skills Demand":
    where, params = build_filter_clause("j")
    st.subheader("Most In-Demand Skills")
    skills_df = run_query(f"""
        SELECT js.skill, COUNT(*) as mentions
        FROM job_skills js
        JOIN jobs j ON js.job_id = j.job_id
        {where}
        GROUP BY js.skill
        ORDER BY mentions DESC
        LIMIT 20
    """, tuple(params))

    if skills_df.empty:
        st.info("No skill mentions match the current filters.")
    else:
        fig = px.bar(skills_df, x="mentions", y="skill", orientation="h",
                     color="mentions", color_continuous_scale=WARM_SCALE)
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False,
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Top 8 Skills — Share of Mentions")
        top8 = skills_df.head(8)
        fig_pie3 = px.pie(top8, names="skill", values="mentions", hole=0.4,
                           color_discrete_sequence=WARM_SEQUENCE)
        fig_pie3.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
        st.plotly_chart(fig_pie3, use_container_width=True)

# ---------------------------------------------------------------------
# Salary Trends
# ---------------------------------------------------------------------
elif page == "Salary Trends":
    where, params = build_filter_clause("jobs")
    st.subheader("Salary Range by Job Title")
    salary_df = run_query(f"""
        SELECT title, AVG(salary_min) as avg_min, AVG(salary_max) as avg_max
        FROM jobs
        {where}{' AND' if where else 'WHERE'} salary_min IS NOT NULL AND salary_max IS NOT NULL
        GROUP BY title
        ORDER BY avg_max DESC
    """, tuple(params))
    if salary_df.empty:
        st.info("No salary data available for the current filters — many postings don't include it.")
    else:
        fig2 = px.bar(salary_df, x="title", y=["avg_min", "avg_max"], barmode="group",
                       color_discrete_sequence=WARM_SEQUENCE)
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------
# Hiring by City
# ---------------------------------------------------------------------
elif page == "Hiring by City":
    where, params = build_filter_clause("jobs")
    st.subheader("Job Postings by City")
    city_df = run_query(f"""
        SELECT city, COUNT(*) as postings
        FROM jobs {where}
        GROUP BY city
        ORDER BY postings DESC
    """, tuple(params))
    fig3 = px.bar(city_df, x="city", y="postings", color="postings", color_continuous_scale=WARM_SCALE)
    fig3.update_layout(coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("City Share of Total Postings")
    fig_pie4 = px.pie(city_df, names="city", values="postings", hole=0.4,
                       color_discrete_sequence=WARM_SEQUENCE)
    fig_pie4.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
    st.plotly_chart(fig_pie4, use_container_width=True)

# ---------------------------------------------------------------------
# Hiring Trend (postings over time)
# ---------------------------------------------------------------------
elif page == "Hiring Trend":
    where, params = build_filter_clause("jobs")
    st.subheader("Job Postings Over Time")

    trend_raw = run_query(f"SELECT created FROM jobs {where}", tuple(params))
    trend_raw["created"] = pd.to_datetime(trend_raw["created"], errors="coerce", utc=True)
    trend_raw = trend_raw.dropna(subset=["created"])

    if trend_raw.empty:
        st.info("No dated postings available for the current filters.")
    else:
        weekly = (
            trend_raw.set_index("created")
            .resample("W")
            .size()
            .reset_index(name="postings")
        )
        fig_trend = px.line(weekly, x="created", y="postings", markers=True,
                             color_discrete_sequence=[ACCENT])
        fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                 font_color="#EDE7DD", xaxis_title="Week", yaxis_title="Postings")
        st.plotly_chart(fig_trend, use_container_width=True)
        st.caption("Note: reflects when Adzuna listed each posting, grouped by week, not real hiring-market volume.")

# ---------------------------------------------------------------------
# Compare Cities
# ---------------------------------------------------------------------
elif page == "Compare Cities":
    st.subheader("Compare Two Cities")
    all_cities_list = run_query("SELECT DISTINCT city FROM jobs ORDER BY city")["city"].dropna().tolist()

    if len(all_cities_list) < 2:
        st.info("Need at least two cities in the data to compare.")
    else:
        col1, col2 = st.columns(2)
        city_a = col1.selectbox("City A", all_cities_list, index=0)
        city_b = col2.selectbox("City B", all_cities_list, index=1)

        def city_summary(city):
            jobs_n = run_query("SELECT COUNT(*) as n FROM jobs WHERE city = ?", (city,))["n"][0]
            avg_sal = run_query(
                "SELECT AVG(salary_min) as amin, AVG(salary_max) as amax FROM jobs WHERE city = ? AND salary_min IS NOT NULL",
                (city,),
            )
            top_skills = run_query("""
                SELECT js.skill, COUNT(*) as mentions
                FROM job_skills js JOIN jobs j ON js.job_id = j.job_id
                WHERE j.city = ?
                GROUP BY js.skill ORDER BY mentions DESC LIMIT 5
            """, (city,))
            return jobs_n, avg_sal, top_skills

        jobs_a, sal_a, skills_a = city_summary(city_a)
        jobs_b, sal_b, skills_b = city_summary(city_b)

        m1, m2 = st.columns(2)
        m1.metric(f"{city_a} — Jobs", f"{jobs_a:,}")
        m2.metric(f"{city_b} — Jobs", f"{jobs_b:,}")

        m3, m4 = st.columns(2)
        avg_a = sal_a["amin"][0]
        avg_b = sal_b["amin"][0]
        m3.metric(f"{city_a} — Avg Min Salary", f"${avg_a:,.0f}" if pd.notna(avg_a) else "N/A")
        m4.metric(f"{city_b} — Avg Min Salary", f"${avg_b:,.0f}" if pd.notna(avg_b) else "N/A")

        st.markdown("### Top Skills Comparison")
        skills_a["city"] = city_a
        skills_b["city"] = city_b
        combined = pd.concat([skills_a, skills_b])
        if combined.empty:
            st.info("No skill data available for these cities.")
        else:
            fig_cmp = px.bar(combined, x="skill", y="mentions", color="city", barmode="group",
                              color_discrete_sequence=WARM_SEQUENCE)
            fig_cmp.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDE7DD")
            st.plotly_chart(fig_cmp, use_container_width=True)

# ---------------------------------------------------------------------
# Salary Predictor (simple ML model)
# ---------------------------------------------------------------------
elif page == "Salary Predictor":
    st.subheader("Predict Expected Salary")
    st.caption("A simple linear regression trained on postings that include salary data. "
               "This is a portfolio-grade estimate, not a precise forecast — accuracy depends "
               "heavily on how much salary data exists per title/city combination.")

    @st.cache_resource
    def train_salary_model():
        df = run_query("""
            SELECT title, city, work_mode, salary_min, salary_max
            FROM jobs
            WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL
        """)
        if len(df) < 20:
            return None, None
        df["salary_avg"] = (df["salary_min"] + df["salary_max"]) / 2
        X = df[["title", "city", "work_mode"]]
        y = df["salary_avg"]

        preprocessor = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["title", "city", "work_mode"]),
        ])
        pipeline = Pipeline([
            ("prep", preprocessor),
            ("model", LinearRegression()),
        ])
        pipeline.fit(X, y)
        return pipeline, df

    model, training_df = train_salary_model()

    if model is None:
        st.warning("Not enough salary data yet to train a reliable model (need at least 20 rows with salary info).")
    else:
        titles = sorted(training_df["title"].unique())
        cities = sorted(training_df["city"].unique())

        col1, col2, col3 = st.columns(3)
        pred_title = col1.selectbox("Job Title", titles)
        pred_city = col2.selectbox("City", cities)
        pred_mode = col3.selectbox("Work Mode", ["onsite", "remote_or_hybrid"])

        if st.button("Predict Salary"):
            input_df = pd.DataFrame([{"title": pred_title, "city": pred_city, "work_mode": pred_mode}])
            prediction = model.predict(input_df)[0]
            st.metric("Estimated Average Salary", f"${prediction:,.0f}")
            st.caption(f"Based on {len(training_df)} postings with salary data in the current database.")

# ---------------------------------------------------------------------
# Resume Matcher
# ---------------------------------------------------------------------
elif page == "Resume Matcher":
    st.subheader("Match Your Resume Against Market Demand")
    st.caption("Upload a resume (PDF or .txt). We scan it for known skills and compare against "
               "what's most in-demand in the current dataset.")

    uploaded = st.file_uploader("Upload resume", type=["pdf", "txt"])

    resume_text = ""
    if uploaded is not None:
        if uploaded.type == "application/pdf":
            if not PDF_SUPPORT:
                st.error("PDF support requires the 'pdfplumber' package. Run: pip install pdfplumber")
            else:
                with pdfplumber.open(uploaded) as pdf:
                    resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        else:
            resume_text = uploaded.read().decode("utf-8", errors="ignore")

    if resume_text:
        resume_lower = resume_text.lower()
        matched_skills = sorted({s for s in SKILLS if s in resume_lower})

        demand_df = run_query("""
            SELECT skill, COUNT(*) as mentions FROM job_skills
            GROUP BY skill ORDER BY mentions DESC LIMIT 15
        """)
        top_demand_skills = demand_df["skill"].tolist()
        missing_skills = [s for s in top_demand_skills if s not in matched_skills]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Skills found in your resume")
            if matched_skills:
                st.write(", ".join(matched_skills))
            else:
                st.info("No known skills detected — try a plain-text export of your resume.")

        with col2:
            st.markdown("#### High-demand skills you're missing")
            if missing_skills:
                st.write(", ".join(missing_skills))
            else:
                st.success("You cover all of the top 15 in-demand skills in this dataset.")

        # Best-matching job titles based on skill overlap
        st.markdown("#### Titles that best match your current skill set")
        title_skills = run_query("""
            SELECT j.title, js.skill
            FROM job_skills js JOIN jobs j ON js.job_id = j.job_id
        """)
        if not title_skills.empty and matched_skills:
            overlap_scores = (
                title_skills[title_skills["skill"].isin(matched_skills)]
                .groupby("title")["skill"]
                .nunique()
                .sort_values(ascending=False)
                .head(5)
            )
            if overlap_scores.empty:
                st.info("No overlapping titles found for the detected skills.")
            else:
                st.dataframe(overlap_scores.rename("matching skills").reset_index(), use_container_width=True)

# ---------------------------------------------------------------------
# Job Alerts (simulated — no real email/Slack sending)
# ---------------------------------------------------------------------
elif page == "Job Alerts":
    st.subheader("Job Alerts")
    st.caption("Simulated alerts — this demonstrates the workflow of a real notification "
               "system without actually sending email or Slack messages.")

    with st.form("alert_form"):
        alert_title = st.text_input("Job title to watch (optional)")
        alert_city = st.text_input("City to watch (optional)")
        alert_email = st.text_input("Notify this email")
        submitted = st.form_submit_button("Create Alert")

        if submitted:
            if not alert_email:
                st.warning("Email is required.")
            else:
                conn = get_conn()
                conn.execute(
                    "INSERT INTO alerts (username, title, city, email) VALUES (?, ?, ?, ?)",
                    (st.session_state.username, alert_title or None, alert_city or None, alert_email),
                )
                conn.commit()
                st.success("Alert created (simulated — no real email will be sent).")

    st.markdown("### Your Alerts")
    my_alerts = run_query(
        "SELECT title, city, email, created_at FROM alerts WHERE username = ? ORDER BY created_at DESC",
        (st.session_state.username,),
    )
    if my_alerts.empty:
        st.info("No alerts created yet.")
    else:
        st.dataframe(my_alerts, use_container_width=True)

        st.markdown("### Simulate a Check")
        if st.button("Check for matching jobs now"):
            latest = my_alerts.iloc[0]
            conditions, params = [], []
            if pd.notna(latest["title"]) and latest["title"]:
                conditions.append("title LIKE ?")
                params.append(f"%{latest['title']}%")
            if pd.notna(latest["city"]) and latest["city"]:
                conditions.append("city LIKE ?")
                params.append(f"%{latest['city']}%")
            where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            match_count = run_query(f"SELECT COUNT(*) as n FROM jobs {where_sql}", tuple(params))["n"][0]
            st.success(f"Simulated result: {match_count} matching jobs would be emailed to {latest['email']}.")

# ---------------------------------------------------------------------
# AI Chatbot (with conversation history)
# ---------------------------------------------------------------------
elif page == "AI Chatbot":
    st.subheader("Ask the Data")
    st.caption("Ask a natural-language question. The AI writes and runs a SQL query behind the scenes.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.warning("Set GEMINI_API_KEY in your .env file to enable the chatbot.")
    else:
        for turn in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(turn["question"])
            with st.chat_message("assistant"):
                st.write(turn["answer"])
                with st.expander("Show generated SQL and raw result"):
                    st.code(turn["sql"], language="sql")
                    if turn["result_df"] is not None:
                        st.dataframe(turn["result_df"])

        question = st.chat_input("What's the average salary for data analyst roles in Austin?")
        if question:
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    sql_used, result_df, answer = ask_chatbot(question, api_key)
                st.write(answer)
                with st.expander("Show generated SQL and raw result"):
                    st.code(sql_used, language="sql")
                    if result_df is not None:
                        st.dataframe(result_df)

            st.session_state.chat_history.append({
                "question": question, "answer": answer, "sql": sql_used, "result_df": result_df,
            })

        if st.session_state.chat_history:
            if st.button("Clear conversation"):
                st.session_state.chat_history = []
                st.rerun()