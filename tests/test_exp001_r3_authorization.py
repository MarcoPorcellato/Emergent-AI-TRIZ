import json
import shutil
import unittest
from pathlib import Path

from latent_triz.exp001_r3_authorization import Exp001AuthorizationError, build_approval_requested, verify_approval_requested, write_approval_requested


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


class Exp001AuthorizationTests(unittest.TestCase):
    def test_builder_and_verifier_are_model_free(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = _repo(Path(directory))
            dossier = build_approval_requested(root, created_at="2026-08-18T00:00:00Z")
            self.assertEqual(verify_approval_requested(root, dossier)["status"], "pass")
            self.assertFalse(dossier["operator_approval_granted"])
            self.assertEqual(dossier["inventory"]["combined_records"], 85)


    def test_protocol_mutation_is_rejected(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = _repo(Path(directory)); dossier = build_approval_requested(root)
            protocol = root / dossier["protocol"]["path"]
            protocol.write_text(protocol.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(Exp001AuthorizationError, "hash or size"):
                verify_approval_requested(root, dossier)


    def test_unfrozen_protocol_cannot_build(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = _repo(Path(directory))
            protocol = root / "experiments/exp001-reference-integrated/protocol.json"
            payload = json.loads(protocol.read_text(encoding="utf-8")); payload["protocol_status"] = "approval_requested"
            protocol.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exp001AuthorizationError, "frozen"):
                build_approval_requested(root)

    def test_writer_refuses_overwrite(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root = _repo(Path(directory))
            dossier = write_approval_requested(root, created_at="2026-08-18T00:00:00Z")
            self.assertEqual(dossier["dossier_status"], "approval_requested")
            with self.assertRaisesRegex(Exp001AuthorizationError, "overwrite"):
                write_approval_requested(root, created_at="2026-08-18T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
