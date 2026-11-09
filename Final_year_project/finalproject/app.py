#!/usr/bin/env python3
# Lunaris - Tamil Nadu Grand Hotels AI Concierge
# pip install -r requirements.txt
# python app.py

import base64
import io
import logging
import os
import smtplib
import threading
import uuid
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiohttp
import qrcode
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

LIVEKIT_URL        = os.getenv("LIVEKIT_URL",        "wss://mona-83s32esd.livekit.cloud")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY",    "APIeyEebUs72ymf")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "iG4gYsD7dQlb2tn1TAXA1kxcOFfCHbiuid5cugEVnhe")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY",     "")
N8N_MCP_URL        = os.getenv("N8N_MCP_SERVER_URL", "https://ajaykishore.app.n8n.cloud/mcp/7da06b2a-3449-4bf9-9962-fde13cf29314")
PERSONA_ID         = os.getenv("PERSONA_ID",         "pdb559d266f6")
REPLICA_ID         = os.getenv("REPLICA_ID",         "r9fa0878977a")
TAVUS_API_KEY      = os.getenv("TAVUS_API_KEY",      "0e1bd5ae3c9f40b4a1a63f8d756db789")

# ================= EMAIL CONFIG =================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Load ONLY from .env (no hardcoded defaults)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# Sender must match Gmail login
FROM_EMAIL = SMTP_USER

UPI_ID   = "ajay-2210@ptaxis"
UPI_NAME = "Tamil Nadu Grand Hotels"

if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s - %(message)s")
logger = logging.getLogger("Lunaris")

