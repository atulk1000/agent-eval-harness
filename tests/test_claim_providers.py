import json
import unittest

from agenteval.claim_eval.providers import (
    JudgeProviderError,
    JudgeProviderTimeout,
    MockJudgeProvider,
    OpenAICompatibleJudgeProvider,
)


class ClaimProviderTests(unittest.TestCase):
    def test_mock_provider_fills_first_evidence_reference(self):
        provider = MockJudgeProvider()
        response = provider.judge(_claim(), [_evidence()])
        self.assertEqual(response.output["evidence_refs"], ["evidence_1"])

    def test_mock_provider_can_timeout(self):
        provider = MockJudgeProvider(failure="timeout")
        with self.assertRaises(JudgeProviderTimeout):
            provider.judge(_claim(), [_evidence()])

    def test_openai_compatible_accepts_direct_structured_response(self):
        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=lambda payload: _output(),
        )
        response = provider.judge(_claim(), [_evidence()])
        self.assertEqual(response.output["verdict"], "supported")

    def test_openai_compatible_decodes_chat_completion_usage(self):
        response_payload = {
            "choices": [{"message": {"content": json.dumps(_output())}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 8},
        }
        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=lambda payload: response_payload,
        )
        response = provider.judge(_claim(), [_evidence()])
        self.assertEqual(response.input_tokens, 20)
        self.assertEqual(response.output_tokens, 8)

    def test_openai_compatible_extracts_claim_array(self):
        response_payload = {
            "choices": [
                {"message": {"content": json.dumps({"claims": [{"text": "Acme is active."}]})}}
            ]
        }
        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=lambda payload: response_payload,
        )
        self.assertEqual(provider.extract("Acme is active.")[0]["text"], "Acme is active.")

    def test_openai_compatible_rejects_unreadable_response(self):
        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=lambda payload: {"choices": []},
        )
        with self.assertRaises(JudgeProviderError):
            provider.judge(_claim(), [_evidence()])

    def test_redaction_flag_is_recorded(self):
        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=lambda payload: _output(),
            redaction_hook=lambda text: text.replace("Acme", "[REDACTED]"),
        )
        response = provider.judge(_claim(), [_evidence()])
        self.assertTrue(response.redacted)

    def test_openai_compatible_retries_transient_timeout(self):
        calls = 0

        def flaky_request(payload):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("temporary timeout")
            return _output()

        provider = OpenAICompatibleJudgeProvider(
            model="test-model",
            endpoint="https://example.invalid/v1",
            request_fn=flaky_request,
            max_retries=1,
        )
        response = provider.judge(_claim(), [_evidence()])
        self.assertEqual(response.attempts, 2)
        self.assertEqual(calls, 2)


def _claim():
    return {"claim_id": "claim_1", "text": "Acme is active."}


def _evidence():
    return {"evidence_id": "evidence_1", "content": "Acme is active."}


def _output():
    return {
        "verdict": "supported",
        "confidence": 0.9,
        "reason": "Matched.",
        "evidence_refs": ["evidence_1"],
        "unsupported_parts": [],
    }


if __name__ == "__main__":
    unittest.main()
