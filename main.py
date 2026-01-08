import uvicorn
from db_utils import init_db
from dotenv import load_dotenv
import os

# Load environment variables first
load_dotenv()

# Initialize database
init_db()

if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "3003"))

    print(f"Starting Discord Bot Web Panel on http://{host}:{port}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "web_app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
