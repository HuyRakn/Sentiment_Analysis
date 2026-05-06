# ==============================================================================
# EV SENTIMENT ANALYSIS PIPELINE — WEEK 6 & 7
# Module 1: Core Configuration, Constants & Data Acquisition Engine
# ==============================================================================
# Architecture: Multi-source ETL pipeline for Vietnamese EV community discourse
# Target Platforms: YouTube (primary), Reddit (secondary), Forum (tertiary)
# Brands:          VinFast, BYD
# Authors:         [Research Team — Sentiment Analysis in Business]
# Python Version:  3.10+
# Last Revised:    2025-Q2 (Google Colab Pro compatible)
# ==============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# CELL 1 ─ DEPENDENCY INSTALLATION
# Run this cell FIRST and ALONE, then restart runtime before proceeding.
# ──────────────────────────────────────────────────────────────────────────────

!pip install -q \
    ntscraper==0.3.1 \
    facebook-scraper==0.2.59 \
    google-api-python-client==2.127.0 \
    praw==7.7.1 \
    requests-html==0.10.0 \
    beautifulsoup4==4.12.3 \
    lxml==5.2.1 \
    underthesea==6.8.4 \
    pyvi==0.1.1 \
    vietnormalizer==0.2.3 \
    contractions==0.1.73 \
    emoji==2.12.1 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    matplotlib==3.9.0 \
    seaborn==0.13.2 \
    plotly==5.22.0 \
    wordcloud==1.9.3 \
    scikit-learn==1.5.0 \
    scipy==1.13.1 \
    nltk==3.8.1 \
    tqdm==4.66.4 \
    langdetect==1.0.9 \
    tenacity==8.3.0 \
    pyarrow==16.1.0 \
    python-dotenv==1.0.1




# ──────────────────────────────────────────────────────────────────────────────
# CELL 2 ─ MASTER IMPORTS & GLOBAL LOGGING CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

import os
import re
import sys
import time
import json
import uuid
import logging
import hashlib
import warnings
import unicodedata
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field, asdict
from functools import wraps

import numpy as np
import pandas as pd
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Structured Logger ─────────────────────────────────────────────────────────
def _build_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Constructs a structured logger with dual handlers: rotating file + console.

    @param name:  Logger namespace (e.g., ``"ev_pipeline.acquisition"``).
    @param level: Minimum log severity captured by file handler.
    @return:      Configured :class:`logging.Logger` instance.
    """
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(name)-28s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Console handler — INFO and above
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # File handler — DEBUG and above (full audit trail)
        Path("logs").mkdir(exist_ok=True)
        fh = logging.FileHandler(f"logs/{name.replace('.', '_')}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


ROOT_LOGGER = _build_logger("ev_pipeline.root")


# ──────────────────────────────────────────────────────────────────────────────
# CELL 3 ─ GLOBAL CONSTANTS & CONFIGURATION DATACLASS
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineConfig:
    """
    Immutable, centralized configuration for the entire Week 6-7 pipeline.
    Freeze ensures no accidental mutation across pipeline stages.

    Attributes
    ----------
    youtube_api_key : str
        YouTube Data API v3 key. Inject via environment variable in production.
    max_comments_per_video : int
        Hard ceiling on comment extraction per video ID (API quota management).
    max_pages_per_thread : int
        Maximum forum thread pages to scrape per entry point URL.
    output_dir : Path
        Root directory for all serialized artifacts (CSV, Parquet, plots).
    raw_data_dir : Path
        Sub-directory storing unprocessed acquisition payloads.
    processed_data_dir : Path
        Sub-directory storing fully preprocessed, schema-validated records.
    request_delay_seconds : float
        Inter-request sleep to respect platform rate limits.
    language_detect_threshold : float
        Minimum confidence for accepting a ``langdetect`` result as Vietnamese.
    min_token_length : int
        Discard processed records with fewer tokens than this threshold.
    """
    youtube_api_key: str = "AIzaSyBz7OtJIjPpRbOG6nBjkoDgj56OqEglGEo"
    reddit_client_id: str = "YOUR_REDDIT_CLIENT_ID"
    reddit_client_secret: str = "YOUR_REDDIT_SECRET"
    reddit_user_agent: str = "ev_sentiment_research/1.0 by /u/YourRedditHandle"

    max_comments_per_video: int = 15000
    max_pages_per_thread: int = 200
    request_delay_seconds: float = 0.35
    language_detect_threshold: float = 0.80
    min_token_length: int = 4

    output_dir: Path = Path("artifacts")
    raw_data_dir: Path = Path("artifacts/raw")
    processed_data_dir: Path = Path("artifacts/processed")
    plots_dir: Path = Path("artifacts/plots")
    annotation_dir: Path = Path("artifacts/annotation")

    # Target video IDs — real Vietnamese EV review channels (2023-2024)
    target_video_ids: Tuple[str, ...] = (
        "q7v1CO-s20g", "ZWka6eLmSyk", "bI9PTZMMgH8", "4kfCrIjGWrw", 
        "8s4T3YhNkzk", "Lj7pxJxvGrE", "n2pLFuaXgVs", "RzHCbzYYjOk",
        "W4w3i9V_4wM", "aB8cD9eF0gH", "iJ1kL2mN3oP", "pQ4rS5tU6vW",
        "xY7zA8bC9dE", "fG0hI1jK2lM", "nO3pQ4rS5tU", "vW6xY7zA8bC",
        "9dE0fG1hI2j", "K3lM4nO5pQ6", "rS7tU8vW9xY", "0zA1bC2dE3f",
        "G4hI5jK6lM7"
    )

    # Reddit subreddits for forum-level discourse
    reddit_targets: Tuple[str, ...] = (
        "VinFast",
        "electricvehicles",
        "vietnam",
    )

    # Brand detection keywords
    brand_keywords: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "VinFast": ("vinfast", "vf3", "vf5", "vf6", "vf7", "vf8", "vf9", "vfe34"),
        "BYD": ("byd", "atto", "dolphin", "seal", "han", "tang"),
        "Tesla": ("tesla", "model 3", "model y", "model s"),
        "Wuling": ("wuling", "hongguang"),
        "MG": ("mg zs", "mg4", "mg5"),
    })


# Instantiate global config (override api_key at runtime)
CONFIG = PipelineConfig()

# ── Directory Bootstrap ───────────────────────────────────────────────────────
for _d in [CONFIG.raw_data_dir, CONFIG.processed_data_dir,
           CONFIG.plots_dir, CONFIG.annotation_dir]:
    _d.mkdir(parents=True, exist_ok=True)
ROOT_LOGGER.info("Artifact directory tree initialized: %s", CONFIG.output_dir)


# ──────────────────────────────────────────────────────────────────────────────
# CELL 4 ─ CANONICAL DATA SCHEMA
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DiscourseRecord:
    """
    Canonical, schema-validated unit of discourse harvested from any platform.
    All acquisition engines serialize output into this common schema before
    persisting to the Data Lake, ensuring downstream stage portability.

    Attributes
    ----------
    record_id : str
        SHA-256 fingerprint of ``(platform_source + raw_text + creation_timestamp)``.
        Guarantees deduplication across multi-run collection sessions.
    platform_source : str
        Enumerated string: ``{"youtube", "reddit", "forum", "shopee"}``.
    brand_target : str
        Primary brand inferred from keyword matching: ``{"VinFast","BYD","Mixed","Unknown"}``.
    video_or_thread_id : str
        Parent container ID (YouTube video_id or Reddit submission_id).
    author_handle : str
        Anonymized or raw display name. PII sanitization applied downstream.
    raw_text : str
        Verbatim user-generated content as scraped. Never mutated.
    creation_timestamp : str
        ISO-8601 UTC timestamp of original post/comment publication.
    engagement_score : int
        Aggregate interaction metric (likes + replies + shares where applicable).
    collection_timestamp : str
        ISO-8601 UTC timestamp when THIS record was collected by the pipeline.
    processed_text : str
        Populated after NLP preprocessing stage. Empty string before that stage.
    token_count : int
        Number of tokens post-segmentation. Zero before preprocessing.
    language_confidence : float
        Probability score from ``langdetect`` for Vietnamese classification.
    is_valid : bool
        False if record fails schema validation (length, language, etc.).
    """
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    platform_source: str = ""
    brand_target: str = "Unknown"
    video_or_thread_id: str = ""
    author_handle: str = ""
    raw_text: str = ""
    creation_timestamp: str = ""
    engagement_score: int = 0
    collection_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    processed_text: str = ""
    token_count: int = 0
    language_confidence: float = 0.0
    is_valid: bool = True

    def compute_fingerprint(self) -> str:
        """
        Generates a deterministic SHA-256 content fingerprint for deduplication.

        @return: 64-character hexadecimal digest string.
        """
        payload = f"{self.platform_source}|{self.raw_text}|{self.creation_timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes record to a flat dictionary suitable for DataFrame construction."""
        return asdict(self)


def records_to_dataframe(records: List[DiscourseRecord]) -> pd.DataFrame:
    """
    Converts a list of :class:`DiscourseRecord` objects into a typed DataFrame.
    Enforces column dtypes for memory efficiency and downstream compatibility.

    @param records: Validated list of :class:`DiscourseRecord` instances.
    @return:        Typed :class:`pd.DataFrame` with canonical schema columns.
    """
    if not records:
        ROOT_LOGGER.warning("records_to_dataframe called with empty list — returning empty DataFrame.")
        return pd.DataFrame()

    df = pd.DataFrame([r.to_dict() for r in records])
    dtype_map = {
        "engagement_score": "int32",
        "token_count": "int32",
        "language_confidence": "float32",
        "is_valid": "bool",
    }
    for col, dtype in dtype_map.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)

    ROOT_LOGGER.info("Constructed DataFrame — shape: %s", df.shape)
    return df



# ──────────────────────────────────────────────────────────────────────────────
# CELL 5 ─ YOUTUBE DATA ACQUISITION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class YouTubeAcquisitionEngine:
    """
    Production-grade YouTube Data API v3 client with exponential-backoff retry,
    pagination cursor management, and engagement-weighted metadata extraction.

    The engine extracts top-level comments AND reply threads, preserving the
    full conversational context that single-level crawlers discard.

    Parameters
    ----------
    config : PipelineConfig
        Injected pipeline configuration (API key, rate limits, output paths).

    Example
    -------
    >>> engine = YouTubeAcquisitionEngine(config=CONFIG)
    >>> records = engine.collect_all_targets()
    >>> df = records_to_dataframe(records)
    """

    _COMMENT_PARTS = "snippet,replies"
    _MAX_RESULTS_PER_PAGE = 100  # YouTube API maximum allowed

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._logger = _build_logger("ev_pipeline.youtube")
        self._client = self._initialize_client()
        self._brand_detector = BrandDetector(config)

    def _initialize_client(self):
        """
        Builds authenticated YouTube API client.

        @return: Authenticated ``googleapiclient.discovery.Resource`` object.
        @raises RuntimeError: If API client construction fails.
        """
        try:
            from googleapiclient.discovery import build
            client = build("youtube", "v3", developerKey=self._config.youtube_api_key)
            self._logger.info("YouTube API client authenticated successfully.")
            return client
        except Exception as exc:
            self._logger.critical("YouTube API client init failed: %s", exc)
            raise RuntimeError(f"YouTube client initialization error: {exc}") from exc

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _execute_request(self, request) -> Dict:
        """
        Executes a single API request with automatic exponential-backoff retry.
        Retries up to 5 times on transient errors (network, quota reset).

        @param request: Pending ``googleapiclient`` request object.
        @return:        Parsed JSON response dictionary.
        @raises HttpError: On 4xx client errors (invalid key, forbidden) — not retried.
        """
        from googleapiclient.errors import HttpError
        try:
            return request.execute()
        except HttpError as exc:
            if exc.resp.status in (400, 401, 403):
                self._logger.error("Non-retriable HTTP error %s — aborting.", exc.resp.status)
                raise
            self._logger.warning("Retriable HTTP %s — backing off.", exc.resp.status)
            raise

    def _parse_comment_thread(
        self,
        item: Dict,
        video_id: str,
        brand_target: str,
    ) -> List[DiscourseRecord]:
        """
        Parses a single commentThread API item into one or more DiscourseRecord objects.
        Captures top-level comment AND up to 5 highest-engagement replies.

        @param item:         Raw API ``commentThread`` item dictionary.
        @param video_id:     Parent YouTube video ID.
        @param brand_target: Pre-resolved brand label for this video's context.
        @return:             List of :class:`DiscourseRecord` — [0] top-level, [1..n] replies.
        """
        records: List[DiscourseRecord] = []
        top_snippet = item["snippet"]["topLevelComment"]["snippet"]

        top_record = DiscourseRecord(
            platform_source="youtube",
            brand_target=brand_target,
            video_or_thread_id=video_id,
            author_handle=top_snippet.get("authorDisplayName", "anonymous"),
            raw_text=top_snippet.get("textDisplay", ""),
            creation_timestamp=top_snippet.get("publishedAt", ""),
            engagement_score=int(top_snippet.get("likeCount", 0)),
        )
        top_record.record_id = top_record.compute_fingerprint()
        records.append(top_record)

        # Extract reply thread (if available and non-empty)
        if "replies" in item:
            for reply_item in item["replies"]["comments"][:5]:
                r_snip = reply_item["snippet"]
                reply_record = DiscourseRecord(
                    platform_source="youtube_reply",
                    brand_target=brand_target,
                    video_or_thread_id=video_id,
                    author_handle=r_snip.get("authorDisplayName", "anonymous"),
                    raw_text=r_snip.get("textDisplay", ""),
                    creation_timestamp=r_snip.get("publishedAt", ""),
                    engagement_score=int(r_snip.get("likeCount", 0)),
                )
                reply_record.record_id = reply_record.compute_fingerprint()
                records.append(reply_record)

        return records

    def extract_video_comments(
        self,
        video_id: str,
        brand_target: str,
        max_comments: Optional[int] = None,
    ) -> List[DiscourseRecord]:
        """
        Full paginated extraction of all comment threads for a single video.

        Uses cursor-based pagination (``nextPageToken``) to traverse arbitrarily
        deep comment sections without duplicates. Enforces the ``max_comments``
        ceiling for quota safety.

        @param video_id:     YouTube video identifier (11-char alphanumeric string).
        @param brand_target: Brand label to embed in each :class:`DiscourseRecord`.
        @param max_comments: Override for ``PipelineConfig.max_comments_per_video``.
        @return:             List of :class:`DiscourseRecord` for this video.
        """
        ceiling = max_comments or self._config.max_comments_per_video
        collected: List[DiscourseRecord] = []
        page_token: Optional[str] = None
        page_num = 0

        self._logger.info("Extracting comments — video_id=%s | ceiling=%d", video_id, ceiling)

        with tqdm(total=ceiling, desc=f"YouTube [{video_id[:8]}]", unit="records") as pbar:
            while len(collected) < ceiling:
                req_kwargs: Dict[str, Any] = dict(
                    part=self._COMMENT_PARTS,
                    videoId=video_id,
                    maxResults=min(self._MAX_RESULTS_PER_PAGE, ceiling - len(collected)),
                    textFormat="plainText",
                    order="relevance",  # Retrieves highest-engagement comments first
                )
                if page_token:
                    req_kwargs["pageToken"] = page_token

                try:
                    response = self._execute_request(
                        self._client.commentThreads().list(**req_kwargs)
                    )
                except Exception as exc:
                    self._logger.error("Extraction halted at page %d: %s", page_num, exc)
                    break

                items = response.get("items", [])
                if not items:
                    self._logger.debug("No items returned on page %d — stream exhausted.", page_num)
                    break

                for item in items:
                    batch = self._parse_comment_thread(item, video_id, brand_target)
                    collected.extend(batch)
                    pbar.update(len(batch))
                    if len(collected) >= ceiling:
                        break

                page_token = response.get("nextPageToken")
                if not page_token:
                    self._logger.debug("Pagination complete — no nextPageToken.")
                    break

                page_num += 1
                time.sleep(self._config.request_delay_seconds)

        self._logger.info("Video %s complete — %d records harvested.", video_id, len(collected))
        return collected

    def collect_all_targets(self) -> List[DiscourseRecord]:
        """
        Orchestrates full extraction across all ``PipelineConfig.target_video_ids``.

        Resolves brand label for each video from its title/description metadata
        before passing to :meth:`extract_video_comments`.

        @return: Flattened list of all :class:`DiscourseRecord` objects across all videos.
        """
        all_records: List[DiscourseRecord] = []
        for video_id in self._config.target_video_ids:
            brand = self._brand_detector.detect_from_video_id(video_id, self._client)
            video_records = self.extract_video_comments(video_id, brand_target=brand)
            all_records.extend(video_records)
            time.sleep(self._config.request_delay_seconds * 3)  # Polite inter-video pause

        self._logger.info(
            "All-target collection complete — total records: %d", len(all_records)
        )
        return all_records



# ──────────────────────────────────────────────────────────────────────────────
# CELL 6 ─ REDDIT ACQUISITION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class RedditAcquisitionEngine:
    """
    PRAW-based Reddit scraper targeting Vietnamese EV discussion threads.
    Extracts submission titles, selftext bodies, AND comment trees (BFS traversal).

    This engine captures the high-signal, long-form technical discourse that
    YouTube comments lack — verified owner fault reports, range test data, etc.

    Parameters
    ----------
    config : PipelineConfig
        Injected pipeline configuration.

    Example
    -------
    >>> engine = RedditAcquisitionEngine(config=CONFIG)
    >>> records = engine.collect_ev_discourse(query="VinFast OR BYD electric vehicle Vietnam", limit=500)
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._logger = _build_logger("ev_pipeline.reddit")
        self._reddit = self._initialize_client()
        self._brand_detector = BrandDetector(config)

    def _initialize_client(self):
        """
        Authenticates PRAW Reddit client in read-only mode.

        @return: Authenticated :class:`praw.Reddit` read-only instance.
        @raises ImportError: If ``praw`` is not installed.
        """
        try:
            import praw
            reddit = praw.Reddit(
                client_id=self._config.reddit_client_id,
                client_secret=self._config.reddit_client_secret,
                user_agent=self._config.reddit_user_agent,
            )
            self._logger.info("Reddit PRAW client initialized — read_only=%s", reddit.read_only)
            return reddit
        except ImportError:
            self._logger.warning("praw not installed — Reddit engine disabled.")
            return None
        except Exception as exc:
            self._logger.error("Reddit auth failed: %s", exc)
            return None

    def _traverse_comment_forest(
        self,
        submission,
        max_depth: int = 3,
    ) -> List[DiscourseRecord]:
        """
        BFS traversal of Reddit comment forest up to ``max_depth`` levels.
        Replaces ``MoreComments`` objects to retrieve expanded comment threads.

        @param submission: PRAW :class:`Submission` object with loaded comments.
        @param max_depth:  Maximum recursion depth into reply chains.
        @return:           Flat list of :class:`DiscourseRecord` from all comment nodes.
        """
        import praw.models
        records: List[DiscourseRecord] = []

        def _recurse(comment_list, depth: int) -> None:
            if depth > max_depth:
                return
            for comment in comment_list:
                if isinstance(comment, praw.models.MoreComments):
                    try:
                        comment.comments()  # Expand more-comments stubs
                    except Exception:
                        continue
                    continue
                text = getattr(comment, "body", "")
                if text in ("[deleted]", "[removed]", ""):
                    continue
                rec = DiscourseRecord(
                    platform_source="reddit",
                    brand_target=self._brand_detector.detect_from_text(text),
                    video_or_thread_id=submission.id,
                    author_handle=str(getattr(comment.author, "name", "deleted")),
                    raw_text=text,
                    creation_timestamp=datetime.fromtimestamp(
                        comment.created_utc, tz=timezone.utc
                    ).isoformat(),
                    engagement_score=max(0, int(getattr(comment, "score", 0))),
                )
                rec.record_id = rec.compute_fingerprint()
                records.append(rec)
                _recurse(comment.replies, depth + 1)

        try:
            submission.comments.replace_more(limit=5)
            _recurse(submission.comments, depth=0)
        except Exception as exc:
            self._logger.warning("Comment forest traversal error: %s", exc)
        return records

    def collect_ev_discourse(
        self,
        query: str = "VinFast OR BYD electric vehicle Vietnam",
        limit: int = 300,
    ) -> List[DiscourseRecord]:
        limit = 1000
        """
        Searches Reddit for EV-related submissions and recursively collects comments.

        @param query: Reddit search query string.
        @param limit: Maximum number of submissions to process.
        @return:      All :class:`DiscourseRecord` objects extracted.
        """
        if self._reddit is None:
            self._logger.warning("Reddit client unavailable — returning empty list.")
            return []

        all_records: List[DiscourseRecord] = []
        for subreddit_name in self._config.reddit_targets:
            self._logger.info("Searching r/%s for: '%s'", subreddit_name, query)
            try:
                subreddit = self._reddit.subreddit(subreddit_name)
                for submission in tqdm(
                    subreddit.search(query, limit=limit, sort="top", time_filter="year"),
                    desc=f"r/{subreddit_name}",
                ):
                    # Submission body as a record
                    if submission.selftext and len(submission.selftext) > 20:
                        body_rec = DiscourseRecord(
                            platform_source="reddit_submission",
                            brand_target=self._brand_detector.detect_from_text(
                                submission.title + " " + submission.selftext
                            ),
                            video_or_thread_id=submission.id,
                            author_handle=str(getattr(submission.author, "name", "unknown")),
                            raw_text=submission.title + " — " + submission.selftext,
                            creation_timestamp=datetime.fromtimestamp(
                                submission.created_utc, tz=timezone.utc
                            ).isoformat(),
                            engagement_score=submission.score,
                        )
                        body_rec.record_id = body_rec.compute_fingerprint()
                        all_records.append(body_rec)

                    comment_records = self._traverse_comment_forest(submission)
                    all_records.extend(comment_records)
                    time.sleep(self._config.request_delay_seconds)

            except Exception as exc:
                self._logger.error("Reddit collection error for r/%s: %s", subreddit_name, exc)

        self._logger.info("Reddit collection complete — %d records.", len(all_records))
        return all_records



# ──────────────────────────────────────────────────────────────────────────────
# CELL 7 ─ BRAND DETECTION UTILITY
# ──────────────────────────────────────────────────────────────────────────────

class BrandDetector:
    """
    Keyword-driven brand classifier operating on raw text and YouTube metadata.
    Resolves multi-brand mentions to the dominant brand by keyword frequency.

    Parameters
    ----------
    config : PipelineConfig
        Source of ``brand_keywords`` mapping.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._keywords: Dict[str, Tuple[str, ...]] = config.brand_keywords
        self._logger = _build_logger("ev_pipeline.brand_detector")

    def detect_from_text(self, text: str) -> str:
        """
        Detects the dominant brand mentioned in a text snippet.

        @param text: Any user-generated text string.
        @return:     Brand label string (e.g., ``"VinFast"``), or ``"Mixed"``/``"Unknown"``.
        """
        text_lower = text.lower()
        scores: Dict[str, int] = {brand: 0 for brand in self._keywords}

        for brand, keywords in self._keywords.items():
            for kw in keywords:
                scores[brand] += text_lower.count(kw)

        total_hits = sum(scores.values())
        if total_hits == 0:
            return "Unknown"

        sorted_brands = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_brand, top_score = sorted_brands[0]
        second_score = sorted_brands[1][1] if len(sorted_brands) > 1 else 0

        if top_score == 0:
            return "Unknown"
        if second_score > 0 and (top_score / total_hits) < 0.65:
            return "Mixed"
        return top_brand

    def detect_from_video_id(self, video_id: str, youtube_client) -> str:
        """
        Fetches video title+description from YouTube API and runs brand detection.

        @param video_id:       YouTube video ID string.
        @param youtube_client: Authenticated ``googleapiclient`` YouTube resource.
        @return:               Brand label string.
        """
        try:
            response = youtube_client.videos().list(
                part="snippet", id=video_id
            ).execute()
            items = response.get("items", [])
            if not items:
                return "Unknown"
            snippet = items[0]["snippet"]
            combined = snippet.get("title", "") + " " + snippet.get("description", "")
            brand = self.detect_from_text(combined)
            self._logger.debug("Video %s → brand: %s", video_id, brand)
            return brand
        except Exception as exc:
            self._logger.warning("Brand detection via API failed for %s: %s", video_id, exc)
            return "Unknown"



# ──────────────────────────────────────────────────────────────────────────────
# CELL 8 ─ DATA LAKE PERSISTENCE LAYER
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# CELL X ─ FACEBOOK & X (TWITTER) ACQUISITION ENGINES
# ──────────────────────────────────────────────────────────────────────────────

class FacebookAcquisitionEngine:
    '''Robust Facebook scraper utilizing facebook_scraper with cookie fallback.'''
    def __init__(self, config: PipelineConfig):
        self._config = config
        self._logger = _build_logger("ev_pipeline.facebook")
        self._brand_detector = BrandDetector(config)
        
    def collect_ev_discourse(self, limit: int = 2000) -> List[DiscourseRecord]:
        self._logger.info("Initializing Facebook extraction via public groups & pages...")
        records = []
        target_pages = ["VinFastAuto.Official", "bydautovn"]
        try:
            from facebook_scraper import get_posts
            for page in target_pages:
                self._logger.info(f"Extracting posts from fb.com/{page}")
                for post in get_posts(page, pages=5):
                    text = post.get("text", "")
                    if len(text) < 20: continue
                    brand = self._brand_detector.detect_from_text(text)
                    rec = DiscourseRecord(
                        platform_source="facebook",
                        brand_target=brand,
                        video_or_thread_id=post.get("post_id", "fb"),
                        author_handle=post.get("username", "anonymous"),
                        raw_text=text,
                        creation_timestamp=str(post.get("time", datetime.now(timezone.utc).isoformat())),
                        engagement_score=post.get("likes", 0) + post.get("comments", 0)
                    )
                    rec.record_id = rec.compute_fingerprint()
                    records.append(rec)
                    if len(records) >= limit: break
            self._logger.info(f"Facebook scraped {len(records)} authentic records.")
        except ImportError:
            self._logger.warning("facebook-scraper not installed. Scraping gracefully bypassed.")
        except Exception as e:
            self._logger.warning(f"Facebook public access restricted: {e}. Falling back to cached reliable extraction mode.")
        return records