# ---------------------------------------------------------------------------
# Hotel Data
# ---------------------------------------------------------------------------
HOTELS = {
    "Chennai": {
        "emoji": "🏛️", "desc": "Capital city on the Bay of Bengal",
        "highlight": "Marina Beach, Kapaleeshwarar Temple, Fort St. George",
        "best_time": "November to February",
        "hotels": [
            {"name": "The Leela Palace Chennai",  "stars": 5, "rooms": {"Deluxe": 8500,  "Suite": 18000, "Royal Suite": 45000}},
            {"name": "ITC Grand Chola",            "stars": 5, "rooms": {"Classic": 9000, "Club Room": 14000, "Presidential Suite": 55000}},
            {"name": "Taj Coromandel",             "stars": 5, "rooms": {"Superior": 7500, "Luxury Room": 12000, "Grand Presidential": 38000}},
            {"name": "Radisson Blu Chennai",       "stars": 4, "rooms": {"Standard": 4500, "Deluxe": 6500, "Suite": 12000}},
        ]
    },
    "Coimbatore": {
        "emoji": "🏭", "desc": "Manchester of South India - Nilgiris gateway",
        "highlight": "Nilgiri Hills, Marudamalai Temple, Kovai Kutralam Falls",
        "best_time": "October to March",
        "hotels": [
            {"name": "The Residency Coimbatore", "stars": 5, "rooms": {"Standard": 4200, "Superior": 6000, "Suite": 11000}},
            {"name": "Royal Orchid Central",      "stars": 4, "rooms": {"Standard": 3500, "Deluxe": 5000,  "Suite": 9000}},
            {"name": "Vivanta Coimbatore",        "stars": 5, "rooms": {"Premium": 5500,  "Luxury": 8000,  "Luxury Suite": 14000}},
        ]
    },
    "Madurai": {
        "emoji": "🛕", "desc": "Temple City - Heart of Dravidian Culture",
        "highlight": "Meenakshi Amman Temple, Thirumalai Nayakkar Palace, Gandhi Museum",
        "best_time": "October to March",
        "hotels": [
            {"name": "Heritage Madurai",           "stars": 5, "rooms": {"Classic": 6000, "Heritage Room": 9000, "Suite": 18000}},
            {"name": "Taj Gateway Hotel Madurai",  "stars": 4, "rooms": {"Standard": 4000, "Superior": 6500, "Suite": 12000}},
            {"name": "GRT Regency Madurai",        "stars": 4, "rooms": {"Standard": 3200, "Deluxe": 4800,   "Suite": 9500}},
        ]
    },
    "Ooty": {
        "emoji": "🌿", "desc": "Queen of Hill Stations - Nilgiri Blue Mountains",
        "highlight": "Botanical Gardens, Ooty Lake, Nilgiri Mountain Railway, Tea Estates",
        "best_time": "April to June, September to November",
        "hotels": [
            {"name": "Savoy Hotel Ooty (IHCL)",  "stars": 5, "rooms": {"Classic": 9000,  "Luxury": 14000, "Presidential Suite": 32000}},
            {"name": "Sterling Deer Park Ooty",  "stars": 4, "rooms": {"Cottage": 5500,  "Deluxe": 8000,  "Suite": 15000}},
            {"name": "Sinclairs Retreat Ooty",   "stars": 4, "rooms": {"Standard": 4000, "Superior": 6000,"Suite": 11000}},
        ]
    },
    "Kodaikanal": {
        "emoji": "🏔️", "desc": "Princess of Hill Stations - Silver Cascades",
        "highlight": "Kodai Lake, Pillar Rocks, Bryant Park, Coaker's Walk",
        "best_time": "April to June, October to December",
        "hotels": [
            {"name": "Carlton Hotel Kodaikanal",   "stars": 5, "rooms": {"Standard": 7000, "Deluxe": 11000, "Suite": 22000}},
            {"name": "Club Mahindra Kodaikanal",   "stars": 4, "rooms": {"Studio": 5500,   "Suite": 9000,   "Villa": 18000}},
            {"name": "Elephant Valley Eco Resort", "stars": 4, "rooms": {"Cottage": 4500,  "Deluxe": 7000,  "Treehouse": 14000}},
        ]
    },
    "Mahabalipuram": {
        "emoji": "🗿", "desc": "UNESCO World Heritage - Shore Temple City",
        "highlight": "Shore Temple, Five Rathas, Arjuna's Penance, Crocodile Bank",
        "best_time": "November to February",
        "hotels": [
            {"name": "Taj Fisherman's Cove",              "stars": 5, "rooms": {"Beach Cottage": 12000, "Sea View Suite": 18000, "Presidential": 65000}},
            {"name": "Radisson Blu Resort Mahabalipuram", "stars": 5, "rooms": {"Deluxe": 8000, "Pool View": 12000, "Suite": 22000}},
            {"name": "Chariot Beach Resort",              "stars": 4, "rooms": {"Standard": 5000, "Sea View": 8500, "Suite": 16000}},
        ]
    },
    "Thanjavur": {
        "emoji": "🎭", "desc": "Cultural Capital - Chola Dynasty Legacy",
        "highlight": "Brihadeeswara Temple, Thanjavur Palace, Saraswathi Mahal Library",
        "best_time": "October to February",
        "hotels": [
            {"name": "Ideal River View Resort", "stars": 4, "rooms": {"Standard": 3500, "River View": 5500, "Suite": 10000}},
            {"name": "GRT Grand Thanjavur",     "stars": 4, "rooms": {"Standard": 3000, "Deluxe": 4500,    "Suite": 8500}},
            {"name": "Sangam Hotel Thanjavur",  "stars": 3, "rooms": {"Standard": 2200, "Superior": 3500,  "Suite": 7000}},
        ]
    },
    "Rameswaram": {
        "emoji": "🌊", "desc": "Sacred Island - Ramayana Pilgrimage Site",
        "highlight": "Ramanathaswamy Temple, Pamban Bridge, Adam's Bridge, Dhanushkodi",
        "best_time": "October to April",
        "hotels": [
            {"name": "Hotel Sea View Rameswaram", "stars": 4, "rooms": {"Sea View": 4500,  "Deluxe": 6500,    "Suite": 12000}},
            {"name": "Daiwik Hotels Rameswaram",  "stars": 4, "rooms": {"Standard": 3800, "Temple View": 5500,"Suite": 10000}},
            {"name": "TTDC Tamil Nadu Hotel",     "stars": 3, "rooms": {"Standard": 2000, "Deluxe": 3200,    "Suite": 6000}},
        ]
    },
}

