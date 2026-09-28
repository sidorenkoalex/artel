"""AC-18 — гейт мержа после `_sync_main_or_wait` сверяет и нынешний лок
каталога приёмочных тестов: файл планки, изменённый в ветке документов
после лока, и сбой git в этой сверке останавливают тело гейта раньше
ожидания CI.

Группа: разовый
Красен до реализации: тело гейта мержа сегодня лок каталога не сверяет — правленая после лока планка и недостижимый `tests_locked_sha` доходят до ожидания CI (`("wait", …)`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class MergeGateLockTest(_sandbox.LongLivedSandbox):

    def setUp(self):
        super().setUp()
        self.lock_with({})

    def test_ac18_plank_edited_after_lock_stops_merge_gate(self):
        """После лока файл `acceptance_tests/test_ac1_plank.py` правится
        коммитом в ветку документов. Тело гейта мержа — `("stopped",)`, и
        текст отказа называет лок приёмочных тестов. Контроль: без правки
        тело доходит до ожидания CI.

        Ловит мутацию: на гейте мержа зовётся только сверка перечня
        долгоживущих файлов, а `_acceptance_lock_refuses` — нет: правленая
        планка доходит до ожидания CI.
        """
        with self.subTest(scenario="контроль"):
            outcome, out, entries = self.merge_gate_body()
            self.assertEqual(outcome[0] if outcome else None, "wait",
                             f"без правки гейт остановлен: {entries!r}\n{out}")
        self.artifact_commit(
            {"acceptance_tests/test_ac1_plank.py":
             _sandbox.plank_source(methods=("test_ac1_plank_fixture",
                                            "test_ac1_extra"))},
            "правка планки после лока")
        outcome, out, entries = self.merge_gate_body()
        text = "\n".join(entries + [out])
        self.assertEqual(outcome, ("stopped",),
                         f"правленая планка прошла гейт мержа: {outcome!r} {text}")
        self.assertIn("лок", text)

    def test_ac18_git_failure_in_lock_check_stops_merge_gate(self):
        """`tests_locked_sha` указывает на коммит, которого нет в
        репозитории (git не отвечает на сверку): тело гейта мержа —
        `("stopped",)`, не проход.

        Ловит мутацию: `names is None` от `gitcmd.diff_names` на гейте
        мержа трактуется как «расхождений нет» — тело доходит до ожидания
        CI.
        """
        self.set_row(tests_locked_sha="0" * 40)
        outcome, out, entries = self.merge_gate_body()
        self.assertEqual(outcome, ("stopped",),
                         f"сбой git в сверке лока пропущен: {outcome!r} "
                         f"{entries!r}\n{out}")


if __name__ == "__main__":
    unittest.main()
