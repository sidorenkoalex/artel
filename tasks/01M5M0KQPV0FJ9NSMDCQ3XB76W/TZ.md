---
task: 01M5M0KQPV0FJ9NSMDCQ3XB76W
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Справка пульта называет все команды реестра; шапка без «Фаза 0»; тест формы pin-update

# Справка пульта называет все команды реестра; шапка без «Фаза 0, все гейты ручные»

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-18 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок; остаток CR-2026-09-30-20 — строка приложения «Направление 0»: «справка без `report`, `acceptance-dry-run`, `plank-run`, `suite-run` …, шапка artel.py:2 «Фаза 0»»). Ссылки сверены с `origin/main` 9e29a444 (после мержа CR-4 01M5K9M5DG и CR-7 01M5KEYG8G: в справке появились строки `canary runs …` и `pin-update <sha main артели> [--wait-ci]` с пояснением `--wait-ci:`). `orchestrator/artel.py` в `origin/main` на 82 строки длиннее, чем на пине 89732e3e, поэтому места в нём названы именами функций и переменных, без номеров строк; ветка задачи растёт от `origin/main`.

- Справка пульта — докстринг модуля `orchestrator/artel.py`: `main()` в `orchestrator/artel.py` печатает `__doc__` без аргументов и по `-h`/`--help` (ветка `if not args or args[0] in ("-h", "--help")`).
- Шапка докстринга: `orchestrator/artel.py:2` — «Артель, Фаза 0 — FSM-оркестратор (CLI).»; `orchestrator/artel.py:5` — «Все гейты Фазы 0 — ручные (approve/reject из CLI).». Факт по `gates.yaml` (`gates:`): `spec_gate: manual`, `acceptance: auto`, `merge_gate: manual`; автогейт приёмки — `orchestrator/fsm_autogate.py` (`_maybe_autogate_acceptance`, проверка `gates.policy("acceptance") != gates.AUTO`).
- Перечень команд — блок «Команды:» докстринга `orchestrator/artel.py` (от строки `Команды:` до первой пустой строки).
- Реестр команд — словарь `table` внутри `main()` в `orchestrator/artel.py`: 56 ключей (сверка на `origin/main` 9e29a444 разбором AST). Семи ключей нет в блоке «Команды:»: `workspace` (`workspace.cmd_workspace(rest[0])`), `report` (`report.cmd_report()`), `acceptance-dry-run` (`dry_run.cmd_acceptance_dry_run(rest[0])`), `plank-run` (`plank_run.cmd_plank_run(rest[0], rest[1] if len(rest) > 1 else None)`), `suite-run` (`suite_run.cmd_suite_run(rest)`), `preflight` (`preflight.cmd_preflight(rest[0])`), `guard` (`_cmd_guard(rest)`). Обратного расхождения нет: каждая команда блока есть в `table`.
- Формы вызова семи команд по коду: `suite-run <id> [--wait <минуты> | --failed]` — строка использования `orchestrator/suite_run.py:741` (`_parse_args`); `guard <id> [<файл>]` — `_cmd_guard` в `orchestrator/artel.py` и отказ «guard требует id задачи: artel.py guard <id> [<файл>].»; `plank-run <id> [<файл>]` — `orchestrator/plank_run.py:164` (`cmd_plank_run(task_id, file_arg=None)`); `preflight <id>` — `orchestrator/preflight.py:229`; `acceptance-dry-run <id>` — `orchestrator/dry_run.py:43`; `workspace <id>` — `orchestrator/workspace.py:255`; `report` — `orchestrator/report.py:1430`, без аргументов.
- Четыре из семи миссии называют ролям: `orchestrator/role_prompt.py:313` (`plank-run`), `:333`–`:335` (`guard`, `plank-run`, `suite-run`); все семь, кроме `workspace`, — в белом списке ролей `_ROLE_ALLOWED_COMMANDS` в `orchestrator/artel.py`.
- Обратное направление по правилу требования 4 (первое слово строки с отступом ровно в два пробела и слово после « | », подходящие под `[a-z][a-z0-9-]*`) на `origin/main` 1521d8f2 (до CR-4 и CR-7): 62 слова блока «Команды:», расхождений с ключами `table` — 0.
- CR-4 (01M5K9M5DG) и CR-7 (01M5KEYG8G) смержены. Хвост независимой проверки CR-4: отказ `pin-update` на втором позиционном аргументе есть в коде (`_cmd_pin_update` в `orchestrator/artel.py`: «pin-update: неизвестный аргумент …»), а теста на него нет.
- Теста «реестр ↔ справка» нет. Существующие тесты справки ищут отдельные строки (`tests/test_canary_template_flag.py`, `tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py`, `tests/test_canary_run_task.py` — «`run-task` в справке нет»); добавление строк их не задевает.

