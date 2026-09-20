"""AC-6 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): `advance` на выходе
`tests_writing` при непустом результате проверки отклоняет переход — в
журнале действие «переход отклонён: планка читает артефакты с диска», в
`detail` текст ошибок, задача остаётся в `tests_writing`.

Красен до реализации: гейт ещё не подключён к выходу `tests_writing` —
`advance` вложенной песочницы уводит задачу в `in_dev`, записи журнала с
этим действием нет ни одной.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class AdvanceRefusesDiskReadingPlankTest(_sandbox.ArtifactSourcePlankSandbox):

    def test_ac6_refusal_is_journalled_and_task_stays_in_tests_writing(self):
        """Выход из `tests_writing` с планкой, читающей `PLAN.md` с
        диска: в журнале ровно одна запись с действием «переход отклонён:
        планка читает артефакты с диска», её `detail` несёт текст ошибок
        проверки (файл планки и рецепт), тот же текст печатается, а
        состояние задачи остаётся `tests_writing`.

        Ловит мутацию: отказ проверки только печатается (или
        журналируется под общим действием «переход отклонён», как
        исторический отказ свежести вердикта), а переход продолжается к
        `store.set_state(..., "in_dev", ...)` — `self.state()` окажется
        `in_dev`, а выборка журнала по точному действию — пустой.
        """
        self.enter_tests_writing()
        source = _sandbox.plank_source([_sandbox.DISK_READ_LINE])
        self.write_plank(source)

        out = self.advance()

        self.assertEqual(self.state(), "tests_writing")
        details = self.refusal_details()
        self.assertEqual(
            len(details), 1,
            f"ожидалась ровно одна запись «{_sandbox.REFUSAL_ACTION}»; "
            f"вывод advance: {out!r}")
        self.assertIn("test_ac.py", details[0])
        self.assertIn(_sandbox.RECIPE_HEAD, details[0])
        self.assertIn(details[0], out)


if __name__ == "__main__":
    unittest.main()
