"""
G1 Controller - 安卓 APK 入口
==============================
这是一个 Kivy 应用，打包成 APK ��：
1. 启动内置的 Web 服务器（同 server.py）
2. 自动打开浏览器显示控制界面
"""

import os
import sys
import threading
import webbrowser

# Kivy 导入
os.environ["KIVY_NO_CONSOLELOG"] = "1"
import kivy
kivy.require("2.2.0")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window

# 设置窗口
Window.clearcolor = (0.1, 0.1, 0.18, 1)

# ===== 内嵌服务器（从 server.py 提取） =====

AES_KEY = "c48cc7b7edc6191f2b393f6990848cbc"
HTTP_PORT = 8888
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

# 导入服务器模块
sys.path.insert(0, CONFIG_DIR)
import server as web_server


class G1App(App):
    """G1 控制器 APK 入口"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = "G1 Controller"
        self.server_thread = None
        self.server_running = False

    def build(self):
        layout = BoxLayout(orientation="vertical", padding=dp(30), spacing=dp(20))

        # 标题
        title = Label(
            text="🤖 G1 控制器",
            font_size=dp(28),
            color=(1, 1, 1, 1),
            size_hint_y=0.3,
        )
        layout.add_widget(title)

        # 状态
        self.status_label = Label(
            text="正在启动服务器...",
            font_size=dp(16),
            color=(0.6, 0.6, 0.65, 1),
            size_hint_y=0.2,
        )
        layout.add_widget(self.status_label)

        # URL 显示
        self.url_label = Label(
            text="",
            font_size=dp(14),
            color=(0.3, 0.6, 1, 1),
            size_hint_y=0.15,
        )
        layout.add_widget(self.url_label)

        # 打开浏览器按钮
        self.open_btn = Button(
            text="🌐 打开控制界面",
            font_size=dp(18),
            size_hint_y=0.15,
            background_normal="",
            background_color=(0.1, 0.45, 0.9, 1),
            color=(1, 1, 1, 1),
            disabled=True,
        )
        self.open_btn.bind(on_release=self.open_browser)
        layout.add_widget(self.open_btn)

        # 提示
        hint = Label(
            text="首次启动后，可将控制界面添加到桌面",
            font_size=dp(11),
            color=(0.4, 0.4, 0.45, 1),
            size_hint_y=0.1,
        )
        layout.add_widget(hint)

        # 启动服务器
        Clock.schedule_once(lambda dt: self.start_server(), 0.5)

        return layout

    def start_server(self):
        """在后台线程中启动 Web 服务器"""
        def run():
            try:
                # 加载快捷按钮配置
                web_server.load_shortcuts()

                # 启动 HTTP 服务器
                from http.server import HTTPServer
                from socketserver import TCPServer

                server = TCPServer(("0.0.0.0", HTTP_PORT), web_server.G1HTTPHandler)
                self.server_running = True

                Clock.schedule_once(lambda dt: self.on_server_ready(), 0)
                server.serve_forever()
            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.on_server_error(str(e)), 0
                )

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()

    def on_server_ready(self):
        self.status_label.text = "✅ 服务器已就绪"
        self.url_label.text = f"http://localhost:{HTTP_PORT}"
        self.open_btn.disabled = False

    def on_server_error(self, error):
        self.status_label.text = f"❌ 启动失败"
        self.url_label.text = str(error)[:40]

    def open_browser(self, btn=None):
        """打开浏览器"""
        webbrowser.open(f"http://localhost:{HTTP_PORT}")

    def on_stop(self):
        """退出时清理"""
        # 服务器线程是 daemon 的，会自动退出
        pass


if __name__ == "__main__":
    G1App().run()
