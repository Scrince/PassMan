from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models.entry import Entry
from models.authenticator import AuthenticatorEntry
from utils.apple_passwords_import import (
    ApplePasswordsImportError,
    import_apple_authenticators_csv,
    import_apple_passwords_csv,
    merge_apple_authenticator_entries,
    merge_apple_password_entries,
)


class ApplePasswordsImportTests(unittest.TestCase):
    def test_imports_apple_csv_fields_and_skips_empty_rows(self) -> None:
        content = (
            "Title,URL,Username,Password,Notes,OTPAuth\n"
            '"Example, Inc.",https://example.com,alice,secret,"work account",otpauth://ignored\n'
            ",,,,,\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "apple.csv"
            path.write_text(content, encoding="utf-8")
            entries = import_apple_passwords_csv(path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "Example, Inc.")
        self.assertEqual(entries[0].type, "Website")
        self.assertEqual(entries[0].fields, {
            "username": "alice", "password": "secret", "url": "https://example.com"
        })
        self.assertEqual(entries[0].notes, "work account")

    def test_rejects_unrecognized_or_empty_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "other.csv"
            path.write_text("foo,bar\na,b\n", encoding="utf-8")
            with self.assertRaises(ApplePasswordsImportError):
                import_apple_passwords_csv(path)
            path.write_text("Title,URL,Username,Password\n,,,\n", encoding="utf-8")
            self.assertEqual(import_apple_passwords_csv(path), [])

    def test_merges_by_site_and_username_updates_changed_password_and_skips_repeat(self) -> None:
        existing = [Entry("Example", "Website", {
            "username": "alice", "password": "old", "url": "https://www.example.com/"
        }, "old note", import_source="apple_passwords")]
        incoming = [Entry("Example Login", "Website", {
            "username": "alice", "password": "new", "url": "http://example.com"
        }, "updated note")]

        self.assertEqual(merge_apple_password_entries(existing, incoming), (0, 1, 0, 0))
        self.assertEqual(len(existing), 1)
        self.assertEqual(existing[0].fields["password"], "new")
        self.assertEqual(existing[0].notes, "updated note")
        self.assertEqual(merge_apple_password_entries(existing, incoming), (0, 0, 1, 0))

    def test_keeps_different_accounts_on_same_site_separate(self) -> None:
        existing = [Entry("Example", "Website", {
            "username": "alice", "password": "secret", "url": "https://example.com"
        })]
        incoming = [Entry("Example", "Website", {
            "username": "bob", "password": "secret", "url": "https://example.com"
        })]
        self.assertEqual(merge_apple_password_entries(existing, incoming), (1, 0, 0, 0))
        self.assertEqual(len(existing), 2)

    def test_deletes_only_stale_apple_imports_and_preserves_manual_entries(self) -> None:
        managed = Entry("Old Apple Login", "Website", {
            "username": "old", "password": "old-secret", "url": "https://old.example"
        }, import_source="apple_passwords")
        manual = Entry("Manual Login", "Website", {
            "username": "manual", "password": "keep", "url": "https://manual.example"
        })
        refreshed = Entry("Current Apple Login", "Website", {
            "username": "current", "password": "current-secret", "url": "https://current.example"
        })
        existing = [managed, manual]

        self.assertEqual(merge_apple_password_entries(existing, [refreshed]), (1, 0, 0, 1))
        self.assertEqual([entry.id for entry in existing], [manual.id, refreshed.id])
        self.assertEqual(manual.fields["password"], "keep")
        self.assertEqual(refreshed.import_source, "apple_passwords")

    def test_imports_otp_auth_data_and_updates_only_apple_managed_authenticators(self) -> None:
        content = (
            "Title,URL,Username,Password,Notes,OTPAuth\n"
            'Example,https://example.com,alice,password,,"otpauth://totp/Example%3Aalice?secret=JBSWY3DPEHPK3PXP&issuer=Example&digits=8&period=60"\n'
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "apple.csv"
            path.write_text(content, encoding="utf-8")
            imported = import_apple_authenticators_csv(path)

        self.assertIsNotNone(imported)
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].issuer, "Example")
        self.assertEqual(imported[0].name, "alice")
        self.assertEqual(imported[0].digits, 8)
        self.assertEqual(imported[0].period, 60)

        managed = AuthenticatorEntry(
            "alice", "JBSWY3DPEHPK3PXP", issuer="Example", import_source="apple_passwords"
        )
        manual = AuthenticatorEntry("Manual", "JBSWY3DPEHPK3PXP", issuer="Other")
        current = [managed, manual]
        self.assertEqual(merge_apple_authenticator_entries(current, imported), (0, 1, 0, 0))
        self.assertEqual(current[0].id, managed.id)
        self.assertEqual(current[1].id, manual.id)
        self.assertEqual(merge_apple_authenticator_entries(current, []), (0, 0, 0, 1))
        self.assertEqual([item.id for item in current], [manual.id])

    def test_invalid_otp_auth_data_aborts_instead_of_treating_it_as_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "apple.csv"
            path.write_text("Title,URL,Username,Password,Notes,OTPAuth\nExample,,,,,not-an-otp-uri\n")
            with self.assertRaisesRegex(ApplePasswordsImportError, "row 2"):
                import_apple_authenticators_csv(path)

    def test_password_whitespace_is_preserved_and_blank_password_clears_old_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "apple.csv"
            path.write_text("Title,URL,Username,Password\nSite,https://example.com,alice,  secret  \n")
            imported = import_apple_passwords_csv(path)
            self.assertEqual(imported[0].fields["password"], "  secret  ")
            existing = [imported[0]]
            existing[0].import_source = "apple_passwords"
            path.write_text("Title,URL,Username,Password\nSite,https://example.com,alice,\n")
            self.assertEqual(merge_apple_password_entries(existing, import_apple_passwords_csv(path)), (0, 1, 0, 0))
            self.assertEqual(existing[0].fields["password"], "")

    def test_unique_url_path_change_keeps_entry_id_and_custom_fields(self) -> None:
        original = Entry("Site", "Website", {
            "username": "alice", "password": "old", "url": "https://example.com/old", "custom": "keep"
        }, import_source="apple_passwords")
        incoming = Entry("Site", "Website", {
            "username": "alice", "password": "new", "url": "https://example.com/new"
        })
        existing = [original]
        self.assertEqual(merge_apple_password_entries(existing, [incoming]), (0, 1, 0, 0))
        self.assertEqual(existing[0].id, original.id)
        self.assertEqual(existing[0].fields["custom"], "keep")
        self.assertEqual(existing[0].fields["url"], "https://example.com/new")

    def test_invalid_url_and_incomplete_csv_row_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "apple.csv"
            path.write_text("Title,URL,Username,Password\nSite,https://[bad,alice,secret\n")
            with self.assertRaisesRegex(ApplePasswordsImportError, "row 2"):
                import_apple_passwords_csv(path)
            path.write_text("Title,URL,Username,Password\nSite,https://example.com,alice\n")
            with self.assertRaisesRegex(ApplePasswordsImportError, "row 2"):
                import_apple_passwords_csv(path)
if __name__ == "__main__":
    unittest.main()
