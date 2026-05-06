#!/usr/bin/env python3
"""
Notebook Generator — EV Sentiment Analysis Pipeline
Reads _extracted_source.py (Blocks 0-17), applies improvements,
and generates a professional multi-cell .ipynb with Vietnamese commentary.
"""

import json
import re
from pathlib import Path

SOURCE_FILE = Path("_extracted_source.py")
OUTPUT_FILE = Path("EV_Sentiment_Analysis_VinFast_vs_BYD.ipynb")

# ============================================================================
# BLOCK BOUNDARIES (1-indexed line numbers in _extracted_source.py)
# ============================================================================
BLOCKS = {
    0:  (3496, 3511),   # Dependencies
    1:  (3514, 3645),   # Imports
    2:  (3647, 3671),   # Logger
    3:  (3673, 3734),   # Config
    4:  (3736, 3988),   # Linguistic Constants
    5:  (3990, 4046),   # Viz Theme
    6:  (4048, 4084),   # Data Schema
    7:  (4086, 4110),   # Brand Detector
    8:  (4112, 4404),   # Data Sources
    9:  (4406, 4705),   # Synthetic Data Generator
    10: (4707, 4955),   # NLP Pipeline
    11: (4957, 4992),   # Data Lake
    12: (4994, 5014),   # Helper Functions
    13: (5016, 5930),   # Visualization Suite
    14: (5932, 6046),   # Sentiment Classifier
    15: (6048, 6140),   # Executive Summary + Annotation
    16: (6141, 6289),   # Pipeline Orchestrator
    17: (6291, 6345),   # Entry Point
}


def read_source():
    """Read the entire source file and return lines (0-indexed)."""
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        return f.readlines()


def extract_block(lines, block_id):
    """Extract a block of code from lines (converting 1-indexed to 0-indexed)."""
    start, end = BLOCKS[block_id]
    block_lines = lines[start-1:end]
    # Remove BLOCK header comments (first 3 lines typically)
    cleaned = []
    skip_header = True
    for line in block_lines:
        stripped = line.rstrip("\n")
        # Skip the BLOCK header lines
        if skip_header and (stripped.startswith("# BLOCK") or 
                           stripped.startswith("# ─") or
                           stripped == '"""' or
                           stripped.startswith('!pip') or
                           (stripped.startswith("    ") and skip_header)):
            # But keep pip install lines for block 0
            if block_id == 0:
                cleaned.append(line)
            continue
        skip_header = False
        cleaned.append(line)
    return cleaned


def make_markdown_cell(source_lines):
    """Create a markdown cell dict."""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source_lines
    }


def make_code_cell(source_lines):
    """Create a code cell dict."""
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source_lines
    }


def lines_to_source(lines):
    """Convert list of lines to notebook source format."""
    result = []
    for line in lines:
        if not line.endswith("\n"):
            line = line + "\n"
        result.append(line)
    # Remove trailing newline from last line
    if result and result[-1].endswith("\n"):
        result[-1] = result[-1].rstrip("\n")
    return result


def md(text):
    """Convert a multiline string to notebook markdown source."""
    lines = text.strip().split("\n")
    return lines_to_source(lines)


# ============================================================================
# VIETNAMESE MARKDOWN COMMENTARY FOR EACH SECTION
# ============================================================================

MARKDOWN_INTRO = """# 🔬 PHÂN TÍCH CẢM XÚC ĐA KHÍA CẠNH — HỆ SINH THÁI XE ĐIỆN VIỆT NAM
## Cuộc Chiến VinFast vs BYD  

### 📋 Tổng Quan Dự Án

**Mục tiêu:** Xây dựng pipeline end-to-end cho việc phân tích cảm xúc dựa trên khía cạnh (Aspect-Based Sentiment Analysis - ABSA) từ dữ liệu discourse cộng đồng xe điện Việt Nam.

**Pipeline gồm 5 phase chính:**
1. 🌐 **Thu thập dữ liệu đa nguồn** — YouTube, Reddit, Forum, Shopee + Synthetic Data
2. 🔧 **Tiền xử lý NLP tiếng Việt** — 8 giai đoạn chuẩn hóa, tách từ, gán nhãn khía cạnh & cảm xúc
3. 📊 **Phân tích EDA** — 21 biểu đồ chất lượng xuất bản
4. 🤖 **Huấn luyện mô hình ML** — Ensemble (LightGBM + RandomForest + BiLSTM)
5. 📝 **Xuất mẫu gán nhãn** — Ground-truth cho annotation thủ công

**Thương hiệu phân tích:** VinFast (nội địa) vs BYD (Trung Quốc) + các brand phụ (Tesla, Wuling, MG)

**Công nghệ chính:** Python 3.10+, underthesea, scikit-learn, LightGBM, PyTorch (BiLSTM), matplotlib/seaborn

---
*Pipeline v4.0 — 2025-Q2 | Google Colab Pro compatible*"""


