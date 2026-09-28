"""AC-7 — 01M3KE8ZJXFARS6KC441PCDCQV: закреплённая версия клиента Claude
поднята до установленной на пульте, с пометкой на строке константы и без
литералов прежнего пина в наборе.

Источник — SPEC.md, «Критерии приёмки»:

AC-7. `config.CLI_VERSION_PIN` равен версии клиента Claude, установленной
на пульте на день разработки и названной в PLAN по выводу
`claude --version` (на 28.09.2026 — `2.1.283`); комментарий строки
константы называет дату и основание сдвига; литералы прежней версии пина
в `tests/` (`tests/test_version.py`, `tests/test_stack.py`) приведены к
новому значению.

Прежнее значение пина планка не зашивает литералом: она читает
`orchestrator/config.py` из базы сравнения ветки. Нижняя граница нового
значения — `2.1.283`, названная критерием как установленная на пульте
28.09.2026: версия клиента с этого дня может только расти, поэтому день
разработки позже ограничения не нарушает.

Красен до реализации: `config.CLI_VERSION_PIN` в ветке задачи всё ещё
`2.1.267` (совпадает с базой сравнения), комментарий строки — от решения
26.09, а `tests/test_version.py` и `tests/test_stack.py` сверяют прежнее
значение литералом.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _catalog  # noqa: E402

from orchestrator import config, models  # noqa: E402

CONFIG_REL = "orchestrator/config.py"

#: Строка константы пина: значение и хвост-комментарий отдельно.
_PIN_LINE = re.compile(r'^CLI_VERSION_PIN\s*=\s*"([^"]+)"[ \t]*(#.*)?$',
                       re.MULTILINE)

#: Дата в комментарии: `28.09`, `28.09.2026` или `2026-09-28`.
_DATE = re.compile(r"(?<!\d)(?:\d{2}\.\d{2}(?:\.\d{4})?|\d{4}-\d{2}-\d{2})"
                   r"(?!\d)")

#: Установленная на пульте версия, названная критерием (28.09.2026).
DECLARED_INSTALLED = "2.1.283"


def _pin_line(text: str):
    """(значение пина, комментарий строки) из текста `config.py`."""
    match = _PIN_LINE.search(text)
    if match is None:
        return None, None
    return match.group(1), (match.group(2) or "").strip()


class CliVersionPinTest(unittest.TestCase):

    def setUp(self):
        self.was, self.was_comment = _pin_line(_catalog.base_file(CONFIG_REL))
        self.assertIsNotNone(
            self.was, f"в базе сравнения не нашлась строка CLI_VERSION_PIN "
                      f"— сверять сдвиг не с чем")
        source = (_catalog.REPO_ROOT / CONFIG_REL).read_text(encoding="utf-8")
        self.now, self.comment = _pin_line(source)
        self.assertIsNotNone(
            self.now, f"{CONFIG_REL}: строка CLI_VERSION_PIN не найдена")

    def test_ac7_pin_is_raised_to_the_version_installed_on_the_pult(self):
        """Пин сдвинут вверх с прежнего значения и не ниже установленной
        на пульте версии, названной критерием (`2.1.283`).

        Ловит мутацию: пин подняли до 2.1.280 — наименьшей версии клиента
        для `claude-opus-5-5` из документации (число стоит рядом в той же
        таблице требования 1 и путается с установленной): расхождение с
        фактом осталось бы, и `doctor`/`artel.py version` продолжили бы
        давать предупреждение `cli-version` на каждом шаге — ровно то,
        ради чего пин и двигают.
        """
        self.assertEqual(self.now, config.CLI_VERSION_PIN,
                         "значение константы разошлось со строкой файла")
        self.assertNotEqual(self.was, self.now,
                            "пин остался прежним — сдвига не было")
        now = models.version_tuple(self.now, "config.CLI_VERSION_PIN")
        self.assertGreater(now,
                           models.version_tuple(self.was, "база сравнения"),
                           "пин уехал вниз")
        self.assertGreaterEqual(
            now, models.version_tuple(DECLARED_INSTALLED, "AC-7"),
            f"пин {self.now} ниже установленной на пульте {DECLARED_INSTALLED}")

    def test_ac7_plan_names_the_version_the_pin_is_set_to(self):
        """PLAN.md задачи называет то самое значение, на которое сдвинут
        пин: критерий требует взять его выводом `claude --version` и
        назвать в PLAN.

        Ловит мутацию: пин поднят числом из бэклога (запись 28.09 про
        обновление клиента посреди прогона канарейки), а вывод
        `claude --version` в PLAN не приведён — сверить, что пин равен
        ФАКТУ пульта, а не переписанному из заметки числу, Оператору
        нечем.
        """
        self.assertIn(self.now, _catalog.plan_text(),
                      f"PLAN.md не называет версию {self.now}, на которую "
                      f"сдвинут config.CLI_VERSION_PIN")

    def test_ac7_pin_line_carries_a_renewed_dated_mark(self):
        """Комментарий строки константы обновлён вместе со значением и
        называет дату.

        Ловит мутацию: значение поднято, а пометка осталась от прошлого
        решения Оператора (26.09, CR-2026-09-26-7) — по строке читалось
        бы, что пин стоит на 2.1.267 по позапрошлому основанию, и
        следующий, кто придёт его двигать, пошёл бы искать несуществующий
        CR.
        """
        self.assertTrue(self.comment,
                        f"{CONFIG_REL}: строка CLI_VERSION_PIN без "
                        f"комментария — основание сдвига не названо")
        self.assertNotEqual(
            self.was_comment, self.comment,
            "комментарий строки не тронут — он описывает прошлый сдвиг")
        self.assertRegex(
            self.comment, _DATE,
            f"комментарий {self.comment!r} не называет даты сдвига")

    def test_ac7_no_test_carries_the_previous_pin_literal(self):
        """Литерала прежнего пина нет ни в одном модуле `tests/`.

        Ловит мутацию: пин поднят, а `tests/test_version.py` (сверка
        значения и пометки) или `tests/test_stack.py` (строки вердикта
        «CLI ≥ минимум — ok») оставлены с прежним числом — полный набор
        красный, и задача встанет на гейте приёмки.
        """
        hits = [f"{rel}:{number}"
                for rel, text in _catalog.tests_sources()
                for number, line in enumerate(text.splitlines(), 1)
                if self.was in line]

        self.assertEqual([], hits,
                         f"прежний пин {self.was} остался в: "
                         f"{', '.join(hits)}")


if __name__ == "__main__":
    unittest.main()
