import os
import requests
from bs4 import BeautifulSoup
import json

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"

URLS = {
    "Claude Apps": "https://docs.anthropic.com/en/release-notes/claude-apps",
    "Claude Platform": "https://docs.anthropic.com/en/release-notes/overview"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message
    })

def get_latest(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        if "," in line:  # غالبًا سطر التاريخ
            title = lines[i + 1] if i + 1 < len(lines) else "Unknown"
            return title

    return None

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def main():
    old_state = load_state()
    new_state = {}
    messages = []

    for name, url in URLS.items():
        latest = get_latest(url)
        new_state[name] = latest

        if old_state.get(name) != latest:
            messages.append(f"🔔 تحديث جديد في {name}\n{latest}\n{url}")

    if messages:
        send_telegram("\n\n".join(messages))

    save_state(new_state)

if __name__ == "__main__":
    main()
