import os
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFileDialog, QDialog)
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QPainterPath, QColor, QConicalGradient, QPen, QBrush

class AnimatedAvatarWidget(QWidget):
    def __init__(self, size=90, parent=None):
        super().__init__(parent)
        self.avatar_size = size
        self.setFixedSize(size + 20, size + 20)
        
        self.image_path = None
        self.pixmap = None
        
        self.angle = 0
        self.glow_alpha = 120
        self.alpha_step = 3
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_avatar_image(self, path):
        if path and os.path.exists(path):
            self.image_path = path
            self.pixmap = QPixmap(path)
            self.update()

    def update_animation(self):
        self.angle = (self.angle + 3) % 360
        self.glow_alpha += self.alpha_step
        if self.glow_alpha >= 245:
            self.glow_alpha = 245
            self.alpha_step = -3
        elif self.glow_alpha <= 60:
            self.glow_alpha = 60
            self.alpha_step = 3
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = self.avatar_size / 2.0
        border_width = 4
        
        gradient = QConicalGradient(center, self.angle)
        gradient.setColorAt(0.00, QColor(255, 0, 128, self.glow_alpha))
        gradient.setColorAt(0.25, QColor(0, 220, 255, self.glow_alpha))
        gradient.setColorAt(0.50, QColor(0, 255, 136, self.glow_alpha))
        gradient.setColorAt(0.75, QColor(255, 180, 0, self.glow_alpha))
        gradient.setColorAt(1.00, QColor(255, 0, 128, self.glow_alpha))
        
        pen = QPen(QBrush(gradient), border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius + 2, radius + 2)
        
        path = QPainterPath()
        path.addEllipse(center, radius, radius)
        painter.setClipPath(path)
        
        if self.pixmap and not self.pixmap.isNull():
            scaled_pixmap = self.pixmap.scaled(
                int(self.avatar_size), int(self.avatar_size),
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = int(center.x() - scaled_pixmap.width() / 2)
            y = int(center.y() - scaled_pixmap.height() / 2)
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            painter.fillRect(self.rect(), QColor("#1e293b"))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignCenter, "صورة")

class ProfileSettingsDialog(QDialog):
    def __init__(self, on_profile_updated_callback=None, parent=None):
        super().__init__(parent)
        self.on_profile_updated = on_profile_updated_callback
        self.setWindowTitle("تخصيص الملف الشخصي")
        self.setFixedSize(360, 320)
        self.setStyleSheet("background-color: #0f172a; color: white; font-family: Segoe UI;")
        self.setLayoutDirection(Qt.RightToLeft)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        self.avatar_widget = AnimatedAvatarWidget(size=100)
        layout.addWidget(self.avatar_widget, alignment=Qt.AlignCenter)
        
        self.btn_change_photo = QPushButton("📷 تغيير الصورة الشخصية")
        self.btn_change_photo.setStyleSheet('''
            QPushButton {
                background-color: #1e293b; color: #38bdf8; border: 1px solid #38bdf8;
                border-radius: 6px; padding: 5px 12px; font-size: 12px;
            }
            QPushButton:hover { background-color: #38bdf8; color: #0f172a; }
        ''')
        self.btn_change_photo.clicked.connect(self.select_photo)
        layout.addWidget(self.btn_change_photo, alignment=Qt.AlignCenter)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("أدخل اسمك الشخصي لتظهر للآخرين...")
        self.name_input.setStyleSheet('''
            QLineEdit {
                background-color: #1e293b; border: 1px solid #475569;
                border-radius: 8px; padding: 8px; color: white; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #38bdf8; }
        ''')
        layout.addWidget(self.name_input)
        
        self.btn_save = QPushButton("حفظ التغيرات 💾")
        self.btn_save.setStyleSheet('''
            QPushButton {
                background-color: #0284c7; color: white; border-radius: 8px;
                padding: 8px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background-color: #0369a1; }
        ''')
        self.btn_save.clicked.connect(self.save_profile)
        layout.addWidget(self.btn_save)
        
        self.setLayout(layout)
        self.load_profile()

    def select_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة شخصية", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.avatar_widget.set_avatar_image(file_path)

    def load_profile(self):
        if os.path.exists("profile_config.json"):
            try:
                with open("profile_config.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.name_input.setText(data.get("user_name", ""))
                    photo_path = data.get("photo_path", "")
                    if photo_path and os.path.exists(photo_path):
                        self.avatar_widget.set_avatar_image(photo_path)
            except Exception:
                pass

    def save_profile(self):
        user_name = self.name_input.text().strip() or "مستخدم محلي"
        photo_path = self.avatar_widget.image_path or ""
        
        profile_data = {
            "user_name": user_name,
            "photo_path": photo_path
        }
        
        with open("profile_config.json", "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=4)
            
        if self.on_profile_updated:
            self.on_profile_updated(user_name, photo_path)
            
        self.accept()