from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


load_environment()
