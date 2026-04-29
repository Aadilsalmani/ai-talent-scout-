import os
import re
import io

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ── Groq SDK ──────────────────────────────────────────────────────────────────
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ── Mode selector ─────────────────────────────────────────────────────────────
mode = st.sidebar.selectbox("Select Mode", ["Recruiter View", "Candidate View"])

# ── API key ───────────────────────────────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY", "").strip()

if not api_key:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔑 Groq API Key")
    api_key = st.sidebar.text_input(
        "Enter Groq API Key",
        type="password",
        help="Free key at console.groq.com — no credit card needed",
    ).strip()

# ── AI client setup ───────────────────────────────────────────────────────────
client      = None
model_name  = "llama-3.3-70b-versatile"
model_error = None

if not GROQ_AVAILABLE:
    model_error = "groq not installed. Run: python -m pip install groq"
elif not api_key:
    model_error = "No API key provided."
else:
    try:
        c = Groq(api_key=api_key)
        c.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        client = c
    except Exception as e:
        model_error = str(e)

# ── Sidebar options ───────────────────────────────────────────────────────────
strict_ai  = st.sidebar.checkbox("🚫 Strict AI Mode (no fallback)")
show_debug = st.sidebar.checkbox("🧠 Show AI Raw Output")

st.sidebar.markdown("---")
if client:
    st.sidebar.success(f"✅ AI active · {model_name}")
elif model_error:
    st.sidebar.error(f"❌ AI error:\n{model_error}")
else:
    st.sidebar.warning("⚠️ No API key — using fallback scoring")

# ── Data ──────────────────────────────────────────────────────────────────────
FILE_PATH = "candidates.csv"
REQUIRED_COLS = {"name", "email", "skills", "response"}

if os.path.exists(FILE_PATH):
    df = pd.read_csv(FILE_PATH)
else:
    df = pd.DataFrame(columns=["name", "email", "skills", "response"])

# ── Candidate View ────────────────────────────────────────────────────────────
if mode == "Candidate View":
    if st.session_state.get("saved"):
        st.success("✅ Profile saved successfully!")
        st.balloons()
        st.session_state["saved"] = False

    if st.session_state.get("clear_form"):
        for k in ["name_input", "email_input", "skills_input", "response_input"]:
            st.session_state[k] = ""
        st.session_state["clear_form"] = False

    st.title("👤 Candidate Portal")

    with st.form("candidate_form"):
        name     = st.text_input("Enter Name",                     key="name_input")
        email    = st.text_input("Enter Email",                    key="email_input")
        skills   = st.text_input("Enter Skills (comma separated)", key="skills_input")
        response = st.text_area("Why are you interested?",         key="response_input")
        submitted = st.form_submit_button("Save Profile")

        if submitted:
            if name and skills and email:
                new_row = {"name": name, "email": email,
                           "skills": skills, "response": response}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                df.to_csv(FILE_PATH, index=False)
                st.session_state["saved"]      = True
                st.session_state["clear_form"] = True
                st.rerun()
            else:
                st.warning("Name, email and skills are required.")

    st.stop()

# ── Build in-memory structures ────────────────────────────────────────────────
def build_candidates(dataframe):
    """Parse a dataframe into candidates list and responses dict."""
    cands = []
    resps = {}
    for _, row in dataframe.iterrows():
        skills_raw    = str(row["skills"]) if pd.notna(row.get("skills")) else ""
        parsed_skills = [s.strip().lower() for s in skills_raw.split(",") if s.strip()]
        row_email     = str(row.get("email", "")).strip()
        if row_email.lower() == "nan":
            row_email = ""
        cands.append({"name": row["name"], "email": row_email, "skills": parsed_skills})
        if row_email:
            resps[row_email] = str(row.get("response", "")).strip()
    return cands, resps

candidates, responses = build_candidates(df)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _display_email(email: str) -> str:
    return "_Not provided_" if not email or email.lower() == "nan" else email


