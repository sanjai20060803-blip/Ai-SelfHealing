from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import GroupShuffleSplit

WINDOW = 6          # readings used as input (about 1 minute at 10 s per reading)
HORIZON = 6         # how many readings ahead we predict
STEP_SECONDS = 10
FORECAST_MODEL_PATH = Path(__file__).parent / "forecast_model.joblib"

METRICS = ["latency_ms", "packet_loss_pct", "jitter_ms", "bandwidth_mbps", "signal_strength"]

# Typical value of each metric at severity 0 (normal), 1 (abnormal), 2 (failure)
ANCHORS = {
    "latency_ms": (45.0, 150.0, 500.0),
    "packet_loss_pct": (0.5, 4.0, 25.0),
    "jitter_ms": (8.0, 30.0, 80.0),
    "bandwidth_mbps": (35.0, 10.0, 1.5),
    "signal_strength": (75.0, 50.0, 25.0),
}
NOISE = {
    "latency_ms": 12.0,
    "packet_loss_pct": 0.4,
    "jitter_ms": 4.0,
    "bandwidth_mbps": 4.0,
    "signal_strength": 6.0,
}
NOISE_GROWS = {"latency_ms", "packet_loss_pct", "jitter_ms"}
LIMITS = {
    "latency_ms": (1, 5000),
    "packet_loss_pct": (0, 100),
    "jitter_ms": (0, 1000),
    "bandwidth_mbps": (0, 1000),
    "signal_strength": (0, 100),
}


def _interp(anchor, s):
    s = min(max(s, 0.0), 2.0)
    if s <= 1.0:
        return anchor[0] + (anchor[1] - anchor[0]) * s
    return anchor[1] + (anchor[2] - anchor[1]) * (s - 1.0)


def _sample(rng, s):
    row = {}
    for m in METRICS:
        scale = NOISE[m] * ((1.0 + s) if m in NOISE_GROWS else 1.0)
        lo, hi = LIMITS[m]
        row[m] = float(np.clip(_interp(ANCHORS[m], s) + rng.normal(0, scale), lo, hi))
    row["connected"] = 0 if (s > 1.6 and rng.random() < 0.4) else 1
    return row


def label_of(s):
    if s < 0.6:
        return "Normal"
    if s < 1.5:
        return "Abnormal"
    return "Failure"


