from pathlib import Path


def _pin_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_qsl_pin_manifests_are_kept_in_sync() -> None:
    root = Path(__file__).resolve().parents[1]
    pins = root / "qsl-pins.txt"
    constraints = root / "constraints.txt"

    assert pins.exists(), "qsl-pins.txt missing"
    assert constraints.exists(), "constraints.txt missing"
    assert "source of truth" in pins.read_text(encoding="utf-8")
    assert "pip-compatible constraints mirror" in constraints.read_text(encoding="utf-8")
    assert _pin_lines(pins) == _pin_lines(constraints)
