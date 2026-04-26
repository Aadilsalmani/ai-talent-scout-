candidates = [
    {
        "name": "Rahul",
        "skills": ["python", "gis", "qgis"]
    },
    {
        "name": "Ayesha",
        "skills": ["sql", "excel"]
    },
    {
        "name": "Arjun",
        "skills": ["python", "machine learning"]
    }
]


jd = "Looking for a GIS analyst with Python and QGIS experience"


candidate_responses = {
    "Rahul": "I am very interested in this role and excited to apply",
    "Ayesha": "Not interested right now",
    "Arjun": "I am interested but depends on salary"
}




def calculate_interest(response):
    response = response.lower()

    if "not interested" in response or "busy" in response:
        return 20
    elif "very interested" in response or "excited" in response:
        return 90
    elif "depends" in response:
        return 50
    elif "interested" in response:
        return 70
    else:
        return 40



def extract_skills(jd):
    keywords = ["python", "gis", "qgis", "sql", "excel", "machine learning"]
    jd = jd.lower()
    return [k for k in keywords if k in jd]



def match_candidates(jd, candidates):
    jd = jd.lower()
    results = []
    jd_skills = extract_skills(jd)

    for candidate in candidates:

        # ✅ Get correct response per candidate
        response = candidate_responses.get(candidate["name"], "")
        interest_score = calculate_interest(response)

        matched_skills = set()

        for skill in candidate["skills"]:
            if skill.lower() in jd_skills:
                matched_skills.add(skill.lower())

        matched_skills = list(matched_skills)

        total_skills = len(candidate["skills"])
        match_score = (len(matched_skills) / total_skills) * 100

        # ✅ Combine properly
        final_score = (0.7 * match_score) + (0.3 * interest_score)

        # Missing skills
        missing_skills = []
        for skill in jd_skills:
            if skill not in matched_skills:
                missing_skills.append(skill)

        # Explanation
        if match_score == 100:
            explanation = "Strong match: All key skills align."
        elif match_score >= 50:
            explanation = "Moderate match: Some relevant skills, but gaps exist."
        else:
            explanation = "Weak match: Limited relevant skills."

        # Decision
        if final_score >= 70:
            decision = "Shortlist"
        elif final_score >= 40:
            decision = "Consider"
        else:
            decision = "Reject"

        results.append({
            "name": candidate["name"],
            "matched_skills": matched_skills,
            "match_score": match_score,
            "interest_score": interest_score,
            "final_score": final_score,
            "missing_skills": missing_skills,
            "explanation": explanation,
            "decision": decision
        })

    # ✅ Sort by final_score (important)
    results = sorted(results, key=lambda x: x["final_score"], reverse=True)

    return results



    
    

results = match_candidates(jd, candidates)



for r in results:
    print("Candidate:", r["name"])
    print("Score:", r["match_score"], "%")
    print("Matched Skills:", r["matched_skills"])
    print("Interest Score:", r["interest_score"])
    print("Final Score:", r["final_score"])
    print("Explanation:", r["explanation"])
    print("Missing Skills:", r["missing_skills"])
    print("Decision:", r["decision"])
    print("-------------------------")
