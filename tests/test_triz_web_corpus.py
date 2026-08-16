import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_URLS = {
    "https://www.triz-consulting.de/the-triz-method/?lang=en",
    "https://www.triz-consulting.de/about-triz/triz-matrix/?lang=en",
    "https://www.triz-consulting.de/2023/11/06/40-innovation-principles-in-132-illustrated-examples-for-free-download/?lang=en",
    "https://www.triz-consulting.de/tools-level-1/?lang=en",
    "https://www.triz-consulting.de/tools-level-2/?lang=en",
    "https://www.triz-consulting.de/tools-level-3/?lang=en",
    "https://www.triz-consulting.de/tools-ai-triz/?lang=en",
    "https://www.triz-consulting.de/about-triz/triz-software/?lang=en",
    "https://www.triz-consulting.de/about-triz/triz-use-cases/?lang=en",
    "https://www.triz-consulting.de/FunctionModel/index.html",
    "https://www.triz-consulting.de/heatmap-web/triz_matrix_analyzer.html",
    "https://www.triz-consulting.de/about-triz/artificial-intelligence-and-triz-a-synergy-for-innovation/?lang=en",
    "https://www.triz-consulting.de/wp-content/uploads/2024/04/TRIZ_and_Generative_AI-V3.0.pdf",
    "https://www.triz-consulting.de/triz-app/?lang=en",
    "https://www.triz-consulting.de/wp-content/uploads/2022/12/ARIZ-85C_eng_v9.pdf",
    "https://www.triz-consulting.de/FunctionModel/help.html",
    "https://www.triz-consulting.de/wp-content/uploads/2025/05/LearningPosters_v01.pdf",
    "https://www.triz-consulting.de/2023/10/19/free-book-gen-triz-knowledge-transfer-basic-module-manual-july-2019/?lang=en",
}


class TrizWebCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((ROOT / "schemas/triz-web-corpus.schema.json").read_text())
        cls.corpus = json.loads((ROOT / "data/triz-consulting-web-corpus.json").read_text())

    def test_schema_and_exact_urls(self):
        self.assertEqual(list(Draft202012Validator(self.schema).iter_errors(self.corpus)), [])
        resources = self.corpus["resources"]
        self.assertEqual(len(resources), 18)
        self.assertEqual({r["url"] for r in resources}, EXPECTED_URLS)
        self.assertEqual(len({r["id"] for r in resources}), 18)

    def test_same_domain_and_no_local_paths(self):
        serialized = json.dumps(self.corpus)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("file://", serialized)
        for resource in self.corpus["resources"]:
            parsed = urlparse(resource["url"])
            self.assertEqual(parsed.scheme, "https")
            self.assertEqual(parsed.netloc, "www.triz-consulting.de")

    def test_boundary_flags_and_coverage(self):
        for resource in self.corpus["resources"]:
            self.assertEqual(resource["authority_status"], "provider_curated_public")
            self.assertTrue(resource["citation_allowed"])
            self.assertFalse(resource["repository_copy_tracked"])
            self.assertFalse(resource["automatic_ground_truth"])
            self.assertFalse(resource["r2_frozen_protocol_eligible"])
            self.assertEqual(resource["future_tranche"], "R3/EXP-001")
            self.assertTrue(resource["coverage_topics"])

        topics = {topic for resource in self.corpus["resources"] for topic in resource["coverage_topics"]}
        self.assertTrue({"physical_contradictions", "ARIZ", "functional_analysis", "CECA_trimming", "AI_prompt_design", "practical_examples"} <= topics)


if __name__ == "__main__":
    unittest.main()
