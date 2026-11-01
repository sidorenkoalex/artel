---
task: 01M6AB4VE2R0Q2V5D4MMJGNGH7
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

Ответ сессии при Операторе (права волны G) на эскалацию разработчика Б2.2, 01.11.2026.

1. **Вариант (а).** Метод `mr_status` общей подделки `FakeForge` (запись вызова, отказ при `fail["mr_status"]`, иначе открытый невлитый MR с `target_branch` базы) принимается как есть, по мандату Оператора 26.10 на тесты, которые меняет ADR-0029: это следствие решения ANSWER-2 п. 2 (отказ при сбое чтения статуса). Утверждения тестов не менять.

Ослабление тестов разрешено: tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac9_existing_link_undrafts_and_assigns, tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac11_undraft_or_assign_refusal_no_second_mr, tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac13_draft_on_verifying_undraft_on_gate

Независимая проверка: проверяющий сессии при Операторе 01.11 — «не ослабляет»: ни одно утверждение файла не снято и не смягчено сверх мандата на test_ac15; метод подделки состояние не меняет, утверждения об отсутствии слияния, отправки base и повторного open_mr остаются; путь отказа проверяется через fail["mr_status"].

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac9_existing_link_undrafts_and_assigns`: подделка `FakeForge` отвечает на `mr_status` | при существующей ссылке MR гейт снимает черновик и назначает исполнителя — `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` | остаётся | `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` (тот же тест, утверждения прежние) | ок |
| `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac11_undraft_or_assign_refusal_no_second_mr`: подделка `FakeForge` отвечает на `mr_status` | отказ снятия черновика или назначения не открывает второй MR — `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` | остаётся | `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` (тот же тест, утверждения прежние) | ок |
| `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py::test_ac13_draft_on_verifying_undraft_on_gate`: подделка `FakeForge` отвечает на `mr_status` | черновик со входа в verifying снимается на гейте — `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` | остаётся | `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380` (тот же тест, утверждения прежние) | ок |
