---
task: 01M6AB4VE2R0Q2V5D4MMJGNGH7
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Б2.2 — команда `mr-sync`: сверка MR и нахождения правки в `base`, закрытие `done` по подтверждению Оператора

## Фаза A: план

- Таблица покрытия полна: требования 1–8 → шаги 1–6; ответы ANSWER-1..3 отражены в «Подходе» и «Влиянии на систему».
- Шаги размера MR, не микрооперации.
- Подход согласован с архитектурой: одна сверка `mr_sync.evaluate` на ручной вызов, `--confirm`, надзор и проверку чужого коммита; закрытие идёт существующим узлом `cleanup._commit_closing`; сверка документов — `artifact_branch.origin_sync_refusal`, то есть узел `_docs_ref_unsynced`.
- Приложение к `tests/test_invariants.py`: `git apply --check` на дереве ветки проходит.
- «Влияние на систему» совпадает с diff: 17 модулей зоны и два существующих теста по мандатам. Вне зоны SPEC ничего не тронуто. Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `forge.py:75-81`, `gitlab_adapter._merge_request`; `ALLOWED_PAIRS` не менялся |
| 2 | OK | `record_fork_point` в `_deliver_mr` перед `set_state`, сверка берёт `row["fork_point"]`; дифф двухточечный |
| 3 | реализовано не так (R1-F1) | таблица итогов и порядок по ANSWER-1 п. 1–3 верны. Строка 1 («любой отказ git → неизвестно») не держится, если в диффе задачи есть файл не в UTF-8 |
| 4 | OK | одна задача, пересчёт, `--by-content` для (в), сверка документов текстом ANSWER-1 п. 7, `closed_as`, RETRO «Закрытие: …», уборка рабочей копии и локальной ветки без отправок и вызовов `forge`, меняющих MR |
| 5 | OK | `_mr_incident_stops` (merged/closed → эскалация, чужой коммит, отказ при сбое — ANSWER-2 п. 2, одно чтение за `approve` — ANSWER-2 п. 1); `accept_server_head` — только для эскалации «чужой коммит» (ANSWER-1 п. 6) |
| 6 | OK | поле и его проверка в `targets.py`; опрос только в надзоре эпика (ANSWER-1 п. 5); первая сверка — тоже смена (ANSWER-2 п. 3); `watch` |
| 7 | OK | `status`/доска (`--md`/`--html`/`--json`); подсказки без «(шаг Б2.2)» |
| 8 | OK | приложение применяется; в обходе команд `mr-sync` сверяет непустой набор; тест строки 18 наблюдает состояние, RETRO и `closed_as` |

Изменённые существующие тесты:
- константа `HINT` — мандат SPEC и ANSWER-1;
- `test_ac15_…` — ровно по ANSWER-2 п. 1: множество, `<= 1` чтения, строка документации;
- метод `FakeForge.mr_status` — ANSWER-3.

Иных изменённых или удалённых утверждений нет, данные под неизменными утверждениями не сужены.

## Замечания

- **major** — `orchestrator/mr_sync.py:100-105` (`_git`), а также `:178`, `:183`, `:190` (`_diff_sign`), `:162-168` (`_commits_sign`: `show`, `log -p`) и `:123-124` (`_apply_passes`: `text=True` на входе патча).
  - Суть: вывод git декодируется строгим UTF-8, а ловится только `OSError`. Файл задачи не в UTF-8 (например, cp1251) даёт `UnicodeDecodeError`. Он выходит мимо `GitFailure` из `evaluate` и `sync_task` наружу.
  - Последствие: SPEC, таблица требования 3, строка 1, требует «любой отказ git → неизвестно с причиной». Вместо этого ручной `mr-sync` без id падает трассировкой на такой задаче. Остальные задачи цикла `cmd_mr_sync` не сверяются, записи журнала и итога у задачи нет.
  - Воспроизведено: `mr_sync._diff_sign` на репозитории с коммитом файла `"Привет\n".encode("cp1251")` бросает `UnicodeDecodeError 'utf-8' codec can't decode byte 0xcf`.
  - Предложение: читать дифф и патчи байтами (`gitcmd.read(..., text=False)`) и подавать байты в `git apply`/`patch-id`; либо декодировать с `errors="surrogateescape"` и сводить сбой декодирования к `GitFailure`. Добавить тест в `tests/` с файлом не в UTF-8 в правке задачи: итог — правильный признак либо «неизвестно», без исключения.
- **minor** — `orchestrator/mr_sync.py:115-127` (`_apply_passes`).
  - Суть: `subprocess.run` вызывается напрямую с `GIT_INDEX_FILE`, мимо `gitcmd.read_env` — функции, которая существует ровно для git с временным индексом. У вызова нет срока и нет плана точки (`_point_plan`).
  - Последствие: зависший `git apply` подвешивает `mr-sync` и опрос надзора эпика без предела.
  - Предложение: перейти на `gitcmd.read_env(repo, env, ..., timeout=…)`.
