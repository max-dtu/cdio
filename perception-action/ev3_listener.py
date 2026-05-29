#!/usr/bin/env python3

import asyncio
import websockets
import json

HOST = "0.0.0.0"
PORT = 8765

async def handler(websocket):
    print("Client connected")

    # send a test message immediately
    await websocket.send(json.dumps({
        "type": "status",
        "payload": "EV3 connected"
    }))

    try:
        async for message in websocket:
            cmd = message.strip()
            print("Received:", cmd)

            # echo status back
            await websocket.send(json.dumps({
                "type": "status",
                "payload": f"received: {cmd}"
            }))

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def main():
    async with websockets.serve(handler, HOST, PORT):
        print(f"WebSocket server running on ws://{HOST}:{PORT}")
        await asyncio.Future()

asyncio.run(main())