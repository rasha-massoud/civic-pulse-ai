"""WhatsApp conversation orchestration and report assembly."""

import logging
from typing import Optional

from app.services.location_quality import (
    is_meaningful_location,
    is_usable_citizen_summary,
)
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
        "en": (
            "We recognized the issue, but need a more precise location. "
            "Please type the street/area name or share your location via WhatsApp."
        ),
        "ar": (
            "تم التعرف على المشكلة، لكن نحتاج إلى موقع أدق. "
            "يرجى كتابة اسم الشارع/المنطقة أو مشاركة الموقع عبر واتساب."
        ),
    },
    "ask_photo": {
        "en": (
            "Would you like to attach a photo? "
            "Send a photo or reply *skip* to continue without one."
        ),
        "ar": (
            "هل ترغب بإرفاق صورة للمشكلة؟ "
            "أرسل صورة أو اكتب *تخطي* للمتابعة بدون صورة."
        ),
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
        "en": "Reply *yes* to submit or *no* to cancel.",
        "ar": "ردّ *نعم* للإرسال أو *لا* للإلغاء.",
    },
    "submitted": {
        "en": (
            "Your report has been submitted successfully. "
            "Reference: {report_id}. Thank you."
        ),
        "ar": (
            "تم إرسال البلاغ بنجاح. "
            "الرقم المرجعي: {report_id}. شكراً لمساهمتك."
        ),
    },
    "cancelled": {
        "en": "Report cancelled. You can send a new issue anytime.",
        "ar": "تم إلغاء البلاغ. يمكنك إرسال بلاغ جديد في أي وقت.",
    },
    "error": {
        "en": "Sorry, something went wrong. Please try again in a moment.",
        "ar": "عذراً، صار في مشكلة. حاول مرة تانية بعد شوي.",
    },
    "ai_error": {
        "en": (
            "I couldn't analyze the complete report right now. "
            "Please try again in a moment; your information is still saved."
        ),
        "ar": (
            "ما قدرت حلّل البلاغ الكامل هلّق. "
            "جرّب كمان مرة بعد شوي؛ معلوماتك بعدها محفوظة."
        ),
    },
}


def _msg(key: str, language: SupportedLanguage, **kwargs: str) -> str:
    text = MESSAGES[key][language.value]
    return text.format(**kwargs) if kwargs else text


def voice_retry_message(language: Optional[SupportedLanguage] = None) -> str:
    """Citizen-facing reply when voice download/transcription fails or is empty."""
    return _msg("voice_unintelligible", language or SupportedLanguage.EN)


def ai_retry_message(language: Optional[SupportedLanguage] = None) -> str:
    """Citizen-facing reply when multimodal analysis cannot complete."""
    return _msg("ai_error", language or SupportedLanguage.EN)


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


def _looks_like_report_content(text: str) -> bool:
    """True when the first message already describes an issue (not just "hi")."""
    stripped = (text or "").strip()
    if not stripped:
        return False
    if classify_issue(stripped):
        return True
    words = [w for w in stripped.split() if w]
    # Short multi-word Arabic/English statements are often complete reports
    # (e.g. "في مشكلة بسوديكو") even without category keywords.
    if len(words) >= 3 and len(stripped) >= 10:
        return True
    # Long free-form content (typical Whisper transcripts / detailed text).
    return len(stripped) >= 40


