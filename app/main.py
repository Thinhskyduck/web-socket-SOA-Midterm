# websocket_server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services import order_service, kitchen_service
import redis
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://metro.proxy.rlwy.net:19160"),
    decode_responses=True
)

kitchen_clients = []

@app.websocket("/ws/order")
async def websocket_order(websocket: WebSocket):
    await websocket.accept()
    try:
        async with asyncio.timeout(300):
            while True:
                data = await websocket.receive_text()
                try:
                    order_data = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON data"})
                    continue

                db: Session = SessionLocal()
                try:
                    processed_order = order_service.process_websocket_order(db, order_data)
                    await websocket.send_json({"status": "Order received", "order_id": processed_order.order_id})
                except HTTPException as e:
                    await websocket.send_json({"error": e.detail})
                finally:
                    db.close()
    except asyncio.TimeoutError:
        logger.info("Order WebSocket timeout")
    except WebSocketDisconnect:
        logger.info("Client disconnected from /ws/order")
    except Exception as e:
        logger.error(f"Order WebSocket error: {str(e)}")
    finally:
        await websocket.close()

@app.websocket("/ws/kitchen")
async def websocket_kitchen(websocket: WebSocket):
    await websocket.accept()
    kitchen_clients.append(websocket)
    db: Session = SessionLocal()
    pubsub = redis_client.pubsub()
    pubsub.subscribe("kitchen:orders", "kitchen:status_updates")
    
    try:
        pending_orders = kitchen_service.get_pending_orders(db)
        await websocket.send_json({"orders": pending_orders})

        async with asyncio.timeout(300):
            while True:
                message = pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        if message["channel"] == "kitchen:orders":
                            await websocket.send_json({"order": data})
                        elif message["channel"] == "kitchen:status_updates":
                            await websocket.send_json({"status_update": data})
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON in Redis message")
                await asyncio.sleep(0.1)
    except asyncio.TimeoutError:
        logger.info("Kitchen WebSocket timeout")
    except WebSocketDisconnect:
        kitchen_clients.remove(websocket)
        logger.info("Kitchen client disconnected")
    except Exception as e:
        logger.error(f"Kitchen WebSocket error: {str(e)}")
    finally:
        db.close()
        pubsub.close()
        await websocket.close()

@app.event("shutdown")
async def shutdown_event():
    for ws in kitchen_clients:
        await ws.close()