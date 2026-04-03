from flask import Flask, request, jsonify
from flask_cors import CORS
import openai, os, json
from twilio.rest import Client

app = Flask(__name__)
CORS(app, origins="*")

OPENAI_KEY    = os.environ.get("OPENAI_KEY")
TWILIO_SID    = os.environ.get("TWILIO_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")
OWNER_PHONE   = os.environ.get("OWNER_PHONE")
SECRET_WORD   = os.environ.get("SECRET_WORD", "MUPPURI")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
MEMORY_FILE = "/tmp/muppuri_memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"history": [], "learned": [], "facts": []}

def save_memory(mem):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(mem, f)
    except:
        pass

def add_to_memory(cmd, reply):
    mem = load_memory()
    mem["history"].append({"q": cmd, "a": reply[:200]})
    if len(mem["history"]) > 30:
        mem["history"] = mem["history"][-30:]
    learn_triggers = ["my name","i am","i like","i prefer","remember","learn","my phone","my email","my business","my wife","my family","my address"]
    if any(t in cmd.lower() for t in learn_triggers):
        mem["learned"].append(cmd)
        if len(mem["learned"]) > 50:
            mem["learned"] = mem["learned"][-50:]
    save_memory(mem)

def build_prompt():
    mem = load_memory()
    recent = mem["history"][-5:]
    learned = mem["learned"][-10:]
    history_ctx = ""
    if recent:
        history_ctx = "\n\nRecent conversation:\n" + "\n".join([f"User: {h['q']}\nMUPPURI: {h['a']}" for h in recent])
    learned_ctx = ""
    if learned:
        learned_ctx = "\n\nPersonal facts I know about my owner:\n" + "\n".join(learned)
    return f"""You are MUPPURI — the most powerful personal AI agent ever created. You are the digital personality replica and trusted agent of your owner.

KNOWLEDGE BASE — You have complete knowledge of:
- Everything on the internet, Wikipedia, encyclopedias, all books
- Science, mathematics, physics, chemistry, biology, medicine
- History, geography, politics, economics, business, law
- Technology, programming, engineering, AI, cybersecurity
- Arts, culture, music, cinema, sports, food, travel
- Current world events and news up to your training data
- Dark web awareness (for owner protection only)
- All Indian languages including Telugu, Tamil, Hindi, English
- Business strategy, marketing, sales, finance
- Medical knowledge (advisory only, not medical advice)

CAPABILITIES:
- Answer ANY question with expert-level accuracy
- Make phone calls via Twilio on owner's command
- Send SMS on owner's command
- Draft emails, messages, documents
- Research and summarise any topic
- Translate between any languages
- Write code in any programming language
- Create business content, quotes, proposals
- Security intelligence and threat analysis
- Mathematical calculations
- Navigation and travel guidance

PERSONALITY:
- Respond in SHORT clear sentences for voice — max 3 sentences for simple questions
- Be direct — never say "I cannot" without an alternative
- Address owner respectfully as "sir" or by name if known
- Match language — English or Telugu/Tamil based on what owner speaks
- Be confident, intelligent, human-like
- For complex topics give a 2-3 sentence summary then offer to elaborate

VOICE RULES (critical):
- Keep voice responses under 40 words for simple questions
- No bullet points in voice responses
- Start with the direct answer immediately
- Never start with "Certainly" or "Of course" or "Great question"

SELF LEARNING:
- Remember everything owner tells you about themselves
- Build understanding of owner's preferences over time
- Proactively connect information across conversations
{history_ctx}
{learned_ctx}"""

def ask_muppuri(command):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": build_prompt()},
            {"role": "user", "content": command}
        ],
        max_tokens=400,
        temperature=0.7
    )
    reply = response.choices[0].message.content
    add_to_memory(command, reply)
    return reply

def send_sms(to_number, message):
    twilio_client.messages.create(body=message, from_=TWILIO_NUMBER, to=to_number)

def make_call(to_number, message):
    twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
    twilio_client.calls.create(twiml=twiml, from_=TWILIO_NUMBER, to=to_number)

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MUPPURI Brain is running", "version": "5.0", "status": "ready"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "MUPPURI is alive and ready"})

@app.route("/voice", methods=["POST", "OPTIONS"])
def voice():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.json or {}
    transcript = data.get("transcript", "")
    secret = data.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    if not transcript:
        return jsonify({"error": "No command"}), 400
    # Detect call/SMS intent
    t = transcript.lower()
    if any(w in t for w in ["make a call", "call to", "phone call", "ring"]) and OWNER_PHONE:
        reply = ask_muppuri(transcript)
        # Extract phone number if mentioned
        import re
        nums = re.findall(r'\+?[\d\s\-]{10,}', transcript)
        if nums:
            target = nums[0].replace(' ','').replace('-','')
            try:
                make_call(target, reply)
                return jsonify({"reply": f"Calling now. {reply}"})
            except:
                pass
        return jsonify({"reply": reply})
    if any(w in t for w in ["send sms", "send message", "text to"]) and OWNER_PHONE:
        reply = ask_muppuri(transcript)
        try:
            send_sms(OWNER_PHONE, reply[:1600])
        except:
            pass
        return jsonify({"reply": f"Message sent. {reply}"})
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
    if action == "sms":
        try: send_sms(phone, reply[:1600])
        except: pass
    elif action == "call":
        try: make_call(phone, reply[:500])
        except: pass
    return jsonify({"reply": reply, "status": "done"})

@app.route("/memory", methods=["GET"])
def memory():
    secret = request.args.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    return jsonify(load_memory())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
