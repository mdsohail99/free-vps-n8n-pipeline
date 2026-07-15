import os, json, re, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Load .env file from same directory (no external dependencies needed)
def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            os.environ.setdefault(key, val)

load_env()
load_env(os.path.join(os.path.dirname(__file__), ".env"))

def normalize_notion_id(value):
    """Accept a raw Notion ID or URL and return the 32-character page ID."""
    value = (value or "").split("?")[0]
    compact = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(compact) < 32:
        return ""
    return compact[-32:]

NOTION_TOKEN = os.getenv("NOTION_INTEGRATION_TOKEN")
PARENT_PAGE_ID = normalize_notion_id(os.getenv("NOTION_PARENT_PAGE_ID"))

if not NOTION_TOKEN:
    print("Error: NOTION_INTEGRATION_TOKEN not set in .env")
    sys.exit(1)
if not PARENT_PAGE_ID:
    print("Error: NOTION_PARENT_PAGE_ID not set in .env")
    print("Set it to a Notion parent page URL or 32-character page ID.")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

properties = {
    "Name": {"title": {}},
    "Date": {"date": {}},
    "Category": {
        "multi_select": {
            "options": [
                {"name": "Frontier Models", "color": "blue"},
                {"name": "Open Source", "color": "green"},
                {"name": "Pricing", "color": "yellow"},
                {"name": "AI Agents", "color": "purple"},
                {"name": "Coding Tools", "color": "orange"},
                {"name": "Benchmarks", "color": "red"},
                {"name": "API Updates", "color": "pink"},
                {"name": "Promotions", "color": "brown"},
                {"name": "Local Models", "color": "gray"},
            ]
        }
    },
    "Topics": {
        "multi_select": {
            "options": [
                {"name": "Frontier Models", "color": "blue"},
                {"name": "Open Source", "color": "green"},
                {"name": "Coding", "color": "orange"},
                {"name": "Local LLMs", "color": "gray"},
                {"name": "OpenRouter", "color": "yellow"},
                {"name": "Ollama", "color": "purple"},
                {"name": "LM Studio", "color": "brown"},
                {"name": "MCP", "color": "pink"},
                {"name": "AI Agents", "color": "red"},
            ]
        }
    },
    "Providers": {
        "multi_select": {
            "options": [
                {"name": "OpenAI", "color": "green"},
                {"name": "Anthropic", "color": "purple"},
                {"name": "Google", "color": "blue"},
                {"name": "xAI", "color": "gray"},
                {"name": "Meta", "color": "blue"},
                {"name": "Alibaba", "color": "orange"},
                {"name": "DeepSeek", "color": "yellow"},
                {"name": "Mistral", "color": "pink"},
                {"name": "Microsoft", "color": "red"},
            ]
        }
    },
    "Featured Models": {
        "multi_select": {
            "options": [
                {"name": "GPT", "color": "green"},
                {"name": "Claude", "color": "purple"},
                {"name": "Gemini", "color": "blue"},
                {"name": "Grok", "color": "gray"},
                {"name": "Qwen", "color": "orange"},
                {"name": "DeepSeek", "color": "yellow"},
                {"name": "Llama", "color": "pink"},
                {"name": "Mistral", "color": "red"},
            ]
        }
    },
    "Importance": {
        "select": {
            "options": [
                {"name": "Critical", "color": "red"},
                {"name": "High", "color": "orange"},
                {"name": "Medium", "color": "yellow"},
                {"name": "Low", "color": "gray"},
            ]
        }
    },
    "Report Type": {
        "select": {
            "options": [
                {"name": "Daily", "color": "blue"},
                {"name": "Weekly", "color": "purple"},
            ]
        }
    },
    "Summary": {"rich_text": {}},
    "New Model Released": {"checkbox": {}},
    "Pricing Changed": {"checkbox": {}},
    "Open Source": {"checkbox": {}},
    "Free Promotion": {"checkbox": {}},
    "Worth Installing": {"checkbox": {}},
    "Best Coding Model": {"select": {}},
    "Best Reasoning Model": {"select": {}},
    "Best Local Model": {"select": {}},
    "Best Value API": {"select": {}},
    "Biggest Release": {"select": {}},
}

payload = {
    "parent": {"type": "page_id", "page_id": PARENT_PAGE_ID},
    "title": [{"type": "text", "text": {"content": "AI Daily Reports"}}],
    "properties": properties,
}

req = Request(
    "https://api.notion.com/v1/databases",
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
    method="POST",
)

try:
    resp = urlopen(req)
    data = json.loads(resp.read().decode("utf-8"))
    db_id = data["id"]
    url = data["url"]
    print(f"Database created successfully!")
    print(f"ID:  {db_id}")
    print(f"URL: {url}")
    print(f"\nAdd these to your .env:")
    print(f"NOTION_DATABASE_ID={db_id}")
except HTTPError as e:
    err = json.loads(e.read().decode("utf-8"))
    print(f"Error {e.code}: {err.get('message', err)}")
    sys.exit(1)
