import base64, json, uuid
from datetime import datetime

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from groq import Groq

import config

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

groq_client = Groq(api_key=config.GROQ_API_KEY) if config.GROQ_API_KEY else None

DESIGN_PROMPT = """You are an expert futuristic car designer.
Generate a detailed concept based on:
Style: {style}
Primary Color: {primary_color}
Accent Color: {accent_color}
Material: {material}
Occasion: {occasion}
Inspiration: {inspiration}

Respond with raw JSON only - no markdown, no explanation.
{{
  "name":"2-4 word creative car name",
  "tagline":"punchy tagline max 10 words",
  "description":"2-3 sentence concept description",
  "materials":["mat1","mat2","mat3"],
  "colorways":[
    {{"name":"variant 1","body":"#hex","roof":"#hex","accent":"#hex","glass":"#hex","wheel":"#hex"}},
    {{"name":"variant 2","body":"#hex","roof":"#hex","accent":"#hex","glass":"#hex","wheel":"#hex"}},
    {{"name":"variant 3","body":"#hex","roof":"#hex","accent":"#hex","glass":"#hex","wheel":"#hex"}}
  ],
  "features":["feat1","feat2","feat3","feat4"],
  "powertrain":"short powertrain line",
  "target_audience":"who this is for",
  "retail_price":"$XXX,XXX",
  "style_tags":["tag1","tag2","tag3"]
}}
Generate exactly 3 colorways. All hex codes must be valid #RRGGBB."""

def get_prefs(data):
    defaults = {
        "style": "futuristic",
        "primary_color": "#1a1a2e",
        "accent_color": "#e2b714",
        "material": "carbon fiber",
        "occasion": "city launch",
        "inspiration": "",
    }
    return {k: (data.get(k) or v) for k, v in defaults.items()}

def strip_json_fences(raw):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip().rstrip("```").strip()

def fallback_concept(prefs):
    p = prefs["primary_color"]
    a = prefs["accent_color"]
    style = prefs["style"].title()
    theme = prefs["inspiration"] or "future motion"
    return {
        "name": f"{style} Vector X",
        "tagline": "Charge the road ahead.",
        "description": f"A {prefs['style']} concept car shaped for {prefs['occasion']}, mixing {prefs['material']} detailing with a bold {theme} influence.",
        "materials": [prefs["material"].title(), "Recycled interior trim", "Performance composite shell"],
        "colorways": [
            {"name": "Launch Spec", "body": p, "roof": "#101317", "accent": a, "glass": "#7aa7c7", "wheel": "#d9d9d9"},
            {"name": "Night Pulse", "body": "#101317", "roof": p, "accent": a, "glass": "#87b7d9", "wheel": "#f0f0f0"},
            {"name": "Solar Drift", "body": a, "roof": "#ffffff", "accent": p, "glass": "#9bc8ea", "wheel": "#222222"},
        ],
        "features": ["Active aero front blade", "Adaptive ambient cabin", "Panoramic canopy roof", "AI driving assistance"],
        "powertrain": "Dual-motor electric drivetrain",
        "target_audience": "Drivers who want bold futuristic design",
        "retail_price": "$148,000",
        "style_tags": [prefs["style"], prefs["occasion"], "concept"],
    }

def generate_concept(prefs):
    if not groq_client:
        return fallback_concept(prefs)
    chat = groq_client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Car design expert. Pure JSON only."},
            {"role": "user", "content": DESIGN_PROMPT.format(**prefs)},
        ],
        temperature=0.85,
        max_tokens=1200,
    )
    return json.loads(strip_json_fences(chat.choices[0].message.content))

def verify_hcaptcha(token):
    if not token:
        return False
    try:
        r = requests.post(
            config.HCAPTCHA_VERIFY_URL,
            data={"secret": config.HCAPTCHA_SECRET, "response": token},
            timeout=5,
        )
        return r.json().get("success", False)
    except Exception:
        return False

