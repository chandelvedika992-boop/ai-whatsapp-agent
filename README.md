# LeadNest AI
### WhatsApp-Based AI Lead Capture and Conversion Agent for Real Estate

Built by Vedika Chandel — Ramdeobaba University, Nagpur  
Deployed on Render. Data in Google Sheets. Messaging via Twilio WhatsApp.

---

## What This Is

LeadNest AI is not a chatbot. It is an autonomous agent that engages real estate leads the moment they message on WhatsApp, qualifies them through a structured conversation, stores their data in a centralised system, and answers real estate questions intelligently when they go off-script.

The entire process runs without any human involvement. No delays. No missed leads. No manual data entry.

The agent collects four things from every lead — name, city, budget, and property type — and saves them to Google Sheets with a status field that feeds into a CRM pipeline. A REST API layer exposes that data to a dashboard being built on top.

---

## Project Structure

```
main.py              — entire backend, built with FastAPI
requirements.txt     — Python dependencies
README.md            — this file
```

---

## Environment Variables

Set these on Render under Environment before deploying.

| Variable           | Description                                       |
|--------------------|---------------------------------------------------|
| OPENROUTER_API_KEY | From openrouter.ai — powers the AI fallback       |
| SHEETDB_URL        | SheetDB API URL connected to      Google Sheet    |
| TWILIO_AUTH_TOKEN  | From Twilio console — used for request validation |

---

## How the Agent Works

### The Conversation Flow

Every user has a state stored in memory. That state tracks exactly where they are in the conversation. This pattern is called a state machine.

```
User sends "Hi"
    The agent resets state and asks for their name.

User replies with their name
    Agent saves it and asks which city they are looking in.

User replies with city
    Agent saves it and asks for their budget range.

User replies with budget
    Agent saves it and asks what type of property they want.

User replies with property type
    Agent saves all four fields, writes the row to Google Sheets, and confirms.

Any message after that
    Agent routes it to the AI model and answers as a real estate assistant.
```

### Why "Hi" Never Gets Saved as a Name

This was one of the first bugs fixed. When a user sends "Hi", the agent resets their state and returns immediately. It never falls through to the name-saving logic. Before this fix, "Hi" was being written into the name column in Google Sheets on every new conversation.

### Why Responses Are in XML

Twilio requires replies in TwiML format — a specific XML structure it uses to deliver messages. Every response from the agent is wrapped like this:

```xml
<Response><Message>Your reply here</Message></Response>
```

### Why User Input Is Escaped Before Going Into XML

If someone types their name as "John & Sons" or includes any character like < or >, placing that directly into XML breaks the response structure entirely. The saxutils.escape() function converts those characters into safe equivalents before they are embedded in the TwiML. This is called XML injection protection.

### Why Every External Call Has a Timeout

Twilio drops a webhook connection if no response arrives within 15 seconds. SheetDB and OpenRouter can be slow under load. Without explicit timeouts on those calls, the agent can hang silently and the user receives nothing. SheetDB calls use a timeout of 8 seconds. OpenRouter calls use 10 seconds.

---

## API Endpoints

### GET /
Health check. Returns a confirmation that the server is running.  
Render uses HEAD requests to this route to verify the service is alive.

### POST /webhook
The core WhatsApp endpoint. Twilio calls this every time a user sends a message. The agent parses the message and phone number, runs the conversation logic, and returns a TwiML XML response.

### GET /leads
Returns all leads from Google Sheets as JSON. Supports optional filtering by status.

```
GET /leads             returns all leads
GET /leads?status=New  returns only leads with status "New"
```

Response shape:
```json
{
  "count": 5,
  "leads": [
    {
      "name": "Rahul Sharma",
      "location": "Nagpur",
      "budget": "50-80L",
      "interest": "2BHK flat",
      "number": "+919876543210",
      "timestamp": "2026-04-27 10:30:00",
      "status": "New"
    }
  ]
}
```

### PATCH /leads/{number}/status
Updates the status of a single lead identified by their phone number.  
Valid values: New, Contacted, Qualified, Closed.

```json
Request body:
{ "status": "Contacted" }

Response:
{ "success": true, "number": "+919876543210", "new_status": "Contacted" }
```

---

## Google Sheets Structure

The sheet must have these exact column headers, in any order, lowercase:

```
name | location | budget | interest | number | timestamp | status
```

Every new lead is written with status set to "New" automatically. The four pipeline stages are New, Contacted, Qualified, and Closed.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API framework | FastAPI | Fast, modern, auto-validates with Pydantic |
| Messaging | Twilio WhatsApp API | Receives and sends WhatsApp messages |
| AI fallback | Mistral 7B via OpenRouter | Handles off-script questions |
| Data storage | Google Sheets via SheetDB | Free, no database setup required |
| Hosting | Render | Free tier, auto-deploys from GitHub |
| State management | In-memory dictionary | Simple, works at current scale |
| XML safety | xml.sax.saxutils | Escapes user input before TwiML embedding |
| Body validation | Pydantic BaseModel | Validates PATCH request body automatically |

---

## Bugs Fixed

### "Hi" was being saved as the lead's name
The state was being fetched before the reset check ran. So when a user sent "Hi", the code reset the stage to ask_name but then immediately fell through and stored "Hi" as the name. Fixed by adding an early return on greeting messages so they never reach the flow logic.

### Duplicate route definition
Two separate @app.get("/") definitions existed in the file. FastAPI silently ignored the first one. Fixed by replacing both with a single @app.api_route("/", methods=["GET", "HEAD"]).

### User input was breaking XML responses
Names or messages containing characters like & and < were placed directly into TwiML XML, corrupting the response. Fixed by running all reply text through saxutils.escape() inside a shared build_response() helper function.

### No timeouts on external API calls
SheetDB and OpenRouter were called without any timeout. If either service was slow, the agent would hang and Twilio would drop the connection before a reply arrived. Fixed by adding timeout=8 on SheetDB and timeout=10 on OpenRouter.

### Empty phone number corrupted shared state
If Twilio sent a malformed request with no From field, the phone number became an empty string. Every such request would share one state slot and overwrite each other's conversation data. Fixed by returning an error response immediately if the phone number is missing.

### First message from a new user was stored as their name
If someone's very first message was not a greeting — for example, "I want a 2BHK flat" — the agent would initialise their state to ask_name and immediately store that sentence as their name. Fixed by greeting new users and returning immediately, so the flow only starts from their next message.

### Completed stage gave no useful response
After finishing the qualification flow, any message the user sent received a static reply telling them to type Hi again, even if they asked a genuine real estate question. Fixed by routing all post-completion messages to the AI fallback.

---

## Known Limitations

| Limitation                         | Impact                                                                                    | Plan |
|------------------------------------|-------------------------------------------------------------------------------------------|--------------------------|
| In-memory state resets on restart | Render free tier sleeps after inactivity. Users mid-conversation lose progress on restart. | Move to Redis in Phase 3 |
| No Twilio signature validation    | Anyone with the webhook URL can send fake messages and write to your Sheet                 | Add twilio.request_validator |
| Single shared Twilio number       |All brokers share one number in current setup                                               | Per-broker numbers via WhatsApp Business API in Phase 4 |
| Google Sheets as database         | Works well under 1000 leads, slows beyond that                                             | Migrate to PostgreSQL when onboarding paying clients |

---

## Deployment on Render

1. Push main.py and requirements.txt to GitHub
2. Go to render.com, create a New Web Service, connect your repo
3. Build command: pip install -r requirements.txt
4. Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
5. Add all three environment variables
6. Deploy

