import json
import asyncio
import aioredis
from fastapi import FastAPI, WebSocket

app = FastAPI()

# Redis URL (public từ Railway)
REDIS_URL = "redis://metro.proxy.rlwy.net:19160"

@app.websocket("/kitchen/ws")
async def websocket_kitchen(websocket: WebSocket):
    await websocket.accept()
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe("queue_updates")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message["data"])
                await websocket.send_json({"updates": data})
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[ERROR kitchen/ws] {e}")
        await websocket.close()
        await pubsub.unsubscribe("queue_updates")


@app.websocket("/kitchen/ws/menu")
async def websocket_menu_updates(websocket: WebSocket):
    await websocket.accept()
    redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe("menu_updates")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message["data"])
                await websocket.send_json({"menu_updates": data})
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"[ERROR kitchen/ws/menu] {e}")
        await websocket.close()
        await pubsub.unsubscribe("menu_updates")
