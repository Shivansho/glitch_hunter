import json
import os
import requests
from datetime import datetime

def build_json_report(incident_time, evidence_level, candidates, deviations):
    """
    Builds the structured JSON incident report.
    """
    report = {
        "incident_id": f"INC-{int(datetime.timestamp(datetime.now()))}",
        "incident_time": str(incident_time),
        "evidence_level": evidence_level,
        "earliest_precursor": None,
        "alternative_hypotheses": [],
        "deviations_chain": []
    }
    
    if len(candidates) > 0:
        report["earliest_precursor"] = {
            "source": candidates[0]['source'],
            "onset_time": str(candidates[0]['onset_time']),
            "lead_time_sec": candidates[0]['lead_time'],
            "confidence_score": candidates[0]['score']
        }
        
        for i in range(1, min(3, len(candidates))):
            report["alternative_hypotheses"].append({
                "source": candidates[i]['source'],
                "onset_time": str(candidates[i]['onset_time']),
                "lead_time_sec": candidates[i]['lead_time'],
                "confidence_score": candidates[i]['score']
            })
            
    # Sort deviations by onset time
    sorted_devs = sorted(deviations.items(), key=lambda x: x[1]['onset_time'])
    for sig, info in sorted_devs:
        report["deviations_chain"].append({
            "signal": sig,
            "onset_time": str(info['onset_time']),
            "magnitude": info['magnitude']
        })
        
    return report

def generate_template_explanation(report):
    """
    Fallback template explanation. Must not claim causation.
    """
    exp = f"Incident Report: {report['incident_id']}\n"
    exp += f"Incident Detected At: {report['incident_time']}\n"
    exp += f"Evidence Level: {report['evidence_level']}\n\n"
    
    if report['evidence_level'] == "INSUFFICIENT":
        exp += "Analysis revealed INSUFFICIENT evidence to determine a clear sequence of precursor events. The incident may be due to random noise or unmonitored variables.\n"
        return exp
        
    prec = report['earliest_precursor']
    exp += f"Earliest Correlated Anomaly & Candidate Precursor:\n"
    exp += f"The earliest meaningful deviation was detected in '{prec['source']}' at {prec['onset_time']}, which preceded the incident by {prec['lead_time_sec']:.1f} seconds.\n\n"
    
    exp += "Sequence of Deviations (Correlation Chain):\n"
    for idx, dev in enumerate(report["deviations_chain"]):
        exp += f"{idx+1}. {dev['signal']} deviated at {dev['onset_time']}\n"
        
    if report["alternative_hypotheses"]:
        exp += "\nAlternative Hypotheses:\n"
        for idx, alt in enumerate(report["alternative_hypotheses"]):
            exp += f"- '{alt['source']}' deviating at {alt['onset_time']} (score: {alt['confidence_score']:.2f})\n"
            
    exp += "\nNote: This system identifies temporal correlations and candidate precursors. It does not establish definitive causation."
    return exp

def get_gemini_explanation(report):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
    prompt = (
        "You are an AI assistant for a temporal anomaly-investigation system called 'Glitch Hunter'.\n"
        "I will provide a structured JSON incident report. Rephrase it into a clear, professional narrative summary.\n"
        "CRITICAL RULES:\n"
        "1. NEVER claim causation (e.g. do not say 'X caused Y'). Only use terms like 'preceded', 'correlated with', 'candidate precursor'.\n"
        "2. Do not introduce any new facts not present in the JSON.\n"
        "JSON Data:\n"
        f"{json.dumps(report, indent=2)}"
    )
    
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Gemini API Error: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print(f"Gemini API Request failed: {e}")
        return None

def generate_explanation(incident_time, evidence_level, candidates, deviations):
    report = build_json_report(incident_time, evidence_level, candidates, deviations)
    
    explanation = get_gemini_explanation(report)
    if not explanation:
        explanation = generate_template_explanation(report)
        
    return explanation, report