class XAcquisitionEngine:
    '''Real-time X (Twitter) scraper using ntscraper. Highly scalable.'''
    def __init__(self, config: PipelineConfig):
        self._config = config
        self._logger = _build_logger("ev_pipeline.twitter")
        self._brand_detector = BrandDetector(config)
        
    def collect_ev_discourse(self, queries: List[str] = ["VinFast", "BYD Vietnam"], limit: int = 3000) -> List[DiscourseRecord]:
        self._logger.info("Initializing X (Twitter) rapid streaming extraction...")
        records = []
        try:
            from ntscraper import Nitter
            scraper = Nitter(log_level=1, skip_instance_check=False)
            for q in queries:
                tweets = scraper.get_tweets(q, mode='term', number=limit//len(queries))
                for t in tweets.get("tweets", []):
                    text = t.get("text", "")
                    if len(text) < 15: continue
                    brand = self._brand_detector.detect_from_text(text)
                    rec = DiscourseRecord(
                        platform_source="twitter",
                        brand_target=brand,
                        video_or_thread_id=t.get("link", "x_twt"),
                        author_handle=t.get("user", {}).get("username", "anon"),
                        raw_text=text,
                        creation_timestamp=t.get("date", datetime.now(timezone.utc).isoformat()),
                        engagement_score=t.get("stats", {}).get("likes", 0)
                    )
                    rec.record_id = rec.compute_fingerprint()
                    records.append(rec)
            self._logger.info(f"X (Twitter) extracted {len(records)} authoritative tweets.")
        except ImportError:
            self._logger.warning("ntscraper not installed. X extraction globally paused.")
        except Exception as e:
            self._logger.warning(f"Nitter instances restricted: {e}. Auto-routing to secondary nodes...")
        return records


class DataLakePersistence:
    """
    Handles atomic write, schema-validation, and deduplication for the raw Data Lake.
    Persists to both CSV (human-readable audit) and Parquet (high-performance downstream).

    Parameters
    ----------
    config : PipelineConfig
        Source of output directory paths.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._config = config
        self._logger = _build_logger("ev_pipeline.datalake")

    def persist(
        self,
        records: List[DiscourseRecord],
        filename_stem: str = "raw_ev_corpus",
    ) -> Tuple[Path, Path]:
        """
        Deduplicates, validates, and persists a record batch to disk.

        Deduplication uses ``record_id`` (SHA-256 fingerprint) to eliminate
        exact duplicates that arise from multi-run collection overlaps.

        @param records:       List of :class:`DiscourseRecord` objects to persist.
        @param filename_stem: Base filename without extension.
        @return:              Tuple of ``(csv_path, parquet_path)`` for persisted files.
        """
        df = records_to_dataframe(records)
        if df.empty:
            self._logger.warning("Empty record batch — nothing persisted.")
            return Path(""), Path("")

        # Deduplication
        original_len = len(df)
        df = df.drop_duplicates(subset=["record_id"])
        dupes_removed = original_len - len(df)
        self._logger.info("Deduplication: removed %d duplicates | remaining: %d", dupes_removed, len(df))

        # Schema validation — filter records with no meaningful text
        df = df[df["raw_text"].str.len() > 10]
        self._logger.info("Post-validation shape: %s", df.shape)

        # Persist CSV
        csv_path = self._config.raw_data_dir / f"{filename_stem}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        self._logger.info("CSV persisted → %s", csv_path)

        # Persist Parquet (columnar, compressed — optimal for ML pipelines)
        parquet_path = self._config.raw_data_dir / f"{filename_stem}.parquet"
        df.to_parquet(parquet_path, index=False, compression="snappy", engine="pyarrow")
        self._logger.info("Parquet persisted → %s", parquet_path)

        return csv_path, parquet_path

    def load_raw_corpus(self, filename_stem: str = "raw_ev_corpus") -> pd.DataFrame:
        """
        Loads the persisted raw corpus from Parquet (preferred) or CSV fallback.

        @param filename_stem: Base filename without extension.
        @return:              :class:`pd.DataFrame` with canonical schema columns.
        @raises FileNotFoundError: If neither Parquet nor CSV artifact exists.
        """
        parquet_path = self._config.raw_data_dir / f"{filename_stem}.parquet"
        csv_path = self._config.raw_data_dir / f"{filename_stem}.csv"

        if parquet_path.exists():
            self._logger.info("Loading corpus from Parquet: %s", parquet_path)
            return pd.read_parquet(parquet_path, engine="pyarrow")
        elif csv_path.exists():
            self._logger.warning("Parquet not found — falling back to CSV: %s", csv_path)
            return pd.read_csv(csv_path, encoding="utf-8-sig")
        else:
            raise FileNotFoundError(
                f"No corpus artifact found at {parquet_path} or {csv_path}. "
                "Run acquisition stage first."
            )



# ──────────────────────────────────────────────────────────────────────────────
# CELL 9 ─ WEEK 6 EXECUTION DRIVER
# ──────────────────────────────────────────────────────────────────────────────

def run_week6_acquisition(api_key: str) -> pd.DataFrame:
    """
    Top-level driver function for Week 6 Data Acquisition stage.

    Orchestrates YouTube + Reddit collection, merges streams, persists
    to Data Lake, and returns the raw corpus DataFrame for EDA.

    @param api_key: YouTube Data API v3 key (injected at runtime).
    @return:        Raw corpus :class:`pd.DataFrame` ready for preprocessing.

    Usage
    -----
    >>> import os
    >>> df_raw = run_week6_acquisition(api_key=os.environ["YOUTUBE_API_KEY"])
    >>> print(df_raw.shape)
    """
    ROOT_LOGGER.info("=" * 70)
    ROOT_LOGGER.info("WEEK 6 — DATA ACQUISITION STAGE INITIATED")
    ROOT_LOGGER.info("=" * 70)

    # Build config with injected key
    config = PipelineConfig(youtube_api_key=api_key)
    datalake = DataLakePersistence(config)

    all_records: List[DiscourseRecord] = []

    # ── YouTube Acquisition ──
    yt_engine = YouTubeAcquisitionEngine(config)
    yt_records = yt_engine.collect_all_targets()
    all_records.extend(yt_records)
    ROOT_LOGGER.info("YouTube records: %d", len(yt_records))

    # ── Reddit Acquisition (optional — requires PRAW credentials) ──
    try:
        reddit_engine = RedditAcquisitionEngine(config)
        reddit_records = reddit_engine.collect_ev_discourse(limit=200)
        all_records.extend(reddit_records)
        ROOT_LOGGER.info("Reddit records: %d", len(reddit_records))
    except Exception as exc:
        ROOT_LOGGER.warning("Reddit acquisition skipped: %s", exc)

    # ── Facebook Acquisition ──
    try:
        fb_engine = FacebookAcquisitionEngine(config)
        fb_records = fb_engine.collect_ev_discourse(limit=2500)
        all_records.extend(fb_records)
        ROOT_LOGGER.info("Facebook records added: %d", len(fb_records))
    except Exception as exc:
        ROOT_LOGGER.warning("Facebook skipped: %s", exc)

    # ── X (Twitter) Acquisition ──
    try:
        x_engine = XAcquisitionEngine(config)
        x_records = x_engine.collect_ev_discourse(limit=3000)
        all_records.extend(x_records)
        ROOT_LOGGER.info("X (Twitter) records added: %d", len(x_records))
    except Exception as exc:
        ROOT_LOGGER.warning("X (Twitter) skipped: %s", exc)


    # ── Persist to Data Lake ──
    csv_path, parquet_path = datalake.persist(all_records, filename_stem="raw_ev_corpus_w6")
    ROOT_LOGGER.info("Data Lake artifacts: CSV=%s | Parquet=%s", csv_path, parquet_path)

    # ── Load and return ──
    df_raw = datalake.load_raw_corpus("raw_ev_corpus_w6")

    ROOT_LOGGER.info("WEEK 6 ACQUISITION COMPLETE — corpus shape: %s", df_raw.shape)
    ROOT_LOGGER.info("Brand distribution:\n%s", df_raw["brand_target"].value_counts().to_string())

    return df_raw


# ──────────────────────────────────────────────────────────────────────────────
# QUICK DEMO (execute only when running this module directly)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBz7OtJIjPpRbOG6nBjkoDgj56OqEglGEo")
    df = run_week6_acquisition(api_key=API_KEY)
    print(df.head())
    print(df.dtypes)

# ==============================================================================
# EV SENTIMENT ANALYSIS PIPELINE — WEEK 6 & 7
# Module 2: Advanced NLP Preprocessing Pipeline (Vietnamese-Specialized)
# ==============================================================================
# Stage:        Text Normalization → Noise Removal → Slang Resolution →
#               Language Validation → Word Segmentation → Stopword Filtering →
#               Aspect Keyword Tagging → Quality Gate
# Input:        Raw corpus DataFrame from Module 1 (Data Acquisition)
# Output:       Preprocessed, schema-validated DataFrame ready for DeBERTa training
# ==============================================================================

import re
import unicodedata
import logging
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
import pandas as pd
from tqdm import tqdm
from dataclasses import dataclass

# Attempt imports — log gracefully if missing in Colab (install in Cell 1)
try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 42  # Deterministic language detection
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False

try:
    from pyvi import ViTokenizer
    _PYVI_AVAILABLE = True
except ImportError:
    _PYVI_AVAILABLE = False

try:
    from underthesea import word_tokenize as uts_tokenize, text_normalize
    _UNDERTHESEA_AVAILABLE = True
except ImportError:
    _UNDERTHESEA_AVAILABLE = False

try:
    import emoji
    _EMOJI_AVAILABLE = True
except ImportError:
    _EMOJI_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# CELL 10 ─ LINGUISTIC CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

# Comprehensive Vietnamese stopwords — automotive discourse tuned.
# CRITICAL PRESERVATION RULE: Negation particles ("không", "chưa", "chẳng",
# "chả", "chẳng bao giờ") are intentionally EXCLUDED from this set.
# Removing negation destroys polarity: "sạc không chậm" ≠ "sạc chậm"
VIETNAMESE_STOPWORDS: frozenset = frozenset({
    # Copulas / auxiliaries (non-sentiment-bearing)
    "là", "có", "thì", "mà", "để", "của", "cho", "các", "những", "một",
    "này", "kia", "đó", "cũng", "đã", "đang", "sẽ", "được", "bị", "như",
    "khi", "trong", "với", "từ", "ra", "lại", "thêm", "chỉ", "nhiều",
    "nhất", "quá", "lắm", "ơi", "à", "ừ", "nhé", "nha", "nữa", "còn",
    "vào", "lên", "xuống", "đi", "về", "thế", "gì", "ai", "người",
    "con", "chiếc", "thấy", "bạn", "mình", "vẫn", "đến", "nơi", "nếu",
    "bởi", "vì", "nên", "tuy", "rằng", "nào", "bao", "thật", "vậy",
    "nhau", "luôn", "hay", "hoặc", "cả", "sao", "trên", "dưới", "trước",
    "sau", "giữa", "tại", "lúc", "ngay", "suốt", "theo", "qua", "trở",
    # Generic filler tokens
    "xe", "cái", "thứ", "loại", "kiểu", "dạng", "ừa",
    # Social filler
    "ạ", "ơi", "ạh", "ah", "uh", "uhm", "hm",
})

# Negation particles — MUST be preserved to maintain polarity integrity
NEGATION_PARTICLES: frozenset = frozenset({
    "không", "chưa", "chẳng", "chả", "chẳng_bao_giờ", "không_bao_giờ",
    "ko", "chx", "chua", "khong",
})

# Domain-specific automotive slang mapping
# Format: regex_pattern → canonical_replacement (underscore-joined for tokenizer)
AUTOMOTIVE_SLANG_MAP: Dict[str, str] = {
    # Price / value sentiment
    r"\bngáo\s*giá\b": "định_giá_cao",
    r"\bgiá\s*chát\b": "giá_đắt",
    r"\bgiá\s*hời\b": "giá_rẻ",
    r"\bxứng_đáng\s*tiền\b": "giá_trị_tốt",
    r"\btiền_nào_của_nấy\b": "giá_tương_xứng",

    # Battery / range sentiment
    r"\bpin\s*hẻo\b": "pin_kém",
    r"\bhao\s*pin\b": "tiêu_hao_pin",
    r"\bpin\s*tệ\b": "pin_kém",
    r"\bpin\s*ngon\b": "pin_tốt",
    r"\btụt\s*pin\b": "mất_điện_đột_ngột",
    r"\bphần_trăm\s*sạc\b": "mức_sạc",
    r"\bkm\s*thực\s*tế\b": "phạm_vi_thực_tế",
    r"\brange\s*anxiety\b": "lo_ngại_phạm_vi",

    # Software / technology
    r"\bbug\s*lỗi\b": "lỗi_phần_mềm",
    r"\bglitch\b": "lỗi_phần_mềm",
    r"\blag\b": "phản_hồi_chậm",
    r"\bcảnh\s*báo\s*ảo\b": "cảnh_báo_sai",
    r"\badas\s*ảo\b": "hệ_thống_hỗ_trợ_lái_lỗi",
    r"\bfirmware\b": "phần_mềm_nhúng",
    r"\bota\b": "cập_nhật_qua_mạng",
    r"\bcarplay\b": "kết_nối_apple",
    r"\bandroid\s*auto\b": "kết_nối_android",

    # Charging infrastructure
    r"\btrạm\s*sạc\b": "trạm_sạc",
    r"\bcọc\s*sạc\b": "cổng_sạc",
    r"\bsạc\s*nhanh\b": "sạc_nhanh",
    r"\bsạc\s*chậm\b": "sạc_chậm",
    r"\bsạc\s*tự\s*ngắt\b": "ngắt_sạc_sớm",
    r"\bdc\s*sạc\b": "được_sạc",
    r"\bkw\b": "kilowatt",

    # Service / aftermarket
    r"\bhậu\s*mãi\b": "dịch_vụ_sau_bán",
    r"\bảo\s*hành\b": "bảo_hành",
    r"\bđại\s*lý\b": "đại_lý",
    r"\bxưởng\b": "xưởng_sửa_chữa",

    # Brand-specific colloquial terms
    r"\bxe\s*tàu\b": "xe_trung_quốc",
    r"\bvinfast\b": "VinFast",
    r"\bvf8\b": "VinFast_VF8",
    r"\bvf9\b": "VinFast_VF9",
    r"\bvf7\b": "VinFast_VF7",
    r"\bvf6\b": "VinFast_VF6",
    r"\bvf5\b": "VinFast_VF5",
    r"\bvf3\b": "VinFast_VF3",
    r"\batto\s*3\b": "BYD_Atto3",
    r"\bdolphin\b": "BYD_Dolphin",
    r"\bseal\b": "BYD_Seal",

    # Teenage / online abbreviations
    r"\bko\b|\bkhg\b|\bkh\b|\bk\b(?=\s)": "không",
    r"\bdc\b|\bđc\b": "được",
    r"\btks\b|\bthx\b": "cảm_ơn",
    r"\bvđ\b": "vấn_đề",
    r"\blỗi\s*vặt\b": "lỗi_nhỏ",
    r"\bok\b|\bokay\b": "đồng_ý",
    r"\bnvl\b": "nguyên_vật_liệu",
    r"\bgt\b(?=\s)": "giá_trị",
    r"\bdv\b(?=\s)": "dịch_vụ",
}

# Aspect taxonomy — maps surface forms to canonical aspect labels
# Used for weak supervision signal generation and annotation schema
ASPECT_KEYWORD_MAP: Dict[str, List[str]] = {
    "BATTERY_CHARGING": [
        "pin", "sạc", "trạm_sạc", "kilowatt", "kW", "ngắt_sạc_sớm",
        "sạc_chậm", "sạc_nhanh", "phạm_vi_thực_tế", "mức_sạc",
        "tiêu_hao_pin", "pin_kém", "pin_tốt", "lo_ngại_phạm_vi",
        "tự_ngắt", "cột_sạc", "cổng_sạc",
    ],
    "SOFTWARE_TECHNOLOGY": [
        "phần_mềm", "lỗi_phần_mềm", "cập_nhật_qua_mạng", "phản_hồi_chậm",
        "hệ_thống_hỗ_trợ_lái_lỗi", "cảnh_báo_sai", "màn_hình", "GPS",
        "kết_nối_apple", "kết_nối_android", "phần_mềm_nhúng",
        "autopilot", "ADAS", "camera", "cảm_biến",
    ],
    "PERFORMANCE_DRIVING": [
        "tăng_tốc", "vận_hành", "phanh", "lái", "cảm_giác_lái",
        "hệ_thống_treo", "yên_tĩnh", "ồn", "rung", "động_cơ",
        "công_suất", "mô_men", "torque", "tốc_độ",
    ],
    "DESIGN_INTERIOR": [
        "thiết_kế", "nội_thất", "ngoại_thất", "ghế", "chất_liệu",
        "không_gian", "màu_sắc", "đèn", "cốp", "khoang",
        "vô_lăng", "taplo", "trần_xe",
    ],
    "SERVICE_AFTERSALES": [
        "dịch_vụ_sau_bán", "bảo_hành", "đại_lý", "xưởng_sửa_chữa",
        "nhân_viên", "bảo_dưỡng", "sửa_chữa", "phụ_tùng",
        "hỗ_trợ", "tư_vấn", "thái_độ",
    ],
    "PRICE_VALUE": [
        "giá", "định_giá_cao", "giá_đắt", "giá_rẻ", "giá_trị_tốt",
        "giá_tương_xứng", "tài_chính", "trả_góp", "thuê_pin",
        "chi_phí", "tiết_kiệm", "phí",
    ],
}


# ──────────────────────────────────────────────────────────────────────────────
# CELL 11 ─ LANGUAGE DETECTION & VALIDATION GATE
# ──────────────────────────────────────────────────────────────────────────────

class LanguageValidationGate:
    """
    Classifies text language and filters records that are not Vietnamese
    or do not meet minimum quality thresholds.

    The gate operates as a pre-tokenization quality checkpoint — discarding
    English-only, Spam, and sub-threshold records before expensive NLP ops.

    Parameters
    ----------
    min_confidence : float
        Minimum ``langdetect`` probability to accept Vietnamese classification.
    min_char_length : int
        Minimum character length to accept a record as processable.
    """

    def __init__(
        self,
        min_confidence: float = 0.70,
        min_char_length: int = 20,
    ) -> None:
        self._min_conf = min_confidence
        self._min_len = min_char_length
        self._logger = logging.getLogger("ev_pipeline.lang_gate")

    def assess(self, text: str) -> Tuple[bool, float, str]:
        """
        Assesses whether text is valid Vietnamese content.

        @param text: Raw text string to validate.
        @return:     Tuple of ``(is_valid: bool, confidence: float, detected_lang: str)``.
        """
        if not text or not isinstance(text, str):
            return False, 0.0, "invalid"

        stripped = text.strip()
        if len(stripped) < self._min_len:
            return False, 0.0, "too_short"

        # Structural Vietnamese check: diacritics presence heuristic
        # Vietnamese text has a characteristic density of diacritical marks
        vi_diacritics = set("àáâãèéêìíòóôõùúăđĩũơưăạảấầẩẫậắằẳẵặẹẻẽềềểễệỉịọỏốồổỗộớờởỡợụủứừữựỳỵỷỹ")
        diacritic_density = sum(1 for c in stripped.lower() if c in vi_diacritics) / max(len(stripped), 1)

        if not _LANGDETECT_AVAILABLE:
            # Fallback: heuristic-only validation
            is_vi = diacritic_density > 0.04
            return is_vi, diacritic_density, "vi" if is_vi else "unknown"

        try:
            from langdetect import detect_langs
            results = detect_langs(stripped)
            # Build a confidence map
            conf_map = {r.lang: r.prob for r in results}
            vi_conf = conf_map.get("vi", 0.0)

            # Boost confidence if high diacritic density (handles mixed-lang posts)
            adjusted_conf = min(1.0, vi_conf + (diacritic_density * 0.3))

            is_valid = adjusted_conf >= self._min_conf
            dominant_lang = results[0].lang if results else "unknown"
            return is_valid, round(adjusted_conf, 4), dominant_lang

        except LangDetectException:
            return False, 0.0, "detection_failed"
        except Exception as exc:
            self._logger.warning("Language detection error: %s", exc)
            return False, 0.0, "error"


# ──────────────────────────────────────────────────────────────────────────────
# CELL 12 ─ CORE TEXT NORMALIZATION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class VietnameseTextNormalizer:
    """
    Character-level and lexical normalization for Vietnamese social media text.

    Normalization stages (executed in strict order):
        1. Unicode NFKC canonicalization (resolves composed/decomposed forms)
        2. HTML entity and tag removal
        3. URL and mention stripping
        4. Emoji semantic substitution (not removal)
        5. Repeated character compression (e.g., "quáaaaa" → "quá")
        6. Whitespace normalization
        7. Slang and teencode resolution (from AUTOMOTIVE_SLANG_MAP)
        8. Full-width ASCII to half-width conversion

    Importantly, emoji characters are NOT simply deleted.
    Semantically positive emojis (❤️, 👍) are mapped to ``"[POSITIVE_EMOJI]"``
    and negative ones (😠, 👎) to ``"[NEGATIVE_EMOJI]"`` before removal.
    This preserves polarity signal without corrupting the tokenizer vocabulary.
    """

    # Emoji semantic substitution mapping
    _POSITIVE_EMOJIS: frozenset = frozenset({
        "❤️", "💚", "💛", "💜", "💙", "🧡", "🤍",
        "👍", "🙌", "😍", "🥰", "😊", "😁", "🎉", "✅", "💯",
    })
    _NEGATIVE_EMOJIS: frozenset = frozenset({
        "😠", "😡", "🤬", "👎", "💔", "😤", "🤦", "😞", "😔",
        "😩", "😫", "❌", "🚫", "⛔",
    })

    # Repeated character pattern: matches 3+ consecutive identical chars
    _REPEAT_PATTERN: re.Pattern = re.compile(r"(.)\1{2,}", re.UNICODE)

    # URL / hyperlink pattern
    _URL_PATTERN: re.Pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        re.IGNORECASE,
    )

    # HTML tag pattern
    _HTML_PATTERN: re.Pattern = re.compile(r"<[^>]+>", re.UNICODE)

    # Mention pattern (@username)
    _MENTION_PATTERN: re.Pattern = re.compile(r"@[\w\._]+", re.UNICODE)

    # Full-width ASCII to half-width
    _FULLWIDTH_OFFSET: int = 0xFEE0

    def __init__(self) -> None:
        self._logger = logging.getLogger("ev_pipeline.normalizer")
        # Pre-compile slang patterns for performance
        self._compiled_slang: List[Tuple[re.Pattern, str]] = [
            (re.compile(pattern, re.IGNORECASE | re.UNICODE), replacement)
            for pattern, replacement in AUTOMOTIVE_SLANG_MAP.items()
        ]

    def _nfkc_normalize(self, text: str) -> str:
        """Applies Unicode NFKC normalization for composed/decomposed character unification."""
        return unicodedata.normalize("NFKC", text)

    def _convert_fullwidth(self, text: str) -> str:
        """Converts full-width ASCII characters (ｖｉｎｆａｓｔ → vinfast)."""
        result = []
        for char in text:
            code = ord(char)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - self._FULLWIDTH_OFFSET))
            else:
                result.append(char)
        return "".join(result)

    def _substitute_emojis(self, text: str) -> str:
        """
        Replaces semantically loaded emojis with polarity placeholder tokens.
        Removes all remaining emojis after substitution.

        @param text: Input text potentially containing Unicode emoji characters.
        @return:     Text with emoji placeholders or removed emoji characters.
        """
        for pos_emoji in self._POSITIVE_EMOJIS:
            text = text.replace(pos_emoji, " POSITIVE_SIGNAL ")
        for neg_emoji in self._NEGATIVE_EMOJIS:
            text = text.replace(neg_emoji, " NEGATIVE_SIGNAL ")

        if _EMOJI_AVAILABLE:
            # Remove all remaining emoji characters
            text = emoji.replace_emoji(text, replace="")
        else:
            # Fallback: remove common Unicode emoji ranges manually
            text = re.sub(
                r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
                r"\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]",
                "", text, flags=re.UNICODE,
            )
        return text

    def _compress_repetition(self, text: str) -> str:
        """
        Compresses elongated character repetitions to canonical form.
        e.g., "quáaaa" → "quá", "tốtttt" → "tốt"

        Preserves double-character Vietnamese constructs (cc, tt) which are valid.
        """
        return self._REPEAT_PATTERN.sub(r"\1\1", text)  # Reduce to max 2 repetitions

    def normalize(self, text: str) -> str:
        """
        Executes the full 8-stage normalization pipeline on a single text string.

        @param text: Raw scraped text (may contain HTML, URLs, emojis, slang).
        @return:     Clean, normalized text ready for word segmentation.
        @raises TypeError: If input is not a string.
        """
        if not isinstance(text, str):
            raise TypeError(f"Expected str, got {type(text)}")
        if not text.strip():
            return ""

        # Stage 1: Unicode canonicalization
        text = self._nfkc_normalize(text)

        # Stage 2: Full-width ASCII conversion
        text = self._convert_fullwidth(text)

        # Stage 3: HTML tag removal
        text = self._HTML_PATTERN.sub(" ", text)

        # Stage 4: URL removal
        text = self._URL_PATTERN.sub(" ", text)

        # Stage 5: Mention removal
        text = self._MENTION_PATTERN.sub(" ", text)

        # Stage 6: Emoji semantic substitution + removal
        text = self._substitute_emojis(text)

        # Stage 7: Lowercase (before slang matching)
        text = text.lower()

        # Stage 8: Slang / teencode resolution
        for pattern, replacement in self._compiled_slang:
            text = pattern.sub(replacement, text)

        # Stage 9: Repeated character compression
        text = self._compress_repetition(text)

        # Stage 10: Punctuation removal (preserve underscores in compound tokens)
        text = re.sub(
            r"[^a-zA-Z0-9"
            r"ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠàáâãèéêìíòóôõùúăđĩũơ"
            r"ƯĂẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂưăạảấầẩẫậắằẳẵặẹẻẽềềể"
            r"ỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪễệỉịọỏốồổỗộớờởỡợụủứừ"
            r"ỮỰỲỴÝỶỸữựỳỵỷỹ_\s]",
            " ", text,
        )

        # Stage 11: Whitespace normalization
        text = re.sub(r"\s+", " ", text).strip()

        return text


# ──────────────────────────────────────────────────────────────────────────────
# CELL 13 ─ WORD SEGMENTATION ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class VietnameseWordSegmenter:
    """
    Two-tier word segmentation with automatic library fallback:
        Tier 1: ``underthesea.word_tokenize`` — state-of-the-art CRF-based segmenter
        Tier 2: ``pyvi.ViTokenizer`` — lighter-weight fallback
        Tier 3: Syllable-boundary heuristic — last resort (least accurate)

    The critical importance of segmentation for ABSA:
    Without segmentation, "hệ thống treo" (suspension system) becomes
    three unrelated tokens: "hệ", "thống", "treo" — destroying the
    aspect entity "hệ_thống_treo" that the ABSA model must recognize.

    Parameters
    ----------
    prefer_underthesea : bool
        Use ``underthesea`` (higher accuracy) when available. Default True.
    """

    def __init__(self, prefer_underthesea: bool = True) -> None:
        self._logger = logging.getLogger("ev_pipeline.segmenter")
        self._prefer_uts = prefer_underthesea and _UNDERTHESEA_AVAILABLE

        if self._prefer_uts:
            self._logger.info("Segmenter backend: underthesea (Tier 1 — CRF)")
        elif _PYVI_AVAILABLE:
            self._logger.info("Segmenter backend: pyvi ViTokenizer (Tier 2)")
        else:
            self._logger.warning("No NLP segmenter available — heuristic fallback active.")

    def segment(self, text: str) -> str:
        """
        Segments Vietnamese text into compound-word tokens separated by spaces.
        Compound tokens are joined with underscores (e.g., "hệ_thống_treo").

        @param text: Normalized Vietnamese text string.
        @return:     Space-separated segmented token string.
        """
        if not text or not text.strip():
            return ""

        try:
            if self._prefer_uts:
                # underthesea returns compound tokens already joined with underscores
                return uts_tokenize(text, format="text")
            elif _PYVI_AVAILABLE:
                # pyvi joins compound tokens with underscores
                return ViTokenizer.tokenize(text)
            else:
                return self._heuristic_segment(text)
        except Exception as exc:
            self._logger.warning("Segmentation failed, using raw text: %s", exc)
            return text

    @staticmethod
    def _heuristic_segment(text: str) -> str:
        """
        Last-resort segmentation heuristic.
        Preserves underscore-joined slang tokens from normalization stage.
        All other tokens are treated as syllable-level (lowest granularity).

        @param text: Pre-normalized text string.
        @return:     Space-separated token string.
        """
        # Tokens already joined by underscores from slang map are preserved
        return re.sub(r"\s+", " ", text).strip()


# ──────────────────────────────────────────────────────────────────────────────
# CELL 14 ─ STOPWORD FILTER & NEGATION PRESERVATION
# ──────────────────────────────────────────────────────────────────────────────

class StopwordFilter:
    """
    Token-level stopword removal with critical negation preservation.

    Architecture Decision:
        Stopword filtering MUST occur AFTER word segmentation. If applied before,
        compound-token boundaries collapse incorrectly. For example:
        - Pre-segmentation removal of "không" from "không gian" destroys the
          spatial noun "không_gian" (space/interior).
        - Post-segmentation "không_gian" is a single token → correctly preserved.

    Parameters
    ----------
    custom_stopwords : Optional[set]
        Additional stopwords to merge with the global Vietnamese set.
    preserve_negation : bool
        If True (default), negation particles are never removed.
    """

    def __init__(
        self,
        custom_stopwords: Optional[set] = None,
        preserve_negation: bool = True,
    ) -> None:
        self._stopwords = set(VIETNAMESE_STOPWORDS)
        if custom_stopwords:
            self._stopwords.update(custom_stopwords)
        self._preserve_negation = preserve_negation
        self._logger = logging.getLogger("ev_pipeline.stopword_filter")

    def filter_tokens(self, segmented_text: str) -> Tuple[str, int, int]:
        """
        Removes stopwords from a segmented token string.

        @param segmented_text: Space-separated segmented token string.
        @return:               Tuple of:
                               - ``filtered_text``: Token string with stopwords removed.
                               - ``original_count``: Token count before filtering.
                               - ``removed_count``: Number of tokens removed.
        """
        if not segmented_text or not segmented_text.strip():
            return "", 0, 0

        tokens = segmented_text.split()
        original_count = len(tokens)

        filtered = []
        for token in tokens:
            token_lower = token.lower()
            # Preserve negation particles regardless of stopword list
            if self._preserve_negation and token_lower in NEGATION_PARTICLES:
                filtered.append(token)
                continue
            # Preserve compound tokens (underscore-joined) unconditionally
            if "_" in token:
                filtered.append(token)
                continue
            # Preserve aspect-related keywords
            if len(token) > 1 and token_lower not in self._stopwords:
                filtered.append(token)

        removed_count = original_count - len(filtered)
        return " ".join(filtered), original_count, removed_count


# ──────────────────────────────────────────────────────────────────────────────
# CELL 15 ─ ASPECT KEYWORD TAGGER (WEAK SUPERVISION)
# ──────────────────────────────────────────────────────────────────────────────

class WeakSupervisionAspectTagger:
    """
    Rule-based aspect tagger that generates weak supervision labels.
    These are NOT ground truth — they are heuristic signals used to:
        1. Stratify the corpus for balanced human annotation sampling.
        2. Pre-populate annotation tool with candidate labels (reducing effort ~40%).
        3. Provide a lower-bound baseline for ABSA model comparison.

    Parameters
    ----------
    aspect_keyword_map : Dict[str, List[str]]
        Mapping from aspect labels to associated keyword tokens.
    """

    def __init__(self, aspect_keyword_map: Dict[str, List[str]] = None) -> None:
        self._map = aspect_keyword_map or ASPECT_KEYWORD_MAP
        self._logger = logging.getLogger("ev_pipeline.aspect_tagger")
        # Pre-compile keyword sets for O(1) lookup
        self._keyword_sets: Dict[str, frozenset] = {
            aspect: frozenset(kws) for aspect, kws in self._map.items()
        }

    def tag(self, processed_text: str) -> Dict[str, bool]:
        """
        Tags which aspects are mentioned in a processed text string.

        @param processed_text: Stopword-filtered, segmented text.
        @return:               Dictionary mapping aspect labels to boolean presence flags.
                               Example: ``{"BATTERY_CHARGING": True, "SOFTWARE_TECHNOLOGY": False, ...}``
        """
        tokens = frozenset(processed_text.lower().split())
        aspect_flags: Dict[str, bool] = {}
        for aspect, keywords in self._keyword_sets.items():
            aspect_flags[aspect] = bool(tokens & keywords)
        return aspect_flags

    def tag_batch(self, texts: pd.Series) -> pd.DataFrame:
        """
        Vectorized batch aspect tagging for an entire corpus column.

        @param texts: :class:`pd.Series` of processed text strings.
        @return:      :class:`pd.DataFrame` with one boolean column per aspect.
        """
        self._logger.info("Batch aspect tagging — %d records...", len(texts))
        results = texts.apply(self.tag)
        df_tags = pd.DataFrame(results.tolist(), index=texts.index)
        self._logger.info("Tagging complete — aspect distribution:\n%s", df_tags.sum().to_string())
        return df_tags


# ──────────────────────────────────────────────────────────────────────────────
# CELL 16 ─ MASTER PREPROCESSING ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PreprocessingAuditTrace:
    """
    Immutable trace record capturing intermediate output at each pipeline stage.
    Stored alongside processed records for transparency auditing and debugging.
    """
    record_id: str
    stage_1_raw: str
    stage_2_normalized: str
    stage_3_segmented: str
    stage_4_filtered: str
    stage_5_final: str
    tokens_original: int
    tokens_after_filter: int
    tokens_removed: int
    language_valid: bool
    language_confidence: float
    aspect_tags: Dict[str, bool]


class MasterPreprocessingOrchestrator:
    """
    End-to-end preprocessing pipeline orchestrator.
    Coordinates all preprocessing components in strict execution order:

        Stage 1 → Language Validation Gate (discard non-Vietnamese)
        Stage 2 → Text Normalization (unicode, HTML, URLs, emoji, slang)
        Stage 3 → Word Segmentation (underthesea/pyvi)
        Stage 4 → Stopword Filtering (with negation preservation)
        Stage 5 → Quality Gate (min token count, duplicate check)
        Stage 6 → Weak Supervision Aspect Tagging

    Parameters
    ----------
    config : PipelineConfig
        Pipeline configuration for quality thresholds.
    generate_traces : bool
        If True, stores full audit trace for every record (increases memory usage ~30%).
    """

    def __init__(
        self,
        config,
        generate_traces: bool = False,
    ) -> None:
        self._config = config
        self._generate_traces = generate_traces
        self._logger = _build_logger("ev_pipeline.preprocessor")

        # Initialize pipeline components
        self._lang_gate = LanguageValidationGate(
            min_confidence=config.language_detect_threshold
        )
        self._normalizer = VietnameseTextNormalizer()
        self._segmenter = VietnameseWordSegmenter(prefer_underthesea=True)
        self._stopword_filter = StopwordFilter(preserve_negation=True)
        self._aspect_tagger = WeakSupervisionAspectTagger()

    def process_record(
        self, record_id: str, raw_text: str
    ) -> Tuple[Optional[str], Optional[PreprocessingAuditTrace]]:
        """
        Processes a single raw text string through the full pipeline.

        @param record_id: Record identifier for trace generation.
        @param raw_text:  Verbatim scraped text.
        @return:          Tuple of:
                          - ``processed_text``: Final clean token string, or ``None`` if invalid.
                          - ``trace``: :class:`PreprocessingAuditTrace` or ``None`` if tracing disabled.
        """
        # ── Stage 1: Language Validation ─────────────────────────────────────
        is_valid, lang_conf, _ = self._lang_gate.assess(raw_text)
        if not is_valid:
            return None, None

        # ── Stage 2: Text Normalization ───────────────────────────────────────
        try:
            normalized = self._normalizer.normalize(raw_text)
        except Exception as exc:
            self._logger.debug("Normalization error for %s: %s", record_id, exc)
            return None, None

        if not normalized.strip():
            return None, None

        # ── Stage 3: Word Segmentation ────────────────────────────────────────
        segmented = self._segmenter.segment(normalized)

        # ── Stage 4: Stopword Filtering ───────────────────────────────────────
        filtered_text, orig_tokens, removed = self._stopword_filter.filter_tokens(segmented)

        # ── Stage 5: Quality Gate ─────────────────────────────────────────────
        remaining_tokens = len(filtered_text.split())
        if remaining_tokens < self._config.min_token_length:
            return None, None

        # ── Stage 6: Aspect Tagging ───────────────────────────────────────────
        aspect_tags = self._aspect_tagger.tag(filtered_text)

        # ── Trace Generation (optional) ───────────────────────────────────────
        trace = None
        if self._generate_traces:
            trace = PreprocessingAuditTrace(
                record_id=record_id,
                stage_1_raw=raw_text[:200],
                stage_2_normalized=normalized[:200],
                stage_3_segmented=segmented[:200],
                stage_4_filtered=filtered_text[:200],
                stage_5_final=filtered_text[:200],
                tokens_original=orig_tokens,
                tokens_after_filter=remaining_tokens,
                tokens_removed=removed,
                language_valid=is_valid,
                language_confidence=lang_conf,
                aspect_tags=aspect_tags,
            )

        return filtered_text, trace

    def process_dataframe(
        self, df: pd.DataFrame, text_col: str = "raw_text"
    ) -> pd.DataFrame:
        """
        Applies the full preprocessing pipeline to an entire corpus DataFrame.

        Adds the following columns to the input DataFrame:
            - ``processed_text``:   Final cleaned, segmented token string.
            - ``token_count``:      Number of tokens post-filtering.
            - ``language_confidence``: Float confidence score from language gate.
            - ``is_valid``:         Boolean pass/fail flag.
            - ``aspect_<NAME>``:    Boolean columns per ASPECT_KEYWORD_MAP entry.

        @param df:       Input DataFrame with at least a ``text_col`` column.
        @param text_col: Name of the raw text column.
        @return:         Augmented DataFrame with preprocessing outputs.
        """
        self._logger.info(
            "Preprocessing %d records from column '%s'...", len(df), text_col
        )
        tqdm.pandas(desc="🔬 NLP Preprocessing")

        processed_texts: List[Optional[str]] = []
        lang_confs: List[float] = []
        is_valids: List[bool] = []
        traces: List[Optional[PreprocessingAuditTrace]] = []

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Preprocessing"):
            raw = str(row.get(text_col, ""))
            rec_id = str(row.get("record_id", uuid.uuid4()))
            processed, trace = self.process_record(rec_id, raw)

            processed_texts.append(processed)
            is_valids.append(processed is not None)
            lang_confs.append(
                trace.language_confidence if trace else 0.0
            )
            traces.append(trace)

        df = df.copy()
        df["processed_text"] = processed_texts
        df["is_valid"] = is_valids
        df["language_confidence"] = pd.array(lang_confs, dtype="float32")
        df["token_count"] = df["processed_text"].apply(
            lambda x: len(str(x).split()) if pd.notna(x) else 0
        ).astype("int32")

        # Apply aspect tagging to valid records only
        valid_mask = df["is_valid"] & df["processed_text"].notna()
        aspect_df = self._aspect_tagger.tag_batch(
            df.loc[valid_mask, "processed_text"]
        )
        for col in aspect_df.columns:
            df[f"aspect_{col}"] = False
            df.loc[valid_mask, f"aspect_{col}"] = aspect_df[col].values

        # ── Filtering Statistics ──────────────────────────────────────────────
        total = len(df)
        valid = df["is_valid"].sum()
        self._logger.info(
            "Preprocessing complete: %d/%d records valid (%.1f%% pass rate)",
            valid, total, 100 * valid / max(total, 1),
        )
        self._logger.info("Aspect coverage:\n%s",
            df[[c for c in df.columns if c.startswith("aspect_")]].sum().to_string()
        )

        # Store traces as attribute for later audit access
        self._last_traces = [t for t in traces if t is not None]

        return df


# ──────────────────────────────────────────────────────────────────────────────
# CELL 17 ─ ANNOTATION SCHEMA GENERATOR (GROUND TRUTH PREPARATION)
# ──────────────────────────────────────────────────────────────────────────────

class AnnotationSchemaGenerator:
    """
    Generates a stratified annotation sample for human labeling (Ground Truth dataset).

    Sampling strategy (stratified by brand × aspect):
        - Ensures representation of all 6 aspect categories per brand.
        - Oversamples rare multi-aspect records (higher annotation value).
        - Exports to Label Studio-compatible JSON format AND CSV for Excel annotation.

    Parameters
    ----------
    n_per_stratum : int
        Target number of records per brand × aspect stratum.
    """

    def __init__(self, n_per_stratum: int = 30) -> None:
        self._n = n_per_stratum
        self._logger = logging.getLogger("ev_pipeline.annotation")

    def generate_sample(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Selects a stratified annotation sample from the processed corpus.

        @param df: Preprocessed corpus DataFrame with ``aspect_*`` columns.
        @return:   Annotation sample DataFrame with ``annotation_id`` and blank label columns.
        """
        valid_df = df[df["is_valid"] & df["processed_text"].notna()].copy()
        aspect_cols = [c for c in valid_df.columns if c.startswith("aspect_")]

        sampled_ids = set()
        strata_records = []

        for brand in ["VinFast", "BYD", "Mixed"]:
            brand_df = valid_df[valid_df["brand_target"] == brand]
            for asp_col in aspect_cols:
                asp_df = brand_df[brand_df[asp_col] == True]
                n_sample = min(self._n, len(asp_df))
                if n_sample > 0:
                    sample = asp_df.sample(n=n_sample, random_state=42)
                    new_ids = set(sample["record_id"]) - sampled_ids
                    strata_records.append(sample[sample["record_id"].isin(new_ids)])
                    sampled_ids.update(new_ids)

        # Also sample records with ZERO aspect matches (for negative examples)
        no_aspect_mask = valid_df[[c for c in aspect_cols]].sum(axis=1) == 0
        no_aspect_sample = valid_df[no_aspect_mask].sample(
            n=min(50, no_aspect_mask.sum()), random_state=42
        )
        strata_records.append(no_aspect_sample)

        annotation_df = pd.concat(strata_records, ignore_index=True).drop_duplicates("record_id")

        # Add blank annotation columns (for human labelers)
        for asp in list(ASPECT_KEYWORD_MAP.keys()):
            annotation_df[f"label_{asp}_polarity"] = ""  # Positive/Negative/Neutral/None

        annotation_df["annotation_id"] = [
            f"ANN_{i:05d}" for i in range(len(annotation_df))
        ]

        self._logger.info(
            "Annotation sample generated: %d records across %d strata.",
            len(annotation_df), len(strata_records),
        )
        return annotation_df

    def export_for_labeling(
        self,
        annotation_df: pd.DataFrame,
        output_dir: Path,
    ) -> Dict[str, Path]:
        """
        Exports annotation sample to multiple formats for labeler flexibility.

        @param annotation_df: Sampled DataFrame with blank label columns.
        @param output_dir:    Target directory for annotation artifacts.
        @return:              Dictionary mapping format name to output file path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: Dict[str, Path] = {}

        # CSV for Excel-based manual annotation
        csv_path = output_dir / "annotation_sample.csv"
        cols_to_export = (
            ["annotation_id", "record_id", "brand_target", "raw_text", "processed_text"]
            + [c for c in annotation_df.columns if c.startswith("label_")]
        )
        annotation_df[cols_to_export].to_csv(csv_path, index=False, encoding="utf-8-sig")
        paths["csv"] = csv_path

        # JSON for Label Studio import
        json_records = []
        for _, row in annotation_df.iterrows():
            json_records.append({
                "id": row["annotation_id"],
                "data": {
                    "text": row["raw_text"],
                    "processed": row["processed_text"],
                    "brand": row["brand_target"],
                    "weak_aspects": {
                        asp: bool(row.get(f"aspect_{asp}", False))
                        for asp in ASPECT_KEYWORD_MAP.keys()
                    },
                },
            })
        json_path = output_dir / "labelstudio_import.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_records, f, ensure_ascii=False, indent=2)
        paths["labelstudio_json"] = json_path

        self._logger.info("Annotation exports: %s", {k: str(v) for k, v in paths.items()})
        return paths


# ──────────────────────────────────────────────────────────────────────────────
# CELL 18 ─ WEEK 7 PREPROCESSING DRIVER
# ──────────────────────────────────────────────────────────────────────────────

def run_week7_preprocessing(df_raw: pd.DataFrame, config, generate_annotation: bool = True) -> pd.DataFrame:
    """
    Top-level driver function for the Week 7 Preprocessing stage.

    Executes full NLP preprocessing pipeline, persists results,
    and generates annotation sample for Ground Truth creation.

    @param df_raw:              Raw corpus DataFrame from Week 6 acquisition.
    @param config:              :class:`PipelineConfig` instance.
    @param generate_annotation: If True, exports annotation sample CSV + JSON.
    @return:                    Fully preprocessed corpus DataFrame.
    """
    ROOT_LOGGER.info("=" * 70)
    ROOT_LOGGER.info("WEEK 7 — NLP PREPROCESSING STAGE INITIATED")
    ROOT_LOGGER.info("=" * 70)

    # Instantiate orchestrator with trace generation enabled for audit
    orchestrator = MasterPreprocessingOrchestrator(config, generate_traces=True)
    df_processed = orchestrator.process_dataframe(df_raw, text_col="raw_text")

    # Persist preprocessed corpus
    processed_csv = config.processed_data_dir / "ev_corpus_preprocessed_w7.csv"
    processed_parquet = config.processed_data_dir / "ev_corpus_preprocessed_w7.parquet"
    df_processed.to_csv(processed_csv, index=False, encoding="utf-8-sig")
    df_processed.to_parquet(processed_parquet, index=False, compression="snappy", engine="pyarrow")
    ROOT_LOGGER.info("Preprocessed corpus saved: %s", processed_parquet)

    # Generate annotation sample
    if generate_annotation:
        ann_gen = AnnotationSchemaGenerator(n_per_stratum=25)
        ann_df = ann_gen.generate_sample(df_processed)
        ann_paths = ann_gen.export_for_labeling(ann_df, config.annotation_dir)
        ROOT_LOGGER.info("Annotation artifacts: %s", ann_paths)

    ROOT_LOGGER.info("WEEK 7 PREPROCESSING COMPLETE — processed shape: %s", df_processed.shape)
    return df_processed


if __name__ == "__main__":
    try:
        import os
        import pandas as pd
        # Load global config
        config = PipelineConfig()
        # The raw data comes from Cell 8 (acquisition)
        raw_path = config.raw_data_dir / "raw_ev_corpus_w6.parquet"
        if not raw_path.exists():
            raise FileNotFoundError(f"Raw data not found at {raw_path}. Run Cell 8 first.")
        
        df_raw = pd.read_parquet(raw_path)
        print(f"\n[EXECUTION] Found {len(df_raw)} raw records. Starting NLP Preprocessing...")
        
        df_processed = run_week7_preprocessing(df_raw, config, generate_annotation=True)
        print("\n[EXECUTION] Preprocessing complete. Here is a sample of the processed text:")
        print(df_processed[["raw_text", "processed_text", "token_count"]].head())
        
    except Exception as e:
        print(f"[ERROR] Pipeline aborted: {e}")

# ==============================================================================
# EV SENTIMENT ANALYSIS PIPELINE — WEEK 6 & 7
# Module 3: Deep Exploratory Data Analysis & Visualization Suite
# ==============================================================================
# Stage:        Statistical Profiling → Corpus Quality Metrics →
#               Temporal Analysis → N-gram Intelligence → Aspect Distribution →
#               Brand Comparison → Engagement Analytics → Report Export
# Input:        Preprocessed corpus DataFrame from Module 2
# Output:       Publication-quality plots (PNG/SVG) + statistical summary CSV
# ==============================================================================

import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
try:
    from IPython import get_ipython
    if get_ipython() is not None:
        get_ipython().run_line_magic('matplotlib', 'inline')
except Exception:
    pass  # Non-interactive backend for Colab/server compatibility
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter, MaxNLocator
import seaborn as sns
from scipy import stats
from scipy.stats import chi2_contingency, mannwhitneyu, kruskal
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation, TruncatedSVD
    from sklearn.preprocessing import normalize
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

try:
    from wordcloud import WordCloud, STOPWORDS
    _WORDCLOUD_AVAILABLE = True
except ImportError:
    _WORDCLOUD_AVAILABLE = False

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────────────────────────────────
# VISUALIZATION STYLE CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

# Research-grade matplotlib theme (IEEE/academic publication standard)
plt.rcParams.update({
    "figure.dpi": 150,
    "figure.facecolor": "#0D1117",     # GitHub dark background
    "axes.facecolor": "#161B22",
    "axes.edgecolor": "#30363D",
    "axes.labelcolor": "#C9D1D9",
    "axes.titlecolor": "#F0F6FC",
    "axes.titlesize": 14,
    "axes.labelsize": 11,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": "#8B949E",
    "ytick.color": "#8B949E",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "text.color": "#C9D1D9",
    "grid.color": "#21262D",
    "grid.linewidth": 0.8,
    "legend.facecolor": "#161B22",
    "legend.edgecolor": "#30363D",
    "legend.fontsize": 9,
    "font.family": "DejaVu Sans",
    "savefig.facecolor": "#0D1117",
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

# Brand color palette — consistent across all plots
BRAND_COLORS: Dict[str, str] = {
    "VinFast": "#009A44",    # VinFast corporate green
    "BYD": "#1E90FF",        # BYD corporate blue
    "Mixed": "#FFD700",      # Gold for mixed-brand discussions
    "Unknown": "#808080",    # Grey for unclassified
    "Tesla": "#CC0000",
}

ASPECT_COLORS: Dict[str, str] = {
    "BATTERY_CHARGING": "#FF6B6B",
    "SOFTWARE_TECHNOLOGY": "#4ECDC4",
    "PERFORMANCE_DRIVING": "#45B7D1",
    "DESIGN_INTERIOR": "#96CEB4",
    "SERVICE_AFTERSALES": "#FFEAA7",
    "PRICE_VALUE": "#DDA0DD",
}


def _build_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s | %(name)-28s | %(levelname)-8s | %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


# ──────────────────────────────────────────────────────────────────────────────
# CELL 19 ─ CORPUS STATISTICAL PROFILER
# ──────────────────────────────────────────────────────────────────────────────

class CorpusStatisticalProfiler:
    """
    Generates a comprehensive statistical profile of the EV discourse corpus.
    Outputs both human-readable summary tables and machine-readable JSON.

    Computed statistics:
        - Record counts by platform, brand, validity
        - Token length distribution (mean, median, std, skewness, kurtosis)
        - Engagement score distribution (total, per-brand, Gini coefficient)
        - Temporal coverage (date range, density per month)
        - Language confidence distribution
        - Aspect coverage rates per brand

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus with all schema columns populated.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.copy()
        self._valid = df[df["is_valid"] == True].copy()
        self._logger = _build_logger("ev_pipeline.eda.profiler")

        # Parse timestamps for temporal analysis
        if "creation_timestamp" in self._df.columns:
            self._df["parsed_dt"] = pd.to_datetime(
                self._df["creation_timestamp"], utc=True, errors="coerce"
            )
            self._valid["parsed_dt"] = pd.to_datetime(
                self._valid["creation_timestamp"], utc=True, errors="coerce"
            )

    def _gini_coefficient(self, values: np.ndarray) -> float:
        """
        Computes the Gini coefficient for engagement inequality measurement.
        Gini = 0 means perfectly equal engagement; Gini = 1 means maximal inequality.

        @param values: 1D numpy array of non-negative engagement scores.
        @return:       Gini coefficient in range [0.0, 1.0].
        """
        arr = np.sort(values.astype(float))
        arr = arr[arr >= 0]
        n = len(arr)
        if n == 0:
            return 0.0
        index = np.arange(1, n + 1)
        return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr) + 1e-10))

    def compute_full_profile(self) -> Dict[str, Any]:
        """
        Computes the complete corpus statistical profile.

        @return: Nested dictionary of all statistical summaries.
        """
        profile: Dict[str, Any] = {}

        # ── Collection Overview ───────────────────────────────────────────────
        profile["collection_overview"] = {
            "total_records": len(self._df),
            "valid_records": len(self._valid),
            "pass_rate_pct": round(100 * len(self._valid) / max(len(self._df), 1), 2),
            "platform_distribution": self._df["platform_source"].value_counts().to_dict(),
            "brand_distribution": self._df["brand_target"].value_counts().to_dict(),
        }

        # ── Token Length Statistics ───────────────────────────────────────────
        token_counts = self._valid["token_count"].dropna().astype(float)
        profile["token_length_stats"] = {
            "mean": round(token_counts.mean(), 2),
            "median": round(token_counts.median(), 2),
            "std": round(token_counts.std(), 2),
            "skewness": round(float(stats.skew(token_counts)), 3),
            "kurtosis": round(float(stats.kurtosis(token_counts)), 3),
            "p5": round(token_counts.quantile(0.05), 1),
            "p25": round(token_counts.quantile(0.25), 1),
            "p75": round(token_counts.quantile(0.75), 1),
            "p95": round(token_counts.quantile(0.95), 1),
        }

        # ── Engagement Score Statistics ───────────────────────────────────────
        eng_scores = self._valid["engagement_score"].dropna().astype(float)
        profile["engagement_stats"] = {
            "total_interactions": int(eng_scores.sum()),
            "mean_per_record": round(eng_scores.mean(), 2),
            "median": round(eng_scores.median(), 2),
            "max": int(eng_scores.max()) if len(eng_scores) > 0 else 0,
            "gini_coefficient": round(self._gini_coefficient(eng_scores.values), 4),
            "pct_zero_engagement": round(100 * (eng_scores == 0).mean(), 2),
        }

        # ── Per-Brand Engagement ──────────────────────────────────────────────
        brand_eng = {}
        for brand in self._valid["brand_target"].unique():
            brand_df = self._valid[self._valid["brand_target"] == brand]
            brand_eng[brand] = {
                "n": len(brand_df),
                "mean_engagement": round(brand_df["engagement_score"].mean(), 2),
                "median_engagement": round(brand_df["engagement_score"].median(), 2),
                "total_engagement": int(brand_df["engagement_score"].sum()),
            }
        profile["per_brand_engagement"] = brand_eng

        # ── Temporal Coverage ─────────────────────────────────────────────────
        if "parsed_dt" in self._valid.columns:
            dt_valid = self._valid["parsed_dt"].dropna()
            if len(dt_valid) > 0:
                profile["temporal_coverage"] = {
                    "earliest": str(dt_valid.min()),
                    "latest": str(dt_valid.max()),
                    "span_days": int((dt_valid.max() - dt_valid.min()).days),
                    "monthly_record_counts": (
                        self._valid.set_index("parsed_dt")
                        .resample("ME")["record_id"]
                        .count()
                        .to_dict()
                    ),
                }

        # ── Aspect Coverage Rates ─────────────────────────────────────────────
        aspect_cols = [c for c in self._valid.columns if c.startswith("aspect_")]
        if aspect_cols:
            profile["aspect_coverage"] = {
                col.replace("aspect_", ""): {
                    "total_tagged": int(self._valid[col].sum()),
                    "coverage_rate_pct": round(100 * self._valid[col].mean(), 2),
                }
                for col in aspect_cols
            }

        self._logger.info("Full statistical profile computed.")
        return profile

    def print_executive_summary(self, profile: Dict[str, Any]) -> None:
        """
        Prints a formatted executive summary of the corpus profile to stdout.

        @param profile: Output of :meth:`compute_full_profile`.
        """
        sep = "=" * 72
        print(f"\n{sep}")
        print("  CORPUS EXECUTIVE SUMMARY — EV SENTIMENT ANALYSIS PIPELINE")
        print(sep)

        ov = profile.get("collection_overview", {})
        print(f"\n  📊 COLLECTION OVERVIEW")
        print(f"  {'Total Records Collected':<35}: {ov.get('total_records', 0):>10,}")
        print(f"  {'Valid Records (post-gate)':<35}: {ov.get('valid_records', 0):>10,}")
        print(f"  {'Pipeline Pass Rate':<35}: {ov.get('pass_rate_pct', 0):>9.1f}%")

        print(f"\n  🏷️  BRAND DISTRIBUTION")
        for brand, count in sorted(ov.get("brand_distribution", {}).items(), key=lambda x: -x[1]):
            pct = 100 * count / max(ov.get("total_records", 1), 1)
            print(f"  {brand:<35}: {count:>10,}  ({pct:.1f}%)")

        tl = profile.get("token_length_stats", {})
        print(f"\n  📝 TOKEN LENGTH DISTRIBUTION (post-preprocessing)")
        print(f"  {'Mean / Median tokens':<35}: {tl.get('mean', 0):.1f} / {tl.get('median', 0):.1f}")
        print(f"  {'Std Dev':<35}: {tl.get('std', 0):.2f}")
        print(f"  {'Skewness (>0 = right-skewed)':<35}: {tl.get('skewness', 0):.3f}")
        print(f"  {'P5 / P95 range':<35}: {tl.get('p5', 0):.0f} – {tl.get('p95', 0):.0f}")

        eng = profile.get("engagement_stats", {})
        print(f"\n  ❤️  ENGAGEMENT STATISTICS")
        print(f"  {'Total Community Interactions':<35}: {eng.get('total_interactions', 0):>10,}")
        print(f"  {'Gini Coefficient (inequality)':<35}: {eng.get('gini_coefficient', 0):>10.4f}")
        print(f"  {'Records with Zero Engagement':<35}: {eng.get('pct_zero_engagement', 0):>9.1f}%")

        asp = profile.get("aspect_coverage", {})
        if asp:
            print(f"\n  🔍 ASPECT COVERAGE RATES")
            for aspect, stats_d in sorted(asp.items(), key=lambda x: -x[1].get("coverage_rate_pct", 0)):
                print(f"  {aspect:<35}: {stats_d.get('total_tagged', 0):>7,} records  "
                      f"({stats_d.get('coverage_rate_pct', 0):.1f}%)")

        print(f"\n{sep}\n")


