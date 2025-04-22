import sys
import queue

from PyQt6.QtWidgets import QApplication

from tracker import TimeTracker
from overlay import OverlayWindow
from browser_watcher import BrowserWatcher


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tracker = TimeTracker()
    message_queue = queue.Queue()

    overlay = OverlayWindow(tracker, message_queue)
    overlay.show()

    watcher = BrowserWatcher(message_queue)
    watcher.start()

    def on_quit():
        tracker.save_session()
        watcher.stop()

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
