# Записка spec_auditor 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- Четвёртый визит (spec_sha 829d7807…). Решения гейта №1 (Т-1, Т-2, Ф-1) и
  №2 (Е-1 — эскалация пульта = unknown по маркеру; В-1 — уровень подмены) в
  SPEC отражены.
- Главная находка Ф-1 (fail): SPEC требует, чтобы маркер
  `ARTIFACT_ESCALATION_ROLE_STEP_MARKER` стоял записью СРАЗУ за
  `state -> escalated`. В коде так не бывает: `store.set_state`
  (store.py:820-827) после `_cas_state` (журнал `state -> escalated`, :852)
  зовёт `record_fixation`, который пишет «sha зафиксирован» (store.py:966),
  и только потом вызывающий пишет маркер (fsm_advance.py:290-292 и др.).
  При дрейфе ссылки — `fixation.journal_drift` (store.py:829). Тест
  tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py:168-170
  фильтрует «sha зафиксирован» и actor lease, чтобы увидеть маркер «следующим».
  Буквальная реализация: каждая эскалация роли → unknown, любой прогон с
  ловушкой не чистый (хуже main). Синтетические журналы AC-1/2/3/11 без
  «sha зафиксирован» этого не ловят.
- Прочие адреса подтверждены: budget.py:300, fixation.py:248, runner.py:447/:800,
  fsm_advance.py:347/:482 (verifying без маркера), models.py:1128/1136/1174,
  config.py:805, catalog.py:667/670, canary.py:291/1734-1747/1848/2146/2232/2361/2504,
  store.py:1442 (DDL), :1516 insert_canary_run, canary_drive.py:41 STEP_FIELDS.

## Не сработало
- `ls` в Bash недоступен (command not found).

## Где остановился
- SPEC-AUDIT.md: verdict fail (Ф-1 + следствия В-2, Е-1).

## Чего не хватило
- Порядок записей журнала внутри `store.set_state` (фиксация пишет свою запись после перехода) — нашёл чтением store.py:775-966.
