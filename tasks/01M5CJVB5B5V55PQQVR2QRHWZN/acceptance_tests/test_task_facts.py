"""Факты задачи о файлах `tests/`: смоук гейтов `advance` не тронут, тесты задачи без сети и Node, прежние сценарии `components:` до `verifying` не ослаблены.

Группа: разовый
Зелёный с рождения: до кода задачи её дифф не трогает ни `tests/test_fsm_advance_gate_smoke.py`, ни прежние долгоживущие файлы, а долгоживущие файлы задачи (`tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_*.py`, автор test_author) уже лежат в рабочей копии без сетевых адресов и запуска Node — краснеть файл обязан, когда developer правит эти пути вопреки критериям.

Источник — помощник пульта `_pult.py`: `changed_paths()` (пути задачи
правилом гейта зон), `branch_diff()` (закоммиченный дифф от базы),
`artifact_text("PLAN.md")`, `CODE_ROOT`. Прогоны pytest — дочерним
интерпретатором в корне рабочей копии с флагами планки пульта.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, TASK_ID, artifact_text, branch_diff, changed_paths  # noqa: E402

SMOKE = "tests/test_fsm_advance_gate_smoke.py"
# Прежний долгоживущий сценарий `in_dev -> verifying` на `components:` с
# `report` (SPEC, «Материалы»).
PREVIOUS = "tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py"
PREVIOUS_SELECT = "Ac15BranchTest"
LONG_LIVED_OF_TASK = re.compile(
    r"^tests/test_" + TASK_ID.lower() + r"_[a-z0-9_]+\.py$")
PREVIOUS_LONG_LIVED = re.compile(r"^tests/test_01[0-9a-z]{24}_[a-z0-9_]+\.py$")
NETWORK = re.compile(r"\bhttps?://|\bwss?://")
NODE_RUN = re.compile(r"""["'](?:node|npx|npm)["']""")


def pytest_run(*args: str, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-p", "no:cacheprovider",
         "-p", "timeout", "-o", "timeout=120", "-q"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=timeout)


def file_hunks(diff: str) -> dict:
    """{путь: (было ли в базе, [удалённые строки])} unified-диффа задачи."""
    found: dict = {}
    path, existed = None, False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, existed = None, False
            continue
        if line.startswith("--- "):
            existed = line != "--- /dev/null"
            continue
        if line.startswith("+++ "):
            target = line[4:]
            path = target[2:] if target.startswith("b/") else None
            if path is not None:
                found.setdefault(path, (existed, []))
            continue
        if path is not None and line.startswith("-"):
            found[path][1].append(line[1:])
    return found


class TaskFactsTest(unittest.TestCase):

    def test_ac1_gate_smoke_unchanged_and_green(self):
        """`tests/test_fsm_advance_gate_smoke.py` не входит в пути задачи и зелёный на её рабочей копии.

        Сценарий: путь смоука нет среди `changed_paths()`; прогон файла
        pytest в корне рабочей копии — код 0.

        Ловит мутацию: смоук подогнан под новый гейт (путь в диффе) либо
        гейт исходов меняет журнал/вывод прежних сценариев — прогон красный.
        """
        self.assertNotIn(SMOKE, changed_paths())
        res = pytest_run(SMOKE, timeout=110)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])

    def test_ac14_task_tests_offline_without_node_on_junit_project(self):
        """Тесты задачи в `tests/` не несут сетевых адресов и запуска Node; сквозной сценарий — на компоненте `junit-xml`.

        Сценарий: новые долгоживущие файлы задачи
        (`tests/test_<id>_*.py`) и прочие новые/изменённые файлы `tests/`
        задачи: хотя бы один файл задачи есть; ни в одном нет адреса
        `http(s)://`/`ws(s)://` и литерала команды `node`/`npx`/`npm`; хотя
        бы один файл задачи строит компонент `junit-xml`.

        Ловит мутацию: тест задачи зовёт настоящий Node или ходит по
        сетевому адресу — признак найден; сквозной сценарий не на
        `junit-xml` — литерала нет ни в одном файле.
        """
        paths = [p for p in changed_paths() if p.startswith("tests/")
                 and p.endswith(".py") and (Path(CODE_ROOT) / p).is_file()]
        own = [p for p in paths if LONG_LIVED_OF_TASK.match(p)]
        self.assertTrue(own, f"долгоживущих файлов задачи нет среди {paths}")
        texts = {p: (Path(CODE_ROOT) / p).read_text(encoding="utf-8") for p in paths}
        for path, text in texts.items():
            with self.subTest(path=path):
                self.assertIsNone(NETWORK.search(text), path)
                self.assertIsNone(NODE_RUN.search(text), path)
        self.assertTrue(any("junit-xml" in texts[p] for p in own), own)

    def test_ac15_previous_components_scenarios_green_assertions_kept(self):
        """Прежние долгоживущие файлы, тронутые задачей, — без удалённых строк и названы в PLAN; сценарий `in_dev -> verifying` на `components:` зелёный.

        Сценарий: по диффу задачи у каждого изменённого (бывшего в базе)
        долгоживущего файла прежних задач `tests/test_<id>_*.py` нет
        удалённых строк, и PLAN.md называет его путь; прогон класса
        `Ac15BranchTest` файла `tests/test_01m5aqh8m2dkbv30nby86j34a7_
        fail_to_pass.py` (переход в `verifying` на `pult-vitest`) — код 0.

        Ловит мутацию: утверждение прежнего сценария переписано под гейт
        (строка удалена) либо добавленная подготовка не заявлена в PLAN;
        гейт исходов отказывает прежнему зелёному сценарию — прогон
        красный.
        """
        hunks = file_hunks(branch_diff())
        touched = [p for p, (existed, _removed) in hunks.items()
                   if existed and PREVIOUS_LONG_LIVED.match(p)
                   and not LONG_LIVED_OF_TASK.match(p)]
        plan = (artifact_text("PLAN.md") or "") if touched else ""
        for path in touched:
            with self.subTest(path=path):
                self.assertEqual(hunks[path][1], [], path)
                self.assertIn(path, plan, f"{path} не назван в PLAN.md")
        res = pytest_run(f"{PREVIOUS}::{PREVIOUS_SELECT}", timeout=110)
        self.assertEqual(res.returncode, 0, res.stdout[-3000:] + res.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
