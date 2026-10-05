import pandas as pd
import numpy as np

def compute_slope(y):
    # compute linear slope of y over the window
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y))
    # Using simple covariance/variance formula for slope
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean)**2)
    if denominator == 0:
        return 0.0
    return numerator / denominator

def extract_rolling_features(df, signals, windows=[10, 30]):
    """
    Compute rolling mean, std, and slope for the specified signals and windows.
    Returns a dataframe with the new features appended.
    """
    df_feat = df.copy()
    
    # We assume 'timestamp' is sorted and spaced by 1s.
    for sig in signals:
        for w in windows:
            # rolling mean and std
            df_feat[f'{sig}_mean_{w}s'] = df[sig].rolling(window=w, min_periods=w).mean()
            df_feat[f'{sig}_std_{w}s'] = df[sig].rolling(window=w, min_periods=w).std()
            
            # rolling slope (can be slow with apply, let's use a faster approx or just apply)
            # using apply is ok since data is ~144k rows, but could take a few seconds
            # Actually, let's vectorize slope computation
            # slope = (cov(x,y) / var(x)) where x is 0..w-1
            # For a fixed window w, x is [0, 1, ..., w-1]
            x = np.arange(w)
            x_mean = (w - 1) / 2.0
            x_var = np.sum((x - x_mean)**2)
            
            def slope_func(y_arr):
                return np.sum((x - x_mean) * (y_arr - np.mean(y_arr))) / x_var
                
            # df_feat[f'{sig}_slope_{w}s'] = df[sig].rolling(window=w, min_periods=w).apply(slope_func, raw=True)
            # A faster way: 
            # cov(x,y) = mean(x*y) - mean(x)mean(y)
            # x is [-(w-1)/2, ..., (w-1)/2]
            # so mean(x) = 0
            # sum(x*y) = sum_{i=0}^{w-1} (i - (w-1)/2) * y_i
            # This is a convolution. Let's build the kernel:
            kernel = np.arange(w) - (w - 1) / 2.0
            kernel = kernel / x_var
            
            # Apply 1D convolution (valid padding means we get w-1 less points, we want full/same with nan padding)
            # using np.convolve with mode='valid', then pad with nans
            slopes = np.convolve(df[sig].values, kernel[::-1], mode='valid')
            padded_slopes = np.concatenate((np.full(w-1, np.nan), slopes))
            df_feat[f'{sig}_slope_{w}s'] = padded_slopes

    return df_feat

def create_lagged_features(df, signals, lags=[1, 2, 5]):
    """
    Create lagged versions of signals.
    """
    df_feat = df.copy()
    for sig in signals:
        for lag in lags:
            df_feat[f'{sig}_lag_{lag}'] = df[sig].shift(lag)
    return df_feat

def build_features(df, signals, train=False):
    """
    Wrapper to build all features.
    If train=True, it will drop rows with NaN values.
    """
    df = extract_rolling_features(df, signals, windows=[10, 30])
    df = create_lagged_features(df, signals, lags=[1, 2, 5])
    if train:
        df = df.dropna().reset_index(drop=True)
    return df
