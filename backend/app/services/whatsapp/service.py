"""WhatsApp conversation orchestration and report assembly."""

import logging
from typing import Optional

from app.services.whatsapp.classifier import (
    classify_issue,
    detect_language,
    format_issue_type,
    is_confirmation,
    is_rejection,
    is_skip_photo,
)
from app.services.whatsapp.schemas import (
    ConversationStep,
    SupportedLanguage,
    WhatsAppReportData,
    WhatsAppSession,
)
from app.services.whatsapp.session import SessionStore, get_session_store

logger = logging.getLogger(__name__)

MESSAGES = {
    "greeting": {
        "en": (
            "Hello! Welcome to CivicPulse AI for Beirut Municipality.\n"
            "What infrastructure issue would you like to report? "
            "(e.g. pothole, garbage, street light, water leak, road damage)"
        ),
        "ar": (
            "أهلاً! مرحباً بك في CivicPulse AI لبلدية بيروت.\n"
            "شو المشكلة يلي بدك تبلّغ عنها؟ "
            "(مثلاً: حفرة، زبالة، إنارة، تسريب مياه، ضرر بالطريق)"
        ),
    },
    "ask_issue": {
        "en": "Please describe the issue you want to report.",
        "ar": "من فضلك صف المشكلة يلي بدك تبلّغ عنها.",
    },
    "ask_location": {
        "en": "Where is the issue located? Please share the area, street, or landmark.",
        "ar": "وين المشكلة؟ شاركنا المنطقة، الشارع، أو معلم قريب.",
    },
    "ask_photo": {
        "en": "Can you send a photo of the issue? Reply *skip* if you don't have one.",
        "ar": "فيكن تبعتو صورة للمشكلة؟ اكتب *تخطي* إذا ما عندكن صورة.",
    },
    "unclassified_issue": {
        "en": (
            "Thanks! I noted your report. "
            "If you can, mention the type (pothole, garbage, street light, water leak, road damage)."
        ),
        "ar": (
            "شكراً! سجّلنا بلاغك. "
            "إذا فيكن، حدّدوا النوع (حفرة، زبالة، إنارة، تسريب مياه، ضرر بالطريق)."
        ),
    },
    "voice_unintelligible": {
        "en": (
            "I couldn't understand that voice message. "
            "Please try recording it again or type your message."
        ),
        "ar": (
            "ما قدرت افهم الرسالة الصوتية. "
            "جرّب ابعتها مرة تانية أو اكتب الرسالة."
        ),
    },
    "confirm_prompt": {
        "en": "Reply *yes* to submit your report or no to cancel and start a new report.",
        "ar": "ردّ *نعم* للإرسال أو *لا* للبدء من جديد.",
    },
    "submitted": {
        "en": "Your report has been submitted. Reference: {report_id}. Thank you!",
        "ar": "تم إرسال بلاغك. الرقم المرجعي: {report_id}. شكراً إلك!",
    },
    "cancelled": {
        "en": "Report cancelled. Send a new message anytime to start again.",
        "ar": "تم إلغاء البلاغ. ابعت رسالة جديدة بأي وقت للبدء من جديد.",
    },
    "error": {
        "en": "Sorry, something went wrong. Please try again in a moment.",
        "ar": "عذراً، صار في مشكلة. حاول مرة تانية بعد شوي.",
    },
}


def _msg(key: str, language: SupportedLanguage, **kwargs: str) -> str:
    text = MESSAGES[key][language.value]
    return text.format(**kwargs) if kwargs else text


def voice_retry_message(language: Optional[SupportedLanguage] = None) -> str:
    """Citizen-facing reply when voice download/transcription fails or is empty."""
    return _msg("voice_unintelligible", language or SupportedLanguage.EN)


