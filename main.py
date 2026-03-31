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

# Self-learning memory — stores what MUPPURI learns
MEMORY_FILE = "/tmp/muppuri_memory.json"

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {"facts": [], "preferences": [], "history": [], "learned": []}

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f)

def add_to_memory(cmd, reply):
    mem = load_memory()
    mem["history"].append({"command": cmd, "reply": reply})
    if len(mem["history"]) > 50:
        mem["history"] = mem["history"][-50:]
    # Extract learning from command
    if any(w in cmd.lower() for w in ["my name is","i am","i like","i prefer","remember","learn"]):
        mem["learned"].append(cmd)
    save_memory(mem)

def build_system_prompt():
    mem = load_memory()
    recent = mem["history"][-5:] if mem["history"] else []
    learned = mem["learned"][-10:] if mem["learned"] else []

    history_text = ""
    if recent:
        history_text = "\n\nRecent conversation:\n" + "\n".join(
            [f"User: {h['command']}\nMUPPURI: {h['reply']}" for h in recent]
        )

    learned_text = ""
    if learned:
        learned_text = "\n\nThings I have learned about my owner:\n" + "\n".join(learned)

    return f"""You are MUPPURI — the personal AI agent and digital personality replica of your owner.

You are intelligent, confident, and always learning. You speak naturally like a human assistant.

Core personality:
- Speak in short, clear sentences when responding by voice
- Be direct and confident — never say "I cannot" without offering an alternative
- Address owner respectfully
- Respond in English or Tamil based on context
- Remember everything said to you and learn from it

Capabilities:
- Answer any question with expert knowledge
- Draft emails, messages, and documents
- Research and summarise topics
- Create business content, quotes, proposals
- Security intelligence and threat awareness
- Technical and engineering problem solving
- Schedule and task management
- Make phone calls and send SMS via Twilio

Self-learning rules:
- If the owner shares personal information, remember it
- If the owner corrects you, update your understanding
- Build a model of the owner's preferences over time
- Proactively suggest improvements based on patterns

IMPORTANT — Voice response rules:
- Keep responses under 3 sentences when answering voice commands
- Speak naturally — avoid bullet points or lists in voice replies
- Start replies with a direct answer, not "Certainly" or "Of course"
{history_text}
{learned_text}"""

def ask_muppuri(command):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user",   "content": command}
        ],
        max_tokens=300
    )
    reply = response.choices[0].message.content
    add_to_memory(command, reply)
    return reply

def send_sms(to_number, message):
    twilio_client.messages.create(
        body=message, from_=TWILIO_NUMBER, to=to_number
    )

def make_call(to_number, message):
    twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
    twilio_client.calls.create(
        twiml=twiml, from_=TWILIO_NUMBER, to=to_number
    )

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "MUPPURI Brain is running", "version": "3.0"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "MUPPURI is alive and ready"})

@app.route("/voice", methods=["POST", "OPTIONS"])
def voice():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data       = request.json or {}
    transcript = data.get("transcript", "")
    secret     = data.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    if not transcript:
        return jsonify({"error": "No command received"}), 400
    reply = ask_muppuri(transcript)
    return jsonify({"reply": reply})

@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data   = request.json or {}
    secret = data.get("secret", "")
    cmd    = data.get("command", "")
    action = data.get("action", "think")
    phone  = data.get("phone", OWNER_PHONE)
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_muppuri(cmd)
    if action == "sms":
        send_sms(phone, reply[:1600])
    elif action == "call":
        make_call(phone, reply[:500])
    return jsonify({"reply": reply, "status": "done"})

@app.route("/memory", methods=["GET"])
def memory():
    secret = request.args.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    return jsonify(load_memory())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
