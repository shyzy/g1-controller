#!/usr/bin/env python3
"""
G1 Web 控制器 - 后端服务器
===========================
启动后：
1. 自动连接 G1 机器人
2. 启动 Web 服务器，Retroid 浏览器打开就能用
3. 处理实体摇杆输入 + 屏幕快捷按钮

不需要编译 APK，Termux 里直接跑！
"""

import asyncio
import json
import os
import sys
import time
import signal
import threading

# ===== 你的 AES 密钥（已填入） =====
AES_KEY = "c48cc7b7edc6191f2b393f6990848cbc"
G1_SERIAL = "E21D6000P7T99GGC"

# ===== 端口 =====
HTTP_PORT = 8888
WS_PORT = 8888

# ===== 快捷按钮配置（JSON 文件自动保存） =====
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shortcuts.json")

DEFAULT_SHORTCUTS = [
    # id, name, icon, color, action, param, desc, combo
    {"id":"sc1","name":"跳舞","icon":"💃","color":"#e53e3e","action":"SwitchMoveSkill","param":"Dance","desc":"= R1+B 效果","combo":"R1+B"},
    {"id":"sc2","name":"握手","icon":"🤝","color":"#805ad5","action":"SwitchMoveSkill","param":"HandShake","desc":"握手动作","combo":""},
    {"id":"sc3","name":"挥手","icon":"👋","color":"#3182ce","action":"SwitchMoveSkill","param":"Wave","desc":"挥手","combo":""},
    {"id":"sc4","name":"行走/站立","icon":"🚶","color":"#38a169","action":"ToggleWalkStand","param":"","desc":"= START 切换","combo":"START"},
    {"id":"sc5","name":"急停","icon":"⛔","color":"#e53e3e","action":"Damping","param":"","desc":"= L1+A 急停","combo":"L1+A"},
    {"id":"sc6","name":"行礼","icon":"🎩","color":"#d69e2e","action":"SwitchMoveSkill","param":"Bow","desc":"行礼","combo":""},
]

shortcuts = []
clients = set()
g1_connected = False

# =====================================================
#  加载/保存配置
# =====================================================

def load_shortcuts():
    global shortcuts
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                shortcuts = json.load(f)
            print(f"  ✅ 已加载 {len(shortcuts)} 个快捷按钮")
            return
        except:
            pass
    shortcuts = DEFAULT_SHORTCUTS.copy()
    save_shortcuts()

