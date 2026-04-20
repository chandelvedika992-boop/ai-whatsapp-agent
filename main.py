from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
import requests
from urllib.parse import parse_qs
import datetime

app = FastAPI()

# 🔐 ENV VARIABLES
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SHEETDB_URL = os.getenv("SHEETDB_URL")

# 🧠 MEMORY STORE (MULTI-USER SUPPORT)
user_states = {}

# 📊 SAVE TO GOOGLE SHEETS
def save_to_sheets(name, location, budget, interest, number):
    data = {
        "data": [
            {
                "name": name,
                "location": location,
                "budget": budget,
                "interest": interest,
                "user_id": number,
                "timestamp": str(datetime.datetime.now())
            }
        ]
    }

    try:
        response = requests.post(SHEETDB_URL, json=data)
        print("Sheet response:", response.text)
    except Exception as e:
        print("Sheet save error:", e)


# 🤖 AI FUNCTION (fallback)
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

    # 🔥 SAFE PARSING
    body = await request.body()
    data = body.decode()
    parsed = parse_qs(data)

    user_message = parsed.get("Body", [""])[0].strip()
    user_number = parsed.get("From", [""])[0]

    print(f"User: {user_number} | Message: {user_message}")
    print("Current states:", user_states)  # 👈 shows multi-user handling

    # 🔄 RESET FLOW
    if user_message.lower() in ["hi", "hello", "hey", "start"]:
        user_states[user_number] = {"stage": "ask_name"}
        return PlainTextResponse(
            "<Response><Message>Hi! What's your name?</Message></Response>",
            media_type="application/xml"
        )

    # 🧠 INIT USER STATE
    if user_number not in user_states:
        user_states[user_number] = {"stage": "ask_name"}

    state = user_states[user_number]

    # 🪜 FLOW LOGIC

    # 👉 NAME
    if state["stage"] == "ask_name":
        if not user_message:
            reply = "Please tell me your name 😊"
        else:
            state["name"] = user_message
            state["stage"] = "ask_location"
            reply = f"Nice to meet you, {user_message}! Which city are you looking in? 📍"

    # 👉 LOCATION
    elif state["stage"] == "ask_location":
        if not user_message:
            reply = "Please tell me the city 📍"
        else:
            state["location"] = user_message
            state["stage"] = "ask_budget"
            reply = "Great! What's your budget range? 💰"

    # 👉 BUDGET
    elif state["stage"] == "ask_budget":
        if not user_message:
            reply = "Please share your budget 💰"
        else:
            state["budget"] = user_message
            state["stage"] = "ask_interest"
            reply = "Nice! What type of property are you looking for?"

    # 👉 INTEREST
    elif state["stage"] == "ask_interest":
        if not user_message:
            reply = "Please tell me property type 🏠"
        else:
            state["interest"] = user_message

            # 📊 SAVE DATA
            save_to_sheets(
                state.get("name"),
                state.get("location"),
                state.get("budget"),
                state.get("interest"),
                user_number
            )

            state["stage"] = "completed"

            reply = "Perfect! Our team will contact you shortly. 😊\n\nType 'Hi' to start again."

    # 👉 COMPLETED
    elif state["stage"] == "completed":
        reply = "Type 'Hi' to start a new conversation 😊"

    # 👉 AI FALLBACK
    else:
        reply = get_ai_reply(user_message)

    # 📤 TWILIO XML RESPONSE
    return PlainTextResponse(
        f"<Response><Message>{reply}</Message></Response>",
        media_type="application/xml"
    )