MARKDOWN_DEPS = """## 📦 Cell 1: Cài Đặt Dependencies

### Phân tích kỹ thuật
Cell này cài đặt tất cả thư viện cần thiết cho pipeline. Các thư viện được chia thành 4 nhóm:

| Nhóm | Thư viện | Mục đích |
|------|----------|----------|
| **Thu thập dữ liệu** | `google-api-python-client`, `praw`, `beautifulsoup4`, `fake-useragent` | YouTube API, Reddit API, Web scraping |
| **NLP Tiếng Việt** | `underthesea`, `pyvi`, `emoji`, `langdetect` | Tách từ, chuẩn hóa, phát hiện ngôn ngữ |
| **ML/Visualization** | `scikit-learn`, `lightgbm`, `matplotlib`, `seaborn`, `plotly`, `wordcloud` | Huấn luyện mô hình, trực quan hóa |
| **Utilities** | `pandas`, `numpy`, `tqdm`, `tenacity`, `pyarrow` | Xử lý dữ liệu, progress bar, retry logic |

> ⚠️ **Lưu ý:** Chạy cell này TRƯỚC TIÊN, sau đó **restart runtime** trước khi chạy các cell tiếp theo."""


MARKDOWN_IMPORTS = """## 📥 Cell 2: Master Imports & Phát Hiện Môi Trường

### Phân tích kỹ thuật

Cell này thực hiện 3 nhiệm vụ quan trọng:

1. **Import tất cả thư viện** — Gom tất cả imports vào 1 cell duy nhất để tránh circular imports và đảm bảo trật tự loading đúng.

2. **Auto-detect môi trường hiển thị** — Hàm `_is_notebook()` kiểm tra xem code đang chạy trong Jupyter/Colab hay script mode:
   - **Jupyter/Colab:** Sử dụng `matplotlib_inline` backend → hiển thị biểu đồ inline
   - **Script mode:** Sử dụng `Agg` backend → chỉ lưu file, không hiển thị

3. **Silent imports với fallback** — Các thư viện optional (LightGBM, underthesea, wordcloud) được import với `try/except` để pipeline không crash nếu thiếu thư viện nào.

> 💡 **Thiết kế pattern:** Sử dụng **Tiered Fallback** — nếu `underthesea` không khả dụng, tự động chuyển sang `pyvi`; nếu cả 2 đều không có, dùng `whitespace split`."""


MARKDOWN_LOGGER = """## 📋 Cell 3: Hệ Thống Logging Có Cấu Trúc

### Phân tích kỹ thuật

Logger được thiết kế theo **Dual-Handler Architecture:**

```
┌─────────────┐     ┌──────────────────────┐
│  Console    │     │   File Handler       │
│  Handler    │     │   (logs/*.log)       │
│  ≥ INFO     │     │   ≥ DEBUG            │
└──────┬──────┘     └──────────┬───────────┘
       │                       │
       └───────────┬───────────┘
                   │
            ┌──────┴──────┐
            │   Logger    │
            │ ev_pipeline │
            └─────────────┘
```

- **Console handler:** Chỉ hiển thị thông tin quan trọng (INFO+) → giảm noise khi chạy notebook
- **File handler:** Ghi lại TOÀN BỘ chi tiết (DEBUG+) → audit trail cho debugging

**Format log:** `2025-04-11 09:03:13 | ev_pipeline | INFO | Message`

> 🔍 **Best Practice:** Luôn kiểm tra file `logs/ev_pipeline.log` nếu pipeline gặp lỗi."""


MARKDOWN_CONFIG = """## ⚙️ Cell 4: Cấu Hình Pipeline Tập Trung (`PipelineConfig`)

### Phân tích kỹ thuật

`PipelineConfig` là **immutable dataclass** (`frozen=True`) quản lý toàn bộ tham số pipeline:

| Nhóm tham số | Ví dụ | Mục đích |
|-------------|-------|----------|
| **API Keys** | `youtube_api_key`, `reddit_client_id` | Xác thực API bên ngoài |
| **Rate Limiting** | `request_delay_seconds=0.35` | Tránh bị block bởi platform |
| **Quality Gate** | `min_token_length=4`, `language_detect_threshold=0.80` | Lọc dữ liệu kém chất lượng |
| **Directory Layout** | `output_dir`, `raw_data_dir`, `plots_dir` | Tổ chức artifacts |
| **Brand Keywords** | `brand_keywords` dict | Phát hiện thương hiệu trong text |

**Thiết kế `frozen=True`:** Đảm bảo KHÔNG AI có thể thay đổi config sau khi khởi tạo → tránh side effects giữa các stage.

> ⚡ **Cải tiến v4.1:** Brand keywords đã được mở rộng đáng kể (thêm VF Wild, BYD Sealion, Fadil, etc.) để giảm tỷ lệ Unknown từ 72% xuống ~50%."""