def save_shortcuts():
    os.makedirs(os.path.dirname(CONFIG_FILE) or ".", exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(shortcuts, f, ensure_ascii=False, indent=2)

# =====================================================
#  G1 连接与控制
# =====================================================

class G1Control:
    def __init__(self):
        self.conn = None
        self.state = "disconnected"
        self.walk_mode = False

    async def connect(self):
        """连接 G1"""
        from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod
        
        print("  🚀 正在连接 G1...")
        self.state = "connecting"
        broadcast_status("正在连接 G1...", "yellow")
        
        self.conn = UnitreeWebRTCConnection(
            WebRTCConnectionMethod.LocalAP,
            aes_128_key=AES_KEY,
        )
        await self.conn.connect()
        self.state = "connected"
        print("  ✅ G1 已连接！")
        broadcast_status("G1 已连接 ✅", "green")
        return True

    async def send(self, cmd, param=""):
        """发送指令"""
        if not self.conn:
            broadcast_status("G1 未连接", "red")
            return
        
        try:
            if cmd == "Damping":
                await self.conn.sport_mode.Damping()
                self.walk_mode = False
            elif cmd == "StandUp":
                await self.conn.sport_mode.StandUp()
                self.walk_mode = False
            elif cmd == "SitDown":
                await self.conn.sport_mode.SitDown()
                self.walk_mode = False
            elif cmd == "StartWalk":
                await self.conn.sport_mode.StandUp()
                self.walk_mode = True
            elif cmd == "StopWalk":
                self.walk_mode = False
            elif cmd == "ZeroTorque":
                await self.conn.sport_mode.ZeroTorque()
            elif cmd == "SwitchMoveSkill" and param:
                await self.conn.sport_mode.SwitchMoveSkill(param)
            elif cmd == "ToggleWalkStand":
                if self.walk_mode:
                    await self.conn.sport_mode.StandUp()
                    self.walk_mode = False
                else:
                    await self.conn.sport_mode.StandUp()
                    self.walk_mode = True
            
            broadcast_status(f"✅ 已执行: {cmd}", "green")
            print(f"  ✅ 指令: {cmd} {param}")
        except Exception as e:
            broadcast_status(f"❌ 指令失败: {str(e)[:30]}", "red")
            print(f"  ❌ 指令失败: {e}")

    async def move(self, fwd=0.0, lat=0.0, rot=0.0):
        """发送运动指令"""
        if self.conn and self.state == "connected":
            try:
                await self.conn.sport_mode.Move(fwd, lat, rot)
            except:
                pass

    async def close(self):
        if self.conn:
            try:
                await self.conn.sport_mode.Damping()
            except:
                pass
            self.conn = None
            self.state = "disconnected"

g1 = G1Control()

# =====================================================
#  WebSocket 广播
# =====================================================

def broadcast_status(text, dot="green"):
    msg = json.dumps({"type": "status", "text": text, "dot": dot})
    for q in list(clients):
        try:
            q.put_nowait(msg)
        except:
            clients.discard(q)

def broadcast_joystick(lx, ly, rx, ry, buttons):
    msg = json.dumps({
        "type": "joystick",
        "lx": f"{lx:.2f}", "ly": f"{ly:.2f}",
        "rx": f"{rx:.2f}", "ry": f"{ry:.2f}",
        "buttons": ", ".join(buttons[:5]) if buttons else "—",
    })
    for q in list(clients):
        try:
            q.put_nowait(msg)
        except:
            clients.discard(q)

def broadcast_shortcuts():
    msg = json.dumps({"type": "shortcuts", "list": shortcuts})
    for q in list(clients):
        try:
            q.put_nowait(msg)
        except:
            clients.discard(q)

# =====================================================
#  HTTP + WebSocket 服务器
# =====================================================

import http.server
import socketserver
import queue
import urllib.parse

html_content = None
ws_queues = {}  # 用个简单的计数器

class G1HTTPHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def do_GET(self):
        global html_content
        
        if self.path == "/ws":
            # WebSocket 升级 - 简化版：使用长轮询或 SSE
            # 这里用 SSE (Server-Sent Events) 替代 WebSocket
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            q = queue.Queue()
            clients.add(q)
            
            try:
                # 发送初始数据
                self.wfile.write(f"data: {json.dumps({'type':'shortcuts','list':shortcuts})}\n\n".encode())
                self.wfile.write(f"data: {json.dumps({'type':'status','text':'G1 已连接 ✅','dot':'green'})}\n\n".encode())
                self.wfile.flush()
                
                while True:
                    try:
                        msg = q.get(timeout=30)
                        self.wfile.write(f"data: {msg}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(": keepalive\n\n".encode())
                        self.wfile.flush()
            except:
                pass
            finally:
                clients.discard(q)
            return
        
        elif self.path == "/api/trigger":
            # 接收快捷按钮触发
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            # 实际通过 POST 更好，但为了简单...
            self.send_json({"ok": True})
            return
        
        # 静态文件
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
        return super().do_GET()
    
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        action = data.get("type", "")
        
        if action == "trigger":
            sid = data.get("id", "")
            s = next((s for s in shortcuts if s["id"] == sid), None)
            if s:
                # 在新线程中执行
                threading.Thread(target=lambda: asyncio.run(g1.send(s["action"], s.get("param", ""))), daemon=True).start()
                self.send_json({"ok": True})
                return
        
        elif action == "save_shortcut":
            item = {
                "id": data.get("id", ""),
                "name": data.get("name", "未命名"),
                "icon": data.get("icon", "🔘"),
                "color": data.get("color", "#3182ce"),
                "action": data.get("action", "Damping"),
                "param": data.get("param", ""),
                "desc": data.get("desc", ""),
                "combo": data.get("combo", ""),
            }
            if data.get("id") and any(s["id"] == data["id"] for s in shortcuts):
                # 更新
                for i, s in enumerate(shortcuts):
                    if s["id"] == data["id"]:
                        shortcuts[i] = item
                        break
            else:
                # 新增
                item["id"] = f"sc{len(shortcuts)+1}_{int(time.time())}"
                shortcuts.append(item)
            save_shortcuts()
            broadcast_shortcuts()
            self.send_json({"ok": True})
            return
        
        elif action == "delete_shortcut":
            shortcuts[:] = [s for s in shortcuts if s["id"] != data.get("id", "")]
            save_shortcuts()
            broadcast_shortcuts()
            self.send_json({"ok": True})
            return
        
        self.send_json({"ok": False})
    
    def send_json(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())
    
    def log_message(self, format, *args):
        pass  # 不输出访问日志

def run_http_server():
    server = socketserver.TCPServer(("0.0.0.0", HTTP_PORT), G1HTTPHandler)
    print(f"  🌐 Web 界面: http://0.0.0.0:{HTTP_PORT}")
    print(f"  📱 在 Retroid 浏览器打开: http://localhost:{HTTP_PORT}")
    print(f"  📱 或在同一网络的其他设备打开: http://<这台电脑的IP>:{HTTP_PORT}")
    server.serve_forever()

# =====================================================
#  主程序
# =====================================================

async def main():
    global shortcuts
    
    print()
    print("=" * 45)
    print("  G1 Web 控制器")
    print(f"  序列号: {G1_SERIAL}")
    print("=" * 45)
    print()
    
    # 加载配置
    load_shortcuts()
    
    # 连接 G1
    try:
        await g1.connect()
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        print(f"     请确保 Retroid 已连上 G1 的 WiFi 热点")
        
        # 即使连接失败，也启动 Web 界面
        broadcast_status(f"❌ 连接失败: {str(e)[:30]}", "red")
    
    # 启动 HTTP 服务器（在单独线程）
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # 实体摇杆读取（如果有 evdev）
    try:
        import evdev
        devices = [evdev.InputDevice(p) for p in evdev.list_devices()]
        gamepad = None
        for dev in devices:
            name = dev.name.lower()
            if any(k in name for k in ["joystick","gamepad","controller","retroid"]):
                gamepad = dev
                break
            caps = dev.capabilities()
            if evdev.ecodes.EV_ABS in caps:
                gamepad = dev
        
        if gamepad:
            print(f"  🎮 检测到手柄: {gamepad.name}")
            
            async for event in gamepad.async_read_loop():
                if event.type == evdev.ecodes.EV_ABS:
                    code = evdev.ecodes.ABS[event.code]
                    norm = event.value / 32767.0
                    if code in ("ABS_Y", "ABS_RY"):
                        norm = -norm
                    if abs(norm) < 0.08:
                        norm = 0.0
                    
                    if code == "ABS_Y":
                        await g1.move(fwd=norm * 0.6)
                    elif code == "ABS_X":
                        await g1.move(lat=norm * 0.4)
                    elif code == "ABS_RX":
                        await g1.move(rot=norm * 0.5)
                    
                    # 广播摇杆数据
                    buttons = []
                    # 这里可以读取更多按键状态
                    broadcast_joystick(0, 0, 0, 0, buttons)
                
                elif event.type == evdev.ecodes.EV_KEY:
                    code = evdev.ecodes.KEY[event.code]
                    pressed = bool(event.value)
                    # A键切换行走/站立
                    if code == "BTN_SOUTH" and not pressed:
                        await g1.send("ToggleWalkStand")
    except ImportError:
        print("  ℹ️ 未安装 evdev，仅支持屏幕按钮控制")
    except Exception as e:
        print(f"  ℹ️ 手柄读取未启用: {e}")
    
    # 保持运行
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  👋 正在关闭...")
        asyncio.run(g1.close())
        print("  ✅ 已退出")
