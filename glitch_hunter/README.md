# AI Glitch Hunter

AI Glitch Hunter is a temporal anomaly-investigation system. It learns normal behavior from unlabeled normal data, detects an incident at time T, then works BACKWARD through the timeline to find the earliest statistically meaningful deviation and rank candidate precursor events. 

Principle: "Don't hunt the anomaly. Hunt the sequence." It must never claim causation, only "earliest correlated anomaly and candidate precursor".

## Architecture

```text
┌─────────────────┐      ┌─────────────────┐       ┌─────────────────┐
│                 │      │                 │       │                 │
│  Data Sources   ├─────►│  Feature Eng.   ├──────►│  Baseline Model │
│ (Signals/Logs)  │      │ (Windows/Lags)  │       │ (Normal only)   │
│                 │      │                 │       │                 │
└─────────────────┘      └─────────────────┘       └────────┬────────┘
                                                            │
                                                            ▼
┌─────────────────┐      ┌─────────────────┐       ┌─────────────────┐
│                 │      │                 │       │                 │
│ Explanation &   │◄─────┤ Backward CUSUM  │◄──────┤ Incident Detect │
│   Reporting     │      │   Investigation │       │ (Anomaly Score) │
│                 │      │                 │       │                 │
└─────────────────┘      └─────────────────┘       └─────────────────┘
```

## Limitations
- **No Causal Claims**: The system only establishes temporal precedence and correlation. It explicitly avoids making definitive causal statements.
- **Data Dependency**: Requires clean, unlabeled normal data to establish a solid baseline. Drift over very long periods might require periodic retraining.
- **Fixed Lookback**: By default, investigates only a 5-minute lookback window. Events originating before this window will not be linked.

## 60-Second Demo Script

1. **Start the App**: Run `streamlit run app.py`. The app will automatically simulate 5 days of normal factory data and train a baseline model (takes ~10 seconds).
2. **Scenario A (Speed)**: Select "Scenario A" from the sidebar. You will see a clear sequence where `conveyor_speed` fluctuates, followed by `motor_vibration`, `temperature`, and finally an incident. The system correctly identifies speed as the precursor.
3. **Scenario B (Thermal)**: Switch to "Scenario B". Notice how the system detects the slow temperature creep followed by a pressure drop leading to failure.
4. **Scenario C (Noise)**: Switch to "Scenario C". The system will detect random pressure spikes but correctly flag the evidence as INSUFFICIENT, avoiding false precursor attribution.
5. **JSON Report**: Click "Download JSON Report" to see the structured output generated for external systems or LLMs.

## Task List
- [x] Phase 1: Simulation
- [x] Phase 2: Baseline
- [x] Phase 3: Detection
- [x] Tests for Phase 1-3
- [x] Phase 4: Events
- [x] Phase 5: Investigation
- [x] Phase 6: Explanation
- [x] Phase 7: App
