"""Unit tests for multimodal report assembly (no network/API key required)."""

from types import SimpleNamespace

import pytest

from app.services.ai.multimodal import (
    CitizenLocation,
    IssueCategory,
    MultimodalReportAnalyzer,
    MultimodalReportInput,
    ReportImage,
    StructuredCivicReport,
)


class FakeResponses:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_parsed=self.result)


def _result(**overrides):
    data = {
        "category": "pothole",
        "severity": "medium",
        "language": "mixed",
        "summary": "Pothole reported on Hamra Street",
        "description": "The citizen reports a pothole; the photo shows road-surface damage.",
        "location_text": "Hamra Street, Beirut",
        "latitude": 0,
        "longitude": 0,
        "image_findings": [
            {"image_index": 1, "observation": "Road-surface damage is visible.", "supports_report": True}
        ],
        "uncertainties": ["The pothole dimensions are unknown."],
        "confidence": 0.91,
    }
    data.update(overrides)
    return StructuredCivicReport.model_validate(data)


def test_sends_text_image_location_and_schema_in_one_request():
    responses = FakeResponses(_result())
    client = SimpleNamespace(responses=responses)
    location = CitizenLocation(text="Hamra Street, Beirut", latitude=33.8967, longitude=35.4822)
    report_input = MultimodalReportInput(
        citizen_text="fi jouret kbire / big hole",
        location=location,
        images=[ReportImage(content=b"\xff\xd8\xffjpeg bytes", mime_type="image/jpeg")],
    )

    result = MultimodalReportAnalyzer(client=client, model="test-model").analyze(report_input)

    assert result.category == IssueCategory.POTHOLE
    assert (result.latitude, result.longitude) == (33.8967, 35.4822)
    assert responses.kwargs["model"] == "test-model"
    assert responses.kwargs["text_format"] is StructuredCivicReport
    content = responses.kwargs["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "fi jouret kbire" in content[0]["text"]
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert responses.kwargs["store"] is False


def test_model_cannot_invent_or_change_coordinates():
    responses = FakeResponses(
        _result(latitude=10, longitude=20, image_findings=[])
    )
    analyzer = MultimodalReportAnalyzer(client=SimpleNamespace(responses=responses))
    without_coordinates = MultimodalReportInput(citizen_text="garbage near my building")

    result = analyzer.analyze(without_coordinates)

    assert result.latitude is None
    assert result.longitude is None


def test_result_adapts_to_existing_report_persistence_schema():
    result = _result(latitude=33.8967, longitude=35.4822)

    intake = result.to_whatsapp_report_data(
        reporter_phone="96170000000", media_urls=["meta:image-id"]
    )

    assert intake.issue_type == "pothole"
    assert intake.severity == "medium"
    assert (intake.latitude, intake.longitude) == (33.8967, 35.4822)
    assert intake.media_urls == ["meta:image-id"]


def test_rejects_empty_evidence_and_partial_coordinates():
    with pytest.raises(ValueError, match="at least text"):
        MultimodalReportInput()
    with pytest.raises(ValueError, match="provided together"):
        CitizenLocation(latitude=33.9)


def test_rejects_non_image_binary_input():
    with pytest.raises(ValueError, match="unsupported image MIME"):
        ReportImage(content=b"not an image", mime_type="audio/ogg")


def test_rejects_empty_mislabeled_and_oversized_images():
    with pytest.raises(ValueError, match="cannot be empty"):
        ReportImage(content=b"", mime_type="image/jpeg")
    with pytest.raises(ValueError, match="does not match"):
        ReportImage(content=b"plain text", mime_type="image/jpeg")
    with pytest.raises(ValueError, match="10 MB"):
        ReportImage(
            content=b"\xff\xd8\xff" + b"x" * ReportImage.MAX_BYTES,
            mime_type="image/jpeg",
        )


def test_preserves_location_text_and_rejects_nonexistent_image_findings():
    responses = FakeResponses(_result(location_text="Invented address"))
    analyzer = MultimodalReportAnalyzer(client=SimpleNamespace(responses=responses))
    report_input = MultimodalReportInput(
        citizen_text="hole near AUB",
        location=CitizenLocation(text="near AUB"),
        images=[ReportImage(content=b"\xff\xd8\xffimage", mime_type="image/jpeg")],
    )

    result = analyzer.analyze(report_input)
    assert result.location_text == "near AUB"

    responses.result = _result(
        image_findings=[
            {"image_index": 2, "observation": "Unsupported", "supports_report": True}
        ]
    )
    with pytest.raises(ValueError, match="nonexistent image"):
        analyzer.analyze(report_input)
