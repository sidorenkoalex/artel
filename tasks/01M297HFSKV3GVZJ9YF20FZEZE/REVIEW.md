---
task: 01M297HFSKV3GVZJ9YF20FZEZE
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: база ветки задачи — origin/main, а не локальный пин; doctor и new видят непушенные коммиты главной копии

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`workspace.ensure` от `origin/<MAIN_BRANCH>`, AC-1..AC-3) | реализовано не так | Реализация буквально верна для прямого self-сценария (`orchestrator/runner.py::role_cwd`, `orchestrator/amend.py`, `orchestrator/pull.py` — реальный `origin`, fetch проходит), но ломает СУЩЕСТВУЮЩЕГО потребителя того же self/артель-пути — `orchestrator/canary.py::_run_one_task` — см. R1-F1. |
| 2 (`doctor` `pin-unpushed`, AC-4..AC-6) | OK | `check_pin_unpushed`/`fetch_origin_main_sha`/`unpushed_commits` в `orchestrator/doctor/root_pin.py` реализуют fail/ok/warn ровно по критериям; зарегистрирована в `orchestrator/doctor/cli.py::all_checks` (проверено юнит-тестом wiring). |
| 3 (`cmd_new` предупреждение + журнал, AC-7/AC-8) | OK | `_warn_pin_divergence`/`_pin_divergence_warning_text`/`_pin_divergence_journal_detail` в `orchestrator/catalog.py` — заведение не блокируется, при отказе fetch — тихо (AC-8). Внутри `_ephemeral_clone` канарейки fetch к `ORIGIN_STUB_URL` тоже отказывает — эта функция деградирует туда безопасно (сама по себе не роняет `cmd_new`), в отличие от R1-F1. |
| 4 (тесты) | реализовано не так | Новые/правленые тесты в `tests/` — зелёные (см. «Проверено исполнением»), но зафиксированный ранее приёмочный тест ДРУГОЙ задачи (`tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac2_ac4_ephemeral_clone_lifecycle.py`), покрывающий тот же self/артель-путь через `_ephemeral_clone`, теперь падает — см. R1-F1. Требование 4 явно говорит «существующие тесты… остаются зелёными без ослабления», без оговорки «только `tests/`». |

## Замечания

- blocker — `orchestrator/workspace.py:73-82` (взаимодействует с `orchestrator/canary.py:1018-1034`) — новый обязательный `git fetch origin <MAIN_BRANCH>` перед заведением НОВОЙ ветки задачи ломает канареечный прогон: `canary._ephemeral_clone` (`orchestrator/canary.py:496-502`) намеренно ставит `origin` на нерабочую схему `ORIGIN_STUB_URL = "canary-stub://ephemeral-clone-no-real-remote"`, чтобы канарейка не трогала настоящую сеть/пул. До этой задачи `workspace.ensure` заводил новую ветку от ЛОКАЛЬНОГО `config.MAIN_BRANCH` эфемерного клона (сеть не нужна) — теперь для ЛЮБОЙ новой ветки задачи (а канареечная задача ВСЕГДА новая — `_new_task_row` строку в БД заводит, git-ветку не создаёт) обязателен успешный fetch, который в этом клоне гарантированно проваливается. Итог — `RuntimeError("canary: worktree для <id> не создан: база ветки недоступна: fetch origin не удался: …")` на каждом (без исключений) канареечном прогоне, то есть `artel.py canary --k N` полностью неработоспособна этим диффом. Это тот самый self/артель-путь, который SPEC явно относит к своей зоне (ANSWER-2: «новая способность касается только self/артель»), и материалы самой задачи опираются на зелёный канареечный прогон как гейт `pin-update` — то есть чинится ровно тот механизм, который эта же задача и ломает.
  Предложение: либо `_ephemeral_clone` заранее наполняет фейковый `origin` реальным содержимым локального main (например, `git remote set-url origin <path-к-исходному-клону>` вместо недостижимой схемы, или отдельный bare-клон рядом), либо `workspace.ensure`/`canary._run_one_task` получают явный путь без fetch для уже пойманного «canary-режима» (например, если ветка целиком заводится этим же вызовом канарейки, использовать локальный `config.MAIN_BRANCH` эфемерного клона напрямую) — в любом случае перед сдачей нужно ПРОГНАТЬ существующий зафиксированный сценарий, см. «Проверено исполнением» (воспроизведено детерминированно).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/workspace.py:73-82 (+ orchestrator/canary.py:1018-1034, 496-502) | Обязательный `git fetch origin` в `workspace.ensure` несовместим с намеренно нерабочим `origin` `canary._ephemeral_clone` | `artel.py canary --k N` падает `RuntimeError` на каждом прогоне — канареечный гейт `pin-update` неработоспособен | `_ephemeral_clone` (`orchestrator/canary.py`) теперь после клона `dest` заводит ОТДЕЛЬНЫЙ одноразовый bare-клон `origin_dir` (`git clone --bare --shared dest origin_dir`, `--shared` — чтобы не удваивать копирование объектов пульта и не подрывать временной запас AC-8/AC-9/AC-11) и ставит `origin` клона на его путь вместо несуществующей схемы `ORIGIN_STUB_URL` (константа убрана); `origin_dir` убирается вместе с `dest` в `finally`. `git fetch origin <MAIN_BRANCH>` внутри клона теперь проходит локально (без сети и без обращения к `outer_root`/пулу), push по-прежнему не покидает пару временных каталогов. Подтверждено прогоном `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac2_ac4_ephemeral_clone_lifecycle.py` (2 passed, 8 subtests) и `test_ac3_no_traces_in_main_pult.py` (1 passed) — см. «Проверено исполнением». |

