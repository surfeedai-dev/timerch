import json
import shutil
from pathlib import Path

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "타임캐릭터"
CONFIG_FILE = APP_SUPPORT / "config.json"
CHAR_FILE   = APP_SUPPORT / "character.png"
LOG_FILE    = APP_SUPPORT / "log.json"

DEFAULTS = {
    "hourly_rate": 10320,
    "character_path": str(CHAR_FILE),
    "level": 0,
}


def load():
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    if not CHAR_FILE.exists():
        src = Path(__file__).parent / "캐릭터예시.jpg"
        if src.exists():
            shutil.copy(src, CHAR_FILE)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            pass
    save(DEFAULTS.copy())
    return DEFAULTS.copy()


def load_log() -> dict:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_log(log: dict):
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save(cfg: dict):
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