def _call_model(prompt: str) -> str | None:
    if strict_ai and not client:
        st.error("❌ Strict AI Mode: No model available.")
        st.stop()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.2,
        )
        result = response.choices[0].message.content
        if show_debug:
            st.sidebar.code(result, language="text")
        return result
    except Exception as e:
        st.sidebar.error(f"❌ AI Error: {e}")
        return None


def _skill_in_text(skill: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE))

# ── Core functions ────────────────────────────────────────────────────────────

def extract_skills(jd: str) -> list[str]:
    res = _call_model(
        "List the key technical skills required from this job description "
        "as a comma-separated list only, no extra text:\n" + jd
    )
    if res:
        return [s.strip().lower() for s in res.split(",") if s.strip()]
    keywords = [
        "python", "gis", "qgis", "sql", "excel", "machine learning",
        "remote sensing", "arcgis", "tableau", "postgis", "r language",
        "deep learning", "tensorflow", "pytorch", "aws", "azure", "docker",
        "java", "javascript", "react", "node.js", "mongodb", "postgresql",
    ]
    return [k for k in keywords if _skill_in_text(k, jd)]


def _fallback_interest_score(text: str) -> int:
    words = len(text.split())
    score = min(40 + words, 70)
    bonus = sum(4 for w in [
        "passionate", "experience", "excited", "love", "interested",
        "background", "worked", "built", "developed", "skilled",
        "years", "project", "team", "contribute", "learn",
    ] if w in text.lower())
    return min(score + bonus, 95)


def calculate_interest(candidate_response: str, jd: str) -> int:
    candidate_response = candidate_response.strip()
    if not candidate_response:
        return 15
    res = _call_model(f"""
Evaluate candidate interest STRICTLY.

Job Description:
{jd}

Candidate Statement:
"{candidate_response}"

Scoring rules:
80-100 → Highly specific, clearly aligned with role
60-79  → Relevant but generic
30-59  → Weak alignment
0-29   → No real interest

- Give DIFFERENT scores to different candidates
- Use the full 0-100 range aggressively
- Do NOT cluster scores near 50

Return ONLY a single integer (0-100). No words, no explanation.
""")
    if res:
        m = re.search(r"\b(\d{1,3})\b", res.strip())
        if m:
            return max(0, min(100, int(m.group(1))))
    return _fallback_interest_score(candidate_response)


def _fallback_skill_score(jd: str, skills_str: str) -> tuple[int, str]:
    tokens = [s.strip().lower() for s in skills_str.split(",") if s.strip()]
    if not tokens:
        return 10, "No skills listed."
    hits  = [s for s in tokens if _skill_in_text(s, jd)]
    score = int(10 + (len(hits) / max(len(tokens), 1)) * 70)
    return (score, f"Keyword matches: {', '.join(hits)}") if hits else (score, "No skill keywords matched.")


def calculate_skill_match_ai(jd: str, skills_str: str) -> tuple[int, str]:
    res = _call_model(f"""
You are a STRICT technical recruiter.

Job Description:
{jd}

Candidate Skills:
{skills_str}

Score STRICTLY:
90-100 → Almost perfect match
70-89  → Good but missing 1-2 important skills
40-69  → Partial match, lacks important skills
0-39   → Poor or irrelevant

Rules:
- Give DIFFERENT scores to different candidates
- Use the full range aggressively
- Penalize missing core skills heavily

Respond ONLY in this exact format (two lines):
Score: <number>
Reason: <one short sentence>
""")
    if res:
        sm = re.search(r"Score:\s*(\d+)", res)
        if sm:
            score  = max(0, min(100, int(sm.group(1))))
            reason = res.split("Reason:")[-1].strip() if "Reason:" in res else res.strip()
            return score, reason
    return _fallback_skill_score(jd, skills_str)


def generate_ai_explanation(jd: str, name: str, match: float, interest: float) -> str:
    res = _call_model(f"""
Job Description: {jd}
Candidate: {name}
Skill Match: {match}/100  |  Interest: {interest}/100

In 2-3 sentences:
- Is this candidate a good fit and why?
- Key strength
- Biggest gap or concern
""")
    return res if res else "AI explanation unavailable."


