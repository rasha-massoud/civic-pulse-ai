"""FastAPI routes for the Meta WhatsApp Cloud API webhook."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import settings
from app.services.ai.multimodal import (
    CitizenLocation,
    ConversationTurn,
    ReportImage,
    analyze_civic_report,
)
from app.services.whatsapp.classifier import detect_language
from app.services.whatsapp.idempotency import get_idempotency_store
from app.services.whatsapp.inbound import InboundWhatsAppMessage, parse_meta_webhook
from app.services.whatsapp.language import format_location_text
from app.services.whatsapp.media import download_media
from app.services.whatsapp.outbound import send_text_message
from app.services.whatsapp.schemas import ConversationStep, SupportedLanguage, WhatsAppSession
from app.services.whatsapp.service import (
    WhatsAppConversationService,
    ai_retry_message,
    voice_retry_message,
)
from app.services.whatsapp.session import get_session_store
from app.services.whatsapp.voice import transcribe_whatsapp_audio

logger = logging.getLogger(__name__)

router = APIRouter()
conversation_service = WhatsAppConversationService()


@router.get("/webhook")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta webhook verification handshake."""
    expected = settings.META_WHATSAPP_WEBHOOK_VERIFY_TOKEN.strip()
    if hub_mode == "subscribe" and hub_verify_token and expected and hub_verify_token == expected:
        logger.info("Meta WhatsApp webhook verified successfully")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    logger.warning("Meta WhatsApp webhook verification failed")
    return PlainTextResponse(content="Forbidden", status_code=403)


def _preferred_language(phone: str) -> SupportedLanguage:
    """Use existing session language when available for voice error replies."""
    session = get_session_store().get(phone)
    if session is not None:
        return session.language
    return SupportedLanguage.EN


async def _body_for_conversation(message: InboundWhatsAppMessage) -> tuple[str, str | None]:
    """Resolve the text body for the conversation service.

    Returns (body, error_reply). If error_reply is set, send that to the citizen
    and skip the conversation service.
    """
    if message.message_type != "audio":
        return message.body, None

    language = _preferred_language(message.phone)
    if not message.media_id:
        logger.warning("Audio message missing media_id | message_id=%s", message.message_id)
        return "", voice_retry_message(language)

    logger.info(
        "Voice processing started | message_id=%s media_id=%s type=audio",
        message.message_id,
        message.media_id,
    )

    try:
        result = await transcribe_whatsapp_audio(
            media_id=message.media_id,
            mime_type=message.media_content_type,
            message_id=message.message_id,
        )
    except Exception:
        logger.exception(
            "Voice processing failed | message_id=%s media_id=%s",
            message.message_id,
            message.media_id,
        )
        return "", voice_retry_message(language)

    transcript = (result.text or "").strip()
    if not transcript:
        logger.info(
            "Empty Whisper transcript | message_id=%s language=%s",
            message.message_id,
            result.language,
        )
        return "", voice_retry_message(language)

    if language == SupportedLanguage.EN:
        language = detect_language(transcript)

    logger.info(
        "Voice note transcribed | message_id=%s text_len=%d language=%s",
        message.message_id,
        len(transcript),
        result.language,
    )
    return transcript, None


async def _images_for_analysis(media_refs: list[str]) -> list[ReportImage]:
    """Resolve stored Meta references into image inputs for OpenAI."""
    images: list[ReportImage] = []
    for media_ref in media_refs[:5]:
        if media_ref.startswith("meta:"):
            media_id = media_ref.removeprefix("meta:").strip()
            if not media_id:
                continue
            downloaded = await download_media(media_id)
            mime_type = downloaded.mime_type or "image/jpeg"
            if not mime_type.startswith("image/"):
                raise ValueError(f"Expected image media, received {mime_type}")
            images.append(
                ReportImage(content=downloaded.content, mime_type=mime_type)
            )
        elif media_ref.startswith(("https://", "http://", "data:image/")):
            images.append(ReportImage(url=media_ref))
        else:
            raise ValueError(f"Unsupported image reference: {media_ref[:30]}")
    return images


async def _analyze_session(session: WhatsAppSession, max_retries: int = 3) -> None:
    """Run joint text/image/location analysis and update session atomically.
    
    Includes retry logic for transient API failures (rate limits, network issues).
    """
    if session.ai_analyzed:
        return

    for attempt in range(1, max_retries + 1):
        try:
            images = await _images_for_analysis(session.media_urls)
            location = CitizenLocation(
                text=session.location_text,
                latitude=session.latitude,
                longitude=session.longitude,
            )
            conversation = [
                ConversationTurn.model_validate(turn)
                for turn in session.conversation_history
                if turn.get("role") in {"citizen", "assistant"} and turn.get("text")
            ]

            result = await asyncio.to_thread(
                analyze_civic_report,
                citizen_text=session.description or "",
                location=location,
                conversation=conversation,
                images=images,
            )
            conversation_service.apply_multimodal_result(session, result)
            logger.info(
                "Multimodal analysis completed | phone=%s category=%s severity=%s confidence=%.2f images=%d",
                session.phone,
                result.category.value,
                result.severity.value,
                result.confidence,
                len(images),
            )
            return  # Success

        except ValueError as e:
            # Schema/configuration errors are not retryable
            logger.error(
                "Multimodal analysis failed (not retryable) | phone=%s error=%s",
                session.phone,
                str(e),
            )
            raise
        except Exception as e:
            logger.warning(
                "Multimodal analysis failed (attempt %d/%d) | phone=%s error=%s",
                attempt,
                max_retries,
                session.phone,
                str(e),
            )
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
            else:
                logger.error(
                    "Multimodal analysis exhausted retries | phone=%s",
                    session.phone,
                )
                raise


