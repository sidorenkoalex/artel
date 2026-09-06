---
task: 01M1VBEDGMEXHVGWAH42FTDZ4X
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на эскалацию «конфликт подтяжки main» (06.09.2026).

Причина: кодовая ветка стартовала от c4f89371 (пин на момент `new`), а
в origin/main с тех пор смержен ADR-0015 «CI до ревью» (01M1TQ0TRC):
из `fsm_advance.review()` убран блок `if status == "approved": …
_origin_push_gate` — рубеж origin-push переехал в `in_dev`
(`_origin_push_gate` вызывается там, строка ~1123 на main). Правка
ветки добавила `_review_escalation_sha_gate` именно в этот удалённый
блок — конфликт содержимого; второй конфликт — `docs/codebase-map.md`.

Что сделать разработчику в этом ходе (логику задачи не менять):
1. Завершить подтяжку: `git merge origin/main` в worktree. В
   `orchestrator/fsm_advance.py::review()` принять сторону main
   (блока с `_origin_push_gate` в `review()` больше нет и возвращать
   его нельзя) и вставить только свой гейт — после
   `_freshness_refuses(...)` и до `iteration = artifacts.
   fresh_verdict_iteration(...)`:

       if status == "approved":
           if _run_gates(conn, task_id,
                         [lambda: _review_escalation_sha_gate(conn, task_id, t)]):
               return False

   Проверка `t["is_canary"]`/`_origin_push_gate` из своей вставки
   не переносится — она относилась к удалённому блоку.
2. `docs/codebase-map.md` взять из origin/main и перегенерировать
   штатным `python3 scripts/codebase_map.py`, закоммитить.
3. Прогнать `tests/test_fsm_review_rework_sha_gate.py`,
   `tests/test_budget_live_lease_and_escalation.py`,
   `tests/test_auto_escalated_return_rework_gate.py`,
   `tests/test_fsm_advance*.py` и планку из worktree
   (`python3 -m unittest discover -s
   tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests`), сдать шаг.

Учесть новый порядок состояний ADR-0015 (in_dev -> verifying -> review):
если тесты ветки предполагают старый порядок, поправить тесты, не
механику. Планку не править. Бюджет $70 — запас есть.