def match_candidates(jd: str, cands: list, resps: dict | None = None) -> list:
    jd_skills = extract_skills(jd)
    results   = []
    for candidate in cands:
        resp    = (resps or {}).get(candidate["email"], "") if candidate["email"] else ""
        i_score = calculate_interest(resp, jd)

        skills_str         = ", ".join(candidate["skills"]) or "None listed"
        m_score, ai_reason = calculate_skill_match_ai(jd, skills_str)
        m_score            = round(m_score, 2)
        final              = round(0.7 * m_score + 0.3 * i_score, 2)

        matched = [s for s in candidate["skills"] if _skill_in_text(s, jd)]
        missing = [s for s in jd_skills if s not in candidate["skills"]]

        explanation = (
            "Strong match: Most key skills align well."         if m_score >= 80 else
            "Moderate match: Some relevant skills, gaps exist." if m_score >= 50 else
            "Weak match: Limited relevant skills for this role."
        )
        decision = "Shortlist" if final >= 70 else "Consider" if final >= 40 else "Reject"

        results.append({
            "name": candidate["name"], "email": candidate["email"],
            "match_score": m_score, "interest_score": i_score, "final_score": final,
            "matched_skills": matched, "missing_skills": missing,
            "decision": decision, "explanation": explanation, "skill_reason": ai_reason,
        })
    return sorted(results, key=lambda x: x["final_score"], reverse=True)

