"""
routers/advisor.py — Gemini-powered AI advisor chat for Accel SYNC.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import Lead, get_db
from routers.catalogue import get_catalogue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advisor", tags=["Advisor"])

# ---------------------------------------------------------------------------
# Gemini client setup
# ---------------------------------------------------------------------------
_gemini_model = None


def _get_gemini():
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel("gemini-3.8-flash")
        return _gemini_model
    except Exception as exc:
        logger.warning("Could not initialise Gemini: %s", exc)
        return None


# ---------------------------------------------------------------------------
# In-memory session store (max 20 sessions, LRU-ish via deque)
# ---------------------------------------------------------------------------
_MAX_SESSIONS = 20
_session_order: deque[str] = deque(maxlen=_MAX_SESSIONS)
_sessions: dict[str, dict[str, Any]] = {}


def _create_session(session_id: str | None = None) -> str:
    sid = session_id or str(uuid.uuid4())
    if sid in _sessions:
        return sid
    # Evict oldest if at capacity
    if len(_sessions) >= _MAX_SESSIONS:
        oldest = _session_order.popleft()
        _sessions.pop(oldest, None)
    _sessions[sid] = {
        "session_id": sid,
        "created_at": datetime.utcnow().isoformat(),
        "history": [],     # list of {"role": "user"|"model", "parts": [{"text": "..."}]}
        "context": {},
        "recommendation": None,
    }
    _session_order.append(sid)
    return sid


def _get_system_prompt() -> str:
    df = get_catalogue()
    catalogue_records = df.to_dict("records")
    # Build a compact JSON for the prompt
    catalogue_json = json.dumps(
        [
            {
                "id": r["product_id"],
                "name": r["product_name"],
                "category": r["category"],
                "price_min": r["price_min_inr_per_month"],
                "price_max": r["price_max_inr_per_month"],
                "setup": r["one_time_setup_inr"],
                "segments": r["target_segments"],
                "requires_gstin": r["requires_gstin"],
                "description": r["description"],
            }
            for r in catalogue_records
        ],
        ensure_ascii=False,
        indent=2,
    )

    return (
        "You are Riya, a friendly and helpful business advisor for Accel Business — "
        "India's leading telecom company for small businesses.\n\n"
        "Your job is to understand a small business owner's needs through a natural "
        "conversation and recommend the perfect bundle of services from our product catalogue.\n\n"
        "LANGUAGE: Detect the user's language from their very first message. If they write in "
        "Hindi, respond entirely in Hindi. If Tamil, respond in Tamil. For English, respond in "
        "English. Never switch languages mid-conversation.\n\n"
        "CONVERSATION FLOW — Ask these questions naturally (not as a numbered list):\n"
        "1. What type of business they run and what city they're in\n"
        "2. How many locations/sites they have\n"
        "3. How many employees (and how many need mobile SIMs)\n"
        "4. Their biggest current pain: internet reliability, customer communication, billing, "
        "security, or something else\n"
        "5. Whether they have a GSTIN (this unlocks more products)\n\n"
        "RECOMMENDATION: Once you have enough info (minimum 3 answers), recommend 2-3 products "
        "from the catalogue that best match their needs. Explain WHY each product helps their "
        "specific business in simple, jargon-free language. Give a clear total monthly price.\n\n"
        "TONE: Warm, helpful, conversational. Use 'aap' in Hindi. Never use jargon. Be concise "
        "— max 3-4 sentences per response.\n\n"
        f"PRODUCT CATALOGUE:\n{catalogue_json}\n\n"
        "When you have a recommendation ready, end your message with a JSON block:\n"
        "<RECOMMENDATION>\n"
        '{"products": ["P01", "P07"], "monthly_total": 1600, "one_time_setup": 0, '
        '"reasoning": "brief reason"}\n'
        "</RECOMMENDATION>"
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
# Fallback response (when Gemini is not available)
# ---------------------------------------------------------------------------
def _fallback_reply(message: str, language: str) -> str:
    if language and "hindi" in language.lower():
        return (
            "Namaste! Main Riya hoon, Accel Business ki advisor. "
            "Aapka swagat hai! Kripya apne business ke baare mein batayein — "
            "aap kis sheher mein hain aur aapka business kya hai?"
        )
    return (
        "Hello! I'm Riya, your Accel Business advisor. "
        "Welcome! Could you tell me a little about your business — "
        "what type of business do you run and which city are you in?"
    )


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
    Send a message to Riya and get an AI-powered response.
    Maintains conversation history per session.
    """
    # Ensure session exists
    sid = _create_session(req.session_id)
    session = _sessions[sid]

    # Update context if provided
    if req.context:
        session["context"].update(req.context)

    # Append user message to history
    session["history"].append({"role": "user", "parts": [{"text": req.message}]})

    language = req.language or "English"
    model = _get_gemini()

    reply_text: str
    if model is None:
        reply_text = _fallback_reply(req.message, language)
    else:
        try:
            system_prompt = _get_system_prompt()
            # Build Gemini chat with system instruction
            chat_session = model.start_chat(
                history=session["history"][:-1]  # all except the last (new) user message
            )
            full_prompt = f"{system_prompt}\n\nUser message: {req.message}"
            # Only inject system prompt once (first message)
            if len(session["history"]) == 1:
                response = chat_session.send_message(full_prompt)
            else:
                response = chat_session.send_message(req.message)
            reply_text = response.text
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            reply_text = _fallback_reply(req.message, language)

    # Parse recommendation block
    clean_reply, reco = _parse_recommendation(reply_text)
    bundle_complete = reco is not None

    if reco:
        session["recommendation"] = reco
        # Persist lead snapshot to DB if we have enough context
        ctx = session.get("context", {})
        try:
            new_lead = Lead(
                session_id=sid,
                business_name=ctx.get("business_name"),
                segment=ctx.get("segment"),
                city=ctx.get("city"),
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

    # Append assistant response to history
    session["history"].append({"role": "model", "parts": [{"text": clean_reply}]})

    return ChatResponse(
        reply=clean_reply,
        language=language,
        recommended_products=reco.get("products") if reco else None,
        bundle_complete=bundle_complete,
        session_id=sid,
    )
