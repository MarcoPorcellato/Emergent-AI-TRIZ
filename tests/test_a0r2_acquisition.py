from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz import a0r2_acquisition as acquisition


def _blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("utf-8") + data).hexdigest()


class _Response:
    def __init__(self, payload: bytes, status_code: int = 200) -> None:
        self._payload = payload
        self._cursor = 0
        self.status_code = status_code
        self.closed = False

    def iter_content(self, chunk_size: int = 1 << 20):
        while self._cursor < len(self._payload):
            start = self._cursor
            end = start + chunk_size
            self._cursor = end
            yield self._payload[start:end]

    def read(self, size: int = 1 << 20) -> bytes:
        if self._cursor >= len(self._payload):
            return b""
        start = self._cursor
        end = min(self._cursor + size, len(self._payload))
        self._cursor = end
        return self._payload[start:end]

    def close(self) -> None:
        self.closed = True


class A0R2AcquisitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.required = acquisition.A0R2_REQUIRED_FILES
        self.contract = json.loads(
            (ROOT / "experiments/a0r2-independent-model/acquisition-contract.json").read_text(encoding="utf-8")
        )
        self.base = {
            "README.md": b"r",
            "config.json": b"c",
            "generation_config.json": b"g",
            "merges.txt": b"m",
            "model.safetensors": b"AB",
            "special_tokens_map.json": b"s",
            "tokenizer.json": b"t",
            "tokenizer_config.json": b"u",
            "vocab.json": b"v",
        }
        self.payloads = {name: self.base[name] for name in self.required}
        self.expected = {
            name: (
                len(self.base[name]),
                hashlib.sha256(self.base[name]).hexdigest()
                if name == "model.safetensors"
                else _blob_sha1(self.base[name]),
            )
            for name in self.required
        }

    def _build_open_url(self, order: list[str], payloads: dict[str, bytes] | None = None):
        source = payloads if payloads is not None else self.payloads

        def _open(url: str, headers: dict[str, str]):
            self.assertEqual(headers.get("Accept-Encoding"), "identity")
            name = Path(url).name
            order.append(name)
            return _Response(source[name])

        return _open

    def test_success_and_verified_skip(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=self.expected):
                order: list[str] = []
                acquisition.acquire_a0r2_runtime(
                    model_dir,
                    allow_download=True,
                    open_url=self._build_open_url(order),
                )
                self.assertEqual(order, list(self.required))

                order.clear()
                acquisition.acquire_a0r2_runtime(
                    model_dir,
                    allow_download=False,
                    open_url=self._build_open_url(order),
                )
                self.assertEqual(order, [])

                receipt = acquisition.build_integrity_receipt(
                    model_dir=model_dir,
                    contract_sha256="a" * 64,
                    local_locator="artifacts/models/smollm2-360m-f8027fd0",
                    receipt_time="2026-08-15T00:00:00Z",
                )
                self.assertEqual(receipt["status"], "pass")
                self.assertEqual(receipt["integrity_status"], "integrity_verified")
                self.assertFalse(receipt["access"]["model_loaded"])
                self.assertFalse(receipt["access"]["model_output_accessed"])
                self.assertFalse(receipt["access"]["sealed_targets_accessed"])
                self.assertFalse(receipt["access"]["feasibility_tested"])

    def test_contract_matches_code_constants(self) -> None:
        runtime_files = self.contract["runtime_files"]
        self.assertEqual(acquisition.A0R2_MODEL_ID, self.contract["model"]["id"])
        self.assertEqual(acquisition.A0R2_MODEL_REVISION, self.contract["model"]["revision"])
        self.assertEqual(acquisition.A0R2_LICENSE_ID, self.contract["model"]["license_id"])
        self.assertEqual(acquisition.A0R2_REQUIRED_FILES, tuple(item["name"] for item in runtime_files))
        self.assertEqual(
            acquisition.A0R2_EXPECTED_SIZE_AND_OID,
            {item["name"]: (item["size"], item["source_oid"]) for item in runtime_files},
        )
        self.assertEqual(acquisition.A0R2_MAX_RUNTIME_BYTES, self.contract["authorization"]["maximum_download_bytes"])
        self.assertEqual(acquisition.A0R2_EXPECTED_TOTAL_BYTES, self.contract["expected_total_bytes"])

    def test_default_opener_is_stdlib_and_closes(self) -> None:
        responses: list[_Response] = []

        def _fake_urlopen(request: object, timeout: int) -> _Response:
            headers = {key.lower(): value for key, value in getattr(request, "headers", {}).items()}
            self.assertEqual(headers.get("accept-encoding"), "identity")
            self.assertEqual(timeout, acquisition.A0R2_NETWORK_TIMEOUT_SECONDS)
            response = _Response(b"x")
            responses.append(response)
            return response

        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            tiny = {
                name: (1, hashlib.sha256(b"x").hexdigest() if name == "model.safetensors" else _blob_sha1(b"x"))
                for name in self.required
            }
            with patch.object(acquisition, "urlopen", _fake_urlopen), patch.object(
                acquisition,
                "A0R2_EXPECTED_SIZE_AND_OID",
                new=tiny,
            ), patch.object(acquisition, "A0R2_REQUIRED_FILES", new=self.required):
                acquisition.acquire_a0r2_runtime(
                    model_dir,
                    allow_download=True,
                )

                self.assertEqual(len(responses), len(self.required))
                self.assertTrue(all(response.closed for response in responses))

    def test_budget_guard(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=self.expected):
                with self.assertRaisesRegex(
                    acquisition.A0R2AcquisitionError,
                    "download exceeds allowed budget",
                ):
                    acquisition.acquire_a0r2_runtime(
                        model_dir,
                        allow_download=True,
                        open_url=self._build_open_url([]),
                        max_runtime_bytes=1,
                    )

    def test_hash_and_blob_verification(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            broken = dict(self.payloads)
            broken["README.md"] = b"x"
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=self.expected):
                with self.assertRaisesRegex(
                    acquisition.A0R2AcquisitionError,
                    "integrity mismatch",
                ):
                    acquisition.acquire_a0r2_runtime(
                        model_dir,
                        allow_download=True,
                        open_url=self._build_open_url([], payloads=broken),
                    )
                self.assertFalse((model_dir / ".README.md.tmp").exists())

    def test_path_and_allowlist_validation(self) -> None:
        with self.assertRaises(acquisition.A0R2AcquisitionError):
            acquisition._validate_allowlist(("README.md", "config.json"))

    def test_cleanup_on_failure(self) -> None:
        bad = dict(self.payloads)
        bad["model.safetensors"] = b"A" * 2
        expected = dict(self.expected)

        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=expected):
                with self.assertRaises(acquisition.A0R2AcquisitionError):
                    acquisition.acquire_a0r2_runtime(
                        model_dir,
                        allow_download=True,
                        open_url=self._build_open_url([], payloads=bad),
                    )
                self.assertFalse(any((model_dir / f".{name}.tmp").exists() for name in self.required))

    def test_download_order_stable(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=self.expected):
                order: list[str] = []
                acquisition.acquire_a0r2_runtime(
                    model_dir,
                    allow_download=True,
                    open_url=self._build_open_url(order),
                    max_runtime_bytes=64,
                )
                self.assertEqual(order, list(self.required))

    def test_reject_unexpected_snapshot_files(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            model_dir.mkdir(parents=True, exist_ok=True)
            for name in self.required:
                (model_dir / name).write_bytes(self.base[name])
            (model_dir / "unexpected.txt").write_text("bad", encoding="utf-8")

            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=self.expected):
                with self.assertRaises(acquisition.A0R2AcquisitionError):
                    acquisition.acquire_a0r2_runtime(
                        model_dir,
                        allow_download=False,
                    )

    def test_read_bytes_is_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as workdir:
            model_dir = Path(workdir) / "smollm2"
            model_dir.mkdir(parents=True)
            tiny = {
                name: (1, hashlib.sha256(b"x").hexdigest() if name == "model.safetensors" else _blob_sha1(b"x"))
                for name in self.required
            }
            for name in self.required:
                (model_dir / name).write_bytes(b"x")
            with patch.object(acquisition, "A0R2_EXPECTED_SIZE_AND_OID", new=tiny), patch.object(
                acquisition, "A0R2_REQUIRED_FILES", new=self.required
            ), patch.object(Path, "read_bytes", side_effect=OSError("blocked")):
                    receipt = acquisition.build_runtime_file_receipts(model_dir)
                    self.assertEqual(len(receipt), len(self.required))
                    self.assertTrue(acquisition.verify_runtime_file(model_dir / "README.md", "README.md")[0])


if __name__ == "__main__":
    unittest.main()
