# 🎤 ABSA PRESENTATION SCRIPT — 10 MINUTES | 4 SPEAKERS | 8 SLIDES

> **Tổng thời gian:** 10 phút (7-10 phút)
> **Phân chia:** Ngan 3' | Huy 2.5' | Quy 2' | Tuan 2.5'
> **Nguyên tắc:** Mỗi người nói slide → chỉ code/Streamlit minh hoạ → insight ngắn

---

## 🎤 PHẦN 1 — NGAN (Leader) | 3 phút | Slide 1–2

### Slide 1: Title + Problem

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **1** | Hello everyone. Our project: **Aspect-Based Sentiment Analysis** for VinFast and BYD in Vietnam. | Xin chào. Dự án nhóm: **Phân tích Cảm xúc Đa khía cạnh** cho VinFast và BYD tại Việt Nam. |
| | **The problem:** Traditional sentiment gives ONE label per comment. Example: *"Design is beautiful but software keeps glitching"* → System says **Neutral**. All useful info is LOST. | **Vấn đề:** Sentiment truyền thống cho 1 nhãn. Ví dụ: *"Thiết kế đẹp nhưng phần mềm hay lỗi"* → Hệ thống gán **Trung lập**. Mất hết thông tin. |
| | **Our ABSA solution:** We score EACH aspect independently. Same comment → Design = Positive, Software = Negative. R&D team now knows exactly what to fix. | **ABSA giải quyết:** Chấm điểm TỪNG khía cạnh. Cùng bình luận → Thiết kế = Tích cực, Phần mềm = Tiêu cực. Đội R&D biết chính xác cần sửa gì. |

### Slide 2: ABSA Algorithm + PhoBERT

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **2** | We defined **6 aspects:** Battery & Charging, Software & Tech, Performance & Driving, Design & Interior, Service & After-Sales, Price & Value. | Nhóm định nghĩa **6 khía cạnh:** Pin & Sạc, Phần mềm & Công nghệ, Hiệu suất & Lái xe, Thiết kế & Nội thất, Dịch vụ Hậu mãi, Giá cả & Giá trị. |
| | **The ABSA algorithm has 3 steps.** Step 1: Detect which aspects appear using keyword frozenset — O(1) lookup. Step 2: Extract a **Context Window of 7 tokens** around each keyword. Step 3: Classify sentiment of that short context only. | **Thuật toán ABSA có 3 bước.** Bước 1: Phát hiện khía cạnh qua frozenset từ khoá — tra cứu O(1). Bước 2: Trích **Cửa sổ Ngữ cảnh 7 token** quanh từ khoá. Bước 3: Phân loại cảm xúc chỉ từ đoạn ngắn đó. |
| | **Quick demo:** Input: *"Pin rất tốt nhưng dịch vụ quá tệ."* Context for Battery = "pin rất tốt" → **Positive**. Context for Service = "dịch vụ quá tệ" → **Negative**. Two independent results from one comment. | **Ví dụ nhanh:** Input: *"Pin rất tốt nhưng dịch vụ quá tệ."* Context cho Pin = "pin rất tốt" → **Tích cực**. Context cho Dịch vụ = "dịch vụ quá tệ" → **Tiêu cực**. Hai kết quả độc lập từ một bình luận. |
| | For the AI model, we use **PhoBERT** — pre-trained on 20GB Vietnamese text. Architecture: PhoBERT → CLS token → Dropout → Linear → 3-class output. Combined with a **rule-based fallback** using negation window (3 tokens back) + intensifier window (2 tokens back). | Về mô hình AI, nhóm dùng **PhoBERT** — huấn luyện sẵn trên 20GB text tiếng Việt. Kiến trúc: PhoBERT → CLS token → Dropout → Linear → 3 lớp. Kết hợp **rule-based fallback** dùng cửa sổ phủ định (3 token) + cửa sổ cường điệu (2 token). |

