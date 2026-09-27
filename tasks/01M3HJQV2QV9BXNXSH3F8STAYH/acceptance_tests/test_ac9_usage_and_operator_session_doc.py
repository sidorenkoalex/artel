"""AC-9 — 01M3HJQV2QV9BXNXSH3F8STAYH: справка команды и
`docs/operator-session.md` описывают флаг выбора шаблона и новый исход.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Справка команды `canary` в `orchestrator/artel.py` называет флаг
`--template` в строке использования и описывает новый исход;
`docs/operator-session.md` описывает флаг выбора шаблона и новый исход,
включая то, что прогон с этим исходом не годится для сдвига пина.

Текст справки — модульный докстринг `orchestrator/artel.py` (его и печатает
команда без аргументов), поэтому флаг ищется в строке докстринга, где живёт
сама команда `canary --k`, а не где-нибудь в файле.

«Описывает новый исход» проверяется по его собственному имени — «исчерпан
потолок» (устойчивая часть формулировки, зафиксированной AC-6): исход, у
которого в документации другое имя, чем в отчёте прогона, Оператор в отчёте
не узнает. Требование «не годится для сдвига пина»
`docs/operator-session.md` обязан нести В ОДНОМ блоке с самим исходом
(абзац или пункт списка, `_util.doc_blocks`) — то же правило, что уже
записано там пунктом 5 «Аварийного режима» про набор ролей: правило,
запрятанное в другой раздел, в аварийном режиме не читают.

Красен до реализации: ни `orchestrator/artel.py`, ни
`docs/operator-session.md` не знают ни флага `--template`, ни исхода
«исчерпан потолок» — сегодня такого исхода в пульте нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import artel  # noqa: E402

OPERATOR_SESSION_MD = _util.DOCS_DIR / "operator-session.md"

#: Имя нового исхода — устойчивая часть формулировки AC-6.
OUTCOME = "исчерпан потолок"

TEMPLATE_FLAG = "--template"


class UsageAndDocTest(unittest.TestCase):

    def setUp(self):
        self.usage = artel.__doc__ or ""
        self.doc = OPERATOR_SESSION_MD.read_text(encoding="utf-8")

    def test_ac9_usage_line_of_the_canary_command_names_the_template_flag(self):
        """Строка использования команды `canary --k` называет `--template`.

        Ловит мутацию: флаг реализован, но в строку использования не добавлен
        — единственный текст, который печатает команда без аргументов, о
        выборе шаблона молчал бы, и флаг существовал бы только в SPEC задачи.
        """
        usage_lines = [line for line in self.usage.splitlines()
                       if "canary --k" in line]
        self.assertTrue(usage_lines,
                        "в справке нет строки команды canary --k")

        self.assertTrue(
            any(TEMPLATE_FLAG in line for line in usage_lines),
            f"строка использования не называет {TEMPLATE_FLAG}: {usage_lines}")

    def test_ac9_usage_describes_the_new_outcome(self):
        """Справка `orchestrator/artel.py` называет новый исход прогона его
        собственным именем.

        Ловит мутацию: справка дополнена только флагом — Оператор, увидев в
        отчёте прогона незнакомый исход, не нашёл бы его ни в одной справке
        пульта и трактовал бы как обычную красноту.
        """
        self.assertIn(OUTCOME, self.usage.lower())

    def test_ac9_operator_session_describes_the_template_flag(self):
        """`docs/operator-session.md` называет флаг выбора шаблона.

        Ловит мутацию: флаг описан только в справке команды — регламент
        сессии, по которому Оператор решает, что и когда прогонять, не знал бы
        способа воспроизвести конкретный сценарий пула.
        """
        self.assertIn(TEMPLATE_FLAG, self.doc)

    def test_ac9_operator_session_ties_the_new_outcome_to_the_pin_rule(self):
        """В `docs/operator-session.md` есть блок, называющий и новый исход, и
        пин: прогон с этим исходом для сдвига пина не годится.

        Ловит мутацию: новый исход описан как «прогон завершился по потолку»
        без слова о пине — зелёного вердикта у такого прогона нет, но Оператор
        в аварийном режиме мог бы счесть «не красный по вине кода» достаточным
        основанием двинуть пин, а ADR-0013 этого не разрешает.
        """
        blocks = [block for block in _util.doc_blocks(self.doc)
                  if OUTCOME in block.lower() and "пин" in block.lower()]

        self.assertTrue(
            blocks,
            f"ни один блок документа не называет «{OUTCOME}» вместе с пином")


if __name__ == "__main__":
    unittest.main()
