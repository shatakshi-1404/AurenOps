import redis
import redis.asyncio as aredis

from app.core.config import settings

r = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def async_redis():
    return aredis.Redis.from_url(settings.redis_url, decode_responses=True)
