"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-8 (протокол гейта SPEC
в docs/operator-gates.md несёт пункт про явное решение Оператора между
делением и монолитом при сработавших сигналах).

`docs/operator-gates.md` — не защищённый путь (skills/conventions-core.md,
`PROTECTED_PATHS` в orchestrator/config.py его не содержит): разработчик
правит файл прямо в ветке задачи, содержимое доступно тесту напрямую
с диска рабочей копии, без фикстур.

Красен до реализации: сегодняшний раздел «Гейт SPEC» перечисляет только
существующие пять пунктов (SPEC прочитан целиком, сверка с ТЗ, AC
проверяемы, budget_usd, «Не входит») и ничего не говорит про деление или
монолит — обе проверки ниже падают, пока разработчик не допишет пункт
требования 4 SPEC.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

GATES_DOC = REPO_ROOT / "docs" / "operator-gates.md"


def _spec_gate_body() -> str:
    text = GATES_DOC.read_text(encoding="utf-8")
    # Заголовок раздела несёт код гейта в скобках («## Гейт SPEC
    # (`spec_gate`)») — ищем сам раздел по регэкспу заголовка, а не по
    # guard.section_body (та требует точного совпадения имени секции).
    # `[\s\S]*?` вместо `.*?` с DOTALL: DOTALL на всё выражение делает
    # жадный `.*` заголовочной строки (`Гейт SPEC.*$`) пожирающим весь
    # остаток файла — переносы стоки внутри него тоже "." под DOTALL.
    match = re.search(r"^##\s+Гейт SPEC[^\n]*\n([\s\S]*?)(?=^##\s|\Z)",
                      text, re.M)
    return match.group(1) if match else ""


class SpecGateProtocolRequiresExplicitDecisionTest(unittest.TestCase):
    """Раздел «Гейт SPEC» протокола называет оба исхода (деление, монолит)
    как решение, которое Оператор явно принимает при сработавших сигналах.

    Ловит мутацию: раздел упоминает только один из двух исходов (например,
    добавлен пункт про деление, но обоснование монолита как равноправный
    исход забыто) — assertion на второе слово покраснеет отдельно от
    первого.
    """

    def test_ac8_spec_gate_section_names_both_division_and_monolith(self):
        body = _spec_gate_body().lower()

        self.assertTrue(body, "в docs/operator-gates.md не нашёлся раздел "
                              "«Гейт SPEC»")
        self.assertIn("делени", body,
                     "раздел «Гейт SPEC» не упоминает исход «деление»")
        self.assertIn("монолит", body,
                     "раздел «Гейт SPEC» не упоминает исход «монолит»")


if __name__ == "__main__":
    unittest.main()
