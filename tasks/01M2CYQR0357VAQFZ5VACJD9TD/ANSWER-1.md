---
task: 01M2CYQR0357VAQFZ5VACJD9TD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ответ Оператора на вопросы 1–2.

1. Вариант (б): `orchestrator/gates.py` (политика гейтов из gates.yaml,
   `policy`/`AUTO`/`MANUAL`) не трогать, `fsm_autogate.py` и
   `tests/test_gates.py` не трогать. Новый пакет называется
   `orchestrator/advance_gates/` («гейты переходов fsm_advance»), состав
   файлов тот же: `__init__.py`, `_base.py`, `zones.py`, `capacity.py`,
   `review.py`, `acceptance.py`, `tests_writing.py`. Везде в SPEC, где
   написано `orchestrator/gates/`, читать `orchestrator/advance_gates/`;
   требование 1 и AC-1 считаются изменёнными этим ответом текстуально
   (путь пакета), по существу — без изменений. Коллизия имени — дефект
   ТЗ (ревизия назвала пакет, не сверив имя с существующим модулем),
   не роли; спасибо за стаб-валидацию.
2. Не актуален (выбран вариант (б)).

Расширение зон разрешено: orchestrator/advance_gates/__init__.py,
orchestrator/advance_gates/_base.py, orchestrator/advance_gates/zones.py,
orchestrator/advance_gates/capacity.py, orchestrator/advance_gates/review.py,
orchestrator/advance_gates/acceptance.py,
orchestrator/advance_gates/tests_writing.py

Продолжай с tests_writing: планка — по новому пути пакета; AC-3 снимается
с escalate (полный набор зелёный проверяет CI/автогейт, пометка skip с
причиной либо тест на импорт `orchestrator.gates.policy` после переноса —
на выбор автора тестов). Пометки manual AC-4/AC-5/AC-6 приняты.