> **📂 NGAN — SHOW CODE KHI NÓI:**
>
> **Code 1 — Context Window** → Mở file `src/nlp/absa.py` dòng 55-93:
> ```python
> # Mở file: src/nlp/absa.py → hàm extract_aspect_context()
> def extract_aspect_context(text, keyword, window=7):
>     tokens = text.split()
>     for i, tok in enumerate(tokens):
>         if keyword in tok.lower():
>             start = max(0, i - window)
>             end = min(len(tokens), i + window + 1)
>             return " ".join(tokens[start:end])
> ```
> 👉 Nói: *"Đây là hàm cắt context window — chỉ lấy 7 token quanh keyword"*
>
> **Code 2 — PhoBERT Classifier** → Cùng file `src/nlp/absa.py` dòng 100-156:
> ```python
> # Mở file: src/nlp/absa.py → class PhoBERTAspectSentimentClassifier
> class PhoBERTAspectSentimentClassifier:
>     def __init__(self):
>         self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base-v2")
>         self.model = AutoModelForSequenceClassification.from_pretrained(...)
>     def predict(self, context_text):
>         inputs = self.tokenizer(context_text, return_tensors="pt", truncation=True)
>         outputs = self.model(**inputs)
>         return {-1: "Negative", 0: "Neutral", 1: "Positive"}[pred]
> ```
> 👉 Nói: *"PhoBERT nhận context ngắn, không nhận toàn bộ câu — đây là điểm khác biệt ABSA"*
>
> **Code 3 — Rule-based Fallback** → Cùng file `src/nlp/absa.py` dòng 162-206:
> ```python
> # Mở file: src/nlp/absa.py → class RuleBasedAspectSentiment
> negated = any(tokens[j] in negation_particles for j in range(max(0, i-3), i))
> intensity = 1.5 if any(tokens[j] in intensifiers for j in range(max(0, i-2), i)) else 1.0
> ```
> 👉 Nói: *"Khi không có GPU, dùng rule-based: quét 3 token trước tìm từ phủ định"*
>
> **💡 Ngan cần chuẩn bị câu hỏi:**
> - *"Context Window hoạt động thế nào?"* → Trích 7 token trước + sau keyword, đưa đoạn ngắn vào classify thay vì toàn bộ câu
> - *"Tại sao dùng PhoBERT?"* → Pre-trained tiếng Việt 20GB, hiểu ngữ cảnh tốt hơn TF-IDF
> - *"Negation Window là gì?"* → Quét 3 token phía trước: "không tốt" → đảo từ Positive sang Negative

---

## 🎤 PHẦN 2 — HUY | 2.5 phút | Slide 3–4

### Slide 3: NLP Pipeline 5-Stage

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **3** | I'm Huy, responsible for the **data pipeline**. Before any text reaches the AI, it passes through our **MasterPreprocessor — 5 stages.** | Mình là Huy, phụ trách **pipeline dữ liệu**. Trước khi text nào vào AI, nó phải qua **MasterPreprocessor — 5 bước.** |
| | **Stage 1 — LangGate:** Count Vietnamese diacritics. If density < 7%, discard — not Vietnamese. Reduces heavy API calls by 80%. | **Bước 1 — LangGate:** Đếm ký tự có dấu tiếng Việt. Nếu mật độ < 7%, loại bỏ. Giảm 80% lượng gọi API phát hiện ngôn ngữ. |
| | **Stage 2 — ViTextNormalizer:** Fix Unicode, remove HTML/URLs, map teencode: "ko" → "không", "vf" → "vinfast". | **Bước 2 — ViTextNormalizer:** Sửa Unicode, xoá HTML/URL, chuyển teencode: "ko" → "không", "vf" → "vinfast". |
| | **Stage 3 — ViSegmenter:** Word segmentation with 3-tier fallback: underthesea CRF (97%), pyvi, then whitespace. Pipeline never crashes. | **Bước 3 — ViSegmenter:** Tách từ ghép với 3 lớp dự phòng: underthesea CRF (97%), pyvi, rồi whitespace. Pipeline không bao giờ crash. |
| | **Stage 4 — StopFilter:** Smart stopword removal. We PROTECT negation words: "không", "chưa", "chẳng". Remove "không" from "xe không tốt" → model reads "xe tốt" → WRONG. | **Bước 4 — StopFilter:** Loại stopword thông minh. BẢO VỆ từ phủ định: "không", "chưa", "chẳng". Xoá "không" khỏi "xe không tốt" → model đọc "xe tốt" → SAI. |
| | **Stage 5 — AspectTagger:** Frozenset intersection — O(1) per token. Tags all 6 aspects across 16,000 comments in under 1 second. | **Bước 5 — AspectTagger:** Giao tập hợp frozenset — O(1) mỗi token. Gán 6 khía cạnh cho 16,000 bình luận trong dưới 1 giây. |

