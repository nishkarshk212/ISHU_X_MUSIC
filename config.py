from os import getenv
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", 0))
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = int(getenv("LOGGER_ID", 0))
        self.STORAGE_GROUP_ID = int(getenv("STORAGE_GROUP_ID", getenv("LOGGER_ID", 0)))
        self.OWNER_ID = int(getenv("OWNER_ID", 0))

        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", 120)) * 60
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", 20))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", 20))

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/titanic_network")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/+WAOT47P-70QwOTBl")

        self.YTPROXY_URL = getenv("YTPROXY_URL", "https://tgapi.xbitcode.com")  # xBit Music Endpoint
        self.YT_API_KEY = getenv("YT_API_KEY", "")  # Get from https://t.me/tgmusic_apibot

        # Self-hosted YouTube API — Heroku apihub proxy (X-API-Key = lily_mOVOd9TG7zuE4L9QDxEndbiyjQc9he).
        self.RAILWAY_YT_API_URL = getenv("LILY_API_URL", getenv("RAILWAY_YT_API_URL", "https://apihub-cebe91de7ae2.herokuapp.com"))
        self.RAILWAY_YT_API_KEY = getenv("LILY_API_KEY", getenv("RAILWAY_YT_API_KEY", "lily_mOVOd9TG7zuE4L9QDxEndbiyjQc9he"))

        # Shruti API — Primary download source (get key from @SHRUTIAPIBOT)
        self.SHRUTI_API_URL = getenv("SHRUTI_API_URL", "http://api01.shrutibots.site")
        self.SHRUTI_API_KEY = getenv("SHRUTI_API_KEY", "")
        
        self.AUTO_LEAVE: bool = getenv("AUTO_LEAVE", "False").lower() == "true"
        self.AUTO_END: bool = getenv("AUTO_END", "False").lower() == "true"

        # ── Daily restart + cleanup (keep playback fast, clear stale URLs) ──
        # Bot does a clean self-restart once per day at this local hour:minute
        # (24h clock). Clearing cache/ + downloads/ every day drops the stale
        # googlevideo URLs and disk clutter that make the bot slow over time.
        # Default -1 (disabled).
        self.RESTART_HOUR = int(getenv("RESTART_HOUR", "-1"))
        self.RESTART_MIN = int(getenv("RESTART_MIN", "0"))

        # Periodic prune of cache/ + downloads/ so accumulated files don't slow
        # the bot down. Interval = how often to scan (minutes, default 60).
        # MAX_AGE = delete files older than this many minutes (default 90).
        self.CLEANUP_INTERVAL: int = int(getenv("CLEANUP_INTERVAL", "60")) * 60
        self.CLEANUP_MAX_AGE: int = int(getenv("CLEANUP_MAX_AGE", "90")) * 60

        # Forward playback errors to the log group (True/False, default True)
        self.LOG_ERRORS: bool = getenv("LOG_ERRORS", "True").lower() == "true"

        self.THUMB_GEN: bool = getenv("THUMB_GEN", "True").lower() == "true"
        self.VIDEO_PLAY: bool = getenv("VIDEO_PLAY", "True").lower() == "true"

        self.LANG_CODE = getenv("LANG_CODE", "en")

        self.COOKIES_URL = [
            url for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.COOKIES_DATA = getenv("COOKIES_DATA", "")
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg")
        self.PING_IMG = getenv("PING_IMG", "https://files.catbox.moe/haagg2.png")
        self.START_IMG = getenv("START_IMG", "https://files.catbox.moe/zvziwk.jpg")

    def check(self):
        missing = [
            var
            for var in ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URL", "LOGGER_ID", "OWNER_ID", "SESSION1"]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
