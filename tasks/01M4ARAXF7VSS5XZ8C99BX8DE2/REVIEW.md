---
task: 01M4ARAXF7VSS5XZ8C99BX8DE2
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Нагрузка машины в записи полного прогона и сигнал роста времени прогона

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Гейт собирает и журналирует метрики на зелёном, красном и таймаутном исходах; для таймаута счётчик и время на тест остаются пустыми. Решением Оператора из ANSWER-1 запись `suite-run` не требуется и запрещена. |
| 2 | OK | Таймауты гейта и `suite-run` используют одну строку снимка нагрузки. |
| 3 | OK | Добавлена проверка `machine-load`: только `ok`/`warn`, с обоими условиями и требуемыми полями сообщения. |
| 4 | OK | `suite.duration` фильтрует записи без времени на тест, разделяет непрерывные суффиксы по числу xdist-процессов, применяет окно из 8 записей и перенос точки отсчёта по ack. |
| 5 | OK | PLAN содержит точный текст строки для `docs/triggers.md`. |
| 6 | OK | PLAN содержит ряд 02.10–07.10, число xdist и расчёт порога внутри группы из 14 процессов. |

Фаза A: план покрывает все требования проверяемыми шагами; решение Оператора по отмене AC-2 и изменению AC-5 учтено со ссылкой на ANSWER-1. Подход согласован с существующим `map.growth` и сохраняет инвариант неизменности журнала задачи у `suite-run`.

Фаза B: diff соответствует SPEC и заявленному влиянию на систему. Новые и изменённые тесты содержат содержательные заявки «Ловит мутацию»; долгоживущие сторожа проверяют запись метрик, исключение дерева pytest, таймаутные строки, условия нагрузки и калибровку сигнала. Ослабления существующих утверждений и изменения защищённых путей отсутствуют.

## Замечания

Нет.

## Реестр замечаний

Замечаний для регистрации нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4ARAXF7VSS5XZ8C99BX8DE2` — 1 passed.
- `python3 -m pytest -q tests/test_suite_duration.py tests/test_suite_run.py` — 17 passed, 4 subtests passed.
- `python3 -m pytest -q tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py` — 7 passed.
- `git diff --check 21e5493b00161ddd6bbf51bf493814120e9b9b03...HEAD` и `python3 -m py_compile` для всех изменённых модулей — без ошибок.
- `python3 -m pytest -q tests/test_acceptance.py tests/test_doctor.py` — 133 passed, 5 subtests passed; один отказ `MaterializeFromBranchGitFailureTest::test_none_from_ls_tree_files_leaves_existing_plank_untouched` воспроизводит известную проблему пустой таблицы `tasks` в окружении теста до затронутых этой задачей функций.

## Предложения системе

- Локальный прогон `tests/test_acceptance.py` подтверждает наблюдение PLAN: `MaterializeFromBranchGitFailureTest` зависит от внешней схемы БД и падает до проверяемого сценария. Нужна изолированная фикстура схемы для этого класса.
