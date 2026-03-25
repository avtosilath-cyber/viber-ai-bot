from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/")
async def webhook(req: Request):
    data = await req.json()

    user_text = data.get("message", {}).get("text", "")

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты менеджер автозапчастей. Отвечай коротко и по делу."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        }
    )

    answer = response.json()["choices"][0]["message"]["content"]

    return {
        "text": answer
    }
