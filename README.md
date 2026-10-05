# Glitch Hunter

Glitch Hunter is an automated anomaly detection and investigation toolkit designed to identify, analyze, and report irregularities across data streams and video events. It provides a full pipeline from baseline generation and feature extraction to incident simulation, detection, and explainability.

## 🚀 Features

*   **Automated Detection:** Core algorithms to establish baselines and detect anomalies in structured data and video feeds.
*   **Video Event Processing:** Specifically handles video stream inputs to identify visual glitches and timeline incidents.
*   **Investigation & Explainability:** Digs into detected incidents to extract meaningful features and explain the root causes of the anomaly.
*   **Simulation Environment:** Built-in tools to simulate incidents for testing and model validation.
*   **API & Web Interface:** Includes a backend API and an application interface for interacting with the detection engine and viewing reports.

## 📁 Repository Structure

```text
glitch_hunter/
├── api.py                  # API endpoints for the detection service
├── app.py                  # Main application entry point
├── mock_app.html           # Frontend mock interface
├── requirements.txt        # Project dependencies
├── data/                   # Data directory (large datasets and CSVs are ignored by Git)
│   ├── ground_truth.json
│   └── (incident_*.csv, normal.csv, events_log.csv - local only)
├── src/                    # Core source code
│   ├── baseline.py         # Baseline metric calculations
│   ├── detect.py           # Anomaly detection logic
│   ├── events.py           # Event parsing and handling
│   ├── explain.py          # Interpretability and root-cause logic
│   ├── features.py         # Feature engineering and extraction
│   ├── investigate.py      # Deep-dive incident analysis
│   ├── report.py           # Automated report generation
│   ├── simulate.py         # Data and incident simulation tools
│   └── video_events.py     # Video processing and visual glitch detection
└── tests/                  # Unit and integration tests
    └── test_glitch_hunter.py
