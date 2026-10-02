"""AC-3: решение «завершена ли проверка и с каким исходом» — одна функция
`orchestrator/ci.py`, общая для `verifying_status` и `branch_status`.

SPEC не называет имени этой функции, и планка его не диктует: общая
функция разыскивается по исходникам двух читателей — функции модуля
`ci`, вызванные по имени в ОБЕИХ, за вычетом прежних общих узлов опроса
(`head_sha`, `check_runs`, `check_runs_page`, `gh`, `run_list`). Среди них
обязана найтись такая, которой передаётся сам check-run (или их список,
или его поля), и подмена которой меняет исход у обоих читателей. Копии
сравнения со строкой `"completed"` ни в одном из двух читателей нет.

Группа: разовый
Красен до реализации: `verifying_status` и `branch_status` каждая сверяет `r.get("status") != "completed"` сама, общей функции решения у них нет — оба теста падают.
"""
import ast
import inspect
import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import ci  # noqa: E402

READERS = ("verifying_status", "branch_status")
POLLING_HELPERS = {"head_sha", "check_runs", "check_runs_page", "gh",
                   "run_list"}

STUCK_REPORTED = {"id": 110766383863, "name": "Валидация артефактов",
                  "status": "in_progress", "conclusion": "success",
                  "started_at": "2026-10-02T08:29:01Z",
                  "created_at": "2026-10-02T08:29:00Z",
                  "completed_at": "2026-10-02T08:31:44Z"}
GREEN_CHECK = {"id": 1, "name": "python", "status": "completed",
               "conclusion": "success", "started_at": "2026-10-02T08:29:01Z",
               "created_at": "2026-10-02T08:29:00Z",
               "completed_at": "2026-10-02T08:30:00Z"}


class Sentinel(Exception):
    pass


def reader_tree(name: str) -> ast.AST:
    return ast.parse(textwrap.dedent(inspect.getsource(getattr(ci, name))))


def called_ci_functions(name: str) -> set[str]:
    """Функции модуля `ci`, вызванные по имени в теле читателя `name`."""
    names = set()
    for node in ast.walk(reader_tree(name)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            obj = getattr(ci, node.func.id, None)
            if inspect.isfunction(obj) and obj.__module__ == ci.__name__:
                names.add(node.func.id)
    return names


def shared_candidates() -> list[str]:
    common = set.intersection(*(called_ci_functions(n) for n in READERS))
    return sorted(common - POLLING_HELPERS - set(READERS))


def mentions_check_run(value) -> bool:
    if value is STUCK_REPORTED or value == STUCK_REPORTED:
        return True
    if isinstance(value, (list, tuple, set)):
        return any(mentions_check_run(v) for v in value)
    if isinstance(value, dict):
        return any(mentions_check_run(v) for v in value.values())
    return value in ("in_progress", STUCK_REPORTED["completed_at"])


def fake_gh(*args, **kwargs):
    joined = " ".join(args)
    if "check-runs" in joined:
        runs = [GREEN_CHECK, STUCK_REPORTED]
        return subprocess.CompletedProcess(
            ["gh"], 0, json.dumps({"total_count": 2, "check_runs": runs}), "")
    return subprocess.CompletedProcess(["gh"], 0, "[]", "")


class SingleCompletionRuleTest(unittest.TestCase):

    def setUp(self):
        for target, value in (("gh", fake_gh),
                              ("head_sha", lambda b, repo=None: ("6cb9b55e" + "0" * 32, ""))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ac3_readers_hold_no_own_completed_comparison(self):
        """В телах обоих читателей нет литерала `"completed"`.

        Сравнение `status != "completed"` (или `== "completed"`) живёт
        только в общей функции решения; читатель, сохранивший свою копию,
        расходился бы с ней при следующей правке правила.

        Ловит мутацию: правило вынесено в функцию для `verifying_status`,
        а в `branch_status` оставлена прежняя строка
        `if r.get("status") != "completed"` — литерал найдётся в её теле.
        """
        for name in READERS:
            literals = [n.lineno for n in ast.walk(reader_tree(name))
                        if isinstance(n, ast.Constant) and n.value == "completed"]
            with self.subTest(reader=name):
                self.assertEqual(literals, [],
                                 f"ci.{name} держит свою копию сравнения со "
                                 f"строкой 'completed' (строки тела {literals})")

    def test_ac3_one_function_decides_for_both_readers(self):
        """Подмена общей функции решения меняет исход обоих читателей.

        Кандидаты — функции `ci`, вызванные по имени и в
        `verifying_status`, и в `branch_status`, кроме узлов опроса.
        Нужная — та, которой при опросе передаётся check-run (сам словарь,
        список check-run'ов или его поля): подменённая функцией, бросающей
        исключение, она обрывает и `verifying_status`, и `branch_status`
        (исход у обеих меняется).

        Ловит мутацию: у каждого читателя своя функция решения
        (`_verifying_running(runs)` и `_gate_running(runs)`) — общей
        функции, получающей check-run, не найдётся; либо общая функция
        заведена, но `branch_status` её не зовёт и решает сама — подмена не
        оборвёт `branch_status`.
        """
        candidates = shared_candidates()
        self.assertTrue(candidates,
                        "у verifying_status и branch_status нет ни одной общей "
                        "функции модуля ci, кроме узлов опроса "
                        f"{sorted(POLLING_HELPERS)}")

        deciding = []
        for name in candidates:
            original = getattr(ci, name)
            seen: dict = {r: False for r in READERS}
            current = {"reader": None}

            def spy(*args, _orig=original, **kwargs):
                if mentions_check_run(list(args) + list(kwargs.values())):
                    seen[current["reader"]] = True
                return _orig(*args, **kwargs)

            with mock.patch.object(ci, name, spy):
                for reader in READERS:
                    current["reader"] = reader
                    getattr(ci, reader)("task/x")
            if all(seen.values()):
                deciding.append(name)

        self.assertTrue(deciding,
                        f"ни одной общей функции {candidates} оба читателя не "
                        f"передают check-run")

        for name in deciding:
            def boom(*args, **kwargs):
                raise Sentinel(name)

            with mock.patch.object(ci, name, boom):
                for reader in READERS:
                    with self.subTest(function=name, reader=reader):
                        with self.assertRaises(Sentinel):
                            getattr(ci, reader)("task/x")


if __name__ == "__main__":
    unittest.main()
