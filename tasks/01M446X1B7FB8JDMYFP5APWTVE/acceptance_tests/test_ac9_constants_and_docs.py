"""Константы дозора хода шага в `orchestrator/config.py` и их описание в сессии Оператора.

Группа: разовый
Красен до реализации: констант `WATCH_PROGRESS_PERIOD_MIN`/`WATCH_NO_COMMIT_WARN_SEC`/`WATCH_STEP_COST_WARN_USD`/`WATCH_PROGRESS_LINES_PER_HOUR` в `config` нет, а `docs/operator-session.md` не называет строк «ход шага»/«предупреждение», действия «прогон pytest» и границы строк в час.

Значения констант — решение этой задачи, которое Оператор вправе
повернуть позже (SPEC, «Материалы»): поэтому файл разовый, а
долгоживущие тесты задачи (`tests/test_<префикс задачи>_*.py`) берут
значения от `config`, не литералами. Остальные критерии (AC-1..AC-8)
покрыты этими долгоживущими файлами.

Документ читается из кода ветки (`config.ROOT / "docs"`), не из
каталога документов задачи.
"""
import re
import unittest
from pathlib import Path

from orchestrator import config

EXPECTED = {
    "WATCH_PROGRESS_PERIOD_MIN": 10,
    "WATCH_NO_COMMIT_WARN_SEC": 2100,
    "WATCH_STEP_COST_WARN_USD": 5.0,
    "WATCH_PROGRESS_LINES_PER_HOUR": 16,
}


class Ac9ConstantsAndDocsTest(unittest.TestCase):

    def test_ac9_constants_declared_in_config_with_spec_values(self):
        """Четыре константы объявлены присваиванием в `orchestrator/config.py`
        и несут значения SPEC: 10 минут, 2100 с, 5.0 $, 16 строк.

        Ловит мутацию: константа заведена в `watch.py` (или присвоена
        `config` извне), а не объявлена в `config.py` — объявления в тексте
        модуля нет; значение перепутано (например, 35 вместо 2100 с — порог
        в минутах) — сверка значения покраснеет.
        """
        source = Path(config.__file__).read_text(encoding="utf-8")
        for name, value in EXPECTED.items():
            with self.subTest(name=name):
                self.assertRegex(source, rf"(?m)^{name}\s*(:[^=\n]*)?=",
                                 f"{name} не объявлена в orchestrator/config.py")
                self.assertEqual(getattr(config, name, None), value, name)

    def test_ac9_operator_session_describes_pytest_class_lines_and_limit(self):
        """`docs/operator-session.md` описывает класс `pytest` (действие
        «прогон pytest»), строки «ход шага» и «предупреждение» и границу
        строк в час.

        Ловит мутацию: описание добавлено только в докстринг `watch.py`, а
        документ сессии Оператора не тронут — ни «ход шага», ни
        «предупреждение», ни «в час» в нём не найдутся; описана граница без
        класса `pytest` — не найдётся ни «прогон pytest», ни «`pytest`».
        """
        text = (config.ROOT / "docs" / "operator-session.md").read_text(
            encoding="utf-8")
        self.assertTrue("прогон pytest" in text or "`pytest`" in text,
                        "класс `pytest` / действие «прогон pytest» не описаны")
        self.assertIn("ход шага", text, "строка «ход шага» не описана")
        self.assertIn("предупреждение", text,
                      "строка «предупреждение» не описана")
        self.assertIn("в час", text, "граница строк в час не описана")
        self.assertTrue(
            "WATCH_PROGRESS_LINES_PER_HOUR" in text
            or re.search(r"(?<!\d)16(?!\d)", text),
            "граница строк в час не названа ни константой, ни числом")


if __name__ == "__main__":
    unittest.main()
