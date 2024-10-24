from typing import List

class Settings:
    PROJECT_NAME: str = "FastAPI Assistant"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DB_URL: str = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
    ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://app.kyndom.com",
    ]

settings = Settings()