import copy
import json
from pathlib import Path
import tempfile
import unittest

from latent_triz.exp001_additional_acquisition import (
    MODEL_SPECS,
    AdditionalAcquisitionError,
    acquire_additional,
    build_receipt_from_authorized,
    validate_authorization,
)


ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / "experiments/exp001-comparative-reference/additional-model-authorization.json"


class _Response:
    status = 200
    url = "https://huggingface.co/test"

    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if not self.payload:
            return b""
        value, self.payload = self.payload[:size], self.payload[size:]
        return value

    def close(self) -> None:
        self.closed = True


class AdditionalAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authorization = json.loads(AUTH_PATH.read_text(encoding="utf-8"))

    def test_exact_authorization_binds_both_candidates(self):
        for model_id, spec in MODEL_SPECS.items():
            validated = validate_authorization(self.authorization, model_id)
            self.assertEqual(validated.revision, spec.revision)
            self.assertEqual(validated.total_declared_bytes, sum(size for _name, size in spec.files))

    def test_approval_requested_and_missing_flag_fail_before_downloader(self):
        refused = copy.deepcopy(self.authorization)
        refused["status"] = "approval_requested"
        for model_id in MODEL_SPECS:
            with self.assertRaises(AdditionalAcquisitionError):
                acquire_additional(model_id, ROOT / MODEL_SPECS[model_id].root_locator, authorization=refused, allow_download=True)
            with self.assertRaises(AdditionalAcquisitionError):
                acquire_additional(model_id, ROOT / MODEL_SPECS[model_id].root_locator, authorization=self.authorization, allow_download=False)

    def test_identity_budget_and_permissions_mutations_fail_closed(self):
        for field, value in (("revision", "0" * 40), ("disk_budget_bytes", 1), ("permissions", {})):
            mutated = copy.deepcopy(self.authorization)
            mutated["candidates"][0][field] = value
            with self.assertRaises(AdditionalAcquisitionError):
                validate_authorization(mutated, "openai-community/gpt2")

    def test_streaming_fake_download_and_receipt(self):
        model_id = "openai-community/gpt2"
        original = MODEL_SPECS[model_id]
        tiny = type(original)(
            model_id=original.model_id,
            revision=original.revision,
            license_id=original.license_id,
            root_locator="artifacts/models/_additional-acquisition-test",
            disk_budget_bytes=64,
            files=(("config.json", 3), ("vocab.json", 2)),
        )
        MODEL_SPECS[model_id] = tiny
        try:
            authorization = copy.deepcopy(self.authorization)
            authorization["candidates"][0]["runtime_root"] = tiny.root_locator
            authorization["candidates"][0]["disk_budget_bytes"] = tiny.disk_budget_bytes
            authorization["candidates"][0]["runtime_files"] = [{"path": n, "size_bytes": s} for n, s in tiny.files]
            with tempfile.TemporaryDirectory(prefix="latent-triz-additional-acquisition-") as workspace:
                workspace_root = Path(workspace)
                root = workspace_root / tiny.root_locator
                responses = iter((_Response(b"abc"), _Response(b"de")))

                def open_response(request, timeout):
                    response = next(responses)
                    response.url = request.full_url
                    return response

                acquire_additional(
                    model_id,
                    root,
                    authorization=authorization,
                    allow_download=True,
                    opener=open_response,
                    repository_root=workspace_root,
                )
                receipt = build_receipt_from_authorized(
                    model_id,
                    root,
                    authorization=authorization,
                    authorization_sha256="a" * 64,
                    repository_root=workspace_root,
                )
                self.assertEqual(receipt["total_bytes"], 5)
                self.assertFalse(receipt["model_loaded"])
        finally:
            MODEL_SPECS[model_id] = original


if __name__ == "__main__":
    unittest.main()
