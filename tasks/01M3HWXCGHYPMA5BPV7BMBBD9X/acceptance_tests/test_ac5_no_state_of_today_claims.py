"""AC-5 — запрет утверждений о состоянии системы «на сегодня» с тремя
названными примерами и ссылкой на ADR-0018.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. После применения приложения `skills/test-authoring.md` запрещает
утверждения о состоянии системы «на сегодня», называет все три примера ТЗ
(полный состав параметров публичной функции или команды, точное число
записей чужих таблиц, полный перечень файлов каталога) и ссылается на
ADR-0018 — в разделе «Запрещено» либо в новом разделе.

Проверяется один и тот же раздел скила после применения приложений PLAN к
базе сравнения (см. `_appendix`) — тот, что ссылается на ADR-0018:
критерий разрешает и «Запрещено», и новый раздел, но не разрешает
рассыпать запрет и его примеры по разным местам файла.

Красен до реализации: приложения на `skills/test-authoring.md` ещё нет — в
базе сравнения нет ни одной ссылки на ADR-0018, раздела с запретом не
существует вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402

ADR = "ADR-0018"
# Слова, которыми скил формулирует запрет (любого достаточно).
PROHIBITION_WORDS = ("запрещ", "нельзя", "не утверждай", "не пиши", "не пишутся")


class NoStateOfTodayClaimsTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()
        self.text = _appendix.applied_text(_appendix.TEST_AUTHORING)
        self.sections = _appendix.sections_with(self.text, ADR)

    def test_ac5_forbids_claims_about_state_of_today(self):
        """В скиле есть раздел со ссылкой на ADR-0018, и он именно
        ЗАПРЕЩАЕТ утверждения о состоянии системы «на сегодня».

        Ловит мутацию: правка описывает повод (планка покраснела от
        добавленного флага) как наблюдение или совет, но не формулирует
        запрет и не ссылается на решение — в разделе не окажется ни слова
        запрета, ни ADR-0018, и проверка покраснеет.
        """
        self.assertTrue(
            self.sections,
            f"в `{_appendix.TEST_AUTHORING}` после применения приложений нет "
            f"раздела со ссылкой на {ADR} ({self.state.diagnosis()})")
        forbidding = [s for s in self.sections
                      if any(_appendix.has(s, w) for w in PROHIBITION_WORDS)
                      and _appendix.has(s, "сегодня")]
        self.assertTrue(
            forbidding,
            f"раздел со ссылкой на {ADR} не запрещает утверждений о "
            f"состоянии системы «на сегодня» (ищутся слово запрета из "
            f"{list(PROHIBITION_WORDS)} и «сегодня» в том же разделе) "
            f"({self.state.diagnosis()})")

    def test_ac5_names_all_three_examples_of_the_ban(self):
        """Тот же раздел называет все три примера ТЗ: полный состав
        параметров публичной функции или команды, точное число записей
        чужих таблиц, полный перечень файлов каталога.

        Ловит мутацию: правка назвала только повод волны — состав
        параметров команды — и промолчала о числе записей чужих таблиц и о
        перечне файлов каталога (два других примера, которых конкретный
        инцидент не касался) — проверка покраснеет, назвав недостающее.
        """
        self.assertTrue(
            self.sections,
            f"раздела со ссылкой на {ADR} нет — примеры проверять не на чем "
            f"({self.state.diagnosis()})")
        needles = ("парамет", "запис", "табли", "файл", "каталог")
        full = [s for s in self.sections if not _appendix.missing(s, needles)]
        self.assertTrue(
            full,
            f"раздел со ссылкой на {ADR} называет не все три примера "
            f"запрещённых утверждений — недостающие слова по разделам: "
            f"{[_appendix.missing(s, needles) for s in self.sections]} "
            f"({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
