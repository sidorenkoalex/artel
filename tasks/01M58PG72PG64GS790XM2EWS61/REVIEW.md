---
task: 01M58PG72PG64GS790XM2EWS61
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: G1а-2: компоненты проекта — проверки doctor (версии инструментов, карта путей CI, каталоги) и ключ кэша итога

## Фаза A — план
- Таблица покрытия полна (требования 1-13 → шаги 1-4). В «Проверке» добавлена итерация 3: сторож R2-F1, временная мутация, `suite-run` №3 зелёный.
- «Влияние на систему» сходится с diff итерации: менялся только `tests/test_component_checks.py` (+50/−1), код не трогали.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1-8 | OK | код не менялся с итерации 1; долгоживущий файл задачи зелёный |
| 9 | OK | `decide` держит `DecideToolsTest`, `_task_own_profile` — `TaskOwnProfileToolsTest` (новый); оба входа под сторожем |
| 10 | OK | `ToolsKeyTest` (принят в итерации 2) |
| 11 | OK | `test_base_key_ignores_tools_and_locks` |
| 12 | OK | пустые `tools` у `test_profile` `pytest-own` — новый тест; AC-15 планки зелёный |
| 13 | OK | новый тест без сети: учебный `targets.yaml` во временном каталоге, `store.task_target` подменён |

## Замечания
Новых замечаний нет. Новый тест `TaskOwnProfileToolsTest` (tests/test_component_checks.py:251-285) несёт заявку «Ловит мутацию: `_task_own_profile` не зовёт `with_tools` — `tools` пусты», и заявка исполнима: при этой мутации тест краснеет (проверено мной). Соединение `sqlite3.connect(":memory:")` в тесте нужно, чтобы пройти проверку `isinstance(conn, sqlite3.Connection)` (acceptance.py:2453), — сам `store.task_target` подменён. Повтора долгоживущего файла задачи нет: этот файл проверяет doctor, вход `_task_own_profile` он не трогает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | orchestrator/acceptance.py:2464-2465; tests/test_component_checks.py:251-285 | у вызова `with_tools` в `_task_own_profile` не было сторожа в `tests/` | — | accepted (reviewer, итерация 3): `TaskOwnProfileToolsTest::test_task_own_profile_carries_single_component_tools`; временная мутация acceptance.py:2464 (`profile = Profile.from_values(answer.values)` без `with_tools`) краснит ровно этот тест (1 failed, 10 passed), код возвращён |

## Вердикт
approved — R2-F1 закрыто, реестр закрыт целиком (R1-F1 и R1-F2 приняты в итерации 2). Blocker и major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_component_checks.py` — 11 passed.
- Временная мутация: в acceptance.py:2464-2465 убран вызов `project_profile.with_tools(...)`, после чего `tests/test_component_checks.py` дал 1 failed (`TaskOwnProfileToolsTest::test_task_own_profile_carries_single_component_tools`, строка 282) и 10 passed. Файл восстановлен через `git checkout`, `git status` чистый.
- `python3 -m pytest -q tests/test_component_checks.py tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py tests/test_01m58fnwbv25ff26e7az9q9912_components.py` — 34 passed, 166 subtests passed.
- `python3 …/artel.py plank-run 01M58PG72PG64GS790XM2EWS61` — 4 passed, код выхода pytest 0.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — отличается только строка `built_at_sha`, по содержимому карта свежая; файл возвращён.
- CI коммита 573e58f9 зелёный (16 проверок, данные из пакета).

## Предложения системе
