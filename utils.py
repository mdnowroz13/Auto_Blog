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

logger = logging.getLogger(__name__)

def load_env_file(filepath='.env'):
    """Load environment variables from a .env file."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Load env vars immediately
load_env_file()

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

def query_huggingface(prompt, token, model="facebook/bart-large-cnn", max_retries=3):
    """Query HuggingFace Inference API."""
    import requests
    headers = {"Authorization": f"Bearer {token}"}
    api_url = f"https://router.huggingface.co/hf-inference/models/{model}"
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 300, "do_sample": False}
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('summary_text') or result[0].get('generated_text')
                elif isinstance(result, dict) and 'generated_text' in result:
                     return result['generated_text']
            else:
                logger.warning(f"HF Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"HF Request failed: {e}")
        time.sleep(2)
    return None

def generate_analytics_report(history_file='history.json', output_file='dashboard.html'):
    """Generate a simple HTML analytics dashboard."""
    history = load_history(history_file)
    if not history:
        return
        
    total_posts = len(history)
    last_run = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Auto-Blogger Analytics</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .card {{ background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #007bff; color: white; }}
            tr:hover {{ background-color: #f1f1f1; }}
            a {{ color: #007bff; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>Auto-Blogger Dashboard</h1>
        <div class="card">
            <h2>Overview</h2>
            <p><strong>Total Posts:</strong> {total_posts}</p>
            <p><strong>Last Run:</strong> {last_run}</p>
        </div>
        
        <div class="card">
            <h2>Publication History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Topic</th>
                        <th>URL</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Sort by date desc
    sorted_history = sorted(history, key=lambda x: x.get('date', ''), reverse=True)
    
    for entry in sorted_history:
        url = entry.get('url', '#')
        link = f"<a href='{url}' target='_blank'>View Post</a>" if url != "URL_PLACEHOLDER" else "Pending"
        html += f"""
                    <tr>
                        <td>{entry.get('date', 'N/A')}</td>
                        <td>{entry.get('topic', 'N/A')}</td>
                        <td>{link}</td>
                    </tr>
        """
        
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    
    with open(output_file, 'w') as f:
        f.write(html)
    logger.info(f"Dashboard generated: {output_file}")
