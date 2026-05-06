"""
ABSA Post-Processor
====================
Runs PhoBERT-based Aspect Sentiment Analysis on existing preprocessed data.

This script:
1. Loads existing ev_corpus_preprocessed_v4.parquet
2. Detects aspects in each record
3. Runs ABSA (PhoBERT or rule-based) to get per-aspect sentiment
4. Saves updated data with ABSA columns

Usage:
    python run_absa.py
    python run_absa.py --mode rule-based    # Skip PhoBERT, use lexicon only
    python run_absa.py --train              # Fine-tune PhoBERT on synthetic data first
"""

import sys
import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import numpy as np
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import (
    ASPECT_MAP, POSITIVE_LEXICON, NEGATIVE_LEXICON,
    NEGATION_PARTICLES, PipelineConfig,
)
from src.nlp.absa import AspectSentimentAnalyzer
from src.utils import compute_nss

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("absa_processor")


def detect_aspects(text: str, aspect_map: dict) -> list:
    """Detect which aspects are mentioned in text."""
    if not text:
        return []
    text_lower = text.lower()
    detected = []
    for aspect, keywords in aspect_map.items():
        for kw in keywords:
            if kw in text_lower:
                detected.append(aspect)
                break
    return detected


def generate_training_data(df: pd.DataFrame) -> tuple:
    """
    Generate training data from records that have both aspect flags and sentiment.
    Creates (context_text, sentiment_label) pairs for each aspect mention.
    """
    from src.nlp.absa import extract_aspect_context

    texts = []
    labels = []

    for _, row in df.iterrows():
        processed = str(row.get("processed_text", ""))
        sentiment = int(row.get("sentiment", 0))
        tokens = processed.split()

        for aspect, keywords in ASPECT_MAP.items():
            aspect_col = f"aspect_{aspect}"
            # Check if this aspect was detected
            has_aspect = False
            if aspect_col in df.columns:
                has_aspect = bool(row.get(aspect_col, False))
            else:
                # Detect from text
                has_aspect = any(kw in processed.lower() for kw in keywords)

            if has_aspect:
                context = extract_aspect_context(tokens, keywords, window_size=7)
                if context and len(context.split()) >= 2:
                    texts.append(context)
                    labels.append(sentiment)

    return texts, labels


