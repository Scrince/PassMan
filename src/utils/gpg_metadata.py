from __future__ import annotations

import base64
import hashlib
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# OpenPGP OIDs used by GnuPG for modern curves.
_ED25519_OID = bytes.fromhex("2B06010401DA470F01")  # 1.3.6.1.4.1.11591.15.1
_CV25519_OID = bytes.fromhex("2B060104019755010501")  # 1.3.6.1.4.1.3029.1.5.1
# Default KDF params used by GnuPG for Curve25519 ECDH public material.
_ECDH_KDF_PARAMS = bytes([0x03, 0x01, 0x08, 0x07])


@dataclass(slots=True)
class KeyIdentity:
    fingerprint: str = ""
    key_id: str = ""
    role: str = ""  # C/S/E/A when known
    label: str = ""
    source: str = ""  # openpgp | gnupg-native | gpg


def extract_key_identities(raw: bytes, filename: str = "") -> list[KeyIdentity]:
    """Extract fingerprint/key-id identities from a .key blob."""
    if not raw:
        return []

    # Prefer native/OpenPGP parsers first so frozen builds work without gpg on PATH.
    identities = _extract_via_gnupg_native(raw, filename)
    if identities:
        return identities

    identities = _extract_via_openpgp_parse(raw)
    if identities:
        return identities

    identities = _extract_via_gpg(raw)
    if identities:
        return identities

    # Keygrip filename alone can sometimes be resolved against the local keyring.
    grip = _keygrip_from_filename(filename)
    if grip:
        resolved = _resolve_keygrip_via_gpg(grip)
        if resolved:
            return [resolved]
    return []


def pick_identity_for_role(identities: list[KeyIdentity], preferred_role: str = "") -> KeyIdentity | None:
    if not identities:
        return None
    role = (preferred_role or "").strip().upper()
    if role:
        for item in identities:
            if item.role == role:
                return item
    for item in identities:
        if item.role and len(item.role) == 1:
            return item
    return identities[0]


def apply_identity_to_fields(
    raw: bytes,
    preferred_role: str = "",
    filename: str = "",
) -> KeyIdentity | None:
    identities = extract_key_identities(raw, filename=filename)
    return pick_identity_for_role(identities, preferred_role)


def describe_extraction_failure(raw: bytes, filename: str = "") -> str:
    if not raw:
        return "The key file is empty."
    text = raw.decode("utf-8", errors="ignore")
    if text.lstrip().startswith("Created:") and "(protected-private-key" in text:
        return (
            "This looks like a passphrase-protected GnuPG private key file. "
            "PassMan can store it, but cannot read the fingerprint until it is "
            "exported as an OpenPGP key (gpg --export-secret-keys) or the public half is available."
        )
    if text.lstrip().startswith("Created:") and "(private-key" in text:
        return (
            "This looks like a GnuPG native .key file, but its public parameters "
            "could not be parsed. Enter Fingerprint and ID manually, or import an "
            "OpenPGP export (gpg --export-secret-keys --armor)."
        )
    if b"-----BEGIN PGP" in raw:
        return (
            "The OpenPGP key block could not be parsed. Enter Fingerprint and ID "
            "manually, or verify the file with: gpg --show-keys file.key"
        )
    return (
        "Could not determine Fingerprint/ID from this file. "
        "Best results come from OpenPGP secret-key exports "
        "(gpg --export-secret-keys --armor) or GnuPG private-keys-v1.d style .key files "
        "that include public parameters. You can still enter Fingerprint and ID manually."
    )


# ---------------------------------------------------------------------------
# GnuPG native private-keys-v1.d format
# ---------------------------------------------------------------------------