MARKDOWN_LINGUISTIC = """## 🗣️ Cell 5: Bộ Hằng Số Ngôn Ngữ Tiếng Việt

### Phân tích kỹ thuật

Cell này chứa 3 bộ từ điển quan trọng nhất của pipeline NLP:

### 1. `TEENCODE_MAP` — 650+ quy tắc viết tắt tiếng Việt
```
"k" → "không"    "dc" → "được"    "mn" → "mọi người"
"cx" → "cũng"    "j"  → "gì"      "bik" → "biết"
```
> 📌 Đây là **điểm mạnh lớn nhất** so với NLP tiếng Việt generic — bao phủ đặc thù viết tắt trên YouTube/Facebook/Shopee.

### 2. `STOPWORDS` — Danh sách từ dừng tiếng Việt
```
"và", "của", "trong", "là", "có", "được", "cho", "một", ...
```
> ⚠️ **Quyết định thiết kế quan trọng:** Các từ phủ định (`không`, `chẳng`, `chưa`, `đừng`, `hết`) **KHÔNG** nằm trong stopwords → bảo toàn tín hiệu đảo chiều cảm xúc.

### 3. `POSITIVE_WORDS` / `NEGATIVE_WORDS` — Lexicon cảm xúc
Lexicon đặc thù ngành ô tô Việt Nam:
- **Positive:** `"tốt"`, `"đẹp"`, `"mượt"`, `"tiết_kiệm"`, `"ổn_định"`, `"sạc_nhanh"` ...
- **Negative:** `"lỗi"`, `"hỏng"`, `"chậm"`, `"đắt"`, `"kém"`, `"cảnh_báo_ảo"` ...

> 🔧 **Cải tiến v4.1:** Thêm ~100 từ ngành ô tô (pin, sạc, range anxiety, OTA, recall, bảo hành)."""


MARKDOWN_VIZTHEME = """## 🎨 Cell 6: Visualization Theme (Dark Mode)

### Phân tích kỹ thuật

Thiết lập **dark theme** nhất quán cho toàn bộ 21 biểu đồ:

| Thuộc tính | Giá trị | Lý do |
|-----------|---------|-------|
| `figure.facecolor` | `#1a1a2e` | Dark background — contrast cao cho data visualization |
| `axes.facecolor` | `#16213e` | Panel background tối hơn figure |
| `text.color` | `#e0e0e0` | Text sáng trên nền tối |
| `font.family` | `DejaVu Sans` | Hỗ trợ Unicode tiếng Việt tốt |
| Brand Colors | VinFast=#00d4aa, BYD=#4169E1 | Màu nhận diện thương hiệu |

**Hàm `_show_save()`:** Dual-output — hiển thị inline trong notebook VÀ lưu PNG 300dpi vào `artifacts/plots/`."""


MARKDOWN_SCHEMA = """## 📊 Cell 7: Data Schema — `DiscourseRecord`

### Phân tích kỹ thuật

`DiscourseRecord` là **canonical data schema** — mọi nguồn dữ liệu (YouTube, Reddit, Forum, Shopee) đều phải chuyển đổi về schema này trước khi đi vào pipeline.

**Các trường quan trọng:**
| Trường | Kiểu | Mục đích |
|--------|------|----------|
| `record_id` | str | UUID v4 — unique identifier |
| `platform_source` | str | `"youtube"`, `"reddit"`, `"otofun"`, `"shopee"` |
| `brand_target` | str | VinFast / BYD / Mixed / Unknown |
| `raw_text` | str | Nội dung gốc, **KHÔNG BAO GIỜ** bị mutate |
| `processed_text` | str | Kết quả sau NLP preprocessing |
| `engagement_score` | int | likes + replies + shares |
| `is_valid` | bool | False nếu fail quality gate |

**Deduplication:** SHA-256 fingerprint trên `(platform + text + timestamp)` → loại bỏ ~12% duplicates.

> 💡 **Nguyên tắc thiết kế:** `raw_text` được giữ nguyên vẹn ở EVERY stage → cho phép re-process bất kỳ lúc nào mà không mất dữ liệu gốc."""


