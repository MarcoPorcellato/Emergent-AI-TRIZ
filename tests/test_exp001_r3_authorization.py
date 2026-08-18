import json
import shutil
from pathlib import Path

import pytest

from latent_triz.exp001_r3_authorization import Exp001AuthorizationError, build_approval_requested, verify_approval_requested


def _repo(tmp_path: Path) -> Path:
    source = Path(__file__).parents[1]
    for rel in ("schemas/exp001-r3-execution-authorization.schema.json", "experiments/exp001-reference-integrated/protocol.json", "results/a0r2/preexecution/smollm2-360m-f8027fd0/integrity-receipt.json", "results/a0r2/preexecution/smollm2-360m-f8027fd0/feasibility-receipt.json"):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dst)
    impl = tmp_path / "experiments/exp001-reference-integrated/implementation.json"
    impl.write_text("{}", encoding="utf-8")
    protocol = tmp_path / "experiments/exp001-reference-integrated/protocol.json"
    payload = json.loads(protocol.read_text(encoding="utf-8")); payload["protocol_status"] = "frozen"
    protocol.write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


def test_builder_and_verifier_are_model_free(tmp_path: Path):
    root = _repo(tmp_path)
    dossier = build_approval_requested(root, created_at="2026-08-18T00:00:00Z")
    assert verify_approval_requested(root, dossier)["status"] == "pass"
    assert dossier["operator_approval_granted"] is False
    assert dossier["inventory"]["combined_records"] == 85


def test_protocol_mutation_is_rejected(tmp_path: Path):
    root = _repo(tmp_path); dossier = build_approval_requested(root)
    protocol = root / dossier["protocol"]["path"]
    protocol.write_text(protocol.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(Exp001AuthorizationError, match="hash or size"):
        verify_approval_requested(root, dossier)


def test_unfrozen_protocol_cannot_build(tmp_path: Path):
    root = _repo(tmp_path)
    protocol = root / "experiments/exp001-reference-integrated/protocol.json"
    payload = json.loads(protocol.read_text(encoding="utf-8")); payload["protocol_status"] = "approval_requested"
    protocol.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Exp001AuthorizationError, match="frozen"):
        build_approval_requested(root)
