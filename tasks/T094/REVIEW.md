---
task: T094
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 3
---

# REVIEW: M1: артефактный контур — Б₃ + ULID

Инкрементальный дифф пакета (`a09296b995578e3c151814daab31db61eb37c77f`..HEAD)
не показывает исправлений двух major-замечаний итерации 2 — они сделаны
коммитом `c44e31b` («закрываю REVIEW.md итерации 2 — бинарные файлы в
артефактной ветке, требование 10 для ядра FSM»), который лежит ДО анкера
пакета (`git merge-base --is-ancestor c44e31b a09296b` → да; anchor
`a09296b` — мерж-коммит `Merge remote-tracking branch 'origin/main'`,
родитель `c44e31b`). Сам анкер в этот раз корректен как «состояние после
предыдущего вердикта» (`git log --oneline -- tasks/T094/REVIEW.md` →
только `3a7b79a` (итерация 2) и `3dee69b` (итерация 1); `c44e31b` и
`a09296b` — оба потомки `3a7b79a`) — это не класс T082/T087 (пустой/
некорректный анкер), просто фиксы двух major лежат в диапазоне
`3a7b79a..a09296b`, который пакетом не показан, а показанный диапазон
(`a09296b..HEAD`) — это уже ТОЛЬКО подтяжка main (35 коммитов, T097-T102)
и сопутствующая правка тестовых фикстур. Чтобы не подписывать `approved`
вслепую под тем, чего не видно в пакетном диффе, оба фикса из `c44e31b`
прочитаны и перепроверены исполнением отдельно (см. «Проверено
исполнением») — не приняты на слово из PLAN.md.

## Фаза A — гейт плана

PLAN.md содержательно не менялся с итерации 2 нигде, кроме добавленного
раздела «Постскриптум» (диф `tasks/T094/PLAN.md` в пакете — 20 строк,
только этот абзац). Реестр точек чтения (первый раздел) по-прежнему
покрывает все точки из требования 1, таблица «Покрытие требований»
согласована с текстом реестра (минорная опечатка «14 vs 15» итерации 2
исправлена — строка 251 теперь единообразно «15»). Раздел «Вопрос
Оператору — требование 10» помечен «СНЯТ итерацией 3» и описывает
реализацию, которая действительно присутствует в коде (см. ниже) —
замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 2 (реестр — первый раздел PLAN.md). |
| 2 | OK | `orchestrator/idgen.py::new_task_id` — единственный генератор (48-бит timestamp + 80-бит `os.urandom`, Crockford base32, без внешних зависимостей); прочитан целиком заново, соответствует SPEC. Без изменений с итерации 1. |
| 3 | OK | Без изменений с итерации 2 (`store.resolve_task_id`, все 15 id-принимающих CLI-команд резолвят префикс на своём верху — файлы `orchestrator/answer.py`, `budget.py`, `auto.py`, `cleanup.py`, `catalog.py`, `fsm.py`, `pause.py`, `release.py`, `runner.py`, `workspace.py` не менялись с коммита `3a7b79a`, подтверждено `git diff 3a7b79a..HEAD --stat` по этим файлам — пусто). |
| 4 | OK (диф, не код ветки) | Без изменений. |
| 5 | OK | Без изменений (`orchestrator/prune.py` не менялся с итерации 2). |
| 6 | OK | Без изменений. |
| 7 | OK | Без изменений (`orchestrator/catalog.py`/`artifact_branch.py` не менялись с итерации 2). |
| 8 | OK | Замечание 1 итерации 2 (бинарные файлы теряются) закрыто коммитом `c44e31b`: `checkpoint._commit_external_step_artifacts` читает `path.read_bytes()` вместо `read_text(utf-8)`, `artifact_branch.write_commit` принимает `files[rel]` и как `str`, и как `bytes` (`hash-object` получает байты напрямую) — перечитано целиком, соответствует описанию. `tests/test_checkpoint_external_step_artifacts.py` — 2 новых теста на этот случай (`test_binary_file_is_not_lost`, `test_all_files_binary_still_commits_and_clears_the_dir`), весь файл прогнан заново — зелёный (см. «Проверено исполнением»). |
| 9 | OK | Без изменений. |
| 10 | OK | Замечание 2 итерации 2 (требование 10 для ядра FSM не закрыто) закрыто коммитом `c44e31b`, реализацией, не эскалацией: общий резолвер `orchestrator/artifact_source.py::resolve(conn, task_id)` (новый файл, 30 строк, прочитан целиком) применён к `orchestrator/fsm.py` (`_answer_file_count`, `_answer_baseline_or_refuse`, `_cmd_approve` ветка `spec_gate`) и `orchestrator/fsm_advance.py` (`spec_writing`, `review`, `tests_writing`, `in_dev`) — везде вместо `t["branch"]` читается резолвленная ветка-источник; `acceptance.materialize_from_branch` закрывает лок `acceptance_tests` для внешнего target (материализация во временный каталог, `finally: shutil.rmtree`). Diff `c44e31b` для `fsm.py`/`fsm_advance.py`/`acceptance.py` прочитан построчно — соответствует описанию PLAN.md, `brief.py` теперь тоже делегирует этому резолверу (не дублирует логику). `git diff 3a7b79a..HEAD --stat` этих файлов после `c44e31b` — пусто (не менялись подтяжкой main), `python3 -c "import orchestrator.fsm_advance"` — без ошибок (циклический импорт не возник от слияния с `guard` T100). |
| 11 | OK | Инвариантные тестовые модули (`test_git_fixation`, `test_acceptance_tests_flow`, `test_gitcmd_branch_reads`) — в полном прогоне `tests/` (1216 passed), без изменений поведения self. |
| 12 | OK | Без изменений. |
| 13 | OK | `test_ac15_retried_by_doctor_after_origin_recovers` — тот же экологический сбой (token×3/live-smoke), перепрогнан лично, см. «Проверено исполнением»; сам ретрай снапшота внутри `doctor` — `[ok] snapshot-pending:...` в выводе. |
| 14 | OK | Без изменений (`orchestrator/retro_corpus.py` не менялся с итерации 2). |
| 15 | OK | `docs/adr/0005-data-preservation-and-memory.md` несёт правки пп. 1, 2, 4, 5 (диф `main...HEAD` для этого файла прочитан целиком — 4 новых блока «Правка SPEC T094», по одному на каждый из четырёх пунктов, содержательно соответствуют требованию: сужение «чужое не публикуем» до видимой поверхности (п.1), артефактная ветка + снапшот вместо переезда в `tasks/` main (п.2), контент-адресация `refs/artifacts/<id>` вместо `<merge-sha>:tasks/<id>/` (п.4), судьба счётчика номеров — legacy (п.5)); пп. 6, 7 не тронуты — подтверждено (диф не касается соответствующих разделов файла). |
| 16 | OK | Без изменений, self исключён из редиректа везде — подтверждено полным прогоном `tests/` без регресса self-флоу. |

