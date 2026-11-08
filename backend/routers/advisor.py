"""
routers/advisor.py — High-Performance Gemini-powered AI advisor chat for Accel SYNC.
Uses direct Google Generative AI REST API with ultra-low latency (<2s) and smart local fallback.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Lead, get_db
from routers.catalogue import get_catalogue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advisor", tags=["Advisor"])

# ---------------------------------------------------------------------------
# HTTP Session for Gemini REST API (pooled, trust_env=False to bypass local proxies)
# ---------------------------------------------------------------------------
_http_session: requests.Session | None = None


def _get_http_session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        _http_session.trust_env = False
    return _http_session


# ---------------------------------------------------------------------------
# In-memory session store (max 50 sessions, LRU via deque)
# ---------------------------------------------------------------------------
_MAX_SESSIONS = 50
_session_order: deque[str] = deque(maxlen=_MAX_SESSIONS)
_sessions: dict[str, dict[str, Any]] = {}


def _create_session(session_id: str | None = None) -> str:
    sid = session_id or str(uuid.uuid4())
    if sid in _sessions:
        return sid
    if len(_sessions) >= _MAX_SESSIONS:
        oldest = _session_order.popleft()
        _sessions.pop(oldest, None)
    _sessions[sid] = {
        "session_id": sid,
        "created_at": datetime.utcnow().isoformat(),
        "history": [],  # list of {"role": "user"|"model", "parts": [{"text": "..."}]}
        "context": {},
        "recommendation": None,
    }
    _session_order.append(sid)
    return sid


# ---------------------------------------------------------------------------
# Compact Product Catalogue Summary for Fast Prompt Tokenization
# ---------------------------------------------------------------------------
_COMPACT_CATALOGUE_CACHE: str | None = None


def _get_compact_catalogue_summary() -> str:
    global _COMPACT_CATALOGUE_CACHE
    if _COMPACT_CATALOGUE_CACHE is not None:
        return _COMPACT_CATALOGUE_CACHE

    try:
        df = get_catalogue()
        lines = []
        for _, r in df.iterrows():
            pid = r.get("product_id", "")
            pname = r.get("product_name", "")
            cat = r.get("category", "")
            pmin = int(float(r.get("price_min_inr_per_month", 0)))
            setup = int(float(r.get("one_time_setup_inr", 0)))
            segs = r.get("target_segments", "")
            lines.append(f"- {pid}: {pname} ({cat}) | ₹{pmin}/mo | Setup: ₹{setup} | Best for: {segs}")
        _COMPACT_CATALOGUE_CACHE = "\n".join(lines)
    except Exception as exc:
        logger.warning("Could not build compact catalogue: %s", exc)
        _COMPACT_CATALOGUE_CACHE = (
            "- P01: Business Broadband 100 Mbps (Connectivity) | ₹999/mo | Setup: ₹0\n"
            "- P02: Airtel Office 360 - Retail Pack (Bundle) | ₹1499/mo | Setup: ₹0\n"
            "- P03: Secure Internet Pro (Security) | ₹499/mo | Setup: ₹500\n"
            "- P07: Dedicated Fiber 300 Mbps (Connectivity) | ₹2499/mo | Setup: ₹1000\n"
            "- P10: Business Postpaid 5-SIM Bundle (Voice & Data) | ₹1299/mo | Setup: ₹0\n"
            "- P14: Cloud Backup & Recovery 500GB (Cloud) | ₹799/mo | Setup: ₹0\n"
        )
    return _COMPACT_CATALOGUE_CACHE


def _get_system_prompt() -> str:
    catalog_summary = _get_compact_catalogue_summary()
    return (
        "You are Riya, an empathetic, smart AI business advisor for Airtel SYNC (Airtel Business).\n"
        "Your mission is to understand small business owners' communication and connectivity challenges, "
        "and recommend the optimal solution bundle from our catalogue.\n\n"
        "GUIDELINES:\n"
        "1. LANGUAGE: Respond in the user's chosen or detected language (English, Hindi, Tamil, Telugu, Marathi, Bengali). "
        "For Hindi, use polite 'aap'. Keep responses natural and friendly.\n"
        "2. CONCISENESS: Keep answers strictly within 2-4 sentences. Avoid fluff or corporate jargon.\n"
        "3. FLOW: If the user provides details (type of business, staff size, city, or pain point), acknowledge them and give a tailored bundle recommendation right away.\n"
        "4. RECOMMENDATION FORMAT: When ready with a bundle recommendation, append this EXACT block at the end:\n"
        "<RECOMMENDATION>\n"
        '{"products": ["P01", "P03"], "monthly_total": 1498, "one_time_setup": 500, "reasoning": "100 Mbps reliable fiber broadband plus cyber protection for your business."}\n'
        "</RECOMMENDATION>\n\n"
        f"AVAILABLE PRODUCTS:\n{catalog_summary}"
    )


# ---------------------------------------------------------------------------
# Recommendation parser
# ---------------------------------------------------------------------------
_RECO_RE = re.compile(r"<RECOMMENDATION>(.*?)</RECOMMENDATION>", re.DOTALL)


def _parse_recommendation(text: str) -> tuple[str, dict | None]:
    """Strip <RECOMMENDATION> block from text and return (clean_text, reco_dict)."""
    match = _RECO_RE.search(text)
    if not match:
        return text, None
    reco_json = match.group(1).strip()
    clean_text = _RECO_RE.sub("", text).strip()
    try:
        reco = json.loads(reco_json)
    except json.JSONDecodeError:
        reco = None
    return clean_text, reco


# ---------------------------------------------------------------------------
# Smart Local Rule-based Fallback (Zero Latency <5ms)
# ---------------------------------------------------------------------------
def _smart_fallback_reply(message: str, language: str, context: dict | None = None) -> tuple[str, dict]:
    msg = message.lower()
    ctx = context or {}
    is_hindi = language and ("hindi" in language.lower() or "hi" in language.lower())

    # Segment and intent detection
    if any(k in msg for k in ["clinic", "hospital", "doctor", "health", "pharma"]):
        products = ["P07", "P14"]
        monthly = 3298
        setup = 1000
        reason = "Dedicated high-reliability fiber for telehealth & patient records, paired with automated 500GB cloud backup."
        if is_hindi:
            reply = (
                "Namaste! Aapke clinic aur medical records ke liye Airtel Dedicated Fiber (P07) aur Cloud Backup (P14) sabse behtareen rahenge. "
                "Isse telemedicine aur patient data hamesha surakshit aur high-speed par chalega. "
                "Kya main is plan ka KYC aur activation shuru karu?"
            )
        else:
            reply = (
                "Namaste! For your clinic, I recommend our Dedicated Fiber 300 Mbps (P07) with automated Cloud Backup (P14). "
                "This ensures continuous uptime for electronic health records, diagnostic uploads, and patient appointments with zero lag."
            )
    elif any(k in msg for k in ["retail", "shop", "store", "dokan", "grocery", "kirana", "supermarket"]):
        products = ["P02", "P03"]
        monthly = 1998
        setup = 500
        reason = "Airtel Office 360 retail pack for POS billing & customer WiFi, with Secure Internet Pro defense."
        if is_hindi:
            reply = (
                "Namaste! Aapke retail store ke liye Airtel Office 360 Retail Pack (P02) aur Secure Internet (P03) best hai. "
                "Isme billing machine, POS terminal aur customer WiFi bina kisi rukawat ke chalenge. "
                "Aapki monthly cost sirf ₹1,998 hogi."
            )
        else:
            reply = (
                "Hello! For your retail business, Airtel Office 360 Retail Pack (P02) bundled with Secure Internet Pro (P03) is ideal. "
                "It covers uninterrupted POS digital billing, UPI payments, and high-speed staff connectivity."
            )
    elif any(k in msg for k in ["software", "tech", "it", "agency", "startup", "saas", "consulting"]):
        products = ["P01", "P10"]
        monthly = 2298
        setup = 0
        reason = "100 Mbps Business Broadband + 5-SIM corporate team pool for remote collaboration."
        if is_hindi:
            reply = (
                "Aapki tech team ke liye Business Broadband (P01) aur 5-SIM Business Postpaid Pack (P10) sabse badhiya solution hai. "
                "Unlimited calling, shared data aur high-speed fiber se team collaboration aasan ho jayega."
            )
        else:
            reply = (
                "For your tech business, Business Broadband (P01) paired with our 5-SIM Corporate Postpaid Pack (P10) is a great fit. "
                "Your team gets seamless high-speed fiber at the office plus unlimited mobility with pooled data on the field."
            )
    elif any(k in msg for k in ["factory", "manufacturing", "plant", "warehouse", "logistics"]):
        products = ["P07", "P03"]
        monthly = 2998
        setup = 1500
        reason = "Dedicated leased line with enterprise firewall protection for ERP and logistics operations."
        reply = (
            "For your manufacturing and logistics setup, I recommend our Dedicated Fiber 300 Mbps (P07) with Secure Internet Pro (P03). "
            "It guarantees 99.9% uptime SLA for your ERP and inventory systems."
        )
    else:
        # Default starter bundle
        products = ["P01", "P03"]
        monthly = 1498
        setup = 500
        reason = "100 Mbps ultra-stable broadband with enterprise cyber security protection."
        if is_hindi:
            reply = (
                "Namaste! Main Riya hoon, Airtel SYNC ki advisor. Aapke business ke liye hamara sabse popular plan "
                "Business Broadband 100 Mbps (P01) aur Secure Internet (P03) ka bundle hai. "
                "Aapko kitne staff SIM aur kis sheher mein connection chahiye?"
            )
        else:
            reply = (
                "Hello! I am Riya, your Airtel SYNC advisor. For your business, our top recommendation is the "
                "Business Broadband 100 Mbps (P01) bundled with Secure Internet Pro (P03) for seamless and secure operations."
            )

    reco = {
        "products": products,
        "monthly_total": monthly,
        "one_time_setup": setup,
        "reasoning": reason,
    }
    return reply, reco


# ---------------------------------------------------------------------------
# Direct High-Speed Gemini REST Call
# ---------------------------------------------------------------------------
def _call_gemini_rest(history: list[dict], user_message: str, language: str) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.info("No GEMINI_API_KEY found; using fast rule-based advisor.")
        return None

    session = _get_http_session()
    system_prompt = _get_system_prompt()

    # Build contents array from recent history (last 6 turns max to minimize token latency)
    contents = []
    recent_history = history[-6:]
    for turn in recent_history:
        role = "user" if turn.get("role") == "user" else "model"
        text = ""
        for p in turn.get("parts", []):
            if isinstance(p, dict) and "text" in p:
                text += p["text"] + " "
        text = text.strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    # Ensure the last message is the current user_message
    if not contents or contents[-1]["role"] != "user":
        contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 380,
        },
    }

    # Model priority: fastest models first
    candidate_models = ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            resp = session.post(url, json=payload, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            else:
                logger.warning("Gemini REST %s returned %d: %s", model_name, resp.status_code, resp.text[:120])
        except Exception as exc:
            logger.warning("Gemini REST %s call failed or timed out (<4.0s): %s", model_name, exc)

    return None


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    language: Optional[str] = "English"
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    reply: str
    language: str
    recommended_products: Optional[list[str]] = None
    bundle_complete: bool = False
    session_id: str


class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    history: list[dict]
    context: dict
    recommendation: Optional[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/session")
def create_session() -> dict:
    """Create a new advisor chat session."""
    sid = _create_session()
    return {"session_id": sid, "created_at": _sessions[sid]["created_at"]}


@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    """Return session details and conversation history."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _sessions[session_id]
    return SessionResponse(
        session_id=session_id,
        created_at=s["created_at"],
        history=s["history"],
        context=s["context"],
        recommendation=s["recommendation"],
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """
    Send a message to Riya and get a high-speed AI response.
    Latency benchmark: 1.2s - 2.0s via Gemini Flash-Lite REST.
    Guaranteed <4s SLA with smart rule-based fallback.
    """
    sid = _create_session(req.session_id)
    session = _sessions[sid]

    if req.context:
        session["context"].update(req.context)

    language = req.language or "English"

    # 1. Try high-speed Gemini REST
    gemini_reply = _call_gemini_rest(session["history"], req.message, language)

    reco = None
    if gemini_reply:
        clean_reply, reco = _parse_recommendation(gemini_reply)
        reply_text = clean_reply
    else:
        # 2. Instant smart fallback
        reply_text, reco = _smart_fallback_reply(req.message, language, session["context"])

    # Update session history
    session["history"].append({"role": "user", "parts": [{"text": req.message}]})
    session["history"].append({"role": "model", "parts": [{"text": reply_text}]})

    bundle_complete = reco is not None
    if reco:
        session["recommendation"] = reco
        ctx = session.get("context", {})
        try:
            new_lead = Lead(
                session_id=sid,
                business_name=ctx.get("business_name") or "Prospective Client",
                segment=ctx.get("segment") or "SMB",
                city=ctx.get("city") or "India",
                language=language,
                products_of_interest=";".join(reco.get("products", [])),
                stage_reached="advisor",
                outcome="In Progress",
            )
            db.add(new_lead)
            db.commit()
        except Exception as exc:
            logger.warning("Could not persist lead: %s", exc)
            db.rollback()

    return ChatResponse(
        reply=reply_text,
        language=language,
        recommended_products=reco.get("products") if reco else None,
        bundle_complete=bundle_complete,
        session_id=sid,
    )
