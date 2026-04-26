import os
import re

import pandas as pd
import streamlit as st

from dotenv import load_dotenv
load_dotenv()

# ── Optional AI import ────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# ── Mode selector ─────────────────────────────────────────────────────────────
mode = st.sidebar.selectbox("Select Mode", ["Recruiter View", "Candidate View"])

# ── AI model setup ────────────────────────────────────────────────────────────
api_key = os.getenv("GOOGLE_API_KEY", "").strip()

if not api_key:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔑 API Key")
    api_key = st.sidebar.text_input(
        "Enter Google API Key",
        type="password",
        help="Get one free at aistudio.google.com",
    ).strip()

CANDIDATE_MODELS = [
    "gemini-1.5-pro-latest",
    "gemini-pro",
]

model       = None
model_name  = None
model_error = None

if not genai:
    model_error = "google-generativeai not installed."
elif api_key:
    try:
        genai.configure(api_key=api_key)
        # Try to find the first available working model
        for name in CANDIDATE_MODELS:
            try:
                candidate = genai.GenerativeModel(name)
                # A simple prompt to verify the key and model work
                candidate.generate_content("Hi") 
                model = candidate
                model_name = name
                break
            except Exception as e:
                last_error = str(e)
        
        if model is None:
            model_error = f"API Key valid, but models failed. Error: {last_error}"
    except Exception as e:
        model_error = f"Configuration error: {str(e)}"



strict_ai = st.sidebar.checkbox("🚫 Disable fallback (Strict AI Mode)")
show_debug = st.sidebar.checkbox("🧠 Show AI Raw Output", key="show_ai_debug")


st.sidebar.markdown("---")
if model:
    st.sidebar.success(f"✅ AI active · {model_name}")
elif model_error:
    st.sidebar.error(f"❌ AI error:\n{model_error}")
else:
    st.sidebar.warning("⚠️ No API key — using fallback scoring")

# ── Data ──────────────────────────────────────────────────────────────────────
FILE_PATH = "candidates.csv"

if os.path.exists(FILE_PATH):
    df = pd.read_csv(FILE_PATH)
else:
    df = pd.DataFrame(columns=["name", "email", "skills", "response"])
    st.info("No candidates yet. Add from Candidate View.")

# ── Candidate View ────────────────────────────────────────────────────────────
if mode == "Candidate View":

    # ✅ FIRST: success message
    if st.session_state.get("saved"):
        st.success("✅ Profile saved successfully!")
        st.balloons()
        st.session_state["saved"] = False

    # ✅ SECOND: clear form BEFORE widgets are created
    if st.session_state.get("clear_form"):
        st.session_state["name_input"] = ""
        st.session_state["email_input"] = ""
        st.session_state["skills_input"] = ""
        st.session_state["response_input"] = ""
        st.session_state["clear_form"] = False

    st.title("👤 Candidate Portal")

    # ✅ THEN create form
    with st.form("candidate_form"):

        name = st.text_input("Enter Name", key="name_input")
        email = st.text_input("Enter Email", key="email_input")
        skills = st.text_input("Enter Skills (comma separated)", key="skills_input")
        response = st.text_area("Why are you interested?", key="response_input")

        submitted = st.form_submit_button("Save Profile")

        if submitted:
            if name and skills and email:
                new_row = {
                    "name": name,
                    "email": email,
                    "skills": skills,
                    "response": response
                }

                df_new = pd.DataFrame([new_row])
                df = pd.concat([df, df_new], ignore_index=True)
                df.to_csv(FILE_PATH, index=False)

                st.session_state["saved"] = True
                st.session_state["clear_form"] = True

                st.rerun()
            else:
                st.warning("Name, email and skills are required.")

                # ✅ CLEAR FIELDS
                st.session_state["clear_form"] = True


                st.session_state["saved"] = True
                st.rerun()




    st.stop()

# ── Build in-memory structures from CSV ───────────────────────────────────────
candidates = []
responses  = {}

for _, row in df.iterrows():
    skills_raw    = str(row["skills"]) if pd.notna(row["skills"]) else ""
    parsed_skills = [s.strip().lower() for s in skills_raw.split(",") if s.strip()]

    row_email = str(row.get("email", "")).strip()
    if row_email.lower() == "nan":
        row_email = ""

    candidates.append({
        "name":   row["name"],
        "email":  row_email,
        "skills": parsed_skills,
    })

    if row_email:
        responses[row_email] = str(row.get("response", "")).strip()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _display_email(email: str) -> str:
    if not email or email.lower() == "nan":
        return "_Not provided_"
    return email


