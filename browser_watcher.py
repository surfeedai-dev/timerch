import subprocess
import threading
import time

BROWSER_SCRIPTS = {
    "Google Chrome": 'tell application "Google Chrome" to get URL of active tab of front window',
    "Arc":           'tell application "Arc" to get URL of active tab of front window',
    "Safari":        'tell application "Safari" to get URL of current tab of front window',
}


def get_active_url():
    for script in BROWSER_SCRIPTS.values():
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    return None


class BrowserWatcher:
    def __init__(self, message_queue, watch_sites: list = None):
        self.message_queue = message_queue
        self._lock = threading.Lock()
        self._sites: list = list(watch_sites or [])
        self._state: dict = {}   # domain → {"start": float, "notified": bool}
        self._running = False

    def update_sites(self, watch_sites: list):
        with self._lock:
            self._sites = list(watch_sites)
            self._state.clear()

    def start(self):
        self._running = True
        threading.Thread(target=self._watch, daemon=True).start()

    def stop(self):
        self._running = False

    def _watch(self):
        while self._running:
            url = get_active_url()
            now = time.time()

            with self._lock:
                sites = list(self._sites)

            for site in sites:
                domain = site.get("domain", "")
                if not domain:
                    continue
                delay = site.get("delay_minutes", 20) * 60
                msg   = site.get("message", f"{domain} 열려 있어! 😅")
                active = bool(url and domain in url)

                if active:
                    st = self._state.setdefault(
                        domain, {"start": now, "notified": False})
                    if not st["notified"] and now - st["start"] >= delay:
                        self.message_queue.put(msg)
                        st["notified"] = True
                else:
                    # 탭을 닫으면 상태 초기화 → 다시 열면 타이머 재시작
                    self._state.pop(domain, None)

            time.sleep(10)