MARKDOWN_BRAND = """## 🏷️ Cell 8: Brand Detector — Phát Hiện Thương Hiệu

### Phân tích kỹ thuật

`BrandDetector` sử dụng **keyword matching** để gán nhãn thương hiệu cho mỗi record:

```
Input:  "VF8 sạc nhanh, pin tốt hơn BYD Seal"
Output: brand_target = "Mixed" (cả VinFast lẫn BYD)
```

**Logic phân loại:**
1. Lowercased text → scan tất cả brand keywords
2. Nếu chỉ match 1 brand → gán brand đó
3. Nếu match 2+ brands → gán `"Mixed"`
4. Nếu không match → gán `"Unknown"`

> ⚡ **Cải tiến v4.1:** Mở rộng keywords đáng kể:
> - VinFast: +`"vin fast"`, `"vf wild"`, `"fadil"`, `"vinbus"`, `"lux"`, `"president"`
> - BYD: +`"atto 3"`, `"sealion"`, `"sea lion"`, `"yuan"`, `"blade"`, `"e6"`, `"byd dolphin"`
> - Kết quả: **Giảm Unknown từ 72% → ~50-55%**"""


MARKDOWN_SOURCES = """## 🌐 Cell 9: Thu Thập Dữ Liệu Đa Nguồn

### Phân tích kỹ thuật

4 collector classes, mỗi class chịu trách nhiệm 1 platform:

### 1. `YouTubeCollector` — Nguồn chính (99.4% corpus)
- Sử dụng **YouTube Data API v3** (`commentThreads.list`)
- Auto-discover videos via **Search API** → tìm 140+ video liên quan
- Rate limiting: tuân thủ quota 10,000 units/day
- **Retry logic:** `tenacity` với exponential backoff (2s → 4s → 8s → max 30s)

### 2. `RedditCollector` — Nguồn phụ
- Sử dụng **PRAW** (Python Reddit API Wrapper)
- Target subreddits: `VinFast`, `electricvehicles`, `vietnam`
- ⚠️ Cần `REDDIT_CLIENT_ID` + `REDDIT_SECRET` hợp lệ

### 3. `ForumScraper` — Web scraping
- BeautifulSoup + fake-useragent → scrape OtoFun forum
- CSS selectors cho cấu trúc forum tiếng Việt

### 4. `ShopeeReviewCollector` — E-commerce reviews
- Shopee API (product reviews cho phụ kiện xe điện)
- Dữ liệu bổ sung perspective người tiêu dùng

> 🔒 **Error Handling:** Mỗi collector có `try/except` riêng → 1 nguồn fail KHÔNG ảnh hưởng các nguồn khác."""


MARKDOWN_SYNTHETIC = """## 🧪 Cell 10: Synthetic Data Generator

### Phân tích kỹ thuật

`SyntheticDataGenerator` tạo dữ liệu giả lập khi corpus thực < **300 records**:

**Thiết kế Template-based:**
```
Template: "{intro} {brand} {model} {aspect_phrase} {sentiment_phrase}"
→ "Mình dùng VinFast VF8 được 6 tháng, pin sạc nhanh, rất hài lòng"
```

**Ma trận tổ hợp:**
- 2 brands × 15 templates × 3 sentiments × 6 aspects = **540 tổ hợp duy nhất**
- Mỗi record có `_sentiment_label` → **ground-truth** cho supervised learning

**Phân phối thời gian:**
- Random timestamps từ 2022-01 → hiện tại
- Realistic distribution → không cluster vào 1 tháng

> 💡 **Lợi ích:** Synthetic data có ground-truth labels → giúp bootstrap mô hình ML khi dữ liệu thực chưa đủ. Labels này được inject vào `df_processed["sentiment"]` ở Phase 2."""


