"""Строка контракта сессии о повторной красноте полного набора.

Группа: разовый
Красен до реализации: в `docs/operator-session.md` рабочей копии строки «одни и те же тесты красные два прогона подряд — …» нет.

Документ читается из рабочей копии кода (`CODE_ROOT` помощника пульта) —
это файл кода задачи (`docs/`), не артефакт `tasks/<id>/`.

Остальные критерии SPEC держат долгоживущие файлы задачи в `tests/`:
AC-1, AC-2, AC-3 — `test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py`;
AC-4, AC-5, AC-6, AC-10 — `test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py`;
AC-7, AC-8, AC-12 — `test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`.
"""

# AC-11: manual — полный набор tests/ в одном тесте не укладывается в предел прогона планки (config.ACCEPTANCE_TIMEOUT_SEC = 300 с на всю планку и 120 с на тест; у полного набора свой предел config.FULL_SUITE_TIMEOUT_SEC = 900 с). Поэтому детерминированно проверить «полный набор на чистом дереве не оставляет .artel/state.db» внутри планки нельзя. Проверка на приёмке: после полного прогона гейта на рабочей копии задачи файла .artel/state.db в ней нет, и в журнале задачи нет записи «прогон набора создал файл БД — неполная изоляция тестов» (требование 4, AC-10).

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

DOC = Path(CODE_ROOT) / "docs" / "operator-session.md"
LINE = ("одни и те же тесты красные два прогона подряд — не случайный сбой: "
        "сравнить с чистым клоном и проверить игнорируемые файлы рабочей "
        "копии")
FIRST_ITEM = "Что проверяет приёмка"
SECOND_ITEM = "Красный набор не по вине задачи"


def normalized(text: str) -> str:
    """Текст без переносов строк Markdown и без регистра: пробелы схлопнуты
    в один — строка вправе начинать предложение с заглавной буквы."""
    return " ".join(text.split()).casefold()


class OperatorSessionDocTest(unittest.TestCase):

    def test_ac9_repeated_red_line_in_full_suite_block(self):
        """Строка требования 7 стоит в блоке о красном полном наборе приёмки.

        Сценарий: из `docs/operator-session.md` берётся участок от пункта
        «Что проверяет приёмка» до конца пункта, следующего за «Красный
        набор не по вине задачи» (строка может стать частью одного из этих
        пунктов или отдельным пунктом сразу за ними). В участке, с точностью
        до переносов строк и регистра, есть фраза «одни и те же тесты красные два
        прогона подряд — не случайный сбой: сравнить с чистым клоном и
        проверить игнорируемые файлы рабочей копии».

        Ловит мутацию: строка добавлена в другой раздел документа (например
        в «Уроки») либо без второй половины про игнорируемые файлы — в
        участке блока полной фразы нет.
        """
        text = DOC.read_text(encoding="utf-8")
        start = text.find(FIRST_ITEM)
        self.assertNotEqual(start, -1, f"{DOC}: нет пункта «{FIRST_ITEM}»")
        second = text.find(SECOND_ITEM, start)
        self.assertNotEqual(second, -1, f"{DOC}: нет пункта «{SECOND_ITEM}»")
        # Конец участка — начало второго пункта списка после «Красный набор
        # …» (первый — возможная новая строка требования 7) либо заголовок.
        end = second
        for _ in range(2):
            bullet = text.find("\n- ", end + 1)
            heading = text.find("\n#", end + 1)
            stops = [i for i in (bullet, heading) if i != -1]
            end = min(stops) if stops else len(text)
            if end == heading:
                break
        block = normalized(text[start:end])
        self.assertIn(normalized(LINE), block,
                      f"{DOC}: в блоке «{FIRST_ITEM}» / «{SECOND_ITEM}» нет "
                      f"строки требования 7:\n{block}")


if __name__ == "__main__":
    unittest.main()