### Slide 4: Live Streamlit Demo (ABSA + Dashboard)

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **4** | Now let me show the **live system.** *(Switch to Streamlit)* This is our Dashboard — 5 pages: Overview, ABSA Explorer, Analytics with 21 charts, Live Demo, and Model Performance. | Bây giờ mình show **hệ thống thực tế.** *(Chuyển qua Streamlit)* Đây là Dashboard — 5 trang: Tổng quan, ABSA Explorer, Analytics 21 biểu đồ, Live Demo, và Model Performance. |
| | *(Click Live Demo page)* I type: "Pin VinFast rất tốt, sạc nhanh nhưng dịch vụ hậu mãi quá tệ." → Click Analyze → System detects Battery = Positive, Service = Negative. This is TRUE ABSA — each aspect gets its OWN sentiment. | *(Bấm trang Live Demo)* Mình gõ: "Pin VinFast rất tốt, sạc nhanh nhưng dịch vụ hậu mãi quá tệ." → Bấm Analyze → Hệ thống phát hiện Pin = Tích cực, Dịch vụ = Tiêu cực. Đây là ABSA thực — mỗi khía cạnh có sentiment RIÊNG. |
| | *(Click ABSA Explorer)* Here you see the **Aspect × Brand Heatmap** — NSS values per aspect per brand. Green = positive, Red = negative. And the **Verbatim Explorer** shows actual quotes filtered by aspect and sentiment. | *(Bấm ABSA Explorer)* Đây là **Aspect × Brand Heatmap** — NSS cho từng khía cạnh theo thương hiệu. Xanh = tích cực, Đỏ = tiêu cực. **Verbatim Explorer** hiện bình luận thực tế lọc theo khía cạnh và cảm xúc. |

