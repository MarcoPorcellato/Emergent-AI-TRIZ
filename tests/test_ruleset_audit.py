import copy
import unittest

from scripts.ruleset_audit import RulesetAuditError, audit_ruleset


EXPECTED = {
    "name": "main-protection",
    "enforcement": "active",
    "target": "branch",
    "include_refs": ["refs/heads/main"],
    "required_status_checks": ["merge-policy/gate"],
    "strict_required_status_checks_policy": True,
    "required_review_thread_resolution": True,
    "allowed_merge_methods": ["squash"],
    "required_linear_history": True,
    "block_deletion": True,
    "block_non_fast_forward": True,
}
LIVE = {
    "name": "main-protection",
    "enforcement": "active",
    "target": "branch",
    "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "required_linear_history"},
        {
            "type": "pull_request",
            "parameters": {
                "required_review_thread_resolution": True,
                "allowed_merge_methods": ["squash"],
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "merge-policy/gate"}],
            },
        },
    ],
}


class RulesetAuditTests(unittest.TestCase):
    def test_matching_ruleset_passes(self) -> None:
        audit_ruleset(EXPECTED, LIVE)

    def test_required_check_drift_fails(self) -> None:
        live = copy.deepcopy(LIVE)
        live["rules"][-1]["parameters"]["required_status_checks"][0]["context"] = "Repository check"
        with self.assertRaisesRegex(RulesetAuditError, "required status checks"):
            audit_ruleset(EXPECTED, live)

    def test_missing_linear_history_fails(self) -> None:
        live = copy.deepcopy(LIVE)
        live["rules"] = [
            rule for rule in live["rules"] if rule["type"] != "required_linear_history"
        ]
        with self.assertRaisesRegex(RulesetAuditError, "required_linear_history"):
            audit_ruleset(EXPECTED, live)


if __name__ == "__main__":
    unittest.main()
