"""AC-14: строка «Назначение» `orchestrator/merge_after.py` в регенерированной карте.

Группа: разовый
Красен до реализации: docstring модуля orchestrator/merge_after.py и карта пока не называют ни «Порядок: после», ни заявленное значение, ни status — проверка состава строки «Назначение» краснеет; сверка «карта регенерирована» зелёная уже сейчас.

Карта и модуль читаются из рабочей копии кода задачи (`_pult.CODE_ROOT`).
«Регенерирована» — строка «Назначение» раздела модуля в карте совпадает с
тем, что из docstring того же модуля выводит генератор
(`scripts/codebase_map.py::extract_purpose`).

Валидация стабом: первая строка docstring `orchestrator/merge_after.py`
временно заменена на «Зависимости мержа `merge_after`: заявление при `new`
строкой ТЗ «Порядок: после», заявленное значение в колонке, сверка с ним на
гейте SPEC, добавка `status` до `acceptance`, проверки и отказ на гейте
мержа.» и карта перегенерирована — тесты позеленели; стаб снят.
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))

from scripts import codebase_map  # noqa: E402

MODULE = "orchestrator/merge_after.py"
MAP = "docs/codebase-map.md"
PURPOSE = "**Назначение:**"


def map_purpose() -> str | None:
    """Значение поля «Назначение» раздела `## orchestrator/merge_after.py`."""
    text = (Path(CODE_ROOT) / MAP).read_text(encoding="utf-8")
    section = re.search(rf"^## {re.escape(MODULE)}\n(.*?)(?=^## |\Z)", text,
                        re.M | re.S)
    if section is None:
        return None
    for line in section.group(1).splitlines():
        if line.startswith(PURPOSE):
            return line[len(PURPOSE):].strip()
    return None


class CodebaseMapPurposeTest(unittest.TestCase):

    def test_ac14_map_purpose_regenerated_from_module_docstring(self):
        """Строка «Назначение» карты совпадает с выводом генератора по docstring модуля.

        Сценарий: из `docs/codebase-map.md` берётся поле «Назначение»
        раздела `orchestrator/merge_after.py`, из модуля — первая строка
        docstring тем же `extract_purpose`, что зовёт генератор. Они равны.

        Ловит мутацию: docstring модуля поправлен, а карта не
        перегенерирована (или «Назначение» вписано в карту руками) —
        строки расходятся.
        """
        source = (Path(CODE_ROOT) / MODULE).read_text(encoding="utf-8")
        expected = codebase_map.extract_purpose(ast.parse(source))

        self.assertEqual(map_purpose(), expected)

    def test_ac14_map_purpose_names_declared_dependencies(self):
        """«Назначение» `merge_after.py` называет «Порядок: после», заявленное значение, гейт SPEC и `status`.

        Сценарий: поле «Назначение» раздела модуля в карте содержит
        «Порядок: после», слово «заявлен…», «гейт… SPEC» и `status`.

        Ловит мутацию: docstring дополнен только частью механики (например,
        сверкой на гейте SPEC без заявления при `new` или без добавки
        `status`) — строка не называет недостающее.
        """
        purpose = map_purpose()
        self.assertIsNotNone(purpose, f"в {MAP} нет «Назначение» {MODULE}")

        for pattern in (r"Порядок: после", r"заявлен", r"гейт\w*\s+SPEC",
                        r"status"):
            self.assertRegex(purpose, pattern, f"«Назначение»: {purpose}")


if __name__ == "__main__":
    unittest.main()
