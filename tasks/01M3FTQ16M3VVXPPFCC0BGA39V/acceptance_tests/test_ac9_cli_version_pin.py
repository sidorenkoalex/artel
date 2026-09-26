"""AC-9 — 01M3FTQ16M3VVXPPFCC0BGA39V: пин версии CLI поднят до 2.1.267 и
несёт пометку даты и решения Оператора.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. `config.CLI_VERSION_PIN` равен `"2.1.267"`, и строка константы
несёт пометку даты и решения Оператора (26.09, CR-2026-09-26-7).

Красен до реализации: `orchestrator/config.py`:256 держит
`CLI_VERSION_PIN = "2.1.236"` с пометкой прошлого решения (03.09) —
падают оба теста.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config  # noqa: E402

CONFIG_REL = "orchestrator/config.py"
EXPECTED_PIN = "2.1.267"
DECISION_DATE = "26.09"
DECISION_FINDING = "CR-2026-09-26-7"
_PIN_LINE_RE = re.compile(r"^CLI_VERSION_PIN\s*=.*$", re.M)


class CliVersionPinTest(unittest.TestCase):

    def test_ac9_pin_value_is_the_installed_version(self):
        """`config.CLI_VERSION_PIN` равен строке `"2.1.267"` — версии,
        установленной на пульте (замер седьмой ревизии).

        Ловит мутацию: пин поднят «на глазок» до другой версии (2.1.26,
        2.1.276, число вместо строки) — сверка со значением критерия
        покраснеет, и предупреждение «cli-version» осталось бы на каждом
        шаге.
        """
        self.assertEqual(EXPECTED_PIN, config.CLI_VERSION_PIN)

    def test_ac9_pin_line_carries_operator_decision_mark(self):
        """Строка константы в `orchestrator/config.py` несёт пометку даты
        решения (26.09) и находки, по которой пин поднят
        (CR-2026-09-26-7).

        Ловит мутацию: значение заменено, а пометка осталась от прошлого
        решения (03.09, pre-flight A7) — по строке нельзя понять, чьим
        решением и когда пин сдвинут, и подъём читается как автоматика,
        которой он по докстрингу `check_cli_version` быть не может;
        проверка подстрок покраснеет.
        """
        text = (_util.REPO_ROOT / CONFIG_REL).read_text(encoding="utf-8")
        lines = _PIN_LINE_RE.findall(text)
        self.assertEqual(
            1, len(lines),
            f"в {CONFIG_REL} ожидается ровно одно присваивание "
            f"CLI_VERSION_PIN (AC-9), найдено: {lines}")
        line = lines[0]
        self.assertIn(DECISION_DATE, line,
                      f"строка константы обязана нести дату решения "
                      f"{DECISION_DATE} (AC-9): {line}")
        self.assertIn(DECISION_FINDING, line,
                      f"строка константы обязана нести решение Оператора по "
                      f"находке {DECISION_FINDING} (AC-9): {line}")


if __name__ == "__main__":
    unittest.main()
