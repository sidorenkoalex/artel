"""AC-12 — область проверок: внешний target (≠ `config.DEFAULT_TARGET`)
на выходе из `tests_writing` отказа по новым проверкам не получает;
канареечная задача target `artel` проверяется как обычная.

Target внешней задачи и признак канарейки ставятся строкой БД вложенной
задачи — та же задача, те же файлы, меняется только область.

Группа: разовый
Красен до реализации: контроль (та же планка у задачи target `artel`) и канареечная задача требуют отказа, а новых проверок на выходе из `tests_writing` ещё нет — обе уходят в `in_dev`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

EXTERNAL_TARGET = "sled"


class ScopeTargetsTest(_sandbox.GroupPlankSandbox):

    def violating_plank(self) -> dict[str, str]:
        """Файл без строки группы и долгоживущий файл с признаками
        требования 3 и методом без «Ловит мутацию»."""
        return {
            "test_no_group.py": _sandbox.plank_source(group=None),
            "test_long.py": _sandbox.plank_source(
                group=_sandbox.GROUP_LONG, claim=None,
                head=['NOTE = "каталог tasks/ пульта"',
                      'sys.path.insert(0, "/nonexistent")',
                      "import _sandbox  # noqa: F401"],
                body=["value = store._private_value"]),
        }

    def test_ac12_external_target_is_not_checked(self):
        """Та же нарушающая планка: у задачи target `artel` — отказ
        (контроль), у той же задачи с target `sled` — переход в `in_dev`
        без записи отказа.

        Ловит мутацию: условие области написано по признаку «не
        канарейка» вместо «target == config.DEFAULT_TARGET» (или не
        написано вовсе) — задача внешнего target отклоняется, остаётся в
        `tests_writing`.
        """
        self.assertNotEqual(EXTERNAL_TARGET, _sandbox.default_target())
        self.assert_refused_naming(self.violating_plank(), "test_no_group.py",
                                   why="контроль: та же планка у target artel")
        self.set_target(EXTERNAL_TARGET)
        self.assert_passes(self.violating_plank(),
                           why=f"задача внешнего target {EXTERNAL_TARGET}")

    def test_ac12_canary_task_of_artel_is_checked(self):
        """Канареечная задача target `artel` с файлом без строки группы —
        отказ перехода с именем файла, как у обычной.

        Ловит мутацию: канареечные задачи исключены из новых проверок тем
        же условием, что `_origin_push_gate`/`_mutation_claim_gate`
        (`if t["is_canary"]: return None`) — канареечная задача уходит в
        `in_dev`.
        """
        self.set_canary()
        self.assert_refused_naming(
            {"test_no_group.py": _sandbox.plank_source(group=None)},
            "test_no_group.py", why="канареечная задача target artel")


if __name__ == "__main__":
    unittest.main()
