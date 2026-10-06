---
task: 01M48WRE8BHFDY011Q0HQGQ91B
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Предел полного прогона tests/ — поле профиля тестов проекта

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–8 и возврат из verifying 06.10; шаги проверяемые (код+тесты, регрессия БД).
- Требование 8: готовая строка для Оператора есть в «Влияние на систему» (внести `full_suite_timeout_sec: 1500` в `test_profile` артели + `artel.py doc-commit targets.yaml`).
- «Влияние на систему» совпадает с diff: 6 модулей зоны + новый `tests/test_full_suite_profile_timeout.py`; `FULL_SUITE_LOCK_WAIT_SEC`, `config.py`, `notes.py`, `targets.yaml` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py:47,51` — подполе в `PROFILE_FIELDS` и `PROFILE_OPTIONAL`, вид `positive_int`. |
| 2 | OK | `targets.py:145-147` — `type(value) is not int or value <= 0` отсекает bool, дробь, строку, ≤0; причина идёт через `_check_profile` с именем `test_profile.full_suite_timeout_sec`; `profile_of` → «не прочитан» (долгоживущий AC-2 зелёный). |
| 3 | OK | `project_profile.full_suite_limit` (стр. 155-163): подполе профиля либо `config.FULL_SUITE_TIMEOUT_SEC`, читаемый в момент вызова. |
| 4 | OK | Автогейт/approve/гейт мержа — через `acceptance.full_suite` (`acceptance.py:1105-1124`, предел из проекта задачи); `suite-run` — `suite_run.py:420,437,401` (ветка и база). `notes.py:1010` вне перечня требования 4 и вне зон — остаётся на config, корректно. |
| 5 | OK | Источник дописан к концу: `_full_suite_timeout_note` («…превысил Nс — завис… (источник: …)»), отказ гейта мержа «прогон не уложился в N с (источник: …; …)», отчёт `suite-run`, строка ожидания замка. Классификатор `_full_suite_outcome` переведён на литерал начала — совместим с `_PULT_BLAME_STARTS`. |
| 6 | OK | `doctor/cli.py:13-20,94` — строка по каждому проекту `targets.yaml`, включая проект без профиля (источник config). |
| 7 | OK | Новые тесты несут «Ловит мутацию»; существующие тесты в diff не менялись (diff `tests/` — только новый файл); `FULL_SUITE_LOCK_WAIT_SEC` не тронут. |
| 8 | OK | Строка в PLAN «Влияние на систему». |

## Замечания
- minor — `orchestrator/acceptance.py:1116`, `orchestrator/fsm_merge_gate.py:927` — `project_profile.full_suite_limit` поднимает `targets.TargetsError` на непрочитанном профиле, а `acceptance.full_suite` до задачи исключений по профилю не поднимал. Автогейт и гейт мержа защищены предшествующим `project_profile.decide` (`fsm_advance.py:195`, `fsm_merge_gate.py:126/776`), но `approve` в `acceptance` (`fsm.py:1141`) явного `decide` перед прогоном не делает, а гейт мержа пересчитывает предел ПОСЛЕ оборванного прогона. Сценарий: Оператор `doc-commit targets.yaml` с неверным значением во время долгого прогона мержа — вместо именованного отказа traceback на ветке таймаута. Узкое окно, на мерж не влияет; при случае — передавать в `_full_suite_or_refuse` предел, применённый прогоном (его уже несёт `run.detail`), а не перечитывать профиль.
- minor — `tests/test_full_suite_profile_timeout.py:33-70,72-88` — частично повторяет долгоживущие тесты задачи (ADR-0020 п.4): разбор значений (AC-1/AC-2 `…_profile_limit_field.py`), строка doctor (AC-8), предел гейта (AC-3). Новые свойства в файле — значение `true` (bool), регрессия «прямой прогон без БД не создаёт state.db» и `render` с пределом; остальное можно было не дублировать.
- minor — `tests/test_full_suite_profile_timeout.py:34,57,73,91,108` — докстринги состоят только из заявки «Ловит мутацию», без сценария и наблюдаемого свойства (skills/test-authoring.md). Заявки при этом наблюдаемы (таймаут/текст/наличие файла БД).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:1116; orchestrator/fsm_merge_gate.py:927 | `full_suite_limit` поднимает `TargetsError` вне защищённых `decide` путей | traceback вместо именованного отказа при сломанном профиле в узком окне | minor, правка не требуется для мержа; принято ревьювером как наблюдение |
| R1-F2 | accepted | tests/test_full_suite_profile_timeout.py:33-88 | частичный повтор долгоживущих тестов задачи | лишнее сопровождение, не ослабление | minor, правка не требуется; принято как наблюдение |
| R1-F3 | accepted | tests/test_full_suite_profile_timeout.py:34-108 | докстринги без сценария | читаемость тестов | minor, правка не требуется; принято как наблюдение |

## Вердикт
approved — blocker/major нет; три minor-наблюдения выше не блокируют мерж и в реестре закрыты как принятые.

## Проверено исполнением
- `python3 -m pytest tests/test_full_suite_profile_timeout.py tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py tests/test_project_profile.py tests/test_suite_run.py tests/test_doctor.py tests/test_fsm_autogate.py -p no:cacheprovider -q` — 166 passed, 8 subtests passed (21 с); `.artel/state.db` в рабочей копии после прогона не появился.
- `python3 -m pytest tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py tests/test_approve_acceptance_full_suite.py -p no:cacheprovider -q` — 19 passed, 2 subtests passed (50 с): AC-3/AC-4/AC-5/AC-6/AC-7 на настоящем гейте мержа и `suite-run`.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M48WRE8BHFDY011Q0HQGQ91B` — «планки нет: … нет файлов test_*.py»; планка задачи целиком в долгоживущих `tests/test_01m48wre8bhfdy011q0hqgq91b_*.py` (прогнаны выше).
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — расхождение только в `built_at_sha`, карта свежа; изменение откатил.
- Сверка путей: `grep -rn FULL_SUITE_TIMEOUT_SEC orchestrator` — константа читается только как умолчание (config-ветка резолвера/текстов); `acceptance.full_suite` вызывают `fsm_autogate.py:306`, `fsm.py:1141`, `fsm_merge_gate.py:920-921` — все получают предел проекта.
- Временную мутацию `run_kwargs = {}` в `acceptance.full_suite` выполнить не удалось (правка файла `sed -i` требовала подтверждения); полагаюсь на мутации, зафиксированные в PLAN, и на зелёные долгоживущие AC-3/AC-6, которые без подачи предела не прошли бы.
- CI коммита a192bb1e — зелёный (16 проверок, из пакета).

## Предложения системе
- Реестр замечаний schema ≥ 3 не различает minor «к сведению» и замечание, требующее правки: чтобы вынести `approved` с minor-наблюдениями, их приходится сразу ставить `accepted` самому ревьюверу — стоит дать отдельный статус/секцию для неблокирующих наблюдений (`skills/review-checklist.md`, `templates/REVIEW.md`).
