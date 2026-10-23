---
task: 01M5KEYG8G1WXHSR4BDKBSH6JP
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: canary runs: история прошедших прогонов канарейки командой пульта

# canary runs: история прошедших прогонов канарейки командой пульта

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-7 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии): стоимость, вердикт и причину отказа прошедших прогонов канарейки сессия Оператора берёт запросами SQL к таблице `canary_runs` или из файлов `logs/canary/run-*.json` — 66 запросов к `canary_runs` за 12 дней по транскриптам. Правки БД нет, но это замещение недостающей команды (правило 06.09 «обход вместо команды — не молча»). Ссылки сверены с `origin/main` 71ce9904 и перепроверены на 1521d8f2 (между ними менялся только код отправки документов задачи, файлы этого ТЗ не затронуты); `orchestrator/canary.py` и `orchestrator/store.py` между HEAD главной копии и `origin/main` не менялись, `orchestrator/artel.py` до строки 1874 не сдвинут.

- Семейство команд `canary` разбирает `orchestrator/artel.py:1541` (`_cmd_canary`): подкоманды `pool-seal`, `live` (`orchestrator/artel.py:1559`), внутренняя `run-task`; остальное — запуск прогона с обязательным `--k`. Строки справки — `orchestrator/artel.py:181`–`185`.
- `canary live` — `orchestrator/canary.py:3129` (`cmd_canary_live`): только реестр живых прогонов; прошедшие прогоны не показывает.
- Прошедшие прогоны лежат в таблице `canary_runs` БД пульта (схема — `orchestrator/store.py:1563`): по строке на задачу прогона — `run_stamp`, `title`, `task_id`, `steps`, `cost_usd`, `review_iterations`, `escalations`, `outcome`, `marker_mismatch`, `created_at`, `main_sha`, `verdict` (`green`/`red`/`ceiling`), `set_name`, `acceptance_route`, `autogate_refusal`, `escalation_roles`. Чтение всех строк — `orchestrator/store.py:1710` (`all_canary_runs`, сама заводит таблицы при их отсутствии); тем же вызовом пользуется `--result-file` (`orchestrator/artel.py:1607`).
- Строку причины отказа автогейта сводка прогона строит `orchestrator/canary.py:2031` (`_acceptance_summary`: пробелы схлопнуты, не длиннее 500 символов, «причина отказа автогейта: …» или «приёмка вручную: …»). Вердикт строки — `orchestrator/canary.py:2050` (`_run_verdict`). Шаблон `run_stamp` — `canary.RUN_STAMP_RE` (`orchestrator/canary.py:2803`, `[0-9]{8}T[0-9]{6}Z`, без якорей начала и конца строки).
- Каталог диагностики незелёной задачи — `.artel/canary/<run_stamp>/<task_id>/` (`canary._diagnostics_dir`).
- На 23.10 в `canary_runs` 187 строк, 162 прогона, первая строка — 05.09.

## Требуется

1. Новая подкоманда `canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]`: разбор — в `orchestrator/artel.py` (ветка `_cmd_canary` рядом с `live`), исполнение — новая функция `canary.cmd_canary_runs(since: str | None = None, run_stamp: str | None = None) -> None`.
2. Отказы — в разборе, до чтения БД, ненулевой код выхода: лишний или неизвестный аргумент — с текстом использования; `--since` без значения, либо значение не проходит одновременно регулярное выражение `\d{4}-\d{2}-\d{2}` (проверка строки целиком) и `datetime.strptime(<значение>, "%Y-%m-%d")` — «canary runs: --since ждёт дату ГГГГ-ММ-ДД»; `run_stamp` не проходит `canary.RUN_STAMP_RE.fullmatch` (совпадение только начала строки отказом не спасается) — «canary runs: run_stamp … не по шаблону ГГГГММДДTЧЧММССZ»; `--since` вместе с `run_stamp` — «canary runs: --since и <run_stamp> несовместимы».
3. Отбор прогонов (прогон — группа строк одного `run_stamp`; порядок — от нового к старому по наибольшему `id` группы; строки внутри — по `id`):
   - без аргументов — последние `canary.CANARY_RUNS_DEFAULT_COUNT = 10` прогонов;
   - `--since <дата>` — все прогоны, у которых есть строка с `created_at` не раньше `<дата> 00:00:00Z`;
   - `<run_stamp>` — один этот прогон; его нет — «canary runs: прогона <run_stamp> нет», ненулевой код выхода.
   Пустая таблица (или пустой отбор `--since`) — одна строка «прогонов канарейки нет», код выхода 0.