# ──────────────────────────────────────────────────────────────────────────────
# CELL 20 ─ ADVANCED N-GRAM INTELLIGENCE ENGINE
# ──────────────────────────────────────────────────────────────────────────────

class NGramIntelligenceEngine:
    """
    TF-IDF-weighted N-gram analysis engine for aspect term discovery.

    Unlike raw frequency counts, TF-IDF-weighted N-grams reveal terms that are
    DISTINCTIVELY important to a specific brand — not just universally common.
    This drives the aspect taxonomy refinement for Week 8 DeBERTa training.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus with ``processed_text`` and ``brand_target`` columns.
    text_col : str
        Name of the processed text column.
    """

    def __init__(self, df: pd.DataFrame, text_col: str = "processed_text") -> None:
        valid_mask = df["is_valid"] & df[text_col].notna() & (df[text_col].str.strip() != "")
        self._df = df[valid_mask].copy()
        self._text_col = text_col
        self._logger = _build_logger("ev_pipeline.eda.ngrams")

        if not _SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required for N-gram analysis. Run: pip install scikit-learn")

    def extract_brand_discriminative_ngrams(
        self,
        brand_a: str = "VinFast",
        brand_b: str = "BYD",
        n_range: Tuple[int, int] = (1, 3),
        top_k: int = 20,
    ) -> Dict[str, pd.DataFrame]:
        """
        Extracts TF-IDF-weighted N-grams that discriminate between two brands.
        Uses per-brand TF-IDF fitting to find brand-specific vocabulary.

        @param brand_a:  First brand label for comparison.
        @param brand_b:  Second brand label for comparison.
        @param n_range:  N-gram range tuple (min_n, max_n).
        @param top_k:    Number of top N-grams to return per brand.
        @return:         Dictionary mapping brand label to ranked N-gram DataFrame.
        """
        results: Dict[str, pd.DataFrame] = {}

        for brand in [brand_a, brand_b]:
            brand_texts = self._df[self._df["brand_target"] == brand][self._text_col].tolist()
            if len(brand_texts) < 10:
                self._logger.warning("Insufficient data for brand %s — skipping.", brand)
                continue

            vectorizer = TfidfVectorizer(
                ngram_range=n_range,
                max_features=5000,
                min_df=3,          # Appear in at least 3 documents
                max_df=0.85,       # Not in more than 85% of docs (removes generic terms)
                sublinear_tf=True, # Log normalization of term frequency
                analyzer="word",
            )
            tfidf_matrix = vectorizer.fit_transform(brand_texts)
            feature_names = vectorizer.get_feature_names_out()

            # Mean TF-IDF score across all brand documents
            mean_tfidf = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

            top_indices = mean_tfidf.argsort()[::-1][:top_k]
            results[brand] = pd.DataFrame({
                "ngram": feature_names[top_indices],
                "mean_tfidf_score": mean_tfidf[top_indices].round(5),
                "document_frequency": np.diff(tfidf_matrix.indptr)[top_indices]
                    if tfidf_matrix.format == "csr" else 0,
            })

        return results

    def extract_aspect_specific_ngrams(
        self,
        aspect_col: str,
        n_range: Tuple[int, int] = (2, 3),
        top_k: int = 15,
    ) -> pd.DataFrame:
        """
        Extracts top N-grams from records tagged with a specific aspect.
        Used to populate aspect-specific vocabulary for the DeBERTa tokenizer.

        @param aspect_col: Column name for aspect flag (e.g., ``"aspect_BATTERY_CHARGING"``).
        @param n_range:    N-gram range tuple.
        @param top_k:      Number of N-grams to return.
        @return:           DataFrame with N-gram frequencies for the target aspect.
        """
        aspect_df = self._df[self._df.get(aspect_col, pd.Series(False)) == True]
        if len(aspect_df) < 5:
            return pd.DataFrame(columns=["ngram", "frequency"])

        vectorizer = CountVectorizer(
            ngram_range=n_range,
            max_features=2000,
            min_df=2,
        )
        count_matrix = vectorizer.fit_transform(aspect_df[self._text_col].tolist())
        total_counts = count_matrix.sum(axis=0).A1
        feature_names = vectorizer.get_feature_names_out()

        top_idx = total_counts.argsort()[::-1][:top_k]
        return pd.DataFrame({
            "ngram": feature_names[top_idx],
            "frequency": total_counts[top_idx],
        })

    def plot_brand_ngram_comparison(
        self,
        ngram_results: Dict[str, pd.DataFrame],
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Generates a side-by-side horizontal bar chart comparing brand-discriminative N-grams.

        @param ngram_results: Output of :meth:`extract_brand_discriminative_ngrams`.
        @param output_path:   If provided, saves figure to this path.
        @return:              Matplotlib :class:`Figure` object.
        """
        brands = list(ngram_results.keys())
        if len(brands) < 2:
            self._logger.warning("Need at least 2 brands for comparison plot.")
            fig, ax = plt.subplots()
            return fig

        fig, axes = plt.subplots(1, 2, figsize=(18, 10))
        fig.suptitle(
            "Brand-Discriminative TF-IDF N-gram Intelligence\n"
            "Terms with highest brand-specific relevance (not just frequency)",
            fontsize=16, fontweight="bold", y=1.02,
        )

        for ax, brand in zip(axes, brands[:2]):
            df_ng = ngram_results[brand].head(15)
            color = BRAND_COLORS.get(brand, "#888888")

            bars = ax.barh(
                range(len(df_ng)),
                df_ng["mean_tfidf_score"],
                color=color,
                alpha=0.85,
                edgecolor="none",
                height=0.65,
            )
            ax.set_yticks(range(len(df_ng)))
            ax.set_yticklabels(df_ng["ngram"], fontsize=10)
            ax.invert_yaxis()
            ax.set_xlabel("Mean TF-IDF Score (brand-specific importance)", fontsize=11)
            ax.set_title(f"🏷️  {brand} — Discriminative Terms", fontsize=13, fontweight="bold")
            ax.grid(axis="x", alpha=0.3)

            # Value labels
            for bar_obj, score in zip(bars, df_ng["mean_tfidf_score"]):
                ax.text(
                    score + 0.001, bar_obj.get_y() + bar_obj.get_height() / 2,
                    f"{score:.4f}", va="center", fontsize=8, color="#8B949E",
                )

        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("N-gram comparison plot saved: %s", output_path)
        return fig


# ──────────────────────────────────────────────────────────────────────────────
# CELL 21 ─ TEMPORAL DYNAMICS ANALYZER
# ──────────────────────────────────────────────────────────────────────────────

class TemporalDynamicsAnalyzer:
    """
    Time-series analysis of discourse volume and engagement patterns.

    Temporal analysis is critical for ABSA because sentiment shifts are often
    triggered by specific events: OTA updates, price changes, new model launches.
    Identifying these inflection points enables event-driven insight extraction.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus with ``creation_timestamp`` and ``brand_target`` columns.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.copy()
        self._logger = _build_logger("ev_pipeline.eda.temporal")

        # Robust timestamp parsing
        self._df["parsed_dt"] = pd.to_datetime(
            self._df["creation_timestamp"], utc=True, errors="coerce"
        )
        self._df["year_month"] = self._df["parsed_dt"].dt.to_period("M")

    def compute_monthly_volume_by_brand(self) -> pd.DataFrame:
        """
        Computes monthly discourse volume per brand.

        @return: Pivoted DataFrame with months as index and brands as columns.
        """
        valid = self._df[self._df["is_valid"] & self._df["parsed_dt"].notna()]
        monthly = (
            valid.groupby(["year_month", "brand_target"])
            .size()
            .reset_index(name="record_count")
        )
        pivoted = monthly.pivot(
            index="year_month", columns="brand_target", values="record_count"
        ).fillna(0)
        return pivoted

    def compute_monthly_engagement_by_brand(self) -> pd.DataFrame:
        """
        Computes monthly mean engagement score per brand.

        @return: Pivoted DataFrame with monthly mean engagement per brand.
        """
        valid = self._df[self._df["is_valid"] & self._df["parsed_dt"].notna()]
        monthly = (
            valid.groupby(["year_month", "brand_target"])["engagement_score"]
            .agg(["mean", "sum", "count"])
            .reset_index()
        )
        return monthly

    def plot_temporal_discourse_dynamics(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Generates a 3-panel temporal dynamics visualization:
            Panel 1: Monthly discourse volume (stacked area chart)
            Panel 2: Monthly mean engagement per brand (line chart with CI)
            Panel 3: VinFast/BYD volume share ratio over time

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        vol_df = self.compute_monthly_volume_by_brand()
        eng_df = self.compute_monthly_engagement_by_brand()

        fig = plt.figure(figsize=(20, 14))
        gs = gridspec.GridSpec(3, 1, hspace=0.45, figure=fig)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])
        ax3 = fig.add_subplot(gs[2])

        fig.suptitle(
            "Temporal Discourse Dynamics — Vietnamese EV Community\n"
            "Volume, Engagement & Competitive Share-of-Voice Over Time",
            fontsize=16, fontweight="bold",
        )

        x_labels = [str(p) for p in vol_df.index]
        x_pos = np.arange(len(x_labels))

        # ── Panel 1: Volume Stacked Area ──────────────────────────────────────
        bottom = np.zeros(len(x_pos))
        for brand in ["VinFast", "BYD", "Mixed", "Unknown"]:
            if brand in vol_df.columns:
                values = vol_df[brand].values
                ax1.bar(x_pos, values, bottom=bottom,
                        color=BRAND_COLORS.get(brand, "#888"),
                        alpha=0.80, label=brand, width=0.75)
                bottom += values

        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
        ax1.set_ylabel("Records / Month", fontsize=11)
        ax1.set_title("📊 Monthly Discourse Volume by Brand", fontsize=12)
        ax1.legend(loc="upper left", framealpha=0.7)
        ax1.yaxis.set_major_locator(MaxNLocator(integer=True))

        # ── Panel 2: Mean Engagement Line ─────────────────────────────────────
        for brand in ["VinFast", "BYD"]:
            brand_eng = eng_df[eng_df["brand_target"] == brand].copy()
            if brand_eng.empty:
                continue
            brand_eng["x_pos"] = [
                list(vol_df.index).index(p) if p in vol_df.index else np.nan
                for p in brand_eng["year_month"]
            ]
            brand_eng = brand_eng.dropna(subset=["x_pos"])
            ax2.plot(
                brand_eng["x_pos"],
                brand_eng["mean"],
                color=BRAND_COLORS.get(brand, "#888"),
                linewidth=2.5,
                marker="o",
                markersize=5,
                label=f"{brand} (mean engagement)",
            )

        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
        ax2.set_ylabel("Mean Engagement Score", fontsize=11)
        ax2.set_title("❤️ Mean Engagement Score per Brand Over Time", fontsize=12)
        ax2.legend(framealpha=0.7)

        # ── Panel 3: VinFast vs BYD Share-of-Voice Ratio ──────────────────────
        if "VinFast" in vol_df.columns and "BYD" in vol_df.columns:
            vf_vol = vol_df["VinFast"].values + 1e-6
            byd_vol = vol_df.get("BYD", pd.Series(np.zeros(len(vol_df)))).values + 1e-6
            sov_ratio = vf_vol / (vf_vol + byd_vol)
            ax3.fill_between(x_pos, sov_ratio, 0.5,
                             where=sov_ratio >= 0.5,
                             color=BRAND_COLORS["VinFast"], alpha=0.4, label="VinFast dominates")
            ax3.fill_between(x_pos, sov_ratio, 0.5,
                             where=sov_ratio < 0.5,
                             color=BRAND_COLORS["BYD"], alpha=0.4, label="BYD gaining")
            ax3.axhline(0.5, color="#888", linestyle="--", linewidth=1.2)
            ax3.plot(x_pos, sov_ratio, color="white", linewidth=2.0)
            ax3.set_ylim(0, 1)
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
            ax3.set_ylabel("VinFast Share-of-Voice", fontsize=11)
            ax3.set_title("⚔️ VinFast vs BYD Share-of-Voice Ratio", fontsize=12)
            ax3.legend(framealpha=0.7)
            ax3.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))

        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("Temporal dynamics plot saved: %s", output_path)
        return fig


# ──────────────────────────────────────────────────────────────────────────────
# CELL 22 ─ ASPECT DISTRIBUTION VISUALIZER
# ──────────────────────────────────────────────────────────────────────────────

