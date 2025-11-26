import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("MY_POSTGRES_HOST", "localhost")
    POSTGRES_DB: str = os.getenv("MY_POSTGRES_DB", "mail")
    POSTGRES_USER: str = os.getenv("MY_POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("MY_POSTGRES_PASSWORD", "")
    POSTGRES_PORT: int = int(os.getenv("MY_POSTGRES_PORT", "5432"))

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("MY_GEMINI_API_KEY", "")

    # Naver
    NAVER_EMAIL: str = os.getenv("MY_NAVER_EMAIL", "")
    NAVER_NAME: str = os.getenv("MY_NAVER_NAME", "")

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
