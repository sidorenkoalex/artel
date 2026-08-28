"""AC-3 (tasks/T064/SPEC.md): задачи, уже вышедшие из состояния
`tests_writing`, этим правилом не затрагиваются — их переходы и
повторные прогоны guard по этому признаку не отклоняются, существующие
каталоги `acceptance_tests/` задним числом не проверяются и не
правятся.

Зелёный с рождения: проверка маркера красноты (SPEC требования 1-2)
включается ТОЛЬКО в месте выхода из `tests_writing`
(`orchestrator/fsm.py::_tests_writing_ac_state`, тот же вызов, что и
трассируемость AC -> тест из T023) — она структурно не может задеть
задачу, чьё состояние уже прошло `tests_writing`, потому что этот код
просто не выполняется для других переходов FSM. Этот тест ставит
задачу СРАЗУ в `review` (минуя `tests_writing`) с каталогом
`acceptance_tests/`, в котором маркера нет вовсе, и проверяет, что
переход `review -> acceptance` (существующий механизм прогона
приёмочных тестов, T023 требование 6) по этому основанию не
отклоняется. Верно уже сегодня (проверки маркера ещё нет вообще) и
обязано остаться верным после реализации T064 — красный прогон здесь
означал бы, что новая проверка ошибочно расширена на переходы, для
которых SPEC её не предусматривает (регресс, не прогресс задачи).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import AC_TEST_NO_MARKER, TmpRootTest  # noqa: E402


class LegacyTaskNotRecheckedTest(TmpRootTest):

    def test_ac3_review_transition_not_blocked_by_missing_marker(self):
        # Задача заведена сразу в `review` — `tests_writing` для неё уже
        # позади (симулирует задачу, чей выход из tests_writing состоялся
        # до появления этой проверки, SPEC требование 4).
        self.enter_review()
        self.write_acceptance_tests(AC_TEST_NO_MARKER, name="test_ac.py")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "acceptance",
            "задача уже прошла tests_writing — отсутствие маркера в "
            "acceptance_tests/test_ac.py не имеет права заблокировать "
            "ПОСЛЕДУЮЩИЙ переход review -> acceptance (SPEC AC-3); "
            "вывод команды: " + out)
