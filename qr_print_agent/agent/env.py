import os
from dotenv import load_dotenv

load_dotenv()  # lee .env del cwd

PRINT_AGENT_TOKEN = os.getenv("PRINT_AGENT_TOKEN", "")
AGENT_ID = os.getenv("AGENT_ID", "agent-unknown")
AGENT_NAME = os.getenv("AGENT_NAME", AGENT_ID)
AGENT_PORT = int(os.getenv("AGENT_PORT", "9001"))

AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "./logs/audit.jsonl")

QUEUE_MAX = int(os.getenv("QUEUE_MAX", "200"))
RETRY_MAX = int(os.getenv("RETRY_MAX", "3"))
RETRY_BASE_SECONDS = float(os.getenv("RETRY_BASE_SECONDS", "1.0"))
