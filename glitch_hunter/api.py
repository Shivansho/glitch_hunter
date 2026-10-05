import os
import json
import pandas as pd
import numpy as np
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# Ensure src is in path
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.features import build_features
from src.baseline import BaselineModel, SIGNALS
from src.detect import compute_anomaly_scores, detect_incidents
from src.investigate import investigate
from src.explain import generate_explanation

app = FastAPI(title="AI Glitch Hunter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = None
try:
    if os.path.exists("models/baseline.joblib"):
        model = BaselineModel.load("models/baseline.joblib")
except Exception as e:
    print(f"Failed to load model: {e}")

@app.get("/", response_class=FileResponse)
async def read_index():
    return FileResponse("mock_app.html")

@app.get("/api/analyze")
async def analyze_scenario(scenario: str, threshold: float = 0.7, lookback: int = 300):
    global model
    if model is None:
        return JSONResponse(status_code=500, content={"error": "Model not loaded. Run simulation first."})
        
    incident_map = {
        "Scenario A (Speed)": "incident_A", 
        "Scenario B (Thermal)": "incident_B", 
        "Scenario C (Noise)": "incident_C"
    }
    
    incident_name = incident_map.get(scenario)
    if not incident_name:
        return JSONResponse(status_code=400, content={"error": "Invalid scenario"})
        
    try:
        df = pd.read_csv(f"data/{incident_name}.csv", parse_dates=['timestamp'])
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"error": f"Data file for {incident_name} not found"})

    # Run pipeline
    df_feat = build_features(df, SIGNALS, train=False).bfill()
    combined_scores, z_scores = compute_anomaly_scores(df_feat, model)
    incident_time, incident_idx = detect_incidents(df, combined_scores, threshold=threshold, n_consecutive=5)
    
    if incident_time is None:
        return {
            "incident_detected": False,
            "plot_data": get_plot_data(df, None, {})
        }
        
    candidates, evidence, deviations = investigate(df, z_scores, incident_time, SIGNALS, lookback_sec=lookback)
    explanation, report = generate_explanation(incident_time, evidence, candidates, deviations)
    
    earliest_dev = str(candidates[0]['onset_time']) if candidates else None
    lead_time = candidates[0]['lead_time'] if candidates else 0.0
    incident_score = float(combined_scores.iloc[incident_idx])
    
    return {
        "incident_detected": True,
        "incident_time": str(incident_time),
        "anomaly_score": incident_score,
        "earliest_deviation": earliest_dev,
        "lead_time": lead_time,
        "evidence_level": evidence,
        "candidates": candidates,
        "deviations": deviations,
        "explanation": explanation,
        "report": report,
        "plot_data": get_plot_data(df, incident_time, deviations)
    }

def get_plot_data(df, incident_time, deviations):
    # Simplify dataframe for plotting to reduce JSON size if needed
    # Here we'll just send the full arrays
    traces = []
    
    for sig in SIGNALS:
        traces.append({
            "name": sig,
            "x": df['timestamp'].astype(str).tolist(),
            "y": df[sig].tolist(),
            "type": "scatter",
            "mode": "lines"
        })
        
        if sig in deviations:
            onset = deviations[sig]['onset_time']
            val = float(df.loc[df['timestamp'] == onset, sig].values[0])
            traces.append({
                "name": f"{sig} onset",
                "x": [str(onset)],
                "y": [val],
                "type": "scatter",
                "mode": "markers",
                "marker": {"color": "yellow", "size": 10, "symbol": "star"}
            })
            
    return {
        "traces": traces,
        "incident_time": str(incident_time) if incident_time else None
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
