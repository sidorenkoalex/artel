---
task: 01M2A22CG2P0E69H00RDHFF3K4
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

## Ответы

1. Планка красная не из-за подтяжки main, а из-за сигнатуры: приёмочные
   тесты (залочены, `test_spec_gate_artifact_source.py:102,136,156`)
   зовут `_spec_gate_next_state(conn, task_id, t)` тремя аргументами —
   так функция объявлена в main (`orchestrator/canary.py:513`), и SPEC
   сигнатуру не меняет. Ты убрал параметр `t`, и планка падает с
   `TypeError`. Разрешение: вернуть сигнатуру `_spec_gate_next_state(conn,
   task_id, t) -> str`; `t` остаётся третьим позиционным параметром
   (допустимо не использовать его в теле — источник SPEC определяется
   только через `artifact_source.resolve(conn, task_id)`, AC-4), вызов в
   `_pass_spec_gate` — прежний, с `t`. Планку не править. После правки
   прогони планку и `tests/test_canary.py`, сдай шаг как обычно.
