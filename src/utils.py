"""
Utility Functions
=================
Helper functions for metrics, text processing, and common operations.
"""

import numpy as np
import pandas as pd
from typing import List, Optional


def compute_nss(sentiments) -> float:
    """Compute Net Sentiment Score: (positive - negative) / total."""
    s = pd.Series(sentiments).dropna()
    if len(s) == 0:
        return 0.0
    pos = (s > 0).sum()
    neg = (s < 0).sum()
    total = len(s)
    return (pos - neg) / total if total > 0 else 0.0


def compute_gini(values) -> float:
    """Compute Gini coefficient for engagement distribution."""
    arr = np.array(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * arr) / (n * np.sum(arr))) - (n + 1) / n


def sentiment_label_to_text(label: int) -> str:
    """Convert numeric sentiment to text label."""
    return {1: "positive", 0: "neutral", -1: "negative"}.get(label, "neutral")


def text_to_sentiment_label(text: str) -> int:
    """Convert text sentiment to numeric label."""
    return {"positive": 1, "neutral": 0, "negative": -1}.get(text.lower(), 0)
