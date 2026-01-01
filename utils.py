import os
import json
import logging
import datetime
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("autoblogger.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_env(key, default=None):
    """Get environment variable or return default."""
    val = os.environ.get(key, default)
    if not val and default is None:
        logger.warning(f"Environment variable {key} not found!")
    return val

def load_history(file_path='history.json'):
    """Load publication history."""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history(history, file_path='history.json'):
    """Save publication history."""
    with open(file_path, 'w') as f:
        json.dump(history, f, indent=2)

def is_duplicate_topic(topic, history, days=7):
    """Check if topic was covered in the last N days."""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for entry in history:
        entry_date = datetime.datetime.fromisoformat(entry['date'])
        if entry['topic'].lower() == topic.lower() and entry_date > cutoff:
            return True
    return False

def random_delay(min_seconds=60, max_seconds=300):
    """Sleep for a random amount of time to mimic human behavior."""
    delay = random.randint(min_seconds, max_seconds)
    logger.info(f"Sleeping for {delay} seconds...")
    time.sleep(delay)