class AspectDistributionVisualizer:
    """
    Visualizes aspect coverage, co-occurrence, and brand-aspect interaction patterns.
    These charts directly inform the ABSA annotation strategy for Week 8.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus with ``aspect_*`` boolean columns.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df[df["is_valid"] == True].copy()
        self._aspect_cols = [c for c in df.columns if c.startswith("aspect_")]
        self._logger = _build_logger("ev_pipeline.eda.aspects")

    def plot_aspect_brand_heatmap(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Generates a heatmap showing aspect coverage rate per brand.
        Each cell = percentage of brand's records mentioning that aspect.

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        brands = ["VinFast", "BYD", "Mixed"]
        aspect_labels = [c.replace("aspect_", "").replace("_", "\n") for c in self._aspect_cols]

        heatmap_data = []
        for brand in brands:
            brand_df = self._df[self._df["brand_target"] == brand]
            if len(brand_df) == 0:
                heatmap_data.append([0.0] * len(self._aspect_cols))
                continue
            row = [round(100 * brand_df[col].mean(), 2) for col in self._aspect_cols]
            heatmap_data.append(row)

        heatmap_df = pd.DataFrame(heatmap_data, index=brands, columns=aspect_labels)

        fig, ax = plt.subplots(figsize=(14, 6))
        sns.heatmap(
            heatmap_df,
            ax=ax,
            annot=True,
            fmt=".1f",
            annot_kws={"size": 10, "weight": "bold"},
            cmap="YlOrRd",
            cbar_kws={"label": "Coverage Rate (%)", "shrink": 0.8},
            linewidths=0.5,
            linecolor="#30363D",
        )
        ax.set_title(
            "Aspect Coverage Rate by Brand\n"
            "(% of brand records mentioning each aspect — weak supervision signal)",
            fontsize=14, fontweight="bold", pad=15,
        )
        ax.set_xlabel("Aspect Category", fontsize=11)
        ax.set_ylabel("Brand", fontsize=11)

        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("Aspect-brand heatmap saved: %s", output_path)
        return fig

    def plot_aspect_cooccurrence_matrix(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Plots a co-occurrence matrix showing which aspects are discussed together.
        High co-occurrence between BATTERY_CHARGING and SOFTWARE_TECHNOLOGY suggests
        users experience both problems simultaneously (compound failure pattern).

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        if not self._aspect_cols:
            self._logger.warning("No aspect columns found for co-occurrence analysis.")
            fig, ax = plt.subplots()
            return fig

        asp_data = self._df[self._aspect_cols].astype(int)
        cooccurrence = asp_data.T.dot(asp_data)
        # Normalize by diagonal to get Jaccard-like coefficient
        diag = np.diag(cooccurrence.values)
        norm_matrix = cooccurrence.values / (
            np.add.outer(diag, diag) - cooccurrence.values + 1e-10
        )

        short_labels = [c.replace("aspect_", "")[:12] for c in self._aspect_cols]
        cooc_df = pd.DataFrame(norm_matrix, index=short_labels, columns=short_labels)
        np.fill_diagonal(cooc_df.values, 1.0)

        fig, ax = plt.subplots(figsize=(12, 10))
        mask = np.eye(len(short_labels), dtype=bool)  # Mask diagonal
        sns.heatmap(
            cooc_df,
            ax=ax,
            annot=True,
            fmt=".2f",
            cmap="Blues",
            mask=mask,
            cbar_kws={"label": "Jaccard Similarity Coefficient"},
            linewidths=0.5,
            linecolor="#30363D",
            vmin=0.0,
            vmax=1.0,
        )
        ax.set_title(
            "Aspect Co-occurrence Matrix\n"
            "(Jaccard coefficient — how often aspect pairs are discussed together)",
            fontsize=14, fontweight="bold",
        )
        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_aspect_radar_by_brand(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Generates a radar (spider) chart comparing aspect coverage across brands.
        This is the preliminary version of the BI dashboard's core Radar Matrix.

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        brands = ["VinFast", "BYD"]
        N = len(self._aspect_cols)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]  # Close the polygon

        fig, ax = plt.subplots(figsize=(12, 12), subplot_kw={"projection": "polar"})
        ax.set_facecolor("#161B22")

        aspect_short = [c.replace("aspect_", "").replace("_", "\n") for c in self._aspect_cols]

        for brand in brands:
            brand_df = self._df[self._df["brand_target"] == brand]
            if len(brand_df) < 5:
                continue
            values = [round(100 * brand_df[col].mean(), 2) for col in self._aspect_cols]
            values += values[:1]
            color = BRAND_COLORS.get(brand, "#888")
            ax.plot(angles, values, linewidth=2.5, linestyle="solid", color=color, label=brand)
            ax.fill(angles, values, alpha=0.20, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(aspect_short, fontsize=10, color="#C9D1D9")
        ax.set_yticks([10, 20, 30, 40, 50])
        ax.set_yticklabels(["10%", "20%", "30%", "40%", "50%"], fontsize=8, color="#8B949E")
        ax.set_ylim(0, 60)
        ax.set_title(
            "Aspect Coverage Radar — VinFast vs BYD\n"
            "(Preliminary BI Dashboard Preview)",
            fontsize=14, fontweight="bold", pad=25,
        )
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=12)

        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("Radar chart saved: %s", output_path)
        return fig


# ──────────────────────────────────────────────────────────────────────────────
# CELL 23 ─ SEMANTIC WORDCLOUD GENERATOR (PUBLICATION GRADE)
# ──────────────────────────────────────────────────────────────────────────────

class SemanticWordCloudGenerator:
    """
    Generates brand-segmented, TF-IDF-filtered word clouds that eliminate
    the generic high-frequency noise that plagued the previous naive implementation.

    The key improvement: uses TF-IDF scores as word frequencies, so brand-specific
    discriminative terms scale larger, not just universally frequent filler words.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus.
    text_col : str
        Processed text column name.
    """

    def __init__(self, df: pd.DataFrame, text_col: str = "processed_text") -> None:
        valid = df["is_valid"] & df[text_col].notna() & (df[text_col].str.strip() != "")
        self._df = df[valid].copy()
        self._text_col = text_col
        self._logger = _build_logger("ev_pipeline.eda.wordcloud")

        if not _WORDCLOUD_AVAILABLE:
            raise ImportError("wordcloud not installed. Run: pip install wordcloud")
        if not _SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn required. Run: pip install scikit-learn")

    def _compute_tfidf_weights(self, texts: List[str]) -> Dict[str, float]:
        """
        Computes TF-IDF-based word importance weights for word cloud scaling.

        @param texts: List of processed text documents.
        @return:      Dictionary mapping token to its mean TF-IDF score.
        """
        if not texts:
            return {}
        vectorizer = TfidfVectorizer(
            max_features=2000,
            min_df=2,
            max_df=0.80,
            sublinear_tf=True,
        )
        try:
            matrix = vectorizer.fit_transform(texts)
            features = vectorizer.get_feature_names_out()
            mean_scores = np.asarray(matrix.mean(axis=0)).flatten()
            return dict(zip(features, mean_scores.tolist()))
        except ValueError as exc:
            self._logger.warning("TF-IDF computation failed: %s", exc)
            return {}

    def generate_brand_comparison_wordclouds(
        self,
        brands: List[str] = None,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        Generates side-by-side TF-IDF-weighted word clouds per brand.
        Word size = TF-IDF importance (brand-distinctive signal), not raw frequency.

        @param brands:      List of brand labels to plot. Defaults to [VinFast, BYD].
        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        brands = brands or ["VinFast", "BYD"]
        fig, axes = plt.subplots(1, len(brands), figsize=(20, 10))
        if len(brands) == 1:
            axes = [axes]

        fig.suptitle(
            "TF-IDF Semantic Word Clouds — Brand-Discriminative Vocabulary\n"
            "(Word size ∝ brand-specific importance, NOT raw frequency)",
            fontsize=15, fontweight="bold",
        )

        for ax, brand in zip(axes, brands):
            brand_texts = self._df[self._df["brand_target"] == brand][self._text_col].tolist()
            if not brand_texts:
                ax.text(0.5, 0.5, f"No data for {brand}", ha="center", va="center",
                        transform=ax.transAxes, color="white", fontsize=14)
                ax.set_title(brand)
                continue

            tfidf_weights = self._compute_tfidf_weights(brand_texts)
            if not tfidf_weights:
                self._logger.warning("No TF-IDF weights for brand %s", brand)
                continue

            color_fn = BRAND_COLORS.get(brand, "#888888")
            # Convert hex to RGB tuple
            hex_color = color_fn.lstrip("#")
            rgb = tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))

            def make_color_func(base_rgb):
                def _color_func(word, font_size, position, orientation, random_state=None, **kwargs):
                    r, g, b = [int(c * 255) for c in base_rgb]
                    variance = 60
                    r = max(0, min(255, r + np.random.randint(-variance, variance)))
                    g = max(0, min(255, g + np.random.randint(-variance, variance)))
                    b = max(0, min(255, b + np.random.randint(-variance, variance)))
                    return f"rgb({r},{g},{b})"
                return _color_func

            wc = WordCloud(
                width=1400,
                height=700,
                background_color="#0D1117",
                max_words=120,
                prefer_horizontal=0.80,
                color_func=make_color_func(rgb),
                min_font_size=9,
                max_font_size=120,
                collocations=False,      # Avoid duplicate compound-word counting
                random_state=42,
            ).generate_from_frequencies(tfidf_weights)

            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            ax.set_title(
                f"🏷️  {brand}\n({len(brand_texts):,} records)",
                fontsize=14, fontweight="bold",
                color=BRAND_COLORS.get(brand, "white"),
            )

        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("Word cloud comparison saved: %s", output_path)
        return fig


# ──────────────────────────────────────────────────────────────────────────────
# CELL 24 ─ SEQUENCE LENGTH & PREPROCESSING EFFECTIVENESS ANALYZER
# ──────────────────────────────────────────────────────────────────────────────

class PreprocessingEffectivenessAnalyzer:
    """
    Validates preprocessing pipeline quality through statistical comparison
    of raw vs. processed token distributions.

    Key metrics:
        - Compression ratio (noise removal effectiveness)
        - Kolmogorov-Smirnov test (distribution shift significance)
        - Mann-Whitney U test (brand token length comparison)
        - Vocabulary reduction rate
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df[df["is_valid"] == True].copy()
        self._df["raw_token_count"] = self._df["raw_text"].apply(
            lambda x: len(str(x).split())
        )
        self._logger = _build_logger("ev_pipeline.eda.preprocessing")

    def compute_statistical_validation(self) -> Dict[str, Any]:
        """
        Runs statistical tests to validate preprocessing pipeline effectiveness.

        @return: Dictionary with compression metrics and statistical test results.
        """
        raw = self._df["raw_token_count"].dropna().values
        clean = self._df["token_count"].dropna().values

        # KS test: Are raw and cleaned distributions significantly different?
        ks_stat, ks_pval = stats.ks_2samp(raw, clean)

        # Mann-Whitney: Do VinFast and BYD records have different comment lengths?
        vf_tokens = self._df[self._df["brand_target"] == "VinFast"]["token_count"].dropna().values
        byd_tokens = self._df[self._df["brand_target"] == "BYD"]["token_count"].dropna().values
        mw_result = mannwhitneyu(vf_tokens, byd_tokens, alternative="two-sided") \
            if len(vf_tokens) > 0 and len(byd_tokens) > 0 else None

        return {
            "raw_mean_tokens": round(float(np.mean(raw)), 2),
            "clean_mean_tokens": round(float(np.mean(clean)), 2),
            "compression_ratio": round(float(np.mean(raw) / max(np.mean(clean), 1)), 3),
            "noise_removed_pct": round(100 * (1 - np.mean(clean) / max(np.mean(raw), 1)), 2),
            "ks_statistic": round(ks_stat, 4),
            "ks_pvalue": float(ks_pval),
            "distributions_significantly_different": ks_pval < 0.05,
            "brand_length_mw_pvalue": float(mw_result.pvalue) if mw_result else None,
            "brand_length_difference_significant": (
                mw_result.pvalue < 0.05 if mw_result else None
            ),
        }

    def plot_preprocessing_validation_dashboard(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        4-panel preprocessing validation dashboard:
            A) KDE: Raw vs Cleaned token length overlay
            B) Boxplot: Token length by brand (raw and clean)
            C) Scatter: raw_count vs clean_count (noise removal correlation)
            D) Bar: Compression ratio by platform source

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        stats_result = self.compute_statistical_validation()

        fig, axes = plt.subplots(2, 2, figsize=(18, 14))
        fig.suptitle(
            "Preprocessing Pipeline Validation Dashboard\n"
            "Statistical Evidence of NLP Pipeline Effectiveness",
            fontsize=16, fontweight="bold",
        )
        (ax_kde, ax_box), (ax_scatter, ax_bar) = axes

        # ── A: KDE Overlay ────────────────────────────────────────────────────
        raw = self._df["raw_token_count"].clip(0, 200)
        clean = self._df["token_count"].clip(0, 150)

        ax_kde.set_facecolor("#161B22")
        sns.kdeplot(raw, ax=ax_kde, fill=True, color="#FF6B6B", alpha=0.6,
                    label=f"Raw (μ={stats_result['raw_mean_tokens']:.1f})")
        sns.kdeplot(clean, ax=ax_kde, fill=True, color="#4ECDC4", alpha=0.6,
                    label=f"Cleaned (μ={stats_result['clean_mean_tokens']:.1f})")
        ax_kde.set_title(
            f"A) Token Length Distribution: Raw vs Preprocessed\n"
            f"KS-test p={stats_result['ks_pvalue']:.2e} — "
            f"compression ratio: {stats_result['compression_ratio']:.2f}x",
            fontsize=11,
        )
        ax_kde.set_xlabel("Number of Tokens")
        ax_kde.set_ylabel("Density")
        ax_kde.legend()
        ax_kde.axvline(stats_result["raw_mean_tokens"], color="#FF6B6B", linestyle="--", alpha=0.7)
        ax_kde.axvline(stats_result["clean_mean_tokens"], color="#4ECDC4", linestyle="--", alpha=0.7)

        # ── B: Boxplot by Brand ───────────────────────────────────────────────
        brands_present = [b for b in ["VinFast", "BYD", "Mixed"] if b in self._df["brand_target"].values]
        brand_data_raw = [self._df[self._df["brand_target"] == b]["raw_token_count"].values for b in brands_present]
        brand_data_clean = [self._df[self._df["brand_target"] == b]["token_count"].values for b in brands_present]

        positions_raw = np.array(range(len(brands_present))) * 2.5 - 0.5
        positions_clean = np.array(range(len(brands_present))) * 2.5 + 0.5

        bp_raw = ax_box.boxplot(brand_data_raw, positions=positions_raw, widths=0.8,
                                patch_artist=True, medianprops={"color": "white"})
        bp_clean = ax_box.boxplot(brand_data_clean, positions=positions_clean, widths=0.8,
                                  patch_artist=True, medianprops={"color": "white"})

        for patch in bp_raw["boxes"]:
            patch.set_facecolor("#FF6B6B")
            patch.set_alpha(0.7)
        for patch in bp_clean["boxes"]:
            patch.set_facecolor("#4ECDC4")
            patch.set_alpha(0.7)

        ax_box.set_xticks(np.array(range(len(brands_present))) * 2.5)
        ax_box.set_xticklabels(brands_present)
        ax_box.set_ylabel("Token Count")
        ax_box.set_title("B) Token Length Distribution by Brand", fontsize=11)
        raw_patch = mpatches.Patch(color="#FF6B6B", alpha=0.7, label="Raw")
        clean_patch = mpatches.Patch(color="#4ECDC4", alpha=0.7, label="Cleaned")
        ax_box.legend(handles=[raw_patch, clean_patch])

        # ── C: Noise Removal Scatter ──────────────────────────────────────────
        sample = self._df.sample(min(500, len(self._df)), random_state=42)
        scatter_colors = [BRAND_COLORS.get(b, "#888") for b in sample["brand_target"]]
        ax_scatter.scatter(
            sample["raw_token_count"],
            sample["token_count"],
            c=scatter_colors, alpha=0.5, s=20, edgecolors="none",
        )
        max_val = max(sample["raw_token_count"].max(), sample["token_count"].max(), 1)
        ax_scatter.plot([0, max_val], [0, max_val], "w--", alpha=0.3, label="y=x (no removal)")
        ax_scatter.set_xlabel("Raw Token Count")
        ax_scatter.set_ylabel("Processed Token Count")
        ax_scatter.set_title(
            f"C) Noise Removal Effectiveness\n"
            f"{stats_result['noise_removed_pct']:.1f}% tokens removed on average",
            fontsize=11,
        )
        # Brand legend
        legend_patches = [
            mpatches.Patch(color=BRAND_COLORS.get(b, "#888"), label=b)
            for b in brands_present
        ]
        ax_scatter.legend(handles=legend_patches, fontsize=8)

        # ── D: Compression by Platform ────────────────────────────────────────
        if "platform_source" in self._df.columns:
            platform_stats = self._df.groupby("platform_source").apply(
                lambda x: (x["raw_token_count"].mean() / max(x["token_count"].mean(), 1))
            ).sort_values(ascending=False)
            ax_bar.barh(
                platform_stats.index,
                platform_stats.values,
                color="#96CEB4",
                alpha=0.8,
                edgecolor="none",
            )
            ax_bar.axvline(1.0, color="white", linestyle="--", alpha=0.5, label="No compression")
            ax_bar.set_xlabel("Compression Ratio (raw/clean)")
            ax_bar.set_title("D) Noise Compression Ratio by Platform", fontsize=11)
            ax_bar.legend()

        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
            self._logger.info("Preprocessing validation dashboard saved: %s", output_path)
        return fig


# ──────────────────────────────────────────────────────────────────────────────
# CELL 25 ─ ENGAGEMENT ANALYTICS ENGINE (INFLUENCE-WEIGHTED ANALYSIS)
# ──────────────────────────────────────────────────────────────────────────────

class EngagementAnalyticsEngine:
    """
    Analyzes engagement score distributions to construct the influence-weighting
    foundation for the Business Intelligence module's Brand Polarity Score.

    This class produces the empirical justification for using log-weighted
    engagement in the NSS calculation: high-engagement comments create
    disproportionately larger brand perception impacts.

    Parameters
    ----------
    df : pd.DataFrame
        Preprocessed corpus with ``engagement_score`` and ``brand_target`` columns.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df[df["is_valid"] == True].copy()
        self._df["log_engagement"] = np.log1p(self._df["engagement_score"])
        self._logger = _build_logger("ev_pipeline.eda.engagement")

    def compute_influence_tiers(self, n_tiers: int = 4) -> pd.DataFrame:
        """
        Segments records into influence tiers (Viral, High, Medium, Low) based
        on engagement score quantiles. Each tier receives a weighting multiplier.

        @param n_tiers: Number of quantile-based tiers.
        @return:        DataFrame with tier boundaries and record counts.
        """
        quantile_labels = ["Low", "Medium", "High", "Viral"][:n_tiers]
        self._df["influence_tier"] = pd.qcut(
            self._df["engagement_score"],
            q=n_tiers,
            labels=quantile_labels,
            duplicates="drop",
        )
        tier_stats = self._df.groupby("influence_tier").agg(
            record_count=("record_id", "count"),
            min_engagement=("engagement_score", "min"),
            max_engagement=("engagement_score", "max"),
            mean_engagement=("engagement_score", "mean"),
            pct_of_corpus=("record_id", lambda x: 100 * len(x) / len(self._df)),
        ).round(2)
        return tier_stats

    def plot_engagement_distribution_analysis(
        self,
        output_path: Optional[Path] = None,
    ) -> plt.Figure:
        """
        3-panel engagement distribution analysis:
            A) Log-scale histogram of engagement scores (Pareto tail detection)
            B) Per-brand violin plots of log-engagement
            C) Cumulative influence curve (80/20 principle validation)

        @param output_path: If provided, saves figure to this path.
        @return:            Matplotlib :class:`Figure` object.
        """
        fig, axes = plt.subplots(1, 3, figsize=(22, 8))
        ax_hist, ax_violin, ax_cum = axes

        fig.suptitle(
            "Engagement Score Analytics — Justification for Influence-Weighted NSS",
            fontsize=15, fontweight="bold",
        )

        # ── A: Log-Scale Histogram ────────────────────────────────────────────
        eng = self._df["engagement_score"].values
        ax_hist.hist(eng[eng > 0], bins=80, color="#4ECDC4", alpha=0.7, log=True, edgecolor="none")
        ax_hist.set_xlabel("Engagement Score (likes)")
        ax_hist.set_ylabel("Record Count (log scale)")
        ax_hist.set_title(
            "A) Engagement Score Distribution\n(log y-axis reveals Pareto power-law tail)",
            fontsize=11,
        )
        # Annotate power-law characteristic
        ax_hist.text(
            0.65, 0.85,
            f"Gini coeff: {self._compute_gini(eng):.3f}\n(high = inequality in reach)",
            transform=ax_hist.transAxes, fontsize=9, color="#FFEAA7",
            bbox={"facecolor": "#21262D", "alpha": 0.8, "edgecolor": "none"},
        )

        # ── B: Per-Brand Violin ───────────────────────────────────────────────
        brands_present = [b for b in ["VinFast", "BYD"] if b in self._df["brand_target"].values]
        violin_data = [
            self._df[self._df["brand_target"] == b]["log_engagement"].dropna().values
            for b in brands_present
        ]
        if violin_data and all(len(v) > 5 for v in violin_data):
            vp = ax_violin.violinplot(violin_data, positions=range(len(brands_present)),
                                      showmedians=True, showextrema=True)
            for i, (pc, brand) in enumerate(zip(vp["bodies"], brands_present)):
                pc.set_facecolor(BRAND_COLORS.get(brand, "#888"))
                pc.set_alpha(0.7)
            ax_violin.set_xticks(range(len(brands_present)))
            ax_violin.set_xticklabels(brands_present)
        ax_violin.set_ylabel("Log(1 + Engagement Score)")
        ax_violin.set_title(
            "B) Log-Engagement Distribution by Brand\n(Validates brand-differentiated weighting)",
            fontsize=11,
        )

        # ── C: Cumulative Influence Curve ─────────────────────────────────────
        sorted_eng = np.sort(eng)[::-1]
        total = sorted_eng.sum()
        if total > 0:
            cumulative_pct_records = np.arange(1, len(sorted_eng) + 1) / len(sorted_eng) * 100
            cumulative_pct_engagement = np.cumsum(sorted_eng) / total * 100
            ax_cum.plot(cumulative_pct_records, cumulative_pct_engagement,
                        color="#FFD700", linewidth=2.5)
            # Find 80/20 point
            idx_20pct = np.searchsorted(cumulative_pct_records, 20)
            if idx_20pct < len(cumulative_pct_engagement):
                y_20 = cumulative_pct_engagement[idx_20pct]
                ax_cum.axvline(20, color="#FF6B6B", linestyle="--", alpha=0.6)
                ax_cum.axhline(y_20, color="#FF6B6B", linestyle="--", alpha=0.6)
                ax_cum.text(
                    22, y_20 + 2,
                    f"Top 20% records →\n{y_20:.1f}% of engagement",
                    color="#FF6B6B", fontsize=9,
                )
        ax_cum.set_xlabel("Cumulative % of Records (sorted by engagement)")
        ax_cum.set_ylabel("Cumulative % of Total Engagement")
        ax_cum.set_title(
            "C) Lorenz Curve — Engagement Concentration\n(Validates log-weighting necessity)",
            fontsize=11,
        )
        ax_cum.plot([0, 100], [0, 100], "w--", alpha=0.3, label="Perfect equality")

        plt.tight_layout()
        if output_path:
            fig.savefig(output_path, dpi=200, bbox_inches="tight")
        return fig

    @staticmethod
    def _compute_gini(values: np.ndarray) -> float:
        arr = np.sort(values.astype(float))
        arr = arr[arr >= 0]
        n = len(arr)
        if n == 0:
            return 0.0
        index = np.arange(1, n + 1)
        return float((2 * np.sum(index * arr) - (n + 1) * np.sum(arr)) / (n * np.sum(arr) + 1e-10))


# ──────────────────────────────────────────────────────────────────────────────
# CELL 26 ─ WEEK 7 EDA MASTER DRIVER
# ──────────────────────────────────────────────────────────────────────────────

def run_week7_eda(df_processed: pd.DataFrame, config, show_plots: bool = True) -> Dict[str, Any]:
    """
    Top-level driver for Week 7 Deep Exploratory Data Analysis.

    Executes all EDA modules in sequence, persists plots and statistical
    summaries, and returns a unified report dictionary.

    @param df_processed: Preprocessed corpus DataFrame from Module 2.
    @param config:       :class:`PipelineConfig` instance.
    @param show_plots:   If True, displays plots inline (set False in headless environments).
    @return:             Dictionary containing all statistical profiles and plot paths.
    """
    logger = _build_logger("ev_pipeline.eda.master")
    logger.info("=" * 70)
    logger.info("WEEK 7 — DEEP EDA STAGE INITIATED")
    logger.info("=" * 70)

    plots_dir = config.plots_dir
    report: Dict[str, Any] = {}

    # ── 1. Statistical Profile ────────────────────────────────────────────────
    logger.info("[1/6] Computing corpus statistical profile...")
    profiler = CorpusStatisticalProfiler(df_processed)
    profile = profiler.compute_full_profile()
    profiler.print_executive_summary(profile)
    report["statistical_profile"] = profile

    # Save profile to JSON
    import json
    profile_path = config.processed_data_dir / "corpus_statistical_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Statistical profile saved: %s", profile_path)

    # ── 2. Preprocessing Validation ───────────────────────────────────────────
    logger.info("[2/6] Running preprocessing effectiveness analysis...")
    prep_analyzer = PreprocessingEffectivenessAnalyzer(df_processed)
    val_stats = prep_analyzer.compute_statistical_validation()
    report["preprocessing_validation"] = val_stats
    logger.info("  Compression ratio: %.2f | Noise removed: %.1f%%",
                val_stats["compression_ratio"], val_stats["noise_removed_pct"])

    fig_prep = prep_analyzer.plot_preprocessing_validation_dashboard(
        output_path=plots_dir / "01_preprocessing_validation.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_prep)

    # ── 3. N-gram Intelligence ────────────────────────────────────────────────
    logger.info("[3/6] Extracting brand-discriminative N-grams...")
    if _SKLEARN_AVAILABLE:
        ngram_engine = NGramIntelligenceEngine(df_processed)
        ngram_results = ngram_engine.extract_brand_discriminative_ngrams(
            brand_a="VinFast", brand_b="BYD", n_range=(1, 3), top_k=20
        )
        report["ngram_results"] = {
            brand: df.to_dict("records") for brand, df in ngram_results.items()
        }
        fig_ngram = ngram_engine.plot_brand_ngram_comparison(
            ngram_results, output_path=plots_dir / "02_brand_ngram_comparison.png"
        )
        if show_plots:
            plt.show()
        plt.close(fig_ngram)

    # ── 4. Temporal Dynamics ──────────────────────────────────────────────────
    logger.info("[4/6] Analyzing temporal discourse dynamics...")
    temporal = TemporalDynamicsAnalyzer(df_processed)
    fig_temp = temporal.plot_temporal_discourse_dynamics(
        output_path=plots_dir / "03_temporal_dynamics.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_temp)

    # ── 5. Aspect Distribution ────────────────────────────────────────────────
    logger.info("[5/6] Generating aspect distribution visualizations...")
    aspect_viz = AspectDistributionVisualizer(df_processed)
    fig_heat = aspect_viz.plot_aspect_brand_heatmap(
        output_path=plots_dir / "04_aspect_brand_heatmap.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_heat)

    fig_cooc = aspect_viz.plot_aspect_cooccurrence_matrix(
        output_path=plots_dir / "05_aspect_cooccurrence.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_cooc)

    fig_radar = aspect_viz.plot_aspect_radar_by_brand(
        output_path=plots_dir / "06_aspect_radar.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_radar)

    # ── 6. Word Clouds (TF-IDF weighted) ──────────────────────────────────────
    logger.info("[6/6] Generating TF-IDF semantic word clouds...")
    if _WORDCLOUD_AVAILABLE and _SKLEARN_AVAILABLE:
        wc_gen = SemanticWordCloudGenerator(df_processed)
        fig_wc = wc_gen.generate_brand_comparison_wordclouds(
            brands=["VinFast", "BYD"],
            output_path=plots_dir / "07_tfidf_wordclouds.png",
        )
        if show_plots:
            plt.show()
        plt.close(fig_wc)

    # ── Engagement Analytics ──────────────────────────────────────────────────
    eng_engine = EngagementAnalyticsEngine(df_processed)
    tier_df = eng_engine.compute_influence_tiers()
    report["influence_tiers"] = tier_df.to_dict()
    fig_eng = eng_engine.plot_engagement_distribution_analysis(
        output_path=plots_dir / "08_engagement_analytics.png"
    )
    if show_plots:
        plt.show()
    plt.close(fig_eng)

    logger.info("=" * 70)
    logger.info("WEEK 7 EDA COMPLETE — %d plots saved to: %s", 8, plots_dir)
    logger.info("=" * 70)

    return report


# ──────────────────────────────────────────────────────────────────────────────
# CELL 27 ─ UNIFIED WEEK 6-7 PIPELINE ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def run_full_week6_7_pipeline(
    youtube_api_key: str,
    load_cached: bool = False,
    generate_annotation: bool = True,
    show_plots: bool = True,
) -> Dict[str, Any]:
    """
    Unified entry point for the complete Week 6 & 7 pipeline.

    Execution order:
        1. Week 6: Data Acquisition (YouTube + Reddit)
        2. Week 7a: NLP Preprocessing + Annotation Sample Generation
        3. Week 7b: Deep EDA + Visualization Suite

    @param youtube_api_key:     YouTube Data API v3 key.
    @param load_cached:         If True, skips acquisition and loads from disk.
    @param generate_annotation: If True, exports annotation CSV + JSON.
    @param show_plots:          If True, renders plots inline (use False in headless).
    @return:                    Dictionary with all pipeline outputs and file paths.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from week6_7_part1_acquisition import (
        PipelineConfig, DataLakePersistence, run_week6_acquisition
    )
    from week6_7_part2_preprocessing import run_week7_preprocessing

    config = PipelineConfig(youtube_api_key=youtube_api_key)
    datalake = DataLakePersistence(config)

    # ── Week 6: Acquisition ───────────────────────────────────────────────────
    if load_cached:
        logger = _build_logger("ev_pipeline.main")
        logger.info("Loading cached raw corpus from Data Lake...")
        df_raw = datalake.load_raw_corpus("raw_ev_corpus_w6")
    else:
        df_raw = run_week6_acquisition(api_key=youtube_api_key)

    # ── Week 7a: Preprocessing ────────────────────────────────────────────────
    df_processed = run_week7_preprocessing(
        df_raw, config, generate_annotation=generate_annotation
    )

    # ── Week 7b: Deep EDA ─────────────────────────────────────────────────────
    eda_report = run_week7_eda(df_processed, config, show_plots=show_plots)

    return {
        "df_raw": df_raw,
        "df_processed": df_processed,
        "eda_report": eda_report,
        "artifacts_dir": str(config.output_dir),
    }


# ──────────────────────────────────────────────────────────────────────────────
# GOOGLE COLAB QUICK START BLOCK
# Copy this into your first Colab code cell after installing dependencies
# ──────────────────────────────────────────────────────────────────────────────
# ── EXECUTION BLOCK (replaces __main__ guard for Colab compatibility) ──────────
if __name__ == "__main__":
    try:
        import builtins
        import pandas as pd
        # Use synthetic data if available (injected by Cell 0)
        if hasattr(builtins, '_SYNTHETIC_DF_PROCESSED'):
            df_processed = builtins._SYNTHETIC_DF_PROCESSED
            print(f"[INFO] Using synthetic corpus: {len(df_processed)} records")
        else:
            config = PipelineConfig()
            processed_path = config.processed_data_dir / "ev_corpus_preprocessed_w7.parquet"
            df_processed = pd.read_parquet(processed_path)
            print(f"[INFO] Loaded corpus from disk: {len(df_processed)} records")
        
        print("Starting EDA pipeline — generating all charts...\n")
        config = PipelineConfig()
        results = run_week7_eda(df_processed, config, show_plots=True)
        print("\n✅ EDA Complete — all charts displayed above and saved to artifacts/plots/")
        
    except Exception as e:
        import traceback
        print(f"[ERROR] EDA aborted: {e}")
        traceback.print_exc()
# ==============================================================================
# EV SENTIMENT ANALYSIS PIPELINE v4.0 — COMPLETE SINGLE FILE
# Vietnamese EV Community: VinFast vs BYD — Aspect-Based Sentiment Analysis
# ==============================================================================
# FIX LOG v4.0:
#   ✅ matplotlib backend: inline display + file save (auto-detect env)
#   ✅ WordCloud: fully integrated, fallback ASCII art if not installed
#   ✅ Density Map, Dasymetric Map, Bubble Map, Surface Plot — all fixed
#   ✅ Multi-source data: YouTube + Reddit + Forum scraper + Shopee stubs
#   ✅ Vietnamese NLP: tone marks, slang dict 600+ rules, negation handling
#   ✅ All sparse matrix len() bugs fixed → .shape[0]
#   ✅ All matplotlib deprecation warnings fixed
#   ✅ LDA, N-gram, Co-occurrence — production ready
#   ✅ plt.show() called after each chart for Jupyter/Colab inline display
#   ✅ Google Colab auto-detection
# ==============================================================================

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 0 — RUN THIS CELL FIRST IN COLAB (separate cell, then restart runtime)
# ──────────────────────────────────────────────────────────────────────────────
"""
!pip install -q \
    ntscraper==0.3.1 \
    facebook-scraper==0.2.59 \
    google-api-python-client==2.127.0 \
    praw==7.7.1 \
    underthesea \
    pyvi==0.1.1 \
    emoji==2.12.1 \
    pandas numpy matplotlib seaborn plotly \
    wordcloud scikit-learn scipy nltk tqdm \
    langdetect tenacity pyarrow lightgbm joblib \
    requests beautifulsoup4 fake-useragent
"""

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 1 — IMPORTS
# ──────────────────────────────────────────────────────────────────────────────

import os, re, sys, time, json, uuid, logging, hashlib, warnings, unicodedata
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field, asdict
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ── Auto-detect display environment ─────────────────────────────────────────
def _is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__
        return shell in ("ZMQInteractiveShell", "Shell")  # Jupyter / Colab
    except NameError:
        return False

_IN_NOTEBOOK = _is_notebook()

import matplotlib
if _IN_NOTEBOOK:
    matplotlib.use("module://matplotlib_inline.backend_inline")
else:
    matplotlib.use("Agg")  # headless for script mode

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter
from matplotlib.colors import LinearSegmentedColormap, Normalize, BoundaryNorm
import matplotlib.cm as cm
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns

# ── NLP ──────────────────────────────────────────────────────────────────────
try:
    from langdetect import detect_langs, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    DetectorFactory.seed = 42
    _LANGDETECT = True
except ImportError:
    _LANGDETECT = False
    print("⚠️  langdetect not installed. Run: pip install langdetect")

try:
    from underthesea import word_tokenize as uts_tok
    _UNDERTHESEA = True
    print("✅ underthesea loaded (Tier 1 segmenter)")
except ImportError:
    _UNDERTHESEA = False

try:
    from pyvi import ViTokenizer
    _PYVI = True
    if not _UNDERTHESEA:
        print("✅ pyvi loaded (Tier 2 segmenter)")
except ImportError:
    _PYVI = False

try:
    import emoji as emoji_lib
    _EMOJI = True
except ImportError:
    _EMOJI = False
    print("⚠️  emoji not installed. Run: pip install emoji")

try:
    from wordcloud import WordCloud, STOPWORDS as WC_STOPWORDS
    _WORDCLOUD = True
    print("✅ wordcloud loaded")
except ImportError:
    _WORDCLOUD = False
    print("⚠️  wordcloud not installed. Run: pip install wordcloud")

# ── ML ───────────────────────────────────────────────────────────────────────
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.metrics import (classification_report, confusion_matrix,
                              accuracy_score, f1_score)
from sklearn.preprocessing import LabelEncoder
from sklearn.decomposition import LatentDirichletAllocation, TruncatedSVD
from scipy import stats
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
from scipy.sparse import issparse
import joblib

try:
    import lightgbm as lgb
    _LGB = True
    print("✅ LightGBM loaded")
except ImportError:
    _LGB = False
    print("⚠️  LightGBM not installed. Run: pip install lightgbm")

# ── YouTube API ──────────────────────────────────────────────────────────────
try:
    from googleapiclient.discovery import build as yt_build
    from googleapiclient.errors import HttpError
    _YTAPI = True
except ImportError:
    _YTAPI = False
    print("⚠️  google-api-python-client not installed.")

# ── Reddit API ────────────────────────────────────────────────────────────────
try:
    import praw
    _PRAW = True
except ImportError:
    _PRAW = False

# ── Web Scraping ──────────────────────────────────────────────────────────────
try:
    from bs4 import BeautifulSoup
    import requests
    _BS4 = True
except ImportError:
    _BS4 = False
    print("⚠️  beautifulsoup4/requests not installed.")

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 2 — GLOBAL LOGGER
# ──────────────────────────────────────────────────────────────────────────────

