"""Audit the candidate trace matrix, case references and implementation DAG."""
from collections import Counter
from graphlib import TopologicalSorter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "docs/requirements/traceability.md"
MATRIX = ROOT / "docs/testing/test-matrix.md"
SOURCE = ROOT / "docs/handoff/v1.4/baseline"


def catalogue(text, pattern):
    return Counter(re.findall(r"^\|\s*\**(" + pattern + r")\**\s*\|", text, re.M))


def check():
    trace = TRACE.read_text()
    ids = r"(?:FR|NFR|MA-FR)-\d+"
    expected = Counter()
    for path in sorted(SOURCE.glob("*.md")):
        expected.update(catalogue(path.read_text(), ids))
    observed = catalogue(trace, ids)
    if not expected or observed != expected:
        raise ValueError(f"Catalogue differences: extra={observed-expected}, missing={expected-observed}")
    cards = sorted((ROOT / "tasks").glob("TASK-C-*.md"))
    graph = {}
    required_cases = set(re.findall(r"\bP0-\d\d\b", trace))
    for card in cards:
        contents = card.read_text()
        key = card.stem.removeprefix("TASK-")
        deps = re.search(r"^\| Dependencies \| (.*?) \|", contents, re.M)
        if deps is None:
            raise ValueError(f"{key} has no dependency field")
        graph[key] = re.findall(r"C-\d{3}", deps[1])
        required_cases.update(re.findall(r"\bP0-\d\d\b", contents))
    ordered = list(TopologicalSorter(graph).static_order())
    if len(cards) != 15 or set(ordered) != set(graph):
        raise ValueError("Missing card or unknown dependency")
    cases = catalogue(MATRIX.read_text(), r"P0-\d\d")
    missing = required_cases - cases.keys()
    duplicates = [key for key, count in cases.items() if count != 1]
    if missing or duplicates:
        raise ValueError(f"Test case definitions: missing={sorted(missing)}, duplicated={duplicates}")
    print(f"{sum(observed.values())} source requirements, {len(cases)} P0 cases, {len(cards)} acyclic cards")


if __name__ == "__main__":
    check()
