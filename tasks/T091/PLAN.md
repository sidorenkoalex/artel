---
task: T091
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Рефакторинг: декомпозиция диспетчеров fsm/runner

## Подход

Чистый перенос кода (правила T015 из skills/code-revision.md): каждая
функция уезжает в новый модуль ЦЕЛИКОМ, без правки тела, кроме
неизбежной квалификации имён, ставших межмодульными (`fsm._helper` вместо
`_helper` там, где вызывающий код теперь в другом файле). Диспетчер
`_cmd_advance` в `fsm.py` вместо if/elif по состояниям стал словарём
`{состояние: обработчик}` — обработчики (по одной функции на состояние)
уехали в `orchestrator/fsm_advance.py`. Аналогично тело окна
`merge_gate -> done` (внешний цикл ожидания CI + сам merge, SPEC T053/
T087) уехало в `orchestrator/fsm_merge_gate.py`, автогейт acceptance
(ADR-0007) — в `orchestrator/fsm_autogate.py`, побочные эффекты после
merge (карта кодовой базы T042, RETRO T043) — в
`orchestrator/fsm_postmerge.py`. Со стороны `runner.py`: WIP-чекпоинты
(T041/T059/T074) — в `orchestrator/checkpoint.py`, классификация ошибок
агента (T082) — в `orchestrator/failure_classification.py`, сборка
миссии/брифа/ревью-пакета роли — в `orchestrator/role_prompt.py`.

`fsm.py`/`runner.py` остаются несущими модулями: диспетчеры
(`cmd_advance`/`cmd_approve`/`cmd_reject`, `cmd_run`) и узлы, общие для
нескольких состояний/гейтов (сверка свежести ветки, чтения с ветки
задачи, guard-отказ, git-identity, окружение/cwd/argv шага, сам цикл
попыток агента). `orchestrator/doctor.py` (936 строк) и
`orchestrator/auto.py` (257 строк) в объём НЕ включены: `doctor.py`
хоть и выше эвристического порога ~500 строк из code-revision.md, несёт
одну связную ответственность (набор pre-flight/recovery/смоук-проверок
через общий `Result`-паттерн, не диспетчер по состоянию) — декомпозиция
потребовала бы отдельного критерия разбиения, не вытекающего из SPEC
буквально; `auto.py` (257 строк) не подходит под эвристику размера
вовсе. Оба — кандидаты следующего захода той же зоны роадмапа P3, не
этой задачи.

Работа фактически была сделана предыдущей (прерванной таймаутом) сессией
шага `developer` — WIP-чекпоинт `c63d950` уже нёс весь перенос. Этот
шаг: (1) верифицировал перенос без потери и без правки поведения
(AST-сверка, см. «Влияние на систему»), (2) сузил диффы `tests/` строго
до строк импортов и адресов `mock.patch` — часть тестовых docstring'ов
в WIP-коммите несла лишний комментарий «перенесено в T091», не входящий
в допустимые правки AC-2, убран отдельным коммитом, (3) регенерировал
`docs/codebase-map.md`, (4) снял смоук до/после и написал этот PLAN.

## Шаги

1. **Декомпозиция `fsm.py`** (коммит `c63d950`, в составе): выделены
   `orchestrator/fsm_advance.py` (обработчики `cmd_advance` по
   состояниям), `orchestrator/fsm_autogate.py` (автогейт acceptance),
   `orchestrator/fsm_merge_gate.py` (тело и внешний цикл гейта
   `merge_gate`), `orchestrator/fsm_postmerge.py` (карта кодовой базы +
   RETRO после merge). `fsm.py`: 1582 -> 684 строки.
2. **Декомпозиция `runner.py`** (коммит `c63d950`, в составе): выделены
   `orchestrator/checkpoint.py` (WIP-чекпоинты), `orchestrator/
   failure_classification.py` (классификация ошибок агента), `orchestrator/
   role_prompt.py` (сборка миссии/брифа/ревью-пакета). `runner.py`:
   1033 -> 642 строки. `orchestrator/pause.py` — точечная правка ссылки
   импорта (`runner.commit_pause_now_checkpoint` ->
   `checkpoint.commit_pause_now_checkpoint`), другого выбора у неё нет:
   она зовёт переехавшую функцию.
