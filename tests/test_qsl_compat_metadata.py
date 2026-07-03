from pathlib import Path
import tomllib


def test_qsl_compat_metadata_exists_and_bundle() -> None:
    qsl_path = Path(__file__).resolve().parents[1] / "qsl.toml"
    assert qsl_path.exists(), "qsl.toml missing"
    with qsl_path.open("rb") as f:
        data = tomllib.load(f)

    assert data.get("compat", {}).get("bundle") == "2026.07.1", "compat.bundle mismatch"

