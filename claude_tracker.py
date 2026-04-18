import os
import requests
from bs4 import BeautifulSoup

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

URLS = {
    "Claude Apps": "https://docs.anthropic.com/en/release-notes/claude-apps",
    "Claude Platform": "https://docs.anthropic.com/en/release-notes/overview"
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )
    response.raise_for_status()

def get_latest_title(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if "Claude" in line or "release" in line.lower() or "update" in line.lower():
            return line

    return "وجد تحديث محتمل، لكن تعذر استخراج العنوان بدقة"

def main():
    messages = []
    for name, url in URLS.items():
        try:
            title = get_latest_title(url)
            messages.append(f"🔔 {name}\n{title}\n{url}")
        except Exception as e:
            messages.append(f"⚠️ {name}\nحدث خطأ أثناء الفحص:\n{e}")

    final_message = "\n\n".join(messages)
    send_telegram(final_message)

if __name__ == "__main__":
    main()
