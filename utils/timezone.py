from datetime import datetime as _datetime
from zoneinfo import ZoneInfo
import sqlalchemy as sa
from sqlalchemy import TypeDecorator, DateTime

# Jakarta timezone constant
JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

class datetime(_datetime):
    @classmethod
    def now(cls, tz=None):
        """Always return Jakarta time by default"""
        tz = tz or JAKARTA_TZ
        return super().now(tz)

    @classmethod
    def utcnow(cls):
        """Return Jakarta time instead of UTC for consistency"""
        return cls.now(JAKARTA_TZ)
    
    @classmethod
    def jakarta_now(cls):
        """Explicit method to get Jakarta time"""
        return cls.now(JAKARTA_TZ)

# Convenience function for direct import
def jakarta_now():
    """Get current datetime in Jakarta timezone"""
    return _datetime.now(JAKARTA_TZ)

def to_jakarta(dt):
    """Convert any datetime to Jakarta timezone"""
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(JAKARTA_TZ)

# Custom SQLAlchemy type that always stores and retrieves Jakarta timezone
class JakartaDateTime(TypeDecorator):
    """A DateTime type that always stores and retrieves Jakarta timezone"""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert to Jakarta timezone before storing"""
        if value is not None:
            if value.tzinfo is None:
                # Assume it's already Jakarta time if no timezone
                value = value.replace(tzinfo=JAKARTA_TZ)
            else:
                # Convert to Jakarta timezone
                value = value.astimezone(JAKARTA_TZ)
            # Store as timezone-aware datetime
            return value
        return value

    def process_result_value(self, value, dialect):
        """Convert to Jakarta timezone when retrieving"""
        if value is not None:
            if value.tzinfo is None:
                # If stored without timezone, assume it's Jakarta time
                value = value.replace(tzinfo=JAKARTA_TZ)
            else:
                # Convert to Jakarta timezone
                value = value.astimezone(JAKARTA_TZ)
        return value