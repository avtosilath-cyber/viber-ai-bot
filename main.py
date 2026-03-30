@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()

    message = data.get("message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    requests.post(f"{URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": f"Ты написал: {text}"
    })

    return {"ok": True}
