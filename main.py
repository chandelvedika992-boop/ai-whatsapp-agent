from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
import requests
from urllib.parse import parse_qs

app = FastAPI()

# 🔐 ENV VARIABLES
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SHEETDB_URL = os.getenv("SHEETDB_URL")

# 🧠 MEMORY STORE (simple)
user_states = {}

# 📊 SAVE TO GOOGLE SHEETS
def save_to_sheets(name, location, interest, number):
    data = {
        "data": [
            {
                "name": name,
                "location": location,
                "interest": interest,
                "number": number
            }
        ]
    }

    try:
        requests.post(SHEETDB_URL, json=data)
    except Exception as e:
        print("Sheet save error:", e)


# 🧠 AI FUNCTION (OpenRouter)
def get_ai_reply(message):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a helpful real estate assistant."},
                    {"role": "user", "content": message}
                ]
            }
        )

        return response.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("AI error:", e)
        return "Sorry, something went wrong."


# 🏠 ROOT CHECK
@app.get("/")
def home():
    return {"message": "Server is running 🚀"}


# 📩 WHATSAPP WEBHOOK
@app.post("/webhook")
async def whatsapp_webhook(request: Request):

    # 🔥 FIXED: manual parsing (NO crash)
    body = await request.body()
    data = body.decode()

    parsed = parse_qs(data)

    user_message = parsed.get("Body", [""])[0]
    user_number = parsed.get("From", [""])[0]

    print(f"User: {user_number} | Message: {user_message}")

    # 🧠 USER STATE FLOW
    if user_number not in user_states:
        user_states[user_number] = {"stage": "ask_name"}

    state = user_states[user_number]

    # 🪜 FLOW LOGIC

    if state["stage"] == "ask_name":
        state["stage"] = "ask_location"
        state["name"] = user_message
        reply = "Nice to meet you! Which city are you looking to buy in?"

    elif state["stage"] == "ask_location":
        state["stage"] = "ask_interest"
        state["location"] = user_message
        reply = "Great! What kind of property are you interested in?"

    elif state["stage"] == "ask_interest":
        state["interest"] = user_message

        # 📊 SAVE DATA
        save_to_sheets(
            state.get("name"),
            state.get("location"),
            state.get("interest"),
            user_number
        )

        state["stage"] = "done"

        reply = "Awesome! Our team will contact you shortly. 😊"

    else:
        # 🤖 AI fallback
        reply = get_ai_reply(user_message)

    # 📤 TWILIO XML RESPONSE (VERY IMPORTANT)
    return PlainTextResponse(
        f"<Response><Message>{reply}</Message></Response>",
        media_type="application/xml"
    )