from unittest.mock import patch

from ai.provider_client import InferenceWorker, describe_missing_completion


def test_missing_completion_error_includes_provider_context_and_payload():
    message = describe_missing_completion(
        {"error": {"message": "Upstream provider unavailable"}, "choices": []},
        "openrouter",
        "provider/model:free",
    )

    assert "openrouter" in message
    assert "provider/model:free" in message
    assert "Upstream provider unavailable" in message
    assert "Response preview" in message


def test_inference_worker_reports_empty_choices_payload():
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"error": {"message": "No capacity"}, "choices": []}

    worker = InferenceWorker("openrouter", "https://example.test/v1", "key", "provider/model:free", [])
    errors = []
    worker.error_occurred.connect(errors.append)

    with patch("ai.provider_client.requests.post", return_value=Response()):
        worker.run()

    assert len(errors) == 1
    assert "No capacity" in errors[0]
    assert "provider/model:free" in errors[0]
