"""Деталь перехода с гейта SPEC — одна константа `advance_gates.tests_writing.SPEC_GATE_PASSED_DETAIL` (AC-5).

Группа: разовый

Критерий называет закрытое имя `auto._LEGIT_FIRST_ENTRY_DETAILS` и
текст модуля `orchestrator/fsm.py` — долгоживущему файлу `tests/` закрытые
имена недоступны (правило ADR-0020), поэтому проверка живёт в планке.
Сквозной `approve` — `fsm.cmd_approve` в лёгкой песочнице переходов
(`tests.sandbox.LightTransitionSandbox`): SPEC версии 5 лежит в каталоге
задачи песочницы (`self.tdir`), git подменён песочницей. Импорт пакета
гейтов в чистом интерпретаторе — отдельный процесс `python3 -c`.

Красен до реализации: `orchestrator/fsm.py` сегодня пишет деталь перехода литералом «гейт SPEC пройден — приёмочные тесты до кода» — проверка текста модуля падает; запись перехода, перечень `auto` и импорт в чистом интерпретаторе держат существующее поведение и зелёные.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

import orchestrator
from orchestrator import auto, fsm, store
from orchestrator.advance_gates import tests_writing
from tests.sandbox import LightTransitionSandbox

CODE_ROOT = Path(orchestrator.__file__).resolve().parent.parent
LITERAL = "гейт SPEC пройден — приёмочные тесты до кода"
ZONE = "orchestrator/t5fr_zone.py"

SPEC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zone}
budget_usd: 25
---

# SPEC: фикстура гейта SPEC

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Оценка объёма и деление

Прогноз диффа: 2 КиБ.

## Не входит

Ничего.

## Материалы

Нет.
"""


class SpecGateDetailTest(LightTransitionSandbox):

    def test_ac5_spec_gate_detail_comes_from_single_constant(self):
        """`approve` на `spec_gate` пишет деталь перехода, равную константе `tests_writing`; литерала в `fsm.py` нет; пакет гейтов импортируется первым без цикла.

        Сценарий: SPEC версии 5 с критерием на `spec_gate`, `approve` —
        задача в `tests_writing`, последняя запись «state -> tests_writing»
        журнала несёт деталь, равную `SPEC_GATE_PASSED_DETAIL`; константа
        входит в `auto._LEGIT_FIRST_ENTRY_DETAILS`. Ни одна строковая
        константа и ни одна строка текста `orchestrator/fsm.py` не несут
        литерала детали. `python3 -c "import
        orchestrator.advance_gates.acceptance"` в корне рабочей копии
        завершается нулём.

        Ловит мутацию: `fsm.py` по-прежнему пишет деталь своим литералом
        (копия текста в модуле); импорт константы вынесен на уровень модуля
        `fsm.py` — первый импорт `orchestrator.advance_gates.acceptance`
        падает `ImportError` кругового импорта; в деталь перехода попало
        иное имя (константа соседнего модуля, текст с хвостом).
        """
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC.format(task=self.TASK, zone=ZONE), encoding="utf-8")
        self.set_state("spec_gate")
        out = self.capture(fsm.cmd_approve, self.TASK)
        self.assertEqual(self.state(), "tests_writing", out)
        details = [r["detail"] for r in store.task_steps(store.db(), self.TASK)
                   if r["action"] == "state -> tests_writing"]
        self.assertTrue(details, f"нет записи перехода:\n{out}")
        self.assertEqual(details[-1], tests_writing.SPEC_GATE_PASSED_DETAIL)
        self.assertIn(tests_writing.SPEC_GATE_PASSED_DETAIL,
                      auto._LEGIT_FIRST_ENTRY_DETAILS)

        source = Path(fsm.__file__).read_text(encoding="utf-8")
        strings = [node.value for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.Constant)
                   and isinstance(node.value, str) and LITERAL in node.value]
        self.assertEqual(strings, [], "литерал детали — строковая константа fsm.py")
        lines = [n for n, line in enumerate(source.splitlines(), start=1)
                 if LITERAL in line]
        self.assertEqual(lines, [], "литерал детали в тексте fsm.py")

        res = subprocess.run(
            [sys.executable, "-c", "import orchestrator.advance_gates.acceptance"],
            cwd=CODE_ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