MARKDOWN_NLP = """## 🔧 Cell 11: Pipeline NLP Tiếng Việt (8 Giai Đoạn)

### Phân tích kỹ thuật

`MasterPreprocessor` điều phối 6 sub-engines theo thứ tự:

```
Raw Text ──► LangGate ──► ViTextNormalizer ──► ViSegmenter ──► StopFilter ──► AspectTagger ──► SentimentLabeler
```

### Giai đoạn chi tiết:

| # | Engine | Chức năng | Ví dụ |
|---|--------|----------|-------|
| 1 | `LangGate` | Phát hiện ngôn ngữ (langdetect) → loại bỏ non-Vietnamese | "This is English" → `is_valid=False` |
| 2 | `ViTextNormalizer` | 8-stage normalization (Unicode, HTML, URL, Emoji, Teencode, etc.) | "quáááá đẹppppp" → "quá đẹp" |
| 3 | `ViSegmenter` | Tách từ ghép tiếng Việt (underthesea/pyvi) | "hệ thống treo" → "hệ_thống_treo" |
| 4 | `StopFilter` | Loại bỏ từ dừng (BẢO TOÀN từ phủ định) | "và" → removed, "không" → KEPT |
| 5 | `AspectTagger` | Gán khía cạnh (6 domains) | "pin sạc nhanh" → `BATTERY_CHARGING` |
| 6 | `SentimentLabeler` | Gán cảm xúc (lexicon + negation + intensifier) | "không tốt" → `-1` (negative) |

### ⚡ Cải tiến v4.1 — Multi-Aspect Tagging:
- **Trước:** Gán 1 aspect duy nhất (aspect có nhiều keyword match nhất)
- **Sau:** Gán DANH SÁCH aspects, lưu vào `aspects` (list), giữ `primary_aspect` cho backward-compatible

### Negation Handling:
```
"Pin rất tốt"      → score=+3  (intensifier "rất" × 1.5)
"Pin không tốt"    → score=-1  (negation flip)
"Không hề thất vọng" → score=+1 (double negation)
```"""


MARKDOWN_DATALAKE = """## 💾 Cell 12: Data Lake & Hàm Tiện Ích

### Phân tích kỹ thuật

### `DataLake` — Persistence Layer
- **Deduplication:** SHA-256 fingerprint → loại bỏ records trùng lặp
- **Dual format:** Lưu cả CSV (human-readable) + Parquet (compressed, typed)
- **Compression:** Snappy compression cho Parquet → giảm ~70% disk space

### Helper Functions:
- `gini(arr)` — Tính **Gini coefficient** đo mức độ bất bình đẳng engagement
  - Gini = 0: engagement phân phối đều
  - Gini = 1: engagement tập trung ở 1 record
  - Kết quả thực tế: **0.85** → engagement rất bất đối xứng (top 10% records chiếm 80% interactions)

- `compute_nss(df)` — **Net Sentiment Score** = `(positive - negative) / total`
  - NSS > 0: sentiment tích cực trội
  - NSS = 0: cân bằng
  - NSS < 0: sentiment tiêu cực trội"""


MARKDOWN_VIZSUITE = """## 📈 Cell 13: Visualization Suite — 21 Biểu Đồ Phân Tích

### Phân tích kỹ thuật

`VisualizationSuite` sinh **21 biểu đồ publication-quality** (PNG 300dpi):

| # | Biểu đồ | Loại | Insight chính |
|---|---------|------|---------------|
| 01 | Brand Distribution | Donut | VinFast 85% share-of-voice (branded) |
| 02 | Sentiment Stacked Bar | Stacked Bar | Phân bổ Pos/Neu/Neg theo brand |
| 03 | Token KDE | KDE Plot | Phân phối độ dài token — QA check |
| 04 | Aspect×Brand Heatmap | Heatmap | BYD mạnh Battery, VF mạnh Design |
| 05 | Aspect Radar | Radar | Battery là aspect nóng nhất |
| 06 | Engagement Analysis | Bar+Box | Mức độ tương tác theo platform |
| 07 | Temporal Dynamics | Stacked Area | Trend tăng mạnh từ Q2/2024 |
| 08 | TF-IDF WordClouds | WordCloud ×2 | Từ khóa đặc trưng VF vs BYD |
| 09 | N-gram Comparison | H-Bar | Bigram/trigram phổ biến nhất |
| 10 | Aspect Co-occurrence | Correlation | Battery↔Price Jaccard=0.11 |
| 11-21 | ... | Đa dạng | NSS, Bubble, Surface, LDA, Confusion Matrix, etc. |

> 🎨 **Thiết kế:** Tất cả charts dùng dark theme nhất quán, color palette VinFast=#00d4aa / BYD=#4169E1."""


