"""AC-20: раздел «Провайдер codex» в `docs/stack.md`. AC-21 — пометка
ниже.

Красен до реализации: раздела «Провайдер codex» в `docs/stack.md` ещё
нет — поиск заголовка не находит ничего.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _codex import (DISABLED_FEATURES, REPO_ROOT,  # noqa: E402
                    discover_key_slot, role_home_reference_dir)

SECTION_TITLE = "Провайдер codex"

# AC-21: manual — обе половины критерия недоступны планке по построению.
# «Наборы tests/... проходят зелёными» — условие, которое пульт уже
# считает САМ и для КАЖДОЙ задачи: автогейт acceptance гоняет ПОЛНЫЙ
# набор tests/ в worktree ветки (orchestrator/acceptance.py::
# run_full_suite как условие approve, ADR-0007), и те же пять файлов
# гоняет CI; собственный прогон внутри планки был бы не проверкой, а
# копией уже действующего гейта — за цену, которой планка рискует
# превысить ACCEPTANCE_TIMEOUT_SEC. «Ни один тест поведения Claude не
# ослаблен и не удалён» — свойство ДИФФА к базовой ревизии, а не
# состояния дерева: планка исполняется на материализованном
# acceptance_tests/ и базовой ревизии не видит, ослабленный ассерт
# внутри уцелевшего метода не отличим от исходного ничем, кроме чтения
# диффа. Сверяет Оператор на приёмке (и ревьювер по диффу ветки).


class StackDocSectionTest(unittest.TestCase):
    """`docs/stack.md` — требование 13, AC-20."""

    def section(self) -> str:
        """Текст раздела «Провайдер codex» — от его заголовка до
        следующего заголовка того же уровня."""
        text = (REPO_ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines)
                  if line.startswith("#") and SECTION_TITLE in line]
        self.assertTrue(starts, f"в docs/stack.md нет раздела «{SECTION_TITLE}»")
        start = starts[0]
        level = len(lines[start]) - len(lines[start].lstrip("#"))
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.startswith("#") and \
                    len(line) - len(line.lstrip("#")) <= level:
                return "\n".join(lines[start:index])
        return "\n".join(lines[start:])

    def test_ac20_section_covers_install_slot_home_disabled_and_the_switch(self):
        """Раздел «Провайдер codex» несёт установку CLI, имя слота ключа,
        адрес дома роли, перечень выключенного с причиной и порядок
        перевода роли на Codex ярусом локального слоя моделей.

        Ловит мутацию: раздел написан «в общем» — про изоляцию сказано
        словами, но одиннадцать выключенных функций не перечислены, и
        Оператор, сверяя дом роли руками, не знает, что именно обязано
        быть выключено; либо имя слота ключа названо неверно (осталось
        от Claude), и ключ кладётся в слот, которого провайдер не
        спрашивает.
        """
        section = self.section()

        self.assertIn("установ", section.lower(), section)

        slot = discover_key_slot(self)
        self.assertIn(slot, section, f"имя слота {slot} не названо")

        reference = role_home_reference_dir().relative_to(REPO_ROOT)
        self.assertTrue(str(reference) in section or ".artel/home/.codex"
                        in section, section)

        missing = [name for name in DISABLED_FEATURES if name not in section]
        self.assertEqual(missing, [], "функции не перечислены поимённо")
        self.assertTrue(any(word in section.lower()
                            for word in ("причин", "почему", "потому")),
                        "перечень выключенного идёт без причины")

        self.assertIn(".artel/models.yaml", section, section)
        self.assertIn("ярус", section.lower(), section)


if __name__ == "__main__":
    unittest.main()
