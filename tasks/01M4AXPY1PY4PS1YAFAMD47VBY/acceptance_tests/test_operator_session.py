"""Формулировки руководства сессии Оператора, внесённые этой задачей.
Группа: разовый
Красен до реализации: руководство ещё не называет --detach и порядок сверки нагрузки.
"""

import re
import unittest
from pathlib import Path


class OperatorSessionTextTest(unittest.TestCase):
    def test_ac14_detach_and_load_before_limits_are_documented(self):
        """Руководство называет штатный отвязанный запуск и диагностику нагрузки перед решением о пределах.

        Ловит мутацию: добавлен только флаг канарейки, а правило проверки uptime и процессов перед пределами пропущено.
        """
        document = (Path(__file__).resolve().parents[3] / "docs" /
                    "operator-session.md").read_text(encoding="utf-8")
        text = re.sub(r"\s+", " ", document)
        detach_positions = [match.start() for match in re.finditer("--detach", text)]
        self.assertTrue(any(all(fragment in text[max(0, at - 220):at + 220].lower()
                                for fragment in ("canary", "штатн", "сесси",
                                                 "оператор"))
                            for at in detach_positions),
                        "нет правила о штатном canary --detach для сессии Оператора")

        uptime_positions = [match.start() for match in re.finditer("uptime", text)]
        self.assertTrue(any(all(fragment in text[max(0, at - 320):at + 320].lower()
                                for fragment in ("таймаут", "замедл", "процесс",
                                                 "загрузк", "предел", "сначала", "потом"))
                            for at in uptime_positions),
                        "нет правила сверять uptime и процессы до решения о пределах")
