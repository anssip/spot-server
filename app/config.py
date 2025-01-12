import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    PROJECT_NAME: str = "SpotCanvas"
    PROJECT_VERSION: str = "1.0.0"

    # Coinbase API settings
    COINBASE_API_KEY: str = os.getenv("COINBASE_API_KEY", "")
    COINBASE_API_SECRET: str = os.getenv("COINBASE_PRIVATE_KEY", "")

    def validate_coinbase_settings(self):
        """Validate that required Coinbase settings are present"""
        if not self.COINBASE_API_KEY or not self.COINBASE_API_SECRET:
            raise ValueError("Please set COINBASE_API_KEY and COINBASE_PRIVATE_KEY environment variables")


settings = Settings()