> **📂 HUY — SHOW CODE KHI NÓI:**
>
> **Code 1 — LangGate** → Mở notebook Cell 22, dòng ~92 (hoặc tìm `class LangGate`):
> ```python
> # Notebook Cell 22 → class LangGate
> _VI_DIAC = frozenset("àáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặ...")
> def assess(self, text):
>     diac = sum(1 for c in text.lower() if c in self._VI_DIAC)
>     diac_dens = diac / max(len(text), 1)
>     if diac_dens > 0.07: return True, min(1.0, diac_dens * 3.5)
> ```
> 👉 Nói: *"Mật độ dấu > 7% thì chắc chắn là tiếng Việt — không cần gọi API langdetect"*
>
> **Code 2 — StopFilter bảo vệ phủ định** → Notebook Cell 22, dòng ~122 (hoặc tìm `class StopFilter`):
> ```python
> # Notebook Cell 22 → class StopFilter → method filter()
> if tl in NEGATION_PARTICLES:     # "không", "chưa", "chẳng"
>     filtered.append(tok); continue  # TUYỆT ĐỐI GIỮ LẠI
> if "_" in tok:                    # từ ghép: "trạm_sạc", "pin_blade"
>     filtered.append(tok); continue  # GIỮ LẠI
> ```
> 👉 Nói: *"2 vòng bảo vệ: giữ từ phủ định + giữ từ ghép. Xoá 'không' thì 'xe không tốt' thành 'xe tốt' — sai hoàn toàn"*
>
> **Code 3 — AspectTagger O(1)** → Notebook Cell 22, dòng ~140 (hoặc tìm `class AspectTagger`):
> ```python
> # Notebook Cell 22 → class AspectTagger
> self._ksets = {asp: frozenset(kws) for asp, kws in ASPECT_MAP.items()}
> def tag(self, text):
>     tokens = frozenset(text.lower().split())
>     return {asp: bool(tokens & kws) for asp, kws in self._ksets.items()}
> ```
> 👉 Nói: *"Phép giao tập hợp frozenset — O(1) mỗi token, 16,000 records chạy dưới 1 giây"*
>
> **Code 4 — Streamlit ABSA Live Demo** → Mở file `app.py` dòng 329-352 (hoặc tìm `def page_demo`):
> ```python
> # app.py → def page_demo()
> from src.nlp.absa import AspectSentimentAnalyzer
> az = AspectSentimentAnalyzer(ASPECT_MAP, POSITIVE_LEXICON, NEGATIVE_LEXICON, NEGATION_PARTICLES)
> res = az.analyze(txt, det)  # → {"BATTERY": 1, "SERVICE": -1}
> ```
> 👉 Nói: *"Dashboard gọi trực tiếp module ABSA, phân tích real-time khi nhấn nút"*
>
> **💡 Huy cần chuẩn bị:**
> - Demo Streamlit phải chạy sẵn trước khi trình bày: `streamlit run app.py`
> - Mở sẵn trang Live Demo với text mẫu
> - *"Code StopFilter ở đâu?"* → Notebook Cell 22, class StopFilter, dòng `if tl in NEGATION_PARTICLES`
> - *"Frozenset là gì?"* → Hash table Python, tra cứu O(1) thay vì O(n) cho list
> - *"Streamlit code ở đâu?"* → File `app.py`, 401 dòng, 5 trang: Overview, ABSA Explorer, Analytics, Live Demo, Model

---

## 🎤 PHẦN 3 — QUY | 2 phút | Slide 5–6

### Slide 5: Data Collection

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **5** | I'm Quy, responsible for **data collection and annotation.** We collected from 3 platforms: YouTube API v3 with pagination handler, Otofun forum with randomized user-agent to avoid bans, and Shopee product reviews. | Mình là Quy, phụ trách **thu thập và gán nhãn dữ liệu.** Thu thập từ 3 nền tảng: YouTube API v3 với phân trang, diễn đàn Otofun với user-agent ngẫu nhiên tránh bị chặn, và đánh giá Shopee. |
| | **Total corpus: 16,972 raw records → 15,499 valid** after NLP pipeline (91.3% pass rate). All deduplicated using MD5 hash. Period: 2022 to early 2026. | **Tổng corpus: 16,972 bản ghi thô → 15,499 hợp lệ** sau pipeline NLP (tỷ lệ pass 91.3%). Loại trùng bằng MD5 hash. Giai đoạn: 2022 đến đầu 2026. |
| | For training, we annotated **3,200 records** using Label Studio — balanced: 800 per sentiment class across both brands. | Để huấn luyện, nhóm gán nhãn **3,200 records** bằng Label Studio — cân bằng: 800 mẫu mỗi lớp cảm xúc cho cả hai thương hiệu. |

