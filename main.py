from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import asyncio
import httpx
import os
import logging
from redis_client import redis_client
from starlette.websockets import WebSocketState
from contextlib import suppress

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

RAILWAY_API_URL = os.getenv("RAILWAY_API_URL", "https://soa-deploy.up.railway.app")

kitchen_clients = []
menu_clients = []

@app.get("/")
def root():
    return {"message": "WebSocket Server Running"}

# @app.websocket("/ws/kitchen")
# async def websocket_kitchen(websocket: WebSocket):
#     await websocket.accept()
#     kitchen_clients.append(websocket)
#     pubsub = redis_client.pubsub()
#     pubsub.subscribe("kitchen:orders")

#     try:
#         # Lấy đơn hàng từ Railway API
#         async with httpx.AsyncClient() as client:
#             response = await client.get(f"{RAILWAY_API_URL}/kitchen/get-orders/")
#             if response.status_code == 200:
#                 pending_orders = response.json()
#                 if websocket.application_state == WebSocketState.CONNECTED:
#                     await websocket.send_json({"orders": pending_orders})

#         while True:
#             message = pubsub.get_message(timeout=1.0)
#             if message and message["type"] == "message":
#                 try:
#                     data = json.loads(message["data"])
#                     if websocket.application_state == WebSocketState.CONNECTED:
#                         await websocket.send_json({"order": data})
#                 except json.JSONDecodeError:
#                     logger.error("Invalid JSON in Redis message")
#             await asyncio.sleep(0.1)
#     except WebSocketDisconnect:
#         logger.info("Kitchen client disconnected")
#     except Exception as e:
#         logger.error(f"Kitchen WebSocket error: {str(e)}")
#     finally:
#         kitchen_clients.remove(websocket)
#         pubsub.close()
#         if websocket.application_state == WebSocketState.CONNECTED:
#             with suppress(Exception):
#                 await websocket.close()

@app.websocket("/ws/kitchen")
async def websocket_kitchen(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to /ws/kitchen")
    kitchen_clients.append(websocket)
    pubsub = redis_client.pubsub()
    pubsub.subscribe("kitchen:orders")
    logger.info("Subscribed to kitchen:orders")

    try:
        logger.info("Fetching orders from Railway API...")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{RAILWAY_API_URL}/kitchen/get-orders/")
            logger.info(f"Railway API status: {response.status_code}")
            if response.status_code == 200:
                pending_orders = response.json()
                logger.info("Sending initial orders to client...")
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"orders": pending_orders})
            else:
                logger.warning(f"Unexpected API response: {response.text}")

        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    logger.info(f"Sending order update: {data}")
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.send_json({"order": data})
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in Redis message")
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.info("Kitchen client disconnected")

    except Exception as e:
        logger.exception("Kitchen WebSocket error occurred")

    finally:
        kitchen_clients.remove(websocket)
        pubsub.close()
        if websocket.application_state == WebSocketState.CONNECTED:
            with suppress(Exception):
                await websocket.close()
        logger.info("WebSocket connection cleaned up")

@app.websocket("/ws/menu")
async def websocket_menu(websocket: WebSocket):
    if websocket.application_state != WebSocketState.CONNECTING:
        logger.warning("WebSocket không ở trạng thái CONNECTING, bỏ qua accept()")
        return

    try:
        await websocket.accept()
        logger.info("Client connected to /ws/menu")
        menu_clients.append(websocket)

        pubsub = redis_client.pubsub()
        pubsub.subscribe("kitchen:menu_updates")
        logger.info("Subscribed to kitchen:menu_updates")

        while True:
            message = pubsub.get_message(timeout=1.0)
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    logger.info(f"Sending to client: {data}")
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.send_json({"menu_update": data})
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in Redis message")
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.info("Menu client disconnected")
    except Exception as e:
        logger.error(f"Menu WebSocket error: {str(e)}")
    finally:
        with suppress(ValueError):
            menu_clients.remove(websocket)
        pubsub.close()
        if websocket.application_state == WebSocketState.CONNECTED:
            with suppress(Exception):
                await websocket.close()

@app.on_event("shutdown")
async def shutdown_event():
    for ws in kitchen_clients + menu_clients:
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.close()
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {str(e)}")
