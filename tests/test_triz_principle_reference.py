"""Structural and mutation tests for the non-evidentiary TRIZ reference set."""

import json
from pathlib import Path

import unittest
from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).parents[1]
DATA = ROOT / "data/triz-reference/principles.jsonl"
SCHEMA = ROOT / "schemas/triz-principle-reference.schema.json"


def records():
    return [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]


class TrizPrincipleReferenceTests(unittest.TestCase):
    def test_exact_ordered_forty_records(self):
        rows = records()
        self.assertEqual(len(rows), 40)
        self.assertEqual([row["principle_number"] for row in rows], list(range(1, 41)))
        self.assertEqual([row["source_page"] for row in rows], list(range(1, 41)))
        self.assertEqual(
            [row["canonical_name"] for row in rows],
            [
                "Segmentation", "Taking Away", "Local Conditions", "Asymmetry", "Merging",
                "Multi-functionality", "Nesting", "Weight Compensation", "Prior Counteraction",
                "Prior Action", "Beforehand Compensation", "Equipotentiality", "The Other Way Round",
                "Curvature Increase", "Dynamics, Adjustability", "Partial, Overdone or Excessive Action",
                "Transition into New Dimension", "Vibration", "Periodic Action", "Continuity of Useful Action",
                "Rushing Through", "Convert Harm into Benefit", "Feedback", "Mediator", "Self Service",
                "Copying", "Cheap Short-living Objects", "Replace Mechanical System with Fields", "Fluid System",
                "Flexible Film or Thin Membranes", "Porous Materials", "Optical Property Changes", "Homogeneity",
                "Rejection and Regeneration", "Changing Properties", "Phase Transition", "Thermal Expansion",
                "Use Strong Oxidizers", "Inert Environment", "Composite Materials",
            ],
        )

    def test_fixed_reference_controls(self):
        for row in records():
            self.assertEqual(row["source_id"], "triz-ref-inventive-principles-2023")
            self.assertEqual(row["exposure_class"], "source_derived_reference")
            self.assertEqual(row["scientific_role"], "authoring_reference_only")
            self.assertIs(row["automatic_ground_truth"], False)
            self.assertIs(row["r2_frozen_protocol_eligible"], False)
            self.assertEqual(row["future_tranche"], "R3/EXP-001")

    def test_schema_rejects_missing_or_extra_fields(self):
        schema = json.loads(SCHEMA.read_text())
        row = records()[0]
        Draft202012Validator(schema).validate(row)
        missing = dict(row)
        del missing["example_summary"]
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(missing)
        extra = dict(row, unapproved_note="not part of the contract")
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(extra)

    def test_schema_rejects_protocol_eligibility_mutation(self):
        validator = Draft202012Validator(json.loads(SCHEMA.read_text()))
        mutated = dict(records()[0], r2_frozen_protocol_eligible=True)
        with self.assertRaises(ValidationError):
            validator.validate(mutated)