4. Формат вывода (поля по колонкам `canary_runs`; отсутствующее значение `NULL` печатается как `—`):
   - заголовок прогона: `<run_stamp>  набор=<set_name>  sha=<main_sha первые 8 знаков>  задач=<N>  зелёных=<число verdict='green'>  $<сумма cost_usd, два знака>`; значения `набор=` и `sha=` берутся из первой строки группы по `id`; при суммировании `cost_usd` значение `NULL` считается нулём;
   - строка задачи с отступом в два пробела: `<title>  <task_id>  вердикт=<verdict>  исход=<outcome>  $<cost_usd, два знака>  шагов=<steps>  ревью-итераций=<review_iterations>  эскалаций=<escalations>`, затем ` (роли: <escalation_roles>)`, если `escalation_roles` непуст, и `  [расхождение маркера]`, если `marker_mismatch` = 1;
   - под строкой задачи с отступом в четыре пробела — причина отказа автогейта тем же текстом, что `canary._acceptance_summary(acceptance_route, autogate_refusal, False)` без ведущих пробелов, если он непуст;
   - под ней же — `    диагностика: <путь>`, если каталог `.artel/canary/<run_stamp>/<task_id>/` существует.
5. Команда только читает (кроме ленивого заведения таблиц внутри `store.all_canary_runs` — `CREATE TABLE IF NOT EXISTS` и `add_column`, — которое команда не меняет и не обходит): строки — `store.all_canary_runs(store.db())`; ни записей журнала, ни правок `canary_runs`/`canary_baseline`, ни сетевых вызовов, ни чтения реестра живых прогонов. Подкоманды `canary live`, `canary pool-seal`, `canary run-task` и запуск прогона (`--k`) не меняются; отказ «нужен параметр --k» для прочих аргументов — прежний.
6. Справка `orchestrator/artel.py`: строка `canary runs [--since <ГГГГ-ММ-ДД> | <run_stamp>]` рядом со строкой `canary live`.
7. Тесты, детерминированные, без сети (строки заводятся прямой вставкой в `canary_runs` песочницы — по образцу записи `canary._record_canary_run` или `INSERT`; корень пульта — песочница `tests/sandbox.py`):
   - три прогона по две задачи с разными вердиктами, стоимостью и причиной отказа — `canary runs` через `artel.main` печатает три заголовка от нового к старому с верными суммами и счётом зелёных, строки задач с полями требования 4 и строку причины отказа (на текущем коде — красный: прежний отказ «нужен параметр --k»);
   - 12 прогонов — без аргументов показаны 10 последних;
   - `--since` отсекает прогоны раньше даты; `<run_stamp>` — ровно один прогон; неизвестный `run_stamp` — отказ и ненулевой код;
   - каждый отказ требования 2 — до чтения БД (подмена `store.db` на функцию, падающую при вызове); в числе отказов — `--since 20261023`, `--since 2026-1-5` и `run_stamp` с хвостом вида `20261023T120000Zxx`;
   - пустая таблица — «прогонов канарейки нет»;
   - после команды число строк `steps`, `canary_runs` и `canary_baseline` не изменилось;
   - `marker_mismatch` = 1 и непустой `escalation_roles` — пометки в строке задачи; `NULL` в `main_sha` — `sha=—`; группа, где `set_name` и `main_sha` первой по `id` строки отличаются от последующих, — в заголовке значения первой строки; `NULL` в `cost_usd` одной из строк — сумма заголовка считает его нулём, строка задачи печатает `$—`.
   Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/canary.py, orchestrator/artel.py, tests/

Ограничение зон по смыслу: в `orchestrator/artel.py` — только ветка `runs` в `_cmd_canary` и строка справки; в `orchestrator/canary.py` — только новая функция `cmd_canary_runs`, константа `CANARY_RUNS_DEFAULT_COUNT` и вспомогательные функции вывода.

Только чтение: orchestrator/store.py, orchestrator/config.py, orchestrator/canary_drive.py, orchestrator/pool_seal.py, orchestrator/models.py (вызывающий `all_canary_runs` — не меняется), docs/operator-session.md, docs/backlog.md.

Не входит: чтение файлов `logs/canary/run-*.json` и журналов эфемерных клонов; сравнение с бейзлайном (`canary_baseline`); фильтр по набору ролей; правка контракта сессии `docs/operator-session.md` о новой команде — строкой `note`/`doc-commit` Оператора после мержа.

Бюджет: $15.
