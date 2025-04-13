# app/redis_client.py (Railway) hoặc redis_client.py (Render)
import redis
import os

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://metro.proxy.rlwy.net:19160"),
    decode_responses=True
)