import pytest
import pandas as pd
import json
import os
from src.features import build_features
from src.baseline import BaselineModel, SIGNALS
from src.detect import compute_anomaly_scores, detect_incidents
from src.investigate import investigate
from src.explain import generate_explanation

@pytest.fixture(scope="module")
def setup_data_and_model():
    # Assume simulate and baseline have been run and files exist
    assert os.path.exists("data/normal.csv")
    assert os.path.exists("models/baseline.joblib")
    
    with open("data/ground_truth.json", "r") as f:
        ground_truth = json.load(f)
        
    model = BaselineModel.load("models/baseline.joblib")
    return model, ground_truth

def run_incident_pipeline(model, incident_name):
    df = pd.read_csv(f"data/{incident_name}.csv", parse_dates=['timestamp'])
    
    # 1. Feature extraction
    df_feat = build_features(df, SIGNALS, train=False).bfill()
    
    # 2. Detect incident
    combined_scores, z_scores = compute_anomaly_scores(df_feat, model)
    incident_time, _ = detect_incidents(df, combined_scores, threshold=0.7, n_consecutive=5)
    
    if incident_time is None:
        return None, None, None, None
        
    # 3. Investigate
    # We will pass empty events for now
    candidates, evidence, deviations = investigate(
        df=df,
        z_scores=z_scores,
        incident_time=incident_time,
        signals=SIGNALS,
        df_events=None,
        lookback_sec=300
    )
    
    return incident_time, candidates, evidence, deviations

def test_incident_a(setup_data_and_model):
    model, gt = setup_data_and_model
    
    incident_time, candidates, evidence, deviations = run_incident_pipeline(model, "incident_A")
    
    assert incident_time is not None, "Incident A should be detected"
    
    true_onset_idx = gt["incident_A"]["onset_idx"]
    true_signal = gt["incident_A"]["initiating_signal"]
    
    # Check that we have STRONG or MODERATE evidence
    assert evidence in ["STRONG", "MODERATE"]
    
    # Check that the earliest precursor is the true signal
    assert len(candidates) > 0
    top_candidate = candidates[0]
    assert top_candidate["source"] == true_signal
    
    # Check that onset idx is within tolerance (e.g. 5 seconds)
    onset_diff = abs(top_candidate["onset_idx"] - true_onset_idx)
    assert onset_diff <= 10, f"Onset index off by {onset_diff}"

def test_incident_b(setup_data_and_model):
    model, gt = setup_data_and_model
    
    incident_time, candidates, evidence, deviations = run_incident_pipeline(model, "incident_B")
    
    assert incident_time is not None, "Incident B should be detected"
    
    true_onset_idx = gt["incident_B"]["onset_idx"]
    true_signal = gt["incident_B"]["initiating_signal"]
    
    assert evidence in ["STRONG", "MODERATE"]
    
    assert len(candidates) > 0
    top_candidate = candidates[0]
    assert top_candidate["source"] == true_signal
    
    onset_diff = abs(top_candidate["onset_idx"] - true_onset_idx)
    assert onset_diff <= 15, f"Onset index off by {onset_diff}"

def test_incident_c(setup_data_and_model):
    model, gt = setup_data_and_model
    
    incident_time, candidates, evidence, deviations = run_incident_pipeline(model, "incident_C")
    
    if incident_time is not None:
        # If an incident is detected on noise, the investigation should yield INSUFFICIENT
        # because the score from temporal proximity, cross-sensor agreement, etc. should be low.
        assert evidence == "INSUFFICIENT"
    else:
        # It's also fine if it's not detected as an incident at all (due to smoothing)
        assert incident_time is None
