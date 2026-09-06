# RETRO: 01M1NBWPKNBXP9ZXXQDJM7AXPJ — Сверка свежести ветки против main артели на origin

Итог: done, sha b3c44ad530027f962f81c1411b7d056b913bee1e
Адрес артефактов: b3c44ad530027f962f81c1411b7d056b913bee1e:tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/
Суть: Сверка свежести ветки против main артели на origin

Стоимость итого: $76.46
  analyst: $1.32, 1940173 токенов
  test_author: $8.27, 16881765 токенов
  developer: $44.45, 103897701 токенов
  reviewer: $18.65, 36433273 токенов

Ревью: 2 итераций; приёмка: 0 отказ(ов)

Эскалации: 4 (последняя): потолок ожидания CI в verifying исчерпан (5400с) — последний статус: CI коммита 7a60674d ещё идёт: Валидация артефактов, Синтаксис и тесты оркестратора

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip

## Правка планки (amend-tests) — 01M1TKP45EM16ZMJGQKNZA5T7J

`tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/_sandbox.py`:
`OriginDivergedSandbox` заводила задачу голым `catalog.cmd_new` без
материализованной приёмочной планки — черновой SPEC.md по умолчанию
(`schema_version: 4`, без `skip_tests`) требовал AC-разметку
(`guard.requires_ac_markup`), а `acceptance_tests/` не нёс ни файла:
`_pull_main_or_escalate` отказывала «планка не найдена в источнике» до
предмета проверки самих тестов (6 из 9 тестов планки красны). Контракт
изменился ПОСЛЕ того, как эта планка была написана (SPEC
01M1R9YEK08XEQWBFX0929WFVJ добавила материализацию/сверку планки узлу
подтяжки) — класс дефекта (б) из «Контекста» SPEC
01M1TKP45EM16ZMJGQKNZA5T7J. Правка: `OriginDivergedSandbox` коммитит
непустую `acceptance_tests/` со SPEC.md `schema_version: 2` без
`skip_tests` в артефактную ветку задачи плотницки (`artifact_branch.
commit_files`, тот же приём, что уже несёт `write_plan_ready`) до
запуска сценариев тестов. Ни один существующий assert не ослаблен —
только исправлена подготовка песочницы под уже сдвинувшийся контракт.
