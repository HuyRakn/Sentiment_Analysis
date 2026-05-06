import json
import ast

NOTEBOOK_PATH = "EV_Sentiment_Analysis_VinFast_vs_BYD.ipynb"

with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

# The new YouTubeComboDiscovery logic to inject
combo_discovery = '''
import time

class YouTubeComboDiscovery:
    """
    Dynamically discovers Vietnamese EV video IDs using:
    1. Channel Playlist Scraping (costs 1 API unit per request) - Primary
    2. Search API (costs 100 API units per request) - Secondary
    """

    def __init__(self, config: PipelineConfig):
        self._cfg = config
        self._log = _build_logger("ev.yt_discovery")
        self._client = None
        if _YTAPI and config.youtube_api_key not in ("", "YOUR_YOUTUBE_API_KEY"):
            try:
                self._client = yt_build("youtube", "v3",
                                         developerKey=config.youtube_api_key)
                self._log.info("YouTube API Client ready ✅")
            except Exception as e:
                self._log.warning("YouTube API init failed: %s", e)

    def _get_uploads_playlist_id(self, channel_id: str) -> str:
        """Convert Channel ID (UC...) to Uploads Playlist ID (UU...)."""
        if channel_id.startswith("UC"):
            return "UU" + channel_id[2:]
        return channel_id

    def discover_from_channels(self) -> list:
        """Fetch videos from specific channels. Extremely quota-efficient."""
        if self._client is None: return []
        discovered = set()
        channels = getattr(self._cfg, "seed_channel_ids", [])
        
        for cid in channels:
            try:
                playlist_id = self._get_uploads_playlist_id(cid)
                resp = self._client.playlistItems().list(
                    part="contentDetails",
                    playlistId=playlist_id,
                    maxResults=50   # Fetch 50 most recent videos per channel
                ).execute()
                for item in resp.get("items", []):
                    vid = item.get("contentDetails", {}).get("videoId")
                    if vid: discovered.add(vid)
                time.sleep(0.1)
            except Exception as e:
                self._log.warning("Channel scrape error for %s: %s", cid, e)
                
        self._log.info("📺 Discovered %d video IDs from Channels", len(discovered))
        return list(discovered)

    def discover_from_search(self) -> list:
        """Fetch videos via Search API. Expensive but catches trending."""
        if self._client is None: return []
        discovered = set()
        queries = getattr(self._cfg, "youtube_search_queries", [])
        max_res = getattr(self._cfg, "max_search_results_per_query", 10)
        
        for q in queries:
            try:
                resp = self._client.search().list(
                    q=q, part="id", type="video",
                    maxResults=max_res, relevanceLanguage="vi", order="relevance",
                ).execute()
                for item in resp.get("items", []):
                    vid = item.get("id", {}).get("videoId")
                    if vid: discovered.add(vid)
                time.sleep(0.5)
            except Exception as e:
                self._log.warning("Search query error '%s': %s", q, e)
                
        self._log.info("🔍 Discovered %d video IDs from Search API", len(discovered))
        return list(discovered)
        
    def discover_all(self) -> list:
        if self._client is None:
            self._log.warning("No YouTube client — discovery disabled.")
            return []
        ch_vids = self.discover_from_channels()
        sr_vids = self.discover_from_search()
        
        merged = list(dict.fromkeys(ch_vids + sr_vids))
        self._log.info("🚀 Total unique discovered video IDs: %d", len(merged))
        return merged

'''

