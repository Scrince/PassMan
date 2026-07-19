from __future__ import annotations

import base64
import hashlib
import hmac
import re
import struct
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse


HASH_ALGORITHMS = {
    "SHA1": hashlib.sha1,
    "SHA256": hashlib.sha256,
    "SHA512": hashlib.sha512,
}


@dataclass(slots=True)
class OtpAuthUri:
    type: str  # totp | hotp
    name: str
    issuer: str
    secret: str
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30
    counter: int = 0


def normalize_secret(secret: str) -> str:
    cleaned = re.sub(r"\s+", "", str(secret or "")).upper().replace("-", "").replace("=", "")
    # Base32 alphabet only
    cleaned = re.sub(r"[^A-Z2-7]", "", cleaned)
    return cleaned


def decode_secret(secret: str) -> bytes:
    cleaned = normalize_secret(secret)
    if not cleaned:
        raise ValueError("Authenticator secret is empty.")
    # Pad to a multiple of 8 for base32.
    padded = cleaned + ("=" * ((8 - len(cleaned) % 8) % 8))
    try:
        return base64.b32decode(padded, casefold=True)
    except Exception as exc:
        raise ValueError("Authenticator secret is not valid Base32.") from exc


def generate_totp(
    secret: str,
    *,
    period: int = 30,
    digits: int = 6,
    algorithm: str = "SHA1",
    for_time: float | None = None,
) -> str:
    period = max(1, int(period or 30))
    digits = max(6, min(8, int(digits or 6)))
    algo = HASH_ALGORITHMS.get((algorithm or "SHA1").upper(), hashlib.sha1)
    key = decode_secret(secret)
    counter = int((time.time() if for_time is None else for_time) // period)
    return _hotp(key, counter, digits=digits, algorithm=algo)


def generate_hotp(
    secret: str,
    counter: int,
    *,
    digits: int = 6,
    algorithm: str = "SHA1",
) -> str:
    digits = max(6, min(8, int(digits or 6)))
    algo = HASH_ALGORITHMS.get((algorithm or "SHA1").upper(), hashlib.sha1)
    key = decode_secret(secret)
    return _hotp(key, int(counter), digits=digits, algorithm=algo)


def seconds_remaining(period: int = 30, for_time: float | None = None) -> int:
    period = max(1, int(period or 30))
    now = time.time() if for_time is None else for_time
    return period - int(now % period)


def _hotp(key: bytes, counter: int, *, digits: int, algorithm) -> str:
    msg = struct.pack(">Q", int(counter) & 0xFFFFFFFFFFFFFFFF)
    digest = hmac.new(key, msg, algorithm).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10**digits)
    return str(code).zfill(digits)


def parse_otpauth_uri(uri: str) -> OtpAuthUri:
    text = str(uri or "").strip()
    if not text.lower().startswith("otpauth://"):
        raise ValueError("Not an otpauth:// URI.")
    parsed = urlparse(text)
    otp_type = (parsed.hostname or "totp").lower()
    if otp_type not in {"totp", "hotp"}:
        raise ValueError(f"Unsupported authenticator type: {otp_type}")

    label = unquote((parsed.path or "").lstrip("/"))
    issuer_from_label = ""
    name = label
    if ":" in label:
        issuer_from_label, name = label.split(":", 1)
        issuer_from_label = issuer_from_label.strip()
        name = name.strip()

    query = parse_qs(parsed.query, keep_blank_values=False)
    secret = (query.get("secret") or [""])[0]
    if not secret:
        raise ValueError("otpauth URI is missing a secret.")
    secret = normalize_secret(secret)
    decode_secret(secret)  # validate

    issuer = (query.get("issuer") or [issuer_from_label])[0].strip() or issuer_from_label
    algorithm = ((query.get("algorithm") or ["SHA1"])[0] or "SHA1").upper()
    if algorithm not in HASH_ALGORITHMS:
        algorithm = "SHA1"
    try:
        digits = int((query.get("digits") or ["6"])[0])
    except ValueError:
        digits = 6
    digits = 6 if digits not in {6, 7, 8} else digits
    try:
        period = int((query.get("period") or ["30"])[0])
    except ValueError:
        period = 30
    period = max(1, min(300, period))
    try:
        counter = int((query.get("counter") or ["0"])[0])
    except ValueError:
        counter = 0

    return OtpAuthUri(
        type=otp_type,
        name=name or issuer or "Authenticator",
        issuer=issuer,
        secret=secret,
        algorithm=algorithm,
        digits=digits,
        period=period,
        counter=max(0, counter),
    )


def parse_import_text(text: str) -> list[OtpAuthUri]:
    """Parse otpauth URIs and simple secret lines from pasted/imported text."""
    results: list[OtpAuthUri] = []
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # otpauth URI
        if line.lower().startswith("otpauth://"):
            try:
                item = parse_otpauth_uri(line)
            except ValueError:
                continue
            key = f"{item.type}:{item.issuer}:{item.name}:{item.secret}"
            if key not in seen:
                seen.add(key)
                results.append(item)
            continue
        # name,secret or issuer:name,secret
        if "," in line:
            left, right = line.split(",", 1)
            left = left.strip()
            secret = normalize_secret(right)
            try:
                decode_secret(secret)
            except ValueError:
                continue
            issuer = ""
            name = left
            if ":" in left:
                issuer, name = left.split(":", 1)
                issuer = issuer.strip()
                name = name.strip()
            item = OtpAuthUri(type="totp", name=name or "Authenticator", issuer=issuer, secret=secret)
            key = f"{item.type}:{item.issuer}:{item.name}:{item.secret}"
            if key not in seen:
                seen.add(key)
                results.append(item)
            continue
        # bare base32 secret
        secret = normalize_secret(line)
        if len(secret) < 8:
            continue
        try:
            decode_secret(secret)
        except ValueError:
            continue
        item = OtpAuthUri(type="totp", name="Imported", issuer="", secret=secret)
        key = f"{item.type}:{item.issuer}:{item.name}:{item.secret}"
        if key not in seen:
            seen.add(key)
            results.append(item)
    return results
