"""Приёмочный тест AC-7 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z: подсказка
`zones-extend` при отсутствующем/несовпадающем разделе «## Расширение
зон» PLAN.md называет командой продолжения `artel.py auto <id>`.

Красен до реализации: `orchestrator/answer.py::_cmd_zones_extend`
печатает сегодня только «... раздел «Расширение зон» PLAN.md не совпадает
с переданными путями — zones_extension не изменён» (answer.py:227-229),
без единой следующей команды — оба теста ветки несовпадения падают на
отсутствии строки `artel.py auto <id>`. Зелёный с рождения —
`test_ac7_matching_plan_section_still_updates_zones_extension`: он
фиксирует вторую половину критерия («обновление `zones_extension` в БД
по-прежнему происходит только при совпадении»), которую задача не меняет.

Через CLI (`artel.main()` с подменённым `sys.argv`), не через прямой
вызов внутренней функции — критерий называет именно командную форму
`artel.py zones-extend <id> <пути>` (тот же приём, что у планки
01M287TPG0HAVXS8CHBCY679WN, где эта команда заводилась).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel  # noqa: E402
from tests.sandbox import capture  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import OUT_OF_ZONE_PATH, ZonesMandateSandbox  # noqa: E402


class Ac7ZonesExtendNamesAutoAsTheNextCommandTest(ZonesMandateSandbox):
    """AC-7."""

    def run_zones_extend(self, paths_arg: str) -> str:
        argv = ["artel.py", "zones-extend", self.TASK, paths_arg]
        with mock.patch.object(sys, "argv", argv):
            return capture(artel.main)

    def assert_names_auto(self, out: str) -> None:
        self.assertIn(
            f"artel.py auto {self.TASK}", out,
            f"подсказка не называет команду продолжения `artel.py auto "
            f"{self.TASK}` — Оператор остаётся без следующего шага, ровно "
            f"как 13.09:\n{out}")

    def test_ac7_missing_plan_section_names_auto_as_the_next_command(self):
        """Раздела «## Расширение зон» в PLAN.md нет вовсе — команда
        печатает подсказку с `artel.py auto <id>`, а `zones_extension` в
        БД не меняется.

        Ловит мутацию: подсказка добавлена в ветку СОВПАДЕНИЯ (где
        продолжение и так очевидно), а ветка несовпадения — та самая, что
        оставила Оператора без следующей команды 13.09, — осталась без
        неё.
        """
        before = self.row()["zones_extension"]

        out = self.run_zones_extend(OUT_OF_ZONE_PATH)

        self.assert_names_auto(out)
        self.assertEqual(self.row()["zones_extension"], before,
                         "zones_extension обновлён без совпадающего раздела "
                         "PLAN.md — вторая половина AC-7 нарушена")

    def test_ac7_mismatching_plan_section_names_auto_as_the_next_command(self):
        """Раздел «## Расширение зон» в PLAN.md есть, но его строка
        `Пути:` называет другой путь — та же подсказка с `artel.py auto
        <id>`, `zones_extension` по-прежнему не меняется.

        Ловит мутацию: подсказка печатается только при ПОЛНОСТЬЮ
        отсутствующем разделе (`plan_paths is None`), а несовпадение
        путей по-прежнему заканчивается тупиком без следующей команды.
        """
        self.commit_plan(extension_paths="docs/another_module.md")
        before = self.row()["zones_extension"]

        out = self.run_zones_extend(OUT_OF_ZONE_PATH)

        self.assert_names_auto(out)
        self.assertEqual(self.row()["zones_extension"], before)

    def test_ac7_matching_plan_section_still_updates_zones_extension(self):
        """Раздел PLAN.md совпадает с переданными путями — `zones_extension`
        обновляется, как и до задачи: вторая половина критерия («только
        при совпадении раздела PLAN с переданными путями»).

        Ловит мутацию: добавляя подсказку, ветки совпадения и
        несовпадения слили в одну и обновление `zones_extension` стало
        безусловным — мандат Оператора начал бы расширять зону в обход
        раздела PLAN, то есть в обход самого условия, ради которого
        сверка и заведена.
        """
        self.commit_plan(extension_paths=OUT_OF_ZONE_PATH)

        self.run_zones_extend(OUT_OF_ZONE_PATH)

        self.assertEqual(self.row()["zones_extension"], OUT_OF_ZONE_PATH)


if __name__ == "__main__":
    unittest.main()
