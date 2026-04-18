from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
import requests
from urllib.parse import parse_qs

app = FastAPI()

# 🔐 ENV VARIABLES
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SHEETDB_URL = os.getenv("SHEETDB_URL")

# 🧠 MEMORY STORE
user_states = {}

# 📊 SAVE TO GOOGLE SHEETS
import datetime

def save_to_sheets(name, location, budget, interest, number):
    data = {
        "data": [
            {
                "name": name,
                "location": location,
                "budget": budget,
                "interest": interest,
                "number": number,
                "timestamp": str(datetime.datetime.now())
            }
        ]
    }

    try:
        requests.post(SHEETDB_URL, json=data)
    except Exception as e:
        print("Sheet save error:", e)

# 🤖 AI FUNCTION
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

    # 🔄 RESET FLOW IF USER SAYS HI
    if user_message.lower() in ["hi", "hello", "hey", "start"]:
        user_states[user_number] = {"stage": "ask_name"}
        return PlainTextResponse(
            "<Response><Message>Hi! What's your name?</Message></Response>",
            media_type="application/xml"
        )

    # 🧠 INIT STATE
    if user_number not in user_states:
        user_states[user_number] = {"stage": "ask_name"}

    state = user_states[user_number]

    # 🪜 FLOW LOGIC

@app.post("/webhook")
async def whatsapp_webhook(request: Request):

    body = await request.body()
    data = body.decode()
    parsed = parse_qs(data)

    user_message = parsed.get("Body", [""])[0].strip()
    user_number = parsed.get("From", [""])[0]

    print(f"User: {user_number} | Message: {user_message}")

    # 🔄 RESET FLOW
    if user_message.lower() in ["hi", "hello", "hey", "start"]:
        user_states[user_number] = {"stage": "ask_name"}
        return PlainTextResponse(
            "<Response><Message>Hi! What's your name?</Message></Response>",
            media_type="application/xml"
        )

    # 🧠 INIT
    if user_number not in user_states:
        user_states[user_number] = {"stage": "ask_name"}

    state = user_states[user_number]

    # 🪜 FLOW

    if state["stage"] == "ask_name":
        state["name"] = user_message
        state["stage"] = "ask_location"
        reply = "Nice to meet you! Which city are you looking in? 📍"

    elif state["stage"] == "ask_location":
        state["location"] = user_message
        state["stage"] = "ask_budget"
        reply = "Great! What's your budget range? 💰"

    elif state["stage"] == "ask_budget":
        state["budget"] = user_message
        state["stage"] = "ask_interest"
        reply = "Nice! What type of property are you looking for?"

    elif state["stage"] == "ask_interest":
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

    elif state["stage"] == "completed":
        reply = "Type 'Hi' to start a new conversation 😊"

    else:
        reply = get_ai_reply(user_message)

    return PlainTextResponse(
        f"<Response><Message>{reply}</Message></Response>",
        media_type="application/xml"
    )