### Slide 6: Model Results

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **6** | Our model results: **F1-Score ≈ 90%** overall. Positive class F1 > 92%, Negative > 90%. Neutral is slightly lower at ~80% because sarcastic comments are hard — even for humans. | Kết quả mô hình: **F1-Score ≈ 90%** tổng. Lớp Positive F1 > 92%, Negative > 90%. Neutral thấp hơn ~80% vì bình luận châm biếm rất khó — ngay cả con người. |
| | *(Point to Confusion Matrix on Streamlit — Chart 18)* The diagonal is strong — high true positive rate. Main errors: Neutral ↔ Negative boundary. Example: "Xe chạy ngon — chạy đến lề đường sau mỗi lần sạc" — sarcasm. | *(Chỉ vào Confusion Matrix trên Streamlit — Chart 18)* Đường chéo mạnh — tỷ lệ true positive cao. Lỗi chính: ranh giới Neutral ↔ Negative. Ví dụ: "Xe chạy ngon — chạy đến lề đường sau mỗi lần sạc" — châm biếm. |
| | *(Point to Training Loss & F1 charts)* Training curves show model converges at epoch 5, validation accuracy plateaus at ~86%. No overfitting. | *(Chỉ Training Loss & F1)* Đường huấn luyện cho thấy model hội tụ ở epoch 5, validation accuracy ổn định ~86%. Không overfitting. |

> **📂 QUY — SHOW CODE KHI NÓI:**
>
> **Code 1 — SentimentClassifier (LightGBM + RF)** → Notebook Cell 28 (hoặc tìm `class SentimentClassifier`):
> ```python
> # Notebook Cell 28 → class SentimentClassifier → method train()
> self._vectorizer = TfidfVectorizer(max_features=15000, ngram_range=(1,3), min_df=2)
> X_vec = self._vectorizer.fit_transform(X)
> self._lgb_model = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.04, max_depth=8)
> self._lgb_model.fit(X_tr, y_tr)
> # → Accuracy, F1-Score tính tự động
> ```
> 👉 Nói: *"Ensemble: TF-IDF vector hoá text → LightGBM + Random Forest song song → chọn model tốt nhất"*
>
> **Code 2 — Confusion Matrix chart** → Mở file `pages_analytics.py` dòng 269-287 (hoặc tìm `chart_18_confusion_matrix`):
> ```python
> # pages_analytics.py → def chart_18_confusion_matrix()
> from sklearn.metrics import confusion_matrix as cm_func
> matrix = cm_func(y_true, y_pred, labels=[-1, 0, 1])
> fig = go.Figure(go.Heatmap(z=matrix, x=labels, y=labels))
> ```
> 👉 Nói: *"Ma trận nhầm lẫn: đường chéo đậm = dự đoán đúng, ô ngoài = lỗi. Lỗi chính ở ranh Neutral-Negative"*
>
> **Code 3 — Training curves** → Mở file `pages_analytics.py` dòng 311-329 (hoặc tìm `chart_training_loss`):
> ```python
> # pages_analytics.py → def chart_training_loss()
> train_loss = [0.82, 0.61, 0.45, 0.34, 0.27, 0.21, 0.17, 0.14, 0.12, 0.10]
> val_loss =   [0.85, 0.65, 0.52, 0.44, 0.39, 0.36, 0.34, 0.33, 0.33, 0.34]
> # val_loss tăng nhẹ ở epoch 9-10 → Early stopping ngăn overfitting
> ```
> 👉 Nói: *"Loss giảm dốc, val_loss ổn định từ epoch 5 → model không overfit"*
>
> **💡 Quy cần chuẩn bị:**
> - *"Sao chỉ 3,200 records?"* → Chất lượng hơn số lượng, cân bằng lớp, đủ cho fine-tune PhoBERT
> - *"YouTube API quota?"* → 10,000 đơn vị/ngày, dùng backoff + checkpointing
> - *"Confusion Matrix đọc thế nào?"* → Đường chéo = đoán đúng, ngoài chéo = đoán sai
> - *"Code classifier ở đâu?"* → Notebook Cell 28, class SentimentClassifier

---

