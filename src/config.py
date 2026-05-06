"""
Pipeline Configuration & Linguistic Constants
================================================
Extracted from EV_Sentiment_Analysis_VinFast_vs_BYD.ipynb (v5.2)

All constants, aspect maps, lexicons, and configuration in one module.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PipelineConfig:
    # ── API Keys ──────────────────────────────────────────────────────────────
    youtube_api_key:      str = os.environ.get("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY")
    reddit_client_id:     str = os.environ.get("REDDIT_CLIENT_ID", "")
    reddit_client_secret: str = os.environ.get("REDDIT_SECRET", "")
    reddit_user_agent:    str = "ev_sentiment_bot/5.2 by u/ev_researcher"

    # ── Collection ────────────────────────────────────────────────────────────
    max_comments_per_video: int = 500
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

    # ── Target YouTube Videos ─────────────────────────────────────────────────
    target_video_ids: Tuple[str, ...] = (
        "q7v1CO-s20g", "ZWka6eLmSyk", "bI9PTZMMgH8", "4kfCrIjGWrw",
    )

    seed_channel_ids: Tuple[str, ...] = (
        "UCq0OBR9O0LIMgFXMFNV8s8A", "UCVIVoSBGfO8TJbRHWu3hFHg",
        "UCJDpFw-8sFEYW3sMGrqHBSQ", "UCdmoLQbTvmI5VWQtNGHnSxw",
        "UC8bnSiS3E7pHBUTKTLqJHSA", "UC9yY8dMssN3kquXXhAowZpw",
    )

    youtube_search_queries: Tuple[str, ...] = (
        "VinFast VF3 trải nghiệm thực tế", "VinFast VF5 review chủ xe",
        "VinFast VF6 đánh giá", "VinFast VF7 review 2024",
        "VinFast VF8 sau 1 năm sử dụng", "VinFast VF9 chủ xe chia sẻ",
        "BYD Atto 3 Việt Nam đánh giá", "BYD Dolphin review tiếng Việt 2024",
        "BYD Seal đánh giá thực tế Việt Nam", "BYD vs VinFast so sánh 2024",
        "xe điện nào tốt nhất Việt Nam 2024", "trạm sạc xe điện Việt Nam",
    )
    max_search_results_per_query: int = 8

    # ── Brand Keywords ────────────────────────────────────────────────────────
    brand_keywords: Dict[str, Tuple[str, ...]] = field(default_factory=lambda: {
        "VinFast": (
            "vinfast", "vf3", "vf5", "vf6", "vf7", "vf8", "vf9", "vfe34",
            "vf 3", "vf 5", "vf 6", "vf 7", "vf 8", "vf 9", "vin",
        ),
        "BYD": (
            "byd", "atto", "dolphin", "seal", "han ev", "tang ev",
            "atto 3", "byd seal", "byd dolphin", "blade battery",
        ),
        "Tesla":  ("tesla", "model 3", "model y", "model s", "cybertruck"),
        "Wuling": ("wuling", "hongguang", "mini ev", "wuling air"),
        "MG":     ("mg zs", "mg4", "mg5", "mg electric", "mg mulan"),
    })


# ══════════════════════════════════════════════════════════════════════════════
# ASPECT TAXONOMY
# ══════════════════════════════════════════════════════════════════════════════

ASPECT_MAP: Dict[str, List[str]] = {
    "BATTERY_CHARGING": [
        "pin", "sạc", "trạm_sạc", "kilowatt", "kilowatt_giờ", "ngắt_sạc_sớm",
        "sạc_chậm", "sạc_nhanh", "phạm_vi_thực_tế", "tiêu_hao_pin", "pin_kém",
        "pin_tốt", "lo_ngại_phạm_vi", "cổng_sạc", "mất_điện_đột_ngột",
        "sạc_ac", "sạc_dc", "chuẩn_sạc", "pin_sắt_lithium", "pin_blade",
        "suy_giảm_pin", "sạc_tại_nhà", "v2l_xuất_điện",
        "range", "km", "battery", "charging", "charge", "kwh",
    ],
    "SOFTWARE_TECHNOLOGY": [
        "phần_mềm", "lỗi_phần_mềm", "cập_nhật_qua_mạng", "phản_hồi_chậm",
        "hệ_thống_hỗ_trợ_lái", "cảnh_báo_sai", "màn_hình", "gps",
        "kết_nối_apple", "kết_nối_android", "phần_mềm_nhúng", "tự_lái",
        "camera", "cảm_biến", "wifi", "bluetooth", "ứng_dụng", "lỗi_hệ_thống",
        "màn_hình_đơ", "giao_diện", "hệ_thống_dilink", "camera_360",
        "kiểm_soát_hành_trình", "giữ_làn_đường", "phanh_khẩn_cấp",
        "cảnh_báo_điểm_mù", "software", "app", "ota", "update",
    ],
    "PERFORMANCE_DRIVING": [
        "tăng_tốc", "vận_hành", "phanh", "lái", "cảm_giác_lái", "hệ_thống_treo",
        "vận_hành_êm", "tiếng_ồn", "rung", "động_cơ", "mã_lực", "mô_men_xoắn",
        "tốc_độ", "gia_tốc_0_100", "êm", "mạnh", "chế_độ_lái", "lái_một_chân",
        "phanh_tái_sinh", "cân_bằng_điện_tử", "dẫn_động_4_bánh", "treo_khí",
        "sport", "eco", "acceleration", "performance", "driving",
    ],
    "DESIGN_INTERIOR": [
        "thiết_kế", "nội_thất", "ngoại_thất", "ghế", "chất_liệu", "không_gian",
        "màu_sắc", "đèn", "cốp_sau", "khoang", "đẹp", "xấu", "sang", "vô_lăng",
        "bảng_điều_khiển", "đèn_pha", "không_gian_chân", "cửa_sổ_trời",
        "da_ghế", "da_nappa", "cốp_trước", "ghế_thông_gió", "chiều_dài_cơ_sở",
        "interior", "exterior", "design", "style", "luxury",
    ],
    "SERVICE_AFTERSALES": [
        "dịch_vụ_sau_bán", "bảo_hành", "đại_lý", "xưởng_sửa_chữa", "nhân_viên",
        "bảo_dưỡng", "sửa_chữa", "phụ_tùng", "hỗ_trợ", "tư_vấn", "thái_độ",
        "khách_hàng", "giao_xe", "trung_tâm_dịch_vụ", "hotline", "cứu_hộ",
        "service", "warranty", "dealer", "repair", "maintenance",
    ],
    "PRICE_VALUE": [
        "giá", "định_giá_cao", "giá_đắt", "giá_rẻ", "giá_trị_tốt", "giá_tương_xứng",
        "tài_chính", "trả_góp", "chi_phí_vận_hành", "tiết_kiệm", "phí_trước_bạ",
        "tiền", "khuyến_mãi", "giá_đắt_nhưng_xứng", "tốn_chi_phí", "xứng_đáng",
        "lãng_phí", "hối_tiếc", "price", "value", "cost", "expensive", "cheap",
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# SENTIMENT LEXICONS
# ══════════════════════════════════════════════════════════════════════════════

POSITIVE_LEXICON: frozenset = frozenset({
    "tốt", "ngon", "tuyệt", "tuyệt_vời", "ổn", "đẹp", "rẻ", "hài_lòng", "thích",
    "yêu", "xuất_sắc", "hoàn_hảo", "ấn_tượng", "mượt", "nhanh", "pin_tốt",
    "sạc_nhanh", "ổn_định", "đáng_mua", "giá_trị_tốt", "thú_vị", "tiện_lợi",
    "đáng_tiền", "xứng_đáng", "mạnh", "êm", "sang", "chắc_chắn", "bền", "tiện",
    "đồng_ý", "tuyệt_hảo", "đỉnh", "xịn", "smooth", "great", "excellent",
    "perfect", "amazing", "awesome", "siêu", "pro", "phong_cách", "hiện_đại",
    "thông_minh", "vượt_trội", "tiết_kiệm", "đáng", "nên_mua", "recommend",
    "worth", "vui_lòng", "tuyệt_đỉnh", "đáng_tin", "chuyên_nghiệp",
    "nhiệt_tình", "tận_tâm", "vận_hành_êm", "sạc_dc", "pin_blade", "ngầu",
    "giá_tương_xứng", "giá_đắt_nhưng_xứng",
    "ok", "oke", "ổn_áp", "ngon_lành", "chất", "phê", "ưng", "ưng_ý", "ưng_bụng",
    "đã", "đã_lắm", "sướng", "khoẻ", "khỏe", "chuẩn", "max", "best", "nice",
    "good", "love", "like", "top", "số_1", "nhất", "win", "tuyệt_cú_mèo",
    "an_toàn", "đáng_đồng_tiền", "hợp_lý", "phải_chăng", "vừa_túi_tiền",
    "nhanh_chóng", "thuận_tiện", "dễ_dùng", "dễ_sử_dụng", "tin_cậy", "bất_ngờ",
    "hơn_mong_đợi", "vượt_mong_đợi", "thoải_mái", "rộng_rãi", "thoáng",
    "sáng_sủa", "đẳng_cấp", "cao_cấp", "premium", "sang_trọng", "luxury",
    "nên", "được", "hay", "ngon_nghẻ", "chất_lừ", "xịn_xò", "đỉnh_cao",
    "phục", "nể", "ủng_hộ", "tin_tưởng", "trung_thành", "quay_lại",
    "giới_thiệu", "khuyên", "5_sao", "cảm_ơn",
})

NEGATIVE_LEXICON: frozenset = frozenset({
    "tệ", "lỗi", "chậm", "kém", "đắt", "thất_vọng", "tức", "chán", "pin_kém",
    "sạc_chậm", "ngắt_sạc_sớm", "cảnh_báo_sai", "phản_hồi_chậm", "lỗi_phần_mềm",
    "hỏng", "trục_trặc", "vấn_đề", "sự_cố", "đơ", "treo",
    "mất_điện_đột_ngột", "định_giá_cao", "giá_đắt", "tiêu_hao_pin", "lo_ngại_phạm_vi",
    "ồn", "rung", "xấu", "kém_chất_lượng", "tồi", "bad", "terrible", "horrible",
    "awful", "worst", "poor", "lỗi_hệ_thống", "màn_hình_đơ", "bực_bội", "khó_chịu",
    "lãng_phí", "lừa_đảo", "hối_tiếc", "được_đánh_giá_cao_quá", "tệ_hại",
    "buồn", "chê", "không_đáng", "overpriced", "scam", "waste",
    "suy_giảm_pin", "lag", "bug", "glitch", "crash",
    "disappointed", "frustrating", "disgusting", "broken", "fail",
    "dở", "rác", "phí_tiền", "phí", "mắc", "tốn", "nguy_hiểm", "tai_nạn", "cháy",
    "triệu_hồi", "recall", "bất_lực", "chậm_trễ", "trì_trệ", "delay", "chờ",
    "nóng", "quá_nóng", "overheat", "rỉ_sét", "bong_tróc", "nứt", "vỡ",
    "gãy", "kẹt", "liệt", "chết", "die", "dead", "tắt", "mất",
    "không_được", "dở_tệ", "dở_ẹc", "tào_lao", "nhảm", "vô_dụng", "bỏ_đi",
    "hư", "hỏng_hóc", "trả_lại", "refund", "hoàn_tiền", "kiện", "khiếu_nại",
    "complaint", "toxic", "spam", "fake", "giả", "lừa", "gian_lận",
    "ngáo_giá", "chặt_chém", "ăn_cắp", "kém_xa", "thua", "flop",
    "chán_ngắt", "nhạt", "thiếu", "yếu", "ọp_ẹp", "mỏng",
    "nguy", "rủi_ro", "risk", "lo", "sợ", "ghét", "hate", "dislike",
    "1_sao", "phốt", "bóc_phốt", "tẩy_chay", "boycott",
})

NEGATION_PARTICLES: frozenset = frozenset({
    "không", "chưa", "chẳng", "chả", "ko", "chx", "khong", "kp", "hem", "hông",
    "chưa_bao_giờ", "không_bao_giờ", "chẳng_bao_giờ", "không_hề", "chưa_hề",
    "chẳng_hề", "ko_có", "k_có", "khum", "hok", "ko_thấy",
})

VIETNAMESE_STOPWORDS: frozenset = frozenset({
    "là", "có", "thì", "mà", "để", "của", "cho", "các", "những", "một", "này", "kia",
    "đó", "cũng", "đã", "đang", "sẽ", "được", "bị", "như", "khi", "trong", "với",
    "từ", "ra", "lại", "thêm", "chỉ", "nhiều", "nhất", "quá", "lắm", "ơi", "à", "ừ",
    "nhé", "nha", "nữa", "còn", "vào", "lên", "xuống", "đi", "về", "thế", "gì", "ai",
    "người", "con", "chiếc", "thấy", "bạn", "mình", "vẫn", "đến", "nơi", "nếu",
    "bởi", "vì", "nên", "tuy", "rằng", "nào", "bao", "thật", "vậy", "nhau", "luôn",
    "hay", "hoặc", "cả", "sao", "trên", "dưới", "trước", "sau", "giữa", "tại", "lúc",
    "ngay", "suốt", "theo", "qua", "trở", "ạ", "ạh", "ah", "uh", "uhm", "hm", "ừa",
    "hehe", "hihi", "lol", "xe", "cái", "thứ", "loại", "kiểu", "dạng", "mọi", "toàn",
    "lần", "rồi", "cùng", "hơn", "vô",
})


# ══════════════════════════════════════════════════════════════════════════════
# VISUALIZATION PALETTES
# ══════════════════════════════════════════════════════════════════════════════

BRAND_PALETTE = {
    "VinFast": "#00C853", "BYD": "#2196F3", "Mixed": "#FFD600",
    "Unknown": "#9E9E9E", "Tesla": "#F44336", "Wuling": "#FF6B35", "MG": "#9C27B0",
}

ASPECT_PALETTE = {
    "BATTERY_CHARGING": "#FF6B6B", "SOFTWARE_TECHNOLOGY": "#4ECDC4",
    "PERFORMANCE_DRIVING": "#45B7D1", "DESIGN_INTERIOR": "#96CEB4",
    "SERVICE_AFTERSALES": "#FFEAA7", "PRICE_VALUE": "#DDA0DD",
}

SENTIMENT_PALETTE = {"positive": "#00C853", "negative": "#F44336", "neutral": "#9E9E9E"}
