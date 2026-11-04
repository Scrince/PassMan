from __future__ import annotations

import csv
import io
from pathlib import Path
from urllib.parse import urlsplit

from models.authenticator import AuthenticatorEntry
from models.entry import Entry
from utils.totp import parse_otpauth_uri

APPLE_PASSWORDS_SOURCE = "apple_passwords"


class ApplePasswordsImportError(ValueError):
    """Raised when an Apple Passwords CSV cannot be imported safely."""


def import_apple_passwords_csv(path: str | Path) -> list[Entry]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            text = stream.read()
    except (OSError, UnicodeError) as exc:
        raise ApplePasswordsImportError(f"Could not read the selected CSV: {exc}") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if not reader.fieldnames:
            raise ApplePasswordsImportError("The selected file is empty or has no CSV header.")
        columns = {_normalize(name): name for name in reader.fieldnames if name}
        title_col = _find(columns, "title", "name")
        username_col = _find(columns, "username", "user name", "login")
        password_col = _find(columns, "password")
        if not (title_col or username_col or password_col):
            raise ApplePasswordsImportError("This does not look like an Apple Passwords CSV export.")

        url_col = _find(columns, "url", "website", "website url")
        notes_col = _find(columns, "notes", "note")
        entries: list[Entry] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ApplePasswordsImportError(f"Incomplete or extra CSV fields on row {row_number}.")
            title = _value(row, title_col)
            username = _value(row, username_col)
            password = str(row.get(password_col) or "") if password_col else ""
            url = _value(row, url_col)
            notes = _value(row, notes_col)
            if url:
                try:
                    urlsplit(url if "://" in url else f"//{url}")
                except ValueError as exc:
                    raise ApplePasswordsImportError(f"Invalid URL on CSV row {row_number}.") from exc
            if not any((title, username, password, url, notes)):
                continue
            fields: dict[str, str] = {}
            if username:
                fields["username"] = username
            if password_col:
                fields["password"] = password
            if url:
                fields["url"] = url
            entries.append(Entry(title or username or url or "Imported Password", "Website", fields, notes))
        return entries
    except csv.Error as exc:
        raise ApplePasswordsImportError(f"The selected CSV is malformed: {exc}") from exc


def import_apple_authenticators_csv(path: str | Path) -> list[AuthenticatorEntry] | None:
    """Read OTPAuth data; None means this CSV has no OTPAuth column."""
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                return None
            columns = {_normalize(name): name for name in reader.fieldnames if name}
            otp_col = _find(columns, "otpauth", "otp auth", "otp uri")
            if not otp_col:
                return None
            entries: list[AuthenticatorEntry] = []
            seen: set[tuple[str, str, str]] = set()
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise ApplePasswordsImportError(f"Incomplete or extra CSV fields on row {row_number}.")
                uri = _value(row, otp_col)
                if not uri:
                    continue
                try:
                    parsed = parse_otpauth_uri(uri)
                except ValueError as exc:
                    raise ApplePasswordsImportError(
                        f"Invalid OTPAuth value on CSV row {row_number}; no changes were applied."
                    ) from exc
                entry = AuthenticatorEntry(
                    name=parsed.name,
                    issuer=parsed.issuer,
                    secret=parsed.secret,
                    type=parsed.type,
                    algorithm=parsed.algorithm,
                    digits=parsed.digits,
                    period=parsed.period,
                    counter=parsed.counter,
                    import_source=APPLE_PASSWORDS_SOURCE,
                )
                key = _authenticator_match_key(entry)
                if key not in seen:
                    entries.append(entry)
                    seen.add(key)
            return entries
    except (OSError, UnicodeError) as exc:
        raise ApplePasswordsImportError(f"Could not read the selected CSV: {exc}") from exc
    except csv.Error as exc:
        raise ApplePasswordsImportError(f"The selected CSV is malformed: {exc}") from exc


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _find(columns: dict[str, str], *names: str) -> str | None:
    return next((columns[_normalize(name)] for name in names if _normalize(name) in columns), None)


def _value(row: dict[str | None, str | None], column: str | None) -> str:
    return str(row.get(column) or "").strip() if column else ""


