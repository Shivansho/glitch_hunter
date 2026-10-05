import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import sys
import time

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.features import build_features
from src.baseline import BaselineModel, SIGNALS
from src.detect import compute_anomaly_scores, detect_incidents
from src.investigate import investigate
from src.explain import generate_explanation

# Dark professional theme is handled by Streamlit config and setting page config
st.set_page_config(
    page_title="AI Glitch Hunter",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark theme adjustments and professional look
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .status-banner {
        padding: 20px;
        border-radius: 10px;
        background-color: #1e2129;
        margin-bottom: 20px;
        border-left: 5px solid #ff4b4b;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #ff4b4b;
    }
    .metric-label {
        font-size: 14px;
        color: #a0aab5;
    }
    .evidence-STRONG { color: #00cc66; font-weight: bold; font-size: 18px; }
    .evidence-MODERATE { color: #ffcc00; font-weight: bold; font-size: 18px; }
    .evidence-INSUFFICIENT { color: #ff4b4b; font-weight: bold; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def load_model():
    if os.path.exists("models/baseline.joblib"):
        return BaselineModel.load("models/baseline.joblib")
    return None

def main():
    st.sidebar.title("🕵️ AI Glitch Hunter")
    
    # Run simulation if data doesn't exist
    if not os.path.exists("data/normal.csv") or not os.path.exists("models/baseline.joblib"):
        st.warning("Data or model not found. Simulating data and training baseline...")
        import src.simulate
        import src.baseline
        src.simulate.main()
        src.baseline.main()
        st.success("Simulation and training complete!")
        time.sleep(1)
        st.rerun()

    model = load_model()
    
    st.sidebar.header("Configuration")
    data_source = st.sidebar.radio("Data Source", ["Scenario A (Speed)", "Scenario B (Thermal)", "Scenario C (Noise)", "Upload CSV"])
    
    df = None
    if data_source.startswith("Scenario"):
        incident_map = {"Scenario A (Speed)": "incident_A", "Scenario B (Thermal)": "incident_B", "Scenario C (Noise)": "incident_C"}
        incident_name = incident_map[data_source]
        try:
            df = pd.read_csv(f"data/{incident_name}.csv", parse_dates=['timestamp'])
        except FileNotFoundError:
            st.error(f"Could not find data/{incident_name}.csv")
    else:
        uploaded_file = st.sidebar.file_uploader("Upload continuous data (CSV)", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file, parse_dates=['timestamp'])
            
    threshold = st.sidebar.slider("Anomaly Score Threshold", 0.0, 1.0, 0.7, 0.05)
    lookback = st.sidebar.slider("Lookback Window (seconds)", 60, 600, 300, 30)
    include_video = st.sidebar.checkbox("Include Video Events (Zone Entry/Motion)", value=False)
    
    st.title("AI Glitch Hunter Dashboard")
    
    tab1, tab2 = st.tabs(["Investigation", "Evaluation"])
    
    with tab1:
        if df is not None and model is not None:
            with st.spinner("Analyzing data..."):
                df_feat = build_features(df, SIGNALS, train=False).bfill()
                combined_scores, z_scores = compute_anomaly_scores(df_feat, model)
                incident_time, incident_idx = detect_incidents(df, combined_scores, threshold=threshold, n_consecutive=5)
                
            if incident_time is None:
                st.info("No incident detected in the data stream.")
                
                # Still show plot
                fig = make_subplots(rows=len(SIGNALS), cols=1, shared_xaxes=True, vertical_spacing=0.02)
                for i, sig in enumerate(SIGNALS):
                    fig.add_trace(go.Scatter(x=df['timestamp'], y=df[sig], name=sig, line=dict(color="#1f77b4")), row=i+1, col=1)
                fig.update_layout(height=800, template="plotly_dark", title_text="Signal Data")
                st.plotly_chart(fig, use_container_width=True)
            else:
                video_events = None
                if include_video and df is not None:
                    from src.video_events import VideoAnalyzer, simulate_video_for_incident
                    vid_path = f"data/{data_source.split()[1] if 'Scenario' in data_source else 'uploaded'}_video.mp4"
                    if not os.path.exists(vid_path):
                        with st.spinner("Simulating video data for analysis..."):
                            simulate_video_for_incident(vid_path, df['timestamp'].iloc[0], len(df), incident_time, fps=10)
                    with st.spinner("Analyzing video for motion & zone entry..."):
                        analyzer = VideoAnalyzer(vid_path, df['timestamp'].iloc[0])
                        video_events = analyzer.analyze()
                        
                candidates, evidence, deviations = investigate(df, z_scores, incident_time, SIGNALS, df_events=video_events, lookback_sec=lookback)
                explanation, report = generate_explanation(incident_time, evidence, candidates, deviations)
                
                earliest_dev = candidates[0]['onset_time'] if candidates else None
                lead_time = candidates[0]['lead_time'] if candidates else 0
                incident_score = combined_scores.iloc[incident_idx]
                
                # Status Banner
                st.markdown(f"""
                <div class="status-banner">
                    <div style="display: flex; justify-content: space-between;">
                        <div>
                            <div class="metric-label">Incident Time</div>
                            <div class="metric-value">{incident_time}</div>
                        </div>
                        <div>
                            <div class="metric-label">Anomaly Score</div>
                            <div class="metric-value">{incident_score:.2f}</div>
                        </div>
                        <div>
                            <div class="metric-label">Earliest Deviation</div>
                            <div class="metric-value">{earliest_dev if earliest_dev else 'N/A'}</div>
                        </div>
                        <div>
                            <div class="metric-label">Lead Time</div>
                            <div class="metric-value">{lead_time:.1f}s</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("Multi-Signal Analysis")
                    # Plotly chart
                    fig = make_subplots(rows=len(SIGNALS), cols=1, shared_xaxes=True, vertical_spacing=0.02, subplot_titles=SIGNALS)
                    for i, sig in enumerate(SIGNALS):
                        fig.add_trace(go.Scatter(x=df['timestamp'], y=df[sig], name=sig, line=dict(color="#1f77b4")), row=i+1, col=1)
                        
                        # Add onset marker if exists
                        if sig in deviations:
                            onset = deviations[sig]['onset_time']
                            val = df.loc[df['timestamp'] == onset, sig].values[0]
                            fig.add_trace(go.Scatter(x=[onset], y=[val], mode='markers', marker=dict(color='yellow', size=10, symbol='star'), name=f"{sig} onset"), row=i+1, col=1)
                            
                        # Incident line
                        fig.add_vline(x=incident_time, line_width=2, line_dash="dash", line_color="red", row=i+1, col=1)
                        
                    fig.update_layout(height=800, template="plotly_dark", showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig, use_container_width=True)
                    
                with col2:
                    st.subheader("Timeline & Evidence")
                    st.markdown(f"Evidence Level: <span class='evidence-{evidence}'>{evidence}</span>", unsafe_allow_html=True)
                    
                    if len(candidates) > 0:
                        st.markdown("#### Candidate Precursors")
                        cand_df = pd.DataFrame([{
                            "Source": c['source'],
                            "Lead Time (s)": f"{c['lead_time']:.1f}",
                            "Score": f"{c['score']:.2f}",
                            "Prox": f"{c['components']['proximity']:.2f}",
                            "Mag": f"{c['components']['magnitude']:.2f}",
                            "Pers": f"{c['components']['persistence']:.2f}",
                            "Cross": f"{c['components']['cross_agreement']:.2f}"
                        } for c in candidates])
                        st.dataframe(cand_df, hide_index=True)
                        
                        st.markdown("#### Incident Timeline")
                        # Vertical timeline +Ns
                        t0 = candidates[0]['onset_time']
                        timeline = []
                        for c in sorted(candidates, key=lambda x: x['onset_time']):
                            offset = (c['onset_time'] - t0).total_seconds()
                            timeline.append(f"**+{offset:.0f}s**: {c['source']} deviated")
                        
                        inc_offset = (incident_time - t0).total_seconds()
                        timeline.append(f"**+{inc_offset:.0f}s**: **INCIDENT DETECTED**")
                        
                        for step in timeline:
                            st.markdown(step)
                            
                    else:
                        st.warning("No significant precursors found.")
                        
                    st.markdown("#### Explanation")
                    st.info(explanation)
                    
                    report_json = json.dumps(report, indent=2)
                    st.download_button("Download JSON Report", data=report_json, file_name=f"report_{report['incident_id']}.json", mime="application/json")
                    
    with tab2:
        st.header("Evaluation against Ground Truth")
        if st.button("Run Full Evaluation"):
            try:
                with open("data/ground_truth.json", "r") as f:
                    gt = json.load(f)
                    
                results = []
                for inc_name in ["incident_A", "incident_B", "incident_C"]:
                    df_inc = pd.read_csv(f"data/{inc_name}.csv", parse_dates=['timestamp'])
                    df_feat_inc = build_features(df_inc, SIGNALS, train=False).bfill()
                    comb, z = compute_anomaly_scores(df_feat_inc, model)
                    inc_t, _ = detect_incidents(df_inc, comb, threshold=threshold, n_consecutive=5)
                    
                    true_sig = gt[inc_name]["initiating_signal"]
                    true_onset = gt[inc_name]["onset_time_str"]
                    
                    if inc_t is not None:
                        cands, ev, devs = investigate(df_inc, z, inc_t, SIGNALS, lookback_sec=lookback)
                        pred_sig = cands[0]['source'] if cands else None
                        pred_onset = str(cands[0]['onset_time']) if cands else None
                        if true_onset and pred_onset:
                            err = abs((pd.to_datetime(pred_onset) - pd.to_datetime(true_onset)).total_seconds())
                        else:
                            err = None
                    else:
                        pred_sig = None
                        err = None
                        ev = "INSUFFICIENT"
                        
                    results.append({
                        "Scenario": inc_name,
                        "True Signal": true_sig,
                        "Predicted Signal": pred_sig,
                        "Correct Signal": true_sig == pred_sig,
                        "Onset Error (s)": err,
                        "Evidence": ev
                    })
                    
                res_df = pd.DataFrame(results)
                st.dataframe(res_df)
                
                correct_pct = res_df["Correct Signal"].mean() * 100
                valid_errs = res_df["Onset Error (s)"].dropna()
                mean_err = valid_errs.mean() if not valid_errs.empty else np.nan
                
                st.metric("Signal Accuracy", f"{correct_pct:.0f}%")
                st.metric("Mean Onset Error", f"{mean_err:.1f}s" if pd.notnull(mean_err) else "N/A")
                
            except Exception as e:
                st.error(f"Evaluation failed: {e}")

if __name__ == "__main__":
    main()