# BUG FIX #3 — removed dead st.sidebar.write() line that was placed after return
def _call_model(prompt: str) -> str | None:
    if not model:
        if strict_ai:
            st.error("🚫 Strict AI Mode: No API key or model available.")
            st.stop()
        return None

    try:
        response = model.generate_content(prompt).text
        
        # 🔥 Show raw AI output (for demo/debug)
        if show_debug:
            st.sidebar.write("🧠 RAW AI RESPONSE:")
            st.sidebar.write(response)

        return response

    except Exception as e:
        if strict_ai:
            st.error(f"❌ AI call failed: {e}")
            st.stop()

        st.sidebar.warning(f"⚠️ AI call failed → fallback used")
        return None


def _skill_in_text(skill: str, text: str) -> bool:
    return bool(re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE))


# ── Functions ─────────────────────────────────────────────────────────────────

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


def _fallback_interest_score(candidate_response: str) -> int:
    text  = candidate_response.lower()
    words = len(text.split())
    score = min(40 + words, 70)
    positive_words = [
        "passionate", "experience", "excited", "love", "interested",
        "background", "worked", "built", "developed", "skilled",
        "years", "project", "team", "contribute", "learn",
    ]
    bonus = sum(4 for w in positive_words if w in text)
    return min(score + bonus, 95)


# BUG FIX #1 — removed accidental `prompt = f"""` line inside the f-string call
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

Do NOT give middle scores unless justified.

- Avoid giving same score to different candidates
- Use full range aggressively

