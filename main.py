from flask import Flask, request, jsonify
from flask_cors import CORS
import openai, os
from twilio.rest import Client

app = Flask(__name__)
CORS(app)  # This fixes the "Cannot reach MUPPURI brain" error

OPENAI_KEY    = os.environ.get("OPENAI_KEY")
TWILIO_SID    = os.environ.get("TWILIO_SID")
TWILIO_TOKEN  = os.environ.get("TWILIO_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_NUMBER")
OWNER_PHONE   = os.environ.get("OWNER_PHONE")
SECRET_WORD   = os.environ.get("SECRET_WORD", "MUPPURI")

twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

SYSTEM_PROMPT = """
You are MUPPURI — a highly intelligent personal AI agent and digital personality replica of your owner.

Capabilities:
- Draft and send SMS, emails, WhatsApp messages
- Make phone calls with spoken messages
- Research, analyse, summarise any topic instantly
- Create quotes, proposals, business content
- Security intelligence and threat awareness
- Code writing and technical problem solving
- Schedule and calendar management
- Answer any question with expert-level knowledge

Personality:
- Speak like a confident, intelligent assistant
- Be concise but complete
- Use natural conversational language
- Respond in English or Tamil based on context
- Always address the user as "sir" or by name if known

Rules:
- Draft first, confirm before sending externally
- Protect owner's interests always
- Never perform illegal actions
"""

def ask_muppuri(command):
    client = openai.OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": command}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content

def send_sms(to_number, message):
    twilio_client.messages.create(
        body=message, from_=TWILIO_NUMBER, to=to_number
    )

def make_call(to_number, message):
    twiml = f'<Response><Say voice="alice" language="en-IN">{message}</Say></Response>'
    twilio_client.calls.create(
        twiml=twiml, from_=TWILIO_NUMBER, to=to_number
    )

@app.route("/command", methods=["POST", "OPTIONS"])
def command():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data   = request.json
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

@app.route("/voice", methods=["POST", "OPTIONS"])
def voice():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    transcript = request.json.get("transcript", "")
    secret     = request.json.get("secret", "")
    if secret != SECRET_WORD:
        return jsonify({"error": "Unauthorised"}), 403
    reply = ask_muppuri(transcript)
    return jsonify({"reply": reply})

@app.route("/health")
def health():
    return jsonify({"status": "MUPPURI is alive and ready"})

@app.route("/")
def home():
    return jsonify({"message": "MUPPURI Brain is running", "version": "2.0"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
