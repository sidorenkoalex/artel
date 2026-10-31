---
task: 01M5XZ9Z68XE2EKPDHYCAK25KF
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

Расширение зон разрешено: orchestrator/amend.py

мандат Оператора: orchestrator/amend.py

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `orchestrator/amend.py`: вызов проверки предела `max_in_flight` первым действием `_cmd_amend_tests` | правка планки `amend-tests` коммитится и отправляется, `tests_locked_sha` сдвигается только после успешной отправки — `orchestrator/amend.py:840` | остаётся | `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:1396` (AC-17, дополняется: отказ до коммита, снимок ветки и `tests_locked_sha` до и после равны) | ок |
| `orchestrator/amend.py`: то же | предел `max_in_flight` в единой точке отправки `gitcmd` — `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:1396` | остаётся | `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:1396` | ок |
| `orchestrator/amend.py`: то же | путь `amend-tests` для проектов без `max_in_flight` (артель, `operator`) — `tests/test_amend.py:1` | остаётся | `tests/test_amend.py:1`, `tests/test_amend_long_lived.py:1` без правки | ок |
