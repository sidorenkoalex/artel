"""AC-3 (tasks/T057/SPEC.md): обвязка `acquire`/`release` мутирующих
команд вызывается из одной общей точки в `orchestrator/lease.py`; все 8
прежних вызывателей (`orchestrator/fsm.py`: advance, approve, reject;
`orchestrator/runner.py`: run; `orchestrator/auto.py`: auto;
`orchestrator/budget.py`: budget; `orchestrator/cleanup.py`: kill;
`orchestrator/workspace.py`: workspace) используют эту точку — grep
прямых пар `acquire`+`release` по этим вызывателям не находит остаточных
самостоятельных копий обвязки.

Критерий не называет конкретное имя новой точки (SPEC отдаёт выбор формы
— «контекст-менеджер или эквивалент» — разработчику), поэтому тест не
завязывается на имя: он (1) grep'ом подтверждает отсутствие у каждого из
6 файлов-вызывателей собственной пары прямых вызовов `.acquire(`/
`.release(` (то есть самодельная обвязка `resolve_session_id → acquire →
отказ → try/finally release` из требования 2 SPEC этими файлами больше
не пишется) и (2) AST-обходом `orchestrator/lease.py` подтверждает, что
в модуле существует ОДНО определение (функция/класс, помимо самих
`acquire`/`release`/`resolve_session_id`), которое вызывает и `acquire`,
и `release`, — то есть общая точка обвязки физически живёт там, где
требует критерий.
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

CALLER_FILES = (
    "orchestrator/fsm.py",
    "orchestrator/runner.py",
    "orchestrator/auto.py",
    "orchestrator/budget.py",
    "orchestrator/cleanup.py",
    "orchestrator/workspace.py",
)

LEASE_MODULE_PATH = REPO_ROOT / "orchestrator" / "lease.py"

# Определения самой lease.py, чьё тело закономерно ссылается на оба имени
# (сами `acquire`/`release`) или ни на одно из них — не в счёт при поиске
# общей точки обвязки.
LEASE_OWN_DEFS = {"acquire", "release", "resolve_session_id", "_age_seconds"}


class NoResidualDirectPairsInCallersTest(unittest.TestCase):
    """Часть 1 критерия: у вызывателей больше нет самодельной пары
    прямых `.acquire(` + `.release(`."""

    def test_ac3_callers_have_no_residual_acquire_release_pairs(self):
        offenders = []
        for rel in CALLER_FILES:
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            has_acquire = ".acquire(" in text
            has_release = ".release(" in text
            if has_acquire and has_release:
                offenders.append(rel)
        self.assertEqual(
            offenders, [],
            f"эти вызыватели обязаны перейти на общую точку обвязки в "
            f"orchestrator/lease.py вместо собственной пары "
            f".acquire(...)/.release(...): {offenders}")


class SharedEntryPointExistsInLeaseModuleTest(unittest.TestCase):
    """Часть 2 критерия: общая точка обвязки физически определена в
    orchestrator/lease.py и вызывает и acquire, и release."""

    def test_ac3_lease_module_defines_a_binding_that_calls_both(self):
        source = LEASE_MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        candidates = []
        for node in ast.walk(tree):
            if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name in LEASE_OWN_DEFS:
                continue
            called_names = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    func = sub.func
                    if isinstance(func, ast.Attribute):
                        called_names.add(func.attr)
                    elif isinstance(func, ast.Name):
                        called_names.add(func.id)
            if {"acquire", "release"} <= called_names:
                candidates.append(node.name)
        self.assertTrue(
            candidates,
            "orchestrator/lease.py обязан определять одну общую точку "
            "обвязки (не acquire/release/resolve_session_id сами по "
            "себе), которая вызывает и acquire, и release")


if __name__ == "__main__":
    unittest.main()
