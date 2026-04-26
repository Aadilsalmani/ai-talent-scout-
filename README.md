# 🤖 AI Talent Scouting Agent

An AI-powered recruitment system that evaluates candidates using Large Language Models instead of traditional keyword matching.

This tool simulates how a real recruiter thinks — by analyzing not just skills, but also context, relevance, and candidate intent.

---

## 🚀 Problem

Most hiring tools rely on keyword matching, which:

* Misses strong candidates with different wording
* Cannot evaluate intent or motivation
* Produces similar scores for different profiles

---

## 💡 Solution

This system uses LLMs to:

* Understand job descriptions semantically
* Evaluate candidate skills in context
* Score interest based on candidate responses
* Identify missing or critical skills

---

## 🧠 Key Features

* AI-based skill match scoring (0–100)
* Interest alignment evaluation
* Final hiring decision engine
* Strict AI Mode (no fallback logic)
* Transparent AI reasoning (raw output)
* Skill gap detection

---

## ⚙️ Scoring Logic

Final Score = (0.7 × Skill Match) + (0.3 × Interest Score)

* Skill Match → evaluated using LLM reasoning
* Interest Score → derived from candidate intent and alignment
* Decision thresholds:

  * ≥ 70 → Shortlist
  * 40–69 → Consider
  * < 40 → Reject

---

## 🧩 Architecture

User Input (Job Description)
↓
LLM Skill Extraction
↓
Candidate Database (CSV)
↓
LLM Evaluation:

* Skill Match
* Interest Score
  ↓
  Final Scoring Engine
  ↓
  Ranking + Decision Output
  ↓
  Streamlit UI