def hex_to_color_name(h):
    h = (h or "").lstrip("#").lower()
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return "colorful"
    mx, mn = max(r, g, b), min(r, g, b)
    br, sat = mx / 255, ((mx - mn) / mx if mx else 0)
    if br < 0.15:
        return "black"
    if br > 0.88 and sat < 0.15:
        return "white"
    if sat < 0.18:
        return "dark gray" if br < 0.4 else "gray" if br < 0.65 else "light gray"
    if mx == r:
        return ("orange" if g > 120 else "dark orange") if g > b + 60 else ("magenta" if b > g + 40 else "red")
    if mx == g:
        return "yellow-green" if r > b + 60 else ("cyan-green" if b > r + 40 else "green")
    return "purple" if r > g + 60 else ("cyan" if g > r + 40 else "blue")

def build_image_prompt(prefs):
    p = hex_to_color_name(prefs["primary_color"])
    a = hex_to_color_name(prefs["accent_color"])
    prompt = (
        f"Professional product photography of a futuristic concept car, {prefs['style']} styling, "
        f"{p} body, {a} accents, {prefs['material']} details, side three-quarter view, white studio background, "
        f"sharp focus, premium automotive render, car only"
    )
    if prefs.get("inspiration"):
        prompt += f", {prefs['inspiration']} theme"
    return prompt

def generate_car_image(prompt):
    if not config.HF_API_KEY:
        return None
    try:
        r = requests.post(
            config.HF_IMAGE_URL,
            headers={
                "Authorization": f"Bearer {config.HF_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"inputs": prompt},
            timeout=60,
        )
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            mime = r.headers["content-type"].split(";")[0].strip()
            return f"data:{mime};base64,{base64.b64encode(r.content).decode()}"
    except Exception:
        pass
    return None

def save_to_history(concept, prefs, image_url=None):
    session.setdefault("history", [])
    entry = {
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now().strftime("%b %d, %Y | %I:%M %p"),
        "concept": concept,
        "prefs": prefs,
        "image_url": image_url,
    }
    session["history"] = ([entry] + session["history"])[: config.MAX_HISTORY]
    return entry["id"]

@app.route("/")
def index():
    return render_template("index.html", hcaptcha_site_key=config.HCAPTCHA_SITE_KEY)

@app.route("/studio")
def studio():
    return render_template("studio.html", hcaptcha_site_key=config.HCAPTCHA_SITE_KEY)

@app.route("/history")
def history():
    return render_template("history.html", designs=session.get("history", []))

@app.route("/clear-history", methods=["POST"])
def clear_history():
    session.pop("history", None)
    return redirect(url_for("history"))

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or request.form
    token = data.get("h-captcha-response", "")
    if not token:
        return jsonify({"error": "Please complete the CAPTCHA."}), 400
    if not verify_hcaptcha(token):
        return jsonify({"error": "CAPTCHA verification failed."}), 400

    prefs = get_prefs(data)
    try:
        concept = generate_concept(prefs)
        concept["image_prompt"] = build_image_prompt(prefs)
        history_id = save_to_history(concept, prefs)
        return jsonify({"success": True, "concept": concept, "prefs": prefs, "history_id": history_id})
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Malformed AI response: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Concept generation failed: {e}"}), 500

@app.route("/generate-image", methods=["POST"])
def generate_image():
    data = request.get_json(silent=True) or {}
    prompt = data.get("image_prompt", "")
    history_id = data.get("history_id", "")
    if not prompt:
        return jsonify({"error": "No image prompt."}), 400
    if not config.HF_API_KEY:
        return jsonify({"error": "HF_API_KEY not configured."}), 503
    image_url = generate_car_image(prompt)
    if not image_url:
        return jsonify({"error": "Image generation failed. Try again."}), 500

    if history_id and "history" in session:
        for entry in session["history"]:
            if entry["id"] == history_id:
                entry["image_url"] = image_url
                break
        session.modified = True

    return jsonify({"success": True, "image_url": image_url})

if __name__ == "__main__":
    app.run(debug=True, port=5000)