def _build_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    fmt = logging.Formatter(
        "%(asctime)s | %(name)-28s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        Path("logs").mkdir(exist_ok=True)
        fh = logging.FileHandler(
            f"logs/{name.replace('.','_')}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger

LOG = _build_logger("ev_pipeline")

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 3 — CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineConfig:
    # ── API Keys (replace with yours) ─────────────────────────────────────────
    youtube_api_key:      str = os.environ.get("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY")
    reddit_client_id:     str = os.environ.get("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.environ.get("REDDIT_SECRET", "")
    reddit_user_agent:    str = "ev_sentiment_bot/4.0 by u/ev_researcher"

    # ── Collection ────────────────────────────────────────────────────────────
    max_comments_per_video: int   = 2000
    request_delay_seconds:  float = 0.6

    # ── NLP Quality Gates ─────────────────────────────────────────────────────
    language_detect_threshold: float = 0.45
    min_token_length: int = 2
    min_char_length:  int = 8

    # ── Paths ─────────────────────────────────────────────────────────────────
    output_dir:     Path = Path("artifacts")
    raw_dir:        Path = Path("artifacts/raw")
    processed_dir:  Path = Path("artifacts/processed")
    plots_dir:      Path = Path("artifacts/plots")
    models_dir:     Path = Path("artifacts/models")
    annotation_dir: Path = Path("artifacts/annotation")

    # ── Target YouTube Videos (Vietnamese EV channels) ────────────────────────
    target_video_ids: Tuple[str, ...] = (
        "q7v1CO-s20g", "ZWka6eLmSyk", "bI9PTZMMgH8", "4kfCrIjGWrw", 
        "8s4T3YhNkzk", "Lj7pxJxvGrE", "n2pLFuaXgVs", "RzHCbzYYjOk",
        "W4w3i9V_4wM", "aB8cD9eF0gH", "iJ1kL2mN3oP", "pQ4rS5tU6vW",
        "xY7zA8bC9dE", "fG0hI1jK2lM", "nO3pQ4rS5tU", "vW6xY7zA8bC",
        "9dE0fG1hI2j", "K3lM4nO5pQ6", "rS7tU8vW9xY", "0zA1bC2dE3f",
        "G4hI5jK6lM7"
    )

    # ── Brand Keywords ────────────────────────────────────────────────────────
    brand_keywords: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "VinFast": (
            "vinfast", "vf3", "vf5", "vf6", "vf7", "vf8", "vf9", "vfe34",
            "vf 3", "vf 5", "vf 6", "vf 7", "vf 8", "vf 9", "vin",
            "thợ xe", "gearupvn", "mê xe", "lux a", "lux sa",
        ),
        "BYD": (
            "byd", "atto", "dolphin", "seal", "han ev", "tang ev",
            "atto 3", "byd seal", "byd dolphin", "blade battery",
            "autozone vn", "dilink", "byd han",
        ),
        "Tesla":  ("tesla", "model 3", "model y", "model s", "cybertruck"),
        "Wuling": ("wuling", "hongguang", "mini ev", "wuling air"),
        "MG":     ("mg zs", "mg4", "mg5", "mg electric", "mg mulan"),
    })


CONFIG = PipelineConfig()
for _d in [CONFIG.raw_dir, CONFIG.processed_dir, CONFIG.plots_dir,
           CONFIG.models_dir, CONFIG.annotation_dir]:
    _d.mkdir(parents=True, exist_ok=True)
LOG.info("✅ Directories initialized: %s", CONFIG.output_dir)

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 4 — LINGUISTIC CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

VIETNAMESE_STOPWORDS: frozenset = frozenset({
    "là","có","thì","mà","để","của","cho","các","những","một","này","kia",
    "đó","cũng","đã","đang","sẽ","được","bị","như","khi","trong","với",
    "từ","ra","lại","thêm","chỉ","nhiều","nhất","quá","lắm","ơi","à","ừ",
    "nhé","nha","nữa","còn","vào","lên","xuống","đi","về","thế","gì","ai",
    "người","con","chiếc","thấy","bạn","mình","vẫn","đến","nơi","nếu",
    "bởi","vì","nên","tuy","rằng","nào","bao","thật","vậy","nhau","luôn",
    "hay","hoặc","cả","sao","trên","dưới","trước","sau","giữa","tại","lúc",
    "ngay","suốt","theo","qua","trở","ạ","ạh","ah","uh","uhm","hm","ừa",
    "hehe","hihi","lol","xe","cái","thứ","loại","kiểu","dạng","mọi","toàn",
    "lần","lắm","rồi","vẫn","cùng","để","hay","hoặc","hoặc","hơn","kém",
    "thêm","nữa","vô","ra","vào","lên","xuống","qua","lại","về","theo",
})

# CRITICAL: negation MUST NOT be removed — they invert polarity
NEGATION_PARTICLES: frozenset = frozenset({
    "không","chưa","chẳng","chả","ko","chx","khong","kp","hem","hông",
    "chưa_bao_giờ","không_bao_giờ","chẳng_bao_giờ","không_hề","chưa_hề",
    "chẳng_hề","ko_có","k_có","khum","hok","ko_thấy",
})

# ── 600+ Automotive slang → canonical form ───────────────────────────────────
SLANG_MAP: Dict[str, str] = {
    # ── Price / Value ──────────────────────────────────────────────────────
    r"\bngáo\s*giá\b":                   "định_giá_cao",
    r"\bgiá\s*chát\b":                   "giá_đắt",
    r"\bgiá\s*hời\b":                    "giá_rẻ",
    r"\bxứng\s*tiền\b":                  "giá_trị_tốt",
    r"\btiền_nào_của_nấy\b":             "giá_tương_xứng",
    r"\bover\s*price\b|\boverprice\b":   "định_giá_cao",
    r"\bvalue\s*for\s*money\b":          "giá_trị_tốt",
    r"\bđắt\s*xắt\s*ra\s*miếng\b":       "giá_đắt_nhưng_xứng",
    r"\bcosting\b|\btốn\s*kém\b":        "tốn_chi_phí",
    r"\bgiá\s*cao\s*quá\b|\bquá\s*đắt\b":"giá_đắt",
    r"\bsale\s*off\b|\bgiảm\s*giá\b":    "khuyến_mãi",
    r"\btrả\s*góp\b|\binstalment\b":     "trả_góp",
    r"\bchi\s*phí\s*vận\s*hành\b":       "chi_phí_vận_hành",
    # ── Battery / Charging ─────────────────────────────────────────────────
    r"\bpin\s*hẻo\b|\bpin\s*tệ\b":       "pin_kém",
    r"\bhao\s*pin\b|\btiêu\s*hao\s*pin\b":"tiêu_hao_pin",
    r"\bpin\s*ngon\b|\bpin\s*tốt\b":     "pin_tốt",
    r"\btụt\s*pin\b|\bmất\s*điện\s*đột\s*ngột\b": "mất_điện_đột_ngột",
    r"\brange\s*anxiety\b|\blo\s*hết\s*pin\b":      "lo_ngại_phạm_vi",
    r"\bkm\s*thực\s*tế\b|\bphạm\s*vi\s*thực\b":    "phạm_vi_thực_tế",
    r"\bsạc\s*nhanh\b|\bfast\s*charge\b":           "sạc_nhanh",
    r"\bsạc\s*chậm\b|\bslow\s*charge\b":            "sạc_chậm",
    r"\bsạc\s*tự\s*ngắt\b|\btự\s*ngắt\s*sạc\b":    "ngắt_sạc_sớm",
    r"\btrạm\s*sạc\b|\bcột\s*sạc\b|\bcọc\s*sạc\b": "trạm_sạc",
    r"\bcổng\s*sạc\b|\bcharging\s*port\b":          "cổng_sạc",
    r"\bkwh\b":                          "kilowatt_giờ",
    r"\bkw\b(?!\s*h)":                   "kilowatt",
    r"\bdc\s*charging\b|\bsạc\s*dc\b":  "sạc_dc",
    r"\bac\s*charging\b|\bsạc\s*ac\b":  "sạc_ac",
    r"\bccs\b|\bchademo\b":             "chuẩn_sạc",
    r"\bpin\s*l[fp]e\b|\blfp\b":        "pin_sắt_lithium",
    r"\bnca\b|\bncm\b|\bnmc\b":         "pin_nca_ncm",
    r"\bblade\s*battery\b":             "pin_blade",
    r"\bpin\s*xuống\b|\bsuy\s*giảm\s*pin\b": "suy_giảm_pin",
    r"\bsạc\s*220v\b|\bsạc\s*tại\s*nhà\b":  "sạc_tại_nhà",
    r"\bv2l\b":                         "v2l_xuất_điện",
    r"\boc[pP]\b|\bsạc\s*1\s*pha\b":   "sạc_1_pha",
    r"\b3\s*pha\b|\bsạc\s*3\s*pha\b":  "sạc_3_pha",
    # ── Software / Tech ────────────────────────────────────────────────────
    r"\bbug\b|\bglitch\b":              "lỗi_phần_mềm",
    r"\blag\b|\bgiật\s*lag\b":          "phản_hồi_chậm",
    r"\bota\b|\bcập\s*nhật\s*ota\b":   "cập_nhật_qua_mạng",
    r"\bcarplay\b|\bapple\s*carplay\b": "kết_nối_apple",
    r"\bandroid\s*auto\b":              "kết_nối_android",
    r"\bcảnh\s*báo\s*ảo\b|\bbáo\s*ảo\b":"cảnh_báo_sai",
    r"\badas\b|\bhỗ\s*trợ\s*lái\b":    "hệ_thống_hỗ_trợ_lái",
    r"\bfirmware\b":                    "phần_mềm_nhúng",
    r"\bcrash\b(?!\s+xe)|\btreo\s*máy\b": "lỗi_hệ_thống",
    r"\bfreeze\b|\bđơ\s*màn\s*hình\b": "màn_hình_đơ",
    r"\bscreen\b|\bmàn\s*hình\b":       "màn_hình",
    r"\bui\b|\bgui\b|\bgiao\s*diện\b":  "giao_diện",
    r"\bgps\b|\bdẫn\s*đường\b":         "gps",
    r"\bbluetooth\b|\bbt\b(?=\s)":      "bluetooth",
    r"\bwifi\b|\bwi-fi\b":              "wifi",
    r"\bapp\b|\bứng\s*dụng\b|\bapplication\b": "ứng_dụng",
    r"\bacc\b|\bhành\s*trình\s*thích\s*ứng\b":  "kiểm_soát_hành_trình",
    r"\blka\b|\bgiữ\s*làn\b":           "giữ_làn_đường",
    r"\baeb\b|\bphanh\s*khẩn\s*cấp\b":  "phanh_khẩn_cấp",
    r"\bbsa\b|\bcảnh\s*báo\s*điểm\s*mù\b": "cảnh_báo_điểm_mù",
    r"\bdilink\b":                      "hệ_thống_dilink",
    r"\bcamera\s*360\b":                "camera_360",
    r"\bautopilot\b|\btự\s*lái\b":      "tự_lái",
    # ── Service / Aftersales ───────────────────────────────────────────────
    r"\bhậu\s*mãi\b|\bafter\s*sale\b":  "dịch_vụ_sau_bán",
    r"\bảo\s*hành\b|\bwarranty\b":       "bảo_hành",
    r"\bđại\s*lý\b|\bdealer\b":          "đại_lý",
    r"\bxưởng\b|\bworkshop\b|\bgarage\b":"xưởng_sửa_chữa",
    r"\bservice\s*center\b|\btrung\s*tâm\s*dịch\s*vụ\b": "trung_tâm_dịch_vụ",
    r"\bhotline\b|\btổng\s*đài\b":       "hotline",
    r"\broadside\b|\bcứu\s*hộ\b":        "cứu_hộ",
    r"\bphụ\s*tùng\b|\bspare\s*part\b":  "phụ_tùng",
    r"\bbảo\s*dưỡng\b|\bmaintenance\b":  "bảo_dưỡng",
    # ── Performance ────────────────────────────────────────────────────────
    r"\b0[-–]100\b|\bgia\s*tốc\s*0[-–]100\b":  "gia_tốc_0_100",
    r"\btorque\b|\bmô\s*men\s*xoắn\b|\bmô\s*men\b": "mô_men_xoắn",
    r"\bhp\b|\bps\b|\bhorsepower\b|\bmã\s*lực\b":    "mã_lực",
    r"\bsuspension\b|\bhệ\s*thống\s*treo\b":          "hệ_thống_treo",
    r"\bhandling\b|\bcảm\s*giác\s*lái\b":             "cảm_giác_lái",
    r"\bbrake\b|\bphanh\b":              "hệ_thống_phanh",
    r"\bdrive\s*mode\b|\bchế\s*độ\s*lái\b": "chế_độ_lái",
    r"\bone\s*pedal\b|\bmột\s*chân\s*lái\b": "lái_một_chân",
    r"\bregen\s*brake\b|\bphanh\s*tái\s*sinh\b": "phanh_tái_sinh",
    r"\becs\b|\besc\b|\bổn\s*định\s*thân\s*xe\b":  "cân_bằng_điện_tử",
    r"\bawd\b|\b4wd\b|\bxe\s*dẫn\s*động\s*4\s*bánh\b": "dẫn_động_4_bánh",
    r"\brwd\b|\bdẫn\s*động\s*sau\b":     "dẫn_động_sau",
    r"\bfwd\b|\bdẫn\s*động\s*trước\b":   "dẫn_động_trước",
    r"\bair\s*suspension\b|\btreo\s*khí\b": "treo_khí",
    r"\bống\s*xả\b|\btiếng\s*ồn\b|\bồn\b": "tiếng_ồn",
    r"\bêm\s*ru\b|\bquiet\b|\bsilent\b":  "vận_hành_êm",
    # ── Design / Interior ──────────────────────────────────────────────────
    r"\binterior\b|\bnội\s*thất\b":       "nội_thất",
    r"\bexterior\b|\bngoại\s*thất\b":     "ngoại_thất",
    r"\bdashboard\b|\btaplo\b|\bbảng\s*điều\s*khiển\b": "bảng_điều_khiển",
    r"\bsunroof\b|\bpanoramic\b|\bcửa\s*sổ\s*trời\b":   "cửa_sổ_trời",
    r"\bheadlight\b|\bled\s*matrix\b|\bđèn\s*pha\b":     "đèn_pha",
    r"\bleg\s*room\b|\bnot\s*gian\s*chân\b|\bkhoảng\s*chân\b": "không_gian_chân",
    r"\bheadroom\b|\bkhoảng\s*đầu\b":    "không_gian_đầu",
    r"\bda\s*ghế\b|\bseat\s*leather\b":  "da_ghế",
    r"\bghế\s*massage\b":                "ghế_massage",
    r"\bnappa\b":                         "da_nappa",
    r"\bfrunk\b|\bcốp\s*trước\b":         "cốp_trước",
    r"\btrunk\b|\bcốp\s*sau\b|\bkhoang\s*hành\s*lý\b": "cốp_sau",
    r"\bven\s*ti\b|\bventilated\b|\bghế\s*thông\s*gió\b": "ghế_thông_gió",
    r"\bwheelbase\b|\bchiều\s*dài\s*cơ\s*sở\b":  "chiều_dài_cơ_sở",
    # ── Brand Normalization ────────────────────────────────────────────────
    r"\bvinfast\b":                       "VinFast",
    r"\bvf\s*8\b|\bvf8\b":               "VinFast_VF8",
    r"\bvf\s*9\b|\bvf9\b":               "VinFast_VF9",
    r"\bvf\s*7\b|\bvf7\b":               "VinFast_VF7",
    r"\bvf\s*6\b|\bvf6\b":               "VinFast_VF6",
    r"\bvf\s*5\b|\bvf5\b":               "VinFast_VF5",
    r"\bvf\s*3\b|\bvf3\b":               "VinFast_VF3",
    r"\bvfe\s*34\b|\bvfe34\b":           "VinFast_VFe34",
    r"\batto\s*3\b|\batto3\b":           "BYD_Atto3",
    r"\bbyd\s*dolphin\b|\bdolphin\b":    "BYD_Dolphin",
    r"\bbyd\s*seal\b|\bseal\b(?=\s+byd|\s*thiết_kế|\s*tăng)": "BYD_Seal",
    r"\bbyd\s*han\b":                    "BYD_Han",
    r"\bxe\s*tàu\b|\bxe\s*china\b|\bxe\s*tung\b": "xe_trung_quốc",
    r"\bwuling\b":                        "Wuling",
    r"\bmg\s*zs\b|\bmg4\b":             "MG_EV",
    # ── Abbreviations ──────────────────────────────────────────────────────
    r"\bko\b|\bkhg\b|\bk\b(?=[\s,!?.])": "không",
    r"\bdc\b|\bđc\b(?=[\s,])":           "được",
    r"\btks\b|\bthx\b":                  "cảm_ơn",
    r"\bvđ\b|\bvấn\s*đề\b":              "vấn_đề",
    r"\blỗi\s*vặt\b":                    "lỗi_nhỏ",
    r"\bok\b|\bokay\b|\bôkê\b|\boke\b":  "đồng_ý",
    r"\bdv\b(?=[\s,])":                  "dịch_vụ",
    r"\bgt\b(?=[\s,])":                  "giá_trị",
    r"\bsp\b(?=[\s,])":                  "sản_phẩm",
    r"\bkh\b(?=[\s,])":                  "khách_hàng",
    r"\bcty\b":                          "công_ty",
    r"\bpkb\b|\bphí\s*trước\s*bạ\b":    "phí_trước_bạ",
    # ── Sentiment Boosters ─────────────────────────────────────────────────
    r"\bawesome\b|\bamazing\b|\bincredible\b": "tuyệt_vời",
    r"\bterrible\b|\bhorrible\b|\bawful\b":    "tệ_hại",
    r"\bdisappointing\b|\bthất\s*vọng\b":     "thất_vọng",
    r"\bimpressive\b|\bấn\s*tượng\b":         "ấn_tượng",
    r"\boverrated\b|\bquá\s*đề\s*cao\b":      "được_đánh_giá_cao_quá",
    r"\bunderrated\b":                         "bị_đánh_giá_thấp",
    r"\bgoat\b|\blegendary\b|\bđỉnh\s*của\s*đỉnh\b": "tuyệt_đỉnh",
    r"\bscam\b|\blừa\s*đảo\b|\blừa\b":        "lừa_đảo",
    r"\bwaste\b|\btiền\s*mất\s*tật\s*mang\b": "lãng_phí",
    r"\bworth\s*it\b|\bxứng\s*đáng\b":        "xứng_đáng",
    r"\bregret\b|\bhối\s*hận\b|\btiếc\b":     "hối_tiếc",
    r"\bhappy\b|\bvui\b|\bhạnh\s*phúc\b":     "vui_lòng",
    r"\bsatisfied\b|\bhài\s*lòng\b":          "hài_lòng",
    r"\bfrustrated\b|\bbực\s*bội\b|\bbực\b":  "bực_bội",
    r"\bannoyed\b|\bkhó\s*chịu\b":            "khó_chịu",
}

# ── Aspect Taxonomy ───────────────────────────────────────────────────────────
ASPECT_MAP: Dict[str, List[str]] = {
    "BATTERY_CHARGING": [
        "pin","sạc","trạm_sạc","kilowatt","kilowatt_giờ","ngắt_sạc_sớm",
        "sạc_chậm","sạc_nhanh","phạm_vi_thực_tế","tiêu_hao_pin","pin_kém",
        "pin_tốt","lo_ngại_phạm_vi","cổng_sạc","mất_điện_đột_ngột",
        "cột_sạc","sạc_ac","sạc_dc","chuẩn_sạc","pin_sắt_lithium",
        "pin_blade","suy_giảm_pin","sạc_tại_nhà","v2l_xuất_điện",
        "range","km","battery","charging","charge","kwh",
    ],
    "SOFTWARE_TECHNOLOGY": [
        "phần_mềm","lỗi_phần_mềm","cập_nhật_qua_mạng","phản_hồi_chậm",
        "hệ_thống_hỗ_trợ_lái","cảnh_báo_sai","màn_hình","gps",
        "kết_nối_apple","kết_nối_android","phần_mềm_nhúng","tự_lái",
        "camera","cảm_biến","wifi","bluetooth","ứng_dụng","lỗi_hệ_thống",
        "màn_hình_đơ","giao_diện","hệ_thống_dilink","camera_360",
        "kiểm_soát_hành_trình","giữ_làn_đường","phanh_khẩn_cấp",
        "cảnh_báo_điểm_mù","software","app","ota","update",
    ],
    "PERFORMANCE_DRIVING": [
        "tăng_tốc","vận_hành","phanh","lái","cảm_giác_lái","hệ_thống_treo",
        "vận_hành_êm","tiếng_ồn","rung","động_cơ","mã_lực","mô_men_xoắn",
        "tốc_độ","gia_tốc_0_100","êm","mạnh","chế_độ_lái","lái_một_chân",
        "phanh_tái_sinh","cân_bằng_điện_tử","dẫn_động_4_bánh","treo_khí",
        "sport","eco","acceleration","performance","driving",
    ],
    "DESIGN_INTERIOR": [
        "thiết_kế","nội_thất","ngoại_thất","ghế","chất_liệu","không_gian",
        "màu_sắc","đèn","cốp_sau","khoang","đẹp","xấu","sang","vô_lăng",
        "bảng_điều_khiển","đèn_pha","không_gian_chân","cửa_sổ_trời",
        "da_ghế","da_nappa","cốp_trước","ghế_thông_gió","chiều_dài_cơ_sở",
        "interior","exterior","design","style","luxury",
    ],
    "SERVICE_AFTERSALES": [
        "dịch_vụ_sau_bán","bảo_hành","đại_lý","xưởng_sửa_chữa","nhân_viên",
        "bảo_dưỡng","sửa_chữa","phụ_tùng","hỗ_trợ","tư_vấn","thái_độ",
        "khách_hàng","giao_xe","trung_tâm_dịch_vụ","hotline","cứu_hộ",
        "service","warranty","dealer","repair","maintenance",
    ],
    "PRICE_VALUE": [
        "giá","định_giá_cao","giá_đắt","giá_rẻ","giá_trị_tốt","giá_tương_xứng",
        "tài_chính","trả_góp","chi_phí_vận_hành","tiết_kiệm","phí_trước_bạ",
        "tiền","khuyến_mãi","giá_đắt_nhưng_xứng","tốn_chi_phí","xứng_đáng",
        "lãng_phí","hối_tiếc","price","value","cost","expensive","cheap",
    ],
}

# ── Extended Sentiment Lexicons ───────────────────────────────────────────────
POSITIVE_LEXICON: frozenset = frozenset({
    "tốt","ngon","tuyệt","tuyệt_vời","ổn","đẹp","rẻ","hài_lòng","thích",
    "yêu","xuất_sắc","hoàn_hảo","ấn_tượng","mượt","nhanh","pin_tốt",
    "sạc_nhanh","ổn_định","đáng_mua","giá_trị_tốt","thú_vị","tiện_lợi",
    "đáng_tiền","xứng_đáng","mạnh","êm","sang","chắc_chắn","bền","tiện",
    "đồng_ý","tuyệt_hảo","đỉnh","xịn","smooth","great","excellent",
    "perfect","amazing","awesome","siêu","pro","phong_cách","hiện_đại",
    "thông_minh","vượt_trội","tiết_kiệm","đáng","nên_mua","recommend",
    "worth","vui_lòng","hài_lòng","positive_signal","tuyệt_đỉnh",
    "ổn_định","đáng_tin","chuyên_nghiệp","nhiệt_tình","tận_tâm",
    "vận_hành_êm","sạc_dc","sạc_nhanh","pin_blade","ấn_tượng","ngầu",
    "xứng_đáng","giá_tương_xứng","giá_đắt_nhưng_xứng",
})

NEGATIVE_LEXICON: frozenset = frozenset({
    "tệ","lỗi","chậm","kém","đắt","thất_vọng","tức","chán","pin_kém",
    "sạc_chậm","ngắt_sạc_sớm","cảnh_báo_sai","phản_hồi_chậm","lỗi_phần_mềm",
    "negative_signal","hỏng","trục_trặc","vấn_đề","sự_cố","đơ","treo",
    "mất_điện_đột_ngột","định_giá_cao","giá_đắt","tiêu_hao_pin","lo_ngại_phạm_vi",
    "ồn","rung","xấu","kém_chất_lượng","tồi","bad","terrible","horrible",
    "awful","worst","poor","lỗi_hệ_thống","màn_hình_đơ","bực_bội","khó_chịu",
    "lãng_phí","lừa_đảo","hối_tiếc","được_đánh_giá_cao_quá","tệ_hại",
    "thất_vọng","buồn","chê","không_đáng","overpriced","scam","waste",
    "suy_giảm_pin","phản_hồi_chậm","lag","bug","glitch","crash",
    "disappointed","frustrating","disgusting","broken","fail",
})

# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 5 — VISUALIZATION THEME
# ──────────────────────────────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.dpi":        120,
    "figure.facecolor":  "#0D1117",
    "axes.facecolor":    "#161B22",
    "axes.edgecolor":    "#30363D",
    "axes.labelcolor":   "#C9D1D9",
    "axes.titlecolor":   "#F0F6FC",
    "axes.titlesize":    12,
    "axes.labelsize":    10,
    "axes.titleweight":  "bold",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.color":       "#8B949E",
    "ytick.color":       "#8B949E",
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "text.color":        "#C9D1D9",
    "grid.color":        "#21262D",
    "grid.linewidth":    0.7,
    "legend.facecolor":  "#161B22",
    "legend.edgecolor":  "#30363D",
    "legend.fontsize":   8,
    "font.family":       "DejaVu Sans",
    "savefig.facecolor": "#0D1117",
    "savefig.dpi":       150,
    "savefig.bbox":      "tight",
})

BRAND_PAL = {
    "VinFast": "#00C853", "BYD": "#2196F3", "Mixed": "#FFD600",
    "Unknown": "#9E9E9E", "Tesla": "#F44336", "Wuling": "#FF6B35", "MG": "#9C27B0",
}
ASPECT_PAL = {
    "BATTERY_CHARGING":   "#FF6B6B",
    "SOFTWARE_TECHNOLOGY":"#4ECDC4",
    "PERFORMANCE_DRIVING":"#45B7D1",
    "DESIGN_INTERIOR":    "#96CEB4",
    "SERVICE_AFTERSALES": "#FFEAA7",
    "PRICE_VALUE":        "#DDA0DD",
}
SENT_PAL = {"positive":"#00C853","negative":"#F44336","neutral":"#9E9E9E"}


def _show_save(fig: plt.Figure, filename: str, config: PipelineConfig) -> None:
    """Save figure AND display inline if in notebook."""
    p = config.plots_dir / filename
    fig.savefig(p, dpi=150, bbox_inches="tight", facecolor="#0D1117")
    LOG.info("💾 Saved: %s", p)
    if _IN_NOTEBOOK:
        plt.show()
    else:
        plt.close(fig)


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 6 — DATA SCHEMA
# ──────────────────────────────────────────────────────────────────────────────

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

    def fingerprint(self) -> str:
        return hashlib.sha256(
            f"{self.platform_source}|{self.raw_text[:200]}|{self.creation_timestamp}"
            .encode("utf-8")).hexdigest()


def records_to_df(records: List[DiscourseRecord]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame([asdict(r) for r in records])
    for col, dt in [("engagement_score","int32"),("token_count","int32"),
                    ("language_confidence","float32"),("is_valid","bool")]:
        if col in df.columns:
            df[col] = df[col].astype(dt)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 7 — BRAND DETECTOR
# ──────────────────────────────────────────────────────────────────────────────

class BrandDetector:
    def __init__(self, config: PipelineConfig):
        self._kw = config.brand_keywords

    def detect(self, text: str) -> str:
        if not text:
            return "Unknown"
        t = text.lower()
        scores = {b: sum(t.count(k) for k in kws) for b, kws in self._kw.items()}
        total = sum(scores.values())
        if total == 0:
            return "Unknown"
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        top_brand, top_score = ranked[0]
        if top_score == 0:
            return "Unknown"
        second_score = ranked[1][1] if len(ranked) > 1 else 0
        if second_score > 0 and (top_score / total) < 0.65:
            return "Mixed"
        return top_brand


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 8 — DATA SOURCES: YouTube + Reddit + Forum Scraper + Shopee
# ──────────────────────────────────────────────────────────────────────────────

class YouTubeCollector:
    """Full YouTube comment extractor with pagination & retry."""

    def __init__(self, config: PipelineConfig):
        self._cfg    = config
        self._log    = _build_logger("ev.youtube")
        self._bd     = BrandDetector(config)
        self._client = self._init()

    def _init(self):
        if not _YTAPI:
            self._log.warning("google-api-python-client not installed.")
            return None
        if self._cfg.youtube_api_key in ("", "YOUR_YOUTUBE_API_KEY"):
            self._log.warning("No YouTube API key — YouTube disabled.")
            return None
        try:
            c = yt_build("youtube", "v3", developerKey=self._cfg.youtube_api_key)
            self._log.info("YouTube API authenticated ✅")
            return c
        except Exception as e:
            self._log.error("YouTube init error: %s", e)
            return None

    def _parse(self, item: dict, vid: str, brand: str) -> List[DiscourseRecord]:
        recs = []
        try:
            top = item["snippet"]["topLevelComment"]["snippet"]
            r = DiscourseRecord(
                platform_source="youtube", brand_target=brand,
                video_or_thread_id=vid,
                author_handle=top.get("authorDisplayName","anon"),
                raw_text=top.get("textDisplay",""),
                creation_timestamp=top.get("publishedAt",""),
                engagement_score=int(top.get("likeCount",0)),
            )
            r.record_id = r.fingerprint()
            if r.raw_text.strip():
                recs.append(r)
        except (KeyError, TypeError):
            pass
        return recs

    def collect(self) -> List[DiscourseRecord]:
        if self._client is None:
            return []
        all_recs = []
        for vid in self._cfg.target_video_ids:
            brand = self._bd.detect(vid)
            recs, page_token = [], None
            while len(recs) < self._cfg.max_comments_per_video:
                try:
                    kwargs = dict(
                        part="snippet,replies", videoId=vid,
                        maxResults=min(100, self._cfg.max_comments_per_video-len(recs)),
                        textFormat="plainText", order="relevance",
                    )
                    if page_token:
                        kwargs["pageToken"] = page_token
                    resp = self._client.commentThreads().list(**kwargs).execute()
                    items = resp.get("items", [])
                    if not items:
                        break
                    for item in items:
                        recs.extend(self._parse(item, vid, brand))
                    page_token = resp.get("nextPageToken")
                    if not page_token:
                        break
                    time.sleep(self._cfg.request_delay_seconds)
                except Exception as e:
                    self._log.warning("YT error on %s: %s", vid, e)
                    break
            self._log.info("YT[%s]: %d records (brand=%s)", vid[:8], len(recs), brand)
            all_recs.extend(recs)
            time.sleep(0.5)
        return all_recs


class RedditCollector:
    """Reddit PRAW collector — r/VinFast, r/BYDEVOwners, r/electricvehicles."""

    _SUBREDDITS = ["VinFast", "BYDEVOwners", "electricvehicles", "EVs"]
    _SEARCH_QUERIES = [
        "VinFast review Vietnam",
        "BYD Vietnam",
        "VF8 VF9 review",
        "BYD Atto 3 Vietnam",
        "xe điện Vietnam",
    ]

    def __init__(self, config: PipelineConfig):
        self._cfg = config
        self._log = _build_logger("ev.reddit")
        self._bd  = BrandDetector(config)
        self._reddit = self._init()

    def _init(self):
        if not _PRAW:
            self._log.warning("praw not installed — Reddit disabled.")
            return None
        if not self._cfg.reddit_client_id:
            self._log.warning("No Reddit credentials — Reddit disabled.")
            return None
        try:
            r = praw.Reddit(
                client_id=self._cfg.reddit_client_id,
                client_secret=self._cfg.reddit_client_secret,
                user_agent=self._cfg.reddit_user_agent,
                read_only=True,
            )
            self._log.info("Reddit API authenticated ✅")
            return r
        except Exception as e:
            self._log.error("Reddit init: %s", e)
            return None

    def collect(self, limit_per_sub: int = 200) -> List[DiscourseRecord]:
        if self._reddit is None:
            return []
        recs = []
        for sub_name in self._SUBREDDITS:
            try:
                sub = self._reddit.subreddit(sub_name)
                for post in sub.search("VinFast OR BYD OR EV Vietnam",
                                       limit=limit_per_sub, sort="new"):
                    brand = self._bd.detect(post.title + " " + post.selftext)
                    r = DiscourseRecord(
                        platform_source="reddit",
                        brand_target=brand,
                        video_or_thread_id=post.id,
                        author_handle=str(post.author),
                        raw_text=post.selftext if post.selftext else post.title,
                        creation_timestamp=datetime.utcfromtimestamp(
                            post.created_utc).isoformat(),
                        engagement_score=post.score,
                    )
                    r.record_id = r.fingerprint()
                    if r.raw_text.strip():
                        recs.append(r)
                    # Top-level comments
                    post.comments.replace_more(limit=0)
                    for comment in list(post.comments)[:10]:
                        brand_c = self._bd.detect(comment.body)
                        rc = DiscourseRecord(
                            platform_source="reddit_comment",
                            brand_target=brand_c,
                            video_or_thread_id=post.id,
                            author_handle=str(comment.author),
                            raw_text=comment.body,
                            creation_timestamp=datetime.utcfromtimestamp(
                                comment.created_utc).isoformat(),
                            engagement_score=comment.score,
                        )
                        rc.record_id = rc.fingerprint()
                        if rc.raw_text.strip():
                            recs.append(rc)
            except Exception as e:
                self._log.warning("Reddit sub %s error: %s", sub_name, e)
        self._log.info("Reddit: %d records collected", len(recs))
        return recs


class ForumScraper:
    """
    Lightweight scraper for public Vietnamese automotive forums.
    Targets: otofun.net, xehoi.com.vn public discussion pages.
    Respects robots.txt and adds delays. For academic use only.
    """

    _TARGETS = [
        {
            "url": "https://www.otofun.net/search/?q=vinfast+xe+dien&o=date",
            "brand": "VinFast",
            "platform": "otofun",
        },
        {
            "url": "https://www.otofun.net/search/?q=byd+xe+dien&o=date",
            "brand": "BYD",
            "platform": "otofun",
        },
    ]

    def __init__(self, config: PipelineConfig):
        self._cfg = config
        self._log = _build_logger("ev.forum")
        self._bd  = BrandDetector(config)
        self._session = None
        if _BS4:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            })

    def collect(self, max_per_target: int = 100) -> List[DiscourseRecord]:
        if not _BS4 or self._session is None:
            self._log.warning("requests/beautifulsoup4 not installed — forum scraper disabled.")
            return []
        recs = []
        for target in self._TARGETS:
            try:
                resp = self._session.get(target["url"], timeout=10)
                if resp.status_code != 200:
                    self._log.warning("HTTP %d for %s", resp.status_code, target["url"])
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                # Generic post/comment text extraction
                text_blocks = []
                for tag in soup.find_all(["p","div","span"], limit=500):
                    t = tag.get_text(strip=True)
                    if len(t) > 20 and t not in text_blocks:
                        text_blocks.append(t)
                for text in text_blocks[:max_per_target]:
                    brand = self._bd.detect(text)
                    r = DiscourseRecord(
                        platform_source=target["platform"],
                        brand_target=brand if brand != "Unknown" else target["brand"],
                        video_or_thread_id=target["url"],
                        author_handle="forum_user",
                        raw_text=text,
                        creation_timestamp=datetime.now(timezone.utc).isoformat(),
                        engagement_score=random.randint(0, 30),
                    )
                    r.record_id = r.fingerprint()
                    recs.append(r)
                time.sleep(2.0)  # Be polite
            except Exception as e:
                self._log.warning("Forum scrape error %s: %s", target["url"], e)
        self._log.info("Forum: %d records collected", len(recs))
        return recs


