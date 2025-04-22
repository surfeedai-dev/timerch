import json
import shutil
from pathlib import Path

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "타임캐릭터"
CONFIG_FILE = APP_SUPPORT / "config.json"
CHAR_FILE   = APP_SUPPORT / "character.png"

DEFAULT_SITES = [
    {"domain": "youtube.com",   "message": "유튜브 재밌어? 😄\n슬슬 일할 시간 아니야?", "delay_minutes": 20},
    {"domain": "instagram.com", "message": "인스타 보고 있어? 😅\n잠깐 쉬는 거야?",   "delay_minutes": 20},
    {"domain": "x.com",         "message": "X 보고 있어? 😅\n잠깐 쉬는 거야?",        "delay_minutes": 20},
    {"domain": "tiktok.com",    "message": "틱톡 보고 있어? 😅\n잠깐 쉬는 거야?",     "delay_minutes": 20},
    {"domain": "facebook.com",  "message": "페북 보고 있어? 😅\n잠깐 쉬는 거야?",     "delay_minutes": 20},
]

DEFAULTS = {
    "hourly_rate": 10320,
    "character_path": str(CHAR_FILE),
    "watch_sites": DEFAULT_SITES,
}


def load():
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    # 첫 실행 시 기본 캐릭터 복사
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


def save(cfg: dict):
    APP_SUPPORT.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
