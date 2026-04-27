from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic, os, json, time, re
from twilio.rest import Client

app = Flask(__name__)
CORS(app, origins="*")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")
TWILIO_SID    = os.environ.get("TWILIO_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")
OWNER_PHONE   = os.environ.get("OWNER_PHONE")
SECRET_WORD   = os.environ.get("SECRET_WORD", "MUPPURI")

try:
    twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
except:
    twilio_client = None

MEMORY_FILE = "/tmp/muppuri_memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"history": [], "learned": [], "contacts": {}}

def save_memory(mem):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(mem, f)
    except:
        pass

def add_to_memory(cmd, reply):
    mem = load_memory()
    mem["history"].append({"q": cmd[:200], "a": reply[:300], "t": int(time.time())})
    if len(mem["history"]) > 40:
        mem["history"] = mem["history"][-40:]
    triggers = ["my name","i am","i like","i prefer","remember","my phone",
                "my email","my business","number is","my address","save","contact"]
    if any(t in cmd.lower() for t in triggers):
        mem["learned"].append(cmd[:200])
        if len(mem["learned"]) > 50:
            mem["learned"] = mem["learned"][-50:]
    # Auto-save contacts
    match = re.search(
        r"(?:remember|save)?\s*(\w+)(?:'s)?\s+(?:number|phone)\s+(?:is\s+)?(\+?[\d\s]{10,})",
        cmd.lower())
    if match:
        mem["contacts"][match.group(1)] = re.sub(r'\s+','',match.group(2))
    save_memory(mem)

def build_system():
    mem = load_memory()
    recent = mem["history"][-6:]
    learned = mem["learned"][-10:]
    contacts = mem.get("contacts", {})

    history_ctx = ""
    if recent:
        history_ctx = "\n\nRecent conversation:\n" + "\n".join(
            [f"Owner: {h['q']}\nMUPPURI: {h['a']}" for h in recent])

    personal_ctx = ""
    if learned:
        personal_ctx = "\n\nPersonal facts:\n" + "\n".join([f"- {l}" for l in learned])

    contacts_ctx = ""
    if contacts:
        contacts_ctx = "\n\nSaved contacts:\n" + "\n".join([f"- {k}: {v}" for k,v in contacts.items()])

    return f"""You are MUPPURI — the world's most powerful personal AI agent.
You are powered by Claude AI (Anthropic) and work exactly like a combination of
Jarvis from Iron Man, Google Assistant, Siri, and Alexa.

COMPLETE WORLD KNOWLEDGE:
- All science: physics, chemistry, biology, medicine, mathematics, astronomy
- All technology: programming, AI, engineering, cybersecurity, networks, apps
- All history from ancient times to today
- All geography: countries, capitals, landmarks, cultures
- All business: finance, marketing, strategy, law, economics, startups
- All arts: music, cinema, literature, sports, food, travel
- Current events and world news
- All Indian topics: Telugu, Tamil, Hindi, Kannada, Malayalam languages
- Legal and medical knowledge (advisory level)
- Dark web and cybersecurity awareness for owner protection
- All programming languages

VOICE RESPONSE RULES (critical):
- Keep answers SHORT — maximum 3 sentences for voice
- Start with the DIRECT answer immediately
- Never start with "Certainly", "Of course", "I'd be happy to", "Great question"
- No bullet points — speak in natural sentences
- Be confident like Jarvis — direct and intelligent

CAPABILITIES:
- Answer any question on any topic instantly
- Make phone calls via Twilio on command
- Send SMS on command
- Remember personal information across conversations
- Translate between any languages
- Write emails, messages, documents, code
- Research and summarise any topic
- Business content and proposals
{history_ctx}
{personal_ctx}
{contacts_ctx}"""

def ask_claude(command):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=build_system(),
        messages=[{"role": "user", "content": command}]
    )
    reply = msg.content[0].text
    add_to_memory(command, reply)
    return reply

def make_call(to_number, message):
    if twilio_client:
        twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
        twilio_client.calls.create(twiml=twiml, from_=TWILIO_NUMBER, to=to_number)

def send_sms(to_number, message):
    if twilio_client:
        twilio_client.messages.create(body=message, from_=TWILIO_NUMBER, to=to_number)

def get_contact(name):
    mem = load_memory()
    contacts = mem.get("contacts", {})
    for k, v in contacts.items():
        if name.lower() in k.lower() or k.lower() in name.lower():
            return v
    return None

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route("/")
def home():
    return jsonify({"message": "MUPPURI Brain — Claude AI Powered", "version": "7.0", "status": "ready"})

@app.route("/health")
def health():
    return jsonify({"status": "MUPPURI is alive and ready", "ai": "Claude Haiku"})

@app.route("/wake")
def wake():
    return jsonify({"status": "awake", "time": int(time.time())})

@app.route("/voice", methods=["POST", "OPTIONS"])
def voice():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    transcript = data.get("transcript", "").strip()
    secret = data.get("secret", "")

    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    if not transcript:
        return jsonify({"error": "No command"}), 400

    t = transcript.lower()

    # Handle call intent
    if any(w in t for w in ["make a call", "call to", "phone call", "ring ", "dial ", "call "]):
        name_match = re.search(r"(?:call|ring|dial)\s+(?:to\s+)?([a-zA-Z]+)", t)
        name = name_match.group(1) if name_match else None
        number = get_contact(name) if name else None
        if not number:
            nums = re.findall(r'\+?[\d]{10,}', transcript)
            number = nums[0] if nums else None

        if number:
            try:
                make_call(number, f"This is MUPPURI calling on behalf of your owner.")
                reply = f"Calling {name or number} now."
            except Exception as e:
                reply = f"Could not make the call. Please check Twilio settings. Error: {str(e)[:50]}"
        else:
            reply = ask_claude(transcript)
        return jsonify({"reply": reply})

    # Handle SMS intent
    if any(w in t for w in ["send sms", "send message", "text to", "send a text"]):
        reply = ask_claude(transcript)
        try:
            if OWNER_PHONE:
                send_sms(OWNER_PHONE, reply[:1600])
        except:
            pass
        return jsonify({"reply": "Message sent. " + reply})

    # Normal question — answer with Claude AI
    reply = ask_claude(transcript)
    return jsonify({"reply": reply})

@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    if data.get("secret", "") != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_claude(data.get("command", ""))
    return jsonify({"reply": reply, "status": "done"})

@app.route("/memory")
def memory():
    if request.args.get("secret", "") != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    return jsonify(load_memory())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
