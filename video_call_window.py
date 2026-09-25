import sys
import cv2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QFrame, QTextEdit, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont


class VideoCallWindow(QWidget):
    end_call_signal = pyqtSignal()
    toggle_cam_signal = pyqtSignal(bool)
    toggle_mic_signal = pyqtSignal(bool)
    hold_call_signal = pyqtSignal(bool)
    invite_user_signal = pyqtSignal()
    send_message_signal = pyqtSignal(str)

    def __init__(self, target_username="المتصل", target_ip="", avatar_pixmap=None):
        super().__init__()
        self.target_username = target_username
        self.target_ip = target_ip
        self.avatar_pixmap = avatar_pixmap
        
        self.is_cam_on = True
        self.is_mic_on = True
        self.is_on_hold = False
        self.is_chat_visible = False

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"مكالمة مع {self.target_username}")
        self.resize(1150, 680)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("background-color: #121212; color: #FFFFFF;")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # 1. شاشة عرض الفيديو
        self.video_container = QFrame()
        self.video_container.setStyleSheet("background-color: #1E1E1E; border-radius: 15px; border: 1px solid #00FFCC;")
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)

        self.video_label = QLabel("جاري انتظار بث الفيديو...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFont(QFont("Segoe UI", 14))
        self.video_label.setStyleSheet("color: #888888;")
        video_layout.addWidget(self.video_label)

        main_layout.addWidget(self.video_container, stretch=3)

        # 2. لوحة الدردشة الجانبية
        self.chat_panel = QFrame()
        self.chat_panel.setFixedWidth(280)
        self.chat_panel.setStyleSheet("background-color: #1A1A24; border-radius: 15px; border: 1px solid #2D2D3F;")
        self.chat_panel.setVisible(False)
        
        chat_layout = QVBoxLayout(self.chat_panel)
        chat_layout.setContentsMargins(10, 10, 10, 10)

        chat_title = QLabel("💬 الدردشة المباشرة")
        chat_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        chat_title.setAlignment(Qt.AlignCenter)
        chat_layout.addWidget(chat_title)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #121218; border: none; border-radius: 8px; color: #EEE;")
        chat_layout.addWidget(self.chat_display)

        chat_input_layout = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("اكتب رسالة...")
        self.msg_input.setStyleSheet("background-color: #2D2D3F; border: none; border-radius: 5px; padding: 5px; color: white;")
        self.msg_input.returnPressed.connect(self.on_send_msg)

        btn_send = QPushButton("ارسال")
        btn_send.setStyleSheet("background-color: #00FFCC; color: black; font-weight: bold; border-radius: 5px; padding: 5px;")
        btn_send.clicked.connect(self.on_send_msg)

        chat_input_layout.addWidget(self.msg_input)
        chat_input_layout.addWidget(btn_send)
        chat_layout.addLayout(chat_input_layout)

        main_layout.addWidget(self.chat_panel, stretch=1)

        # 3. لوحة التحكم العمودية جهة اليمين
        self.right_panel = QFrame()
        self.right_panel.setFixedWidth(260)
        self.right_panel.setStyleSheet("background-color: #1E1E2E; border-radius: 15px; border: 1px solid #3B3B54;")
        
        panel_layout = QVBoxLayout(self.right_panel)
        panel_layout.setContentsMargins(15, 20, 15, 20)
        panel_layout.setSpacing(12)

        self.avatar_label = QLabel("👤")
        self.avatar_label.setFont(QFont("Segoe UI", 42))
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.avatar_label.setFixedSize(90, 90)
        self.avatar_label.setStyleSheet("background-color: #2D2D3F; border-radius: 45px; border: 2px solid #00FFCC;")
        
        if self.avatar_pixmap and not self.avatar_pixmap.isNull():
            self.avatar_label.setPixmap(self.avatar_pixmap.scaled(90, 90, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

        self.username_label = QLabel(self.target_username)
        self.username_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.username_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("متصل الآن...")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.status_label.setAlignment(Qt.AlignCenter)

        panel_layout.addWidget(self.avatar_label, alignment=Qt.AlignCenter)
        panel_layout.addWidget(self.username_label)
        panel_layout.addWidget(self.status_label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #2D2D3F;")
        panel_layout.addWidget(line)

        # الأزرار العمودية
        self.btn_cam = self._create_button("📹  إيقاف الكاميرا", "#3B3B54", self.on_toggle_cam)
        self.btn_mic = self._create_button("🎙️  كتم المايك", "#3B3B54", self.on_toggle_mic)
        self.btn_hold = self._create_button("⏸️  تعليق المكالمة", "#3B3B54", self.on_toggle_hold)
        self.btn_chat = self._create_button("💬  فتح الرسائل", "#3B3B54", self.on_toggle_chat)
        self.btn_invite = self._create_button("➕  دعوة شخص آخر", "#2D5B88", self.on_invite)
        self.btn_end = self._create_button("🔴  إنهاء المكالمة", "#D32F2F", self.on_end_call)

        panel_layout.addWidget(self.btn_cam)
        panel_layout.addWidget(self.btn_mic)
        panel_layout.addWidget(self.btn_hold)
        panel_layout.addWidget(self.btn_chat)
        panel_layout.addWidget(self.btn_invite)
        
        panel_layout.addStretch()
        panel_layout.addWidget(self.btn_end)

        main_layout.addWidget(self.right_panel, stretch=1)

    def _create_button(self, text, bg_color, callback):
        btn = QPushButton(text)
        btn.setFixedHeight(42)
        btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border-radius: 8px;
                text-align: right;
                padding-right: 12px;
            }}
            QPushButton:hover {{
                background-color: {bg_color}DD;
                border: 1px solid #FFFFFF;
            }}
        """)
        btn.clicked.connect(callback)
        return btn

    def update_remote_frame(self, cv_frame):
        if self.is_on_hold:
            return

        rgb_image = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled_pixmap)

    def receive_chat_message(self, sender, text):
        self.chat_display.append(f"<b>{sender}:</b> {text}")

    def on_send_msg(self):
        text = self.msg_input.text().strip()
        if text:
            self.chat_display.append(f"<b>أنت:</b> {text}")
            self.send_message_signal.emit(text)
            self.msg_input.clear()

    def on_toggle_chat(self):
        self.is_chat_visible = not self.is_chat_visible
        self.chat_panel.setVisible(self.is_chat_visible)
        self.btn_chat.setText("💬  إغلاق الرسائل" if self.is_chat_visible else "💬  فتح الرسائل")

    def on_toggle_cam(self):
        self.is_cam_on = not self.is_cam_on
        self.btn_cam.setText("📹  إيقاف الكاميرا" if self.is_cam_on else "📷  تشغيل الكاميرا")
        self.toggle_cam_signal.emit(self.is_cam_on)

    def on_toggle_mic(self):
        self.is_mic_on = not self.is_mic_on
        self.btn_mic.setText("🎙️  كتم المايك" if self.is_mic_on else "🔇  تشغيل المايك")
        self.toggle_mic_signal.emit(self.is_mic_on)

    def on_toggle_hold(self):
        self.is_on_hold = not self.is_on_hold
        if self.is_on_hold:
            self.btn_hold.setText("▶️  استئناف المكالمة")
            self.status_label.setText("المكالمة معلقة...")
            self.status_label.setStyleSheet("color: #FFC107;")
            self.video_label.setPixmap(QPixmap())
            self.video_label.setText("المكالمة قيد التعليق المؤقت")
        else:
            self.btn_hold.setText("⏸️  تعليق المكالمة")
            self.status_label.setText("متصل الآن...")
            self.status_label.setStyleSheet("color: #4CAF50;")
            self.video_label.setText("جاري انتظار بث الفيديو...")
        self.hold_call_signal.emit(self.is_on_hold)

    def on_invite(self):
        self.invite_user_signal.emit()

    def on_end_call(self):
        self.end_call_signal.emit()
        self.close()