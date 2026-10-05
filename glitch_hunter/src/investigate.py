import pandas as pd
import numpy as np

def run_cusum(z_series, drift=0.5):
    """
    Standard forward CUSUM on z-scores to find exact onset.
    z_series: absolute z-scores.
    Returns the index of the onset (where CUSUM > 0 and starts growing).
    """
    S = np.zeros(len(z_series))
    for i in range(1, len(z_series)):
        S[i] = max(0, S[i-1] + z_series.iloc[i] - drift)
        
    # Find where S becomes > 0 and stays > 0
    # The true onset is the last time S was 0 before a big increase
    # Let's find the max CUSUM point, and trace back to 0.
    max_idx = np.argmax(S)
    if S[max_idx] == 0:
        return None # No shift detected
        
    # Trace back to the last zero before max_idx
    for i in range(max_idx, -1, -1):
        if S[i] == 0:
            return z_series.index[i]
            
    return z_series.index[0]

def find_deviations(df_lookback, z_scores_lookback, signals, threshold=3.0, k=3):
    """
    Find onset for each signal in the lookback window.
    """
    deviations = {}
    
    for sig in signals:
        z = z_scores_lookback[f'{sig}_zscore']
        abs_z = np.abs(z)
        
        is_anom = (abs_z > threshold).astype(int)
        rolling = is_anom.rolling(window=k).sum()
        
        # Find first time it persists for k
        starts = rolling[rolling >= k]
        if len(starts) > 0:
            # We have a candidate, let's refine with CUSUM up to this point
            candidate_idx = starts.index[0]
            # Provide CUSUM on a window before this candidate to find exact onset
            z_sub = abs_z.loc[:candidate_idx]
            onset_idx = run_cusum(z_sub, drift=1.0)
            if onset_idx is None:
                onset_idx = candidate_idx
            
            # magnitude: max z-score after onset
            mag = abs_z.loc[onset_idx:candidate_idx].max()
            persistence = (abs_z.loc[onset_idx:] > threshold).mean() # % of time above threshold after onset
            
            deviations[sig] = {
                'onset_time': df_lookback.loc[onset_idx, 'timestamp'],
                'onset_idx': onset_idx,
                'magnitude': mag,
                'persistence': persistence
            }
            
    return deviations

def score_candidates(deviations, incident_time, df_events_lookback=None):
    """
    Score candidates based on:
    - temporal precedence/proximity
    - magnitude
    - persistence
    - cross-sensor agreement (how many other signals deviated shortly after)
    """
    candidates = []
    
    # We treat each signal's onset as a candidate precursor
    for sig, info in deviations.items():
        # Proximity: closer to incident is better, but needs some lead time. 
        # Time difference in seconds
        delta_t = (incident_time - info['onset_time']).total_seconds()
        
        if delta_t <= 0:
            continue # Must precede incident
            
        # P(event -> incident) components
        # 1. Proximity score: decays with distance, but too close is also bad if it's part of the failure itself.
        # Let's say optimal lead time is 10-60 seconds.
        prox_score = np.exp(-abs(delta_t - 30) / 30.0)
        
        # 2. Magnitude score: 1.0 - exp(-mag/5)
        mag_score = 1.0 - np.exp(-info['magnitude'] / 5.0)
        
        # 3. Persistence: already in [0,1]
        pers_score = info['persistence']
        
        # 4. Cross-sensor agreement: fraction of other signals that deviated AFTER this one but BEFORE incident
        subsequent_devs = sum(1 for s, i in deviations.items() if s != sig and info['onset_time'] < i['onset_time'] < incident_time)
        cross_score = subsequent_devs / (len(deviations) - 1) if len(deviations) > 1 else 0
        
        total_score = 0.3 * prox_score + 0.3 * mag_score + 0.2 * pers_score + 0.2 * cross_score
        
        candidates.append({
            'source': sig,
            'onset_time': info['onset_time'],
            'onset_idx': info['onset_idx'],
            'lead_time': delta_t,
            'components': {
                'proximity': prox_score,
                'magnitude': mag_score,
                'persistence': pers_score,
                'cross_agreement': cross_score
            },
            'score': total_score
        })
        
    # Also score discrete events if any
    if df_events_lookback is not None:
        for _, row in df_events_lookback.iterrows():
            delta_t = (incident_time - row['timestamp']).total_seconds()
            if delta_t <= 0:
                continue
                
            prox_score = np.exp(-abs(delta_t - 60) / 60.0) # Discrete events might have longer lead time
            mag_score = row.get('severity', 0.5)
            pers_score = 1.0 # Discrete event is instant but persistent in effect
            
            # Cross agreement: how many signals deviated after this event
            subsequent_devs = sum(1 for s, i in deviations.items() if row['timestamp'] < i['onset_time'] < incident_time)
            cross_score = subsequent_devs / len(deviations) if len(deviations) > 0 else 0
            
            total_score = 0.3 * prox_score + 0.3 * mag_score + 0.2 * pers_score + 0.2 * cross_score
            
            candidates.append({
                'source': f"{row['source']} ({row['type']})",
                'onset_time': row['timestamp'],
                'onset_idx': -1,
                'lead_time': delta_t,
                'components': {
                    'proximity': prox_score,
                    'magnitude': mag_score,
                    'persistence': pers_score,
                    'cross_agreement': cross_score
                },
                'score': total_score
            })
            
    # Sort candidates by onset time (earliest first), or score?
    # The prompt: "rank candidates and choose the earliest meaningful deviation"
    # Meaningful means score > some threshold.
    meaningful_threshold = 0.4
    meaningful_candidates = [c for c in candidates if c['score'] >= meaningful_threshold]
    
    # Sort by time to find the earliest
    meaningful_candidates.sort(key=lambda x: x['onset_time'])
    
    # Label evidence
    if len(meaningful_candidates) == 0:
        evidence = "INSUFFICIENT"
    else:
        # Check if we have multiple independent signals
        sources = set([c['source'] for c in meaningful_candidates])
        if len(sources) > 1:
            evidence = "STRONG"
        else:
            evidence = "MODERATE"
            
    # Return top ranked by time, but also we can output the 2nd and 3rd.
    return meaningful_candidates, evidence

def investigate(df, z_scores, incident_time, signals, df_events=None, lookback_sec=300):
    # Filter 5-minute lookback
    lookback_start = incident_time - pd.Timedelta(seconds=lookback_sec)
    
    mask = (df['timestamp'] >= lookback_start) & (df['timestamp'] <= incident_time)
    df_lookback = df[mask]
    z_lookback = z_scores[mask]
    
    events_lookback = None
    if df_events is not None and not df_events.empty:
        mask_ev = (df_events['timestamp'] >= lookback_start) & (df_events['timestamp'] <= incident_time)
        events_lookback = df_events[mask_ev]
        
    deviations = find_deviations(df_lookback, z_lookback, signals)
    
    candidates, evidence = score_candidates(deviations, incident_time, events_lookback)
    
    return candidates, evidence, deviations
