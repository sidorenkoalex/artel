"""AC-6 (SPEC): «Планка A7 (44 приёмочных теста) и планка hotfix
01M1KT0792125J9ZNJNZJ86E9Q остаются зелёными без ослабления существующих
проверок».

Зелёный с рождения (обе части): обе планки уже зелёные СЕГОДНЯ, до
единой строчки кода этой задачи — критерий охраняет РЕГРЕССИЮ будущей
правки `checkpoint.py`/`fsm_advance.py`/`doctor.py`, а не описывает новую
функциональность. Тот же приём и то же основание, что уже применил
`tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/
test_ac7_full_suite_and_a7_tests_green.py` для СВОЕЙ пары «tests/ +
планка A7» — здесь пара другая («планка A7» + «планка hotfix»), приём
идентичен: `subprocess` прогон `unittest discover` реальным интерпретатором
против ТЕКУЩЕГО кода `orchestrator/`, не зафиксированной копии.

Планка hotfix живёт не в рабочем дереве этой ветки (RETRO задачи
01M1KT0792125J9ZNJNZJ86E9Q убрала `tasks/01M1KT0792125J9ZNJNZJ86E9Q/` из
main целиком — см. `docs/retro/01M1KT0792125J9ZNJNZJ86E9Q.md`), только на
её артефактной ветке (`git branch -a`: `remotes/origin/artifact/
01m1kt0792125j9znjnzj86e9q`, объекты уже в локальной базе этого клона —
ссылка НЕ требует сети). Второй тест ниже вытягивает её оттуда
`git archive` (адресно, без checkout — рабочее дерево этого клона не
трогается) во временный каталог поверх настоящего `tasks/
01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/` РЕАЛЬНОГО репозитория (не
подставного `_REPO_ROOT` — иначе `sys.path.insert(0, parents[3])` внутри
извлечённых файлов указал бы не туда, и `from orchestrator import ...`
внутри них не нашёл бы пакет), запускает и убирает за собой; если ссылки
в конкретном клоне нет — тест честно пропускается, а не лжёт зелёным.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

A7_ACCEPTANCE_TESTS = _REPO_ROOT / "tasks/01M1H224X5A8W159MKF1Q24R5Y/acceptance_tests"
HOTFIX_TASK = "01M1KT0792125J9ZNJNZJ86E9Q"
HOTFIX_REL = f"tasks/{HOTFIX_TASK}/acceptance_tests"
HOTFIX_REFS = (
    f"refs/heads/artifact/{HOTFIX_TASK.lower()}",
    f"refs/remotes/origin/artifact/{HOTFIX_TASK.lower()}",
)


def _discover(start_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(start_dir), "-q"],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=600)


def _resolve_hotfix_ref() -> str:
    for ref in HOTFIX_REFS:
        res = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                             cwd=_REPO_ROOT, capture_output=True, text=True)
        if res.returncode == 0:
            return ref
    return ""


class ExistingPlankasStayGreenTest(unittest.TestCase):

    def test_ac6_a7_planka_44_tests_stays_green(self):
        """`python3 -m unittest discover -s tasks/01M1H224X5A8W159MKF1Q24R5Y/
        acceptance_tests` (планка A7, каталог уже на диске этой ветки) —
        код 0, ровно 44 теста, ни одного `FAILED`.

        Ловит мутацию: правка `checkpoint.py`/`fsm_advance.py` этой
        задачи, ломающая существующее поведение планки A7 (например,
        фильтрация `.gitignore` случайно исключает и НЕигнорируемый
        файл) — `returncode` станет ненулевым, `stderr` понесёт
        `FAILED`, тест покраснеет.
        """
        self.assertTrue(A7_ACCEPTANCE_TESTS.is_dir(),
                        f"{A7_ACCEPTANCE_TESTS} обязан быть на диске")

        result = _discover(A7_ACCEPTANCE_TESTS)

        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertIn("Ran 44 tests", result.stderr)
        self.assertNotIn("FAILED", result.stderr)

    def test_ac6_hotfix_planka_stays_green(self):
        """Планка hotfix 01M1KT0792125J9ZNJNZJ86E9Q, вытянутая из
        собственной артефактной ветки во временный каталог, кладётся ПО
        РЕАЛЬНОМУ ПУТИ `tasks/01M1KT0792125J9ZNJNZJ86E9Q/acceptance_tests/`
        настоящего репозитория (`_REPO_ROOT`, не временная копия — иначе
        `parents[3]` внутри самих извлечённых тестов резолвился бы не в
        репозиторий, и `import orchestrator` внутри них падал бы ImportError
        по причине, не имеющей отношения к AC-6), прогоняется и убирается
        `addCleanup` независимо от исхода.

        Ловит мутацию: правка `checkpoint.py`/`fsm_advance.py` этой
        задачи, ломающая существующее поведение планки hotfix (например,
        сужение фильтра `.gitignore` задевает и её собственные проверки
        удаления артефактов, AC-6 hotfix) — `returncode` станет
        ненулевым, тест покраснеет.
        """
        ref = _resolve_hotfix_ref()
        if not ref:
            self.skipTest(
                "ни " + " ни ".join(HOTFIX_REFS) + " не резолвятся в этом "
                "клоне — планку hotfix взять неоткуда без сети")

        dest = _REPO_ROOT / "tasks" / HOTFIX_TASK
        self.assertFalse(dest.exists(),
                         f"{dest} уже существует — тест не имеет права "
                         "затирать чужое содержимое")
        self.addCleanup(shutil.rmtree, dest, True)

        archive = subprocess.run(
            ["git", "archive", ref, HOTFIX_REL], cwd=_REPO_ROOT,
            capture_output=True, timeout=60)
        self.assertEqual(archive.returncode, 0, archive.stderr.decode(errors="replace"))
        extract = subprocess.run(["tar", "-x"], cwd=_REPO_ROOT,
                                 input=archive.stdout, capture_output=True,
                                 timeout=60)
        self.assertEqual(extract.returncode, 0, extract.stderr.decode(errors="replace"))
        hotfix_dir = _REPO_ROOT / HOTFIX_REL
        self.assertTrue(hotfix_dir.is_dir(),
                        "git archive обязан был материализовать каталог")

        result = _discover(hotfix_dir)

        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertNotIn("FAILED", result.stderr)


if __name__ == "__main__":
    unittest.main()
