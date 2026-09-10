import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8000/api/ws/ws/TestUser"
    
    async with websockets.connect(uri) as websocket:
        # 接收欢迎消息
        welcome = await websocket.recv()
        print(f"收到: {welcome}")
        
        # 发送消息
        await websocket.send("大家好！")
        
        # 接收广播消息
        response = await websocket.recv()
        print(f"收到: {response}")
        
        # 测试命令
        await websocket.send("/users")
        response = await websocket.recv()
        print(f"收到: {response}")

asyncio.run(test_chat())
