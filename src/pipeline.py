"""
Pipeline Orchestrator
=====================
Coordinates the full ABSA pipeline from data loading to dashboard launch.

Usage:
    python -m src.pipeline             # Run full pipeline
    python -m src.pipeline --absa-only # Only run ABSA on existing data
    python -m src.pipeline --dashboard # Launch Streamlit dashboard
"""

import sys
import subprocess
import logging
from pathlib import Path

LOG = logging.getLogger("ev.pipeline")


def run_absa_pipeline(mode: str = "phobert", train: bool = False, epochs: int = 3):
    """Run ABSA post-processing on existing data."""
    cmd = [sys.executable, "run_absa.py", "--mode", mode]
    if train:
        cmd.extend(["--train", "--epochs", str(epochs)])

    LOG.info("🚀 Running ABSA pipeline: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent.parent))
    return result.returncode == 0


def launch_dashboard():
    """Launch Streamlit dashboard."""
    LOG.info("🌐 Launching Streamlit dashboard...")
    subprocess.run(
        ["streamlit", "run", "app.py", "--server.headless", "true"],
        cwd=str(Path(__file__).parent.parent),
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="EV Sentiment ABSA Pipeline")
    parser.add_argument("--absa-only", action="store_true", help="Only run ABSA")
    parser.add_argument("--dashboard", action="store_true", help="Launch dashboard")
    parser.add_argument("--train", action="store_true", help="Fine-tune PhoBERT")
    parser.add_argument("--mode", default="phobert", choices=["phobert", "rule-based"])
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s")

    if args.dashboard:
        launch_dashboard()
    elif args.absa_only:
        run_absa_pipeline(args.mode, args.train, args.epochs)
    else:
        # Full pipeline: ABSA then dashboard
        success = run_absa_pipeline(args.mode, args.train, args.epochs)
        if success:
            launch_dashboard()


if __name__ == "__main__":
    main()
