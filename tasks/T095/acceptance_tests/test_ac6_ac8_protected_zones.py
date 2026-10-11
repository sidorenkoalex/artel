"""AC-6 и AC-8 (tasks/T095/SPEC.md) — защищённые зоны не затронуты.

AC-6: «если способ — запись в журнал по завершении шага (вариант 4б):
изменения не затрагивают catalog/store-ядро, fsm-фиксации,
ветко-чтения, guard, coldstart, canary».
AC-8: «изменения задачи не выходят за зоны agent_log.py, report.py и
(только при варианте 4б) точки завершения шага; catalog/store-ядро,
fsm-фиксации, ветко-чтения, guard, coldstart, canary не затронуты».

Оба критерия называют один и тот же список защищённых систем — он не
зависит от того, какой из двух вариантов (4а/4б) выбрал разработчик
(SPEC требование 4, AC-7): даже если выбран 4б, эти конкретные файлы
всё равно не вправе быть тронуты, а если выбран 4а — тем более (AC-6
формально условие «если 4б», но список защищённых имён у AC-6 и AC-8 —
подмножество друг друга, и он неизменен независимо от условия). Отсюда
— один и тот же прямой тест-инвариант на оба критерия, по образцу
`tasks/T092/acceptance_tests/test_ac12_diff_does_not_touch_protected_modules.py`
(реальный `git diff` ветки задачи относительно `main`, без единого
мока).

Список файлов — прямое соответствие именам зон SPEC/ТЗ (docs/
codebase-map.md, поиск по назначению модуля):
- catalog/store-ядро → `orchestrator/catalog.py`, `orchestrator/store.py`
- fsm-фиксации → `orchestrator/fsm.py` и семейство `fsm_*.py`,
  `orchestrator/fixation.py` (hash-фиксация артефактов на переходах FSM)
- ветко-чтения → `orchestrator/gitcmd.py` (см. `tests/
  test_gitcmd_branch_reads.py`, `tests/test_fsm_branch_correct_status_reads.py`)
- guard → `scripts/guard.py`
- coldstart → `orchestrator/coldstart.py`
- canary → `orchestrator/canary.py`

AC-8 несёт ещё и позитивный список («изменения НЕ ВЫХОДЯТ ЗА зоны
agent_log.py/report.py [+точка завершения шага при 4б]») — то, что
конкретный ДОПОЛНИТЕЛЬНЫЙ файл для точки завершения шага при выборе
4б является ИМЕННО точкой завершения шага (а не расползанием вовне),
сверяется по PLAN.md разработчика на приёмке (текст ещё не
существующего документа, тот же случай, что `tasks/T062/
acceptance_tests/test_ac6_ac7_ac8_manual_criteria.py` — часть критерия
без готового текста PLAN.md проверяется Оператором чтением диффа против
заявленного там выбора); список protected-файлов ниже — та часть AC-8,
что верна независимо от текста PLAN.md.

Зелёный с рождения: на момент написания этих тестов ветка задачи несёт
только SPEC/тесты — ни один защищённый файл ещё не тронут; проверка
обязана остаться зелёной и после реализации (инвариант диффа, не
временное состояние).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

PROTECTED_FILES = (
    "orchestrator/catalog.py",
    "orchestrator/store.py",
    "orchestrator/fsm.py",
    "orchestrator/fsm_advance.py",
    "orchestrator/fsm_autogate.py",
    "orchestrator/fsm_merge_gate.py",
    "orchestrator/fsm_postmerge.py",
    "orchestrator/fixation.py",
    "orchestrator/gitcmd.py",
    "scripts/guard.py",
    "orchestrator/coldstart.py",
    "orchestrator/canary.py",
)


def _git(*args: str) -> str:
    res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def _branch_diff_files():
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "main":
        return None
    merge_base = _git("merge-base", "main", branch)
    return _git("diff", "--name-only", merge_base, branch).splitlines()


class ProtectedZonesUntouchedTest(unittest.TestCase):

    def test_ac6_protected_zones_untouched_regardless_of_variant(self):
        changed = _branch_diff_files()
        if changed is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [p for p in changed if p in PROTECTED_FILES]
        self.assertEqual(
            offending, [],
            f"дифф ветки трогает защищённые этой задачей (и T094) "
            f"файлы: {offending}")

    def test_ac8_protected_zones_untouched(self):
        changed = _branch_diff_files()
        if changed is None:
            self.skipTest("рабочее дерево на main — диффить не с чем")
        offending = [p for p in changed if p in PROTECTED_FILES]
        self.assertEqual(
            offending, [],
            f"дифф ветки трогает защищённые этой задачей (и T094) "
            f"файлы: {offending}")


if __name__ == "__main__":
    unittest.main()
