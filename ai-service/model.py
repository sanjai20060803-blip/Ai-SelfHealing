from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

FEATURES = [
    "latency_ms",
    "packet_loss_pct",
    "jitter_ms",
    "bandwidth_mbps",
    "cpu_pct",
    "memory_pct",
    "signal_strength",
    "connected",
]
MODEL_PATH = Path(__file__).parent / "model.joblib"


def _block(rng, n, label, p):
    """Make n rows of fake metrics. p holds (mean, std) for each feature."""
    df = pd.DataFrame({
        "latency_ms": rng.normal(*p["latency"], n).clip(1, None),
        "packet_loss_pct": rng.normal(*p["loss"], n).clip(0, 100),
        "jitter_ms": rng.normal(*p["jitter"], n).clip(0, None),
        "bandwidth_mbps": rng.normal(*p["bw"], n).clip(0, None),
        "cpu_pct": rng.normal(*p["cpu"], n).clip(0, 100),
        "memory_pct": rng.normal(*p["mem"], n).clip(0, 100),
        "signal_strength": rng.normal(*p["signal"], n).clip(0, 100),
        "connected": (rng.random(n) < p["conn_prob"]).astype(int),
    })
    df["label"] = label
    return df


def generate_data(seed=42):
    rng = np.random.default_rng(seed)
    # CPU and memory overlap heavily between classes, so the model
    # relies mainly on the real network metrics.
    normal = _block(rng, 600, "Normal", dict(
        latency=(45, 18), loss=(0.5, 0.5), jitter=(8, 6), bw=(35, 15),
        cpu=(35, 20), mem=(60, 20), signal=(75, 12), conn_prob=1.0))
    abnormal = _block(rng, 400, "Abnormal", dict(
        latency=(150, 50), loss=(4, 2), jitter=(30, 12), bw=(10, 5),
        cpu=(50, 22), mem=(65, 20), signal=(50, 12), conn_prob=1.0))
    failure = _block(rng, 400, "Failure", dict(
        latency=(500, 200), loss=(25, 12), jitter=(80, 30), bw=(1.5, 1.2),
        cpu=(55, 25), mem=(70, 20), signal=(25, 12), conn_prob=0.4))
    data = pd.concat([normal, abnormal, failure], ignore_index=True)
    return data.sample(frac=1, random_state=seed).reset_index(drop=True)


def train_and_save():
    data = generate_data()
    X = data[FEATURES]
    y = data["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    model = RandomForestClassifier(n_estimators=150, random_state=42)
    model.fit(X_train, y_train)
    print(classification_report(y_test, model.predict(X_test)))
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    return model


def load_or_train():
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return train_and_save()


if __name__ == "__main__":
    train_and_save()