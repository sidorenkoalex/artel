"""AC-6 — 01M2DC6SQVSANMECXPDZJDP75D: диф кода ветки задачи не содержит
правок `tests/test_invariants.py`.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Диф кода ветки задачи не содержит правок `tests/test_invariants.py`;
группы `setUp` `:439/733` и `:635/1420` этого файла не изменены.

Если файл целиком отсутствует среди изменённых путей диффа ветки задачи
относительно `main` — ни одна его строка, включая обе защищённые группы
`setUp` (`:439/733` — `MergeOnlyFromMergeGateTest`/`AgentRunsOnlyFromRunTest`,
байтово идентичные тела; `:635/1420` — `MergeNeedsGreenCiTest`/
`ManualGatesNeedTheOperatorTest`, тоже байтово идентичные), тривиально не
изменена — вторая половина критерия не нуждается в отдельной проверке
диапазонов строк (она была бы чистым логическим подмножеством первой,
без дополнительной ловящей силы).

Зелёный с рождения: задача ещё не тронула ни одной строки
`tests/test_invariants.py` (ветка только что заведена от `main`), диф
пуст уже сейчас. Ловит мутацию (стаб не нужен — сам механизм проверен на
чужом прецеденте, `tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/
test_ac4_invariants_diff_attachment.py::TaskBranchDoesNotTouchTestInvariantsTest`,
байт-в-байт тот же приём): тест покраснеет РОВНО тогда, когда чей-то диф
случайно (или намеренно, в обход запрета SPEC «Не входит») коснётся
этого файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

TARGET_FILE = "tests/test_invariants.py"


class TaskBranchDoesNotTouchTestInvariantsTest(unittest.TestCase):

    def test_ac6_task_branch_diff_does_not_touch_test_invariants(self):
        """Диф ветки задачи (от точки расхождения с `main` до текущего
        рабочего дерева, включая незакоммиченное) не называет
        `tests/test_invariants.py` среди изменённых путей.

        Ловит мутацию: разработчик правит `tests/test_invariants.py`
        напрямую в коде ветки (например, чтобы «заодно» унести и его
        `setUp` в базовый класс, хотя SPEC «Не входит» это прямо
        запрещает) — файл появится в списке изменённых путей, и
        `assertNotIn` покраснеет.
        """
        changed = _util.changed_paths_since_main()
        self.assertNotIn(
            TARGET_FILE, changed,
            f"{TARGET_FILE} не должен меняться в дифе кода ветки задачи "
            f"— защищённый путь, AC-6")


if __name__ == "__main__":
    unittest.main()
