"""FastAPI routes for the Twilio WhatsApp webhook."""

import logging
from typing import Optional

from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.whatsapp.service import WhatsAppConversationService

logger = logging.getLogger(__name__)

router = APIRouter()
conversation_service = WhatsAppConversationService()


def build_twiml_reply(message: str) -> str:
    """Wrap plain text in a Twilio MessagingResponse TwiML document."""
    twiml = MessagingResponse()
    twiml.message(message)
    return str(twiml)


@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
) -> Response:
    """Receive inbound Twilio WhatsApp messages and reply with TwiML."""
    logger.info(
        "WhatsApp webhook | from=%s body_len=%d num_media=%d content_type=%s",
        From,
        len(Body or ""),
        NumMedia,
        MediaContentType0,
    )

    reply_text = conversation_service.handle_message(
        phone=From,
        body=Body,
        num_media=NumMedia,
        media_url=MediaUrl0,
        media_content_type=MediaContentType0,
    )

    return Response(
        content=build_twiml_reply(reply_text),
        media_type="application/xml",
    )
