from datetime import datetime as _datetime
from zoneinfo import ZoneInfo

class datetime(_datetime):
    @classmethod
    def now(cls, tz=None):
        tz = tz or ZoneInfo("Asia/Jakarta")
        return super().now(tz)

    @classmethod
    def utcnow(cls):
        # fallback biar konsisten
        return cls.now()