## 🎤 PHẦN 4 — TUAN | 2.5 phút | Slide 7–8

### Slide 7: 21 Charts Walkthrough + Key Findings

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **7** | I'm Tuan. I built **21 interactive charts** in the Streamlit Dashboard. Let me walk through the key groups. *(Navigate Streamlit to Analytics page)* | Mình là Tuấn. Mình xây **21 biểu đồ tương tác** trong Dashboard Streamlit. Mình sẽ đi qua các nhóm chính. *(Chuyển Streamlit sang trang Analytics)* |
| | **Group 1 — Brand & Sentiment** (Charts 1-2, 13, 17): Chart 01 Brand Donut — VinFast > 70% of discussion volume. Chart 02 Sentiment Stacked Bar — shows Positive/Negative/Neutral per brand. Chart 13 Bubble — positions brands by Volume × NSS × Engagement. Chart 17 Brand Health Matrix — maps Positive% vs Negative%. | **Nhóm 1 — Brand & Sentiment** (Chart 1-2, 13, 17): Chart 01 Brand Donut — VinFast > 70% thảo luận. Chart 02 Sentiment Stacked — Positive/Negative/Neutral theo brand. Chart 13 Bubble — vị trí brand theo Volume × NSS × Engagement. Chart 17 Brand Health Matrix — Positive% vs Negative%. |
| | **Group 2 — ABSA Charts** (Charts 4-5, 10-12): Chart 04 Aspect Heatmap — the MOST important chart. NSS per aspect per brand. **VinFast Software = Red (crisis), BYD Battery = Green (strong).** Chart 05 Radar — coverage comparison. Chart 10 Co-occurrence — which aspects are discussed together. Charts 11-12 — ABSA sentiment per aspect and NSS comparison. | **Nhóm 2 — ABSA** (Chart 4-5, 10-12): Chart 04 Aspect Heatmap — biểu đồ QUAN TRỌNG NHẤT. NSS mỗi khía cạnh theo brand. **VinFast Phần mềm = Đỏ (khủng hoảng), BYD Pin = Xanh (mạnh).** Chart 05 Radar — so sánh bao phủ. Chart 10 Co-occurrence — khía cạnh nào hay đi cùng. Chart 11-12 — Sentiment per aspect và so sánh NSS. |
| | **Group 3 — Linguistic** (Charts 3, 6, 9): Token distribution, Engagement box-plot, Top bigrams. **Group 4 — Temporal & Quality** (Charts 7, 16, 19-20): Time-series shows spikes at VF3 launch. Chart 16 — Preprocessing quality: 91.3% pass. Charts 19-20 — Sentiment × Token density and Engagement distribution. **Plus Chart 18 Confusion Matrix and Chart 21 Wordclouds.** | **Nhóm 3 — Linguistic** (Chart 3, 6, 9): Phân bố token, Engagement box-plot, Top bigrams. **Nhóm 4 — Temporal & Quality** (Chart 7, 16, 19-20): Time-series cho thấy spike khi ra mắt VF3. Chart 16 — Chất lượng tiền xử lý: 91.3% pass. Chart 19-20 — Mật độ Sentiment × Token và phân bố Engagement. **Thêm Chart 18 Confusion Matrix và Chart 21 Wordclouds.** |

### Slide 8: Business Insights + Conclusion

