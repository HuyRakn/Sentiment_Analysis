import json

NOTEBOOK_PATH = "EV_Sentiment_Analysis_VinFast_vs_BYD.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if "class PipelineConfig:" in src:
            import re
            
            replacement = '''    target_video_ids: Tuple[str, ...] = (
        "q7v1CO-s20g", "ZWka6eLmSyk", "bI9PTZMMgH8", "4kfCrIjGWrw",
    )
    
    seed_channel_ids: Tuple[str, ...] = (
        "UCq0OBR9O0LIMgFXMFNV8s8A",  # AutoDailyVN
        "UCVIVoSBGfO8TJbRHWu3hFHg",  # Xehay
        "UCJDpFw-8sFEYW3sMGrqHBSQ",  # Tipcar
        "UCdmoLQbTvmI5VWQtNGHnSxw",  # Xe Hay TV
        "UC8bnSiS3E7pHBUTKTLqJHSA",  # VinFast Official VN
        "UC9yY8dMssN3kquXXhAowZpw",  # Xe Điện Việt
    )

    youtube_search_queries: Tuple[str, ...] = (
        "VinFast VF3 trải nghiệm thực tế", "VinFast VF5 review chủ xe",
        "VinFast VF6 đánh giá", "VinFast VF7 review 2024",
        "VinFast VF8 sau 1 năm sử dụng", "VinFast VF9 chủ xe chia sẻ",
        "VinFast e34 review", "taxi xanh SM trải nghiệm", "trạm sạc V-Green thực tế",
        "BYD Atto 3 Việt Nam đánh giá", "BYD Dolphin review tiếng Việt 2024",
        "BYD Seal đánh giá thực tế Việt Nam", "BYD Han EV review",
        "xe điện Trung Quốc so sánh VinFast", "BYD vs VinFast so sánh 2024",
    )
    max_search_results_per_query: int = 5'''
            
            # This handles both cases (whether it was patched by the previous scripts or not)
            src = re.sub(r'    target_video_ids: Tuple\[.*?\]\)(?:\n\n    youtube_search_queries:[^\n]*\n.*?\))?(?:\n    max_search_results_per_query:[^\n]*)?', replacement, src, flags=re.DOTALL)
            
            # Since the user could have the base notebook or patched notebook:
            src = re.sub(r'    # Verified working Vietnamese EV videos\..*?max_search_results_per_query: int = \d+', replacement, src, flags=re.DOTALL)
            
            nb["cells"][i]["source"] = [l + "\n" if not l.endswith("\n") else l for l in src.split("\n")]
            if nb["cells"][i]["source"]: nb["cells"][i]["source"][-1] = nb["cells"][i]["source"][-1].rstrip("\n")

with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("✅ Force patched config variables in PipelineConfig")
