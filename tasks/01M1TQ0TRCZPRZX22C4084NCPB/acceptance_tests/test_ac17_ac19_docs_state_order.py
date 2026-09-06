"""Приёмочные тесты 01M1TQ0TRCZPRZX22C4084NCPB — AC-17, AC-18, AC-19:
`docs/invariants.md`, раздел `docs/roadmap.md` про флоу FSM и текст
схемы состояний в выводе `artel.py --help` отражают новый порядок
`in_dev -> verifying -> review -> acceptance -> merge_gate`.

Красен до реализации:
- `docs/invariants.md` нигде не несёт цепочки состояний, где `verifying`
  стоит МЕЖДУ `in_dev` и `review` (проверено grep по репозиторию перед
  написанием теста — единственные упоминания `verifying` в этом файле не
  формируют такую цепочку вовсе);
- `docs/roadmap.md` тем же образом не несёт такой цепочки нигде;
- `orchestrator/artel.py` (строка 8, докстринг модуля — тот же текст,
  что печатает `--help`) несёт буквально устаревший порядок:
  `spec_writing -> spec_gate -> tests_writing -> in_dev -> review ->
  acceptance -> merge_gate -> done` — `verifying` не упомянут вовсе.

Регэксп ниже принимает и ASCII-стрелку (`->`, конвенция `artel.py`), и
юникодную (`→`, конвенция `docs/*.md` — см. `docs/roadmap.md:155`
`spec_gate → in_dev → review (1 итерация) → acceptance → merge_gate →
done`), допускает пробелы вокруг стрелки, но требует все пять состояний
СТРОГО подряд в этом порядке — совпадение по разрозненным упоминаниям
в разных абзацах не считается.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artel  # noqa: E402

_ARROW = r"\s*(?:->|→)\s*"
_NEW_ORDER_CHAIN = re.compile(
    "in_dev" + _ARROW + "verifying" + _ARROW + "review" + _ARROW
    + "acceptance" + _ARROW + "merge_gate")


def _text(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


class DocsStateOrderTest(unittest.TestCase):

    def test_ac17_invariants_doc_describes_new_order(self):
        """`docs/invariants.md` несёт где-либо цепочку `in_dev ->
        verifying -> review -> acceptance -> merge_gate` (в любом из двух
        принятых написаний стрелки).

        Ловит мутацию: файл продолжает описывать порядок со старым
        расположением `verifying` (после `acceptance`, как сегодня) —
        цепочка нового порядка нигде не встретится, `search` вернёт
        `None`.
        """
        text = _text("docs/invariants.md")
        self.assertIsNotNone(
            _NEW_ORDER_CHAIN.search(text),
            "docs/invariants.md не несёт цепочку нового порядка "
            "in_dev -> verifying -> review -> acceptance -> merge_gate")

    def test_ac18_roadmap_flow_section_describes_new_order(self):
        """`docs/roadmap.md` несёт где-либо цепочку `in_dev -> verifying
        -> review -> acceptance -> merge_gate`.

        Ловит мутацию: раздел про флоу FSM продолжает называть старый
        порядок (`in_dev -> review -> verifying -> ...`, как в
        сегодняшней строке 155) — новая цепочка нигде не встретится.
        """
        text = _text("docs/roadmap.md")
        self.assertIsNotNone(
            _NEW_ORDER_CHAIN.search(text),
            "docs/roadmap.md не несёт цепочку нового порядка "
            "in_dev -> verifying -> review -> acceptance -> merge_gate")

    def test_ac19_help_text_describes_new_order(self):
        """Докстринг `orchestrator/artel.py` (тот же текст, что печатает
        `python3 artel.py --help`/без аргументов, `print(__doc__)`) несёт
        цепочку `in_dev -> verifying -> review -> acceptance ->
        merge_gate`.

        Ловит мутацию: строка схемы состояний остаётся байт-в-байт
        сегодняшней (`in_dev -> review -> acceptance`, без `verifying`
        вовсе) — новая цепочка не встретится в тексте докстринга.
        """
        self.assertIsNotNone(
            _NEW_ORDER_CHAIN.search(artel.__doc__ or ""),
            "текст --help (докстринг artel.py) не несёт цепочку нового "
            "порядка in_dev -> verifying -> review -> acceptance -> "
            "merge_gate")


if __name__ == "__main__":
    unittest.main()
