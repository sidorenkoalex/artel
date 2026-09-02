"""AC-2 (tasks/01M1H186VEVG6NF40YKH1338MD/SPEC.md): содержимое
tasks/<id>/acceptance_tests/ без образца формата идентификатора задачи
не вызывает отказа перехода tests_writing -> in_dev по этому
основанию — переход происходит как прежде.

Зелёный с рождения: сценарий «нет образца формата идентификатора ->
переход не блокируется по этому основанию» верен уже сегодня (до
реализации этой задачи такой проверки просто нет вовсе, значит она и
не блокирует) и обязан остаться верным после реализации (SPEC
требования 1-2 добавляют отказ только для НАЛИЧИЯ образца, не для его
отсутствия). Тест не должен ни разу покраснеть в ходе реализации —
красный прогон здесь означал бы, что разработчик реализовал проверку
шире, чем требует AC-2 (регресс, не прогресс).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import fsm  # noqa: E402

from _sandbox import AC_TEST_CLEAN, TmpRootTest  # noqa: E402


class NoIdFormatSampleDoesNotBlockTest(TmpRootTest):

    def test_ac2_content_without_sample_advances_as_before(self):
        """Чистое содержимое (без образца) проходит переход как прежде.
        
        Ловит мутацию: разработчик делает образец слишком широким
        (например, ловит любые «{3}») — проверка ложно сработает на
        чистом файле и переход не пройдёт.
        """
        self.enter_tests_writing()
        self.write_acceptance_tests(AC_TEST_CLEAN, name="test_ac.py")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "in_dev",
            "содержимое acceptance_tests/test_ac.py не несёт образца "
            "формата идентификатора задачи — переход обязан пройти как "
            "прежде (SPEC AC-2)")