def main():
    parser = argparse.ArgumentParser(description="Run ABSA on preprocessed data")
    parser.add_argument("--mode", choices=["phobert", "rule-based"], default="phobert",
                        help="ABSA mode: phobert (default) or rule-based")
    parser.add_argument("--train", action="store_true",
                        help="Fine-tune PhoBERT before inference")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Training epochs (if --train)")
    parser.add_argument("--input", type=str,
                        default="artifacts/processed/ev_corpus_preprocessed_v4.parquet",
                        help="Input parquet file")
    parser.add_argument("--output", type=str, default=None,
                        help="Output parquet file (default: overwrite input)")
    args = parser.parse_args()

    config = PipelineConfig()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    # ── Load Data ─────────────────────────────────────────────────────────────
    if not input_path.exists():
        LOG.error("❌ Input file not found: %s", input_path)
        LOG.info("Run the notebook first to generate preprocessed data.")
        sys.exit(1)

    LOG.info("📂 Loading data from %s", input_path)
    df = pd.read_parquet(input_path)
    LOG.info("   Loaded %d records", len(df))

    # Filter valid records
    if "is_valid" in df.columns:
        valid_mask = df["is_valid"] == True
        LOG.info("   Valid records: %d / %d", valid_mask.sum(), len(df))
    else:
        valid_mask = pd.Series([True] * len(df))

    # ── Detect Aspects (if not already done) ──────────────────────────────────
    aspect_cols_exist = all(f"aspect_{a}" in df.columns for a in ASPECT_MAP)
    if not aspect_cols_exist:
        LOG.info("🔍 Detecting aspects in text...")
        for aspect in ASPECT_MAP:
            col = f"aspect_{aspect}"
            if col not in df.columns:
                df[col] = False
            keywords = ASPECT_MAP[aspect]
            for idx in tqdm(df[valid_mask].index, desc=f"  {aspect}"):
                text = str(df.at[idx, "processed_text"]).lower()
                df.at[idx, col] = any(kw in text for kw in keywords)
        LOG.info("✅ Aspect detection complete")

    # ── Initialize ABSA Analyzer ──────────────────────────────────────────────
    model_path = str(config.models_dir / "phobert_absa.pt")
    if args.mode == "rule-based":
        effective_model_path = None  # Force rule-based
    elif Path(model_path).exists():
        effective_model_path = model_path
    else:
        effective_model_path = None  # No saved model yet

    analyzer = AspectSentimentAnalyzer(
        aspect_map=ASPECT_MAP,
        positive_lexicon=POSITIVE_LEXICON,
        negative_lexicon=NEGATIVE_LEXICON,
        negation_particles=NEGATION_PARTICLES,
        window_size=7,
        model_path=effective_model_path,
    )
    LOG.info("🔬 ABSA Analyzer: %s", analyzer.info)

    # ── Optional: Fine-tune PhoBERT ───────────────────────────────────────────
    if args.train and analyzer.mode != "phobert-finetuned":
        LOG.info("📚 Generating training data from corpus...")
        train_texts, train_labels = generate_training_data(df[valid_mask])
        LOG.info("   Training samples: %d", len(train_texts))

        if len(train_texts) >= 50:
            metrics = analyzer.train_on_synthetic(
                texts=train_texts,
                labels=train_labels,
                epochs=args.epochs,
                batch_size=16,
                learning_rate=2e-5,
                save_path=model_path,
            )
            LOG.info("✅ Training complete. Final accuracy: %.4f",
                      metrics.get("epoch_accuracies", [0])[-1])
        else:
            LOG.warning("⚠️ Not enough training data (%d samples). Skipping training.",
                        len(train_texts))

    # ── Run ABSA on all valid records ─────────────────────────────────────────
    LOG.info("🚀 Running ABSA on %d valid records...", valid_mask.sum())

    # Initialize ABSA columns
    for aspect in ASPECT_MAP:
        col = f"aspect_{aspect}_sentiment"
        if col not in df.columns:
            df[col] = np.nan

    start_time = time.time()
    processed_count = 0

    for idx in tqdm(df[valid_mask].index, desc="ABSA Analysis"):
        processed_text = str(df.at[idx, "processed_text"])
        raw_text = str(df.at[idx, "raw_text"]) if "raw_text" in df.columns else ""

        # Get detected aspects for this record
        detected = []
        for aspect in ASPECT_MAP:
            if df.at[idx, f"aspect_{aspect}"] == True:
                detected.append(aspect)

        if not detected:
            continue

        # Run ABSA
        result = analyzer.analyze(processed_text, detected, raw_text)

        # Store results
        for aspect, sentiment in result.items():
            df.at[idx, f"aspect_{aspect}_sentiment"] = sentiment

        processed_count += 1

    elapsed = time.time() - start_time
    LOG.info("✅ ABSA complete: %d records processed in %.1f seconds (%.1f rec/s)",
             processed_count, elapsed, processed_count / elapsed if elapsed > 0 else 0)

    # ── Print ABSA Summary ────────────────────────────────────────────────────
    print("\n")
    print("┌" + "─" * 72 + "┐")
    print("│" + " 🔬 ABSA RESULTS SUMMARY".center(72) + "│")
    print("├" + "─" * 72 + "┤")
    print("│" + f"  Mode: {analyzer.mode}".ljust(72) + "│")
    print("│" + f"  Records processed: {processed_count:,}".ljust(72) + "│")
    print("│" + "".ljust(72) + "│")

    for aspect in ASPECT_MAP:
        col = f"aspect_{aspect}_sentiment"
        if col in df.columns:
            data = df[col].dropna()
            if len(data) > 0:
                nss = compute_nss(data)
                pos = (data > 0).sum()
                neg = (data < 0).sum()
                neu = (data == 0).sum()
                total = len(data)
                label = aspect.replace("_", " ").title()
                line = f"  {label:<25} n={total:>5}  NSS={nss:+.3f}  P={pos} N={neg} Neu={neu}"
                print("│" + line.ljust(72) + "│")

    print("└" + "─" * 72 + "┘")
    print()

    # ── Save Results ──────────────────────────────────────────────────────────
    LOG.info("💾 Saving to %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False, compression="snappy")

    # Also save CSV for easy inspection
    csv_path = output_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    LOG.info("💾 CSV saved to %s", csv_path)
    LOG.info("✅ ABSA post-processing complete!")


if __name__ == "__main__":
    main()