3. **Сужение диффа `tests/` до AC-2** (коммит `73712e5`): из 6
   затронутых тестовых файлов убраны docstring-предложения
   «перенесено из X в T091», не являющиеся ни строкой импорта, ни
   адресом `mock.patch` — оставлены только необходимые правки (импорт
   переехавшего модуля вместо `fsm`/`runner`, замена квалификатора
   `fsm.`/`runner.` на новый на местах вызова, и — где сам факт
   переезда упоминался в докстринге по существу, например «Юнит-тесты
   `checkpoint.commit_step_artifacts`» вместо `runner....` — оставлена
   ТОЛЬКО замена имени модуля, без сопроводительной фразы).
4. **Регенерация карты + PLAN + смоук** (этот шаг): `docs/codebase-map.md`
   пересобран (`scripts/codebase_map.py`), написан этот PLAN.md со
   сверкой поведения.

Один MR — одна ветка задачи целиком (три коммита внутри неё); дробить
дальше незачем, декомпозиция fsm/runner — семантически одно изменение,
и `git revert -m 1 <merge>` откатывает его целиком за один шаг (см.
«Влияние на систему»).

## Покрытие требований

| Требование SPEC | Шаг |
|---|---|
| 1 (декомпозиция fsm.py/runner.py, зоны-ориентиры) | 1, 2 |
| 2 (поведение всех команд не меняется) | 1, 2 (перенос без правки тела); проверено AST-сверкой и смоуком ниже |
| 3 (правки tests/ — только импорты/mock.patch) | 3 |
| 4 (без попутных улучшений/переименований поведения) | 1, 2, 3 (см. «Влияние на систему», AST-сверка) |
| 5 (таблица переносов + план отката) | этот документ, разделы «Таблица переносов» и «Откат» |
| 6 (смоук до/после на живых данных пульта) | этот документ, раздел «Смоук до/после» |

## Таблица переносов

Полный перечень: КАЖДЫЙ функция верхнего уровня старых `fsm.py`
(1582 строки, коммит `e0c1fc1`) и `runner.py` (1033 строки, тот же
коммит) учтена — 54 определения на входе, 60 на выходе (шесть новых
имён — это извлечённые ветки if/elif `_cmd_advance`/`_cmd_run`,
получившие собственное имя функции: `spec_writing`, `review`,
`verifying`, `tests_writing`, `in_dev`, `mission_brief_package`; текст
внутри них не менялся). Автоматическая сверка — раздел «Влияние на
систему» ниже.

### fsm.py -> fsm_advance.py (по одному обработчику на состояние `cmd_advance`)

| Символ | Откуда | Куда |
|---|---|---|
| `spec_writing` (ветка `state == "spec_writing"` в `_cmd_advance`) | fsm.py | fsm_advance.py |
| `review` (ветка `state == "review"`) | fsm.py | fsm_advance.py |
| `verifying` (ветка `state == "verifying"`) | fsm.py | fsm_advance.py |
| `tests_writing` (ветка `state == "tests_writing"`) | fsm.py | fsm_advance.py |
| `in_dev` (ветка `state == "in_dev"`) | fsm.py | fsm_advance.py |

### fsm.py -> fsm_autogate.py (автогейт acceptance, ADR-0007)

| Символ | Откуда | Куда |
|---|---|---|
| `_autogate_conditions` | fsm.py | fsm_autogate.py |
| `_maybe_autogate_acceptance` | fsm.py | fsm_autogate.py |

### fsm.py -> fsm_merge_gate.py (тело и внешний цикл гейта `merge_gate`)

| Символ | Откуда | Куда |
|---|---|---|
| `_touches_protected_path` | fsm.py | fsm_merge_gate.py |
| `_handle_merge_conflict` | fsm.py | fsm_merge_gate.py |
| `_ci_confirm_red_or_flake` | fsm.py | fsm_merge_gate.py |
| `_wait_for_branch_ci_green` | fsm.py | fsm_merge_gate.py |
| `_cmd_approve_merge_gate` | fsm.py | fsm_merge_gate.py |
| `_cmd_approve_merge_gate_cycle` | fsm.py | fsm_merge_gate.py |