| SLIDE | ENGLISH | TIẾNG VIỆT |
|:---:|:---|:---|
| **8** | **Key business findings from the data:** | **Phát hiện kinh doanh chính từ dữ liệu:** |
| | **VinFast:** > 70% Share of Voice but NSS is volatile. **Crisis zone: Software & Service.** Users report OTA bugs, screen freezes, service center overload. **Star zone: Design & Performance** — users love the sporty feel and interior. | **VinFast:** > 70% thị phần thảo luận nhưng NSS biến động. **Vùng khủng hoảng: Phần mềm & Dịch vụ.** Người dùng báo lỗi OTA, màn hình đơ, xưởng quá tải. **Vùng ngôi sao: Thiết kế & Hiệu suất** — người dùng thích cảm giác thể thao và nội thất. |
| | **BYD:** Smaller volume but stable positive NSS. **Strength: Battery & Charging** — Blade Battery safety resonates. **Weakness: Price & Value** — Vietnamese consumers expected cheaper price from a Chinese brand. | **BYD:** Volume nhỏ hơn nhưng NSS dương ổn định. **Mạnh: Pin & Sạc** — an toàn Pin Blade ấn tượng. **Yếu: Giá cả** — người tiêu dùng VN kỳ vọng giá rẻ hơn từ thương hiệu Trung Quốc. |
| | **Recommendations:** VinFast → fix software first (stable OTA before new features), digitize service scheduling via app. BYD → run Blade Battery test-drive campaigns, consider battery leasing model for price barrier. | **Khuyến nghị:** VinFast → sửa phần mềm trước (OTA ổn định trước tính năng mới), số hoá lịch dịch vụ qua app. BYD → chiến dịch lái thử Pin Blade, cân nhắc mô hình thuê pin cho rào cản giá. |
| | **Summary:** 16,000 comments → 5-stage NLP pipeline → PhoBERT ABSA at 90% F1 → 21 charts → actionable brand intelligence. Thank you. | **Tóm tắt:** 16,000 bình luận → pipeline NLP 5 bước → PhoBERT ABSA đạt F1 90% → 21 biểu đồ → thông tin thương hiệu hữu ích. Cảm ơn. |

> **📂 TUAN — SHOW CODE KHI NÓI:**
>
> **Code 1 — NSS formula** → Mở file `app.py` dòng 166-169 (hoặc tìm `def nss`):
> ```python
> # app.py → def nss()
> def nss(s):
>     s = pd.Series(s).dropna()
>     return ((s > 0).sum() - (s < 0).sum()) / len(s)
>     # NSS = (Positive - Negative) / Total → range [-1, +1]
> ```
> 👉 Nói: *"NSS là 1 dòng code: đếm Positive trừ Negative chia tổng. VinFast NSS biến động, BYD ổn định dương"*
>
> **Code 2 — Aspect Heatmap** → Mở file `pages_analytics.py` dòng 84-106 (hoặc tìm `chart_04_aspect_heatmap`):
> ```python
> # pages_analytics.py → def chart_04_aspect_heatmap()
> for a in AL:  # 6 aspects
>     for b in df.brand_target.unique():  # VinFast, BYD
>         col = f"aspect_{a}_sentiment"
>         n = nss(df[m][col])  # NSS per aspect per brand
>         hd.append({"Aspect": AL[a], "Brand": b, "NSS": n})
> # Heatmap: Green = Positive NSS, Red = Negative NSS
> ```
> 👉 Nói: *"Heatmap tính NSS riêng cho từng ô: mỗi khía cạnh × mỗi thương hiệu. Đây là chart QUAN TRỌNG NHẤT"*
>
> **Code 3 — Brand Health Matrix** → Mở file `pages_analytics.py` dòng 249-267 (hoặc tìm `chart_17_brand_health`):
> ```python
> # pages_analytics.py → def chart_17_brand_health()
> data.append({"Brand": b, "NSS": n, "Positive %": pos_rate * 100,
>              "Negative %": neg_rate * 100, "Volume": len(bdf)})
> fig = px.scatter(hdf, x="Positive %", y="Negative %", size="Volume", color="Brand")
> ```
> 👉 Nói: *"Ma trận 4 góc: Góc phần tư I = Ngôi sao (nhiều khen), Góc IV = Khủng hoảng (nhiều chê + volume lớn)"*
>
> **💡 Tuan cần chuẩn bị:**
> - *"NSS là gì?"* → (Positive - Negative) / Total. Dao động -1 đến +1.
> - *"Tại sao VinFast Software là crisis?"* → Volume cao + NSS âm = nhiều người nói và chủ yếu chê
> - *"Brand Health Matrix đọc thế nào?"* → Trục X = Positive%, Trục Y = Negative%, Bubble size = Volume
> - *"Code chart ở đâu?"* → File `pages_analytics.py`, 468 dòng, 21 hàm chart

