---
task: 01M56TNTY7HEC85MC940KZR1ZJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Гейт неослабления: помощники по области ослабления проекта

## Подход
Режим прослеживания помощников несёт `guard.TestModules` — один объект
стороны сравнения, который и так получают все места разбора
(`test_assertions`, `_assertion_records`, `changed_classes`,
`method_literal_keys`). Новые необязательные аргументы
`TestModules(load, external=False, workdir="", in_scope=None)`; без них
поведение артели при любом `workdir` (требования 2, 6). У внешнего режима:
- имя модуля `a.b` → `<workdir>/a/b.py` (без `workdir` — `a/b.py`), модуль
  виден, только если путь входит в область (`in_scope`), без проверки
  первого сегмента `tests` (требования 1, 5);
- относительный импорт разрешается от пути файла без префикса `workdir`
  (`backend/tests/test_y.py` → пакет `tests`), затем тот же перевод с
  `workdir` (требование 4);
- функция импортированного модуля области — помощник (не только
  `tests/sandbox.py`); префикс `test_` по-прежнему отсеивается.
`method_literal_keys` не меняется: режим приходит через свой аргумент
`modules`; вызов `fsm.py:1053-1060` не правится.

В `test_integrity._evaluate` (общий узел трёх входов) режим и профиль
читаются по `task_id`: `repo_context.is_artel(store.task_target(...))`,
профиль — `project_profile.decide`. У внешнего проекта область узла,
модулей и поиска вызывающих — `weakening_scope` профиля, `git grep` идёт
без pathspec `tests/` с отсевом по области; у артели всё как сейчас.
`review.py` и `fsm_merge_gate.py` не правятся (требование 3).

## Шаги
1. `scripts/guard.py`: режим в `TestModules`, перевод имени модуля и
   относительного импорта с `workdir`, функция модуля области — помощник
   у внешнего проекта.
2. `orchestrator/advance_gates/test_integrity.py`: чтение режима/профиля
   на `_evaluate`, передача в `_compare` → `_side_modules`,
   `_helper_callers` по области у внешнего проекта.
3. Юнит-тесты guard (обратная совместимость без аргументов,
   `workdir` без режима не действует, перевод с `workdir`, базовый класс
   модуля области, `method_literal_keys` с модулями внешнего режима) в
   `tests/test_guard_helper_scope_modes.py`; регенерация карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 3 |
| 3 | 2 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1, 3 |
| 7 | 1, 2 (AC-5 долгоживущего файла) |
| 8 | 3 |

## Влияние на систему
Инвариант 38 (гейт неослабления) усиливается для внешних проектов:
помощники и вызывающие под `workdir` теперь видны. У артели код идёт по
прежним веткам (режим не включается: `is_artel` истинен), AC-5
долгоживущего файла фиксирует пять прежних исходов. Узел у внешнего
проекта при отсутствии профиля остаётся на переданной области (как
раньше). Откат — revert merge-коммита.

## Риски
- `git grep` без pathspec у внешнего проекта шире по объёму вывода —
  отсев по области сразу после.

## Проверка
- `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py` (долгоживущий,
  AC-1..AC-5) — 5 passed, 8 subtests.
- `tests/test_guard_helper_scope_modes.py` — 6 passed; временные мутации
  (режим из `workdir`, без нормализации `workdir`, без сверки с областью,
  функции только из песочницы у внешнего, перевод без `workdir`) —
  каждая красит свой тест.
- Тесты затронутых модулей зелёные: `tests/test_test_integrity_gate.py`
  (51), `tests/test_test_integrity_helper_heirs.py`,
  `tests/test_guard_helper_scope.py`, `tests/test_guard_assertion_changes.py`,
  `tests/test_guard_test_ast.py`, `tests/test_guard_mutation_claim.py`,
  `tests/test_01m4g8n9kbtvnnt7ygz59q5wbf_helper_assertions.py`,
  `tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py` (72).
- Карта регенерирована `python3 scripts/codebase_map.py`.

## Предложения системе
- `pytest -n` (xdist) в шаге роли падает «node down: Not properly
  terminated» на всех воркерах — тесты затронутых модулей приходится гнать
  последовательно, это > 10 минут.
- Причина возврата с приёмки не несёт команды воспроизведения и пути лога
  ручного прогона — роль не может повторить «2 из 2» в том же окружении.
  Стоит требовать команду и лог в тексте `reject` для падения вне
  fullsuite-логов.
- `test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` чувствителен ко
  времени: `time.sleep(0.01)` и `time.sleep(4.0)` одной длины, а кеш байткода
  `.pycache-warm` сверяет только mtime и размер. Это кандидат во флаки под
  нагрузкой (задача на тест — через Оператора, файл долгоживущий).

## Возврат с приёмки (ANSWER-1)
Оператор признал возврат по ac8
`tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` ошибочным: тест
красный на любом коммите (в том числе на origin/main 6019e421) при прямом
pytest из сессии Оператора, но зелёный в CI main и в `suite-run` №1 ветки.
Падение зависит от окружения запуска, не от кода ветки. По ответу код и
тесты не менялись; артефакты сданы повторно как есть.

Разбор, проведённый до ответа (ветка, HEAD 4222b94f):
- `python3 -m pytest tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal`
  зелёный 4 раза из 4 (≈17 с). Весь файл — 6 passed (57 с). Вместе с
  `tests/test_01m56tnty7hec85mc940kzr1zj_helper_scope.py` и
  `tests/test_guard_helper_scope_modes.py` — 17 passed.
- `artel.py suite-run 01M56TNTY7HEC85MC940KZR1ZJ` №1 (полный набор ветки):
  зелёный, 5772 passed, 0 failed, 2 skipped. Лог:
  `.artel/logs/suite-run/01M56TNTY7HEC85MC940KZR1ZJ/01M56TNTY7HEC85MC940KZR1ZJ-suiterun-1.log`.
- В журнале задачи упавшие fullsuite-1 и fullsuite-2 не содержат ac8: там
  ac6 этого файла и doctor-тесты чужих задач под нагрузкой (load ≈ 30 на 14
  ядер, замок был у гейта задачи 01M56T94ZJE6H973HEBTM0Q0TD).
- Путь `doctor_checks` → `doctor.all_checks` →
  `doctor/suite_duration.check_suite_duration`; измерения пишет
  `acceptance.full_suite` → `run_full_suite` → `_suite_metrics`. Ни один из
  этих модулей не зовёт `guard.TestModules`, `_HelperScope`, `_module_entry`
  или `advance_gates/test_integrity` (grep по `orchestrator/doctor/` и
  `orchestrator/acceptance.py`). `acceptance.py` берёт из guard только
  `scan_acceptance_tests`/`count_test_methods`/`TEST_METHOD`, а их ветка не
  меняла (diff ветки — `scripts/guard.py`, `test_integrity.py`, тесты и
  карта).
- «6 с» на 9 прогонов pytest с паузой 4 с в девятом выглядит как пропуск
  паузы. Под это подходят исполнение старого байткода: строки
  `time.sleep(0.01)` и `time.sleep(4.0)` одной длины, а `.pycache-warm`
  сверяет только mtime и размер. Ещё подходит не начавшийся прогон. Ни
  то, ни другое не зависит от кода ветки.