def _severity_path(rng, n):
    kind = rng.choice(["stable", "degrade", "sudden", "recover", "flap"],
                      p=[0.30, 0.30, 0.15, 0.15, 0.10])
    t = np.arange(n)
    if kind == "stable":
        s = np.full(n, rng.choice([0.1, 0.1, 1.0, 2.0]))
    elif kind == "degrade":
        start = rng.integers(8, 40)
        rate = rng.uniform(0.04, 0.18)
        s = np.clip(0.1 + rate * np.maximum(0, t - start + 1), 0.1, 2.0)
    elif kind == "sudden":
        start = rng.integers(15, 60)
        s = np.where(t >= start, rng.choice([1.0, 2.0]), 0.1)
    elif kind == "recover":
        start = rng.integers(8, 40)
        rate = rng.uniform(0.04, 0.18)
        s = np.clip(2.0 - rate * np.maximum(0, t - start), 0.1, 2.0)
    else:  # flap
        period = rng.integers(8, 20)
        s = np.where((t // period) % 2 == 0, 0.1, rng.choice([1.0, 2.0]))
    return np.clip(s + rng.normal(0, 0.03, n), 0.0, 2.0)


_XC = np.arange(WINDOW, dtype=float) - (WINDOW - 1) / 2.0
_XDEN = float((_XC ** 2).sum())


def feature_names():
    names = []
    for m in METRICS:
        names += [f"{m}_last", f"{m}_mean", f"{m}_std", f"{m}_slope"]
    names += ["connected_last", "connected_min"]
    return names


def window_features(values, connected):
    """values: metric -> list of WINDOW numbers (oldest first)."""
    f = []
    for m in METRICS:
        v = np.asarray(values[m], dtype=float)
        slope = float(((v - v.mean()) * _XC).sum() / _XDEN)
        f += [float(v[-1]), float(v.mean()), float(v.std()), slope]
    c = np.asarray(connected, dtype=float)
    f += [float(c[-1]), float(c.min())]
    return f


def build_dataset(n_paths=1500, length=80, seed=7):
    rng = np.random.default_rng(seed)
    X, y, current, groups = [], [], [], []
    for gid in range(n_paths):
        s = _severity_path(rng, length)
        rows = [_sample(rng, v) for v in s]
        cols = {m: [r[m] for r in rows] for m in METRICS}
        conn = [r["connected"] for r in rows]
        for t in range(WINDOW - 1, length - HORIZON, 2):
            sl = slice(t - WINDOW + 1, t + 1)
            X.append(window_features({m: cols[m][sl] for m in METRICS}, conn[sl]))
            y.append(label_of(s[t + HORIZON]))
            current.append(label_of(s[t]))
            groups.append(gid)
    return pd.DataFrame(X, columns=feature_names()), np.array(y), np.array(current), np.array(groups)


def train_and_save():
    X, y, current, groups = build_dataset()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))

    model = RandomForestClassifier(
        n_estimators=150, min_samples_leaf=3, random_state=42, n_jobs=-1
    )
    model.fit(X.iloc[train_idx], y[train_idx])

    pred = model.predict(X.iloc[test_idx])
    y_test, cur_test = y[test_idx], current[test_idx]

    print("=== Forecast model: predicts the status about 60 seconds ahead ===")
    print(classification_report(y_test, pred))
    print(f"Forecast accuracy:        {(pred == y_test).mean():.3f}")
    print(f"Naive baseline accuracy:  {(cur_test == y_test).mean():.3f} (assumes nothing changes)")
    early = (cur_test == "Normal") & (y_test != "Normal")
    if early.any():
        recall = (pred[early] != "Normal").mean()
        print(f"Early-warning recall:     {recall:.3f} of {int(early.sum())} cases that look "
              f"Normal now but degrade within 60 s (the naive baseline catches 0)")

    joblib.dump(model, FORECAST_MODEL_PATH)
    print(f"Forecast model saved to {FORECAST_MODEL_PATH}")
    return model


def load_or_train_forecast():
    if FORECAST_MODEL_PATH.exists():
        return joblib.load(FORECAST_MODEL_PATH)
    return train_and_save()


def forecast(model, history):
    """history: list of dicts (oldest first) with the 5 metrics and 'connected'."""
    h = history[-WINDOW:]
    values = {m: [float(r[m]) for r in h] for m in METRICS}
    conn = [1 if r["connected"] else 0 for r in h]
    feats = pd.DataFrame([window_features(values, conn)], columns=feature_names())

    probs = model.predict_proba(feats)[0]
    classes = list(model.classes_)
    p = dict(zip(classes, (float(x) for x in probs)))
    best = int(np.argmax(probs))
    risk = int(round(100 * (0.5 * p.get("Abnormal", 0.0) + p.get("Failure", 0.0))))

    sl = dict(zip(feature_names(), feats.iloc[0]))
    worse = (sl["latency_ms_slope"] > 6 or sl["packet_loss_pct_slope"] > 0.3
             or sl["jitter_ms_slope"] > 2 or sl["bandwidth_mbps_slope"] < -1.5)
    better = (sl["latency_ms_slope"] < -6 or sl["packet_loss_pct_slope"] < -0.3
              or sl["jitter_ms_slope"] < -2 or sl["bandwidth_mbps_slope"] > 1.5)
    trend = "worsening" if worse else ("improving" if better else "stable")

    return {
        "forecast_status": classes[best],
        "confidence": round(float(probs[best]), 4),
        "probabilities": {c: round(v, 4) for c, v in p.items()},
        "risk_score": risk,
        "trend": trend,
    }


if __name__ == "__main__":
    train_and_save()