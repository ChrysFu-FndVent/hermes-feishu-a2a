from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def verify_webhook_signature(
    body: bytes,
    *,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    encrypt_key: str,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify Feishu's SHA-256 signature over timestamp, nonce, key, and raw body."""
    if not timestamp or not nonce or not signature or not encrypt_key:
        return False
    try:
        if tolerance_seconds and abs(time.time() - int(timestamp)) > tolerance_seconds:
            return False
    except ValueError:
        return False
    signed = timestamp.encode() + nonce.encode() + encrypt_key.encode() + body
    expected = hashlib.sha256(signed).hexdigest()
    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def decrypt_feishu_event(encrypted: str, encrypt_key: str) -> dict[str, Any]:
    """Decrypt the common Feishu ``encrypt`` envelope using AES-CBC."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    key = hashlib.sha256(encrypt_key.encode()).digest()
    raw = base64.b64decode(encrypted)
    block_size = algorithms.AES.block_size // 8
    if len(raw) < block_size * 2 or len(raw) % block_size:
        raise ValueError("invalid encrypted Feishu event length")
    iv, ciphertext = raw[:block_size], raw[block_size:]
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(algorithms.AES.block_size).unpadder()
    payload = unpadder.update(padded) + unpadder.finalize()
    parsed: object = json.loads(payload.decode())
    if not isinstance(parsed, dict):
        raise ValueError("decrypted Feishu event must be a JSON object")
    return {str(key): value for key, value in parsed.items()}
