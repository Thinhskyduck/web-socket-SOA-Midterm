import json
import asyncio
import redis.asyncio as redis  # ✅ fix lỗi
from fastapi import FastAPI, WebSocket

app = FastAPI()

REDIS_URL = "redis://metro.proxy.rlwy.net:19160"

@app.websocket("/kitchen/ws")
async def websocket_kitchen(websocket: WebSocket):
    await websocket.accept()
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("kitchen_queue")

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
        await pubsub.unsubscribe("kitchen_queue")


@app.websocket("/kitchen/ws/menu")
async def websocket_menu_updates(websocket: WebSocket):
    await websocket.accept()
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
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
