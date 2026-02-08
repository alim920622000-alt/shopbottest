import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

CANCEL_WINDOW_MINUTES = 10

def _parse_ids(value: str) -> set[int]:
    if not value:
        return set()
    return {int(x.strip()) for x in value.split(",") if x.strip().isdigit()}

@dataclass(frozen=True)
class Settings:
    bot_token: str
    superadmin_ids: set[int]
    admin_ids: set[int]
    db_path: str

def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is empty. Put it into .env or environment variables.")

    return Settings(
        bot_token=token,
        superadmin_ids=_parse_ids(os.getenv("SUPERADMIN_IDS", "")),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
        db_path=os.getenv("DB_PATH", "shop.db"),
    )