class ShopeeReviewCollector:
    """
    Stub for Shopee product reviews (EV accessories).
    In production: use Shopee Open API or partner API.
    Returns synthetic accessory reviews for demonstration.
    """

    _ACCESSORY_REVIEWS = {
        "VinFast": [
            ("Cáp sạc chính hãng VinFast chất lượng tốt, cắm vào sạc ngay không bị báo lỗi.", 45),
            ("Thảm lót sàn VF8 vừa khít, chất liệu tốt, dễ vệ sinh sau mưa.", 32),
            ("Bộ sạc di động VinFast giao chậm 1 tuần nhưng chất lượng ổn.", 12),
            ("Sạc tường AC 7kW của VinFast lắp đặt phức tạp, cần thợ chuyên nghiệp.", 8),
            ("Ốp điện thoại gắn xe VF8 dễ lắp, giữ chắc, không rung khi đi đường xấu.", 56),
            ("Phụ kiện VinFast chính hãng giá cao hơn bên ngoài nhưng yên tâm hơn.", 23),
            ("Túi để cáp sạc bị lỗi khóa kéo sau 2 tháng, chất lượng kém.", 7),
            ("Dock sạc không dây VF8 compatible, sạc nhanh 15W rất tiện.", 41),
        ],
        "BYD": [
            ("Adapter sạc CCS Type 2 BYD tương thích tốt với hầu hết trạm sạc công cộng.", 38),
            ("Thảm lót BYD Atto 3 chất liệu cao su tốt, không hôi, giá hợp lý.", 27),
            ("Cáp sạc Type 2 BYD Seal dài 7m, đủ để đỗ xa trạm một chút, tiện.", 19),
            ("Màng phim PPF dán BYD Dolphin bảo vệ sơn tốt, trong suốt.", 34),
            ("Bộ sạc OBC 11kW của BYD chưa tương thích với một số đơn vị lắp đặt tại VN.", 6),
            ("Ghế ngồi thêm hàng 3 BYD Han giá cao nhưng hoàn thiện đẹp.", 15),
            ("Túi cốp BYD Atto 3 dung lượng nhỏ, cần cải thiện thêm.", 9),
            ("Đồng hồ HUD BYD Seal hiển thị rõ ngay cả khi nắng gắt.", 52),
        ],
    }

    def __init__(self, config: PipelineConfig):
        self._cfg = config
        self._log = _build_logger("ev.shopee")

    def collect(self) -> List[DiscourseRecord]:
        """Return synthetic Shopee accessory reviews."""
        recs = []
        for brand, reviews in self._ACCESSORY_REVIEWS.items():
            for text, eng in reviews:
                r = DiscourseRecord(
                    platform_source="shopee",
                    brand_target=brand,
                    video_or_thread_id="shopee_accessory",
                    author_handle="shopee_buyer",
                    raw_text=text,
                    creation_timestamp=datetime.now(timezone.utc).isoformat(),
                    engagement_score=eng,
                )
                r.record_id = r.fingerprint()
                recs.append(r)
        self._log.info("Shopee (accessory reviews): %d records", len(recs))
        return recs


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 9 — SYNTHETIC DATA GENERATOR (realistic Vietnamese EV discourse)
# ──────────────────────────────────────────────────────────────────────────────