## Вердикт

changes_requested — единственный, но полностью блокирующий дефект: R1-F1. Реализация требований 1-3 сама по себе следует SPEC корректно (юнит- и приёмочные тесты этой задачи зелёные, вычитаны построчно), но ломает работающий сегодня канареечный прогон — интеграционный эффект, не учтённый ни в PLAN («Влияние на систему», «Риски»), ни в собственном регрессионном прогоне разработчика (тот перечисляет только файлы `tests/`, а ломающийся тест лежит в `tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`, вне `tests/` и вне CI-прогона на каждый пуш — поэтому CI 313e52aa зелёный, несмотря на дефект). Почини R1-F1 и подтверди прогоном сломанного теста в следующей итерации.

## Проверено исполнением

- `python3 -m pytest tests/test_workspace.py tests/test_doctor.py tests/test_catalog_pin_divergence.py -q` — 162 passed, 3 subtests passed.
- `python3 -m pytest tests/test_amend.py tests/test_kill_cleanup.py tests/test_step_refixation.py tests/test_task_id_prefix_regression.py tests/test_timeout_checkpoint.py -q` — 106 passed (файлы, точечно правленные этой задачей ради `add_synced_origin`/фейкового `FETCH_HEAD`).
- `python3 -m pytest tasks/01M297HFSKV3GVZJ9YF20FZEZE/acceptance_tests/*.py -q` (все три файла AC-1..AC-8 этой задачи) — 10 passed.
- `python3 -m pytest tests/test_canary.py -q` — 72 passed, 4 subtests passed (существующие юнит-тесты канарейки мокают `workspace.ensure`/`runner.cmd_run` целиком, поэтому регрессию R1-F1 не ловят — сверено чтением setUp каждого класса).
- `python3 -m pytest tasks/01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/test_ac2_ac4_ephemeral_clone_lifecycle.py -q` — 2 failed, оба тем же `RuntimeError`, что описан в R1-F1 (полный traceback зафиксирован при ревью). Этот файл не входит в `tests/` и не гоняется CI на пуш, поэтому зелёный статус CI коммита 313e52aa не противоречит находке.
- Отдельная ручная репродукция вне pytest: реальный git-клон с `origin` вида `canary-stub://ephemeral-clone-no-real-remote` (в точности как `canary._ephemeral_clone`) + вызов `orchestrator.workspace.ensure` напрямую — тот же отказ `fetch`, тот же текст причины.
- Полный набор `tests/` не прогонялся (решение Оператора 05.09 — гоняет CI); ограничился планкой задачи, затронутыми модулями и точечной проверкой найденного класса регрессии.

## Предложения системе

- Регрессионный прогон разработчика (см. PLAN «Подход», абзац «Побочный эффект») ограничивается `tests/` — зафиксированные `acceptance_tests/` ЗАВЕРШЁННЫХ задач того же класса риска (здесь: всё, что заводит worktree/ветку задачи через `workspace.ensure`/`cmd_new` на настоящем git) в этот прогон не попадают и не гоняются CI повторно; для правок с широким «слепым» риском (тут — сигнатура/поведение общего примитива `workspace.ensure`) стоило бы явно рекомендовать `grep` по `workspace.ensure`/`_ephemeral_clone` среди `tasks/*/acceptance_tests/` прошлых задач, не только среди `tests/`.
