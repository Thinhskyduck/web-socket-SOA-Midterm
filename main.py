# websocket_server.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import asyncio
import httpx
import os
import logging
from redis_client import redis_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# URL API trên Railway
RAILWAY_API_URL = os.getenv("RAILWAY_API_URL", "https://soa-deploy.up.railway.app")
# RAILWAY_API_URL = "https://soa-deploy.up.railway.app"

kitchen_clients = []
menu_clients = []

@app.websocket("/ws/order")
async def websocket_order(websocket: WebSocket):
    await websocket.accept()
    async with httpx.AsyncClient() as client:
        try:
            async with asyncio.timeout(300):
                while True:
                    data = await websocket.receive_text()
                    try:
                        order_data = json.loads(data)
                    except json.JSONDecodeError:
                        await websocket.send_json({"error": "Invalid JSON data"})
                        continue

                    # Gửi order đến API Railway
                    try:
                        response = await client.post(
                            f"{RAILWAY_API_URL}/order/confirm",
                            json=order_data
                        )
                        if response.status_code != 200:
                            await websocket.send_json({"error": response.json().get("detail", "Failed to create order")})
                            continue
                        order_response = response.json()
                        await websocket.send_json({"status": "Order received", "order_id": order_response["order_id"]})
                    except httpx.HTTPError as e:
                        await websocket.send_json({"error": f"Failed to connect to API: {str(e)}"})
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
    async with httpx.AsyncClient() as client:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("kitchen:orders")
        
        try:
            # Lấy danh sách order hiện tại từ API Railway
            response = await client.get(f"{RAILWAY_API_URL}/kitchen/get-orders/")
            if response.status_code == 200:
                pending_orders = response.json()
                await websocket.send_json({"orders": pending_orders})

            async with asyncio.timeout(300):
                while True:
                    message = pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await websocket.send_json({"order": data})
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
            pubsub.close()
            await websocket.close()

@app.websocket("/ws/menu")
async def websocket_menu(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to /ws/menu")
    menu_clients.append(websocket)
    pubsub = redis_client.pubsub()
    pubsub.subscribe("kitchen:menu_updates")
    logger.info("Subscribed to kitchen:menu_updates")
    
    try:
        async with asyncio.timeout(300):
            while True:
                message = pubsub.get_message(timeout=1.0)
                if message:
                    logger.info(f"Received message from Redis: {message}")
                if message and message["type"] == "message":
                    try:
                        print(type(message["data"]))    #log type data
                        
                        data = json.loads(message["data"].decode())
                        logger.info(f"Sending to client: {data}")
                        await websocket.send_json({"menu_update": data})
                    except json.JSONDecodeError:
                        logger.error("Invalid JSON in Redis message")
                # Gửi heartbeat để giữ kết nối
                await websocket.send_json({"type": "heartbeat"})
                await asyncio.sleep(0.1)
    except asyncio.TimeoutError:
        logger.info("Menu WebSocket timeout")
    except WebSocketDisconnect:
        menu_clients.remove(websocket)
        logger.info("Menu client disconnected")
    except Exception as e:
        logger.error(f"Menu WebSocket error: {str(e)}")
    finally:
        pubsub.close()
        await websocket.close()

@app.event("shutdown")
async def shutdown_event():
    for ws in kitchen_clients + menu_clients:
        await ws.close()