def _extract_via_gnupg_native(raw: bytes, filename: str = "") -> list[KeyIdentity]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []
    if "Created:" not in text or "(private-key" not in text:
        # protected-private-key has no usable public params for fingerprinting here
        return []
    if "(protected-private-key" in text and "(private-key" not in text.replace("protected-private-key", ""):
        return []

    created = _parse_gnupg_created(text)
    if created is None:
        return []

    role_hint = ""
    body: bytes | None = None

    if re.search(r"\(rsa\b", text):
        n = _parse_gnupg_hex_token(text, "n")
        e = _parse_gnupg_hex_token(text, "e")
        if not n or not e:
            return []
        body = (
            bytes([4])
            + int(created).to_bytes(4, "big")
            + bytes([1])  # RSA
            + _mpi_encode(n)
            + _mpi_encode(e)
        )
        role_hint = "C"
    elif re.search(r"curve\s+Ed25519", text, re.I):
        q = _parse_gnupg_hex_token(text, "q")
        if not q:
            return []
        body = (
            bytes([4])
            + int(created).to_bytes(4, "big")
            + bytes([22])  # EdDSA
            + bytes([len(_ED25519_OID)])
            + _ED25519_OID
            + _mpi_encode(q)
        )
        # S and A both use Ed25519; leave role empty unless caller prefers one.
        role_hint = ""
    elif re.search(r"curve\s+Curve25519", text, re.I):
        q = _parse_gnupg_hex_token(text, "q")
        if not q:
            return []
        body = (
            bytes([4])
            + int(created).to_bytes(4, "big")
            + bytes([18])  # ECDH
            + bytes([len(_CV25519_OID)])
            + _CV25519_OID
            + _mpi_encode(q)
            + _ECDH_KDF_PARAMS
        )
        role_hint = "E"
    else:
        return []

    fingerprint = _v4_fingerprint(body)
    return [
        KeyIdentity(
            fingerprint=fingerprint,
            key_id=_key_id_from_fingerprint(fingerprint),
            role=role_hint,
            source="gnupg-native",
        )
    ]


def _parse_gnupg_created(text: str) -> int | None:
    match = re.search(r"Created:\s*(\d{8}T\d{6})", text)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(dt.timestamp())


def _parse_gnupg_hex_token(text: str, name: str) -> bytes | None:
    # Matches: (n #HEX WITH SPACES AND NEWLINES#)
    pattern = re.compile(rf"\(\s*{re.escape(name)}\s*#([0-9A-Fa-f\s]+)#\s*\)", re.S)
    match = pattern.search(text)
    if not match:
        return None
    hex_digits = re.sub(r"\s+", "", match.group(1))
    if len(hex_digits) % 2:
        hex_digits = "0" + hex_digits
    try:
        return bytes.fromhex(hex_digits)
    except ValueError:
        return None


def _mpi_encode(data: bytes) -> bytes:
    value = data.lstrip(b"\x00") or b"\x00"
    bit_length = value[0].bit_length() + 8 * (len(value) - 1)
    return bit_length.to_bytes(2, "big") + value


def _keygrip_from_filename(filename: str) -> str:
    stem = Path(filename or "").stem
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", stem)
    if len(cleaned) == 40:
        return cleaned.upper()
    return ""


# ---------------------------------------------------------------------------
# gpg CLI helpers
# ---------------------------------------------------------------------------


