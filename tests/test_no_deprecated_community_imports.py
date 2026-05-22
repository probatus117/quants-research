from pathlib import Path


def test_production_code_does_not_import_deprecated_community_shim():
    root = Path(__file__).resolve().parents[1]
    forbidden = "from src.data.graph_query.community import"
    offenders = []

    for base in ["src", "tools"]:
        for path in (root / base).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if path.as_posix().endswith("src/data/graph_query/community.py"):
                continue
            if forbidden in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(root).as_posix())

    assert offenders == []
