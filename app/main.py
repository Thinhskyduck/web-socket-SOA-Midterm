import asyncio
import aioredis
from fastapi import FastAPI, WebSocket

app = FastAPI()

REDIS_URL = "redis://metro.proxy.rlwy.net:19160"  # Redis Railway của bạn

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe("new_order")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                await websocket.send_text(f"New order: {message['data']}")
            await asyncio.sleep(0.1)
    except Exception as e:
        await websocket.close()