# ── Recruiter View ────────────────────────────────────────────────────────────
if mode == "Recruiter View":
    st.title("🤖 AI Talent Scouting Agent")
    st.caption("🧠 Powered by LLM-based semantic evaluation, not keyword matching")

    if strict_ai:
        st.warning("🚫 Strict AI Mode Enabled — No fallback allowed")
    elif client:
        st.success(f"🧠 AI Mode Active ({model_name})")
    else:
        st.info("⚙️ Fallback Mode Active")

    # ── CSV Upload ────────────────────────────────────────────────────────────
    st.subheader("📂 Candidate Database")

    with st.expander("⬆️ Upload your own candidates CSV", expanded=False):
        st.markdown(
            "Upload a CSV with these columns: "
            "`name`, `email`, `skills` (comma-separated), `response`"
        )

        # Download template button
        template_df  = pd.DataFrame([{
            "name":     "Jane Doe",
            "email":    "jane@example.com",
            "skills":   "python, sql, machine learning",
            "response": "I am passionate about data science and have 3 years of experience..."
        }])
        template_csv = template_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download template CSV",
            data=template_csv,
            file_name="candidates_template.csv",
            mime="text/csv",
        )

        uploaded_file = st.file_uploader(
            "Choose CSV file",
            type=["csv"],
            key="csv_uploader",
        )

        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                # Validate required columns
                missing_cols = REQUIRED_COLS - set(uploaded_df.columns.str.lower())
                if missing_cols:
                    st.error(
                        f"❌ Missing columns: **{', '.join(missing_cols)}**\n\n"
                        "Your CSV must have: `name`, `email`, `skills`, `response`"
                    )
                else:
                    # Normalise column names to lowercase
                    uploaded_df.columns = uploaded_df.columns.str.lower()

                    col1, col2 = st.columns(2)
                    col1.metric("Rows found", len(uploaded_df))
                    col2.metric(
                        "Valid emails",
                        uploaded_df["email"].dropna()
                        .apply(lambda x: "@" in str(x)).sum()
                    )

                    st.dataframe(uploaded_df.head(5), use_container_width=True)

                    action = st.radio(
                        "What would you like to do?",
                        ["Replace existing candidates", "Merge with existing candidates"],
                        horizontal=True,
                    )

                    if st.button("✅ Confirm & Load", type="primary"):
                        if action == "Replace existing candidates":
                            df = uploaded_df.copy()
                        else:
                            df = pd.concat([df, uploaded_df], ignore_index=True).drop_duplicates(
                                subset=["email"]
                            )
                        df.to_csv(FILE_PATH, index=False)
                        # Rebuild in-memory structures
                        candidates, responses = build_candidates(df)
                        st.success(
                            f"✅ Loaded {len(df)} candidates "
                            f"({'replaced' if action.startswith('Replace') else 'merged'})."
                        )
                        st.rerun()

            except Exception as e:
                st.error(f"❌ Could not read file: {e}")

    # ── View / filter existing candidates ────────────────────────────────────
    with st.expander("👁️ View Candidates", expanded=False):
        df_display  = df.copy()
        sort_option = st.selectbox("Sort by", ["Name (A-Z)", "Latest Added"])
        df_display  = (df_display.sort_values("name")
                       if sort_option == "Name (A-Z)" else df_display.iloc[::-1])
        skill_filter = st.text_input("Filter by Skill")
        if skill_filter:
            df_display = df_display[
                df_display["skills"].str.contains(skill_filter, case=False, na=False)
            ]
        st.dataframe(df_display, use_container_width=True)

        # Export current database
        if not df.empty:
            st.download_button(
                label="📤 Export current candidates CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="candidates_export.csv",
                mime="text/csv",
            )

    jd_input = st.text_area(
        "Enter Job Description",
        "Looking for a GIS Analyst with strong Python and QGIS experience. "
        "The candidate should be comfortable with spatial data analysis, SQL, "
        "and remote sensing. Experience with ArcGIS or PostGIS is a plus.",
    )

    if df.empty:
        st.warning("No candidates yet. Upload a CSV above or switch to Candidate View.")
        st.stop()

    if st.button("Run Analysis", type="primary"):
        if strict_ai and not client:
            st.error("❌ Cannot run: AI model not available in Strict Mode.")
            st.stop()
        if not jd_input.strip():
            st.warning("Please enter a job description.")
            st.stop()

        with st.spinner("🔍 Analysing candidates…"):
            results = match_candidates(jd_input, candidates, responses)

        st.success(f"✅ Analysis complete! {len(results)} candidates evaluated.")
        st.caption("🧠 Scores via AI" if client else "⚙️ Scores via fallback logic")
        st.balloons()
        st.divider()

        st.subheader("🏆 Top Candidates")
        for t in results[:3]:
            st.markdown(
                f"**👤 {t['name']}**  \n"
                f"📧 {_display_email(t['email'])}  \n"
                f"⭐ **Score:** {t['final_score']}"
            )
            st.divider()

        if client:
            top_text = "\n".join([
                f"{t['name']}: score {t['final_score']}, skills {t['matched_skills']}"
                for t in results[:3]
            ])
            summary = _call_model(f"""
Job Description: {jd_input}

Top Candidates:
{top_text}

In a short paragraph: why are these the top candidates, their key strengths,
and any hiring risks?
""")
            if summary:
                st.subheader("🧠 AI Recruiter Summary")
                st.markdown(summary)
        else:
            st.info("AI summary unavailable (fallback mode active).")

        st.divider()

        for i, r in enumerate(results):
            with st.container():
                st.markdown(f"### 👤 {r['name']}  📧 {_display_email(r['email'])}")

                c1, c2, c3 = st.columns(3)
                c1.metric("Final Score",    r["final_score"])
                c2.metric("Match Score",    r["match_score"])
                c3.metric("Interest Score", r["interest_score"])

                st.write("🔎 Matched Skills:", ", ".join(r["matched_skills"]) or "None")
                st.write("🧠 AI Skill Evaluation:", r.get("skill_reason", "N/A"))

                if r["decision"] == "Shortlist":
                    st.success("✅ Shortlist")
                elif r["decision"] == "Consider":
                    st.warning("⚠️ Consider")
                else:
                    st.error("❌ Reject")

                if r["decision"] != "Shortlist" and r["missing_skills"]:
                    st.markdown("🚫 **Missing skills:**")
                    st.write(", ".join(r["missing_skills"]))

                explanation = (
                    generate_ai_explanation(
                        jd_input, r["name"], r["match_score"], r["interest_score"]
                    ) if i < 3 else r["explanation"]
                )
                st.markdown(f"🧠 **AI Insight:** {explanation}")
                st.caption(r["explanation"])
                st.divider()
