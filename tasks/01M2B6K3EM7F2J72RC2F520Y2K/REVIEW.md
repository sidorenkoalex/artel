---
task: 01M2B6K3EM7F2J72RC2F520Y2K
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Признак роли в окружении и conftest вместо хука роли

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ARTEL_ROLE/ARTEL_TASK в role_env, константы config.py) | OK | Без изменений с итерации 1. `orchestrator/config.py:47-56` — `ARTEL_ROLE_ENV`/`ARTEL_TASK_ENV`; `runner.role_env(role, task_id)` (`orchestrator/runner.py:543,597-600`) кладёт обе переменные только если значение передано; вызов `run_agent_once` передаёт `task_id` (`runner.py:790`). Тесты `tests/test_multitarget.py::RoleEnvTest` — зелёные. |
| 2 (conftest.py — гейт сбора pytest «теми же критериями, что bash_guard._pytest_verdict») | OK | Итерация 1 нашла R1-F1 (`any()` вместо репликации семантики хука — смешанный вызов `pytest <файл> tests` проходил гейт, реально собирая весь `tests/`). Коммит `c331a52e` заменил условие на `not positionals or not all(_is_targeted_path(p) for p in positionals)` (`conftest.py:72-74`) — теперь блокирует, если позиционных аргументов нет ИЛИ среди них есть хотя бы один нецелевой, что верно реплицирует старую семантику «любой нецелевой путь топит весь вызов». Добавлен регресс `tests/test_conftest_role_guard.py::test_mixed_targeted_and_whole_tree_blocked_under_role` с докстрингом «Ловит мутацию: … `any()` вместо `all(...)`» — сценарий описан точно, не пересказ имени метода. Прогнал вручную: тест красится при откате `all` на `any` (проверено чтением diff — старое условие `not any(...)` пропускает `["tests/test_slugify.py", "tests"]`, поскольку `any()` истинно на первом аргументе; новое `not all(...)` ловит его, поскольку второй аргумент не целевой) и зелен на текущем коде (см. «Проверено исполнением»). |
| 3 (artel.py — отказ init/doctor --restore/canary pool-seal под ARTEL_ROLE) | OK | Без изменений с итерации 1. `_role_restricted_command`/`_refuse_if_role_restricted` (`orchestrator/artel.py:737-763`), вызов до диспетчерской таблицы (`main()`, строка 771). `tests/test_artel_role_restricted_commands.py` — зелёные. |
| 4 (курируемый слой: убрать hooks.PreToolUse и hooks/bash_guard.py, permissions.deny не тронут) | OK | Без изменений с итерации 1. `settings.json` не несёт `hooks` (diff коммита 592175ce убирает только блок `hooks`, `permissions.deny` — те же 7 записей строка в строку); `hooks/bash_guard.py` и каталог `hooks/` удалены. |
| 5 (тесты покрывают требования 1-4 без ослабления существующих) | OK | Пробел итерации 1 (ни один тест не покрывал смешанный сценарий R1-F1) закрыт новым тестом. `tests/test_doctor.py::RoleHomeReferenceHooksDirTest` → `RoleHomeReferenceSettingsFileTest` — переименование легитимно, докстринги обоих методов несут «Ловит мутацию: …», проверяемое свойство `_role_home_diff` (отсутствие/расхождение файла референса → warn) сохранено, просто на другом файле-примере (`settings.json` вместо снятого `hooks/bash_guard.py`). `tests/test_role_bash_guard.py` удалён целиком — гарантия перенесена в `test_conftest_role_guard.py`/`test_artel_role_restricted_commands.py` (допустимо по AC-7). |