## Замечания

Замечаний уровня blocker/major/minor по итогам этой итерации нет — оба
major-замечания итерации 2 закрыты фактически (не декларативно, оба
перечитаны и перепроверены исполнением), минорное замечание итерации 2
(опечатка «14 vs 15») тоже исправлено.

Подтяжка main (постскриптум PLAN.md) и правка фикстур
`test_agent_log.py`/`test_step_cost.py` под ULID проверены: разрешение
конфликта импортов в `fsm_advance.py` (объединение `shutil`/
`artifact_source` этой ветки с `from scripts import guard` T100) не
потеряло и не изменило поведение ни одной из сторон — реестр замечаний
ревью T100 (`orchestrator/fsm_advance.py::review()`, ветка `status ==
"approved"`) и редирект T094 (резолвер ветки-источника чуть выше по той
же функции) сосуществуют без конфликта логики (прочитано целиком,
`python3 -c "import orchestrator.fsm_advance"` — без ошибок, полный
прогон тестов включает оба класса тестов зелёными). Правка тестовых
фикстур (замена `TASK = "T001"` + `self.capture(cmd_new)` на
`capture_new_task_id`) — тот же класс дефекта и тот же приём починки,
что уже применён в `test_agent_failure.py`/`test_advance_guard.py` до
этой ветки — не новый паттерн, консистентно.

## Реестр замечаний

Записей нет — 0 blocker/major/minor замечаний по итогам этой итерации.
Оба major-замечания итерации 2 (REVIEW.md T094 итерации 2, свободный
текст «Замечания», schema_version на тот момент 2 — секции «Реестр
замечаний» тогда не существовало, ни в одном REVIEW.md этой задачи не
заводились id) закрыты кодом (`c44e31b`) и перепроверены выше построчно,
не переносятся сюда как записи задним числом (SPEC T100, «Не входит»:
ретроспективная миграция закрытых итераций в реестр не требуется — та
же логика применена здесь к итерациям ДО перехода этой задачи на
schema_version 3).

## Вердикт

approved

## Проверено исполнением

- `git log --oneline -- tasks/T094/REVIEW.md` — только `3a7b79a`
  (итерация 2), `3dee69b` (итерация 1); `git merge-base --is-ancestor
  c44e31b a09296b995578e3c151814daab31db61eb37c77f` — да (фиксы
  итерации-2-замечаний лежат внутри диапазона `3a7b79a..a09296b`, не
  показанного пакетным диффом) — см. пояснение анкера в начале файла.
- `git show c44e31b -- orchestrator/checkpoint.py orchestrator/
  artifact_branch.py orchestrator/artifact_source.py orchestrator/
  fsm.py orchestrator/fsm_advance.py orchestrator/acceptance.py` —
  прочитан построчно целиком, соответствует описанию PLAN.md
  («Итерация 3», шаги 16-17).
- `git show 0e32a98 -- orchestrator/fsm_advance.py` — конфликт слияния
  (`shutil`/`artifact_source` этой ветки vs `from scripts import guard`
  T100) прочитан, разрешение объединением подтверждено; `python3 -c
  "import orchestrator.fsm_advance"` — без ошибок.