def _find_gpg() -> str | None:
    found = shutil.which("gpg") or shutil.which("gpg.exe")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files\GnuPG\bin\gpg.exe"),
        Path(r"C:\Program Files (x86)\GnuPG\bin\gpg.exe"),
        Path.home() / "AppData/Local/Programs/GnuPG/bin/gpg.exe",
        Path("/usr/bin/gpg"),
        Path("/usr/local/bin/gpg"),
        Path("/opt/homebrew/bin/gpg"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _extract_via_gpg(raw: bytes) -> list[KeyIdentity]:
    gpg = _find_gpg()
    if not gpg:
        return []

    with tempfile.TemporaryDirectory(prefix="passman-gpg-") as tmp:
        path = Path(tmp) / "import.key"
        path.write_bytes(raw)
        output = _run_gpg_metadata(gpg, path)
    if not output:
        return []
    identities = _parse_gpg_colon_output(output)
    for item in identities:
        item.source = "gpg"
    return identities


def _run_gpg_metadata(gpg: str, path: Path) -> str:
    base = [gpg, "--batch", "--no-tty", "--status-fd", "2"]
    commands = [
        base + ["--show-keys", "--with-colons", "--with-fingerprint", str(path)],
        base
        + [
            "--import-options",
            "show-only",
            "--import",
            "--with-colons",
            "--with-fingerprint",
            str(path),
        ],
        base + ["--list-packets", str(path)],
    ]
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (completed.stdout or "") + "\n" + (completed.stderr or "")
        if "fpr:" in text or "sec:" in text or "pub:" in text or "ssb:" in text or "sub:" in text:
            return text
        if "keyid:" in text.lower() or "keyid :" in text.lower():
            return text
    return ""


def _parse_gpg_colon_output(text: str) -> list[KeyIdentity]:
    identities: list[KeyIdentity] = []
    pending_role = ""
    pending_label = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # gpg --list-packets style: "keyid: 1F4DF0EB1C80C710"
        keyid_match = re.search(r"keyid[:\s]+([0-9A-Fa-f]{8,40})", line, re.I)
        if keyid_match and ":" not in line.split()[0]:
            # Only use list-packets keyid if we cannot find colon fingerprints later.
            pass
        if ":" not in line:
            continue
        parts = line.split(":")
        tag = parts[0]
        if tag in {"sec", "pub", "ssb", "sub"}:
            pending_role = _roles_from_capability_field(parts[11] if len(parts) > 11 else "")
            if tag in {"sec", "pub"} and not pending_role:
                pending_role = "C"
        elif tag == "uid" and len(parts) > 9 and parts[9]:
            pending_label = parts[9]
        elif tag == "fpr" and len(parts) > 9 and parts[9]:
            fingerprint = _normalize_fingerprint(parts[9])
            if not fingerprint:
                continue
            identities.append(
                KeyIdentity(
                    fingerprint=fingerprint,
                    key_id=_key_id_from_fingerprint(fingerprint),
                    role=pending_role,
                    label=pending_label,
                )
            )
            pending_role = ""
    if identities:
        return identities

    # Fallback: parse list-packets keyids (no full fingerprint available).
    for raw_line in text.splitlines():
        match = re.search(r"keyid[:\s]+([0-9A-Fa-f]{16})", raw_line, re.I)
        if match:
            key_id = match.group(1).upper()
            identities.append(KeyIdentity(key_id=key_id, fingerprint="", source="gpg"))
    return identities


def _resolve_keygrip_via_gpg(keygrip: str) -> KeyIdentity | None:
    gpg = _find_gpg()
    if not gpg:
        return None
    commands = [
        [gpg, "--batch", "--no-tty", "--with-colons", "--with-fingerprint", "--with-keygrip", "--list-secret-keys"],
        [gpg, "--batch", "--no-tty", "--with-colons", "--with-fingerprint", "--with-keygrip", "--list-keys"],
    ]
    for command in commands:
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        text = completed.stdout or ""
        pending_fpr = ""
        pending_role = ""
        for line in text.splitlines():
            parts = line.split(":")
            if not parts:
                continue
            tag = parts[0]
            if tag in {"sec", "pub", "ssb", "sub"}:
                pending_role = _roles_from_capability_field(parts[11] if len(parts) > 11 else "")
                if tag in {"sec", "pub"} and not pending_role:
                    pending_role = "C"
            elif tag == "fpr" and len(parts) > 9:
                pending_fpr = _normalize_fingerprint(parts[9])
            elif tag == "grp" and len(parts) > 9:
                grip = _normalize_fingerprint(parts[9])
                if grip == keygrip.upper() and pending_fpr:
                    return KeyIdentity(
                        fingerprint=pending_fpr,
                        key_id=_key_id_from_fingerprint(pending_fpr),
                        role=pending_role,
                        source="gpg",
                    )
    return None


def _roles_from_capability_field(field: str) -> str:
    lowered = (field or "").lower()
    if lowered in {"s", "sign"}:
        return "S"
    if lowered in {"e", "encrypt"}:
        return "E"
    if lowered in {"a", "auth", "authenticate"}:
        return "A"
    if "c" in lowered and "s" not in lowered and "e" not in lowered and "a" not in lowered:
        return "C"
    if "c" in lowered:
        return "C"
    if "s" in lowered and "e" not in lowered and "a" not in lowered:
        return "S"
    if "e" in lowered and "s" not in lowered and "a" not in lowered:
        return "E"
    if "a" in lowered and "s" not in lowered and "e" not in lowered:
        return "A"
    return ""


# ---------------------------------------------------------------------------
# OpenPGP binary / armored packets
# ---------------------------------------------------------------------------


def _extract_via_openpgp_parse(raw: bytes) -> list[KeyIdentity]:
    try:
        binary = _maybe_dearmor(raw)
    except Exception:
        return []
    identities: list[KeyIdentity] = []
    for tag, body in _iter_packets(binary):
        if tag not in {5, 6, 7, 14} or not body:
            continue
        if not body or body[0] != 4:
            continue
        public_body = _public_key_body_from_packet(tag, body)
        if not public_body:
            continue
        fingerprint = _v4_fingerprint(public_body)
        role = "C" if tag in {5, 6} else ""
        identities.append(
            KeyIdentity(
                fingerprint=fingerprint,
                key_id=_key_id_from_fingerprint(fingerprint),
                role=role,
                source="openpgp",
            )
        )
    return identities


def _maybe_dearmor(raw: bytes) -> bytes:
    text = raw.decode("ascii", errors="ignore")
    if "-----BEGIN" not in text:
        return raw
    lines: list[str] = []
    in_body = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-----BEGIN"):
            in_body = True
            continue
        if stripped.startswith("-----END"):
            break
        if not in_body or not stripped or stripped.startswith("="):
            continue
        lines.append(stripped)
    if not lines:
        return raw
    return base64.b64decode("".join(lines), validate=False)


def _iter_packets(data: bytes):
    offset = 0
    length = len(data)
    while offset < length:
        tag_byte = data[offset]
        offset += 1
        if tag_byte & 0x80 == 0:
            break
        if tag_byte & 0x40:
            tag = tag_byte & 0x3F
            try:
                body_len, offset = _read_new_length(data, offset)
            except Exception:
                break
        else:
            length_type = tag_byte & 0x03
            tag = (tag_byte >> 2) & 0x0F
            if length_type == 0:
                if offset >= length:
                    break
                body_len = data[offset]
                offset += 1
            elif length_type == 1:
                body_len = int.from_bytes(data[offset : offset + 2], "big")
                offset += 2
            elif length_type == 2:
                body_len = int.from_bytes(data[offset : offset + 4], "big")
                offset += 4
            else:
                body_len = length - offset
        body = data[offset : offset + body_len]
        offset += body_len
        yield tag, body


def _read_new_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 192:
        return first, offset
    if first < 224:
        second = data[offset]
        offset += 1
        return ((first - 192) << 8) + second + 192, offset
    if first == 255:
        value = int.from_bytes(data[offset : offset + 4], "big")
        offset += 4
        return value, offset
    raise ValueError("Partial body length packets are not supported")


def _public_key_body_from_packet(tag: int, body: bytes) -> bytes | None:
    if not body or body[0] != 4:
        return None
    if tag in {6, 14}:
        return body
    try:
        return _slice_public_part_from_secret_body(body)
    except Exception:
        return None


def _slice_public_part_from_secret_body(body: bytes) -> bytes:
    if len(body) < 6:
        raise ValueError("Secret key packet too short")
    algo = body[5]
    offset = 6
    offset = _skip_public_key_material(body, offset, algo)
    return body[:offset]


def _skip_public_key_material(body: bytes, offset: int, algo: int) -> int:
    if algo in {1, 2, 3}:
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        return offset
    if algo == 16:
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        return offset
    if algo == 17:
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        offset = _skip_mpi(body, offset)
        return offset
    if algo in {18, 19, 22}:
        oid_len = body[offset]
        offset += 1 + oid_len
        offset = _skip_mpi(body, offset)
        if algo == 18:
            kdf_len = body[offset]
            offset += 1 + kdf_len
        return offset
    raise ValueError(f"Unsupported public-key algorithm: {algo}")


def _skip_mpi(body: bytes, offset: int) -> int:
    bit_len = int.from_bytes(body[offset : offset + 2], "big")
    offset += 2
    byte_len = (bit_len + 7) // 8
    return offset + byte_len


def _v4_fingerprint(public_key_body: bytes) -> str:
    length = len(public_key_body)
    prefix = bytes([0x99, (length >> 8) & 0xFF, length & 0xFF])
    return hashlib.sha1(prefix + public_key_body).hexdigest().upper()


def _normalize_fingerprint(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", value or "")
    return cleaned.upper()


def _key_id_from_fingerprint(fingerprint: str) -> str:
    cleaned = _normalize_fingerprint(fingerprint)
    if len(cleaned) < 16:
        return cleaned
    return cleaned[-16:]