# Process Config (Cell 4)
for i, cell in enumerate(nb["cells"]):
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # 1. Update Config Variables
        if "class PipelineConfig:" in src:
            # We want to replace the whole variables declaration from target_video_ids... up to max_comments_per_video
            import re
            
            # Find the starting position of target_video_ids
            replacement = '''    # Verified working Vietnamese EV videos.
    target_video_ids: Tuple[str, ...] = (
        "q7v1CO-s20g", "ZWka6eLmSyk", "bI9PTZMMgH8", "4kfCrIjGWrw",
    )
    
    seed_channel_ids: Tuple[str, ...] = (
        "UCq0OBR9O0LIMgFXMFNV8s8A",  # AutoDailyVN
        "UCVIVoSBGfO8TJbRHWu3hFHg",  # Xehay
        "UCJDpFw-8sFEYW3sMGrqHBSQ",  # Tipcar
        "UCdmoLQbTvmI5VWQtNGHnSxw",  # Xe Hay TV
        "UC8bnSiS3E7pHBUTKTLqJHSA",  # VinFast Official VN
        "UC9yY8dMssN3kquXXhAowZpw",  # Xe Điện Việt
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
            
            # Use regex to replace everything between target_video_ids: Tuple[str,...] to max_search_results_per_query: int = 15
            pattern = re.compile(r'    # Verified working Vietnamese EV videos.*?max_search_results_per_query: int = \d+', re.DOTALL)
            if pattern.search(src):
                src = pattern.sub(replacement, src)
            else:
                # Fallback if that pattern doesn't exist, we replace from target_video_ids...
                fallback_pattern = re.compile(r'    target_video_ids: Tuple.*?max_search_results_per_query: int = \d+', re.DOTALL)
                src = fallback_pattern.sub(replacement, src)

            # Change max_comments_per_video
            src = re.sub(r'max_comments_per_video:\s*int\s*=\s*\d+', 'max_comments_per_video: int = 500', src)
            
            nb["cells"][i]["source"] = [l + "\n" if not l.endswith("\n") else l for l in src.split("\n")]
            if nb["cells"][i]["source"]: nb["cells"][i]["source"][-1] = nb["cells"][i]["source"][-1].rstrip("\n")

        # 2. Inject YouTubeComboDiscovery
        if "class YouTubeCollector" in src:
            # We first strip out the old YouTubeSearchDiscovery if it's there
            if "class YouTubeSearchDiscovery:" in src:
                import re
                src = re.sub(r'class YouTubeSearchDiscovery:.*?class RedditCollector:', "class RedditCollector:", src, flags=re.DOTALL)
                # Ensure spacing
                src = src.replace("class RedditCollector:", "\n\nclass RedditCollector:")

            yt_end = "        return all_recs\n\n\nclass RedditCollector:"
            yt_repl = "        return all_recs\n" + combo_discovery + "\nclass RedditCollector:"
            if yt_end in src:
                src = src.replace(yt_end, yt_repl)
            else:
                # Alternate ending match
                fallback_end = "        return all_recs"
                src = src.replace(fallback_end, fallback_end + "\n" + combo_discovery, 1)

            nb["cells"][i]["source"] = [l + "\n" if not l.endswith("\n") else l for l in src.split("\n")]
            if nb["cells"][i]["source"]: nb["cells"][i]["source"][-1] = nb["cells"][i]["source"][-1].rstrip("\n")

        # 3. Modify Orchestrator
        if "def run_full_pipeline(" in src:
            # Replace old logic with ComboDiscovery logic
            import re
            
            # The orchestrator logic block to replace
            pattern = re.compile(r'        # Source 1: YouTube \(Static IDs \+ Dynamic Search Discovery\).*?all_records\.extend\(yt_recs\)', re.DOTALL)
            
            new_source1 = '''        # Source 1: YouTube (Combo: Channels + Search API)
        yt_discovery = YouTubeComboDiscovery(config)
        discovered_ids = yt_discovery.discover_all()

        seed_ids = list(config.target_video_ids)
        all_video_ids = list(dict.fromkeys(seed_ids + discovered_ids))
        LOG.info("YouTube targets: %d total video IDs prioritized", len(all_video_ids))

        expanded_config = PipelineConfig(
            youtube_api_key=config.youtube_api_key,
            reddit_client_id=config.reddit_client_id,
            reddit_client_secret=config.reddit_client_secret,
            target_video_ids=tuple(all_video_ids),
        )
        
        object.__setattr__(expanded_config, "seed_channel_ids", getattr(config, "seed_channel_ids", ()))
        object.__setattr__(expanded_config, "youtube_search_queries", getattr(config, "youtube_search_queries", ()))
        object.__setattr__(expanded_config, "max_search_results_per_query", getattr(config, "max_search_results_per_query", 5))
        object.__setattr__(expanded_config, "max_comments_per_video", config.max_comments_per_video)

        yt_recs = YouTubeCollector(expanded_config).collect()
        LOG.info("YouTube: %d records fetched", len(yt_recs))
        all_records.extend(yt_recs)'''
            
            if pattern.search(src):
                src = pattern.sub(new_source1, src)
            
            nb["cells"][i]["source"] = [l + "\n" if not l.endswith("\n") else l for l in src.split("\n")]
            if nb["cells"][i]["source"]: nb["cells"][i]["source"][-1] = nb["cells"][i]["source"][-1].rstrip("\n")

with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("✅ Patched notebook with Combo YouTube Discovery (Channels + Search).")