### fsm.py -> fsm_postmerge.py (побочные эффекты после merge: карта, RETRO)

| Символ | Откуда | Куда |
|---|---|---|
| `_map_content_without_sha` | fsm.py | fsm_postmerge.py |
| `_map_regen_incident` | fsm.py | fsm_postmerge.py |
| `_regenerate_and_commit_map` | fsm.py | fsm_postmerge.py |
| `_retro_incident` | fsm.py | fsm_postmerge.py |
| `_write_and_stage_retro` | fsm.py | fsm_postmerge.py |
| `_commit_retro` | fsm.py | fsm_postmerge.py |
| `_generate_and_commit_retro` | fsm.py | fsm_postmerge.py |

### runner.py -> checkpoint.py (WIP-чекпоинты, T041/T059/T074)

| Символ | Откуда | Куда |
|---|---|---|
| `commit_timeout_checkpoint` | runner.py | checkpoint.py |
| `commit_abnormal_checkpoint` | runner.py | checkpoint.py |
| `commit_pause_now_checkpoint` | runner.py | checkpoint.py |
| `commit_step_artifacts` | runner.py | checkpoint.py |
| `_commit_worktree_change` | runner.py | checkpoint.py |

### runner.py -> failure_classification.py (классификация ошибок агента, T082)

| Символ | Откуда | Куда |
|---|---|---|
| `classify_attempt_failure` | runner.py | failure_classification.py |
| `_attempt_output_text` | runner.py | failure_classification.py |
| `_record_failure_classification` | runner.py | failure_classification.py |

### runner.py -> role_prompt.py (миссия/бриф/ревью-пакет роли)

| Символ | Откуда | Куда |
|---|---|---|
| `mission_brief_package` (тело `_cmd_run`, сборка `mission`/`brief_text`/`package` по роли) | runner.py | role_prompt.py |

### Остаётся на месте (диспетчеры и узлы, общие для нескольких состояний/гейтов)

`fsm.py`: `cmd_advance`, `_advance_with_refixation`, `_cmd_advance`
(диспетчер — теперь словарь состояние->обработчик), `confirm_fixation`,
`cmd_approve`, `_cmd_approve` (диспетчер), `cmd_reject`, `_cmd_reject`,
`guard_refuses`, `_dirty_refuses`, `_read_branch_text_or_refuse`,
`_answer_file_count`, `_answer_baseline_or_refuse`,
`_tests_writing_ac_state`, `_pull_main_or_escalate`,
`_conflicting_files`, `_auto_resolve_map_conflict`,
`_verifying_elapsed_seconds`, `_maybe_ensure_draft_mr`.

`runner.py`: `cmd_run`, `_cmd_run`, `_attempts_word`, `spawn_agent`,
`step_role`, `git_identity`, `role_token`, `role_env`, `role_cwd`,
`role_cmd`, `run_agent_once`, `close_pump`.

### Побочная правка вне fsm/runner

`orchestrator/pause.py` — ссылка импорта `runner.commit_pause_now_checkpoint`
заменена на `checkpoint.commit_pause_now_checkpoint` (10 строк diff):
неизбежное следствие переезда функции, которую `pause.py` зовёт; тело
`cmd_pause_now` не меняется.

## Влияние на систему

**Поведение команд не меняется — как проверено:**

1. **Тесты.** `python3 -m unittest discover -s tests`: 1125 из 1125
   зелёных на итоговом коммите ветки; тот же состав, что и до
   рефакторинга (ни один тест не добавлен, не удалён, не заскипан —
   правки `tests/` только двигают импорты/квалификаторы вслед за
   переехавшими символами, AC-2 — см. «Таблица переносов» и коммит
   `73712e5`).
