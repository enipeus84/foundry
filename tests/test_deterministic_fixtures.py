"""DET-6: projection-relevant demo fixtures must declare their clock."""

import ast
from pathlib import Path


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _unclocked_demo_builds(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_build_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "foundry.demo_data"
        for alias in node.names
        if alias.name == "build"
    }
    seeded_module_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name in ("foundry.demo_data", "seed_synthetic_household")
    } | {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module in ("foundry", "examples")
        for alias in node.names
        if alias.name in ("demo_data", "seed_synthetic_household")
    }

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        direct_call = (
            isinstance(node.func, ast.Name)
            and node.func.id in direct_build_names
        )
        seeded_call = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "build"
            and _qualified_name(node.func.value) in seeded_module_names
        )
        if not (direct_call or seeded_call):
            continue
        as_of = next(
            (keyword.value for keyword in node.keywords
             if keyword.arg == "as_of"),
            None,
        )
        if as_of is None or (
            isinstance(as_of, ast.Constant) and as_of.value is None
        ):
            violations.append(node.lineno)
    return violations


def test_guard_detects_direct_and_module_qualified_unclocked_builds(tmp_path):
    fixture = tmp_path / "test_unclocked.py"
    fixture.write_text(
        "from foundry.demo_data import build\n"
        "import seed_synthetic_household as seed\n"
        "import foundry.demo_data\n"
        "build(log)\n"
        "seed.build(log)\n"
        "foundry.demo_data.build(log)\n"
        "build(log, as_of=123.0)\n",
        encoding="utf-8",
    )

    assert _unclocked_demo_builds(fixture) == [4, 5, 6]


def test_projection_relevant_demo_builds_declare_explicit_as_of():
    tests_root = Path(__file__).resolve().parent
    violations = {
        path.name: lines
        for path in sorted(tests_root.glob("test_*.py"))
        if (lines := _unclocked_demo_builds(path))
    }

    assert violations == {}
