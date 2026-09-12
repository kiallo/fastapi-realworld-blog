"""WebSocket 基础"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Optional
from loguru import logger
import json

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 存储所有活跃连接
        self.active_connections: List[WebSocket] = []
        # 存储用户信息
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections[username] = websocket
        logger.info(f"🔌 {username} 已连接. 当前在线: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, username: str):
        """断开 WebSocket 连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if username in self.user_connections:
            del self.user_connections[username]
        logger.info(f"🔌 {username} 已断开. 当前在线: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, username: str):
        """发送个人消息"""
        if username in self.user_connections:
            websocket = self.user_connections[username]
            await websocket.send_text(message)

    async def broadcast(self, message: str, sender: Optional[str] = None):
        """广播消息给所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                if sender:
                    # 带发送者信息的消息
                    await connection.send_text(f"[{sender}]: {message}")
                else:
                    # 系统消息
                    await connection.send_text(message)
            except:
                # 标记断开的连接
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)


# 创建全局连接管理器
manager = ConnectionManager()

@router.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    """
    WebSocket 聊天室端点
    
    使用方式：
    ws://localhost:8000/api/ws/ws/你的用户名
    """
    # 连接
    await manager.connect(websocket, username)

    # 广播用户加入消息
    await manager.broadcast(
        f"👋 {username} 加入了聊天室",
        sender="系统"
    )

    # 发送欢迎消息给新用户
    await manager.send_personal_message(
        f"欢迎 {username}！当前在线人数: {len(manager.active_connections)}",
        username
    )

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            logger.info(f"📩 收到来自 {username} 的消息: {data}")
            
            # 处理特殊命令
            if data.startswith("/"):
                await handle_command(data, username, websocket)
            else:
                # 广播消息
                await manager.broadcast(data, sender=username)
                
    except WebSocketDisconnect:
        # 用户断开连接
        manager.disconnect(websocket, username)
        await manager.broadcast(
            f"👋 {username} 离开了聊天室",
            sender="系统"
        )


async def handle_command(command: str, username: str, websocket: WebSocket):
    """处理特殊命令"""
    if command == "/help":
        await websocket.send_text("""
📖 可用命令：
/help - 显示帮助
/users - 查看在线用户
/quit - 退出聊天室
        """)
    
    elif command == "/users":
        users = list(manager.user_connections.keys())
        await websocket.send_text(f"👥 在线用户: {', '.join(users)}")
    
    elif command == "/quit":
        await websocket.send_text("👋 再见！")
        await websocket.close()
    
    else:
        await websocket.send_text(f"❌ 未知命令: {command}，输入 /help 查看帮助")