def merge_apple_password_entries(
    existing: list[Entry], imported: list[Entry]
) -> tuple[int, int, int, int]:
    """Reconcile Apple-managed entries, returning (added, updated, unchanged, deleted)."""
    added = updated = unchanged = deleted = 0
    incoming_keys: set[tuple[str, str, str]] = set()
    processed_keys: set[tuple[str, str, str]] = set()
    matched_ids: set[str] = set()
    incoming_host_users = [_host_user_key(entry) for entry in imported]
    for incoming in imported:
        incoming.import_source = APPLE_PASSWORDS_SOURCE
        key = _entry_match_key(incoming)
        if key:
            if key in processed_keys:
                unchanged += 1
                continue
            processed_keys.add(key)
            incoming_keys.add(key)
        if not key:
            existing.append(incoming)
            added += 1
            continue
        candidates = [
            entry for entry in existing
            if entry.import_source == APPLE_PASSWORDS_SOURCE
            and entry.id not in matched_ids
            and _entry_match_key(entry) == key
        ]
        if not candidates:
            host_user = _host_user_key(incoming)
            if host_user and incoming_host_users.count(host_user) == 1:
                candidates = [
                    entry for entry in existing
                    if entry.import_source == APPLE_PASSWORDS_SOURCE
                    and entry.id not in matched_ids
                    and _host_user_key(entry) == host_user
                ]
        if len(candidates) > 1:
            matched_ids.update(entry.id for entry in candidates)
            unchanged += 1
            continue
        if not candidates:
            existing.append(incoming)
            added += 1
            continue
        current = candidates[0]
        matched_ids.add(current.id)
        changed = current.name != incoming.name or current.notes != incoming.notes
        new_fields = dict(current.fields)
        for key, value in incoming.fields.items():
            if new_fields.get(key) != value:
                new_fields[key] = value
                changed = True
        if changed:
            current.name = incoming.name
            current.notes = incoming.notes
            current.fields = new_fields
            current.mark_modified()
            updated += 1
        else:
            unchanged += 1

    retained: list[Entry] = []
    for entry in existing:
        if (
            entry.import_source == APPLE_PASSWORDS_SOURCE
            and entry.id not in matched_ids
            and _entry_match_key(entry) is not None
            and _entry_match_key(entry) not in incoming_keys
        ):
            deleted += 1
        else:
            retained.append(entry)
    existing[:] = retained
    return added, updated, unchanged, deleted


def merge_apple_authenticator_entries(
    existing: list[AuthenticatorEntry], imported: list[AuthenticatorEntry]
) -> tuple[int, int, int, int]:
    """Reconcile Apple-managed OTP records, returning added/updated/unchanged/deleted."""
    added = updated = unchanged = deleted = 0
    incoming_keys: set[tuple[str, str, str]] = set()
    processed_keys: set[tuple[str, str, str]] = set()
    matched_ids: set[str] = set()
    for incoming in imported:
        key = _authenticator_match_key(incoming)
        if key in processed_keys:
            unchanged += 1
            continue
        processed_keys.add(key)
        incoming_keys.add(key)
        candidates = [
            entry for entry in existing
            if entry.import_source == APPLE_PASSWORDS_SOURCE
            and entry.id not in matched_ids
            and _authenticator_match_key(entry) == key
        ]
        if len(candidates) > 1:
            matched_ids.update(entry.id for entry in candidates)
            unchanged += 1
            continue
        if not candidates:
            existing.append(incoming)
            added += 1
            continue
        current = candidates[0]
        matched_ids.add(current.id)
        changed = any(
            getattr(current, attr) != getattr(incoming, attr)
            for attr in ("name", "issuer", "secret", "type", "algorithm", "digits", "period", "counter")
        )
        if changed:
            for attr in ("name", "issuer", "secret", "type", "algorithm", "digits", "period", "counter"):
                setattr(current, attr, getattr(incoming, attr))
            current.mark_modified()
            updated += 1
        else:
            unchanged += 1
    retained: list[AuthenticatorEntry] = []
    for entry in existing:
        if (
            entry.import_source == APPLE_PASSWORDS_SOURCE
            and _authenticator_match_key(entry) not in incoming_keys
        ):
            deleted += 1
        else:
            retained.append(entry)
    existing[:] = retained
    return added, updated, unchanged, deleted


def _entry_match_key(entry: Entry) -> tuple[str, str, str] | None:
    fields = {_normalize(str(key)): str(value).strip() for key, value in entry.fields.items()}
    username = next((fields[name] for name in ("username", "user name", "login") if fields.get(name)), "")
    url = next((fields[name] for name in ("url", "website", "website url") if fields.get(name)), "")
    site = _normalize_site(url)
    if username and site:
        return "site-user", site, username.casefold()
    if username and entry.name.strip():
        return ("site-user-title", site, username.casefold()) if site else ("title-user", _normalize(entry.name), username.casefold())
    if site and entry.name.strip():
        return "site-title", site, _normalize(entry.name)
    if entry.name.strip():
        return "title", _normalize(entry.name), ""
    return None


def _authenticator_match_key(entry: AuthenticatorEntry) -> tuple[str, str, str]:
    issuer = _normalize(entry.issuer)
    name = _normalize(entry.name)
    return ("issuer-name", issuer, name) if issuer else ("name", name, "")


def _host_user_key(entry: Entry) -> tuple[str, str] | None:
    fields = {_normalize(str(key)): str(value).strip() for key, value in entry.fields.items()}
    username = next((fields[name] for name in ("username", "user name", "login") if fields.get(name)), "")
    url = next((fields[name] for name in ("url", "website", "website url") if fields.get(name)), "")
    site = _normalize_site(url)
    host = site.split("/", 1)[0]
    return (host, username.casefold()) if host and username else None


def _normalize_site(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw if "://" in raw else f"//{raw}")
    except ValueError:
        return ""
    host = (parsed.hostname or "").removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}"
