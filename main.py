from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
import requests
from dotenv import load_dotenv
import os

# 🔐 Load environment variables
load_dotenv()

app = FastAPI()

# 🔑 Secure keys from .env
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

SHEETDB_URL = os.getenv("SHEETDB_URL")

# 🧠 In-memory storage
user_data = {}

# 🤖 AI helper
def generate_ai_reply(prompt):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional real estate assistant. Be friendly, concise, and helpful."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("AI ERROR:", str(e))
        return "Got it! Let me help you further."


# 📥 Save to Google Sheets
def save_to_sheets(data):
    try:
        print("📤 Sending to Sheets:", data)
        response = requests.post(SHEETDB_URL, json={"data": [data]})
        print("✅ Sheet Response:", response.text)
    except Exception as e:
        print("❌ Sheet Error:", str(e))


@app.get("/")
def home():
    return {"message": "Server is running 🚀"}


@app.post("/webhook")
async def whatsapp_webhook(request: Request):

    # 🔒 Basic security check
    if "Twilio" not in request.headers.get("User-Agent", ""):
        return PlainTextResponse("Unauthorized", status_code=403)

    form = await request.form()
    form_data = dict(form)

    user_message = form_data.get("Body", "").strip()
    user_number = form_data.get("From", "")

    print(f"👤 User: {user_number} | Message: {user_message}")

    # 📌 Initialize user
    if user_number not in user_data:
        user_data[user_number] = {
            "name": None,
            "budget": None,
            "location": None,
            "stage": "start"
        }

    user = user_data[user_number]

    # 🤖 Hybrid Flow
    if user["stage"] == "start":
        user["stage"] = "ask_name"
        reply = generate_ai_reply("Ask the user their name politely.")

    elif user["stage"] == "ask_name":
        if not user_message:
            reply = "Please tell me your name 😊"
        else:
            user["name"] = user_message
            user["stage"] = "ask_budget"
            reply = generate_ai_reply(f"The user's name is {user['name']}. Ask their budget.")

    elif user["stage"] == "ask_budget":
        if not user_message:
            reply = "Please share your budget 💰"
        else:
            user["budget"] = user_message
            user["stage"] = "ask_location"
            reply = generate_ai_reply("Ask which city they are looking in.")

    elif user["stage"] == "ask_location":
        if not user_message:
            reply = "Please tell me the city 📍"
        else:
            user["location"] = user_message
            user["stage"] = "done"

            print("🧠 DEBUG DATA:", user)

            # 💾 Save to Sheets
            save_to_sheets({
                "Name": user["name"],
                "Budget": user["budget"],
                "Location": user["location"],
                "Phone": user_number
            })

            summary = f"""
User Details:
Name: {user['name']}
Budget: {user['budget']}
Location: {user['location']}
"""

            reply = generate_ai_reply(
                f"Summarize this nicely and tell the user that a property agent will contact them soon:\n{summary}"
            )

            print("🔥 LEAD CAPTURED:", user)

    else:
        reply = generate_ai_reply("Tell the user we will contact them soon.")

    return PlainTextResponse(
    f"<Response><Message>{reply}</Message></Response>",
    media_type="application/xml"
)