2. **AST-сверка старого монолита с новым пакетом** (тот же приём, что
   T015). Скрипт (не входит в диф задачи, разовый инструмент проверки):
   для каждого модуля снимаются top-level `FunctionDef`/`AsyncFunctionDef`,
   из тела вырезаются квалификаторы новых межмодульных имён
   (`fsm.`, `fsm_advance.`, `fsm_autogate.`, `fsm_merge_gate.`,
   `fsm_postmerge.`, `checkpoint.`, `failure_classification.`,
   `role_prompt.`, `runner.`), результат сравнивается по `ast.dump`.
   Результат: **54 определения верхнего уровня в старых `fsm.py`+
   `runner.py` (коммит `e0c1fc1`), 60 в новом пакете; потеряно 0**.
   Шесть «новых» имён — это ветки `if/elif` `_cmd_advance`/`_cmd_run`,
   получившие собственное имя функции при переезде (`spec_writing`,
   `review`, `verifying`, `tests_writing`, `in_dev`,
   `mission_brief_package`) — не новый код, а поименованный старый.
   AST различается только у диспетчеров (`_cmd_advance`, `_cmd_approve`,
   `_cmd_run` — ожидаемо: тело заменено на выбор обработчика/вызов
   вынесенной функции) и у `commit_timeout_checkpoint`, единственная
   правка которого — обновление ссылки на `role_cwd` в докстринге
   (`` `role_cwd` `` -> `` `runner.role_cwd` ``, код не тронут).
   Точечная сверка (см. «Смоук до/после» и текстовое сравнение веток
   `verifying`/`in_dev`/`tests_writing` monolith-vs-package) не нашла ни
   одного расхождения в самом теле перенесённых функций.
3. **Смоук на живых данных пульта до/после** — см. отдельный раздел
   ниже; расхождений в наблюдаемом выводе не найдено.

**Что рядом и почему не ослабляется:**

- **Тесты (1125, включая `test_invariants.py` — неослабляемый).** Ни
  один сценарий, ассерт или `subTest` не менялся — только импорты и
  квалификаторы (AC-2, коммит `73712e5`).
- **`scripts/guard.py`, `gates.yaml`, `roles.yaml`, `.github/`,
  `templates/`, `skills/`, `docs/invariants.md`,
  `tests/test_invariants.py`.** Не тронуты (AC-5).
- **`docs/codebase-map.md`.** Регенерирован тем же коммитом, что и
  правка `*.py` в `orchestrator/` (conventions-core), отражает новую
  структуру модулей — карта живая, не ADR-подобная фиксация.
- **Живая БД `.artel/state.db`.** Схема и `store.py` не тронуты вовсе —
  декомпозиция не задевает файл БД, миграций нет.
- **Инвариант T056** («пульт исполняется только из главной копии, не из
  worktree», `orchestrator/artel.py::_refuse_if_worktree`) — не тронут;
  из-за него прямой прогон `artel.py status/log/doctor` через `main()`
  недостижим ни из worktree задачи T091, ни из вспомогательных
  worktree'ов смоука (см. «Смоук до/после», как обойдена).

## Смоук до/после

**Ограничение окружения сессии.** Разрешённое дерево каталогов этой
сессии — только worktree задачи T091; живой `.artel/state.db` главной
копии пульта (`/Users/al.sidorenko/projects/artel/.artel/state.db`)
физически недостижим (`ls`/`cat` вне разрешённого дерева блокируются
песочницей инструмента). Сверка живой БД пульта — вне возможностей
роли `developer` в этой сессии; ближайший доступный эквивалент —
описанный ниже.

**Метод.** Два git-worktree, заведённых прямо для сверки: `before`
(detached на `e0c1fc1` — последний коммит ДО переноса, монолитные
`fsm.py`/`runner.py`) и `after` (detached на `73712e5` — итоговый
коммит переноса+сужения tests/, ДО этого PLAN.md). В `before` собрана
синтетическая, но реалистичная `state.db` (`store.create_schema` +
5 задач в состояниях `in_dev`/`review`/`escalated`/`done`/`killed`,
с записями журнала) — тем же инструментом (`store.py`), который не
тронут декомпозицией. Файл БД скопирован байт-в-байт в `after`
(идентичный вход для обеих сторон). Инвариант T056 (см. выше) не даёт
прогнать команды через `artel.py main()` из ЛЮБОГО git-worktree — вызваны
напрямую функции команд (`catalog.cmd_status`, `catalog.cmd_log`,
`doctor.cmd_doctor`), то есть то же самое, что исполнил бы `main()`
после разбора argv; сам диспетчер `main()`/`_refuse_if_worktree` в
рефакторинг не входит и здесь не проверяется отдельно.

