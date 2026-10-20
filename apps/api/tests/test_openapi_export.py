from pathlib import Path

from ephoros_api.openapi import export_openapi


def test_export_is_byte_stable(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "nested" / "b.json"
    export_openapi(a)
    export_openapi(b)
    assert a.read_bytes() == b.read_bytes()
    assert '"operationId": "readyz"' in a.read_text()
