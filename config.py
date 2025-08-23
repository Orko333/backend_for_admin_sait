from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Order Platform Backend"
    debug: bool = True
    postgres_dsn: str = "postgresql://postgres.gggsulegkxbpfsxrjptc:Karatist2006@aws-1-eu-west-3.pooler.supabase.com:6543/postgres"
    jwt_secret: str = "CHANGE_ME_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "*"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings():
    return Settings()
