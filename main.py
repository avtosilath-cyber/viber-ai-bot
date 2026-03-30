import os
from fastapi import FastAPI, Request
import requests

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        requests.post(f"{URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": f"Ты написал: {text}"
        })

    return {"ok": True}
