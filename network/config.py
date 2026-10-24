from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

def load_properties(file_path: Path):
    props = {}
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
    return props

secrets_props = load_properties(BASE_DIR / "secrets.properties")

# Pydantic Settings for environment-based configuration
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # MongoDB Settings (for MongoDB Compass connectivity)
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "selfhealing"

    # Server settings
    server_port: int = 8080

    # Monitoring settings
    monitor_interval_ms: int = 10000
    ping_host: str = "8.8.8.8"
    ai_service_url: str = "http://localhost:8000"
    recovery_real_commands: bool = False
    healing_cooldown_ms: int = 30000

    # Mail / Notification settings
    notify_enabled: bool = True
    mail_password: str = secrets_props.get("MAIL_PASSWORD", "")
    # The receiving account is also used as the SMTP sender and login account.
    notify_to: str = secrets_props.get(
        "NOTIFY_TO", secrets_props.get("MAIL_USERNAME", "")
    )
    notify_min_gap_ms: int = 120000
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    # GNS3 settings
    gns3_enabled: bool = True
    gns3_console_host: str = "127.0.0.1"
    gns3_console_port: int = 5000
    gns3_target: str = "10.0.0.2"
    gns3_ping_count: int = 4
    gns3_max_wait_sec: int = 30

settings = Settings()

# Direct export aliases for backward compatibility across modules
MONGO_URI = settings.mongo_uri
MONGO_DB = settings.mongo_db
SERVER_PORT = settings.server_port
MONITOR_INTERVAL_MS = settings.monitor_interval_ms
PING_HOST = settings.ping_host
AI_SERVICE_URL = settings.ai_service_url
RECOVERY_REAL_COMMANDS = settings.recovery_real_commands
HEALING_COOLDOWN_MS = settings.healing_cooldown_ms
NOTIFY_ENABLED = settings.notify_enabled
MAIL_PASSWORD = settings.mail_password
# Destination address for self-healing notifications.
NOTIFY_TO = settings.notify_to
NOTIFY_MIN_GAP_MS = settings.notify_min_gap_ms
SMTP_HOST = settings.smtp_host
SMTP_PORT = settings.smtp_port
GNS3_ENABLED = settings.gns3_enabled
GNS3_CONSOLE_HOST = settings.gns3_console_host
GNS3_CONSOLE_PORT = settings.gns3_console_port
GNS3_TARGET = settings.gns3_target
GNS3_PING_COUNT = settings.gns3_ping_count
GNS3_MAX_WAIT_SEC = settings.gns3_max_wait_sec
