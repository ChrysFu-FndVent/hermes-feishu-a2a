from __future__ import annotations

import base64
import hashlib
import json
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from hermes_a2a.security import decrypt_feishu_event, verify_webhook_signature


def test_webhook_signature_accepts_current_body() -> None:
    body = b'{"event":"message"}'
    timestamp = str(int(time.time()))
    nonce = "nonce"
    encrypt_key = "encrypt-key"
    signature = hashlib.sha256(
        timestamp.encode() + nonce.encode() + encrypt_key.encode() + body
    ).hexdigest()

    assert verify_webhook_signature(
        body,
        timestamp=timestamp,
        nonce=nonce,
        signature=f"sha256={signature}",
        encrypt_key=encrypt_key,
    )
    assert not verify_webhook_signature(
        body + b"!",
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        encrypt_key=encrypt_key,
    )


def test_webhook_signature_rejects_stale_timestamp() -> None:
    timestamp = str(int(time.time()) - 600)
    assert not verify_webhook_signature(
        b"body",
        timestamp=timestamp,
        nonce="nonce",
        signature="bad",
        encrypt_key="encrypt-key",
        tolerance_seconds=30,
    )


def test_feishu_event_decryption_roundtrip() -> None:
    event = {"type": "event", "event": {"message": {"chat_id": "oc_demo"}}}
    encrypt_key = "test-encrypt-key"
    key = hashlib.sha256(encrypt_key.encode()).digest()
    iv = b"0123456789abcdef"
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(json.dumps(event).encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    encrypted = base64.b64encode(iv + ciphertext).decode()

    assert decrypt_feishu_event(encrypted, encrypt_key) == event
