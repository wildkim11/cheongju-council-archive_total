import hashlib
import json
from pathlib import Path

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

def save_json(path: Path, obj) -> None:
    save_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