def create_report_from_whatsapp(data: WhatsAppReportData) -> str:
    """Persist a confirmed WhatsApp report and return the dashboard ticket reference."""
    from app.db.session import SessionLocal
    from app.services.reports import create_report_from_intake

    db = SessionLocal()
    try:
        report = create_report_from_intake(db, data)
        ticket_ref = f"CIV-{report.issue_id:06d}"
        logger.info("WhatsApp intake saved | ticket=%s report_id=%s", ticket_ref, report.id)
        return ticket_ref
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class WhatsAppConversationService:
    """Handles multi-step WhatsApp intake for a single inbound message."""

    def __init__(self, store: Optional[SessionStore] = None) -> None:
        self.store = store or get_session_store()

    def handle_message(
        self,
        phone: str,
        body: str,
        media_id: Optional[str] = None,
        media_content_type: Optional[str] = None,
        location_text: Optional[str] = None,
    ) -> str:
        """Process one inbound message and return the reply text."""
        try:
            text = (body or "").strip()
            language = detect_language(text) if text else SupportedLanguage.EN

            session = self._get_or_create_session(phone, language)
            if text:
                session.language = detect_language(text)

            if location_text and location_text.strip():
                session.location_text = location_text.strip()

            # Only treat image media IDs as photo attachments (not voice notes).
            if media_id and media_content_type and media_content_type.startswith("image/"):
                media_ref = f"meta:{media_id}"
                if media_ref not in session.media_urls:
                    session.media_urls.append(media_ref)
            elif media_id and not media_content_type:
                # Image caption/media without mime still allowed for photo step.
                media_ref = f"meta:{media_id}"
                if media_ref not in session.media_urls:
                    session.media_urls.append(media_ref)

            reply = self._advance(session, text)
            self.store.set(phone, session)
            return reply
        except Exception:
            logger.exception("Failed to handle WhatsApp message from %s", phone)
            return _msg("error", detect_language(body or ""))

    def _get_or_create_session(
        self, phone: str, language: SupportedLanguage
    ) -> WhatsAppSession:
        session = self.store.get(phone)
        if session is None:
            session = WhatsAppSession(phone=phone, language=language)
            self.store.set(phone, session)
        return session

    def _advance(self, session: WhatsAppSession, text: str) -> str:
        step = session.step

        if step == ConversationStep.GREETING:
            session.step = ConversationStep.AWAITING_ISSUE
            return _msg("greeting", session.language)

        if step == ConversationStep.AWAITING_ISSUE:
            return self._handle_issue_step(session, text)

        if step == ConversationStep.AWAITING_LOCATION:
            return self._handle_location_step(session, text)

        if step == ConversationStep.AWAITING_PHOTO:
            return self._handle_photo_step(session, text)

        if step == ConversationStep.AWAITING_CONFIRMATION:
            return self._handle_confirmation_step(session, text)

        session.step = ConversationStep.AWAITING_ISSUE
        return _msg("ask_issue", session.language)

    def _handle_issue_step(self, session: WhatsAppSession, text: str) -> str:
        if not text and not session.media_urls:
            return _msg("ask_issue", session.language)

        if text:
            session.description = text
            issue_type = classify_issue(text)
            if issue_type:
                session.issue_type = issue_type
            elif not session.issue_type:
                session.issue_type = "other"

        if not session.description and session.media_urls:
            session.description = "Photo attached by reporter"

        if not session.issue_type and text:
            session.issue_type = classify_issue(text) or "other"

        return self._request_missing_fields(session)

    def _handle_location_step(self, session: WhatsAppSession, text: str) -> str:
        # Native WhatsApp location may already have been applied in handle_message.
        if session.location_text:
            return self._request_missing_fields(session)

        if not text:
            return _msg("ask_location", session.language)

        session.location_text = text
        return self._request_missing_fields(session)

    def _handle_photo_step(self, session: WhatsAppSession, text: str) -> str:
        if session.media_urls:
            return self._go_to_confirmation(session)

        if is_skip_photo(text):
            return self._go_to_confirmation(session)

        if text and not session.media_urls:
            return _msg("ask_photo", session.language)

        return _msg("ask_photo", session.language)

    def _handle_confirmation_step(self, session: WhatsAppSession, text: str) -> str:
        if is_confirmation(text):
            return self._finalize_report(session)

        if is_rejection(text):
            self.store.delete(session.phone)
            return _msg("cancelled", session.language)

        return f"{self._build_summary(session)}\n\n{_msg('confirm_prompt', session.language)}"

    def _request_missing_fields(self, session: WhatsAppSession) -> str:
        if not session.location_text:
            session.step = ConversationStep.AWAITING_LOCATION
            prefix = ""
            if session.issue_type == "other":
                prefix = _msg("unclassified_issue", session.language) + "\n\n"
            return prefix + _msg("ask_location", session.language)

        if not session.media_urls:
            session.step = ConversationStep.AWAITING_PHOTO
            return _msg("ask_photo", session.language)

        return self._go_to_confirmation(session)

    def _go_to_confirmation(self, session: WhatsAppSession) -> str:
        session.step = ConversationStep.AWAITING_CONFIRMATION
        return (
            f"{self._build_summary(session)}\n\n"
            f"{_msg('confirm_prompt', session.language)}"
        )

    def _build_summary(self, session: WhatsAppSession) -> str:
        issue_label = format_issue_type(
            session.issue_type or "other", session.language
        )
        photo_count = len(session.media_urls)

        if session.language == SupportedLanguage.AR:
            return (
                "ملخص البلاغ:\n"
                f"- النوع: {issue_label}\n"
                f"- الوصف: {session.description or '—'}\n"
                f"- الموقع: {session.location_text or '—'}\n"
                f"- الصور: {photo_count}"
            )

        return (
            "Report summary:\n"
            f"- Type: {issue_label}\n"
            f"- Description: {session.description or '—'}\n"
            f"- Location: {session.location_text or '—'}\n"
            f"- Photos: {photo_count}"
        )

    def _finalize_report(self, session: WhatsAppSession) -> str:
        report_data = WhatsAppReportData(
            reporter_phone=session.phone,
            issue_type=session.issue_type or "other",
            description=session.description or "",
            location_text=session.location_text or "",
            media_urls=list(session.media_urls),
            language=session.language.value,
        )
        report_id = create_report_from_whatsapp(report_data)
        self.store.delete(session.phone)
        return _msg("submitted", session.language, report_id=report_id)