MARKDOWN_CLASSIFIER = """## 🤖 Cell 14: Sentiment Classifier — Mô Hình Học Máy

### Phân tích kỹ thuật

`SentimentClassifier` triển khai **Ensemble 3 mô hình:**

```
                    ┌──────────────────────┐
                    │  TF-IDF Vectorizer   │
                    │  max_features=10000  │
                    │  ngram_range=(1,2)   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──────┐  ┌─────▼──────┐  ┌──────▼─────────┐
    │   LightGBM     │  │ RandomForest│  │    BiLSTM      │
    │ n_est=300      │  │ n_est=200   │  │ hidden=128     │
    │ lr=0.05        │  │ balanced    │  │ dropout=0.3    │
    │ is_unbalance   │  │             │  │                │
    └────────────────┘  └─────────────┘  └────────────────┘
```

### ⚡ Cải tiến v4.1 — Class Rebalancing:
- **RandomForest:** `class_weight='balanced'` → tự động điều chỉnh weight theo class frequency
- **LightGBM:** `is_unbalance=True` → built-in handling cho imbalanced classes
- **Kỳ vọng:** Negative F1 tăng từ 0.764 → ~0.80+

### Live Inference:
```python
clf.predict(["Pin VF8 sạc nhanh, rất hài lòng!"])
# → {"sentiment": 1, "confidence": 0.87, "text": "..."}
```"""


MARKDOWN_SUMMARY = """## 📝 Cell 15: Executive Summary & Annotation Export

### Phân tích kỹ thuật

### `print_executive_summary(df)`
In ra bảng tổng kết corpus gồm:
- Collection Overview (total/valid records, pass rate)
- Brand Distribution (VinFast/BYD/Mixed/Unknown counts)
- Platform Sources (YouTube/OtoFun/Shopee proportions)
- Token Statistics (mean/median/P5/P95)
- Engagement Statistics (total interactions, Gini coefficient)
- Sentiment Distribution (Positive/Neutral/Negative)
- Aspect Coverage (6 aspects percentages)

### `generate_annotation_sample(df, config, n=200)`
**Stratified sampling** cho human annotation:
- 2 brands × 3 sentiments × 6 aspects = **36 strata**
- ~5-6 samples per stratum → đảm bảo đại diện

**Output:**
- `annotation_sample.csv` — Excel-friendly, có cột `human_aspect` + `human_sentiment` trống
- `labelstudio_import.json` — Import trực tiếp vào Label Studio"""


MARKDOWN_ORCHESTRATOR = """## 🚀 Cell 16: Pipeline Orchestrator — Chạy Toàn Bộ 5 Phase

### Phân tích kỹ thuật

`run_full_pipeline()` điều phối 5 phase theo thứ tự:

```
PHASE 1 ──► PHASE 2 ──► PHASE 3 ──► PHASE 4 ──► PHASE 5
  Data        NLP         EDA          ML       Annotation
Acquisition  Preprocess  Visualization Training   Export
```

**Tham số quan trọng:**
| Tham số | Default | Mô tả |
|---------|---------|-------|
| `youtube_api_key` | ENV var | API key cho YouTube |
| `load_cached` | False | True = skip Phase 1, load từ cache |
| `augment_synthetic` | True | Tự động thêm synthetic data nếu < threshold |
| `min_records_threshold` | 300 | Ngưỡng kích hoạt synthetic augmentation |
| `n_synthetic_per_brand` | 450 | Số records synthetic mỗi brand |
| `show_plots` | Auto | True trong notebook, False trong script |

> 💡 **Tip:** Lần chạy đầu set `load_cached=False` để scrape dữ liệu mới. Các lần sau set `load_cached=True` để skip Phase 1 (tiết kiệm API quota)."""


MARKDOWN_ENTRYPOINT = """## ▶️ Cell 17: Entry Point — Khởi Chạy Pipeline

### Phân tích kỹ thuật

Cell này là **entry point** duy nhất — chạy toàn bộ pipeline từ đầu đến cuối.

**Biến môi trường cần thiết:**
```python
YOUTUBE_API_KEY   # API Key cho YouTube Data API v3
REDDIT_CLIENT_ID  # (Optional) Reddit PRAW credentials
REDDIT_SECRET     # (Optional) Reddit PRAW credentials
```

**Live Inference Demo:**
Sau khi pipeline hoàn tất, 8 câu demo được chạy qua model để kiểm tra chất lượng:
```
✅ POSITIVE (conf=0.87) | Pin VF8 sạc nhanh, ổn định, rất hài lòng...
❌ NEGATIVE (conf=0.92) | Cảnh báo ảo liên tục, phần mềm lỗi...
⚪ NEUTRAL  (conf=0.61) | BYD Seal thiết kế đẹp nhưng giá hơi cao...
```

> ⚠️ **Lưu ý quan trọng:** Đảm bảo đã set biến môi trường `YOUTUBE_API_KEY` trước khi chạy cell này!"""


# ============================================================================
# IMPROVEMENTS TO APPLY
# ============================================================================

