"""Fail when transport or orchestration dependencies leak into P0 domain ports."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / "apps/api/app/ports.py"
DOMAIN_FORBIDDEN = {
    "alembic",
    "anthropic",
    "fastapi",
    "google",
    "langgraph",
    "litellm",
    "openai",
    "psycopg",
    "pydantic",
    "sqlalchemy",
}
VENDOR_ROOTS = {"anthropic", "google", "litellm", "openai"}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> None:
    port_leaks = imported_roots(PORT) & DOMAIN_FORBIDDEN
    if port_leaks:
        raise SystemExit(f"Domain port imports forbidden dependencies: {sorted(port_leaks)}")

    product_leaks = []
    for path in sorted((ROOT / "apps/api/app").rglob("*.py")):
        if "adapters" in path.parts:
            continue
        leaked = imported_roots(path) & VENDOR_ROOTS
        if leaked:
            product_leaks.append(f"{path.relative_to(ROOT)}: {sorted(leaked)}")
    if product_leaks:
        raise SystemExit("Vendor SDK import outside adapters:\n" + "\n".join(product_leaks))
    print("ProviderPort boundary is transport-neutral; no vendor SDK leaks found")


if __name__ == "__main__":
    main()
