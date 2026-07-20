from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def verify_webhook_signature(
    body: bytes,
    *,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    token: str,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify a simple Feishu-compatible HMAC envelope.

    Gateways may put the signature in ``X-Lark-Signature`` or pass it as a
    request field. The signed value is timestamp + nonce + raw body. Keeping
    this check in one place avoids accidentally authenticating parsed JSON.
    """
    if not timestamp or not nonce or not signature or not token:
        return False
    try:
        if tolerance_seconds and abs(time.time() - int(timestamp)) > tolerance_seconds:
            return False
    except ValueError:
        return False
    expected = hmac.new(
        token.encode(), timestamp.encode() + nonce.encode() + body, hashlib.sha256
    ).hexdigest()
    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def decrypt_feishu_event(encrypted: str, encrypt_key: str) -> dict[str, Any]:
    """Decrypt the common Feishu ``encrypt`` envelope using AES-CBC."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    key = hashlib.sha256(encrypt_key.encode()).digest()
    raw = base64.b64decode(encrypted)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor()
    padded = decryptor.update(raw) + decryptor.finalize()
    unpadder = PKCS7(algorithms.AES.block_size).unpadder()
    payload = unpadder.update(padded) + unpadder.finalize()
    parsed: object = json.loads(payload.decode())
    if not isinstance(parsed, dict):
        raise ValueError("decrypted Feishu event must be a JSON object")
    return {str(key): value for key, value in parsed.items()}


class SecretBox:
    def __init__(self, key: str):
        if not key:
            raise ValueError("a persistent Fernet key is required")
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("secret could not be decrypted") from exc


def redact(value: object, secrets: list[str]) -> object:
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[REDACTED]")
        return result
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value