- `git diff 3a7b79a..HEAD --stat -- orchestrator/snapshot.py
  orchestrator/doctor.py orchestrator/retro_corpus.py orchestrator/
  catalog.py orchestrator/cleanup.py orchestrator/fsm_merge_gate.py
  orchestrator/fixation.py orchestrator/store.py orchestrator/prune.py
  orchestrator/workspace.py orchestrator/answer.py orchestrator/
  budget.py orchestrator/auto.py orchestrator/pause.py orchestrator/
  release.py orchestrator/runner.py orchestrator/config.py` — пусто:
  эти файлы не менялись с итерации 2, вердикты по ним перенесены без
  повторного построчного чтения (уже проверены итерацией 2), с прямой
  выборочной перепроверкой AC-15 (doctor) и AC-3 (резолвер префикса)
  живым прогоном ниже.
- `python3 -m unittest discover -s tests -q` — 1216 тестов, OK
  (~112с). Совпадает с цифрой из постскриптума PLAN.md.
- `python3 -m unittest tests.test_agent_log tests.test_step_cost -v` —
  94 теста, все зелёные (правка фикстур под ULID не сломала ничего
  вокруг).
- `python3 -m unittest discover -s tasks/T094/acceptance_tests -p
  "test_*.py"` — 28 тестов, 27 ok / 1 error
  (`test_ac15_retried_by_doctor_after_origin_recovers`); перепрогнан
  отдельно с `-v`: `doctor.cmd_doctor()` — 4 отказа, все три `token` и
  `live-smoke` (нет keychain-слотов `artel-developer`/`artel-reviewer`/
  `artel-test_author`, `claude` не залогинен в этой песочнице —
  `Not logged in · Please run /login`), `[ok] snapshot-pending:...`
  подтверждает, что сам ретрай снапшота внутри доктора отработал
  верно — тот же диагноз, что риск №2 PLAN.md.
- `python3 scripts/guard.py --all` — `GUARD: ок (353 файлов)`.
- `python3 scripts/codebase_map.py --check` — чисто, карта свежая.
- `git diff main...HEAD --stat -- gates.yaml roles.yaml .github/
  templates/ skills/` — пусто: ни один защищённый путь не тронут этой
  веткой (protected-контент, принесённый подтяжкой main из T100, уже в
  main, не диф этой ветки относительно main).
- `git diff main...HEAD --stat -- docs/adr/0005-data-preservation-
  and-memory.md` — 40 добавлений/4 удаления, прочитан целиком (см.
  требование 15 выше).
- `git ls-files | grep -i repro_binary_loss` — пусто: временный репро-
  скрипт итерации 2 (`scratchpad/repro_binary_loss.py`) не попал в
  ветку задачи.
- `git diff main...HEAD --stat -- scratchpad/` — пусто.
- Прочитан `orchestrator/idgen.py` целиком (требование 2) и
  `orchestrator/store.py::resolve_task_id`/`get_task` (требование 3) —
  заново, не по памяти прошлых итераций.

## Предложения системе

- `orchestrator/config.py:190-196` (`LEASE_STALE_AFTER_SEC`, не
  диф этой ветки — значение и комментарий пришли с main, коммит
  `20afc92`, не тронуты T094 ни строкой): комментарий обосновывает
  `LEASE_STALE_AFTER_SEC = 7200` запасом над «до `AGENT_ATTEMPTS(3)`
  попыток по `AGENT_TIMEOUT_SEC(1800)` каждая ≈ 90 минут», но
  `AGENT_TIMEOUT_SEC` на main уже 2700 (тот же коммит `20afc92`,
  временное решение Оператора 02.09) — арифметика комментария не
  пересчитана: 3×2700с = 8100с (135 мин) уже ПРЕВЫШАЕТ
  `LEASE_STALE_AFTER_SEC` (120 мин), то есть именно та гонка, от
  которой комментарий обещает защиту («ещё реально работающий шаг
  выглядел бы протухшим»), структурно возможна уже сегодня на main.
  Не находка T094 (файл и значения не в диффе этой ветки, восстановлены
  дословно с main по замыслу PLAN.md) — стоит проверить отдельной
  мелочью на main, пока временный потолок 2700 не откатили обратно.
- Пакет ревью в этот раз не воспроизвёл класс T082/T087 (анкер = HEAD),
  но принёс соседний вариант того же семейства: анкер синтаксически
  корректен (не равен HEAD, лежит на ветке REVIEW.md), но диапазон,
  который он покрывает, не включает исправления замечаний предыдущей
  итерации — они лежат МЕЖДУ прошлым вердиктом и анкером, а не между
  анкером и HEAD. Ревьювер, доверившийся только пакетному диффу, не
  увидел бы фактических фиксов вовсе. Стоит явно упомянуть в
  review-checklist этот вариант (анкер корректен, но не покрывает
  «предыдущий вердикт → фикс замечаний» диапазон) отдельно от «анкер
  == HEAD» — сегодня скил описывает только последний случай.
