---
task: 01M6EZXVFGXC6WBDA9QJESAZRW
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab Б2.3-1: отказ при сбое вместо пропуска

Родительская задача: 01M6EXF3TMNRKCZH8CS9BXXG1Z — GitLab Б2.3: хук pre-push в клоне, сверки отправки, строки doctor, отказ при сбое, открытие gitlab и target-human
Зоны: orchestrator/fsm_merge_gate.py, orchestrator/gitcmd.py, orchestrator/github_adapter.py, orchestrator/ci.py, orchestrator/targets.py, tests/
Порядок: после 01M6AB4VE2R0Q2V5D4MMJGNGH7
Рамка: $40

Часть 1 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3). Основание — ADR-0029, находки проверяющих приёмки Б2.1а, Б2.1б, Б2.2 и В1.1 (01.11). Задача идёт до открытия `gitlab`/`target-human` (часть 4).

Требуется. Каждый путь, где сбой чтения пропускает проверку, отказывает с причиной:
- `orchestrator/fsm_merge_gate.py` (`:1516`, вызов `github_adapter.people_entry`, `orchestrator/github_adapter.py:347-355`, сейчас `TargetsError` → `None`). При сбое чтения записи признак гейта не известен, поэтому для задачи любого проекта, кроме артели, сбой чтения записи — отказ гейта мержа «гейт мержа неизвестен», а не путь слияния в `base`. Так же отказывает единая точка отправки (`orchestrator/gitcmd.py:928-932`). Задачи артели — без изменений. Отказ для всех внешних проектов, кроме артели, подтвердил Оператор (возврат с гейта SPEC родителя 02.11);
- `orchestrator/fsm_merge_gate.py` (`_awaiting_limit_refuses`, `:1789-1808`, сейчас `TargetsError` → `False` на `:1796-1797`): сбой чтения записи — отказ, а не пропуск предела `max_awaiting`;
- `orchestrator/gitcmd.py`, три места:
  - `in_flight_refusal` (`:768-775`): `TargetsError`/`sqlite3.Error` → `None`;
  - `_push_plan` (`:956-961`, проверка `policy.max_in_flight`): `sqlite3.Error` → `waiting = None`;
  - `in_repo` (`:1242-1245`): `sqlite3.Error` → `refusal = None`.
  В каждом сбой — отказ отправки с причиной. В `in_repo` отказ только для отправки в проект вне артели, чья запись под белым списком (`targets.push_whitelisted`) или не прочитана. Отправки артели и проектов `operator` при сбое БД идут как прежде;
- `orchestrator/github_adapter.py` (`:173`, сейчас `IN_FLIGHT_LIMIT_REASON in stderr`): отказ пределом различается по коду результата, а не по строке stderr;
- `fsm_merge_gate._mr_incident_stops` (`:1661-1702`, сейчас статус вне трёх значений даёт проход на `:1695-1698`): статус MR вне `opened`/`merged`/`closed` (например `locked` или пустой) — отказ гейта с причиной, а не проход;
- правило ANSWER-1 п. 3 Б2.2 (`orchestrator/mr_sync.py` `:356`; код не меняется, только тест в `tests/`): у открытого MR, чей `sha` уже предок `origin/<base>`, признак (а) не засчитывается, и `mr-sync <id> --confirm` без `--by-content` отказывает;
- проверка записи «`full_suite: ci|both` только для хостинга с чтением отчёта задания» (В1.1) не зависит от того, загружен ли модуль `ci`. Реестр хостингов не подставляется при импорте `ci` (`orchestrator/ci.py:28`, `orchestrator/targets.py:1098`), а загрузка записи в `doctor` без `ci` отказывает так же. `orchestrator/targets.py` в этой части трогается только ради этого пункта.

Признак гейта проекта — помощники `targets.py` (`push_whitelisted`, `merged_by_project_people`). Сравнение значения `forge`/`merge_gate` с литералом вне `targets.py` и новые исключения `EXEMPT` сторожа ac9 (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`) запрещены.

Критерии приёмки:
- на каждый путь, в том числе на каждое из трёх мест `gitcmd`, — тест с подменённым сбоем:
  - сбой подменяется в точке чтения внутри гейта или отправки, а не постоянной подменой загрузчика: постоянный `TargetsError` отказывает раньше, в `repo_context.resolve` (`orchestrator/fsm_merge_gate.py:1508-1514`, `orchestrator/repo_context.py:93-96`), а постоянный `sqlite3.Error` валит отправку исключением в `gitcmd._project_tasks` (`orchestrator/gitcmd.py:215-220`), и такой тест зелёный без правки. Для записи — чтение `people_entry`/`targets.target` внутри `fsm_merge_gate` и `gitcmd`; для БД — чтение названного места (`in_flight_refusal`, проверка `max_in_flight` в `_push_plan`, `in_repo`);
  - тест сверяет возвращённый отказ с причиной, а не летящее исключение;
  - состояние задачи и БД после отказа не изменились;
  - шпион не видит слияния, отправки или открытия MR;
- сбой чтения записи у задачи проекта `github` + `operator` на гейте мержа тоже даёт отказ;
- сбой БД в чтении `in_repo` при отправке артели отказа не даёт;
- тест правила признака (а) `mr_sync` проверяет `--confirm` без `--by-content` и ловит мутацию `state == "merged"` → `True`;
- артель и проекты `github` + `operator` при читаемых записи и БД: поведение и существующие тесты прежние.

Только чтение: `orchestrator/gitlab_adapter.py`, `orchestrator/mr_sync.py`, `docs/adr/0029-external-delivery-via-mr.md`.

Не входит: открытие списков поддержки и тексты отказа (часть 4); хук и сверки отправки (часть 2); сверка MR по веб-хуку хостинга (бэклог).