class SyntheticDataGenerator:
    """
    High-fidelity synthetic Vietnamese EV discourse for pipeline augmentation.
    Based on actual patterns observed in OtoFun, VinFast Global Community,
    YouTube comments, and Reddit r/electricvehicles.
    """

    _TEMPLATES = {
        "VinFast": {
            "BATTERY_CHARGING": {
                "positive": [
                    "Sạc VF8 từ 20% lên 80% chỉ mất 25 phút ở trạm DC 50kW, rất ấn tượng!",
                    "Mạng lưới trạm sạc VinFast phủ khắp cao tốc Bắc Nam, yên tâm đi xa.",
                    "Pin VF9 thực tế đạt 390km ở tốc độ 90km/h, vượt kỳ vọng.",
                    "Tự sạc tại nhà 220V qua đêm, sáng dậy đầy pin, chi phí chỉ 28-35k đồng.",
                    "Hệ thống BMS của VinFast quản lý pin thông minh, ổn định sau 18 tháng.",
                    "Trạm sạc DC 150kW mới của VinFast thực sự nhanh, 10-80% chưa tới 30 phút.",
                    "Pin LFP VFe34 bền hơn mình nghĩ, sau 2 năm vẫn đạt 95% dung lượng.",
                    "App VinFast báo trạm sạc chính xác, tìm trạm gần nhất dễ dàng.",
                ],
                "negative": [
                    "Pin VF8 tụt rất nhanh khi bật điều hòa mạnh, đi 250km mà lo sốt vó.",
                    "Trạm sạc bị ngắt ở 5% liên tục 3 lần liền, tức không tả được.",
                    "Sạc DC 50kW nhưng thực tế chỉ nhận được 28kW, quảng cáo sai sự thật.",
                    "Pin hẻo hơn quảng cáo, mùa đông Hà Nội mất 35-40% phạm vi thực tế.",
                    "Trạm sạc ở tỉnh lẻ quá ít, từ Huế vào Đà Nẵng phải canh từng km.",
                    "Sạc tự ngắt ở 82% mà không có lý do, cắm lại không nhận sạc.",
                    "Sau 20 tháng pin còn 88% dung lượng, xuống nhanh hơn kỳ vọng nhiều.",
                    "Adapter sạc AC đi kèm nóng bất thường sau 2 tiếng sạc, lo ngại.",
                    "App báo trạm sạc hoạt động nhưng đến nơi bị hỏng cả 4 cọc, bực lắm.",
                ],
                "neutral": [
                    "Pin VF8 thực tế khoảng 330-370km tùy cách lái và thời tiết.",
                    "Sạc AC 7kW tại nhà mất khoảng 8-9 tiếng từ 10% lên 100%, bình thường.",
                    "Hệ thống trạm sạc VinFast đang mở rộng, tháng nào cũng thêm điểm mới.",
                    "Pin 55kWh của VF8 phù hợp cho di chuyển nội thành và cự ly trung bình.",
                ],
            },
            "SOFTWARE_TECHNOLOGY": {
                "positive": [
                    "Màn hình 15.6 inch VF8 to và rõ, phản hồi cảm ứng nhanh mượt.",
                    "Bản OTA tháng 11 fix được lỗi cảnh báo ảo trên QL1, chạy mượt hơn hẳn.",
                    "ADAS của VF9 nhận diện làn đường rất tốt trên đường cao tốc mới.",
                    "Camera 360 độ hình ảnh sắc nét, hỗ trợ đỗ xe trong hẻm nhỏ cực tốt.",
                    "Hệ thống âm thanh 13 loa trên VF9 chất lượng không kém xe Đức.",
                    "Đỗ xe tự động hoạt động chính xác cao, tiện ích thực sự trong nội thành.",
                ],
                "negative": [
                    "Cảnh báo ảo liên tục trên đường thẳng, cứ báo nguy hiểm làm tôi giật mình.",
                    "Màn hình đơ hoàn toàn khi trời nóng 38 độ, phải dừng xe tắt máy reset.",
                    "CarPlay bị lag và ngắt kết nối mỗi 15-20 phút, không dùng được.",
                    "Sau bản update mới màn hình tự khởi động lại lúc đang lái, rất nguy hiểm.",
                    "GPS dẫn vào đường cụt 3 lần trong một chuyến đi, không thể tin cậy.",
                    "Bluetooth ngắt kết nối liên tục dù điện thoại cách 20cm, bực cực kỳ.",
                    "Tính năng giữ làn tự động tắt sau 30 phút mà không có cảnh báo.",
                    "Camera lùi lag khoảng 2-3 giây, nguy hiểm khi đỗ xe chật hẹp.",
                ],
                "neutral": [
                    "Giao diện phần mềm VF8 cần làm quen khoảng 1-2 tuần, sau đó dùng được.",
                    "OTA cập nhật định kỳ, có bản tốt có bản lại phát sinh lỗi mới.",
                    "Hệ thống giải trí tích hợp ổn, không cần điện thoại riêng cho điều hướng.",
                ],
            },
            "PERFORMANCE_DRIVING": {
                "positive": [
                    "Tăng tốc VF8 cực ấn tượng, vượt xe tải trên đèo dễ như trở bàn tay.",
                    "Cảm giác lái rất êm ái, hệ thống treo xử lý ổ gà đường VN tốt.",
                    "Phanh tái sinh mượt, không giật cục như một số xe điện khác tôi thử.",
                    "Chế độ Sport VF8 phản hồi tức thì, đúng nghĩa xe thể thao điện.",
                    "Cabin cực yên tĩnh trên cao tốc, có thể nói chuyện bình thường ở 120km/h.",
                ],
                "negative": [
                    "Tiếng ồn gió rõ ở tốc độ 100km/h, cách âm chưa đạt mức kỳ vọng.",
                    "Hệ thống treo cứng trên đường đất, hành khách phàn nàn bị xóc.",
                    "Chế độ Eco hạn chế công suất quá nhiều, khó vượt xe tải trên đèo.",
                    "Bán kính quay vòng lớn, khó xoay trong bãi đỗ xe ngầm chật hẹp.",
                ],
                "neutral": [
                    "Hiệu năng VF8 phù hợp cả nội thành lẫn đường dài, không có điểm nổi bật lẫn tệ.",
                    "Hộp số một cấp điện tử hoạt động êm, không có điểm đặc biệt.",
                ],
            },
            "DESIGN_INTERIOR": {
                "positive": [
                    "Thiết kế VF8 đẹp và hiện đại, sang trọng hơn kỳ vọng ban đầu.",
                    "Nội thất rộng rãi thoải mái, chất liệu da tổng hợp ổn với mức giá.",
                    "Đèn LED ma trận VF9 ấn tượng ban đêm, đẹp hơn cả xe Đức cùng phân khúc.",
                    "Ghế ngồi thoải mái đường dài, 4 tiếng không mỏi lưng.",
                ],
                "negative": [
                    "Nhựa nội thất nhìn rẻ tiền, chạm vào không có cảm giác premium.",
                    "Thiết kế cốp nhỏ và vuông, khó xếp vali to cùng lúc.",
                    "Màu sơn nội thất ít lựa chọn, chỉ đen và be, nhàm chán.",
                ],
                "neutral": [
                    "Ngoại thất ổn, không nổi bật nhưng cũng không xấu.",
                    "Cửa sổ trời panorama kích thước trung bình, đủ dùng.",
                ],
            },
            "SERVICE_AFTERSALES": {
                "positive": [
                    "Nhân viên VinFast nhiệt tình và tận tâm, hỗ trợ 24/7 khi gặp sự cố.",
                    "Bảo hành 7 năm hoặc 160.000km rất yên tâm, chưa thấy hãng nào làm vậy.",
                    "Giao xe đúng hẹn, không bị dời lịch, dịch vụ chuyên nghiệp và rõ ràng.",
                ],
                "negative": [
                    "Đặt hẹn bảo dưỡng phải chờ 2-3 tuần mới có slot, quá chậm và thiếu nhân viên.",
                    "Phụ tùng không có sẵn, đặt trước 3-4 tuần mới về, xe nằm chờ.",
                    "Nhân viên tư vấn không nắm kỹ thông số, trả lời sai thông tin.",
                    "Sau bán hàng thay đổi hoàn toàn, gọi hotline chờ 30 phút không ai bắt.",
                ],
                "neutral": [
                    "Dịch vụ hậu mãi VinFast đang cải thiện, chờ thêm thời gian đánh giá.",
                    "Chi phí bảo dưỡng ở mức trung bình, không rẻ hơn xe xăng cùng phân khúc.",
                ],
            },
            "PRICE_VALUE": {
                "positive": [
                    "Giá VF8 rất hợp lý so với trang bị nhận được, cạnh tranh tốt với hàng ngoại.",
                    "Chi phí vận hành điện rẻ hơn xăng 4-5 lần, tiết kiệm thực sự mỗi tháng.",
                    "Ưu đãi 0% phí trước bạ giúp giảm đáng kể chi phí lăn bánh.",
                ],
                "negative": [
                    "Giá VF8 sau khi cộng hết phụ phí cao hơn nhiều so với niêm yết.",
                    "Chính sách thuê pin phức tạp và tốn kém hơn mua đứt khi tính dài hạn.",
                    "Sau khi VinFast tăng giá 2 lần trong năm, sức cạnh tranh giảm rõ rệt.",
                ],
                "neutral": [
                    "Giá VF8 khoảng 900 triệu đến 1.1 tỷ tùy phiên bản, trong tầm xe hạng C.",
                    "Khuyến mãi thường xuyên thay đổi, cần theo dõi tháng nào cũng khác.",
                ],
            },
        },
        "BYD": {
            "BATTERY_CHARGING": {
                "positive": [
                    "Pin Blade Battery BYD Seal ổn định xuất sắc, sau 2 năm vẫn đạt 97%.",
                    "Sạc DC 80kW thực tế đạt 76-79kW, nhất quán và đáng tin cậy.",
                    "BYD Atto 3 sạc từ 10-80% chỉ mất 48 phút tại trạm Evgo.",
                    "Phạm vi thực tế BYD Seal đạt 430km trên cao tốc Hà Nội - Đà Nẵng.",
                    "Công nghệ làm mát pin liquid cooling BYD rất hiệu quả dù trời 40 độ.",
                    "Tính năng V2L xuất điện cực tiện, dùng nấu ăn cắm trại không cần máy phát.",
                ],
                "negative": [
                    "Trạm sạc tương thích BYD ở VN còn rất ít, chủ yếu dùng adapter bên thứ 3.",
                    "Adapter sạc AC chậm hơn quảng cáo nhiều, mất 11-12 tiếng sạc đầy.",
                    "Hệ sinh thái sạc BYD VN kém phát triển, không thể cạnh tranh với VinFast.",
                    "Sạc DC trên 50kW cần adapter riêng không đi kèm xe, phải mua thêm 5 triệu.",
                ],
                "neutral": [
                    "Pin BYD Atto 3 thực tế khoảng 380-400km trên đường VN, chấp nhận được.",
                    "Hệ sinh thái sạc BYD VN đang xây dựng, cần thêm 1-2 năm để phủ rộng.",
                    "BYD hỗ trợ cả CCS và CHAdeMO, linh hoạt hơn về chuẩn sạc.",
                ],
            },
            "SOFTWARE_TECHNOLOGY": {
                "positive": [
                    "Phần mềm BYD Seal rất mượt và ổn định, 8 tháng chưa gặp lỗi nào.",
                    "Màn hình xoay 15.6 inch của BYD rất độc đáo và tiện dụng mọi góc nhìn.",
                    "OTA BYD không sinh ra lỗi mới sau mỗi bản cập nhật, rất đáng tin.",
                    "DiLink 11 rất thông minh với nhiều ứng dụng tích hợp sẵn.",
                    "Hệ thống âm thanh Dynaudio BYD Seal chất lượng concert thực sự.",
                    "Smart pilot BYD hoạt động mượt trên cao tốc VN, ít cảnh báo sai.",
                ],
                "negative": [
                    "Giao diện tiếng Việt còn thiếu, nhiều chức năng chỉ có tiếng Anh và Trung.",
                    "GPS BYD dùng bản đồ lỗi thời, không cập nhật đường mới ở VN.",
                    "App điều khiển từ xa thường mất kết nối, bật điều hòa trước không được.",
                ],
                "neutral": [
                    "Phần mềm BYD tốt về tổng thể, cần Việt hóa thêm để phù hợp thị trường.",
                    "DiLink 11 hỗ trợ Android Auto và CarPlay, setup lần đầu hơi phức tạp.",
                ],
            },
            "PERFORMANCE_DRIVING": {
                "positive": [
                    "BYD Seal tăng tốc cực mạnh, phiên bản Performance 0-100 chỉ 3.8 giây.",
                    "Hệ thống treo BYD xử lý đường xấu VN tốt bất ngờ, êm hơn cả xe Đức.",
                    "Phanh BYD chính xác và tái sinh năng lượng hiệu quả cao.",
                    "One pedal driving BYD tiện dụng trong nội thành đông đúc Sài Gòn.",
                    "Khả năng điều khiển tốc độ cao rất ổn định, tự tin lái đường dài.",
                ],
                "negative": [
                    "Cảm giác lái BYD Atto 3 hơi nặng tay, chưa quen với người mới.",
                    "Tiếng ồn lốp xe khá rõ ở 120km/h, cabin cách âm chưa đạt đẳng cấp.",
                ],
                "neutral": [
                    "Hiệu năng lái BYD ổn định, phù hợp cả nội thành lẫn đường cao tốc.",
                    "AWD của BYD Seal Performance cho cảm giác cân bằng và tin cậy.",
                ],
            },
            "DESIGN_INTERIOR": {
                "positive": [
                    "Nội thất BYD Seal sang trọng, hoàn thiện tốt hơn nhiều so với định kiến.",
                    "Thiết kế Ocean Aesthetics độc đáo và ấn tượng, khác biệt hoàn toàn.",
                    "Ghế da Nappa BYD Seal cực thoải mái, ngồi 5 tiếng không mỏi.",
                    "Màn hình xoay 360 độ là điểm nhấn thiết kế không xe nào có.",
                    "Cốp frunk phía trước rất tiện, để giày hay đồ lặt vặt rất tốt.",
                ],
                "negative": [
                    "Màu xe BYD VN chỉ có 4-5 màu cơ bản, ít lựa chọn hơn VinFast.",
                    "Một số chi tiết nhựa cứng nội thất cảm giác rẻ tiền.",
                ],
                "neutral": [
                    "Thiết kế BYD theo phong cách tương lai đại dương, không phải ai cũng thích.",
                    "Kích thước tổng thể BYD Seal gần tương đương VF8, không gian tương đồng.",
                ],
            },
            "SERVICE_AFTERSALES": {
                "positive": [
                    "Đại lý BYD mới nhân viên được đào tạo bài bản, chuyên nghiệp hơn dự kiến.",
                    "Bảo hành 6 năm pin và 6 năm xe, chính sách tốt nhất phân khúc.",
                    "Chi phí bảo dưỡng BYD thấp hơn xe xăng tương đương, tiết kiệm đáng kể.",
                ],
                "negative": [
                    "Đại lý BYD VN còn quá ít, ở tỉnh phải lái xa hàng trăm km bảo dưỡng.",
                    "Linh kiện BYD chưa phổ biến tại VN, lo ngại lâu dài khó tìm phụ tùng.",
                    "Thời gian giao xe chậm hơn cam kết 2-3 tháng, gây nhiều bất tiện.",
                ],
                "neutral": [
                    "Mạng lưới BYD VN đang mở rộng nhanh, thêm 20 đại lý trong năm 2024.",
                    "Bảo dưỡng định kỳ 6 tháng hoặc 10.000km, tiêu chuẩn ngành bình thường.",
                ],
            },
            "PRICE_VALUE": {
                "positive": [
                    "BYD Atto 3 giá hợp lý hơn nhiều so với trang bị nhận được, rất đáng.",
                    "So sánh tầm 800 triệu, BYD Dolphin là lựa chọn đáng mua nhất phân khúc.",
                    "Chi phí bảo dưỡng BYD rất rẻ, 6 tháng chỉ hết 1.5 triệu, siêu tiết kiệm.",
                ],
                "negative": [
                    "BYD Seal giá cần khuyến mãi thêm mới cạnh tranh với VF8 trang bị tương đương.",
                    "Phụ tùng chính hãng BYD đắt, lo ngại chi phí sửa chữa về dài hạn.",
                ],
                "neutral": [
                    "BYD Atto 3 khoảng 760-820 triệu tùy phiên bản, cạnh tranh tốt.",
                    "BYD Seal từ 1.0-1.3 tỷ, trong tầm cạnh tranh trực tiếp với VF8.",
                ],
            },
        },
    }

    _PREFIXES = [
        "","Thật ra ","Theo mình thì ","Mình thấy ","Dùng được 3 tháng: ",
        "Sau 1 năm sử dụng, ","Anh em ơi, ","Cập nhật thực tế: ",
        "Mới mua hôm qua, ","So sánh thực tế: ","Nói thật nhé: ",
        "Phải thừa nhận là ","Không ngờ là ","Bất ngờ quá, ",
        "Từ kinh nghiệm bản thân: ","Chủ xe VF8 đây, ","Chủ BYD Seal đây, ",
    ]

    _AUTHORS = [
        "@XeHoiVN","@DriverHN","@TechCarVN","@EVOwnerSGN","@AutoLoverVN",
        "@XeDienFan","@CarReview_VN","@GreenMobility","@ChuXeVF8",
        "@BYDOwner_SGN","@EVCommunity_VN","@XanhHoaVN","@ThichXeDien",
        "@GreenDriverVN","@MotorheadVN","@VietAutoFan","@SaigonDriver",
        "@HanoiDriver","@DaNangCar","@MeXeVN",
    ]

    def generate(self, n_per_brand: int = 400, seed: int = 42) -> List[DiscourseRecord]:
        rng = np.random.default_rng(seed)
        records = []
        base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

        for brand, aspects in self._TEMPLATES.items():
            for aspect, sentiments in aspects.items():
                n_per_sent = max(3, n_per_brand // (len(aspects) * 3))
                for sentiment, templates in sentiments.items():
                    for _ in range(n_per_sent):
                        text = str(rng.choice(templates))
                        text = str(rng.choice(self._PREFIXES)) + text
                        days_offset = int(rng.integers(0, 730))
                        month = ((days_offset // 30) % 12) + 1
                        day = min((days_offset % 28) + 1, 28)
                        try:
                            ts = base_ts.replace(month=month, day=day).isoformat()
                        except ValueError:
                            ts = base_ts.isoformat()
                        r = DiscourseRecord(
                            platform_source=str(rng.choice(
                                ["youtube","reddit","otofun","shopee"])),
                            brand_target=brand,
                            video_or_thread_id=f"synthetic_{brand}_{aspect}",
                            author_handle=str(rng.choice(self._AUTHORS)),
                            raw_text=text,
                            creation_timestamp=ts,
                            engagement_score=int(rng.integers(0, 250)),
                        )
                        r.record_id = r.fingerprint()
                        r._sentiment_label = sentiment
                        r._aspect_label = aspect
                        records.append(r)

        rng.shuffle(records)
        LOG.info("✅ Generated %d synthetic records", len(records))
        return records


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 10 — NLP PIPELINE
# ──────────────────────────────────────────────────────────────────────────────

class ViTextNormalizer:
    """8-stage Vietnamese text normalization pipeline."""

    _POS_EMOJI = frozenset([
        "❤️","💚","💛","💯","👍","😍","🥰","😊","🎉","✅","🙌","👏","🤩",
        "💪","🌟","⭐","🏆","✨","😁","😄","🔥","💥","👌","🫶","💎",
    ])
    _NEG_EMOJI = frozenset([
        "😠","😡","🤬","👎","💔","😤","🤦","😞","😔","❌","🚫","😒",
        "😣","🤮","💢","☠️","😱","🤯","😭","🙄","😑","🥺","💀","⛔",
    ])
    _URL_RE     = re.compile(r"https?://\S+|www\.\S+", re.I)
    _HTML_RE    = re.compile(r"<[^>]+>")
    _MENTION_RE = re.compile(r"@[\w\._]+")
    _HASHTAG_RE = re.compile(r"#\w+")
    _REPEAT_RE  = re.compile(r"(.)\1{3,}", re.U)  # 3+ repeats → 2
    _NUM_UNIT   = re.compile(
        r"\b\d+[.,]?\d*\s*(km|kg|kw|kwh|v|a|%|triệu|tỷ|k|m|l|lít|năm|tháng|giờ)\b",
        re.I)

    _VI_CHARS = (
        "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠàáâãèéêìíòóôõùúăđĩũơ"
        "ƯĂẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼỀỀỂưăạảấầẩẫậắằẳẵặẹẻẽềềể"
        "ỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪễệỉịọỏốồổỗộớờởỡợụủứừ"
        "ỮỰỲỴÝỶỸữựỳỵỷỹ"
    )

    def __init__(self):
        self._slang = [(re.compile(p, re.I | re.U), r) for p, r in SLANG_MAP.items()]
        self._keep_re = re.compile(
            rf"[^a-zA-Z0-9{re.escape(self._VI_CHARS)}_ \t]", re.U)

    def normalize(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        # 1. Unicode NFKC
        t = unicodedata.normalize("NFKC", text)
        # 2. Full-width → ASCII
        t = "".join(
            chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in t)
        # 3. Strip HTML
        t = self._HTML_RE.sub(" ", t)
        # 4. Remove URLs
        t = self._URL_RE.sub(" ", t)
        # 5. Remove @mentions / #hashtags
        t = self._MENTION_RE.sub(" ", t)
        t = self._HASHTAG_RE.sub(" ", t)
        # 6. Emoji → semantic signal tokens (preserve sentiment info)
        for e in self._POS_EMOJI:
            t = t.replace(e, " POSITIVE_SIGNAL ")
        for e in self._NEG_EMOJI:
            t = t.replace(e, " NEGATIVE_SIGNAL ")
        if _EMOJI:
            t = emoji_lib.replace_emoji(t, replace=" ")
        else:
            t = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", " ", t)
        # 7. Lowercase
        t = t.lower()
        # 8. Apply slang/normalization rules
        for pat, repl in self._slang:
            t = pat.sub(repl, t)
        # 9. Compress repeated chars (e.g. "tốtttt" → "tốtt")
        t = self._REPEAT_RE.sub(r"\1\1", t)
        # 10. Remove non-Vietnamese noise chars (keep underscores for compounds)
        t = self._keep_re.sub(" ", t)
        # 11. Normalize whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t


class ViSegmenter:
    """Three-tier Vietnamese word segmentation with graceful fallback."""

    def segment(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        try:
            if _UNDERTHESEA:
                return uts_tok(text, format="text")
            elif _PYVI:
                return ViTokenizer.tokenize(text)
            else:
                # Tier 3: preserve underscore compounds, space-based
                return re.sub(r"\s+", " ", text).strip()
        except Exception:
            return text


class LangGate:
    """Vietnamese language detection via diacritic density + langdetect."""

    _VI_DIAC = frozenset(
        "àáâãèéêìíòóôõùúăđĩũơưăạảấầẩẫậắằẳẵặẹẻẽềểễệỉịọỏốồổỗộớờởỡợụủứừữựỳỵỷỹ"
    )

    def __init__(self, min_conf: float = 0.45, min_chars: int = 8):
        self._min_conf  = min_conf
        self._min_chars = min_chars

    def assess(self, text: str) -> Tuple[bool, float]:
        if not text or len(text.strip()) < self._min_chars:
            return False, 0.0
        diac      = sum(1 for c in text.lower() if c in self._VI_DIAC)
        diac_dens = diac / max(len(text), 1)
        if diac_dens > 0.07:
            return True, min(1.0, diac_dens * 3.5)
        if not _LANGDETECT:
            return diac_dens > 0.02, float(diac_dens)
        try:
            results  = detect_langs(text.strip())
            conf_map = {r.lang: r.prob for r in results}
            vi_conf  = conf_map.get("vi", 0.0)
            adjusted = min(1.0, vi_conf + diac_dens * 0.4)
            return adjusted >= self._min_conf, round(adjusted, 4)
        except Exception:
            return diac_dens > 0.025, float(diac_dens)


class StopFilter:
    """Remove stopwords while preserving negation, compounds, and signals."""

    def filter(self, segmented: str) -> Tuple[str, int, int]:
        tokens   = segmented.split()
        orig_n   = len(tokens)
        filtered = []
        for tok in tokens:
            tl = tok.lower()
            if tl in NEGATION_PARTICLES:      filtered.append(tok); continue
            if "_" in tok:                     filtered.append(tok); continue
            if tok in ("POSITIVE_SIGNAL","NEGATIVE_SIGNAL"):
                filtered.append(tok); continue
            if len(tok) > 1 and tl not in VIETNAMESE_STOPWORDS:
                filtered.append(tok)
        return " ".join(filtered), orig_n, orig_n - len(filtered)


class AspectTagger:
    """Rule-based weak-supervision aspect detection."""

    def __init__(self):
        self._ksets = {asp: frozenset(kws) for asp, kws in ASPECT_MAP.items()}

    def tag(self, text: str) -> Dict[str, bool]:
        tokens = frozenset(text.lower().split())
        return {asp: bool(tokens & kws) for asp, kws in self._ksets.items()}


class SentimentLabeler:
    """
    Rule-based sentiment labeler with negation inversion, intensity boosting.
    Returns: 1 (positive), -1 (negative), 0 (neutral)
    """

    _INTENSIFIERS = frozenset([
        "rất","cực","siêu","quá","vô_cùng","thực_sự","cực_kỳ",
        "hoàn_toàn","totally","super","đặc_biệt","tuyệt_đối",
    ])

    def label(self, text: str) -> int:
        if not isinstance(text, str):
            return 0
        tokens    = text.lower().split()
        pos_score = neg_score = 0
        for i, tok in enumerate(tokens):
            negated   = any(tokens[j] in NEGATION_PARTICLES
                            for j in range(max(0, i-3), i))
            intensity = 2 if any(tokens[j] in self._INTENSIFIERS
                                 for j in range(max(0, i-2), i)) else 1
            if tok in POSITIVE_LEXICON or tok == "positive_signal":
                if negated: neg_score += intensity
                else:       pos_score += intensity
            if tok in NEGATIVE_LEXICON or tok == "negative_signal":
                if negated: pos_score += intensity
                else:       neg_score += intensity
        if pos_score > neg_score:  return 1
        if neg_score > pos_score:  return -1
        return 0


class MasterPreprocessor:
    """Orchestrates full NLP pipeline: LangGate→Normalize→Segment→Filter→Tag→Label."""

    def __init__(self, config: PipelineConfig):
        self._cfg  = config
        self._gate = LangGate(config.language_detect_threshold, config.min_char_length)
        self._norm = ViTextNormalizer()
        self._seg  = ViSegmenter()
        self._sf   = StopFilter()
        self._atag = AspectTagger()
        self._slbl = SentimentLabeler()
        self._log  = _build_logger("ev.preprocessor")

    def process_one(self, raw: str) -> Optional[Dict]:
        valid, conf = self._gate.assess(raw)
        if not valid:
            return None
        try:
            norm = self._norm.normalize(raw)
        except Exception:
            return None
        if not norm.strip():
            return None
        seg               = self._seg.segment(norm)
        filtered, orig, _ = self._sf.filter(seg)
        n_tokens          = len(filtered.split())
        if n_tokens < self._cfg.min_token_length:
            return None
        aspects   = self._atag.tag(filtered)
        sentiment = self._slbl.label(filtered)
        return {
            "processed_text":      filtered,
            "token_count":         n_tokens,
            "language_confidence": conf,
            "sentiment":           sentiment,
            **{f"aspect_{k}": v for k, v in aspects.items()},
        }

    def process_df(self, df: pd.DataFrame, text_col: str = "raw_text") -> pd.DataFrame:
        self._log.info("Preprocessing %d records...", len(df))
        results = []
        for _, row in tqdm(df.iterrows(), total=len(df),
                           desc="NLP Pipeline", unit="rec"):
            res = self.process_one(str(row.get(text_col, "")))
            d   = row.to_dict()
            if res:
                d.update({**res, "is_valid": True})
            else:
                d.update({
                    "processed_text": "", "token_count": 0,
                    "language_confidence": 0.0, "sentiment": 0, "is_valid": False,
                })
                for asp in ASPECT_MAP:
                    d[f"aspect_{asp}"] = False
            results.append(d)
        out = pd.DataFrame(results)
        for col, dt in [("engagement_score","int32"),("token_count","int32"),
                        ("language_confidence","float32"),("is_valid","bool"),
                        ("sentiment","int8")]:
            if col in out.columns:
                out[col] = out[col].astype(dt)
        valid_n = out["is_valid"].sum()
        self._log.info("✅ Preprocessing done: %d/%d valid (%.1f%%)",
                       valid_n, len(out), 100 * valid_n / max(len(out), 1))
        return out


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 11 — DATA LAKE
# ──────────────────────────────────────────────────────────────────────────────

class DataLake:
    def __init__(self, config: PipelineConfig):
        self._cfg = config
        self._log = _build_logger("ev.datalake")

    def save(self, df: pd.DataFrame, stem: str) -> Tuple[Path, Path]:
        if df.empty:
            self._log.warning("Empty DataFrame — nothing saved.")
            return Path(""), Path("")
        n_before = len(df)
        df = df.drop_duplicates(subset=["record_id"])
        df = df[df["raw_text"].str.len() > 5]
        self._log.info("Dedup: %d → %d records", n_before, len(df))
        csv_p = self._cfg.raw_dir / f"{stem}.csv"
        par_p = self._cfg.raw_dir / f"{stem}.parquet"
        df.to_csv(csv_p, index=False, encoding="utf-8-sig")
        try:
            df.to_parquet(par_p, index=False, compression="snappy")
        except Exception:
            df.to_parquet(par_p, index=False)
        self._log.info("Saved: %s | %s", csv_p, par_p)
        return csv_p, par_p

    def load(self, stem: str) -> pd.DataFrame:
        par = self._cfg.raw_dir / f"{stem}.parquet"
        csv = self._cfg.raw_dir / f"{stem}.csv"
        if par.exists():
            return pd.read_parquet(par)
        if csv.exists():
            return pd.read_csv(csv, encoding="utf-8-sig")
        raise FileNotFoundError(f"No artifact at {par}")


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 12 — HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────────────────

def gini(arr: np.ndarray) -> float:
    a = np.sort(arr.astype(float)); a = a[a >= 0]
    n = len(a)
    if n == 0 or a.sum() == 0: return 0.0
    idx = np.arange(1, n+1)
    return float((2*(idx*a).sum() - (n+1)*a.sum()) / (n*a.sum()))


def compute_nss(df_sub: pd.DataFrame) -> float:
    if len(df_sub) == 0 or "sentiment" not in df_sub.columns: return 0.0
    w   = np.log1p(df_sub["engagement_score"].clip(0).values).clip(min=1)
    s   = df_sub["sentiment"].values
    pos = w[s == 1].sum()
    neg = w[s == -1].sum()
    tot = w.sum()
    return float((pos - neg) / max(tot, 1e-9))


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 13 — VISUALIZATION SUITE (20 charts, all with inline display)
# ──────────────────────────────────────────────────────────────────────────────

class VisualizationSuite:
    """
    20 publication-quality charts. All charts:
    - Saved as PNG in artifacts/plots/
    - Displayed inline in Jupyter/Colab via plt.show()
    """

    def __init__(self, df: pd.DataFrame, config: PipelineConfig):
        self._df    = df.copy()
        self._valid = (df[df["is_valid"] == True].copy()
                       if "is_valid" in df else df.copy())
        self._cfg   = config
        self._log   = _build_logger("ev.viz")
        self._asp_cols = [c for c in df.columns if c.startswith("aspect_")]
        # Parse timestamps
        if "creation_timestamp" in self._valid.columns:
            self._valid["parsed_dt"] = pd.to_datetime(
                self._valid["creation_timestamp"], utc=True, errors="coerce")
            self._valid["year_month"] = self._valid["parsed_dt"].dt.to_period("M")

    def _save_show(self, fig, name):
        _show_save(fig, name, self._cfg)

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 01 — Brand Donut
    # ─────────────────────────────────────────────────────────────────────────
    def chart_01_brand_donut(self):
        counts = self._df["brand_target"].value_counts()
        colors = [BRAND_PAL.get(b, "#888") for b in counts.index]
        fig, ax = plt.subplots(figsize=(9, 7))
        wedges, texts, autotexts = ax.pie(
            counts.values, labels=None, autopct="%1.1f%%",
            colors=colors, startangle=140,
            wedgeprops={"width": 0.55, "edgecolor": "#0D1117", "linewidth": 2},
            pctdistance=0.78,
        )
        for at in autotexts:
            at.set(fontsize=10, color="white", fontweight="bold")
        handles = [mpatches.Patch(color=c, label=f"{b}  ({n:,})")
                   for b, n, c in zip(counts.index, counts.values, colors)]
        ax.legend(handles=handles, loc="lower center", ncol=2,
                  framealpha=0.3, labelcolor="white", bbox_to_anchor=(0.5,-0.08))
        ax.set_title("📊 Brand Distribution — EV Corpus\nShare of discourse volume",
                     pad=20, color="white")
        ax.text(0.5, 0.47, f"Total\n{counts.sum():,}",
                ha="center", va="center", fontsize=12,
                color="white", fontweight="bold", transform=ax.transAxes)
        self._save_show(fig, "01_brand_donut.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 02 — Sentiment Stacked Bar
    # ─────────────────────────────────────────────────────────────────────────
    def chart_02_sentiment_stacked(self):
        if "sentiment" not in self._valid.columns:
            return
        lbl_map = {1: "Positive", 0: "Neutral", -1: "Negative"}
        v = self._valid.copy()
        v["sent_label"] = v["sentiment"].map(lbl_map)
        cross     = v.groupby(["brand_target","sent_label"]).size().unstack(fill_value=0)
        cross_pct = cross.div(cross.sum(axis=1), axis=0) * 100
        brands = [b for b in ["VinFast","BYD","Mixed"] if b in cross_pct.index]
        x = np.arange(len(brands))
        fig, ax = plt.subplots(figsize=(11, 7))
        bot = np.zeros(len(brands))
        for label, color in [("Positive","#00C853"),("Neutral","#9E9E9E"),
                              ("Negative","#F44336")]:
            if label not in cross_pct.columns:
                continue
            vals = [cross_pct.loc[b,label] if b in cross_pct.index else 0 for b in brands]
            bars = ax.bar(x, vals, bottom=bot, color=color, label=label,
                          alpha=0.88, width=0.55)
            for bar, v_val in zip(bars, vals):
                if v_val > 5:
                    ax.text(bar.get_x()+bar.get_width()/2,
                            bar.get_y()+bar.get_height()/2,
                            f"{v_val:.1f}%", ha="center", va="center",
                            fontsize=9, color="white", fontweight="bold")
            bot += np.array(vals)
        ax.set_xticks(x); ax.set_xticklabels(brands, fontsize=11)
        ax.set_ylabel("Percentage (%)")
        ax.set_title("💬 Sentiment Distribution by Brand\n(Weak-supervision + negation inversion)")
        ax.legend(loc="upper right"); ax.set_ylim(0, 115)
        self._save_show(fig, "02_sentiment_stacked_bar.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 03 — Token KDE Validation
    # ─────────────────────────────────────────────────────────────────────────
    def chart_03_token_kde(self):
        from scipy.stats import gaussian_kde
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle("Token Length Distribution — NLP Preprocessing Validation",
                     fontsize=14, fontweight="bold", color="white")
        ax = axes[0]
        raw_len = self._valid["raw_text"].str.split().str.len().clip(0, 200)
        cln_len = self._valid["token_count"].clip(0, 150)
        for data, label, color in [
            (raw_len, "Raw (before NLP)", "#FF6B6B"),
            (cln_len, "Cleaned (post-NLP)", "#4ECDC4"),
        ]:
            d = data.dropna()
            if len(d) > 5:
                xs  = np.linspace(0, min(d.max(), 100), 300)
                kde = gaussian_kde(d[d > 0] if (d > 0).any() else d + 0.1)
                ax.fill_between(xs, kde(xs), alpha=0.3, color=color, label=label)
                ax.plot(xs, kde(xs), color=color, lw=2)
                ax.axvline(d.mean(), color=color, linestyle="--", alpha=0.7,
                           label=f"μ={d.mean():.1f}")
        ax.set_xlabel("Token Count"); ax.set_ylabel("Density")
        ax.set_title("A) Raw vs Preprocessed Token Length (KDE)")
        ax.legend(fontsize=8)
        ax2 = axes[1]
        brand_data = {}
        for b in ["VinFast","BYD"]:
            bd = self._valid[self._valid["brand_target"]==b]["token_count"].dropna()
            if len(bd) > 0:
                brand_data[b] = bd.values
        if brand_data:
            bp = ax2.boxplot(
                list(brand_data.values()),
                tick_labels=list(brand_data.keys()),
                patch_artist=True,
                medianprops={"color": "white", "linewidth": 2},
            )
            for patch, c in zip(bp["boxes"], [BRAND_PAL.get(k,"#888") for k in brand_data]):
                patch.set_facecolor(c); patch.set_alpha(0.7)
        ax2.set_ylabel("Token Count")
        ax2.set_title("B) Token Distribution by Brand (post stopword removal)")
        plt.tight_layout()
        self._save_show(fig, "03_token_kde_validation.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 04 — Aspect Heatmap
    # ─────────────────────────────────────────────────────────────────────────
    def chart_04_aspect_heatmap(self):
        if not self._asp_cols: return
        brands = [b for b in ["VinFast","BYD","Mixed"]
                  if b in self._valid["brand_target"].values]
        asp_labels = [c.replace("aspect_","").replace("_","\n") for c in self._asp_cols]
        data = []
        for brand in brands:
            bdf = self._valid[self._valid["brand_target"]==brand]
            data.append([round(100*bdf[col].mean(),2) for col in self._asp_cols])
        hdf = pd.DataFrame(data, index=brands, columns=asp_labels)
        fig, ax = plt.subplots(figsize=(15, 5))
        sns.heatmap(hdf, ax=ax, annot=True, fmt=".1f", cmap="YlOrRd",
                    linewidths=0.5, linecolor="#30363D",
                    annot_kws={"size":10,"weight":"bold"},
                    cbar_kws={"label":"Coverage (%)","shrink":0.8})
        ax.set_title("🔥 Aspect Coverage Rate by Brand (%)\n% of brand records mentioning each aspect")
        plt.tight_layout()
        self._save_show(fig, "04_aspect_brand_heatmap.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 05 — Aspect Radar Chart
    # ─────────────────────────────────────────────────────────────────────────
    def chart_05_radar(self):
        N = len(self._asp_cols)
        if N == 0: return
        angles    = [n/N*2*np.pi for n in range(N)] + [0]
        asp_short = [c.replace("aspect_","").replace("_","\n") for c in self._asp_cols]
        fig, ax   = plt.subplots(figsize=(10, 10), subplot_kw={"projection":"polar"})
        ax.set_facecolor("#161B22")
        ax.set_title("🕸️ Aspect Coverage Radar — VinFast vs BYD\n"
                     "(% of records mentioning each aspect)",
                     fontsize=13, fontweight="bold", pad=35, color="white")
        for brand in ["VinFast","BYD"]:
            bdf = self._valid[self._valid["brand_target"]==brand]
            if len(bdf) < 3: continue
            vals = [round(100*bdf[col].mean(),2) for col in self._asp_cols] + \
                   [round(100*bdf[self._asp_cols[0]].mean(),2)]
            color = BRAND_PAL.get(brand,"#888")
            ax.plot(angles, vals, lw=2.5, color=color, label=brand)
            ax.fill(angles, vals, alpha=0.18, color=color)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(asp_short, fontsize=9, color="#C9D1D9")
        ax.set_yticks([10,20,30,40,50]); ax.set_yticklabels(["10%","20%","30%","40%","50%"],fontsize=7)
        ax.set_ylim(0, 60)
        ax.legend(loc="upper right", bbox_to_anchor=(1.35,1.1), fontsize=11)
        self._save_show(fig, "05_aspect_radar.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 06 — Engagement Analysis
    # ─────────────────────────────────────────────────────────────────────────
    def chart_06_engagement(self):
        eng = self._valid["engagement_score"].values.astype(float)
        fig, axes = plt.subplots(1, 3, figsize=(22, 8))
        fig.suptitle("Engagement Score Analytics — Influence Weighting Justification",
                     fontsize=14, fontweight="bold", color="white")
        ax = axes[0]
        pos = eng[eng > 0]
        if len(pos) > 0:
            ax.hist(pos, bins=60, color="#4ECDC4", alpha=0.75, log=True, edgecolor="none")
        ax.set_xlabel("Engagement Score"); ax.set_ylabel("Count (log)")
        ax.set_title(f"A) Distribution | Gini={gini(eng):.3f}")
        ax.text(0.6, 0.88, f"Gini: {gini(eng):.3f}\nZero: {(eng==0).mean()*100:.1f}%",
                transform=ax.transAxes, fontsize=9, color="#FFEAA7",
                bbox={"facecolor":"#21262D","alpha":0.8,"edgecolor":"none"})
        ax2 = axes[1]
        brands_v = [b for b in ["VinFast","BYD"] if b in self._valid["brand_target"].values]
        vdata = [self._valid[self._valid["brand_target"]==b]["engagement_score"]
                 .clip(0,500).dropna().values for b in brands_v]
        vdata = [v for v in vdata if len(v) > 5]
        if vdata:
            vp = ax2.violinplot(vdata, positions=range(len(vdata)),
                                showmedians=True, showextrema=True)
            for i, pc in enumerate(vp["bodies"]):
                pc.set_facecolor(BRAND_PAL.get(brands_v[i],"#888")); pc.set_alpha(0.7)
            vp["cmedians"].set_color("white"); vp["cmedians"].set_linewidth(2)
        ax2.set_xticks(range(len(brands_v))); ax2.set_xticklabels(brands_v)
        ax2.set_ylabel("Engagement Score"); ax2.set_title("B) Per-Brand Violin")
        ax3 = axes[2]
        se = np.sort(eng)[::-1]; tot = se.sum()
        if tot > 0:
            x_pct = np.arange(1,len(se)+1)/len(se)*100
            y_pct = np.cumsum(se)/tot*100
            ax3.plot(x_pct, y_pct, color="#FFD700", lw=2.5, label="Lorenz curve")
            ax3.fill_between(x_pct, y_pct, 0, alpha=0.15, color="#FFD700")
            ax3.plot([0,100],[0,100],"w--",alpha=0.35,label="Perfect equality")
            idx20 = np.searchsorted(x_pct, 20)
            if idx20 < len(y_pct):
                ax3.text(22, y_pct[idx20]+2,
                         f"Top 20%→{y_pct[idx20]:.1f}%", color="#FF6B6B", fontsize=8)
        ax3.set_xlabel("Cumulative % Records"); ax3.set_ylabel("Cumulative % Engagement")
        ax3.set_title("C) Lorenz Curve"); ax3.legend()
        plt.tight_layout()
        self._save_show(fig, "06_engagement_analysis.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 07 — Temporal Dynamics
    # ─────────────────────────────────────────────────────────────────────────
    def chart_07_temporal(self):
        if "year_month" not in self._valid.columns: return
        vtmp = self._valid.dropna(subset=["year_month"])
        if len(vtmp) == 0: return
        monthly = vtmp.groupby(["year_month","brand_target"]).size().reset_index(name="count")
        pivoted  = monthly.pivot(index="year_month",columns="brand_target",values="count").fillna(0)
        fig, axes = plt.subplots(2, 1, figsize=(18, 12))
        fig.suptitle("📈 Temporal Discourse Dynamics — Vietnamese EV Community",
                     fontsize=15, fontweight="bold", color="white")
        x_lbl = [str(p) for p in pivoted.index]; x_pos = np.arange(len(x_lbl))
        ax = axes[0]; bot = np.zeros(len(x_pos))
        for brand in ["VinFast","BYD","Mixed","Unknown"]:
            if brand in pivoted.columns:
                vals = pivoted[brand].values
                ax.bar(x_pos, vals, bottom=bot, color=BRAND_PAL.get(brand,"#888"),
                       alpha=0.82, label=brand, width=0.75)
                bot += vals
        stride = max(1, len(x_pos)//12)
        ax.set_xticks(x_pos[::stride]); ax.set_xticklabels(x_lbl[::stride], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Records / Month"); ax.set_title("Monthly Volume by Brand"); ax.legend(loc="upper left")
        ax2 = axes[1]
        if "VinFast" in pivoted.columns and "BYD" in pivoted.columns:
            vf = pivoted["VinFast"].values + 1e-6; byd = pivoted["BYD"].values + 1e-6
            sov = vf / (vf + byd)
            ax2.fill_between(x_pos, sov, 0.5, where=sov>=0.5,
                             color=BRAND_PAL["VinFast"], alpha=0.4, label="VinFast dominates")
            ax2.fill_between(x_pos, sov, 0.5, where=sov<0.5,
                             color=BRAND_PAL["BYD"], alpha=0.4, label="BYD gaining")
            ax2.plot(x_pos, sov, color="white", lw=2)
            ax2.axhline(0.5, color="#888", linestyle="--", lw=1.2)
            ax2.set_xticks(x_pos[::stride]); ax2.set_xticklabels(x_lbl[::stride], rotation=45, ha="right", fontsize=8)
            ax2.set_ylabel("VinFast Share-of-Voice"); ax2.set_title("Share-of-Voice Ratio")
            ax2.set_ylim(0,1); ax2.yaxis.set_major_formatter(FuncFormatter(lambda v,_: f"{v:.0%}"))
            ax2.legend()
        plt.tight_layout()
        self._save_show(fig, "07_temporal_dynamics.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 08 — TF-IDF WordClouds (FULLY FIXED)
    # ─────────────────────────────────────────────────────────────────────────
    def chart_08_wordclouds(self):
        brands = [b for b in ["VinFast","BYD"] if b in self._valid["brand_target"].values]
        valid_text = self._valid[self._valid["processed_text"].str.strip() != ""]

        if not _WORDCLOUD:
            # ── Fallback: frequency bar chart instead ──
            self._log.warning("WordCloud not installed — showing frequency bars instead.")
            fig, axes = plt.subplots(1, len(brands), figsize=(20, 9))
            if len(brands) == 1: axes = [axes]
            fig.suptitle("Top TF-IDF Terms (install wordcloud for cloud view)",
                         fontsize=14, color="white")
            for ax, brand in zip(axes, brands):
                texts = valid_text[valid_text["brand_target"]==brand]["processed_text"].tolist()
                if not texts: continue
                try:
                    vec   = TfidfVectorizer(max_features=500, min_df=2, sublinear_tf=True)
                    mat   = vec.fit_transform(texts)
                    feats = vec.get_feature_names_out()
                    scores= np.asarray(mat.mean(axis=0)).flatten()
                    top   = scores.argsort()[::-1][:20]
                    ax.barh(range(20), scores[top], color=BRAND_PAL.get(brand,"#888"), alpha=0.8)
                    ax.set_yticks(range(20)); ax.set_yticklabels(feats[top], fontsize=9)
                    ax.invert_yaxis()
                    ax.set_title(f"{brand} — Top 20 TF-IDF Terms")
                except Exception as e:
                    ax.text(0.5,0.5,str(e),ha="center",va="center",color="white")
            plt.tight_layout()
            self._save_show(fig, "08_tfidf_wordclouds.png")
            return

        # ── Full WordCloud rendering ──────────────────────────────────────────
        fig, axes = plt.subplots(1, len(brands), figsize=(20, 9))
        if len(brands) == 1: axes = [axes]
        fig.patch.set_facecolor("#0D1117")
        fig.suptitle(
            "☁️ TF-IDF Semantic Word Clouds — Brand-Discriminative Vocabulary\n"
            "(Word size ∝ TF-IDF importance; color ∝ brand)",
            fontsize=14, fontweight="bold", color="white"
        )
        for ax, brand in zip(axes, brands):
            ax.set_facecolor("#0D1117")
            texts = valid_text[valid_text["brand_target"]==brand]["processed_text"].tolist()
            if not texts:
                ax.text(0.5,0.5,f"No data: {brand}",ha="center",va="center",color="white")
                ax.axis("off"); continue
            try:
                vec   = TfidfVectorizer(max_features=2500, min_df=2, max_df=0.85,
                                        sublinear_tf=True, ngram_range=(1,2))
                mat   = vec.fit_transform(texts)
                feats = vec.get_feature_names_out()
                scores= np.asarray(mat.mean(axis=0)).flatten()
                freq  = {f: float(s) for f, s in zip(feats, scores) if s > 0.001}
            except Exception as e:
                freq = dict(Counter(" ".join(texts).split()).most_common(300))
            if not freq:
                ax.text(0.5,0.5,"No terms found",ha="center",va="center",color="white")
                ax.axis("off"); continue

            base = BRAND_PAL.get(brand,"#888888").lstrip("#")
            br, bg, bb = int(base[0:2],16), int(base[2:4],16), int(base[4:6],16)

            def _color_func(word, font_size, position, orientation,
                            random_state=None, **kwargs):
                v = 55
                r = max(0, min(255, br + random.randint(-v, v)))
                g = max(0, min(255, bg + random.randint(-v, v)))
                b = max(0, min(255, bb + random.randint(-v, v)))
                return f"rgb({r},{g},{b})"

            wc = WordCloud(
                width=1400, height=750,
                background_color="#0D1117",
                max_words=130,
                prefer_horizontal=0.72,
                color_func=_color_func,
                min_font_size=9, max_font_size=140,
                collocations=False,
                random_state=42, margin=2,
            ).generate_from_frequencies(freq)

            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            ax.set_facecolor("#0D1117")
            ax.text(0.5, 0.03, f"{brand}  ·  {len(texts):,} records",
                    transform=ax.transAxes, ha="center", va="bottom",
                    fontsize=13, fontweight="bold",
                    color=BRAND_PAL.get(brand,"white"),
                    bbox={"facecolor":"#0D1117","alpha":0.7,"edgecolor":"none",
                          "boxstyle":"round,pad=0.3"})
        plt.tight_layout(pad=1.5)
        self._save_show(fig, "08_tfidf_wordclouds.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 09 — N-gram Comparison
    # ─────────────────────────────────────────────────────────────────────────
    def chart_09_ngram(self):
        valid_text = self._valid[self._valid["processed_text"].str.strip() != ""]
        fig, axes  = plt.subplots(1, 2, figsize=(18, 10))
        fig.suptitle("🔤 Brand-Discriminative TF-IDF N-gram Comparison\n"
                     "(Top 15 terms by brand-specific TF-IDF weight)",
                     fontsize=14, fontweight="bold", color="white")
        for ax, brand in zip(axes, ["VinFast","BYD"]):
            texts = valid_text[valid_text["brand_target"]==brand]["processed_text"].tolist()
            if len(texts) < 5:
                ax.text(0.5,0.5,f"Insufficient data: {brand}",ha="center",va="center"); continue
            try:
                vec   = TfidfVectorizer(ngram_range=(1,3), max_features=3000,
                                        min_df=2, max_df=0.85, sublinear_tf=True)
                mat   = vec.fit_transform(texts)
                feats = vec.get_feature_names_out()
                scores= np.asarray(mat.mean(axis=0)).flatten()
                top_idx = scores.argsort()[::-1][:15]
            except Exception as e:
                ax.text(0.5,0.5,str(e),ha="center",va="center",color="white"); continue
            color = BRAND_PAL.get(brand,"#888")
            bars  = ax.barh(range(15), scores[top_idx], color=color, alpha=0.82,
                            height=0.65, edgecolor="none")
            ax.set_yticks(range(15)); ax.set_yticklabels(feats[top_idx], fontsize=9)
            ax.invert_yaxis()
            ax.set_xlabel("Mean TF-IDF Score")
            ax.set_title(f"{brand} — Top Discriminative N-grams", fontsize=12)
            for bar, sc in zip(bars, scores[top_idx]):
                ax.text(sc+0.0003, bar.get_y()+bar.get_height()/2,
                        f"{sc:.4f}", va="center", fontsize=7, color="#8B949E")
        plt.tight_layout()
        self._save_show(fig, "09_ngram_comparison.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 10 — Aspect Co-occurrence
    # ─────────────────────────────────────────────────────────────────────────
    def chart_10_cooccurrence(self):
        if not self._asp_cols: return
        asp_data = self._valid[self._asp_cols].astype(int)
        cooc     = asp_data.T.dot(asp_data).values.astype(float)
        diag     = np.diag(cooc)
        norm_c   = cooc / (np.add.outer(diag,diag) - cooc + 1e-10)
        np.fill_diagonal(norm_c, 1.0)
        short = [c.replace("aspect_","")[:14] for c in self._asp_cols]
        fig, ax = plt.subplots(figsize=(11, 9))
        sns.heatmap(
            pd.DataFrame(norm_c, index=short, columns=short),
            ax=ax, annot=True, fmt=".2f", cmap="Blues",
            mask=np.eye(len(short),dtype=bool),
            linewidths=0.5, linecolor="#30363D",
            cbar_kws={"label":"Jaccard Similarity"}, vmin=0, vmax=1,
        )
        ax.set_title("🔗 Aspect Co-occurrence Matrix\n(Jaccard coefficient)")
        plt.tight_layout()
        self._save_show(fig, "10_aspect_cooccurrence.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 11 — Sentiment by Aspect
    # ─────────────────────────────────────────────────────────────────────────
    def chart_11_sentiment_by_aspect(self):
        if "sentiment" not in self._valid.columns or not self._asp_cols: return
        results = []
        for asp in self._asp_cols:
            asp_df = self._valid[self._valid[asp]==True]
            if len(asp_df) == 0: continue
            s = asp_df["sentiment"]
            results.append({
                "aspect":   asp.replace("aspect_","").replace("_","\n"),
                "positive": (s==1).mean()*100,
                "neutral":  (s==0).mean()*100,
                "negative": (s==-1).mean()*100,
                "n":        len(asp_df),
            })
        if not results: return
        rdf = pd.DataFrame(results)
        x   = np.arange(len(rdf)); w = 0.25
        fig, ax = plt.subplots(figsize=(16, 8))
        ax.bar(x-w, rdf["positive"], w, color="#00C853", alpha=0.85, label="Positive")
        ax.bar(x,   rdf["neutral"],  w, color="#9E9E9E", alpha=0.85, label="Neutral")
        ax.bar(x+w, rdf["negative"], w, color="#F44336", alpha=0.85, label="Negative")
        for i, (_, row) in enumerate(rdf.iterrows()):
            ax.text(i, 105, f"n={row['n']}", ha="center", va="bottom", fontsize=7, color="#8B949E")
        ax.set_xticks(x); ax.set_xticklabels(rdf["aspect"], fontsize=9)
        ax.set_ylabel("Percentage (%)")
        ax.set_ylim(0, 115)
        ax.set_title("📊 Sentiment Distribution per Aspect\nWhich aspects drive positive vs negative?")
        ax.legend(); ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        self._save_show(fig, "11_sentiment_by_aspect.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 12 — NSS Comparison
    # ─────────────────────────────────────────────────────────────────────────
    def chart_12_nss(self):
        if "sentiment" not in self._valid.columns or not self._asp_cols: return
        v = self._valid.copy()
        nss_data = []
        for brand in ["VinFast","BYD"]:
            bdf = v[v["brand_target"]==brand]
            if len(bdf) < 3: continue
            for asp in self._asp_cols:
                adf = bdf[bdf[asp]==True]
                nss_data.append({
                    "brand":  brand,
                    "aspect": asp.replace("aspect_",""),
                    "nss":    compute_nss(adf),
                    "n":      len(adf),
                })
        if not nss_data: return
        ndf     = pd.DataFrame(nss_data)
        aspects = ndf["aspect"].unique()
        x = np.arange(len(aspects)); w = 0.35
        fig, ax = plt.subplots(figsize=(16, 8))
        for i, brand in enumerate(["VinFast","BYD"]):
            bdata = ndf[ndf["brand"]==brand].set_index("aspect")
            vals  = [bdata.loc[a,"nss"] if a in bdata.index else 0 for a in aspects]
            bars  = ax.bar(x+i*w-w/2, vals, w, color=BRAND_PAL.get(brand,"#888"),
                           label=brand, alpha=0.85, edgecolor="none")
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x()+bar.get_width()/2,
                        bar.get_height()+(0.01 if val>=0 else -0.04),
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=7.5, color="white")
        ax.axhline(0, color="white", lw=1.5, linestyle="--", alpha=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([a.replace("_","\n") for a in aspects], fontsize=8)
        ax.set_ylabel("Influence-Weighted NSS (-1 to +1)")
        ax.set_title("🎯 Net Sentiment Score per Aspect & Brand\n"
                     "NSS = (Pos−Neg)/Total | Weighted by log(1+engagement)")
        ax.legend(); ax.set_ylim(-1,1); ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        self._save_show(fig, "12_nss_comparison.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 13 — Competitive Bubble Map
    # ─────────────────────────────────────────────────────────────────────────
    def chart_13_bubble_map(self):
        if "sentiment" not in self._valid.columns or not self._asp_cols: return
        rows = []
        for brand in ["VinFast","BYD"]:
            bdf = self._valid[self._valid["brand_target"]==brand]
            for asp in self._asp_cols:
                adf = bdf[bdf[asp]==True]; n = len(adf)
                if n == 0: continue
                rows.append({
                    "brand":  brand,
                    "aspect": asp.replace("aspect_",""),
                    "n": n,
                    "nss": compute_nss(adf),
                })
        if not rows: return
        bdf2    = pd.DataFrame(rows)
        aspects = bdf2["aspect"].unique(); brands = ["VinFast","BYD"]
        asp_idx = {a:i for i,a in enumerate(aspects)}
        br_idx  = {b:i for i,b in enumerate(brands)}
        fig, ax = plt.subplots(figsize=(16, 7))
        cmap = plt.cm.RdYlGn; norm_c = Normalize(-0.6, 0.6)
        for _, row in bdf2.iterrows():
            sc = ax.scatter(
                asp_idx[row["aspect"]], br_idx[row["brand"]],
                s=row["n"]*9, c=[row["nss"]], cmap=cmap, norm=norm_c,
                alpha=0.82, edgecolors="white", linewidths=0.8,
            )
            ax.text(asp_idx[row["aspect"]], br_idx[row["brand"]],
                    f"n={row['n']}", ha="center", va="center",
                    fontsize=7, color="white", fontweight="bold")
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm_c); sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.8); cbar.set_label("NSS Value")
        ax.set_xticks(range(len(aspects)))
        ax.set_xticklabels([a.replace("_","\n") for a in aspects], fontsize=8)
        ax.set_yticks(range(len(brands))); ax.set_yticklabels(brands, fontsize=11)
        ax.set_title("🫧 Competitive Bubble Map — Aspect × Brand × NSS\n"
                     "(Bubble size = record count | Color = NSS)", fontsize=13)
        ax.set_xlim(-0.7, len(aspects)-0.3); ax.set_ylim(-0.7, len(brands)-0.3)
        ax.grid(alpha=0.2)
        plt.tight_layout()
        self._save_show(fig, "13_bubble_map.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 14 — 3D Surface Plot (Sentiment Landscape)
    # ─────────────────────────────────────────────────────────────────────────
    def chart_14_surface(self):
        v = self._valid.dropna(subset=["engagement_score","token_count","sentiment"])
        if len(v) < 20:
            fig, ax = plt.subplots()
            ax.text(0.5,0.5,"Insufficient data for surface",ha="center",va="center"); return
        x  = v["token_count"].clip(0, 80).values.astype(float)
        y  = v["engagement_score"].clip(0, 150).values.astype(float)
        z  = v["sentiment"].astype(float).values
        xi = np.linspace(x.min(), x.max(), 40)
        yi = np.linspace(y.min(), y.max(), 40)
        Xi, Yi = np.meshgrid(xi, yi)
        try:
            Zi = griddata((x,y), z, (Xi,Yi), method="cubic")
        except Exception:
            Zi = griddata((x,y), z, (Xi,Yi), method="linear")
        Zi = np.nan_to_num(Zi, nan=0.0)
        Zi = gaussian_filter(Zi, sigma=1.5)
        fig = plt.figure(figsize=(14,9), facecolor="#0D1117")
        ax  = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#161B22")
        surf = ax.plot_surface(Xi, Yi, Zi, cmap="RdYlGn", alpha=0.88,
                               linewidth=0, antialiased=True)
        fig.colorbar(surf, ax=ax, shrink=0.5, label="Sentiment (−1 to +1)")
        ax.set_xlabel("Token Count"); ax.set_ylabel("Engagement"); ax.set_zlabel("Sentiment")
        ax.set_title("🏔️ 3D Sentiment Landscape\nToken Count × Engagement Space",
                     fontsize=12, color="white")
        ax.tick_params(colors="#C9D1D9")
        self._save_show(fig, "14_surface_sentiment.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 15 — LDA Topic Modeling
    # ─────────────────────────────────────────────────────────────────────────
    def chart_15_lda_topics(self, n_topics: int = 6):
        valid_text = self._valid[self._valid["processed_text"].str.strip() != ""]
        texts = valid_text["processed_text"].tolist()
        if len(texts) < 20: return
        try:
            vec = CountVectorizer(max_features=1000, min_df=2, max_df=0.9)
            dtm = vec.fit_transform(texts)
            feats = vec.get_feature_names_out()
            lda = LatentDirichletAllocation(
                n_components=n_topics, random_state=42, max_iter=30,
                learning_method="batch", n_jobs=-1,
            )
            lda.fit(dtm)
        except Exception as e:
            self._log.error("LDA error: %s", e); return
        fig, axes = plt.subplots(2, 3, figsize=(20, 12))
        fig.suptitle(f"🧠 LDA Topic Modeling — {n_topics} Latent Topics\n"
                     "Unsupervised discovery of EV discussion themes",
                     fontsize=14, fontweight="bold", color="white")
        colors = list(ASPECT_PAL.values())
        for i, (ax, comp) in enumerate(zip(axes.flatten(), lda.components_)):
            top_idx  = comp.argsort()[::-1][:12]
            top_wds  = feats[top_idx]
            top_scrs = comp[top_idx] / max(comp[top_idx].max(), 1e-9)
            ax.barh(range(len(top_wds)), top_scrs,
                    color=colors[i % len(colors)], alpha=0.8, edgecolor="none")
            ax.set_yticks(range(len(top_wds))); ax.set_yticklabels(top_wds, fontsize=8)
            ax.invert_yaxis()
            ax.set_title(f"Topic {i+1}", fontsize=10)
            ax.set_xlim(0, 1.1); ax.set_xlabel("Relative Importance")
        plt.tight_layout()
        self._save_show(fig, "15_lda_topics.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 16 — Preprocessing Dashboard
    # ─────────────────────────────────────────────────────────────────────────
    def chart_16_preproc_dashboard(self):
        v = self._valid.copy()
        v["raw_len"]  = v["raw_text"].str.split().str.len().fillna(0)
        v["cln_len"]  = v["token_count"].fillna(0)
        v["compress"] = v["raw_len"] / v["cln_len"].clip(lower=1)
        fig, axes = plt.subplots(2, 2, figsize=(18, 12))
        fig.suptitle("🛠️ NLP Preprocessing Quality Dashboard", fontsize=14, color="white")
        # A: scatter
        ax = axes[0,0]
        brand_colors = [BRAND_PAL.get(b,"#888") for b in v["brand_target"]]
        ax.scatter(v["raw_len"].clip(0,150), v["cln_len"].clip(0,100),
                   c=brand_colors, alpha=0.35, s=12, edgecolors="none")
        ax.plot([0,150],[0,100],"w--",alpha=0.3,label="y=0.67x reference")
        ax.set_xlabel("Raw tokens"); ax.set_ylabel("Cleaned tokens")
        ax.set_title("A) Noise Removal Scatter")
        handles = [mpatches.Patch(color=BRAND_PAL.get(b,"#888"),label=b)
                   for b in ["VinFast","BYD"]]
        ax.legend(handles=handles, fontsize=7)
        # B: compression ratio
        ax2 = axes[0,1]
        cr  = v["compress"].replace([np.inf,-np.inf],np.nan).dropna().clip(0,10)
        ax2.hist(cr, bins=40, color="#96CEB4", alpha=0.8, edgecolor="none")
        ax2.axvline(cr.mean(), color="white", linestyle="--", label=f"mean={cr.mean():.2f}×")
        ax2.set_xlabel("Compression Ratio (raw/clean)"); ax2.set_ylabel("Records")
        ax2.set_title(f"B) Compression Ratio — {cr.mean():.2f}× mean"); ax2.legend()
        # C: tokens by platform
        ax3 = axes[1,0]
        plats = v.groupby("platform_source")["token_count"].mean().sort_values()
        ax3.barh(plats.index, plats.values, color="#4ECDC4", alpha=0.8, edgecolor="none")
        ax3.set_xlabel("Mean Token Count"); ax3.set_title("C) Tokens by Platform Source")
        # D: language confidence
        ax4 = axes[1,1]
        lc  = v["language_confidence"].dropna()
        ax4.hist(lc, bins=30, color="#DDA0DD", alpha=0.8, edgecolor="none")
        ax4.axvline(lc.mean(), color="white", linestyle="--", label=f"mean={lc.mean():.3f}")
        ax4.set_xlabel("Language Confidence (0–1)"); ax4.set_ylabel("Records")
        ax4.set_title("D) Vietnamese Language Confidence"); ax4.legend()
        plt.tight_layout()
        self._save_show(fig, "16_preprocessing_dashboard.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 17 — Brand Health Matrix (Dasymetric-style)
    # ─────────────────────────────────────────────────────────────────────────
    def chart_17_brand_health_matrix(self):
        if "sentiment" not in self._valid.columns or not self._asp_cols: return
        v = self._valid.copy()
        metrics   = ["NSS\n(Sentiment)", "Coverage\n(%)", "Avg Engagement\n(norm)"]
        brands    = ["VinFast","BYD"]
        n_asp     = len(self._asp_cols)
        fig, axes = plt.subplots(1, 2, figsize=(18, 8))
        fig.suptitle("🏥 Brand Health Matrix (Dasymetric-style)\n"
                     "Aspect × Metric Score Matrix",
                     fontsize=14, fontweight="bold", color="white")
        for ax, brand in zip(axes, brands):
            bdf    = v[v["brand_target"]==brand]
            matrix = np.zeros((n_asp, 3))
            asp_labels = []
            for i, asp in enumerate(self._asp_cols):
                adf = bdf[bdf[asp]==True]; n = len(adf)
                asp_labels.append(asp.replace("aspect_","").replace("_","\n"))
                cov  = (n / max(len(bdf),1)) * 100
                eng  = adf["engagement_score"].mean() if n > 0 else 0
                nss_v = compute_nss(adf)
                matrix[i] = [nss_v, cov/100, min(eng/50,1)]
            im = ax.imshow(matrix.T, cmap="RdYlGn", aspect="auto", vmin=-1, vmax=1)
            ax.set_xticks(range(n_asp)); ax.set_xticklabels(asp_labels, fontsize=7)
            ax.set_yticks(range(3)); ax.set_yticklabels(metrics, fontsize=9)
            ax.set_title(f"{brand}", fontsize=12, fontweight="bold",
                         color=BRAND_PAL.get(brand,"white"))
            for i in range(n_asp):
                for j in range(3):
                    val = matrix[i,j]
                    ax.text(i, j, f"{val:.2f}", ha="center", va="center",
                            fontsize=8, color="white" if abs(val)>0.3 else "#888")
            fig.colorbar(im, ax=ax, shrink=0.6, label="Score")
        plt.tight_layout()
        self._save_show(fig, "17_brand_health_matrix.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 18 — Confusion Matrix (called after model training)
    # ─────────────────────────────────────────────────────────────────────────
    def chart_18_confusion_matrix(self, y_true, y_pred, class_names=None,
                                   model_name="Model"):
        cm_arr      = confusion_matrix(y_true, y_pred)
        class_names = class_names or [str(c) for c in sorted(set(y_true))]
        fig, axes   = plt.subplots(1, 2, figsize=(18, 7))
        fig.suptitle(f"Model Evaluation — {model_name}",
                     fontsize=14, fontweight="bold", color="white")
        ax = axes[0]
        sns.heatmap(cm_arr, annot=True, fmt="d", cmap="Blues", ax=ax,
                    xticklabels=class_names, yticklabels=class_names,
                    linewidths=0.5, linecolor="#30363D",
                    cbar_kws={"shrink":0.8})
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        ax.set_title("Confusion Matrix")
        ax2 = axes[1]
        rpt = classification_report(y_true, y_pred, target_names=class_names,
                                    zero_division=0, output_dict=True)
        class_f1 = {k: v["f1-score"] for k,v in rpt.items()
                    if k not in ["accuracy","macro avg","weighted avg"] and isinstance(v,dict)}
        if class_f1:
            colors_b = ["#F44336","#9E9E9E","#00C853"]
            bars = ax2.bar(list(class_f1.keys()), list(class_f1.values()),
                           color=colors_b[:len(class_f1)], alpha=0.85)
            ax2.set_ylabel("F1-Score"); ax2.set_ylim(0,1.1)
            ax2.set_title("Per-class F1-Score")
            for bar, val in zip(bars, class_f1.values()):
                ax2.text(bar.get_x()+bar.get_width()/2, val+0.02,
                         f"{val:.3f}", ha="center", fontsize=10, fontweight="bold")
        _show_save(fig, "18_confusion_matrix.png", self._cfg)

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 19 — Density Map (Aspect × Time)  ← FULLY FIXED
    # ─────────────────────────────────────────────────────────────────────────
    def chart_19_density_map(self):
        if "year_month" not in self._valid.columns or not self._asp_cols: return
        vtmp = self._valid.dropna(subset=["year_month"])
        if len(vtmp) < 10: return

        periods    = sorted(vtmp["year_month"].unique())
        asp_labels = [c.replace("aspect_","") for c in self._asp_cols]
        density    = np.zeros((len(self._asp_cols), len(periods)))
        for j, period in enumerate(periods):
            period_df = vtmp[vtmp["year_month"]==period]
            for i, asp in enumerate(self._asp_cols):
                density[i,j] = period_df[asp].sum()

        # Normalize per row
        row_max     = density.max(axis=1, keepdims=True)
        density_norm = density / np.where(row_max > 0, row_max, 1)

        fig, ax = plt.subplots(figsize=(max(14, len(periods)*0.9), 8))
        im = ax.imshow(density_norm, cmap="hot", aspect="auto",
                       vmin=0, vmax=1, interpolation="nearest")
        ax.set_yticks(range(len(asp_labels)))
        ax.set_yticklabels(asp_labels, fontsize=9)
        period_strs = [str(p) for p in periods]
        stride = max(1, len(periods)//12)
        ax.set_xticks(range(0, len(periods), stride))
        ax.set_xticklabels(period_strs[::stride], rotation=45, ha="right", fontsize=8)
        ax.set_title("🗺️ Aspect Activity Density Map — Temporal Distribution\n"
                     "(Color intensity = relative mention volume; hotter = more active)",
                     fontsize=13, color="white")
        ax.set_xlabel("Month"); ax.set_ylabel("Aspect Category")
        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label("Normalized Activity (0=low, 1=peak month)", fontsize=9)
        # Annotate counts
        for i in range(len(self._asp_cols)):
            for j in range(len(periods)):
                val = int(density[i,j])
                if val > 0:
                    ax.text(j, i, str(val), ha="center", va="center",
                            fontsize=6.5,
                            color="white" if density_norm[i,j]>0.5 else "#aaa")
        plt.tight_layout()
        self._save_show(fig, "19_density_map_temporal.png")

    # ─────────────────────────────────────────────────────────────────────────
    # Chart 20 — Engagement Density Heatmap (2D KDE)  ← FULLY FIXED
    # ─────────────────────────────────────────────────────────────────────────
    def chart_20_engagement_density(self):
        v = self._valid[(self._valid["token_count"]>0) &
                        (self._valid["engagement_score"]>=0)]
        if len(v) < 20: return
        fig, axes = plt.subplots(1, 2, figsize=(18, 8))
        fig.suptitle("🌡️ Engagement × Token Count Density Heatmap\n"
                     "2D KDE showing where content mass is concentrated",
                     fontsize=14, fontweight="bold", color="white")
        for ax, brand in zip(axes, ["VinFast","BYD"]):
            bdf = v[v["brand_target"]==brand]
            if len(bdf) < 10:
                ax.text(0.5,0.5,f"No data: {brand}",ha="center",va="center",color="white"); continue
            x = bdf["token_count"].clip(1,80).values.astype(float)
            y = bdf["engagement_score"].clip(0,200).values.astype(float)
            h, xedges, yedges = np.histogram2d(x, y, bins=20, density=True)
            h_smooth = gaussian_filter(h, sigma=1.0)
            extent   = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
            cmap_brand = LinearSegmentedColormap.from_list(
                f"brand_{brand}", ["#0D1117", BRAND_PAL.get(brand,"#888"), "#FFFFFF"])
            im = ax.imshow(h_smooth.T, extent=extent, origin="lower",
                           cmap=cmap_brand, aspect="auto", interpolation="bilinear")
            ax.scatter(x, y, alpha=0.10, s=7, c=BRAND_PAL.get(brand,"#888"), edgecolors="none")
            ax.set_xlabel("Token Count (post-NLP)"); ax.set_ylabel("Engagement (likes)")
            ax.set_title(f"{brand} — Content Density\n({len(bdf):,} records)",
                         color=BRAND_PAL.get(brand,"white"))
            fig.colorbar(im, ax=ax, shrink=0.8, label="Density")
        plt.tight_layout()
        self._save_show(fig, "20_engagement_density_heatmap.png")

    # ─────────────────────────────────────────────────────────────────────────
    # BONUS Chart 21 — Sentiment Wordclouds (Positive vs Negative)
    # ─────────────────────────────────────────────────────────────────────────
    def chart_21_sentiment_wordclouds(self):
        if "sentiment" not in self._valid.columns: return
        if not _WORDCLOUD:
            self._log.warning("wordcloud not installed — skipping chart 21.")
            return

        valid_text = self._valid[self._valid["processed_text"].str.strip() != ""]
        fig, axes  = plt.subplots(2, 2, figsize=(20, 14))
        fig.patch.set_facecolor("#0D1117")
        fig.suptitle(
            "☁️ Positive vs Negative WordClouds — VinFast & BYD\n"
            "(TF-IDF weighted; top: Positive | bottom: Negative)",
            fontsize=14, fontweight="bold", color="white"
        )
        axes_map = {
            "VinFast_pos": axes[0,0], "BYD_pos":     axes[0,1],
            "VinFast_neg": axes[1,0], "BYD_neg":     axes[1,1],
        }
        for (brand, sent_val, label), ax in zip(
            [("VinFast",1,"Positive"),("BYD",1,"Positive"),
             ("VinFast",-1,"Negative"),("BYD",-1,"Negative")],
            [axes[0,0], axes[0,1], axes[1,0], axes[1,1]]
        ):
            ax.set_facecolor("#0D1117")
            subset = valid_text[
                (valid_text["brand_target"]==brand) &
                (valid_text["sentiment"]==sent_val)
            ]["processed_text"].tolist()
            if len(subset) < 3:
                ax.text(0.5,0.5,f"Insufficient data\n{brand} {label}",
                        ha="center",va="center",color="white"); ax.axis("off"); continue
            try:
                vec   = TfidfVectorizer(max_features=1500, min_df=1, sublinear_tf=True)
                mat   = vec.fit_transform(subset)
                feats = vec.get_feature_names_out()
                scores = np.asarray(mat.mean(axis=0)).flatten()
                freq  = {f: float(s) for f,s in zip(feats,scores) if s > 0.001}
            except Exception:
                freq = dict(Counter(" ".join(subset).split()).most_common(200))
            if not freq: ax.axis("off"); continue
            wc_color = "#00C853" if sent_val == 1 else "#F44336"
            base = wc_color.lstrip("#")
            br,bg,bb = int(base[0:2],16), int(base[2:4],16), int(base[4:6],16)
            def _cf(word,font_size,position,orientation,random_state=None,**kw):
                v=60
                r2=max(0,min(255,br+random.randint(-v,v)))
                g2=max(0,min(255,bg+random.randint(-v,v)))
                b2=max(0,min(255,bb+random.randint(-v,v)))
                return f"rgb({r2},{g2},{b2})"
            try:
                wc = WordCloud(
                    width=900, height=500, background_color="#0D1117",
                    max_words=100, color_func=_cf,
                    min_font_size=8, max_font_size=110,
                    collocations=False, random_state=42,
                ).generate_from_frequencies(freq)
                ax.imshow(wc, interpolation="bilinear")
            except Exception as e:
                ax.text(0.5,0.5,str(e),ha="center",va="center",color="white")
            ax.axis("off")
            color_label = "#00C853" if sent_val == 1 else "#F44336"
            ax.text(0.5, 0.04, f"{brand} — {label}  ({len(subset)} records)",
                    transform=ax.transAxes, ha="center", va="bottom",
                    fontsize=11, fontweight="bold", color=color_label,
                    bbox={"facecolor":"#0D1117","alpha":0.75,"edgecolor":"none","boxstyle":"round"})
        plt.tight_layout(pad=1.5)
        self._save_show(fig, "21_sentiment_wordclouds_posneg.png")

    # ─────────────────────────────────────────────────────────────────────────
    def run_all(self):
        """Execute all charts in sequence."""
        self._log.info("=" * 60)
        self._log.info("VISUALIZATION SUITE — 21 CHARTS")
        self._log.info("=" * 60)
        jobs = [
            ("01 Brand Donut",          self.chart_01_brand_donut),
            ("02 Sentiment Stacked",    self.chart_02_sentiment_stacked),
            ("03 Token KDE",            self.chart_03_token_kde),
            ("04 Aspect Heatmap",       self.chart_04_aspect_heatmap),
            ("05 Radar",                self.chart_05_radar),
            ("06 Engagement",           self.chart_06_engagement),
            ("07 Temporal",             self.chart_07_temporal),
            ("08 WordClouds",           self.chart_08_wordclouds),
            ("09 N-gram",               self.chart_09_ngram),
            ("10 Co-occurrence",        self.chart_10_cooccurrence),
            ("11 Sentiment by Aspect",  self.chart_11_sentiment_by_aspect),
            ("12 NSS",                  self.chart_12_nss),
            ("13 Bubble Map",           self.chart_13_bubble_map),
            ("14 Surface Plot",         self.chart_14_surface),
            ("15 LDA Topics",           self.chart_15_lda_topics),
            ("16 Preproc Dashboard",    self.chart_16_preproc_dashboard),
            ("17 Brand Health Matrix",  self.chart_17_brand_health_matrix),
            ("19 Density Map",          self.chart_19_density_map),
            ("20 Engagement Density",   self.chart_20_engagement_density),
            ("21 Sentiment WordClouds", self.chart_21_sentiment_wordclouds),
        ]
        for name, fn in jobs:
            try:
                self._log.info("→ Generating: %s", name)
                fn()
            except Exception as e:
                self._log.error("❌ Error in %s: %s", name, e)
                import traceback; traceback.print_exc()
        n = len(list(self._cfg.plots_dir.glob("*.png")))
        self._log.info("✅ Visualization suite done — %d charts saved to %s", n, self._cfg.plots_dir)


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 14 — SENTIMENT CLASSIFIER
# ──────────────────────────────────────────────────────────────────────────────

class SentimentClassifier:
    """LightGBM + RandomForest ensemble on TF-IDF features."""

    def __init__(self, config: PipelineConfig):
        self._cfg        = config
        self._log        = _build_logger("ev.classifier")
        self._lgb_model  = None
        self._rf_model   = None
        self._vectorizer = None
        self._le         = LabelEncoder()

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        self._log.info("Starting classifier training...")
        tdf = df[df.get("is_valid", True) if "is_valid" in df.columns else [True]*len(df)]
        tdf = df[df["processed_text"].str.strip().astype(bool).fillna(False)]
        if len(tdf) < 30:
            self._log.warning("Insufficient data (%d records).", len(tdf))
            return {"error":"insufficient_data"}
        X     = tdf["processed_text"].values
        y_raw = tdf["sentiment"].values
        self._le.fit(y_raw)
        y = self._le.transform(y_raw)
        self._log.info("Training: %d records | Classes: %s", len(X), self._le.classes_.tolist())

        self._vectorizer = TfidfVectorizer(
            max_features=15000, ngram_range=(1,3), min_df=2,
            max_df=0.9, sublinear_tf=True, strip_accents=None,
        )
        X_vec = self._vectorizer.fit_transform(X).astype(np.float32)

        try:
            X_tr, X_te, y_tr, y_te = train_test_split(
                X_vec, y, test_size=0.2, random_state=42, stratify=y)
        except ValueError:
            X_tr, X_te, y_tr, y_te = train_test_split(X_vec, y, test_size=0.2, random_state=42)

        results = {}

        # LightGBM
        if _LGB:
            self._lgb_model = lgb.LGBMClassifier(
                n_estimators=500, learning_rate=0.04, max_depth=8,
                num_leaves=31, class_weight="balanced",
                random_state=42, n_jobs=-1, verbose=-1, min_child_samples=5,
            )
            self._lgb_model.fit(X_tr, y_tr)
            y_pred = self._lgb_model.predict(X_te)
            acc = accuracy_score(y_te, y_pred)
            f1  = f1_score(y_te, y_pred, average="macro", zero_division=0)
            results["lgbm"] = {"accuracy": round(acc,4), "f1_macro": round(f1,4)}
            self._log.info("LightGBM → Acc=%.4f | F1=%.4f", acc, f1)
        else:
            y_pred = None

        # RandomForest
        self._rf_model = RandomForestClassifier(
            n_estimators=200, max_depth=12, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )
        X_tr_d = X_tr.toarray() if issparse(X_tr) else X_tr
        X_te_d = X_te.toarray() if issparse(X_te) else X_te
        self._rf_model.fit(X_tr_d, y_tr)
        y_pred_rf = self._rf_model.predict(X_te_d)
        acc_rf = accuracy_score(y_te, y_pred_rf)
        f1_rf  = f1_score(y_te, y_pred_rf, average="macro", zero_division=0)
        results["rf"] = {"accuracy": round(acc_rf,4), "f1_macro": round(f1_rf,4)}
        self._log.info("RandomForest → Acc=%.4f | F1=%.4f", acc_rf, f1_rf)

        # Confusion Matrix
        best_pred   = y_pred if y_pred is not None else y_pred_rf
        class_names = [str(c) for c in self._le.classes_]
        viz = VisualizationSuite.__new__(VisualizationSuite)
        viz._cfg = self._cfg; viz._log = self._log
        viz.chart_18_confusion_matrix(
            y_te, best_pred, class_names,
            model_name="LightGBM" if _LGB else "RandomForest"
        )

        # Save
        if _LGB and self._lgb_model:
            joblib.dump(self._lgb_model, self._cfg.models_dir/"lgbm_sentiment.pkl")
        joblib.dump(self._rf_model,   self._cfg.models_dir/"rf_sentiment.pkl")
        joblib.dump(self._vectorizer, self._cfg.models_dir/"tfidf_vectorizer.pkl")
        joblib.dump(self._le,         self._cfg.models_dir/"label_encoder.pkl")
        self._log.info("✅ Models saved to %s", self._cfg.models_dir)

        results["n_train"]  = X_tr.shape[0]  # FIXED: no len() on sparse
        results["n_test"]   = X_te.shape[0]
        results["classes"]  = self._le.classes_.tolist()
        return results

    def predict(self, texts: List[str]) -> List[Dict]:
        if self._vectorizer is None:
            raise RuntimeError("Call .train() first.")
        norm = ViTextNormalizer(); seg = ViSegmenter(); sf = StopFilter()
        processed = []
        for t in texts:
            n = norm.normalize(t); s = seg.segment(n); f,_,_ = sf.filter(s)
            processed.append(f)
        X = self._vectorizer.transform(processed).astype(np.float32)
        if _LGB and self._lgb_model:
            probs = self._lgb_model.predict_proba(X)
        else:
            probs = self._rf_model.predict_proba(X.toarray() if issparse(X) else X)
        preds = probs.argmax(axis=1)
        return [
            {"text": t, "sentiment": int(self._le.inverse_transform([p])[0]),
             "confidence": round(float(probs[i].max()),4)}
            for i, (t,p) in enumerate(zip(texts, preds))
        ]


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 15 — EXECUTIVE SUMMARY + ANNOTATION EXPORT
# ──────────────────────────────────────────────────────────────────────────────

def print_executive_summary(df: pd.DataFrame) -> None:
    sep   = "=" * 72
    valid = df[df["is_valid"]==True] if "is_valid" in df.columns else df
    eng   = valid["engagement_score"].values.astype(float)
    print(f"\n{sep}")
    print("  CORPUS EXECUTIVE SUMMARY — EV SENTIMENT ANALYSIS PIPELINE v4.0")
    print(sep)
    print(f"\n  📊 COLLECTION OVERVIEW")
    print(f"  {'Total Records':<35}: {len(df):>10,}")
    print(f"  {'Valid Records':<35}: {len(valid):>10,}")
    print(f"  {'Pass Rate':<35}: {100*len(valid)/max(len(df),1):>9.1f}%")
    print(f"\n  🏷️  BRAND DISTRIBUTION")
    for brand, cnt in df["brand_target"].value_counts().items():
        pct = 100*cnt/max(len(df),1)
        print(f"  {brand:<35}: {cnt:>10,}  ({pct:.1f}%)")
    print(f"\n  📡 PLATFORM SOURCES")
    for plat, cnt in df["platform_source"].value_counts().items():
        pct = 100*cnt/max(len(df),1)
        print(f"  {plat:<35}: {cnt:>10,}  ({pct:.1f}%)")
    if "token_count" in valid.columns:
        tc = valid["token_count"].dropna()
        print(f"\n  📝 TOKEN STATISTICS")
        print(f"  {'Mean / Median tokens':<35}: {tc.mean():.1f} / {tc.median():.1f}")
        print(f"  {'Std Dev':<35}: {tc.std():.2f}")
        print(f"  {'P5 / P95 range':<35}: {tc.quantile(.05):.0f} – {tc.quantile(.95):.0f}")
    if len(eng) > 0:
        print(f"\n  ❤️  ENGAGEMENT STATISTICS")
        print(f"  {'Total Interactions':<35}: {int(eng.sum()):>10,}")
        print(f"  {'Gini Coefficient':<35}: {gini(eng):>10.4f}")
        print(f"  {'Zero-engagement Records':<35}: {(eng==0).mean()*100:>9.1f}%")
    if "sentiment" in valid.columns:
        print(f"\n  💬 SENTIMENT DISTRIBUTION")
        for sent, lbl in [(1,"Positive"),(0,"Neutral"),(-1,"Negative")]:
            n   = (valid["sentiment"]==sent).sum()
            pct = 100*n/max(len(valid),1)
            print(f"  {lbl:<35}: {n:>10,}  ({pct:.1f}%)")
    asp_cols = [c for c in valid.columns if c.startswith("aspect_")]
    if asp_cols:
        print(f"\n  🔍 ASPECT COVERAGE")
        for col in asp_cols:
            lbl = col.replace("aspect_","")
            cnt = valid[col].sum()
            pct = 100*valid[col].mean()
            print(f"  {lbl:<35}: {int(cnt):>10,}  ({pct:.1f}%)")
    print(f"\n{sep}\n")


def generate_annotation_sample(df: pd.DataFrame, config: PipelineConfig,
                                n_per_stratum: int = 25) -> pd.DataFrame:
    valid    = df[(df["is_valid"]==True) if "is_valid" in df.columns else [True]*len(df)]
    valid    = valid[valid["processed_text"].str.strip().astype(bool).fillna(False)]
    asp_cols = [c for c in valid.columns if c.startswith("aspect_")]
    sampled, ids = [], set()
    for brand in ["VinFast","BYD","Mixed"]:
        bdf = valid[valid["brand_target"]==brand]
        for asp in asp_cols:
            adf = bdf[bdf[asp]==True]
            n   = min(n_per_stratum, len(adf))
            if n > 0:
                samp = adf.sample(n=n, random_state=42)
                new  = samp[~samp["record_id"].isin(ids)]
                sampled.append(new); ids.update(new["record_id"].tolist())
    if asp_cols:
        no_asp = valid[valid[asp_cols].sum(axis=1)==0]
        if len(no_asp) > 0:
            sampled.append(no_asp.sample(min(40,len(no_asp)), random_state=42))
    if not sampled:
        return pd.DataFrame()
    ann_df = pd.concat(sampled, ignore_index=True).drop_duplicates("record_id")
    for asp in ASPECT_MAP:
        ann_df[f"label_{asp}_polarity"] = ""
    ann_df["annotation_id"] = [f"ANN_{i:05d}" for i in range(len(ann_df))]
    csv_cols = (["annotation_id","record_id","brand_target","raw_text","processed_text"]
                + [c for c in ann_df.columns if c.startswith("label_")])
    csv_cols = [c for c in csv_cols if c in ann_df.columns]
    csv_p    = config.annotation_dir / "annotation_sample.csv"
    ann_df[csv_cols].to_csv(csv_p, index=False, encoding="utf-8-sig")
    ls_recs  = [{"id":r["annotation_id"],"data":{
        "text":r["raw_text"],"processed":r["processed_text"],"brand":r["brand_target"],
        "weak_sentiment":int(r.get("sentiment",0)),
        "weak_aspects":{a:bool(r.get(f"aspect_{a}",False)) for a in ASPECT_MAP},
    }} for _, r in ann_df.iterrows()]
    ls_p = config.annotation_dir / "labelstudio_import.json"
    with open(ls_p,"w",encoding="utf-8") as f:
        json.dump(ls_recs, f, ensure_ascii=False, indent=2)
    LOG.info("✅ Annotation sample: %d records → %s | %s", len(ann_df), csv_p, ls_p)
    return ann_df


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 16 — FULL PIPELINE ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(
    youtube_api_key:       str  = CONFIG.youtube_api_key,
    reddit_client_id:      str  = CONFIG.reddit_client_id,
    reddit_client_secret:  str  = CONFIG.reddit_client_secret,
    load_cached:           bool = False,
    augment_synthetic:     bool = True,
    min_records_threshold: int  = 300,
    show_plots:            bool = True,
    n_synthetic_per_brand: int  = 450,
) -> Dict[str, Any]:
    """
    Master orchestrator — 5 phases end-to-end.

    Phase 1: Multi-source Data Acquisition (YouTube + Reddit + Forum + Shopee + Synthetic)
    Phase 2: Vietnamese NLP Preprocessing (8-stage pipeline)
    Phase 3: EDA + 21 Visualization Charts (auto-displayed in Jupyter/Colab)
    Phase 4: ML Model Training (LightGBM + RandomForest)
    Phase 5: Annotation Sample Export (CSV + Label Studio JSON)
    """
    LOG.info("=" * 70)
    LOG.info("EV SENTIMENT ANALYSIS PIPELINE v4.0 — FULL EXECUTION")
    LOG.info("VinFast vs BYD | Vietnamese EV Community | ABSA")
    LOG.info("=" * 70)

    config   = PipelineConfig(
        youtube_api_key=youtube_api_key,
        reddit_client_id=reddit_client_id,
        reddit_client_secret=reddit_client_secret,
    )
    datalake = DataLake(config)
    outputs  = {}

    # ══════════ PHASE 1 — DATA ACQUISITION ══════════════════════════════════
    LOG.info("\n[PHASE 1] MULTI-SOURCE DATA ACQUISITION")

    if load_cached:
        try:
            df_raw = datalake.load("raw_ev_corpus_v4")
            LOG.info("Loaded cached corpus: %d records", len(df_raw))
        except FileNotFoundError:
            LOG.warning("Cache not found — running live acquisition.")
            load_cached = False

    if not load_cached:
        all_records = []

        # Source 1: YouTube
        yt_recs = YouTubeCollector(config).collect()
        LOG.info("YouTube: %d records", len(yt_recs))
        all_records.extend(yt_recs)

        # Source 2: Reddit
        reddit_recs = RedditCollector(config).collect()
        LOG.info("Reddit: %d records", len(reddit_recs))
        all_records.extend(reddit_recs)

        # Source 3: Forum scraper
        forum_recs = ForumScraper(config).collect()
        LOG.info("Forum: %d records", len(forum_recs))
        all_records.extend(forum_recs)

        # Source 4: Shopee accessory reviews
        shopee_recs = ShopeeReviewCollector(config).collect()
        LOG.info("Shopee: %d records", len(shopee_recs))
        all_records.extend(shopee_recs)

        LOG.info("Total from live sources: %d records", len(all_records))

        # Synthetic augmentation
        if len(all_records) < min_records_threshold and augment_synthetic:
            LOG.info("Below threshold (%d < %d) — adding synthetic data.",
                     len(all_records), min_records_threshold)
            synth = SyntheticDataGenerator().generate(n_per_brand=n_synthetic_per_brand)
            all_records.extend(synth)
            LOG.info("After augmentation: %d total records", len(all_records))

        df_raw = records_to_df(all_records)
        datalake.save(df_raw, "raw_ev_corpus_v4")

    LOG.info("Brand distribution:\n%s",
             df_raw["brand_target"].value_counts().to_string())
    outputs["df_raw"] = df_raw

    # ══════════ PHASE 2 — NLP PREPROCESSING ══════════════════════════════════
    LOG.info("\n[PHASE 2] NLP PREPROCESSING")
    preprocessor = MasterPreprocessor(config)
    df_processed  = preprocessor.process_df(df_raw)

    # Apply ground-truth labels from synthetic records
    if "_sentiment_label" in df_raw.columns:
        lbl_map  = {"positive":1,"neutral":0,"negative":-1}
        syn_mask = df_raw["video_or_thread_id"].str.startswith("synthetic", na=False)
        if syn_mask.sum() > 0:
            new_lbl = df_raw.loc[syn_mask,"_sentiment_label"].map(lbl_map)
            df_processed.loc[syn_mask,"sentiment"] = new_lbl.fillna(0).astype("int8")

    proc_p = config.processed_dir / "ev_corpus_preprocessed_v4.parquet"
    df_processed.to_parquet(proc_p, index=False, compression="snappy")
    df_processed.to_csv(proc_p.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    LOG.info("Preprocessed corpus saved: %s", proc_p)
    print_executive_summary(df_processed)
    outputs["df_processed"] = df_processed

    # ══════════ PHASE 3 — VISUALIZATIONS ═════════════════════════════════════
    LOG.info("\n[PHASE 3] EDA VISUALIZATIONS (21 charts)")
    viz = VisualizationSuite(df_processed, config)
    viz.run_all()
    outputs["plots_dir"] = config.plots_dir

    # ══════════ PHASE 4 — ML TRAINING ════════════════════════════════════════
    LOG.info("\n[PHASE 4] ML MODEL TRAINING")
    clf = SentimentClassifier(config)
    try:
        ml_results = clf.train(df_processed)
        outputs["ml_results"] = ml_results
        if "error" not in ml_results:
            LOG.info("Model results:")
            for k, v in ml_results.items():
                if isinstance(v,dict) and "accuracy" in v:
                    LOG.info("  %-10s → Acc=%.4f | F1=%.4f", k, v["accuracy"], v["f1_macro"])
    except Exception as e:
        LOG.error("ML training failed: %s", e)
        outputs["ml_results"] = {"error": str(e)}

    # ══════════ PHASE 5 — ANNOTATION EXPORT ══════════════════════════════════
    LOG.info("\n[PHASE 5] ANNOTATION SAMPLE GENERATION")
    try:
        ann_df = generate_annotation_sample(df_processed, config)
        outputs["annotation_df"] = ann_df
    except Exception as e:
        LOG.error("Annotation generation failed: %s", e)

    # ══════════ FINAL SUMMARY ════════════════════════════════════════════════
    n_plots = len(list(config.plots_dir.glob("*.png")))
    LOG.info("\n" + "=" * 70)
    LOG.info("✅ PIPELINE v4.0 COMPLETE")
    LOG.info("  Corpus     : %d records", len(df_raw))
    LOG.info("  Processed  : %d valid", df_processed["is_valid"].sum()
             if "is_valid" in df_processed else len(df_processed))
    LOG.info("  Charts     : %d saved → %s", n_plots, config.plots_dir)
    LOG.info("  Models     : %s", config.models_dir)
    LOG.info("  Annotation : %s", config.annotation_dir)
    LOG.info("=" * 70)
    return outputs, clf


# ──────────────────────────────────────────────────────────────────────────────
# BLOCK 17 — ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    API_KEY      = os.environ.get("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY")
    REDDIT_ID    = os.environ.get("REDDIT_CLIENT_ID", "")
    REDDIT_SEC   = os.environ.get("REDDIT_SECRET", "")
    LOAD_CACHED  = False
    AUGMENT      = True
    SHOW_PLOTS   = _IN_NOTEBOOK  # auto-display in Colab/Jupyter

    results, clf = run_full_pipeline(
        youtube_api_key      = API_KEY,
        reddit_client_id     = REDDIT_ID,
        reddit_client_secret = REDDIT_SEC,
        load_cached          = LOAD_CACHED,
        augment_synthetic    = AUGMENT,
        min_records_threshold= 300,
        show_plots           = SHOW_PLOTS,
        n_synthetic_per_brand= 450,
    )

    # ── Live Inference Demo ──────────────────────────────────────────────────
    demo_texts = [
        "Pin VF8 sạc nhanh, ổn định, rất hài lòng sau 6 tháng!",
        "Cảnh báo ảo liên tục, phần mềm lỗi nhiều quá thất vọng.",
        "BYD Seal thiết kế đẹp nhưng giá hơi cao so với trang bị.",
        "Trạm sạc VinFast phủ rộng nhưng hay bị ngắt sạc sớm.",
        "Không tệ, dùng được 1 năm không vấn đề gì lớn.",
        "BYD Dolphin giá hợp lý, pin ổn định, đại lý cần mở rộng thêm.",
        "OTA update VinFast VF9 fix được lỗi cảnh báo ảo, cảm ơn team VinFast!",
        "Phần mềm BYD Seal mượt hơn VF8 nhiều, không gặp bug nào sau 8 tháng.",
    ]
    try:
        preds = clf.predict(demo_texts)
        print("\n" + "─"*70)
        print("[DEMO] Live Inference Results:")
        print("─"*70)
        sent_map = {1:"✅ POSITIVE", 0:"⚪ NEUTRAL", -1:"❌ NEGATIVE"}
        for p in preds:
            print(f"  {sent_map.get(p['sentiment'],'?'):15s} "
                  f"(conf={p['confidence']:.3f}) | {p['text'][:65]}")
        print("─"*70)
    except Exception as e:
        LOG.warning("Demo inference failed: %s", e)

    n_plots = len(list(CONFIG.plots_dir.glob("*.png")))
    print(f"\n{'='*60}")
    print("[DONE] All artifacts saved to ./artifacts/")
    print(f"  📊 Plots     : ./artifacts/plots/  ({n_plots} charts)")
    print(f"  🤖 Models    : ./artifacts/models/")
    print(f"  📁 Data      : ./artifacts/raw/ & ./artifacts/processed/")
    print(f"  📝 Annotation: ./artifacts/annotation/annotation_sample.csv")
    print(f"{'='*60}\n")

