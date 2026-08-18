from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from latent_triz.validator import validate


class TrackBSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.protocol_schema = json.loads((self.root / "schemas/track-b-protocol.schema.json").read_text())
        self.manifest_schema = json.loads((self.root / "schemas/track-b-freeze-manifest.schema.json").read_text())
        self.protocol = json.loads((self.root / "experiments/track-b-emergence/protocol.json").read_text())
        self.manifest = json.loads((self.root / "experiments/track-b-emergence/freeze-manifest.json").read_text())

    def test_tracked_artifacts_validate_and_bind_protocol(self) -> None:
        self.assertEqual(validate(self.protocol, self.protocol_schema), [])
        self.assertEqual(validate(self.manifest, self.manifest_schema), [])
        protocol_bytes = (self.root / self.manifest["protocol"]["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(protocol_bytes).hexdigest(), self.manifest["protocol"]["sha256"])
        self.assertEqual(len(protocol_bytes), self.manifest["protocol"]["size"])
        self.assertEqual(self.protocol["status"], "planned")
        self.assertEqual(self.protocol["execution_readiness"], "no_model_ready")

    def test_protocol_fails_closed_for_access_freeze_controls_and_claims(self) -> None:
        mutations = []

        target_access = copy.deepcopy(self.protocol)
        target_access["scope_boundary"]["target_access_permitted"] = True
        mutations.append(target_access)

        mutable_split = copy.deepcopy(self.protocol)
        mutable_split["frozen_inputs"]["splits"]["post_freeze_modification_permitted"] = True
        mutations.append(mutable_split)

        incomplete_controls = copy.deepcopy(self.protocol)
        incomplete_controls["control_families"] = incomplete_controls["control_families"][:-1]
        mutations.append(incomplete_controls)

        claim_promotion = copy.deepcopy(self.protocol)
        claim_promotion["publication_boundary"]["claim_promotion_allowed"] = True
        mutations.append(claim_promotion)

        for mutation in mutations:
            self.assertTrue(validate(mutation, self.protocol_schema))

    def test_manifest_fails_closed_for_access_and_terminal_outcomes(self) -> None:
        access = copy.deepcopy(self.manifest)
        access["access_receipt"]["model_loaded"] = True
        self.assertTrue(validate(access, self.manifest_schema))

        terminal = copy.deepcopy(self.manifest)
        terminal["publication_boundary"]["terminal_outcomes"].append("inconclusive")
        self.assertTrue(validate(terminal, self.manifest_schema))


if __name__ == "__main__":
    unittest.main()
