# utils/io.py
import json
from pathlib import Path
from typing import Any


def save_json(data, output_path, indent: int = 4):
    """
    Lưu object Python thành file json.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def load_json(input_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)
