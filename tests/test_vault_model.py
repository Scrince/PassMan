from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models.vault_model import VaultModel  # noqa: E402


class VaultModelLoadingTests(unittest.TestCase):
    def test_rejects_non_object_records_in_all_collections(self) -> None:
        collections = (
            "entries",
            "key_projects",
            "authenticator_entries",
            "recovery_entries",
            "seed_entries",
        )
        for collection in collections:
            with self.subTest(collection=collection):
                with self.assertRaisesRegex(ValueError, rf"{collection}.*index 1"):
                    VaultModel.from_json_dict({collection: [{}, "invalid"]})

    def test_rejects_non_list_record_collections(self) -> None:
        with self.assertRaisesRegex(ValueError, "authenticator_entries.*list"):
            VaultModel.from_json_dict({"authenticator_entries": {"name": "unexpected"}})

    def test_rejects_non_list_or_malformed_project_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "project field 'keys'.*list"):
            VaultModel.from_json_dict({"key_projects": [{"keys": {"role": "S"}}]})

        with self.assertRaisesRegex(ValueError, "project field 'keys'.*index 1"):
            VaultModel.from_json_dict({"key_projects": [{"keys": [{}, None]}]})

    def test_older_payloads_without_new_collections_remain_supported(self) -> None:
        model = VaultModel.from_json_dict({"entries": [], "settings": {}})
        self.assertEqual(model.key_projects, [])
        self.assertEqual(model.authenticator_entries, [])
        self.assertEqual(model.recovery_entries, [])
        self.assertEqual(model.seed_entries, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
