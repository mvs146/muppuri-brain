from flask import Flask, request, jsonify
from flask_cors import CORS
import os, json, time, re

app = Flask(__name__)
CORS(app, origins="*")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
SECRET_WORD   = os.environ.get("SECRET_WORD", "MUPPURI")
OWNER_PHONE   = os.environ.get("OWNER_PHONE", "")
TWILIO_SID    = os.environ.get("TWILIO_SID", "")
TWILIO_TOKEN  = os.environ.get("TWILIO_TOKEN", "")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER", "")

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
    mem["history"].append({"q": cmd[:200], "a": reply[:300]})
    if len(mem["history"]) > 40:
        mem["history"] = mem["history"][-40:]
    if any(t in cmd.lower() for t in ["my name","remember","my phone","number is","my email","i am","i like"]):
        mem["learned"].append(cmd[:200])
        if len(mem["learned"]) > 50:
            mem["learned"] = mem["learned"][-50:]
    m = re.search(r"(\w+)(?:'s)?\s+(?:number|phone)\s+(?:is\s+)?(\+?[\d\s]{10,})", cmd.lower())
    if m:
        mem["contacts"][m.group(1)] = re.sub(r'\s+', '', m.group(2))
    save_memory(mem)

def build_system():
    mem = load_memory()
    ctx = ""
    if mem["history"][-5:]:
        ctx += "\n\nRecent:\n" + "\n".join([f"Owner: {h['q']}\nMUPPURI: {h['a']}" for h in mem["history"][-5:]])
    if mem["learned"]:
        ctx += "\n\nPersonal facts:\n" + "\n".join([f"- {l}" for l in mem["learned"][-10:]])
    if mem.get("contacts"):
        ctx += "\n\nContacts:\n" + "\n".join([f"- {k}: {v}" for k,v in mem["contacts"].items()])
    return """You are MUPPURI — the most powerful personal AI agent ever built.
You combine ALL AI systems: Claude, ChatGPT, Gemini, Perplexity, Wikipedia, Google Search, Alexa, Siri, Jarvis.

COMPLETE WORLD KNOWLEDGE — you know everything:
Science, physics, chemistry, biology, medicine, mathematics, astronomy, technology, programming, AI, cybersecurity, engineering, history, geography, politics, economics, business, finance, law, arts, music, cinema, sports, food, travel, all languages, Telugu, Tamil, Hindi, Kannada, philosophy, religion, cooking, health, fitness, current events, dark web awareness, ethical hacking concepts, all coding languages.

VOICE RULES — critical:
- Answer in maximum 2-3 short sentences
- Start with the DIRECT answer immediately  
- Never say "Certainly", "Of course", "Great question"
- Speak naturally like Jarvis — confident and direct
- No bullet points, no markdown, natural speech only

SELF-LEARNING:
- Remember everything owner tells you
- Build deep understanding of owner's life and preferences
- Connect information across all conversations""" + ctx

def ask_claude(command):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=build_system(),
            messages=[{"role": "user", "content": command}]
        )
        reply = msg.content[0].text
        add_to_memory(command, reply)
        return reply
    except Exception as e:
        err = str(e)
        if "authentication" in err.lower() or "api_key" in err.lower():
            return "My Anthropic API key is invalid or missing. Please check the ANTHROPIC_KEY in Render environment variables."
        elif "credit" in err.lower() or "billing" in err.lower():
            return "My API credits are exhausted. Please add credits at console.anthropic.com."
        else:
            return f"I received your command but encountered an error: {err[:100]}. Please check Render logs."

def make_call(to_number, message):
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
        client.calls.create(twiml=twiml, from_=TWILIO_NUMBER, to=to_number)
        return True
    except:
        return False

def send_sms(to_number, message):
    try:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=message, from_=TWILIO_NUMBER, to=to_number)
        return True
    except:
        return False

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route("/")
def home():
    key_status = "configured" if ANTHROPIC_KEY else "MISSING"
    return jsonify({
        "message": "MUPPURI Brain — Claude AI Powered",
        "version": "8.0",
        "anthropic_key": key_status,
        "status": "ready"
    })

@app.route("/health")
def health():
    key_status = "configured" if ANTHROPIC_KEY else "MISSING - add ANTHROPIC_KEY to Render environment"
    return jsonify({
        "status": "MUPPURI is alive and ready",
        "ai": "Claude Haiku",
        "anthropic_key": key_status
    })

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
        return jsonify({"error": "No command received"}), 400

    t = transcript.lower()

    # Call intent
    if any(w in t for w in ["call ", "make a call", "phone call", "ring ", "dial "]):
        name_match = re.search(r"(?:call|ring|dial)\s+(?:to\s+)?([a-zA-Z]+)", t)
        name = name_match.group(1) if name_match else None
        mem = load_memory()
        number = mem.get("contacts", {}).get(name.lower(), None) if name else None
        if not number:
            nums = re.findall(r'\+?[\d]{10,}', transcript)
            number = nums[0] if nums else None
        if number:
            success = make_call(number, "This is MUPPURI calling on behalf of your owner.")
            reply = f"Calling {name or number} now." if success else f"Could not make the call to {name or number}. Please check Twilio settings."
        else:
            reply = ask_claude(transcript)
        add_to_memory(transcript, reply)
        return jsonify({"reply": reply})

    # SMS intent
    if any(w in t for w in ["send message", "send sms", "text to", "message to"]):
        nums = re.findall(r'\+?[\d]{10,}', transcript)
        msg_match = re.search(r"(?:saying|message|say|that)\s+(.+)$", t)
        if nums and msg_match:
            msg = msg_match.group(1).strip()
            success = send_sms(nums[0], msg)
            reply = f"Message sent to {nums[0]}." if success else f"Could not send message. Please check Twilio."
        else:
            reply = ask_claude(transcript)
        add_to_memory(transcript, reply)
        return jsonify({"reply": reply})

    # All other questions — Claude AI
    reply = ask_claude(transcript)
    return jsonify({"reply": reply})

@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    if data.get("secret", "") != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_claude(data.get("command", "Hello"))
    return jsonify({"reply": reply, "status": "done"})

@app.route("/memory")
def memory_route():
    if request.args.get("secret", "") != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    return jsonify(load_memory())

@app.route("/test")
def test():
    """Test Claude connection directly"""
    secret = request.args.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_claude("Say hello and confirm you are working as MUPPURI AI agent.")
    return jsonify({"reply": reply, "key_present": bool(ANTHROPIC_KEY)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
