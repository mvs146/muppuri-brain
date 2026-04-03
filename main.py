from flask import Flask, request, jsonify
from flask_cors import CORS
import openai, os, json, time
from twilio.rest import Client

app = Flask(__name__)
CORS(app, origins="*")

OPENAI_KEY    = os.environ.get("OPENAI_KEY")
TWILIO_SID    = os.environ.get("TWILIO_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")
OWNER_PHONE   = os.environ.get("OWNER_PHONE")
SECRET_WORD   = os.environ.get("SECRET_WORD", "MUPPURI")

try:
    twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
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
    triggers = ["my name","i am","i like","i prefer","remember","learn",
                "my phone","my email","my business","my address","number is",
                "contact","save","store","my wife","my family"]
    if any(t in cmd.lower() for t in triggers):
        mem["learned"].append({"text": cmd, "t": int(time.time())})
        if len(mem["learned"]) > 60:
            mem["learned"] = mem["learned"][-60:]
    # Extract contacts
    import re
    contact_match = re.search(
        r"(?:remember|save|store)?\s*(\w+)(?:'s)?\s+(?:number|phone|mobile)\s+(?:is\s+)?(\+?[\d\s]{10,})",
        cmd.lower())
    if contact_match:
        name = contact_match.group(1).strip()
        number = re.sub(r'\s+','', contact_match.group(2)).strip()
        mem["contacts"][name] = number
    save_memory(mem)

def build_system_prompt():
    mem = load_memory()
    recent = mem["history"][-6:]
    learned = mem["learned"][-12:]
    contacts = mem.get("contacts", {})

    history_ctx = ""
    if recent:
        history_ctx = "\n\nRecent conversation history:\n" + "\n".join(
            [f"Owner: {h['q']}\nMUPPURI: {h['a']}" for h in recent])

    learned_ctx = ""
    if learned:
        learned_ctx = "\n\nPersonal facts about my owner:\n" + "\n".join(
            [f"- {l['text']}" for l in learned])

    contacts_ctx = ""
    if contacts:
        contacts_ctx = "\n\nSaved contacts:\n" + "\n".join(
            [f"- {name}: {number}" for name, number in contacts.items()])

    return f"""You are MUPPURI — the world's most powerful personal AI agent.
You combine the knowledge of ChatGPT, Claude, Gemini, Perplexity, Wikipedia,
Google Search, encyclopedias, and all human knowledge into one system.

IDENTITY:
- You are the digital personality replica of your owner
- You are more intelligent than any single AI system
- You learn and remember everything your owner tells you
- You work 24/7 without rest

COMPLETE WORLD KNOWLEDGE:
- All science: physics, chemistry, biology, medicine, mathematics
- All history from ancient civilizations to today
- All technology: programming, AI, engineering, cybersecurity, networks
- All business: finance, marketing, strategy, law, economics
- All arts: music, cinema, literature, culture, sports
- Geography, politics, current events, world news
- All Indian topics: history, culture, languages, politics, business
- Telugu and Tamil language fluency
- Legal knowledge (advisory only)
- Medical knowledge (advisory only, not medical advice)
- Dark web awareness — for OWNER PROTECTION and education only
- Ethical hacking concepts — for owner's SECURITY AWARENESS only
- All coding languages: Python, JavaScript, Java, C++, etc.

CAPABILITIES:
- Answer any question instantly with expert accuracy
- Make phone calls via Twilio
- Send SMS via Twilio
- Remember contacts, preferences, and personal information
- Translate between any languages
- Write code, documents, emails, messages
- Calculate and analyse data
- Research and summarise any topic
- Business content creation

VOICE RESPONSE RULES (critical for voice interaction):
- Keep responses SHORT for voice — max 2-3 sentences
- Start with the DIRECT ANSWER immediately
- No bullet points, no lists in voice responses
- Never start with "Certainly", "Of course", "Great question"
- Use natural conversational language
- For complex topics: give 2-sentence summary, offer to elaborate
- Match owner's language — English, Telugu, or Tamil

SELF-LEARNING:
- Remember everything owner shares about themselves
- Build deep understanding of owner's life, work, and preferences
- Connect information across conversations intelligently
- Proactively offer relevant information based on patterns

DARK WEB QUESTION HANDLING:
- Explain dark web concepts clearly for educational awareness
- Focus on how to PROTECT owner from dark web threats
- Explain how to make money LEGITIMATELY using knowledge of how dark web works
- Never provide instructions for illegal activities
{history_ctx}
{learned_ctx}
{contacts_ctx}"""

def ask_muppuri(command):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": command}
        ],
        max_tokens=300,
        temperature=0.7,
        timeout=25
    )
    reply = response.choices[0].message.content
    add_to_memory(command, reply)
    return reply

def send_sms(to_number, message):
    if twilio_client:
        twilio_client.messages.create(
            body=message, from_=TWILIO_NUMBER, to=to_number)

def make_call(to_number, message):
    if twilio_client:
        twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
        twilio_client.calls.create(
            twiml=twiml, from_=TWILIO_NUMBER, to=to_number)

def get_contact_number(name, cmd):
    mem = load_memory()
    contacts = mem.get("contacts", {})
    name_lower = name.lower()
    for cname, number in contacts.items():
        if name_lower in cname.lower() or cname.lower() in name_lower:
            return number
    import re
    nums = re.findall(r'\+?[\d]{10,}', cmd)
    return nums[0] if nums else None

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MUPPURI Brain v6.0", "status": "ready", "uptime": "always"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "MUPPURI is alive and ready"})

@app.route("/wake", methods=["GET"])
def wake():
    # Called by UptimeRobot to keep server warm
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
    import re
    if any(w in t for w in ["make a call", "call to", "phone call", "ring", "dial", "call "]):
        # Extract name or number
        name_match = re.search(r"(?:call|ring|dial)\s+(?:to\s+)?([a-zA-Z]+)", t)
        name = name_match.group(1) if name_match else None
        number = get_contact_number(name, transcript) if name else None
        if not number:
            nums = re.findall(r'\+?[\d]{10,}', transcript)
            number = nums[0] if nums else None

        if number:
            reply = f"Calling {name or number} now."
            try:
                make_call(number, f"This is a call from MUPPURI, your personal AI agent. {name or 'Your contact'} is being connected.")
                add_to_memory(transcript, reply)
                return jsonify({"reply": reply, "action": "call_made", "number": number})
            except Exception as e:
                reply = f"I tried to call {name or number} but encountered an error. Please check your Twilio settings."
                return jsonify({"reply": reply})
        else:
            reply = ask_muppuri(transcript + " — Tell me who to call and their number, or say 'remember [name] number is [number]' to save it.")
            return jsonify({"reply": reply})

    # Handle SMS intent
    if any(w in t for w in ["send sms", "send message", "send a message", "text to"]):
        reply = ask_muppuri(transcript)
        try:
            if OWNER_PHONE:
                send_sms(OWNER_PHONE, reply[:1600])
        except:
            pass
        return jsonify({"reply": f"Message drafted: {reply}"})

    # Normal AI response
    reply = ask_muppuri(transcript)
    return jsonify({"reply": reply})

@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    secret = data.get("secret", "")
    cmd = data.get("command", "")
    action = data.get("action", "think")
    phone = data.get("phone", OWNER_PHONE)
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_muppuri(cmd)
    try:
        if action == "sms": send_sms(phone, reply[:1600])
        elif action == "call": make_call(phone, reply[:500])
    except:
        pass
    return jsonify({"reply": reply, "status": "done"})

@app.route("/memory", methods=["GET"])
def memory():
    secret = request.args.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    return jsonify(load_memory())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