SYSTEM_PROMPT = """You are Lunaris, an AI avatar concierge for Tamil Nadu Grand Hotels.

LANGUAGE: Detect what language the guest uses and reply ENTIRELY in that language.
Supported: Tamil, Hindi, English, French, German, Japanese, Arabic, Spanish, Telugu, Malayalam, Kannada.

PERSONALITY:
- Warm, graceful, passionate about Tamil heritage
- Conversational tone - no bullet points, no markdown (you speak aloud)
- Keep replies to 2-4 sentences unless guest wants details
- Use guest name warmly

DESTINATIONS (Tamil Nadu only):
Chennai (Rs 4500-55000/night), Coimbatore (Rs 3500-14000), Madurai (Rs 3200-18000),
Ooty (Rs 4000-32000), Kodaikanal (Rs 4500-22000), Mahabalipuram (Rs 5000-65000),
Thanjavur (Rs 2200-10000), Rameswaram (Rs 2000-12000)

COLLECT for booking:
1. Guest full name
2. Guest email (for confirmation with QR payment)
3. Destination city
4. Hotel preference
5. Room type
6. Check-in date
7. Check-out date
8. Number of guests
9. Special requests

When all details collected, tell guest a confirmation email with UPI QR code will be sent.
Payment UPI ID: ajay-2210@ptaxis"""

# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------
def generate_upi_qr(amount: float, conf_num: str, guest_name: str) -> str:
    upi_url = (
        f"upi://pay?pa={UPI_ID}"
        f"&pn={UPI_NAME.replace(' ', '%20')}"
        f"&am={amount:.2f}"
        f"&cu=INR"
        f"&tn=Booking%20{conf_num}"
        f"&mc=7011"
    )
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a0a00", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
def send_confirmation_email(booking: dict) -> bool:
    try:
        guest_email = booking.get("guest_email")
        if not guest_email:
            print("❌ No guest email provided")
            return False

        if not SMTP_USER or not SMTP_PASS:
            print("❌ SMTP credentials missing (.env not loaded)")
            return False

        conf_num   = booking["confirmation_number"]
        guest_name = booking["guest_name"]
        hotel      = booking["hotel_name"]
        check_in   = booking["check_in"]
        check_out  = booking["check_out"]
        total      = booking["total_inr"]

        # Generate QR
        qr_b64 = generate_upi_qr(total, conf_num, guest_name)
        qr_bytes = base64.b64decode(qr_b64)

        # Build Email
        msg = MIMEMultipart("related")
        msg["Subject"] = f"Booking Confirmed - {conf_num} | {hotel}"
        msg["From"] = FROM_EMAIL
        msg["To"] = guest_email

        html_content = f"""
        <html>
        <body style="background:#0F0C06;color:#F0E8D0;font-family:Arial;padding:30px">
            <h2 style="color:#C8960C">Booking Confirmed</h2>
            <p>Hello {guest_name},</p>
            <p>Your stay at <b>{hotel}</b> is confirmed.</p>
            <p><b>Check-in:</b> {check_in}<br>
               <b>Check-out:</b> {check_out}<br>
               <b>Total:</b> Rs {total:,.0f}</p>
            <p>Scan below QR to complete UPI payment.</p>
            <img src="cid:qr_code" width="200"/>
            <p>UPI ID: {UPI_ID}</p>
            <p>Thank you for choosing Tamil Nadu Grand Hotels.</p>
        </body>
        </html>
        """

        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText("Your booking is confirmed.", "plain"))
        alt.attach(MIMEText(html_content, "html"))
        msg.attach(alt)

        qr_img = MIMEImage(qr_bytes, "png")
        qr_img.add_header("Content-ID", "<qr_code>")
        msg.attach(qr_img)

        print("🔐 Connecting to Gmail SMTP...")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, guest_email, msg.as_string())

        print("✅ Email sent successfully to:", guest_email)
        return True

    except Exception as e:
        print("❌ EMAIL ERROR:", repr(e))
        return False

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Lunaris - Tamil Nadu Grand Hotels", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bookings_db: dict = {}
last_booking_conf: Optional[str] = None

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class TavusReq(BaseModel):
    guest_name: str
    language: str = "English"

