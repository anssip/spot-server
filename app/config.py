import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    PROJECT_NAME: str = "Your API"
    PROJECT_VERSION: str = "1.0.0"

    # You can add database configurations, API keys, etc. here
    # DATABASE_URL: str = os.getenv("DATABASE_URL", "")


settings = Settings()
