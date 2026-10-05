import pandas as pd
import numpy as np

def load_events(events_path):
    """Load discrete events from events_log.csv"""
    try:
        df = pd.read_csv(events_path, parse_dates=['timestamp'])
        # Ensure it has 'source', 'type' (which we will map from 'message'), 'severity', 'magnitude'
        events = []
        for _, row in df.iterrows():
            events.append({
                'timestamp': row['timestamp'],
                'source': row['source'],
                'type': row['message'],
                'severity': 0.5, # Default severity
                'magnitude': 1.0
            })
        return pd.DataFrame(events)
    except FileNotFoundError:
        return pd.DataFrame(columns=['timestamp', 'source', 'type', 'severity', 'magnitude'])

def signal_to_events(df_signals, z_scores, signals, threshold=3.0, k=5):
    """
    Convert continuous signals with high z-scores into structured events.
    (Optional preprocessing step, but we will do onset detection dynamically in investigate.py)
    """
    events = []
    for sig in signals:
        is_anom = (np.abs(z_scores[f'{sig}_zscore']) > threshold).astype(int)
        rolling = is_anom.rolling(window=k).sum()
        starts = (rolling == k) & (rolling.shift(1) < k)
        
        for idx in starts[starts].index:
            events.append({
                'timestamp': df_signals.loc[idx, 'timestamp'],
                'source': sig,
                'type': 'signal_deviation',
                'severity': min(1.0, np.abs(z_scores.loc[idx, f'{sig}_zscore']) / 10.0),
                'magnitude': np.abs(z_scores.loc[idx, f'{sig}_zscore'])
            })
    return pd.DataFrame(events)

def get_time_aligned_stream(df_signals, z_scores, signals, events_path):
    df_logs = load_events(events_path)
    df_sig_events = signal_to_events(df_signals, z_scores, signals)
    
    df_all = pd.concat([df_logs, df_sig_events], ignore_index=True)
    if not df_all.empty:
        df_all = df_all.sort_values('timestamp').reset_index(drop=True)
    return df_all
