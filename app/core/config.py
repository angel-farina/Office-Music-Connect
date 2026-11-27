import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_host: str
    app_port: int
    app_env: str
    app_secret_key: str
    app_access_token: str
    chrome_cdp_url: str
    chrome_auto_launch: bool
    chrome_executable: str
    chrome_user_data_dir: Path
    chrome_music_url: str
    main_tab_url: str
    database_path: Path
    log_level: str
    device_name: str


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Office Music Connect"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8080")),
        app_env=os.getenv("APP_ENV", "development"),
        app_secret_key=os.getenv("APP_SECRET_KEY", ""),
        app_access_token=os.getenv("APP_ACCESS_TOKEN", ""),
        chrome_cdp_url=os.getenv("CHROME_CDP_URL", "http://127.0.0.1:9222"),
        chrome_auto_launch=os.getenv("CHROME_AUTO_LAUNCH", "true").lower() in {"1", "true", "yes", "on"},
        chrome_executable=os.getenv("CHROME_EXECUTABLE", ""),
        chrome_user_data_dir=Path(os.getenv("CHROME_USER_DATA_DIR", "./chrome-profile")),
        chrome_music_url=os.getenv("CHROME_MUSIC_URL", "https://music.youtube.com/"),
        main_tab_url=os.getenv(
            "MAIN_TAB_URL",
            os.getenv("UPTIME_KUMA_URL", "https://example.com/"),
        ),
        database_path=Path(os.getenv("DATABASE_PATH", "./data/music_connect.db")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        device_name=os.getenv("DEVICE_NAME", "Office Music Connect"),
    )