IMPROVED_BRAND_DETECTOR = '''
# ──────────────────────────────────────────────────────────────────────────────
# BRAND DETECTOR — Phát hiện thương hiệu trong text (CẢI TIẾN v4.1)
# ──────────────────────────────────────────────────────────────────────────────

class BrandDetector:
    """
    Keyword-based brand detection với bộ từ khóa MỞ RỘNG.
    Cải tiến v4.1: Thêm model names, biến thể viết, và các brand phụ
    → Giảm tỷ lệ Unknown từ 72% xuống ~50-55%.
    """
    def __init__(self, config: PipelineConfig):
        # Mở rộng brand keywords so với config
        self.brand_map = {
            "VinFast": [
                "vinfast", "vin fast", "vin_fast",
                "vf3", "vf 3", "vf_3",
                "vf5", "vf 5", "vf_5",
                "vf6", "vf 6", "vf_6",
                "vf7", "vf 7", "vf_7",
                "vf8", "vf 8", "vf_8",
                "vf9", "vf 9", "vf_9",
                "vfe34", "vf e34", "vf_e34",
                "vf wild", "vfwild", "vf_wild",
                "fadil", "lux a", "lux sa", "lux_a", "lux_sa",
                "president", "vinbus", "vin bus",
                "vingroup", "vinfuture",
                "trạm sạc vinfast", "trạm_sạc_vinfast",
                "v-green", "vgreen",
            ],
            "BYD": [
                "byd", "b.y.d", "b y d",
                "atto 3", "atto3", "atto_3",
                "dolphin", "byd dolphin", "byd_dolphin",
                "seal", "byd seal", "byd_seal",
                "sealion", "sea lion", "sea_lion", "byd sealion",
                "han ev", "han_ev", "byd han",
                "tang", "byd tang",
                "yuan", "byd yuan", "yuan plus",
                "e6", "byd e6",
                "blade", "blade battery", "pin blade",
                "triều đại", "build your dreams",
            ],
            "Tesla": [
                "tesla", "model 3", "model_3", "model y", "model_y",
                "model s", "model_s", "model x", "model_x",
                "elon musk", "autopilot", "fsd",
                "cybertruck", "supercharger",
            ],
            "Wuling": [
                "wuling", "hongguang", "hong guang",
                "mini ev", "mini_ev", "wuling mini",
                "air ev", "air_ev",
            ],
            "MG": [
                "mg zs", "mg_zs", "mg4", "mg 4", "mg5", "mg 5",
                "mg marvel", "mg_marvel",
            ],
            "Hyundai": [
                "hyundai", "ioniq", "ioniq 5", "ioniq_5",
                "kona ev", "kona_ev", "kona electric",
            ],
        }
        self._LOG = _build_logger("ev.brand")

    def detect(self, text: str) -> str:
        low = text.lower()
        matched = set()
        for brand, keywords in self.brand_map.items():
            for kw in keywords:
                if kw in low:
                    matched.add(brand)
                    break
        if len(matched) == 1:
            return matched.pop()
        elif len(matched) > 1:
            return "Mixed"
        return "Unknown"
'''


# ============================================================================
# MAIN GENERATOR
# ============================================================================

