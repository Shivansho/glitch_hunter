import cv2
import numpy as np
import pandas as pd
from datetime import timedelta
import os

class VideoAnalyzer:
    def __init__(self, video_path, start_time, zone_rect=None):
        """
        video_path: path to video
        start_time: pd.Timestamp of the first frame
        zone_rect: tuple (x, y, w, h) defining the restricted zone
        """
        self.video_path = video_path
        self.start_time = start_time
        # Default zone: right half of the frame
        self.zone_rect = zone_rect 
        
    def analyze(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"Error opening video {self.video_path}")
            return pd.DataFrame(columns=['timestamp', 'source', 'type', 'severity', 'magnitude'])
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or np.isnan(fps):
            fps = 30.0
            
        fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
        
        events = []
        frame_idx = 0
        
        # Read first frame to set default zone if None
        ret, frame = cap.read()
        if not ret:
            return pd.DataFrame(columns=['timestamp', 'source', 'type', 'severity', 'magnitude'])
            
        if self.zone_rect is None:
            h, w = frame.shape[:2]
            self.zone_rect = (w // 2, 0, w // 2, h)
            
        x, y, zw, zh = self.zone_rect
        
        # Reset and process
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        in_zone_active = False
        motion_active = False
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            current_time = self.start_time + timedelta(seconds=frame_idx / fps)
            
            fgmask = fgbg.apply(frame)
            # Threshold to remove shadows (which are 127)
            _, fgmask = cv2.threshold(fgmask, 250, 255, cv2.THRESH_BINARY)
            
            # General motion detection
            motion_pixels = cv2.countNonZero(fgmask)
            is_motion = motion_pixels > 500
            
            if is_motion and not motion_active:
                events.append({
                    'timestamp': current_time,
                    'source': 'Camera_1',
                    'type': 'motion_detected',
                    'severity': 0.3,
                    'magnitude': motion_pixels / (frame.shape[0] * frame.shape[1])
                })
                motion_active = True
            elif not is_motion:
                motion_active = False
                
            # Zone entry detection
            zone_mask = fgmask[y:y+zh, x:x+zw]
            zone_pixels = cv2.countNonZero(zone_mask)
            is_in_zone = zone_pixels > 200
            
            if is_in_zone and not in_zone_active:
                events.append({
                    'timestamp': current_time,
                    'source': 'Camera_1',
                    'type': 'zone_entry',
                    'severity': 0.8, # High severity for zone entry
                    'magnitude': zone_pixels / (zw * zh)
                })
                in_zone_active = True
            elif not is_in_zone:
                in_zone_active = False
                
            frame_idx += 1
            
        cap.release()
        
        df_events = pd.DataFrame(events)
        if df_events.empty:
            df_events = pd.DataFrame(columns=['timestamp', 'source', 'type', 'severity', 'magnitude'])
        return df_events

def simulate_video_for_incident(out_path, start_time, duration_sec, incident_time, fps=10):
    """
    Creates a simulated video with a moving object entering a zone before the incident.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    w, h = 320, 240
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    
    # Event times
    time_to_incident = (incident_time - start_time).total_seconds()
    # Let's say person enters zone 60 seconds before incident
    entry_start = max(0, time_to_incident - 60)
    entry_end = entry_start + 10
    
    for i in range(int(duration_sec * fps)):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        
        current_sec = i / fps
        
        # Draw zone
        cv2.rectangle(frame, (w//2, 0), (w, h), (50, 50, 50), -1)
        
        if entry_start <= current_sec <= entry_end:
            # Draw moving object going into the zone
            progress = (current_sec - entry_start) / (entry_end - entry_start)
            obj_x = int(w * 0.2 + progress * (w * 0.6))
            obj_y = h // 2
            cv2.circle(frame, (obj_x, obj_y), 20, (255, 255, 255), -1)
            
        out.write(frame)
        
    out.release()
    return out_path
