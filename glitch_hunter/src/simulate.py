import numpy as np
import pandas as pd
import json
import os
from pathlib import Path

def setup_seed(seed=42):
    np.random.seed(seed)

def generate_normal_data(duration_sec, start_time="2024-01-01 08:00:00"):
    """
    Generate normal operating data.
    duration_sec: total seconds. 5 days * 8 hours = 144000
    """
    t = np.arange(duration_sec)
    timestamps = pd.date_range(start=start_time, periods=duration_sec, freq='s')
    
    # Base signals
    daily_cycle = np.sin(2 * np.pi * t / (8 * 3600))
    slow_drift = np.cumsum(np.random.normal(0, 0.001, duration_sec))
    
    conveyor_speed = 1.0 + np.random.normal(0, 0.02, duration_sec)
    motor_vibration = 0.5 + 0.2 * conveyor_speed + np.random.normal(0, 0.05, duration_sec)
    temperature = 50.0 + 5.0 * daily_cycle + 2.0 * slow_drift + np.random.normal(0, 0.5, duration_sec)
    motor_current = 10.0 + 2.0 * conveyor_speed + 3.0 * daily_cycle + np.random.normal(0, 0.2, duration_sec)
    pressure = 100.0 - 0.1 * temperature + np.random.normal(0, 1.0, duration_sec)
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'conveyor_speed': conveyor_speed,
        'motor_vibration': motor_vibration,
        'temperature': temperature,
        'motor_current': motor_current,
        'pressure': pressure,
        'failure': 0
    })
    return df

def generate_incident_a(df_base, t0, duration):
    """
    Incident A: speed-initiated
    speed fluctuates at t0 → vibration t0+23s → temperature t0+40s → current spike t0+46s → failure t0+49s
    """
    df = df_base.copy()
    
    # speed fluctuates
    df.loc[t0:t0+duration, 'conveyor_speed'] += np.sin(np.arange(duration+1) * 0.5) * 0.5
    
    # vibration
    df.loc[t0+23:t0+duration, 'motor_vibration'] += 1.5
    
    # temperature
    df.loc[t0+40:t0+duration, 'temperature'] += 15.0
    
    # current spike
    df.loc[t0+46:t0+duration, 'motor_current'] += 20.0
    
    # failure
    df.loc[t0+49:t0+duration, 'failure'] = 1
    
    return df

def generate_incident_b(df_base, t0, duration):
    """
    Incident B: thermal-initiated
    temperature creeps up → pressure drops → current spikes → failure
    Assume: creep over 30s -> drop at t0+30 -> current t0+45 -> failure t0+50
    """
    df = df_base.copy()
    
    # temperature creeps up
    creep_len = 30
    df.loc[t0:t0+creep_len, 'temperature'] += np.linspace(0, 20.0, creep_len+1)
    df.loc[t0+creep_len+1:t0+duration, 'temperature'] += 20.0
    
    # pressure drops
    df.loc[t0+30:t0+duration, 'pressure'] -= 25.0
    
    # current spikes
    df.loc[t0+45:t0+duration, 'motor_current'] += 25.0
    
    # failure
    df.loc[t0+50:t0+duration, 'failure'] = 1
    
    return df

def generate_incident_c(df_base, t0, duration):
    """
    Incident C: noise only
    random spikes in one signal, NO real chain
    """
    df = df_base.copy()
    
    # random spikes in pressure
    spikes = np.random.choice([0, 15.0, -15.0], size=duration+1, p=[0.9, 0.05, 0.05])
    df.loc[t0:t0+duration, 'pressure'] += spikes
    
    return df

def generate_events_log(df, num_events=1000):
    timestamps = np.random.choice(df['timestamp'], size=num_events, replace=False)
    timestamps.sort()
    
    sources = ['ZoneA_Door', 'Auth_System', 'Main_Controller', 'Maintenance_Terminal']
    messages = ['person_entered_zone', 'auth_failure', 'config_update', 'routine_check_start']
    
    events = []
    for ts in timestamps:
        src = np.random.choice(sources)
        if src == 'ZoneA_Door':
            msg = 'person_entered_zone'
        elif src == 'Auth_System':
            msg = 'auth_failure'
        elif src == 'Main_Controller':
            msg = 'config_update'
        else:
            msg = 'routine_check_start'
            
        events.append({'timestamp': ts, 'source': src, 'message': msg})
        
    return pd.DataFrame(events)

def main():
    setup_seed(42)
    os.makedirs("data", exist_ok=True)
    
    # 5 days x 8 hours = 144,000 seconds
    duration_sec = 5 * 8 * 3600
    
    print("Generating normal data...")
    df_normal = generate_normal_data(duration_sec)
    df_normal.to_csv("data/normal.csv", index=False)
    
    # Generate smaller segments for incidents (e.g. 1000 seconds)
    print("Generating incidents...")
    incident_duration = 1000
    t0_A = 200
    df_incident_a = generate_incident_a(generate_normal_data(incident_duration, start_time="2024-01-06 08:00:00"), t0_A, 100)
    df_incident_a.to_csv("data/incident_A.csv", index=False)
    
    t0_B = 200
    df_incident_b = generate_incident_b(generate_normal_data(incident_duration, start_time="2024-01-07 08:00:00"), t0_B, 100)
    df_incident_b.to_csv("data/incident_B.csv", index=False)
    
    t0_C = 200
    df_incident_c = generate_incident_c(generate_normal_data(incident_duration, start_time="2024-01-08 08:00:00"), t0_C, 100)
    df_incident_c.to_csv("data/incident_C.csv", index=False)
    
    # Ground truth JSON
    ground_truth = {
        "incident_A": {
            "initiating_signal": "conveyor_speed",
            "onset_time_str": str(df_incident_a.iloc[t0_A]['timestamp']),
            "onset_idx": t0_A,
            "description": "speed fluctuates at t0 → vibration t0+23s → temperature t0+40s → current spike t0+46s → failure t0+49s"
        },
        "incident_B": {
            "initiating_signal": "temperature",
            "onset_time_str": str(df_incident_b.iloc[t0_B]['timestamp']),
            "onset_idx": t0_B,
            "description": "temperature creeps up → pressure drops → current spikes → failure"
        },
        "incident_C": {
            "initiating_signal": None,
            "onset_time_str": None,
            "onset_idx": None,
            "description": "noise only: random spikes in pressure, NO real chain"
        }
    }
    with open("data/ground_truth.json", "w") as f:
        json.dump(ground_truth, f, indent=4)
        
    print("Generating events log...")
    # Generate events over the whole 5 day + incidents period? Just normal data is fine, 
    # but we should inject a few relevant ones near incidents for Phase 5 if needed.
    # We will generate a general log.
    df_events = generate_events_log(df_normal, num_events=5000)
    
    # Inject specific events near incident A and B just as an example
    special_events = [
        {'timestamp': df_incident_a.iloc[t0_A - 5]['timestamp'], 'source': 'Main_Controller', 'message': 'config_update'},
        {'timestamp': df_incident_b.iloc[t0_B - 60]['timestamp'], 'source': 'ZoneA_Door', 'message': 'person_entered_zone'}
    ]
    df_events = pd.concat([df_events, pd.DataFrame(special_events)], ignore_index=True)
    df_events = df_events.sort_values('timestamp')
    df_events.to_csv("data/events_log.csv", index=False)
    print("Phase 1 simulation complete.")

if __name__ == "__main__":
    main()
