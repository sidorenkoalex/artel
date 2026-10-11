"""Приёмочные тесты T034: AC-6 — патчеры `serve()` внутри subTest-цикла.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 4
(ревью T018): `tests/test_ci_status.py`, `PaginationTest.serve()` заводит
патчи `mock.patch.object(...).start()` и снимает их только через
`self.addCleanup`, который выполняется в конце ВСЕГО тестового метода —
а не в конце каждой итерации `subTest`, вызывающей `serve()` заново
(например, `test_an_unreadable_total_count_is_unknown_and_not_green`,
три итерации). Патчи от предыдущих итераций остаются активными, пока не
кончится метод целиком, вместо того чтобы сняться до следующей.

Проверяется буквально то же, что называет критерий: число АКТИВНЫХ
патчей `unittest.mock` (`mock._patch._active_patches` — общий для
процесса реестр, который `start()`/`stop()` пополняют и опустошают)
не должно расти от одного вызова `serve()` к другому внутри того же
теста.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tests import test_ci_status  # noqa: E402


class Ac6SerdePatchesDoNotAccumulateTest(unittest.TestCase):
    """AC-6: число активных патчей не растёт от итерации к итерации."""

    def active_patch_count(self) -> int:
        return len(mock._patch._active_patches)

    def test_ac6_two_serve_calls_in_a_row_leave_the_same_number_of_active_patches(self):
        tc = test_ci_status.PaginationTest(
            "test_a_page_shorter_than_promised_is_unknown_and_not_green")
        tc.setUp()
        self.addCleanup(tc.doCleanups)

        tc.serve([[]], total=0)
        tc.status()
        after_first = self.active_patch_count()

        tc.serve([[]], total=0)
        tc.status()
        after_second = self.active_patch_count()

        self.assertEqual(
            after_second, after_first,
            f"патчи serve() копятся от итерации к итерации: было "
            f"{after_first} активных после первого вызова, "
            f"{after_second} — после второго (не остановлены до tearDown "
            f"класса, SPEC T034 требование 4)")

    def test_ac6_patches_are_still_fully_cleaned_up_after_the_test(self):
        """Смежная гарантия: снятие per-итерацию не оставляет утечки —
        к концу теста активных патчей не больше, чем было до него."""
        tc = test_ci_status.PaginationTest(
            "test_a_page_shorter_than_promised_is_unknown_and_not_green")
        before = self.active_patch_count()
        tc.setUp()

        tc.serve([[]], total=0)
        tc.status()
        tc.serve([[]], total=0)
        tc.status()
        tc.doCleanups()

        self.assertEqual(self.active_patch_count(), before,
                         "патчи не сняты полностью после теста — утечка "
                         "в другие тесты процесса")


if __name__ == "__main__":
    unittest.main()
