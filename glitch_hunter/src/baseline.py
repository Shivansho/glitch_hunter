import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest
from scipy.stats import median_abs_deviation
from src.features import build_features

SIGNALS = ['conveyor_speed', 'motor_vibration', 'temperature', 'motor_current', 'pressure']

class BaselineModel:
    def __init__(self, signals):
        self.signals = signals
        self.predictors = {}
        self.residual_stats = {}
        self.iso_forest = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
        
    def _get_signal_features(self, df, target_sig):
        """
        Features for a signal:
        - Other signals (current value)
        - Lags of the target signal
        """
        features = [col for col in self.signals if col != target_sig]
        features += [col for col in df.columns if col.startswith(f'{target_sig}_lag_')]
        return features

    def train(self, df):
        print("Building features for training...")
        df_feat = build_features(df, self.signals, train=True)
        
        # 1. Train per-signal context-aware model
        for sig in self.signals:
            print(f"Training model for {sig}...")
            X = df_feat[self._get_signal_features(df_feat, sig)]
            y = df_feat[sig]
            
            # Using subset of data to speed up training if needed, but 144k rows is manageable
            # Let's use 20% of data for training the predictor to save time, or use smaller max_depth
            sub_idx = np.random.choice(len(X), min(len(X), 50000), replace=False)
            model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
            model.fit(X.iloc[sub_idx], y.iloc[sub_idx])
            
            self.predictors[sig] = model
            
            # Compute residuals on all training data
            preds = model.predict(X)
            residuals = y - preds
            
            # Robust median/MAD
            med = np.median(residuals)
            # scipy median_abs_deviation defaults to non-scaled, multiply by 1.4826 for std equivalence
            mad = median_abs_deviation(residuals, scale='normal') 
            
            if mad == 0:
                mad = 1e-6
                
            self.residual_stats[sig] = {'median': med, 'mad': mad}
            
        # 2. Train IsolationForest on rolling window features
        print("Training IsolationForest...")
        iso_features = []
        for sig in self.signals:
            iso_features += [f'{sig}_mean_10s', f'{sig}_std_10s', f'{sig}_slope_10s']
            iso_features += [f'{sig}_mean_30s', f'{sig}_std_30s', f'{sig}_slope_30s']
            
        X_iso = df_feat[iso_features]
        # Fit on a subset to save time
        iso_sub_idx = np.random.choice(len(X_iso), min(len(X_iso), 50000), replace=False)
        self.iso_forest.fit(X_iso.iloc[iso_sub_idx])
        self.iso_features = iso_features
        
        print("Training complete.")
        
    def predict_residuals_and_zscore(self, df_feat):
        """
        Return df with added z_score columns for each signal.
        """
        out = pd.DataFrame(index=df_feat.index)
        for sig in self.signals:
            X = df_feat[self._get_signal_features(df_feat, sig)]
            preds = self.predictors[sig].predict(X)
            residuals = df_feat[sig] - preds
            
            med = self.residual_stats[sig]['median']
            mad = self.residual_stats[sig]['mad']
            
            z_score = (residuals - med) / mad
            out[f'{sig}_zscore'] = z_score
            
        return out
        
    def predict_isolation_forest(self, df_feat):
        """
        Return isolation forest scores. Score is scaled.
        """
        X = df_feat[self.iso_features]
        # score_samples returns negative anomaly score, lower is more anomalous
        scores = self.iso_forest.score_samples(X) 
        # invert and scale to [0,1] roughly
        scores = -scores
        # Normalize between 0 and 1 using simple min-max from training or just logistic
        return scores

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({
            'predictors': self.predictors,
            'residual_stats': self.residual_stats,
            'iso_forest': self.iso_forest,
            'iso_features': self.iso_features,
            'signals': self.signals
        }, path)
        
    @classmethod
    def load(cls, path):
        data = joblib.load(path)
        obj = cls(data['signals'])
        obj.predictors = data['predictors']
        obj.residual_stats = data['residual_stats']
        obj.iso_forest = data['iso_forest']
        obj.iso_features = data['iso_features']
        return obj

def main():
    print("Loading normal data...")
    df = pd.read_csv("data/normal.csv", parse_dates=['timestamp'])
    model = BaselineModel(SIGNALS)
    model.train(df)
    print("Saving model...")
    model.save("models/baseline.joblib")
    
if __name__ == "__main__":
    main()