- **minor** — `orchestrator/mr_sync.py:262-266` (`record_fork_point`) и `:315-316` (`_signs`).
  - Суть: если на `approve` не удались `fetch` или `merge-base`, задача всё равно уходит в `awaiting_human` без точки ответвления.
  - Последствие: каждая следующая сверка — «неизвестно: точка ответвления задачи не записана», `--confirm` невозможен. Выход один — `kill`, хотя люди могли влить MR.
  - Предложение: при пустой точке отказывать `approve` (задача остаётся на гейте, повтор `approve`) — по образцу отказа `mr_status` в ANSWER-2 п. 2. Либо явно назвать путь восстановления в подсказке итога.
- **minor** — `tests/test_mr_sync_units.py:37-48` (`test_foreign_commit_escalation_accepts_server_head`).
  - Суть: тест повторяет свойство, которое уже держит долгоживущий `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py::test_ac14_foreign_commit_sync_escalates_then_accepted_head`: после `answer` + `approve` голова сервера принята, следующая сверка не эскалирует. Это нарушает ADR-0020 п. 4.
  - Последствие: два сторожа одного свойства, правка механики — правка в двух местах.
  - Предложение: оставить в файле только отрицательную половину (`test_other_escalation_does_not_accept_head`), её долгоживущий файл не держит.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/mr_sync.py:100 (также :123, :162-168, :178, :183, :190) | строгий UTF-8 вывода git; `UnicodeDecodeError` не сводится к `GitFailure` | `mr-sync` падает трассировкой на файле не в UTF-8, остальные задачи не сверены; нарушена строка 1 таблицы требования 3 | читать байтами или `surrogateescape`, сбой декодирования → «неизвестно»; тест в `tests/`. Разработчик: `_git`/`_out_bytes` читают вывод байтами (`gitcmd.read`), `_out` декодирует `surrogateescape`, патчи в `patch-id`/`git apply` идут байтами (файлом), показ путей — `_shown` со знаком замены; истечение срока git — `GitFailure`; тест `tests/test_mr_sync_units.py::NonUtf8DiffTest::test_signs_on_cp1251_file` (краснеет на строгом декодировании) |
| R1-F2 | fixed | orchestrator/mr_sync.py:115 | `_apply_passes` — прямой `subprocess.run` без срока, мимо `gitcmd.read_env` | зависший `git apply` подвешивает сверку и надзор эпика | `gitcmd.read_env` со сроком. Разработчик: `_apply_passes` (`mr_sync.py:132`) — `gitcmd.read_env` со сроком `GIT_TIMEOUT_SEC` (60 с) и на `read-tree`, и на `apply`; `Timeout`/`OSError`/сбой декодирования → `GitFailure` («неизвестно») |
| R1-F3 | fixed | orchestrator/mr_sync.py:262 | точка ответвления не вычислена — переход в `awaiting_human` всё равно идёт | задача навсегда в итоге «неизвестно», закрытие невозможно, только `kill` | отказ `approve` при пустой точке или явный путь восстановления. Разработчик: `fsm_merge_gate._deliver_mr` считает точку (`mr_sync.fork_point`) до любых вызовов MR; не вычислена — отказ `approve` с причиной, задача на гейте, MR не тронут; тест `tests/test_mr_sync_units.py::test_gate_refuses_without_fork_point` (краснеет без отказа) |
| R1-F4 | fixed | tests/test_mr_sync_units.py:37 | повтор свойства долгоживущего AC-14 (принятая голова) | двойной сторож одного свойства (ADR-0020 п. 4) | оставить только отрицательную половину. Разработчик: `test_foreign_commit_escalation_accepts_server_head` убран (файл новый в ветке, в base его нет), оставлен `test_other_escalation_does_not_accept_head` |

## Вердикт

`changes_requested`: исправить R1-F1 (major), решить R1-F2–R1-F4 (minor). Всё остальное — соответствие SPEC и ANSWER-1..3, неослабление тестов, приложение к инвариантам — в порядке.

## Проверено исполнением

- `python3 -m pytest tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_awaiting_hint.py tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_fields.py tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py tests/test_mr_sync_units.py tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_commands.py -q -p no:cacheprovider -x` — 102 passed за 124.8 с.
- `artel.py plank-run 01M6AB4VE2R0Q2V5D4MMJGNGH7` — 1 passed, код выхода pytest 0.
- `git apply --check -v` приложения PLAN к `tests/test_invariants.py` — «Checking patch tests/test_invariants.py...», код 0.
- Воспроизведение R1-F1: `mr_sync._diff_sign` на временном репозитории с правкой файла в cp1251 → `UnicodeDecodeError 'utf-8' codec can't decode byte 0xcf in position 97`.

## Предложения системе

- В чек-листе ревью нет пункта «кодировка вывода внешних git-команд» для кода, который читает дифф чужих проектов (`target-human`). Класс проблемы: `text=True` без `errors=` на диффе недоверенного репозитория.
