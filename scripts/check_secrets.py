from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache"}
PATTERNS = {
    "Feishu app secret": re.compile(
        r"(?:app_secret|secret)\s*[:=]\s*['\"]?(?!replace|your|xxx|change-me)[A-Za-z0-9_\-]{20,}",
        re.I,
    ),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{24,}", re.I),
}


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {path.relative_to(ROOT)}")
    if findings:
        print("Potential secrets found:")
        print("\n".join(findings))
        return 1
    print("No obvious secrets found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
