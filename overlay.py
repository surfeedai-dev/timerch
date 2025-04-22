import math
import queue
import ctypes
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QAction
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication, QMenu


def _apply_overlay_level(ns_window):
    """NSWindow 레벨과 CollectionBehavior 적용."""
    try:
        from Quartz import CGWindowLevelForKey, kCGMaximumWindowLevelKey
        max_level = CGWindowLevelForKey(kCGMaximumWindowLevelKey)
    except Exception:
        max_level = 2147483631  # kCGMaximumWindowLevelKey fallback

    ns_window.setLevel_(max_level)
    # CanJoinAllSpaces(1) | Stationary(16) 만 사용
    # FullScreenAuxiliary(256)는 오히려 fullscreen Space에서 제외시키므로 제거
    ns_window.setCollectionBehavior_(1 | 16)
    ns_window.orderFrontRegardless()


def _set_macos_fullscreen_overlay(win_id: int):
    try:
        import objc
        ns_view = objc.objc_object(c_void_p=ctypes.c_void_p(win_id))
        ns_window = ns_view.window()
        _apply_overlay_level(ns_window)
        return ns_window
    except Exception:
        return None


class SpeechBubble(QWidget):
    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background-color: white;
                border-radius: 14px;
                border: 2px solid #e0e0e0;
                padding: 10px 16px;
                font-size: 13px;
                color: #333;
                font-family: -apple-system, sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(self, text, pos, duration_ms=8000):
        self.label.setText(text)
        self.adjustSize()
        self.move(pos)
        self.show()
        _set_macos_fullscreen_overlay(int(self.winId()))
        self._hide_timer.start(duration_ms)


class OverlayWindow(QWidget):
    def __init__(self, tracker, message_queue: queue.Queue):
        super().__init__()
        self.tracker = tracker
        self.message_queue = message_queue

        self._drag_pos = None
        self._bob_time = 0.0
        self._base_y = 0
        self._ns_window = None

        self._setup_window()
        self._setup_ui()
        self._setup_timers()
        self._bubble = SpeechBubble()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(180)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.char_label = QLabel()
        self.char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_character()
        layout.addWidget(self.char_label)

        self.earnings_label = QLabel()
        self.earnings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.earnings_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 170);
                color: #FFD700;
                font-size: 13px;
                font-weight: bold;
                border-radius: 10px;
                padding: 4px 12px;
                font-family: -apple-system, sans-serif;
            }
        """)
        layout.addWidget(self.earnings_label)

        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 120);
                color: #cccccc;
                font-size: 11px;
                border-radius: 8px;
                padding: 2px 8px;
                font-family: -apple-system, sans-serif;
            }
        """)
        layout.addWidget(self.time_label)

        self.adjustSize()

    def _load_character(self):
        img_path = Path(__file__).parent / "캐릭터예시.jpg"
        if img_path.exists():
            pixmap = QPixmap(str(img_path))
            pixmap = pixmap.scaled(
                140, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            # 둥근 모서리 적용
            rounded = QPixmap(pixmap.size())
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), 20, 20)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            self.char_label.setPixmap(rounded)
        else:
            self.char_label.setText("🐾")
            self.char_label.setStyleSheet("font-size: 80px;")

    def _setup_timers(self):
        update_timer = QTimer(self)
        update_timer.timeout.connect(self._update_display)
        update_timer.start(1000)

        bob_timer = QTimer(self)
        bob_timer.timeout.connect(self._bob)
        bob_timer.start(50)

        queue_timer = QTimer(self)
        queue_timer.timeout.connect(self._check_message_queue)
        queue_timer.start(500)

        # 전체화면 전환 시 레벨이 리셋되므로 2초마다 재적용
        overlay_timer = QTimer(self)
        overlay_timer.timeout.connect(self._reapply_overlay)
        overlay_timer.start(2000)

    def show(self):
        super().show()
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 80
        self.move(x, y)
        self._base_y = y
        self._ns_window = _set_macos_fullscreen_overlay(int(self.winId()))

    def _reapply_overlay(self):
        if self._ns_window is not None:
            try:
                _apply_overlay_level(self._ns_window)
            except Exception:
                self._ns_window = _set_macos_fullscreen_overlay(int(self.winId()))

    def _update_display(self):
        self.earnings_label.setText(f"💰 {self.tracker.format_earnings()}")
        self.time_label.setText(f"⏱ {self.tracker.format_time()}")

    def _bob(self):
        if self._drag_pos is not None:
            return
        self._bob_time += 0.08
        offset = int(math.sin(self._bob_time) * 3)
        self.move(self.pos().x(), self._base_y + offset)

    def _check_message_queue(self):
        try:
            msg = self.message_queue.get_nowait()
            self.show_bubble(msg)
        except queue.Empty:
            pass

    def show_bubble(self, text):
        pos = self.pos()
        bubble_pos = QPoint(pos.x() - 10, pos.y() - 90)
        self._bubble.show_message(text, bubble_pos)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: white; border-radius: 8px; }")
        quit_action = QAction("타임캐릭터 종료", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            self._base_y = new_pos.y()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
