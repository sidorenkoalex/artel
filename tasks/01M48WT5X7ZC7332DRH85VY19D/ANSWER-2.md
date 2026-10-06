---
task: 01M48WT5X7ZC7332DRH85VY19D
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Решение Оператора 07.10 по эскалации разработчика: вариант А — правка зафиксированного теста, привести вызов гейта к настоящему поведению гейта мержа.

Ослабление тестов разрешено: tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::BaseComparisonTest::test_ac13_gate_full_suite_result_is_reused_as_base

Объём мандата — ровно одна правка: вызов гейта в методе (`acceptance.full_suite(gate, self.task_id())`, ~строка 880) получает команду профиля тестов этого проекта — ту же, что берёт suite-run, `command=[str(self.python), "-m", "pytest"]` (как `fsm_merge_gate.py:920–921` передаёт команду профиля). Утверждения метода (`len(self.base_calls()) == before`, `phrase_number(out, ALSO_ON_BASE) == n_base`, `assertFalse(result.green)`) и его докстринг-заявка «Ловит мутацию» не меняются; другие методы и файлы под этот мандат не попадают. Ключ (требования 1 и 12) остаётся строгим: разные собранные команды — разные ключи, интерпретатор из ключа не убирается.

Расхождение автогейта и approve (вызов full_suite без команды профиля, fsm_autogate.py:306, fsm.py:1141) с гейтом мержа — вне задачи, записано Оператором в копилку; в этой задаче не исправлять.
