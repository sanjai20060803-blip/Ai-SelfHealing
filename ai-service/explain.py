"""Explains WHY the AI gave its answer for one reading.

Method (plain words): for every reading we ask the model two questions.
1. "If this one value were normal, how much more normal would the whole picture look?"
2. "If everything else were normal and only this value stayed as measured, how far from normal would it look?"
The average of both answers is that reading's share of the blame. Nothing is guessed:
every number comes from asking the trained model itself.
"""
import pandas as pd

# A typical healthy value for each reading (the same values the Normal simulation uses).
BASELINE = {
    "latency_ms": 40.0,
    "packet_loss_pct": 0.5,
    "jitter_ms": 5.0,
    "bandwidth_mbps": 40.0,
    "cpu_pct": 30.0,
    "memory_pct": 50.0,
    "signal_strength": 75.0,
    "connected": 1.0,
}

LABELS = {
    "latency_ms": ("Latency", "ms"),
    "packet_loss_pct": ("Packet loss", "%"),
    "jitter_ms": ("Jitter", "ms"),
    "bandwidth_mbps": ("Bandwidth", "Mbps"),
    "cpu_pct": ("CPU use", "%"),
    "memory_pct": ("Memory use", "%"),
    "signal_strength": ("Wi-Fi signal", "%"),
    "connected": ("Connection", ""),
}

MIN_EFFECT = 0.02  # ignore readings that change the picture by less than 2 points


def explain(model, features, values, top=3):
    classes = list(model.classes_)
    i_normal = classes.index("Normal")

    def p_normal(vals):
        row = pd.DataFrame([[vals[f] for f in features]], columns=features)
        return float(model.predict_proba(row)[0][i_normal])

    actual = {f: float(values[f]) for f in features}
    base = {f: BASELINE[f] for f in features}
    p_actual = p_normal(actual)
    p_base = p_normal(base)

    effect = {}
    for f in features:
        without = dict(actual)
        without[f] = base[f]
        only = dict(base)
        only[f] = actual[f]
        removing_it_helps = p_normal(without) - p_actual
        alone_hurts = p_base - p_normal(only)
        effect[f] = 0.5 * (removing_it_helps + alone_hurts)

    blamed = {f: e for f, e in effect.items() if e > MIN_EFFECT}
    total = sum(blamed.values())

    reasons = []
    for f, e in sorted(blamed.items(), key=lambda kv: -kv[1])[:top]:
        label, unit = LABELS[f]
        reasons.append({
            "feature": f,
            "label": label,
            "unit": unit,
            "value": round(actual[f], 1),
            "typical": BASELINE[f],
            "direction": "higher" if actual[f] > BASELINE[f] else "lower",
            "share_pct": round(100 * e / total),
        })
    return reasons