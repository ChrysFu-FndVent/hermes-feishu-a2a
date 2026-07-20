from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from hermes_a2a.security import SecretBox, decrypt_feishu_event, verify_webhook_signature


def test_webhook_signature_accepts_current_body() -> None:
    body = b'{"event":"message"}'
    timestamp = str(int(time.time()))
    nonce = "nonce"
    token = "verification-token"
    signature = hmac.new(
        token.encode(), timestamp.encode() + nonce.encode() + body, hashlib.sha256
    ).hexdigest()

    assert verify_webhook_signature(
        body,
        timestamp=timestamp,
        nonce=nonce,
        signature=f"sha256={signature}",
        token=token,
    )
    assert not verify_webhook_signature(
        body + b"!",
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        token=token,
    )


def test_webhook_signature_rejects_stale_timestamp() -> None:
    timestamp = str(int(time.time()) - 600)
    assert not verify_webhook_signature(
        b"body",
        timestamp=timestamp,
        nonce="nonce",
        signature="bad",
        token="token",
        tolerance_seconds=30,
    )


def test_feishu_event_decryption_roundtrip() -> None:
    event = {"type": "event", "event": {"message": {"chat_id": "oc_demo"}}}
    encrypt_key = "test-encrypt-key"
    key = hashlib.sha256(encrypt_key.encode()).digest()
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(json.dumps(event).encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).encryptor()
    encrypted = base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode()

    assert decrypt_feishu_event(encrypted, encrypt_key) == event


def test_secret_box_requires_persistent_key() -> None:
    with pytest.raises(ValueError, match="persistent Fernet key"):
        SecretBox("")