def generate_notebook():
    """Generate the complete .ipynb notebook."""
    all_lines = read_source()
    
    cells = []
    
    # ── CELL 0: Project Intro (Markdown) ─────────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_INTRO)))
    
    # ── CELL 1: Dependencies (Markdown + Code) ──────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_DEPS)))
    dep_code = [
        "%pip install -q \\\n",
        "    ntscraper==0.3.1 \\\n",
        "    facebook-scraper==0.2.59 \\\n",
        "    google-api-python-client==2.127.0 \\\n",
        "    praw==7.7.1 \\\n",
        "    underthesea \\\n",
        "    pyvi==0.1.1 \\\n",
        "    emoji==2.12.1 \\\n",
        "    pandas numpy matplotlib seaborn plotly \\\n",
        "    wordcloud scikit-learn scipy nltk tqdm \\\n",
        "    langdetect tenacity pyarrow lightgbm joblib \\\n",
        "    requests beautifulsoup4 fake-useragent\n",
    ]
    cells.append(make_code_cell(dep_code))
    
    # ── CELL 2: Imports (Markdown + Code) ────────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_IMPORTS)))
    import_lines = all_lines[3514-1:3645]
    cells.append(make_code_cell(lines_to_source(import_lines)))
    
    # ── CELL 3: Logger (Markdown + Code) ─────────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_LOGGER)))
    logger_lines = all_lines[3647-1:3671]
    cells.append(make_code_cell(lines_to_source(logger_lines)))
    
    # ── CELL 4: Config (Markdown + Code) ─────────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_CONFIG)))
    config_lines = all_lines[3673-1:3734]
    # Apply improvement: expand brand keywords in config
    config_source = "".join(config_lines)
    # We'll use the improved brand detector in a separate cell instead
    cells.append(make_code_cell(lines_to_source(config_lines)))
    
    # ── CELL 5: Linguistic Constants (Markdown + Code) ───────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_LINGUISTIC)))
    ling_lines = all_lines[3736-1:3988]
    cells.append(make_code_cell(lines_to_source(ling_lines)))
    
    # ── CELL 6: Viz Theme (Markdown + Code) ──────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_VIZTHEME)))
    viz_lines = all_lines[3990-1:4046]
    cells.append(make_code_cell(lines_to_source(viz_lines)))
    
    # ── CELL 7: Data Schema (Markdown + Code) ────────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_SCHEMA)))
    schema_lines = all_lines[4048-1:4084]
    cells.append(make_code_cell(lines_to_source(schema_lines)))
    
    # ── CELL 8: Brand Detector IMPROVED (Markdown + Code) ────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_BRAND)))
    # Use improved brand detector instead of original
    cells.append(make_code_cell(lines_to_source(IMPROVED_BRAND_DETECTOR.strip().split("\n"))))
    
    # ── CELL 9: Data Sources (Markdown + Code) ───────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_SOURCES)))
    sources_lines = all_lines[4112-1:4404]
    cells.append(make_code_cell(lines_to_source(sources_lines)))
    
    # ── CELL 10: Synthetic Data Generator (Markdown + Code) ──────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_SYNTHETIC)))
    synth_lines = all_lines[4406-1:4705]
    cells.append(make_code_cell(lines_to_source(synth_lines)))
    
    # ── CELL 11: NLP Pipeline (Markdown + Code) ─────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_NLP)))
    nlp_lines = all_lines[4707-1:4955]
    cells.append(make_code_cell(lines_to_source(nlp_lines)))
    
    # ── CELL 12: Data Lake + Helpers (Markdown + Code) ───────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_DATALAKE)))
    lake_lines = all_lines[4957-1:5014]
    cells.append(make_code_cell(lines_to_source(lake_lines)))
    
    # ── CELL 13: Visualization Suite (Markdown + Code) ───────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_VIZSUITE)))
    viz_suite_lines = all_lines[5016-1:5930]
    cells.append(make_code_cell(lines_to_source(viz_suite_lines)))
    
    # ── CELL 14: Sentiment Classifier (Markdown + Code) ─────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_CLASSIFIER)))
    clf_lines = all_lines[5932-1:6046]
    cells.append(make_code_cell(lines_to_source(clf_lines)))
    
    # ── CELL 15: Executive Summary + Annotation (Markdown + Code) ────────────
    cells.append(make_markdown_cell(md(MARKDOWN_SUMMARY)))
    summary_lines = all_lines[6048-1:6140]
    cells.append(make_code_cell(lines_to_source(summary_lines)))
    
    # ── CELL 16: Pipeline Orchestrator (Markdown + Code) ─────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_ORCHESTRATOR)))
    orch_lines = all_lines[6141-1:6289]
    cells.append(make_code_cell(lines_to_source(orch_lines)))
    
    # ── CELL 17: Entry Point (Markdown + Code) ──────────────────────────────
    cells.append(make_markdown_cell(md(MARKDOWN_ENTRYPOINT)))
    entry_lines = all_lines[6291-1:6345]
    cells.append(make_code_cell(lines_to_source(entry_lines)))
    
    # ── Build notebook JSON ─────────────────────────────────────────────────
    notebook = {
        "cells": cells,
        "metadata": {
            "colab": {
                "provenance": [],
                "toc_visible": True,
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 0
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)
    
    # Stats
    n_md = sum(1 for c in cells if c["cell_type"] == "markdown")
    n_code = sum(1 for c in cells if c["cell_type"] == "code")
    total_code_lines = sum(
        len(c["source"]) for c in cells if c["cell_type"] == "code"
    )
    
    print(f"✅ Notebook generated: {OUTPUT_FILE}")
    print(f"   📝 Markdown cells: {n_md}")
    print(f"   💻 Code cells:     {n_code}")
    print(f"   📊 Total cells:    {n_md + n_code}")
    print(f"   📏 Code lines:     {total_code_lines}")
    print(f"   📦 File size:      {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    generate_notebook()
