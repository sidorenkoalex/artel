"""AC-20 — у задачи внешнего target и у задачи со `skip_tests` перечня
нет и сверки перечня нет: их переходы ведут себя как до задачи.

Внешний target: кодовая ветка несёт и долгоживущий файл с префиксом, и
правку файла базы `tests/`; выход из `tests_writing` проходит, в дереве
коммита лока перечня нет. `skip_tests`: `tests_writing` задача не
проходит вовсе (лока нет); кодовая ветка несёт долгоживущий файл с
префиксом, и рубежи Р4 проходят без перечня.

Группа: разовый
Зелёный с рождения: сегодня ни перечня, ни сверки нет ни у одной задачи — файл сторожит, что реализация не распространит их на внешний target и на задачу со `skip_tests` (например, отказом «перечня нет» на `in_dev -> verifying`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

EXTERNAL_TARGET = "outer-fixture"


class ExternalTargetScopeTest(_sandbox.LongLivedSandbox):

    def test_ac20_external_target_writes_no_manifest_and_keeps_old_gate(self):
        """Задача внешнего target: кодовая ветка добавила долгоживущий файл
        с префиксом и правит `tests/test_existing.py` базы. Выход из
        `tests_writing` проходит (гейта «только добавление» для неё нет),
        и перечня в дереве коммита лока нет.

        Ловит мутацию: область правила проверяется по признаку
        канареечности или не проверяется вовсе, а не по target — внешняя
        задача получает отказ за правку файла базы и перечень.
        """
        self.set_row(target=EXTERNAL_TARGET)
        existing = "tests/test_existing.py"
        self.wt_commit({
            self.ll_path("alpha"): _sandbox.long_lived_source(),
            existing: self.branch_text(existing) + "# правка\n",
        })
        out, entries = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev",
                         f"выход внешней задачи отклонён: {entries!r}\n{out}")
        self.assertIsNone(self.manifest_at_lock(),
                          "у задачи внешнего target записан перечень")


class SkipTestsScopeTest(_sandbox.LongLivedSandbox):

    SPEC_EXTRA = "skip_tests: вложенная песочница без планки\n"
    WITH_PLANK = False

    def test_ac20_skip_tests_task_passes_boundaries_without_manifest(self):
        """Задача со `skip_tests` в `in_dev` без лока и без перечня; кодовая
        ветка несёт долгоживущий файл с префиксом. `in_dev -> verifying`,
        `verifying -> review` проходят, тело гейта мержа доходит до
        ожидания CI.

        Ловит мутацию: узел сверки трактует отсутствие перечня как
        расхождение («перечень не найден — отказ») без оглядки на
        `skip_tests` — задача встаёт на `in_dev`.
        """
        self.wt_commit({self.ll_path("alpha"): _sandbox.long_lived_source()})
        self.set_row(tests_locked_sha=None)
        for name, call, target_state in (
                ("in_dev -> verifying", self.advance_in_dev, "verifying"),
                ("verifying -> review", self.advance_verifying, "review")):
            with self.subTest(boundary=name):
                out, entries = call()
                self.assertEqual(self.state(), target_state,
                                 f"{name}: задача со skip_tests отклонена: "
                                 f"{entries!r}\n{out}")
        outcome, out, entries = self.merge_gate_body()
        self.assertEqual(outcome[0] if outcome else None, "wait",
                         f"гейт мержа задачи со skip_tests остановлен: "
                         f"{entries!r}\n{out}")


if __name__ == "__main__":
    unittest.main()