Return ONLY a number (0-100). No words, no explanation.
""")

    if res:
        match = re.search(r"\b(\d{1,3})\b", res.strip())
        if match:
            return max(0, min(100, int(match.group(1))))

    return _fallback_interest_score(candidate_response)


def _fallback_skill_score(jd: str, skills_str: str) -> tuple[int, str]:
    skill_tokens = [s.strip().lower() for s in skills_str.split(",") if s.strip()]
    if not skill_tokens:
        return 10, "No skills listed."

    hits  = [s for s in skill_tokens if _skill_in_text(s, jd)]
    ratio = len(hits) / max(len(skill_tokens), 1)
    score = int(10 + ratio * 70)

    if hits:
        return score, f"Keyword matches: {', '.join(hits)}"
    return score, "No skill keywords matched the job description."


# BUG FIX #2 — removed accidental `prompt = f"""` line inside the f-string call
def calculate_skill_match_ai(jd: str, skills_str: str) -> tuple[int, str]:
    res = _call_model(f"""
You are a STRICT technical recruiter.

Job Description:
{jd}

Candidate Skills:
{skills_str}

Score STRICTLY using this rubric:

90-100 → Almost perfect match (has most required + relevant experience)
70-89  → Good match but missing 1-2 important skills
40-69  → Partial match, lacks important skills
0-39   → Poor or irrelevant

IMPORTANT RULES:
- Do NOT give similar scores to different candidates
- Use full range aggressively
- Penalize missing core skills heavily
- Use DIFFERENT scores for different candidates
- Avoid clustering scores
- Be decisive

Return ONLY in this exact format:
Score: <number>
Reason: <one short sentence>
""")

    if res:
        score_match = re.search(r"Score:\s*(\d+)", res)
        score       = int(score_match.group(1)) if score_match else None
        reason      = res.split("Reason:")[-1].strip() if "Reason:" in res else res.strip()
        if score is not None:
            return max(0, min(100, score)), reason

    return _fallback_skill_score(jd, skills_str)


def generate_ai_explanation(
    jd: str,
    candidate_name: str,
    match_score: float,
    interest_score: float,
) -> str:
    res = _call_model(f"""
Job Description:
{jd}

Candidate: {candidate_name}
Skill Match Score: {match_score}/100
Interest Score: {interest_score}/100

In 2-3 sentences explain:
- Whether this candidate is a good fit and why
- Their key strength
- The biggest concern or gap (if any)
""")
    return res if res else "AI explanation unavailable."


def match_candidates(jd: str, candidates: list, responses: dict | None = None) -> list:
    jd_skills = extract_skills(jd)
    results   = []

    for candidate in candidates:
        candidate_response = ""
        if responses and candidate["email"]:
            candidate_response = responses.get(candidate["email"], "")

        interest_score = calculate_interest(candidate_response, jd)

        skills_str  = ", ".join(candidate["skills"]) if candidate["skills"] else "None listed"
        match_score, ai_reason = calculate_skill_match_ai(jd, skills_str)
        match_score = round(match_score, 2)

        final_score    = round((0.7 * match_score) + (0.3 * interest_score), 2)
        matched_skills = [s for s in candidate["skills"] if _skill_in_text(s, jd)]
        missing_skills = [s for s in jd_skills if s not in candidate["skills"]]

        if match_score >= 80:
            explanation = "Strong match: Most key skills align well."
        elif match_score >= 50:
            explanation = "Moderate match: Some relevant skills, but gaps exist."
        else:
            explanation = "Weak match: Limited relevant skills for this role."

        if final_score >= 70:
            decision = "Shortlist"
        elif final_score >= 40:
            decision = "Consider"
        else:
            decision = "Reject"

        results.append({
            "name":           candidate["name"],
            "email":          candidate["email"],
            "match_score":    match_score,
            "interest_score": interest_score,
            "final_score":    final_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "decision":       decision,
            "explanation":    explanation,
            "skill_reason":   ai_reason,
        })

        

    return sorted(results, key=lambda x: x["final_score"], reverse=True)


# ── Recruiter View ────────────────────────────────────────────────────────────
if mode == "Recruiter View":
    st.title("🤖 AI Talent Scouting Agent")
    st.caption("🧠 Powered by LLM-based semantic evaluation, not keyword matching")
    if strict_ai:
        st.warning("🚫 Strict AI Mode Enabled — No fallback allowed")
    elif model:
        st.success("🧠 AI Mode Active")
    else:
        st.info("⚙️ Fallback Mode Active")

    st.subheader("📂 Candidate Database")
    with st.expander("View Candidates", expanded=False):
        df_display  = df.copy()
        sort_option = st.selectbox("Sort Candidates By", ["Name (A-Z)", "Latest Added"])

        if sort_option == "Name (A-Z)":
            df_display = df_display.sort_values(by="name")
        else:
            df_display = df_display.iloc[::-1]

        skill_filter = st.text_input("Filter by Skill")
        if skill_filter:
            df_display = df_display[
                df_display["skills"].str.contains(skill_filter, case=False, na=False)
            ]
        st.dataframe(df_display, use_container_width=True)

    jd_input = st.text_area(
        "Enter Job Description",
        "Looking for a GIS Analyst with strong Python and QGIS experience. "
        "The candidate should be comfortable with spatial data analysis, SQL, "
        "and remote sensing. Experience with ArcGIS or PostGIS is a plus.",
    )

    if df.empty:
        st.warning("No candidates yet. Switch to Candidate View to add profiles.")
        st.stop()


    if strict_ai:
        st.warning("🚫 Strict AI Mode Enabled — No fallback allowed")

    if st.button("Run Analysis"):
        if not jd_input.strip():
            st.warning("Please enter a job description.")
            st.stop()

        with st.spinner("🔍 Analysing candidates…"):
            results = match_candidates(jd_input, candidates, responses)

        st.success(f"✅ Analysis complete! {len(results)} candidates evaluated.")
        if model:
            st.caption("🧠 Scores generated using AI")
        else:
            st.caption("⚙️ Scores generated using fallback logic")
        st.balloons()
        st.divider()

        top = results[:3]
        st.subheader("🏆 Top Candidates")
        for t in top:
            st.markdown(
                f"**👤 {t['name']}**  \n"
                f"📧 {_display_email(t['email'])}  \n"
                f"⭐ **Score:** {t['final_score']}"
            )
            st.divider()

        top_text = "\n".join([
            f"{t['name']} ({_display_email(t['email'])}): "
            f"score {t['final_score']}, skills {t['matched_skills']}"
            for t in top
        ])

        if model:
            res = _call_model(f"""
Job Description: {jd_input}

Top Candidates:
{top_text}

In a short paragraph explain why these are the top candidates,
their key strengths, and any hiring risks to watch out for.
""")
            if res:
                st.subheader("🧠 AI Recruiter Summary")
                st.markdown(res)
        else:
            st.info("AI summary unavailable (fallback mode active).")

        st.divider()

        for i, r in enumerate(results):
            with st.container():
                st.markdown(f"### 👤 {r['name']}  📧 {_display_email(r['email'])}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Final Score",    r["final_score"])
                col2.metric("Match Score",    r["match_score"])
                col3.metric("Interest Score", r["interest_score"])

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

                ai_explanation = (
                    generate_ai_explanation(
                        jd_input,
                        r["name"],
                        r["match_score"],
                        r["interest_score"],
                    )
                    if i < 3
                    else r["explanation"]
                )

                st.markdown(f"🧠 **AI Insight:** {ai_explanation}")
                st.caption(r["explanation"])
                st.divider()