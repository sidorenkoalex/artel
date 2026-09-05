"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-9 (SPEC без секции
«## Деление» — обычный случай без заявки на деление — не меняет
поведение существующего `approve` на `spec_gate`: переход в
`tests_writing`/`in_dev` по прежним правилам, без создания подзадач).

Фикстура — `schema_version: 1` без AC-разметки (`guard.requires_ac_markup`
отдаёт `False`) — существующий `_cmd_approve` сегодня ведёт такой SPEC в
`in_dev` напрямую (`orchestrator/fsm.py:818-821`, ветка «SPEC schema_version
... — без AC-разметки, tests_writing недоступна»); тест фиксирует, что
ветка деления НЕ перехватывает этот путь заранее (не проверяет саму
логику skip_tests/AC-markup — она чужая для этой задачи и уже покрыта
`tests/test_advance_guard.py`/AC-15 этой SPEC).

Зелёный с рождения: до появления ветки деления `_cmd_approve` на
`spec_gate` не читает секцию «## Деление» вовсе — поведение SPEC без неё
не отличается от поведения любого SPEC версии 1 сегодня, тест уже зелёный
и останется таким после реализации (AC-9 требует НЕИЗМЕННОСТИ этого пути,
не новой механики) — сохранение поведения, не новая функциональность,
проверено прогоном ниже без единой правки кода.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import SplitApproveSandbox, spec_text  # noqa: E402


class NoDivisionSectionLeavesApproveUnaffectedTest(SplitApproveSandbox):
    """SPEC без секции «## Деление» — `approve` переводит в `in_dev`
    (обычный путь SPEC без AC-разметки) и не заводит ни одной подзадачи.

    Ловит мутацию: проверка «секция «## Деление» заполнена» реализована
    без проверки на ПУСТОТУ/ОТСУТСТВИЕ секции (например код всегда пробует
    разобрать подразделы и на пустом тексте заводит 0 «подзадач» побочным
    эффектом, либо ошибочно переводит родителя в killed без единой
    подзадачи) — набор задач или итоговое состояние родителя отличились бы
    от привычного поведения без единой строчки заявки на деление.
    """

    def test_ac9_spec_without_division_section_behaves_as_before(self):
        text = spec_text(subsections=None)
        sha = self.enter_spec_gate(text)

        self.approve(sha)

        row = self.task_row()
        self.assertEqual(
            row["state"], "in_dev",
            f"SPEC без секции «## Деление» изменил обычный переход "
            f"spec_gate -> in_dev (AC-9): строка {row}")
        self.assertEqual(
            self.all_task_ids(), {self.TASK},
            f"SPEC без секции «## Деление» породил подзадачи, хотя "
            f"заявки на деление не было (AC-9): {self.all_task_ids()}")


if __name__ == "__main__":
    unittest.main()
