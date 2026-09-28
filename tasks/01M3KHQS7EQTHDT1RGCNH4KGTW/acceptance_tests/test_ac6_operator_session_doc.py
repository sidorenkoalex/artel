"""Приёмочный тест 01M3KHQS7EQTHDT1RGCNH4KGTW — AC-6 (SPEC.md).

`docs/operator-session.md` — обычный документ вне защищённых путей, его
правит разработчик тем же коммитом, что и код; тест читает текст с диска,
не импортируя кода (тот же приём, что `tasks/01M1VBEAWZW4EBZHKMGNBBK648/
acceptance_tests/test_ac9_operator_session_doc.py`).

«Раздел о занятой зоне» — пункты документа, говорящие об ожидании занятой
зоны (пункт назван по содержанию, а не по номеру строки или заголовку
раздела: и строки, и заголовки соседей документ меняет постоянно). Три
утверждения критерия ищутся в их общем тексте, поэтому разбиение правки
на соседние пункты тест не красит.

Красен до реализации: сегодняшний пункт о занятой зоне (docs/operator-
session.md:194-210) описывает настройку как ту, что «Оператор выставляет
сам», и не несёт ни даты 28.09.2026, ни слова «перезапуск», ни отсылки к
журналу задачи — проверено разбором документа 28.09.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

DOC = Path(config.ROOT).resolve() / "docs" / "operator-session.md"
DECISION_DATE = "28.09.2026"


def _bullets(text: str) -> list:
    """Пункты верхнего уровня документа: строка «- …» и её продолжение
    (пустые и отбитые отступом строки до следующего пункта либо до
    неотбитого текста/заголовка)."""
    items, current = [], None
    for line in text.splitlines():
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = [line]
        elif current is not None:
            if line.strip() and not line.startswith(" "):
                items.append(current)
                current = None
            else:
                current.append(line)
    if current is not None:
        items.append(current)
    return ["\n".join(item) for item in items]


def _zone_wait_section() -> str:
    """Общий текст пунктов документа об ожидании занятой зоны."""
    chosen = [item for item in _bullets(DOC.read_text(encoding="utf-8"))
              if "зон" in item.lower() and "ожидан" in item.lower()]
    return "\n".join(chosen)


class Ac6OperatorSessionDocTest(unittest.TestCase):

    def test_ac6_zone_section_carries_all_three_statements(self):
        """Раздел `docs/operator-session.md` о занятой зоне несёт все три
        утверждения критерия: настройка включена решением Оператора
        28.09.2026; ручной перезапуск цикла с `--wait-zone` больше не
        нужен; ожидающие задачи видны через `status` и журнал задачи.

        Ловит мутацию: разработчик поднимает значение настройки в
        `orchestrator/config.py` и правит тесты, а документ оставляет
        прежним (классический пропуск: код зелен и без него) — Оператор
        читал бы в своём документе, что настройку он «выставляет сам», и
        продолжал бы перезапускать вставшие циклы руками с флагом, ровно
        как 28.09 с задачей 01M3KE8ZJXFARS6KC441PCDCQV.
        """
        section = _zone_wait_section()
        self.assertTrue(
            section,
            f"в {DOC} нет ни одного пункта об ожидании занятой зоны")
        lowered = section.lower()

        self.assertIn(
            DECISION_DATE, section,
            f"раздел не называет дату решения Оператора:\n{section}")
        self.assertRegex(
            lowered, r"включен[ао]",
            f"раздел не сообщает, что настройка включена:\n{section}")
        self.assertRegex(
            lowered, r"перезапуск",
            f"раздел не говорит о ручном перезапуске цикла:\n{section}")
        self.assertRegex(
            lowered, r"больше не нуж",
            f"раздел не сообщает, что ручной перезапуск больше не "
            f"нужен:\n{section}")
        self.assertIn(
            "status", lowered,
            f"раздел не называет `status` среди способов увидеть ожидающие "
            f"задачи:\n{section}")
        self.assertRegex(
            lowered, r"журнал",
            f"раздел не называет журнал задачи среди способов увидеть "
            f"ожидающие задачи:\n{section}")


if __name__ == "__main__":
    unittest.main()
