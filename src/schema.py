"""
Data Schema — DiscourseRecord
==============================
Canonical data schema for all data sources.
Upgraded with aspect_sentiments field for true ABSA.
"""

import uuid
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class DiscourseRecord:
    record_id:            str   = field(default_factory=lambda: str(uuid.uuid4()))
    platform_source:      str   = ""
    brand_target:         str   = "Unknown"
    video_or_thread_id:   str   = ""
    author_handle:        str   = ""
    raw_text:             str   = ""
    creation_timestamp:   str   = ""
    engagement_score:     int   = 0
    collection_timestamp: str   = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_text:       str   = ""
    token_count:          int   = 0
    language_confidence:  float = 0.0
    is_valid:             bool  = True
    sentiment:            int   = 0   # Overall sentiment: -1, 0, 1

    # ── NEW: ABSA fields ──────────────────────────────────────────────────────
    aspect_sentiments:    Dict[str, int] = field(default_factory=dict)
    # Maps aspect_name → sentiment_label (-1, 0, 1)
    # Example: {"BATTERY_CHARGING": 1, "SERVICE_AFTERSALES": -1}

    def fingerprint(self) -> str:
        return hashlib.sha256(
            f"{self.platform_source}|{self.raw_text[:200]}|{self.creation_timestamp}"
            .encode("utf-8")).hexdigest()


def records_to_df(records: List[DiscourseRecord]) -> pd.DataFrame:
    """Convert list of DiscourseRecord to DataFrame with ABSA columns."""
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame([asdict(r) for r in records])

    # Type optimization
    for col, dt in [("engagement_score", "int32"), ("token_count", "int32"),
                    ("language_confidence", "float32"), ("is_valid", "bool"),
                    ("sentiment", "int8")]:
        if col in df.columns:
            df[col] = df[col].astype(dt)

    # Expand aspect_sentiments dict into separate columns
    if "aspect_sentiments" in df.columns:
        from src.config import ASPECT_MAP
        for aspect in ASPECT_MAP:
            col_name = f"aspect_{aspect}_sentiment"
            df[col_name] = df["aspect_sentiments"].apply(
                lambda d: d.get(aspect, None) if isinstance(d, dict) else None
            )
        df.drop(columns=["aspect_sentiments"], inplace=True, errors="ignore")

    return df
