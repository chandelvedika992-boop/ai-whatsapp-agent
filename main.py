from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os
import requests
import datetime
import xml.sax.saxutils as saxutils  # FIX 1: to safely escape user text in XML
from urllib.parse import parse_qs
from pydantic import BaseModel

app = FastAPI()


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SHEETDB_URL = os.getenv("SHEETDB_URL")


user_states = {}



def save_to_sheets(name, location, budget, interest, number):
    clean_number = number.replace("whatsapp:", "")  # Twilio adds "whatsapp:" prefix

    data = {
    "data": [
        {
            "name": name,
            "location": location,
            "budget": budget,
            "interest": interest,
            "number": clean_number,
            "timestamp": str(datetime.datetime.now()),
            "status": "New"          
        }
    ]
}
    try:
        response = requests.post(SHEETDB_URL, json=data, timeout=8)  # FIX 2: always set timeout
        print("Sheet response:", response.text)
    except Exception as e:
        print("Sheet save error:", e)



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
                    {"role": "system", "content": "You are a helpful real estate assistant for an Indian real estate company. Keep replies short and friendly, under 3 sentences."},
                    {"role": "user", "content": message}
                ]
            },
            timeout=10  # FIX 2: timeout on AI call too
        )
        return response.json()["choices"][0]["message"]["content"]

    except Exception as e:
        print("AI error:", e)
        return "Sorry, I couldn't process that right now. Type 'Hi' to start fresh! 😊"



@app.api_route("/", methods=["GET", "HEAD"])
def home():
    return {"message": "LeadNest AI is running 🚀"}



@app.post("/webhook")
async def whatsapp_webhook(request: Request):

    
    body = await request.body()
    parsed = parse_qs(body.decode())

    user_message = parsed.get("Body", [""])[0].strip()
    user_number = parsed.get("From", [""])[0]

    
    if not user_number:
        return PlainTextResponse(
            "<Response><Message>Something went wrong. Please try again.</Message></Response>",
            media_type="application/xml"
        )

    print(f" From: {user_number} | Message: {user_message}")

    
    if user_message.lower() in ["hi", "hello", "hey", "start"]:
        user_states[user_number] = {"stage": "ask_name"}
        return build_response("Hi there! 👋 I'm your real estate assistant.\n\nWhat's your name?")

   
    if user_number not in user_states:
        user_states[user_number] = {"stage": "ask_name"}
        return build_response("Hi there! 👋 I'm your real estate assistant.\n\nWhat's your name?")

   
    state = user_states[user_number]

    

    if state["stage"] == "ask_name":
        state["name"] = user_message
        state["stage"] = "ask_location"
        reply = f"Nice to meet you, {user_message}! 😊\n\nWhich city are you looking for a property in? 📍"

    elif state["stage"] == "ask_location":
        state["location"] = user_message
        state["stage"] = "ask_budget"
        reply = "Great choice! 💰 What's your budget range?\n\n(Example: 30-50 lakhs, 1 crore+)"

    elif state["stage"] == "ask_budget":
        state["budget"] = user_message
        state["stage"] = "ask_interest"
        reply = "Almost done! 🏠 What type of property are you looking for?\n\n(Example: 2BHK flat, villa, plot, commercial)"

    elif state["stage"] == "ask_interest":
        state["interest"] = user_message
        state["stage"] = "completed"

        
        save_to_sheets(
            state.get("name"),
            state.get("location"),
            state.get("budget"),
            state.get("interest"),
            user_number
        )

        reply = (
            f"Perfect, {state.get('name')}! ✅\n\n"
            "Our team will review your requirements and contact you shortly.\n\n"
            "Have a real estate question in the meantime? Just ask me! 😊"
        )

    elif state["stage"] == "completed":
        # FIX 6: After completing the form, don't just say "type hi again."
        # Use the AI to answer real questions — this makes the bot actually useful.
        reply = get_ai_reply(user_message)

    else:
        reply = get_ai_reply(user_message)

    return build_response(reply)



def build_response(text: str) -> PlainTextResponse:
    safe_text = saxutils.escape(text)
    xml = f"<Response><Message>{safe_text}</Message></Response>"
    return PlainTextResponse(xml, media_type="application/xml")

@app.get("/leads")
def get_leads(status: str = None):
    try:
        response = requests.get(SHEETDB_URL, timeout=8)
        response.raise_for_status()  # raises an error if SheetDB returns 4xx/5xx
 
        leads = response.json()  # SheetDB returns a list of row dicts
 
        # If ?status=New was passed, filter to only matching rows
        # .lower() on both sides so "new" and "New" both match
        if status:
            leads = [
                lead for lead in leads
                if lead.get("status", "").lower() == status.lower()
            ]
 
        return {
            "count": len(leads),
            "leads": leads
        }
 
    except requests.exceptions.Timeout:
        # SheetDB took too long — tell the caller clearly
        return {"error": "SheetDB timed out. Try again."}, 504
 
    except Exception as e:
        print("Get leads error:", e)
        return {"error": "Could not fetch leads."}, 500
 
class StatusUpdate(BaseModel):
    status: str
 
VALID_STATUSES = ["New", "Contacted", "Qualified", "Closed"]

@app.patch("/leads/{number}/status")
def update_lead_status(number: str, body: StatusUpdate):
 
    # Reject invalid status values before hitting SheetDB
    if body.status not in VALID_STATUSES:
        return {
            "error": f"Invalid status. Must be one of: {VALID_STATUSES}"
        }, 400
 
    try:
        
        patch_url = f"{SHEETDB_URL}/number/{number}"
 
        response = requests.patch(
            patch_url,
            json={"data": {"status": body.status}},
            timeout=8
        )
        response.raise_for_status()
 
        return {
            "success": True,
            "number": number,
            "new_status": body.status
        }
 
    except requests.exceptions.Timeout:
        return {"error": "SheetDB timed out."}, 504
 
    except Exception as e:
        print("Status update error:", e)
        return {"error": "Could not update status."}, 500
 