import os
from dotenv import load_dotenv

load_dotenv()

APP_TITLE = "AI Car Concept Lab"
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "car-lab-dev-secret")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_IMAGE_URL = os.getenv(
    "HF_IMAGE_URL",
    "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
)

HCAPTCHA_SITE_KEY = os.getenv("HCAPTCHA_SITE_KEY", "10000000-ffff-ffff-ffff-000000000001")
HCAPTCHA_SECRET = os.getenv("HCAPTCHA_SECRET", "0x0000000000000000000000000000000000000000")
HCAPTCHA_VERIFY_URL = "https://api.hcaptcha.com/siteverify"

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))