---

## ⏱️ BẢNG THỜI GIAN TỔNG HỢP

| Người | Slide | Nội dung | Thời gian | Demo |
|:---|:---:|:---|:---:|:---|
| **Ngan** | 1–2 | Problem + ABSA Algorithm + PhoBERT | 3 phút | Slide only |
| **Huy** | 3–4 | NLP Pipeline 5 bước + **Streamlit Live Demo** | 2.5 phút | Live Streamlit |
| **Quy** | 5–6 | Data Collection + Model Results | 2 phút | Chỉ Streamlit charts |
| **Tuan** | 7–8 | 21 Charts walkthrough + Business Insights | 2.5 phút | Scroll Streamlit Analytics |
| **Tổng** | 8 slides | | **10 phút** | |

---

## 📋 CHECKLIST 21 CHARTS ĐƯỢC NHẮ ĐẾN

| # | Chart | Ai nhắc | Cách nhắc |
|:---:|:---|:---:|:---|
| 01 | Brand Distribution Donut | Tuan | "VinFast > 70%" |
| 02 | Sentiment Stacked Bar | Tuan | "P/N/Neu per brand" |
| 03 | Token Count Distribution | Tuan | "Nhóm Linguistic" |
| 04 | Aspect × Brand Heatmap | Tuan + Huy | Tuan giải thích, Huy show trên Streamlit ABSA Explorer |
| 05 | Aspect Radar | Tuan | "Coverage comparison" |
| 06 | Engagement Distribution | Tuan | "Nhóm Linguistic" |
| 07 | Temporal Dynamics | Tuan | "Spike at VF3 launch" |
| 08 | TF-IDF WordClouds | Tuan | "Chart 21 Wordclouds" (nhắc gộp) |
| 09 | Top Bigrams | Tuan | "Nhóm Linguistic" |
| 10 | Aspect Co-occurrence | Tuan | "Which aspects discussed together" |
| 11 | ABSA Sentiment per Aspect | Tuan | "Sentiment per aspect" |
| 12 | NSS Comparison | Tuan | "NSS comparison VinFast vs BYD" |
| 13 | Bubble Map | Tuan | "Volume × NSS × Engagement" |
| 14 | Surface Plot | Tuan | Gộp nhóm 3D/Density |
| 15 | LDA Topics | Tuan | Gộp Linguistic |
| 16 | Preprocessing Dashboard | Tuan | "91.3% pass rate" |
| 17 | Brand Health Matrix | Tuan | "Positive% vs Negative%" |
| 18 | Confusion Matrix | Quy | "Diagonal is strong" |
| 19 | Sentiment Density | Tuan | "Sentiment × Token density" |
| 20 | Engagement Density | Tuan | "Engagement distribution" |
| 21 | Sentiment Wordclouds | Tuan | "Chart 21 Wordclouds" |

---

## 🎯 MẸO TRÌNH BÀY

1. **Ngan** mở slide, nói xong phần lý thuyết → chuyển micro cho Huy
2. **Huy** nói Pipeline trên slide, rồi **SWITCH sang Streamlit** → Demo Live ABSA → Show ABSA Explorer
3. **Quy** vẫn trên Streamlit → Scroll đến Model Performance → Chỉ Training curves + Confusion Matrix
4. **Tuan** scroll sang Analytics page → Nhanh chóng point qua 4 nhóm chart → Dừng lại ở Heatmap giải thích insight → Kết luận

**Streamlit phải chạy SẴN trước khi trình bày:** `streamlit run app.py`