**Результат.** `status`, `log T101` (in_dev), `log T104` (done),
`doctor` — вывод посимвольно идентичен между `before` и `after`, за
вычетом:
- `disk-space` (82710 vs 82708 МБ свободно) — реальное изменение
  свободного места на диске машины между двумя прогонами, не код;
- `live-smoke` (`duration_ms`/`uuid` живого ответа `claude`) — сам
  чек делает боевой сетевой вызов CLI, каждый прогон получает свежий
  `uuid`/тайминг ответа сервера; текст результата (`rc=1`, `Not logged
  in`) идентичен;
- `orphans-worktrees` — перечисляет сами вспомогательные
  `before`/`after` worktree'ы смоука (путь неизбежно разный,
  `smoke_before` vs `smoke_after`) — артефакт метода сверки, не
  наблюдаемое поведение системы.

Ни одно расхождение не связано с содержимым декомпозиции. Мутирующие
команды (`advance`/`approve`/`run`) на этой синтетической БД не
гонялись — их поведение закрыто юнит- и приёмочными тестами на
временных БД (пункт 1 выше); AST-сверка (пункт 2) и посимвольная сверка
перенесённых функций (текстовая, см. `git show` `_cmd_advance` ветки
`in_dev` vs `fsm_advance.in_dev` — совпадают дословно, включая
комментарии) закрывают то, что смоук read-only команд не мог бы
показать напрямую. Вспомогательные worktree'ы смоука убраны
(`git worktree remove --force`) — в дифф задачи не входят.

## Откат

Рефакторинг лёг тремя коммитами одной ветки задачи и мержится одним
merge-коммитом в `main` (обычный flow гейта `merge_gate`). Откат —
`git revert -m 1 <merge>`: возвращает монолитные `fsm.py`/`runner.py`
и правки `tests/` к состоянию до задачи одним коммитом. `.artel/state.db`
не мигрирует (схема не менялась) — откат её не касается.
`docs/codebase-map.md` возвращается revert'ом автоматически (входит в
тот же merge); отдельного шага не требуется.

## Риски

- **Расширение зоны.** Соблазн заодно разбить `orchestrator/doctor.py`
  (936 строк, тоже под эвристику ~500 строк code-revision.md) или
  дедуплицировать код между новыми модулями. Оба — не входят: SPEC
  оставляет `doctor.py`/`auto.py` на усмотрение разработчика, выбор —
  не трогать (см. «Подход»); дедупликация нового кода — не входит по
  требованию 4 SPEC (только идентичные фрагменты, которых перенос сам
  по себе не создаёт).
- **Молчаливая потеря квалификации при переезде.** Класс риска T015:
  `from module import name` вместо `module.name` в новом файле оставил
  бы тест зелёным при пустой подмене. Смягчение — полный набор тестов
  зелёный (1125/1125) плюс AST-сверка, требующая точного совпадения
  тела функции с учётом квалификаторов (несовпадение хотя бы одного
  вызова проявилось бы как AST-diff).
- **Смоук не на настоящей живой БД пульта** (см. «Смоук до/после»,
  «Ограничение окружения сессии») — ограничение песочницы сессии, не
  выбор разработчика. Компенсировано AST-сверкой всего перенесённого
  кода и полным прогоном тестов; ревьюеру стоит перепроверить смоук
  на реальной `.artel/state.db`, если у него есть доступ к главной
  копии пульта.

## Предложения системе

- skills/code-revision.md, блок T015 требует смоука «на живых данных
  пульта», но роль `developer` работает в изолированном git-worktree
  задачи (ADR T045) и структурно не имеет доступа к `.artel/state.db`
  главной копии — на задачах класса «рефакторинг» это правило пока
  выполнимо только приближённо (синтетическая БД в собственном
  worktree). Стоит явно разрешить такую замену в тексте скила, чтобы
  следующий разработчик не тратил цикл на попытки достать
  недостижимые живые данные.
