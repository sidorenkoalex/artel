"""AC-11 — отказ по AC-1, AC-2, AC-5, AC-8 оставляет задачу в
`tests_writing`, журнал несёт запись отказа с перечнем ошибок и подсказкой
«исправь файл и повтори»; после исправления файла повторный `advance`
проходит без `amend-tests`.

Группа: разовый
Красен до реализации: ни одна из четырёх проверок на выходе из `tests_writing` ещё не существует — первый же `advance` с нарушением уходит в `in_dev`, записи отказа с подсказкой нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import amend, store  # noqa: E402


class RefusalAndRetryTest(_sandbox.GroupPlankSandbox):

    def scenarios(self) -> dict[str, str]:
        """Нарушение каждого из четырёх критериев — один файл `test_ac.py`."""
        return {
            "AC-1 нет строки группы": _sandbox.plank_source(group=None),
            "AC-2 неизвестная группа": _sandbox.plank_source(
                raw_group_line="Группа: временный"),
            "AC-5 признак требования 3": _sandbox.plank_source(
                head=['sys.path.insert(0, "/nonexistent")']),
            "AC-8 метод без заявки": _sandbox.plank_source(claim=None),
        }

    def test_ac11_refusal_journalled_with_hint_then_fixed_file_passes(self):
        """Для каждого из четырёх нарушений: `advance` оставляет задачу в
        `tests_writing`, и за этот вызов в журнале появилась запись
        отказа, которая называет файл `test_ac.py` и несёт подсказку
        «исправь файл … повтори»; затем файл заменён чистой фикстурой —
        повторный `advance` уводит задачу в `in_dev`, а записи
        `amend-tests` («правка планки») в журнале нет.

        Ловит мутацию: ошибки новых проверок журналируются, но подсказка
        только печатается (`GateRefusal.hint` уходит в `print`, в журнал
        — лишь `detail`) — в записях журнала подсказки «исправь файл и
        повтори» нет.
        """
        clean = _sandbox.plank_source()
        for label, broken in self.scenarios().items():
            with self.subTest(scenario=label):
                self.write_plank({"test_ac.py": broken})
                out, refusals = self.advance()
                self.assertEqual(self.state(), "tests_writing",
                                 f"{label}: переход прошёл: {out!r}")
                with_hint = [text for text in refusals
                             if "test_ac.py" in text and _sandbox.HINT.search(text)]
                self.assertTrue(
                    with_hint,
                    f"{label}: нет записи отказа с файлом и подсказкой "
                    f"«исправь файл и повтори»: {refusals!r}")

                self.write_plank({"test_ac.py": clean})
                out, refusals = self.advance()
                self.assertEqual(self.state(), "in_dev",
                                 f"{label}: исправленный файл не прошёл: "
                                 f"{refusals!r} {out!r}")
                amended = [row for row in store.task_steps(store.db(), self.TASK)
                           if row["action"] == amend.AMEND_ACTION]
                self.assertEqual(amended, [])


if __name__ == "__main__":
    unittest.main()
