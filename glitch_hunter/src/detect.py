import pandas as pd
import numpy as np
import json
from src.features import build_features
from src.baseline import BaselineModel, SIGNALS

def compute_anomaly_scores(df_feat, model):
    z_scores = model.predict_residuals_and_zscore(df_feat)
    iso_scores = model.predict_isolation_forest(df_feat)
    
    # Combined score
    # Normalize z_scores to [0,1] space using a sigmoid-like function or simply max over signals
    max_z = np.abs(z_scores).max(axis=1)
    
    # max_z typically is ~0-3 for normal, >5 for anomalous
    # Let's map max_z to [0, 1) using 1 - exp(-max_z / 3)
    z_prob = 1.0 - np.exp(-max_z / 3.0)
    
    # iso_scores: isolation forest returns scores generally > 0.5 for anomalies, 
    # but we extracted it as -score_samples which is usually around 0.4-0.6 for normal, higher for anomalies.
    # Let's shift and scale it:
    # Typical iso score range: min 0.3, max 0.8.
    iso_prob = np.clip((iso_scores - 0.4) / 0.4, 0.0, 1.0)
    
    # Combine
    combined = 0.5 * z_prob + 0.5 * iso_prob
    return combined, z_scores

def detect_incidents(df, combined_scores, threshold=0.8, n_consecutive=5):
    """
    Returns the first timestamp of an incident, or None.
    An incident is score > threshold for n_consecutive seconds, or failure == 1.
    """
    above_thresh = (combined_scores > threshold).astype(int)
    rolling_sum = above_thresh.rolling(window=n_consecutive).sum()
    
    # Check threshold triggers
    trigger_idx = rolling_sum[rolling_sum >= n_consecutive].index
    
    # Check failure flag triggers
    if 'failure' in df.columns:
        failure_idx = df[df['failure'] == 1].index
    else:
        failure_idx = pd.Index([])
        
    if len(trigger_idx) == 0 and len(failure_idx) == 0:
        return None
        
    first_trigger = trigger_idx[0] if len(trigger_idx) > 0 else np.inf
    first_failure = failure_idx[0] if len(failure_idx) > 0 else np.inf
    
    idx = min(first_trigger, first_failure)
    return df.iloc[idx]['timestamp'], idx

def evaluate_detection(ground_truth_path="data/ground_truth.json"):
    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)
        
    model = BaselineModel.load("models/baseline.joblib")
    
    results = {}
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    for incident_name in ["incident_A", "incident_B", "incident_C"]:
        df = pd.read_csv(f"data/{incident_name}.csv", parse_dates=['timestamp'])
        # Build features without dropping NaN to preserve timeline, 
        # but the first few rows will have NaN features. 
        # We can fill them with 0 or drop them. 
        # Dropping will shift index. Let's bfill them.
        df_feat = build_features(df, SIGNALS, train=False).bfill()
        
        combined_scores, z_scores = compute_anomaly_scores(df_feat, model)
        
        incident_time, incident_idx = detect_incidents(df, combined_scores, threshold=0.7, n_consecutive=5)
        
        gt = ground_truth[incident_name]
        is_true_incident = gt["onset_time_str"] is not None
        
        predicted = incident_time is not None
        
        results[incident_name] = {
            "predicted_time": str(incident_time) if incident_time else None,
            "ground_truth_time": gt["onset_time_str"],
            "correct": predicted == is_true_incident
        }
        
        if is_true_incident and predicted:
            true_positives += 1
        elif is_true_incident and not predicted:
            false_negatives += 1
        elif not is_true_incident and predicted:
            false_positives += 1
            
    # For normal data, we should test false positives.
    print("Testing on normal data for false positives...")
    df_normal = pd.read_csv("data/normal.csv", parse_dates=['timestamp'])
    # Only test on a subset to save time
    df_normal_sub = df_normal.iloc[:10000].copy()
    df_feat_normal = build_features(df_normal_sub, SIGNALS, train=False).bfill()
    comb, _ = compute_anomaly_scores(df_feat_normal, model)
    time, idx = detect_incidents(df_normal_sub, comb, threshold=0.7, n_consecutive=5)
    
    if time is not None:
        false_positives += 1
        print(f"False positive found in normal data at {time}")
        
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    
    print("\nDetection Results:")
    for k, v in results.items():
        print(f"{k}: predicted={v['predicted_time']} (GT={v['ground_truth_time']}) - Correct: {v['correct']}")
    print(f"\nPrecision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")

if __name__ == "__main__":
    evaluate_detection()