## Требования

1. В блок «Команды:» докстринга `orchestrator/artel.py` добавляются строки семи команд в формах по коду: `workspace <id>`, `report`, `acceptance-dry-run <id>`, `plank-run <id> [<файл>]`, `suite-run <id> [--wait <минуты> | --failed]`, `preflight <id>`, `guard <id> [<файл>]` — тем же оформлением, что соседние строки (команды через « | », перенос строки с отступом). Остальные строки блока не меняются.
2. Шапка докстринга исправляется: первая строка — без «Фаза 0» (например, «Артель — FSM-оркестратор (CLI).»); предложение «Все гейты Фазы 0 — ручные (approve/reject из CLI).» заменяется утверждением по факту: гейты `spec_gate` и `merge_gate` — ручные (approve/reject из CLI), `acceptance` проходит автогейтом по политике `gates.yaml` (`orchestrator/fsm_autogate.py`), а при невыполненном условии ждёт Оператора. Схема состояний и остальные абзацы докстринга не меняются.
3. Тест «реестр ↔ справка» (новый файл в `tests/`): ключи словаря `table` берутся разбором исходника `artel.main` (`inspect.getsource` + `ast`: присваивание имени `table` словарём, ключи — строковые константы), не списком в тесте; блок «Команды:» — от строки `Команды:` докстринга до первой пустой строки. Каждый ключ встречается в блоке отдельным словом команды: перед ним начало строки, пробел или `|`, после — пробел, `|` или конец строки (так `pin` не засчитывается вхождением `pin-update`). Сообщение отказа перечисляет недостающие ключи. На текущем коде — красный: семь ключей требования 1.
4. Тест обратного направления в том же файле: в блоке «Команды:» первое слово каждой строки с отступом ровно в два пробела и слово сразу после ` | ` (вертикальная черта с пробелами), если оно подходит под `[a-z][a-z0-9-]*`, — ключ `table`. На текущем коде — зелёный; держит отсутствие команд справки без реестра.
5. Тест шапки в том же файле: текст `artel.__doc__` до строки `Состояния:` содержит `spec_gate`, `acceptance`, `merge_gate`, «ручн», «автогейт» и `gates.yaml` и не содержит «Фаза 0» и «Фазы 0»; текущая политика гейтов тестом не читается. На текущем коде — красный («Фаза 0», имён гейтов нет).
6. Поведение команд не меняется: правится только докстринг `orchestrator/artel.py`. Существующие тесты не правятся и остаются зелёными.
7. Тест (тот же новый файл): `artel.py pin-update <sha1> <sha2>` (два синтаксически полных sha) — отказ с текстом «pin-update: неизвестный аргумент <sha2>» и строкой использования; `pin.cmd_pin_update` не вызывается (подмена-шпион), `fetch` не выполняется. На текущем коде — зелёный; держит форму команды, введённую CR-4.

Зоны: orchestrator/artel.py, tests/

Ограничение зон по смыслу: в `orchestrator/artel.py` — только докстринг модуля (шапка и блок «Команды:»); `table`, `main()` и разборщики аргументов не меняются.

Только чтение: orchestrator/pin.py (`cmd_pin_update` — не меняется), gates.yaml (защищённый путь, политика гейтов), orchestrator/gates.py, orchestrator/fsm_autogate.py, orchestrator/workspace.py, orchestrator/report.py, orchestrator/dry_run.py, orchestrator/plank_run.py, orchestrator/suite_run.py, orchestrator/preflight.py, orchestrator/role_prompt.py (миссии ролей — не меняются), orchestrator/amend.py (вызывающий `cmd_workspace` — не меняется).

Не входит: прочие остатки CR-2026-09-30-20 — `README.md` («Фаза 0 и Фаза A закрыты», число задач), `roles.yaml:4` «Фаза 0» (защищённый путь), статус `escalate` в `templates/PLAN.md` (защищённый путь) — приложением Оператора (строка очереди Оператора по ревизии 22.10); абзац `orchestrator/artel.py:97` («Фаза 0: гейт плана … plan_review появится в MVP») — отдельное решение о плане ревью; справка подкоманд (`<команда> --help`, строка копилки L268); подсказка venv-sync в `orchestrator/stack.py:669` — строка бэклога 333, дефект не определён находкой.

Бюджет: $10.
