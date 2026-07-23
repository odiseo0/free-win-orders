"""Exporta el contrato OpenAPI generado por la aplicación."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.application import app

OUTPUT_PATH = PROJECT_ROOT / "docs" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT_PATH.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI exportado en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