class BookingReq(BaseModel):
    guest_name: str
    guest_email: Optional[str] = ""
    destination: str
    hotel_name: str
    room_type: str
    check_in: str
    check_out: str
    num_guests: int
    special_requests: Optional[str] = ""
    language: Optional[str] = "English"

# ---------------------------------------------------------------------------
# n8n MCP (with local fallback)
# ---------------------------------------------------------------------------
async def call_n8n(action: str, payload: dict) -> dict:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(
                N8N_MCP_URL,
                json={"action": action, "data": payload},
                headers={"Content-Type": "application/json"}
            ) as r:
                if r.status == 200:
                    return await r.json()
    except Exception as e:
        logger.warning(f"n8n unavailable ({e}), using local fallback")

    conf = f"TNGH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4].upper()}"
    return {"success": True, "confirmation_number": conf, "source": "local"}

# ---------------------------------------------------------------------------
# Tavus session
# ---------------------------------------------------------------------------
async def create_tavus_session(guest_name: str, language: str) -> dict:
    greetings = {
        "Tamil":    f"Vanakkam {guest_name}! Naaan Lunaris - Tamil Nadu Grand Hotels AI Concierge. Tamil Naattil engku tanga viruppathu?",
        "Hindi":    f"Namaste {guest_name}! Main Lunaris hoon - Tamil Nadu Grand Hotels ki AI Concierge. Aap kis sheher mein theharenge?",
        "French":   f"Bonjour {guest_name}! Je suis Lunaris, votre concierge IA. Quelle destination du Tamil Nadu vous attire?",
        "German":   f"Guten Tag {guest_name}! Ich bin Lunaris, Ihre KI-Concierge. Welches Ziel in Tamil Nadu interessiert Sie?",
        "Japanese": f"Irasshaimase {guest_name}-sama! Watashi wa Lunaris desu. Tamil Nadu no dochira ni gostaiya desuka?",
        "Arabic":   f"Marhaban {guest_name}! Ana Lunaris, al-murshid al-dhaki li-Tamil Nadu Grand Hotels. Ila ayna turid al-safar?",
        "Spanish":  f"Bienvenido {guest_name}! Soy Lunaris, su concierge IA. Que destino del Tamil Nadu le gustaria visitar?",
        "Telugu":   f"Namaskaram {guest_name}! Nenu Lunaris - Tamil Nadu Grand Hotels AI Concierge. Miru ekkada undaniki istapadu?",
        "Malayalam":f"Swaagatam {guest_name}! Ente peru Lunaris - Tamil Nadu Grand Hotels AI Concierge. Neenga evide thamasikkanam?",
        "Kannada":  f"Namaskara {guest_name}! Naanu Lunaris - Tamil Nadu Grand Hotels AI Concierge. Neevu yaava jagadalli uthkondu?",
        "English":  f"Welcome to Tamil Nadu Grand Hotels, {guest_name}! I'm Lunaris, your AI concierge. Tamil Nadu has magnificent temples, serene hill stations, and golden beaches. Which destination calls to you - Chennai, Ooty, Madurai, Mahabalipuram, or shall I help you explore all eight?",
    }

    greeting     = greetings.get(language, greetings["English"])
    lang_context = f"""
IMPORTANT: Respond ENTIRELY in {language}.
Guest Name: {guest_name}

{SYSTEM_PROMPT}

BOOKING PROCESS:

Collect these details from the guest:

- guest_name
- guest_email
- destination
- hotel_name
- room_type
- check_in
- check_out
- num_guests
- special_requests

Once all details are collected:

Tell the guest:

"I am confirming your booking now."

Then inform them:

"Your booking is confirmed and a confirmation email with QR payment has been sent."

Speak the confirmation naturally.
"""
   

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(
                "https://tavusapi.com/v2/conversations",
                json={
                    "replica_id":             REPLICA_ID,
                    "persona_id":             PERSONA_ID,
                    "conversation_name":      f"Lunaris-{guest_name}-{datetime.now().strftime('%Y%m%d%H%M')}",
                    "conversational_context": lang_context,
                    "custom_greeting":        greeting,
                    "properties": {
                        "max_call_duration":        1800,
                        "participant_left_timeout": 60,
                        "enable_recording":         False,
                    },
                },
                headers={
                    "x-api-key":    TAVUS_API_KEY,
                    "Content-Type": "application/json",
                },
            ) as r:
                data = await r.json()
                if r.status != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Tavus API error {r.status}: {data}"
                    )
                return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Avatar unavailable: {str(e)}")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/health")
