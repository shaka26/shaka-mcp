import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Gnews API Key
    GNEWS_API_KEY: str = os.getenv("GNEWS_API_KEY", "")

    # Server host and port
    HOST: str = os.getenv("HOST", "localhost")
    PORT: int = int(os.getenv("PORT", 10000))

settings = Settings()