def append_citizen_evidence(session: WhatsAppSession, text: str) -> bool:
    """Accumulate raw citizen/Whisper text without dropping earlier turns.

    Returns True when new evidence was appended (triggers re-analysis upstream).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    existing = (session.raw_citizen_text or "").strip()
    if not existing:
        session.raw_citizen_text = cleaned
        # Provisional municipal description until multimodal rewrites it.
        if not (session.description or "").strip():
            session.description = cleaned
        return True
    if cleaned == existing or cleaned in existing.split("\n"):
        return False
    session.raw_citizen_text = f"{existing}\n{cleaned}"
    # Keep provisional description aligned with full evidence pre-AI polish.
    if not (session.citizen_summary or "").strip():
        session.description = session.raw_citizen_text
    return True


def is_control_utterance(text: str) -> bool:
    """True for workflow commands that must never become report evidence."""
    return is_confirmation(text) or is_rejection(text) or is_skip_photo(text)


def _is_location_reply(text: str) -> bool:
    """True for short place-name replies (not full issue narratives)."""
    cleaned = (text or "").strip()
    if is_control_utterance(cleaned):
        return False
    if not is_meaningful_location(cleaned):
        return False
    # Issue keywords mean this turn is about the problem, not only the place.
    if classify_issue(cleaned):
        return False
    return len(cleaned) <= 48


class WhatsAppConversationService:
    """Handles multi-step WhatsApp intake for a single inbound message."""

    def __init__(self, store: Optional[SessionStore] = None) -> None:
        self._store = store

    @property
    def store(self) -> SessionStore:
        """Use an injected store, or resolve the active application store lazily."""
        return self._store or get_session_store()

    def handle_message(
        self,
        phone: str,
        body: str,
        media_id: Optional[str] = None,
        media_content_type: Optional[str] = None,
        location_text: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> str:
        """Process one inbound message and return the reply text."""
        try:
            text = (body or "").strip()
            language = detect_language(text) if text else SupportedLanguage.EN

            session = self._get_or_create_session(phone, language)
            control = is_control_utterance(text)
            # Workflow commands never change the language chosen from report content.
            if text and not control:
                session.language = detect_language(text)

            # Confirmation is a strict decision state: no extraction, location
            # assignment, or evidence accumulation is allowed here.
            if session.step == ConversationStep.AWAITING_CONFIRMATION:
                reply = self._advance(session, text)
                if self.store.get(phone) is not None:
                    self.store.set(phone, session)
                return reply

            if location_text and location_text.strip():
                if is_meaningful_location(location_text):
                    if (session.location_text or "") != location_text.strip():
                        session.ai_analyzed = False
                    session.location_text = location_text.strip()
                else:
                    logger.info(
                        "Ignoring non-meaningful location text | phone=%s text=%s",
                        phone,
                        location_text.strip()[:40],
                    )
            if latitude is not None and longitude is not None:
                if session.latitude != latitude or session.longitude != longitude:
                    session.ai_analyzed = False
                session.latitude = latitude
                session.longitude = longitude

            if text:
                is_greeting = (
                    session.step == ConversationStep.GREETING
                    and not _looks_like_report_content(text)
                )
                if not control and not is_greeting:
                    session.conversation_history.append(
                        {"role": "citizen", "text": text}
                    )
                    if append_citizen_evidence(session, text):
                        # New text after a prior AI pass must be re-merged.
                        session.ai_analyzed = False

            # Only treat image media IDs as photo attachments (not voice notes).
            if media_id and media_content_type and media_content_type.startswith("image/"):
                media_ref = f"meta:{media_id}"
                if media_ref not in session.media_urls:
                    session.media_urls.append(media_ref)
                    session.photo_resolved = True
                    session.ai_analyzed = False
                    logger.info(
                        "WhatsApp image received | phone=%s media_id=%s mime=%s",
                        phone,
                        media_id,
                        media_content_type,
                    )
            elif media_id and not media_content_type:
                # Image caption/media without mime still allowed for photo step.
                media_ref = f"meta:{media_id}"
                if media_ref not in session.media_urls:
                    session.media_urls.append(media_ref)
                    session.photo_resolved = True
                    session.ai_analyzed = False
                    logger.info(
                        "WhatsApp image received | phone=%s media_id=%s mime=unknown",
                        phone,
                        media_id,
                    )

            reply = self._advance(session, text)
            # Confirmation/cancellation deletes the completed session. Do not
            # accidentally recreate it after _advance returns.
            if self.store.get(phone) is not None:
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
            if (
                _looks_like_report_content(text)
                or session.media_urls
                or session.location_text
            ):
                if text and not is_control_utterance(text):
                    self._apply_text_extractions(session, text)
                if not session.description and session.media_urls:
                    session.description = "Photo attached by reporter"
                return self.decide_next_reply(session)
            return _msg("greeting", session.language)

        if step == ConversationStep.AWAITING_ISSUE:
            if text and not is_control_utterance(text):
                self._apply_text_extractions(session, text)
            if not session.description and session.media_urls:
                session.description = "Photo attached by reporter"
            return self.decide_next_reply(session)

        if step == ConversationStep.AWAITING_LOCATION:
            if text and not is_control_utterance(text):
                self._apply_text_extractions(session, text)
            return self.decide_next_reply(session)

        if step == ConversationStep.AWAITING_PHOTO:
            if is_skip_photo(text):
                session.photo_resolved = True
            elif text and not is_control_utterance(text):
                self._apply_text_extractions(session, text)
            if session.media_urls:
                session.photo_resolved = True
            return self.decide_next_reply(session)

        if step == ConversationStep.AWAITING_CONFIRMATION:
            if is_rejection(text):
                phone = session.phone
                language = session.language
                self.store.delete(phone)
                logger.info("WhatsApp report cancelled | phone=%s", phone)
                return _msg("cancelled", language)
            if is_confirmation(text):
                if self.is_ready_for_confirmation(session):
                    return self._finalize_report(session)
                return self.decide_next_reply(session)
            return self.decide_next_reply(session)

        session.step = ConversationStep.AWAITING_ISSUE
        return _msg("ask_issue", session.language)

    def missing_required_fields(self, session: WhatsAppSession) -> list[str]:
        """Return required report fields still missing."""
        # Drop generic location fragments so they never satisfy the requirement.
        if session.location_text and not is_meaningful_location(session.location_text):
            session.location_text = None

        missing: list[str] = []
        has_evidence = bool(
            (session.raw_citizen_text or session.description or session.citizen_summary or "").strip()
            or session.media_urls
        )
        if not has_evidence:
            missing.append("description")
        if not session.issue_type:
            missing.append("issue_type")
        has_location = is_meaningful_location(session.location_text) or (
            session.latitude is not None and session.longitude is not None
        )
        if not has_location:
            missing.append("location")
        return missing

    def is_ready_for_confirmation(self, session: WhatsAppSession) -> bool:
        """Require complete evidence, resolved photo choice, and AI analysis."""
        if not session.photo_resolved or not session.ai_analyzed:
            return False
        return not self.missing_required_fields(session)

    def reply_for_missing_fields(self, session: WhatsAppSession) -> str:
        """Compatibility entry point delegated to the state-machine authority."""
        return self.decide_next_reply(session)

    def decide_next_reply(self, session: WhatsAppSession) -> str:
        """Set the one correct next step and render its citizen-facing reply."""
        if session.media_urls:
            session.photo_resolved = True

        missing = self.missing_required_fields(session)
        if "description" in missing or "issue_type" in missing:
            session.step = ConversationStep.AWAITING_ISSUE
            return _msg("ask_issue", session.language)

        if "location" in missing:
            session.step = ConversationStep.AWAITING_LOCATION
            return _msg("ask_location", session.language)

        if not session.photo_resolved:
            session.step = ConversationStep.AWAITING_PHOTO
            return _msg("ask_photo", session.language)

        session.step = ConversationStep.AWAITING_CONFIRMATION
        if not session.ai_analyzed:
            # Holding reply: the router enriches data, then calls this method again.
            return _msg("confirm_prompt", session.language)
        return f"{self._build_summary(session)}\n\n{_msg('confirm_prompt', session.language)}"

    def _apply_text_extractions(self, session: WhatsAppSession, text: str) -> None:
        """Pull issue/location cues from any turn — step only guides questions."""
        cleaned = (text or "").strip()
        if not cleaned:
            return
        issue_type = classify_issue(cleaned)
        # Bare generics like "طريق" must not overwrite a known category.
        substantial = len(cleaned) >= 12
        if issue_type and substantial:
            if not session.issue_type or session.issue_type == "other" or len(cleaned) >= 20:
                session.issue_type = issue_type
        elif not session.issue_type:
            session.issue_type = "other"

        # Prefer phrase extraction; accept short place-only replies as location.
        from app.services.ai.multimodal import extract_location_text_from_transcript

        extracted = extract_location_text_from_transcript(cleaned)
        if is_meaningful_location(extracted):
            if (session.location_text or "") != extracted:
                session.ai_analyzed = False
            session.location_text = extracted
        elif _is_location_reply(cleaned):
            if (session.location_text or "") != cleaned:
                session.ai_analyzed = False
            session.location_text = cleaned

    def _citizen_facing_issue_label(self, session: WhatsAppSession) -> str:
        """Canonical short category label — never AI/Whisper sentence copy."""
        return format_issue_type(session.issue_type or "other", session.language)

    def _optional_confirmation_detail(self, session: WhatsAppSession) -> str | None:
        """Extra line only when it adds material info beyond issue + location."""
        detail = (session.citizen_summary or "").strip()
        if not detail or len(detail) > 100:
            return None

        issue = self._citizen_facing_issue_label(session)
        location = (session.location_text or "").strip()
        if self._detail_repeats_issue_or_location(detail, issue, location):
            return None

        lowered = detail.casefold()
        material_signals = (
            "مغلق",
            "بالكامل",
            "بغزارة",
            "خطر",
            "عاجل",
            "غارق",
            "blocked",
            "closed",
            "flooding",
            "gushing",
            "urgent",
            "dangerous",
            "completely",
        )
        if not any(signal in detail or signal in lowered for signal in material_signals):
            return None
        return detail

    @staticmethod
    def _detail_repeats_issue_or_location(
        detail: str, issue: str, location: str
    ) -> bool:
        """True when detail is basically the same as issue and/or location."""
        norm = " ".join(detail.split()).casefold()
        issue_n = " ".join(issue.split()).casefold()
        loc_n = " ".join(location.split()).casefold()
        if not norm:
            return True
        if issue_n and (issue_n in norm or norm in issue_n):
            # Detail is mostly the issue label (optionally plus location).
            remainder = norm.replace(issue_n, "").strip(" :-–—,.")
            if not remainder or (loc_n and remainder == loc_n):
                return True
            if loc_n and loc_n in remainder and len(remainder) <= len(loc_n) + 8:
                return True
        if loc_n and norm == loc_n:
            return True
        # Near-duplicate when detail equals "issue + location" phrasing.
        if issue_n and loc_n:
            compact = norm.replace(issue_n, "").replace(loc_n, "").strip(" :-–—,.")
            if len(compact) <= 4:
                return True
        return False

    def _build_summary(self, session: WhatsAppSession) -> str:
        """Minimal citizen-facing confirmation (category + location + photo).

        Built only here — dashboard keeps richer AI fields separately.
        """
        issue_label = self._citizen_facing_issue_label(session)
        location = (session.location_text or "—").strip() or "—"
        photo_count = len(session.media_urls)
        extra = self._optional_confirmation_detail(session)

        if session.language == SupportedLanguage.AR:
            lines = [
                "ملخص البلاغ",
                "",
                f"المشكلة: {issue_label}",
                f"الموقع: {location}",
            ]
            if extra:
                lines.append(f"ملاحظة: {extra}")
            if photo_count >= 1:
                lines.append("الصورة: مرفقة")
            return "\n".join(lines)

        lines = [
            "Report Summary",
            "",
            f"Issue: {issue_label}",
            f"Location: {location}",
        ]
        if extra:
            lines.append(f"Note: {extra}")
        if photo_count >= 1:
            lines.append("Photo: Attached")
        return "\n".join(lines)

    def confirmation_reply(self, session: WhatsAppSession) -> str:
        """Compatibility entry point delegated to the state-machine authority."""
        return self.decide_next_reply(session)

    def apply_multimodal_result(self, session: WhatsAppSession, result: object) -> None:
        """Merge AI output into session — never replace good fields with null/unknown.

        Raw Whisper/citizen text stays in raw_citizen_text. Polished WhatsApp copy
        comes from citizen_summary / citizen_issue_label. Keyword classification is
        provisional — joint multimodal evidence is authoritative for category when
        it is concrete (not a weak 'other' overwrite of a known issue).
        """
        # Preserve raw evidence if only description was set during intake.
        if not session.raw_citizen_text and (session.description or "").strip():
            session.raw_citizen_text = session.description

        category = getattr(getattr(result, "category", None), "value", None)
        if category and category != "other":
            session.issue_type = category
        elif category == "other" and not session.issue_type:
            session.issue_type = "other"
        # else: keep existing non-empty issue_type when model returns "other"

        # Municipal English fields for the dashboard / DB.
        description = (getattr(result, "description", None) or "").strip()
        if description and is_usable_citizen_summary(description):
            session.description = description
        elif description and not (session.description or "").strip():
            session.description = description

        summary = (getattr(result, "summary", None) or "").strip()
        if summary and is_usable_citizen_summary(summary):
            session.ai_summary = summary
        elif summary and not (session.ai_summary or "").strip():
            session.ai_summary = summary

        citizen_summary = (getattr(result, "citizen_summary", None) or "").strip()
        if is_usable_citizen_summary(citizen_summary):
            session.citizen_summary = citizen_summary
        # Reject "لا يوجد معلومات كافية" / empty — keep prior polished summary.

        citizen_issue_label = (getattr(result, "citizen_issue_label", None) or "").strip()
        if citizen_issue_label and "معلومات كافية" not in citizen_issue_label:
            if "not enough" not in citizen_issue_label.casefold():
                session.citizen_issue_label = citizen_issue_label

        severity = getattr(getattr(result, "severity", None), "value", None)
        if severity:
            session.ai_severity = severity

        confidence = getattr(result, "confidence", None)
        if confidence is not None:
            session.ai_confidence = confidence

        findings = getattr(result, "image_findings", None) or []
        if findings:
            session.ai_image_findings = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in findings
            ]
        uncertainties = getattr(result, "uncertainties", None)
        if uncertainties is not None:
            session.ai_uncertainties = list(uncertainties)

        result_location = (getattr(result, "location_text", None) or "").strip()
        if is_meaningful_location(result_location):
            # Prefer existing meaningful citizen-provided location; fill gaps only.
            if not is_meaningful_location(session.location_text):
                session.location_text = result_location
        elif session.location_text and not is_meaningful_location(session.location_text):
            session.location_text = None
        # Never clear a meaningful session location because the model returned null.

        if session.latitude is None and getattr(result, "latitude", None) is not None:
            session.latitude = result.latitude
            session.longitude = result.longitude
        elif session.latitude is not None:
            pass
        else:
            session.latitude = getattr(result, "latitude", None)
            session.longitude = getattr(result, "longitude", None)

        session.ai_analyzed = True
        self.store.set(session.phone, session)

        logger.info(
            "AI fields applied to session | phone=%s category=%s location=%s "
            "severity=%s confidence=%s citizen_summary_len=%d missing=%s",
            session.phone,
            session.issue_type,
            (session.location_text or "")[:80] or "-",
            session.ai_severity,
            session.ai_confidence,
            len(session.citizen_summary or ""),
            self.missing_required_fields(session),
        )

    def _finalize_report(self, session: WhatsAppSession) -> str:
        report_data = WhatsAppReportData(
            reporter_phone=session.phone,
            issue_type=session.issue_type or "other",
            description=session.description or "",
            location_text=session.location_text or "",
            media_urls=list(session.media_urls),
            language=session.language.value,
            severity=session.ai_severity,
            latitude=session.latitude,
            longitude=session.longitude,
            ai_summary=session.ai_summary,
            ai_confidence=session.ai_confidence,
            ai_image_findings=session.ai_image_findings,
            ai_uncertainties=session.ai_uncertainties,
        )
        report_id = create_report_from_whatsapp(report_data)
        self.store.delete(session.phone)
        return _msg("submitted", session.language, report_id=report_id)


def decide_next_reply(session: WhatsAppSession) -> str:
    """Public functional entry point for state-machine tests and integrations."""
    return WhatsAppConversationService().decide_next_reply(session)
