## Features

- Live data pipeline — pulls real job postings from the Adzuna API (title, company, city, salary, description)
- Skill extraction — scans job descriptions against a curated skills dictionary to surface in-demand technologies
- Onsite vs. remote detection** — keyword-based classification of work mode
- Interactive dashboard — built with Streamlit, includes:
  - Overview KPIs and work-mode/job-title distribution
  - Skills demand ranking and share-of-mentions breakdown
  - Salary trends by job title
  - Hiring volume by city
  - Postings-over-time trend line
  - Side-by-side city comparison
- AI chatbot (text-to-SQL) — ask questions in plain English; the app uses Google Gemini to generate and safely execute a SQL query against the live database, then explains the result in natural language, with full conversation history
- Salary predictor — a `scikit-learn` linear regression model trained on postings with salary data, predicting expected salary for a given title/city/work-mode combination
- Resume matcher — upload a resume (PDF/txt) and see which in-demand skills you already have, which top skills you're missing, and which job titles best match your current profile
- Simulated job alerts — demonstrates a notification workflow (create an alert, simulate a match check) without sending real emails
- User authentication — simple login/signup system with hashed passwords, gating access to the dashboard

## Tech Stack

| Layer            | Tools                                      |
|-------------------|---------------------------------------------|
| Data collection    | Python, Adzuna API                         |
| Storage            | SQLite                                     |
| Analysis           | pandas, SQL                                |
| Machine learning   | scikit-learn (salary prediction)           |
| Dashboard          | Streamlit, Plotly                          |
| AI chatbot         | Google Gemini API (text-to-SQL)            |
| Resume parsing     | pdfplumber                                 |


## Limitations & Honest Notes

This is a student/portfolio project, not a production system:
- Single data source (Adzuna) — coverage is limited to what that API returns
- Onsite/remote classification is keyword-based, not a verified field
- Skill extraction uses a fixed dictionary, not full NLP/NER
- Authentication is demo-grade (hashed passwords, no sessions/tokens/password reset)
- Job alerts are simulated — no real email/Slack integration
- Salary predictions depend heavily on how much salary data exists per title/city; treat as an estimate, not a forecast

## Future Improvements

- Add a second data source (e.g., USAJOBS) and deduplicate
- Replace keyword-based skill extraction with a trained NER model
- Add real email delivery for job alerts (e.g., via SendGrid)
- Add proper session-based authentication
- Deploy with a persistent database (Postgres) instead of local SQLite for multi-user use

## License

This project is open source and available under the [MIT License](LICENSE).

## Author

Built by Parnika Tawade as a portfolio/academic project.