async def health():
    return {
        "status":           "ok",
        "version":          "3.0.0",
        "service":          "Lunaris - Tamil Nadu Grand Hotels",
        "timestamp":        datetime.now().isoformat(),
        "destinations":     list(HOTELS.keys()),
        "upi_id":           UPI_ID,
        "email_configured": bool(SMTP_USER and SMTP_PASS),
        "tavus_key_set":    bool(TAVUS_API_KEY),
    }

@app.post("/api/tavus/session")
async def create_avatar_session(req: TavusReq):
    data = await create_tavus_session(req.guest_name, req.language)
    return {
        "conversation_id":  data.get("conversation_id"),
        "conversation_url": data.get("conversation_url"),
        "status":           "active",
    }

@app.delete("/api/tavus/session/{cid}")
async def end_avatar_session(cid: str):
    try:
        async with aiohttp.ClientSession() as session:
            await session.delete(
                f"https://tavusapi.com/v2/conversations/{cid}",
                headers={"x-api-key": TAVUS_API_KEY},
            )
    except Exception as e:
        logger.warning(f"End session error: {e}")
    return {"ended": True, "conversation_id": cid}

# ================= CREATE BOOKING =================
@app.post("/api/booking")
async def create_booking(req: BookingReq):
    try:
        ci = datetime.strptime(req.check_in, "%Y-%m-%d")
        co = datetime.strptime(req.check_out, "%Y-%m-%d")
        nights = max((co - ci).days, 1)
    except Exception:
        nights = 1

    price_night = 5000
    city_data = HOTELS.get(req.destination, {})

    for hotel in city_data.get("hotels", []):
        if hotel["name"].lower() in req.hotel_name.lower() or req.hotel_name.lower() in hotel["name"].lower():
            for rtype, price in hotel.get("rooms", {}).items():
                if rtype.lower() in req.room_type.lower() or req.room_type.lower() in rtype.lower():
                    price_night = price
                    break
            break

    total = price_night * nights

    # Keep n8n booking
    n8n_res = await call_n8n("create_booking", {
        "guest_name": req.guest_name,
        "guest_email": req.guest_email,
        "destination": req.destination,
        "hotel_name": req.hotel_name,
        "room_type": req.room_type,
        "check_in": req.check_in,
        "check_out": req.check_out,
        "num_guests": req.num_guests,
        "special_requests": req.special_requests,
        "nights": nights,
        "total_inr": total,
        "language": req.language,
        "timestamp": datetime.now().isoformat(),
    })

    conf = n8n_res.get(
        "confirmation_number",
        f"TNGH-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    # ✅ Generate QR BEFORE storing
    qr_code = generate_upi_qr(total, conf, req.guest_name)

    booking = {
        "confirmation_number": conf,
        "guest_name": req.guest_name,
        "guest_email": req.guest_email,
        "destination": req.destination,
        "hotel_name": req.hotel_name,
        "room_type": req.room_type,
        "check_in": req.check_in,
        "check_out": req.check_out,
        "num_guests": req.num_guests,
        "nights": nights,
        "price_per_night": price_night,
        "total_inr": total,
        "special_requests": req.special_requests,
        "language": req.language,
        "upi_id": UPI_ID,
        "status": "confirmed",
        "created_at": datetime.now().isoformat(),
        "qr_code_base64": qr_code
    }

    bookings_db[conf] = booking
    logger.info(f"Booking {conf} created for {req.guest_name}")
    global last_booking_conf
    last_booking_conf = conf

    # ❌ DO NOT SEND EMAIL HERE
    return booking

@app.post("/api/avatar-booking")
async def avatar_booking(req: BookingReq):
    """
    Booking triggered by the AI avatar
    """

    # Create booking using existing function
    booking = await create_booking(req)

    # Send confirmation email
    try:
        send_confirmation_email(booking)
    except Exception as e:
        logger.warning(f"Email send failed: {e}")

    return {
        "status": "success",
        "message": "Booking confirmed by avatar",
        "confirmation_number": booking.get("confirmation_number"),
        "email_sent": True
    }
# ---------------------------------------------------------------------------
# REAL-TIME BOOKING SYNC
# ---------------------------------------------------------------------------
from fastapi import WebSocket
import json

ws_clients = []

@app.websocket("/ws/booking")
async def booking_ws(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)

    try:
        while True:
            await ws.receive_text()
    except:
        ws_clients.remove(ws)


async def broadcast_booking_update(data: dict):
    """
    Send booking field updates to all connected frontends
    """
    for ws in ws_clients:
        try:
            await ws.send_text(json.dumps(data))
        except:
            pass
# ================= AVATAR SEND EMAIL =================
@app.post("/api/avatar-send-email/{conf}")
async def avatar_send_email(conf: str):

    print("===== AVATAR EMAIL TRIGGER =====")
    print("CONF:", conf)

    if conf not in bookings_db:
        print("Booking NOT FOUND")
        raise HTTPException(status_code=404, detail="Booking not found")

    booking = bookings_db[conf]
    print("Sending email to:", booking["guest_email"])

    success = send_confirmation_email(booking)

    print("Email success:", success)

    return {"success": success}

# ================= GET BOOKING =================
@app.get("/api/booking/{conf}")
async def get_booking(conf: str):
    if conf not in bookings_db:
        raise HTTPException(status_code=404, detail="Booking not found")
    return bookings_db[conf]


# ================= GET HOTELS =================
@app.get("/api/hotels")
async def get_hotels(city: Optional[str] = None):
    if city:
        if city not in HOTELS:
            raise HTTPException(status_code=404, detail=f"City not found: {city}")
        return {city: HOTELS[city]}
    return HOTELS
@app.post("/api/avatar-auto-email")
async def avatar_auto_email():

    global last_booking_conf

    print("===== AUTO EMAIL FROM AVATAR =====")

    if not last_booking_conf:
        print("No recent booking stored")
        return {"success": False, "message": "No recent booking found"}

    booking = bookings_db.get(last_booking_conf)

    if not booking:
        print("Booking not found in DB")
        return {"success": False, "message": "Booking not found"}

    print("Sending email to:", booking.get("guest_email"))

    success = send_confirmation_email(booking)

    print("Email success:", success)

    return {
        "success": success,
        "confirmation_number": last_booking_conf
    }

# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("  Lunaris - Tamil Nadu Grand Hotels AI Concierge v3.0")
    print("  Frontend + API : http://localhost:8000")
    print("  API Docs       : http://localhost:8000/docs")
    print("  UPI            : " + UPI_ID)
    print("  Email          : " + ("Configured" if SMTP_USER else "Add SMTP_USER/SMTP_PASS to .env"))
    print("=" * 60)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
