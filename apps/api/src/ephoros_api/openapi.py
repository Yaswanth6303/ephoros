"""Write the OpenAPI document to a file: python -m ephoros_api.openapi <path>."""

import json
import sys
from pathlib import Path

from ephoros_api.app import create_app
from ephoros_api.config import Settings


def export_openapi(path: Path) -> None:
    app = create_app(Settings(database_url="unused", redis_url="unused"))
    path.parent.mkdir(parents=True, exist_ok=True)
    # sorted + fixed indent keeps the file byte-stable for the CI drift check
    path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    export_openapi(Path(sys.argv[1]))