Дополнительно:
- AC-8 (PLAN.md называет факт «дом не переписывается автоматически») — OK, раздел «Влияние на систему» PLAN.md (строки 118-128) содержит нужный факт.
- AC-9 (runner/catalog/doctor без ослабления) — OK, единственная правка `test_doctor.py` — легитимный ренейм с сохранением свойства (см. выше).
- Расширение зоны на `docs/reference/role-home.md` — правомерно, мандат ANSWER-2.md.
- Диапазон изменений этой задачи проверен отдельно от diff-пакета (пустой инкрементальный diff пакета указывал на sha, совпадающий с текущим HEAD — не на коммит вердикта итерации 1): весь код задачи лежит в одном коммите `592175ce` + фикс `c331a52e`; всё остальное в `git diff main...HEAD` (canary.py, notes.py, lease.py, fsm_advance.py, docs/backlog.md, skills/test-authoring.md и т.д.) — чужие изменения main, попавшие в ветку подтяжкой (`e9a0069f`), не тронуты коммитами этой задачи (подтверждено `git log -- <файл>` — авторы те же операторские копилки/задачи, не 592175ce/c331a52e).

## Замечания

(нет — R1-F1 устранено, новых дефектов не найдено)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | conftest.py:72-74 | Гейт сбора pytest блокировал по `any(целевой путь)`, а не по репликации `bash_guard._pytest_verdict` | Смешанный вызов `pytest <файл> tests` проходил гейт, реально запуская весь `tests/` внутри шага роли | Условие заменено на `not positionals or not all(_is_targeted_path(p) for p in positionals)`; добавлен и прогнан регресс-тест `test_mixed_targeted_and_whole_tree_blocked_under_role` — подтверждено чтением diff (`c331a52e`) и повторным прогоном (см. «Проверено исполнением»); суть устранена, реестр закрыт |

## Вердикт

approved — все требования SPEC (1-5, AC-1..AC-9) реализованы и покрыты тестами; R1-F1 из итерации 1 устранено корректно, реестр замечаний закрыт целиком.

## Проверено исполнением

- `python3 -m pytest tests/test_conftest_role_guard.py tests/test_multitarget.py tests/test_artel_role_restricted_commands.py tests/test_doctor.py -q` — 198 passed, 17 subtests passed (55.56s), без падений.
- `python3 -m pytest tasks/01M2B6K3EM7F2J72RC2F520Y2K/acceptance_tests/ -q` — 24 passed, 1 skipped (AC-7: легитимный skip, `test_role_bash_guard.py` удалён целиком).
- `git show c331a52e -- conftest.py tests/test_conftest_role_guard.py` — прочитан построчно: условие гейта и новый тест `test_mixed_targeted_and_whole_tree_blocked_under_role` с докстринг-заявкой «Ловит мутацию: …», описывающей сценарий и наблюдаемое свойство, не пересказ имени.
- `git show 592175ce -- orchestrator/config.py orchestrator/runner.py orchestrator/artel.py docs/reference/role-home/claude/settings.json tests/test_doctor.py` — построчная сверка реализации требований 1, 3, 4 и ренейма теста doctor с SPEC/PLAN — совпадает без ослаблений.
- `python3 scripts/codebase_map.py` (сравнение с `docs/codebase-map.md` без строки `built_at_sha`) — расхождений нет, карта свежая.
- `git diff main...HEAD --stat` и `git log --oneline -- <файл>` для файлов вне зоны задачи (docs/backlog.md, skills/test-authoring.md, orchestrator/canary.py и др.) — подтверждено, что это чужие изменения main, попавшие подтяжкой (e9a0069f), не коммитами этой задачи.

## Предложения системе

- Диапазон «sha предыдущего вердикта» в ревью-пакете этой задачи снова совпал с текущим HEAD вместо коммита реального вердикта итерации 1 (`3f66c01a`) — тот же класс, что уже описан в скиле (T082, T087). Здесь причина третья: между коммитом вердикта и HEAD лежит коммит-фикс разработчика (`c331a52e`), который сам стал новым HEAD кода, и пакет посчитал diff от него же до себя. Возможный адрес: инкрементальный diff пакета вычислять от sha, зафиксированного в предыдущем REVIEW.md (git log по самому файлу), а не от отдельно хранимого указателя «sha предыдущего вердикта».
