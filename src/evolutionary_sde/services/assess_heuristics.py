from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass
class AssessmentResult:
    passed: bool
    big_o_guess: str
    space_guess: str
    bullets: list[str]


def assess_python(code: str) -> AssessmentResult:
    """Lightweight static hints — not a substitute for real analysis."""
    bullets: list[str] = []
    if not code.strip():
        return AssessmentResult(
            False,
            "unknown",
            "unknown",
            ["Empty submission — add a concrete implementation."],
        )

    tree = None
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return AssessmentResult(
            False,
            "unknown",
            "unknown",
            [f"Syntax error — fix before complexity discussion: {e.msg} at line {e.lineno}."],
        )

    loop_depth = _max_loop_depth(tree)
    has_nested = loop_depth >= 2
    uses_sorted = _uses_call(tree, "sorted")
    uses_dict = _uses_constructor(tree, "dict") or _uses_dict_literal(tree)
    uses_set = _uses_constructor(tree, "set") or _uses_set_literal(tree)
    uses_heap = _uses_call(tree, "heappush") or _uses_call(tree, "heapq")

    big_o = "O(n) or better (single pass / hash lookups)"
    if has_nested:
        big_o = "Likely O(n²) or worse — verify whether inner loop is amortized or bounded"
    if uses_sorted:
        big_o = "At least O(n log n) from sorting — acceptable if problem requires ordering"

    space = "O(n) auxiliary if storing all inputs"
    if uses_dict or uses_set:
        space = "O(n) typical for hash structures — call out key size / memory per entry"
    if uses_heap:
        space = "O(k) heap if only top-k — good; else O(n) if heap holds all"

    bullets.append(f"Static scan suggests **time**: {big_o}.")
    bullets.append(f"Static scan suggests **space**: {space}.")

    if has_nested:
        bullets.append(
            "Nested loops detected — justify with **input constraints** or refactor "
            "(two-pointer, monotonic stack, prefix sums, hash map)."
        )
    if re.search(r"\+=\s*[\"']", code):
        bullets.append(
            "String concatenation in a loop often devolves to **O(n²)** — prefer list join or io.StringIO."
        )
    if "list(" in code and "sorted(" in code:
        bullets.append("Ensure you are not **sorting repeatedly** inside a hot loop.")

    # Phase-1 bar: require some structure beyond a stub
    passed = tree is not None and len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]) >= 1
    if not passed:
        bullets.append("Add at least one **function** with a clear API for the core logic.")

    return AssessmentResult(passed, big_o, space, bullets)


def _max_loop_depth(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            best = max(best, _max_loop_depth(child, depth + 1))
        else:
            best = max(best, _max_loop_depth(child, depth))
    return best


def _uses_call(tree: ast.AST, name: str) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id == name:
                return True
            if isinstance(n.func, ast.Attribute) and n.func.attr == name:
                return True
    return False


def _uses_constructor(tree: ast.AST, name: str) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name:
            return True
    return False


def _uses_dict_literal(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            return True
    return False


def _uses_set_literal(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Set):
            return True
    return False
