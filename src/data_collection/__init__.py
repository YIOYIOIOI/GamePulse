"""数据采集模块"""

try:
    from .steam_scraper import SteamReviewScraper
except ModuleNotFoundError:
    # Heavy/legacy collector dependencies may be absent in the lightweight demo
    # environment. The Streamlit product console uses steam_light_collector.
    SteamReviewScraper = None

__all__ = ['SteamReviewScraper']
