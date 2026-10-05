import json
import os
import argparse
from src.investigate import investigate
from src.detect import compute_anomaly_scores, detect_incidents
from src.baseline import BaselineModel, SIGNALS
from src.features import build_features
from src.explain import generate_explanation
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Generate incident report.")
    parser.add_argument("--incident", type=str, default="incident_A", help="Incident name (e.g. incident_A)")
    args = parser.parse_args()
    
    print(f"Loading data for {args.incident}...")
    df = pd.read_csv(f"data/{args.incident}.csv", parse_dates=['timestamp'])
    
    print("Loading baseline model...")
    model = BaselineModel.load("models/baseline.joblib")
    
    print("Extracting features...")
    df_feat = build_features(df, SIGNALS, train=False).bfill()
    
    print("Computing anomaly scores...")
    combined_scores, z_scores = compute_anomaly_scores(df_feat, model)
    
    print("Detecting incident...")
    incident_time, _ = detect_incidents(df, combined_scores, threshold=0.7, n_consecutive=5)
    
    if incident_time is None:
        print("No incident detected.")
        return
        
    print(f"Incident detected at {incident_time}. Investigating...")
    candidates, evidence, deviations = investigate(df, z_scores, incident_time, SIGNALS)
    
    print("Generating report and explanation...")
    explanation, report = generate_explanation(incident_time, evidence, candidates, deviations)
    
    print("\n================ REPORT ================\n")
    print(json.dumps(report, indent=2))
    
    print("\n============= EXPLANATION ==============\n")
    print(explanation)
    
    # Save to file
    os.makedirs("reports", exist_ok=True)
    with open(f"reports/{args.incident}_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    with open(f"reports/{args.incident}_explanation.txt", "w") as f:
        f.write(explanation)
        
if __name__ == "__main__":
    main()
