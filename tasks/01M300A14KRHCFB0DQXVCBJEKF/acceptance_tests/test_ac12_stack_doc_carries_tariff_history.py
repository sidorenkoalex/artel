"""AC-12 — 01M300A14KRHCFB0DQXVCBJEKF: раздел `docs/stack.md` «Модели:
каталог, ярусы, тариф» несёт тариф и историю тарифов.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Раздел `docs/stack.md` «Модели: каталог, ярусы, тариф» несёт тариф
и историю тарифов: что делает Оператор при смене цен и где живёт
`model_tariffs`.

Проверяется именно раздел, а не файл целиком: упоминание таблицы в любом
другом месте документа критерию не отвечает — Оператор читает про модели
и тариф здесь.

Красен до реализации: раздел существует (заведён частью 1 линии,
`docs/stack.md:70`), но слова `model_tariffs` в нём нет — истории
тарифов на момент его написания не существовало.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tariff  # noqa: E402

SECTION_TITLE = "## Модели: каталог, ярусы, тариф"
TABLE = "model_tariffs"


def _section_body(text: str, title: str) -> str | None:
    """Тело раздела markdown от его заголовка до следующего заголовка
    того же уровня; `None` — раздела нет."""
    start = text.find(f"{title}\n")
    if start < 0:
        return None
    rest = text[start + len(title):]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


class StackDocDescribesTariffHistoryTest(unittest.TestCase):

    def test_ac12_models_section_names_the_tariff_history_table(self):
        """Раздел про модели называет таблицу `model_tariffs` и говорит
        о смене цен Оператором.

        Ловит мутацию: история тарифов заведена в коде и схеме, но в
        документе не описана — Оператор, меняющий цены, не знает ни что
        при этом происходит само, ни где смотреть прошлые тарифы, и
        первая же сверка расхода упирается в таблицу, о которой нигде не
        сказано.
        """
        doc = (_tariff.REPO_ROOT / "docs" / "stack.md").read_text(
            encoding="utf-8")

        body = _section_body(doc, SECTION_TITLE)

        self.assertIsNotNone(
            body, f"в docs/stack.md нет раздела «{SECTION_TITLE}»")
        self.assertIn(TABLE, body)
        self.assertIn("истори", body.lower())
        self.assertIn("цен", body.lower())


if __name__ == "__main__":
    unittest.main()