async def _ensure_analysis(phone: str) -> WhatsAppSession | None:
    session = conversation_service.store.get(phone)
    if (
        session is not None
        and session.step == ConversationStep.AWAITING_CONFIRMATION
        and not session.ai_analyzed
    ):
        await _analyze_session(session)
    return conversation_service.store.get(phone)


async def process_inbound_message(message: InboundWhatsAppMessage) -> None:
    """Background worker: download/transcribe (if needed), converse, reply via Meta.

    Structured so a real queue can replace FastAPI BackgroundTasks later.
    """
    idempotency = get_idempotency_store()
    message_id = message.message_id

    try:
        location_text = None
        if message.message_type == "location":
            location_text = format_location_text(
                name=message.location_name,
                address=message.location_address,
                latitude=message.latitude,
                longitude=message.longitude,
            )

        body, error_reply = await _body_for_conversation(message)
        if error_reply:
            await send_text_message(to=message.phone, text=error_reply)
            logger.info("Meta WhatsApp reply sent | message_id=%s (voice error)", message_id)
            idempotency.mark_completed(message_id)
            return

        # If this is a confirmation response after a previous analysis failure,
        # finish analysis before allowing the synchronous service to persist.
        try:
            await _ensure_analysis(message.phone)
        except Exception:
            logger.exception(
                "Multimodal analysis failed before confirmation | message_id=%s",
                message_id,
            )
            await send_text_message(
                to=message.phone,
                text=ai_retry_message(_preferred_language(message.phone)),
            )
            idempotency.mark_completed(message_id)
            return

        media_id = None if message.message_type == "audio" else message.media_id
        media_content_type = (
            None if message.message_type == "audio" else message.media_content_type
        )

        reply_text = conversation_service.handle_message(
            phone=message.phone,
            body=body,
            media_id=media_id,
            media_content_type=media_content_type,
            location_text=location_text,
            latitude=message.latitude,
            longitude=message.longitude,
        )

        # A location/image/skip message may have completed evidence collection.
        # Analyze now so the citizen confirms the AI-generated report, not the
        # preliminary keyword-classifier summary.
        try:
            analyzed_session = await _ensure_analysis(message.phone)
        except Exception:
            logger.exception(
                "Multimodal analysis failed after intake | message_id=%s",
                message_id,
            )
            reply_text = ai_retry_message(_preferred_language(message.phone))
        else:
            if analyzed_session is not None and analyzed_session.ai_analyzed:
                reply_text = conversation_service.confirmation_reply(analyzed_session)
        logger.info(
            "Conversation reply generated | message_id=%s reply_len=%d",
            message_id,
            len(reply_text or ""),
        )

        if reply_text:
            await send_text_message(to=message.phone, text=reply_text)
            logger.info("Meta WhatsApp reply sent | message_id=%s", message_id)

        if message.message_type == "audio":
            logger.info("Voice processing completed | message_id=%s", message_id)

        idempotency.mark_completed(message_id)
    except Exception:
        logger.exception("Voice processing failed | message_id=%s", message_id)
        idempotency.mark_failed(message_id)


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Response:
    """Acknowledge Meta immediately; process messages asynchronously."""
    try:
        payload = await request.json()
    except Exception:
        logger.exception("Invalid WhatsApp webhook JSON body")
        return JSONResponse(content={"status": "received"}, status_code=200)

    inbound_messages = parse_meta_webhook(payload if isinstance(payload, dict) else {})
    if not inbound_messages:
        # Status-only or unsupported events — acknowledge without processing.
        return JSONResponse(content={"status": "received"}, status_code=200)

    idempotency = get_idempotency_store()

    for message in inbound_messages:
        logger.info(
            "WhatsApp webhook | message_id=%s from=%s type=%s media_id=%s body_len=%d",
            message.message_id,
            message.phone,
            message.message_type,
            message.media_id or "-",
            len(message.body or ""),
        )

        if not idempotency.try_acquire(message.message_id):
            logger.info(
                "Duplicate WhatsApp message ignored | message_id=%s",
                message.message_id,
            )
            continue

        background_tasks.add_task(process_inbound_message, message)

    # Meta must get 200 quickly; Whisper/conversation run in background.
    return JSONResponse(content={"status": "received"}, status_code=200)
