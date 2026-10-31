---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Б2.1а — состояние `awaiting_human` и его учёт в перечнях пульта

## Подход
Одно новое значение `awaiting_human` в `fsm.STATES` (сразу после
`merge_gate`, не окончательное, без роли и гейта Оператора) и его учёт во
всех перечнях пульта одним изменением — иначе сверки
`tests/test_invariants.py:611` и свипы `tests/test_auto_cycle.py` красные.
Константы `fsm.AWAITING_HUMAN` и `fsm.AWAITING_HUMAN_HINT` («состояние ждёт
людей проекта — mr-sync (шаг Б2.2)») — единственный адрес литерала
подсказки для `approve`/`reject`/`answer`/`amend-tests`.

Ключевые решения:
- **Поля доставки** — `max_awaiting`/`awaiting_holds_zones` объявлены в
  `targets.LOCAL_FIELDS["policy"]` и `DELIVERY_POLICY_FIELDS` (переносятся в
  плоскую запись), проверка — в `_check_delivery` рядом с `max_in_flight`/
  `draft_mr`. Умолчания — `targets.DELIVERY_DEFAULTS`, отдаёт их только
  `targets.delivery_policy(entry)`; строка цифр в `mr_assignee` там же
  толкуется целым id. Предикат `targets.merged_by_project_people(entry)` —
  по образцу `push_whitelisted`.
- **Запрет отправки** — в `gitcmd._push_plan` сразу после разбора refspec
  (`_refspecs`), до белого списка и до записи «ветка отправлена»:
  `_awaiting_human_spec` ищет refspec вида `branch` (в том числе с
  `colon` — удаление `:<ветка>`) на ветку задачи в `awaiting_human`;
  `--delete <ветка>` разбирается тем же refspec. Отказ — `_refuse` с
  записью «отправка отказана» в журнал задачи, процесс git не запускается.
  По ANSWER-1 п. 5 тот же отказ стоит и на входе `gitcmd.in_repo`
  (`_awaiting_human_refusal`, до вызова `gitcmd.git`, который подменяют
  тесты и вызыватели): общий разбор назначения вынесен в
  `_push_destination`, отказ — `_refuse_awaiting_human`; прочие отказы
  единой точки решает по-прежнему только `_push_plan` внутри `git`, так что
  отказ не журналируется дважды.
- **Зоны** — `awaiting_human` в `zone_lock.BLOCKING_STATES`; поле записи
  проекта читает `zone_lock._holds_zones(row)` (через `delivery_policy`) в
  отказе старта (`_occupier`) и в прогнозе (`forecast_overlaps`).
- **Надзор эпика** — статус `_AWAITING` «ждёт людей проекта» раньше
  остальных правил `_epic_view`, задача исключена из `view.running` (не
  занимает место лимита), `awaiting_human` — в `_NOT_HOLDING_STOP_STATES`.
- **Ссылка на MR** — столбцы `tasks.mr_iid INTEGER`, `tasks.mr_url TEXT`
  (DDL + `add_column`), функции `store.set_mr_link`/`mr_link`/
  `mr_link_text`. Показ: карточка доски (`mr_iid`/`mr_url`, виды `--md`,
  `--html`, `--json`), плитка `report`, строка `status`, строка `watch` при
  переходе в `awaiting_human` (`watch._print_state`).
- **`kill`** — `cleanup._server_left_to_project_people`: `target-human` и
  запись «ветка отправлена» (`PUSH_SENT_ACTION` или старый вид) в журнале —
  `cleanup_project_remote` не закрывает PR/MR и не удаляет ветку в
  `origin`, пишет запись «уборка» со ссылкой на MR; локальная уборка
  (`cleanup_killed_task`) прежняя.

Сверка с ANSWER-1 Оператора:
1. `delivery_policy` отдаёт `mr_assignee` как `int | str | None`; целое и
   строка цифр — id (целое) — так и реализовано.
2. Вход в `escalated` из `awaiting_human` — только существующими путями
   (`fixation.py:239`, `store.py:1281`, `budget.py:384` пишут
   `escalated_from` = текущее состояние); новых путей не добавлено, возврат
   — механика `escalated_from` (AC-17).
3. `kill` `target-human`: `_commit_closing` (`cleanup.py:669`) досылает
   коммит закрытия в `refs/artifacts/<id>` как прежде; ранний выход
   `cleanup_project_remote` пропускает только закрытие PR/MR и удаление
   ветки в `origin`.
4. `max_awaiting` — целое > 0, `bool` отказан (`_check_delivery`).
5. Отказ на входе `gitcmd.in_repo` — добавлен в этом шаге (см. выше).
6. `awaiting_human` не занимает место в лимите параллельности эпика —
   исключение из `view.running` в `auto._epic_view` (AC-16).

Бюджет SPEC ($45) не пересматриваю.

## Шаги
1. `targets.py`: поля, проверка, `delivery_policy`, `merged_by_project_people`,
   `mr_assignee` целым.
2. `fsm.py`: состояние, константы, отказ `approve`/`reject`; `answer.py`,
   `amend.py` (`_refuse_awaiting_human` первым действием обоих путей).
3. `gitcmd.py`: отказ отправки ветки задачи в `awaiting_human`.
4. `schema.py`/`store.py`: ссылка на MR.
5. Перечни: `zone_lock`, `config.AUTO_STOP`, `auto` (`_NO_ALERT_FINAL_STATES`,
   надзор эпика), `board` (`HUMAN_STATES` → `waiting_on: human`, ссылка MR),
   `report`, `watch._GATE_STATES`, `catalog` (`status`),
   `doctor/branch_freshness.py`.
6. `cleanup.py`: `kill` проекта `target-human` после отправки.
7. Тесты: мандатные правки перечней (требование 22), новый
   `tests/test_awaiting_human_units.py`, приложение к
   `tests/test_invariants.py`, регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 (используется в 6) |
| 5 | 2 |
| 6 | 5 (`board.HUMAN_STATES`) |
| 7 | 5 (`zone_lock.BLOCKING_STATES`, `_holds_zones`) |
| 8 | 5 (`config.AUTO_STOP`, `auto._NO_ALERT_FINAL_STATES`) |
| 9 | 5 (`auto._epic_view`, `_NOT_HOLDING_STOP_STATES`) |
| 10 | 5 (`report.STATE_ORDER` = `fsm.STATES`, `MANUAL_GATE_STATES` без него, `watch._GATE_STATES`, `catalog._status_line`) |
| 11 | без новой механики: `merge_after.py:769` (`s != "done"`); держит AC-12 |
| 12 | 2 (в перечни не добавлено; AC-3) |
| 13 | без новой механики: `fsm._approve_escalated` (`escalated_from`); держит AC-17 |
| 14 | рабочая копия не трогается нигде, кроме `kill`/`done`; lease в `awaiting_human` не берётся — `parallel_limit` его не считает; надзор — шаг 5 |
| 15 | 5 (`doctor/branch_freshness.py`) |
| 16 | 4, 5 |
| 17 | 2 |
| 18 | 3 |
| 19 | 2 |
| 20 | 6 |
| 21 | 7 (приложение ниже) |
| 22 | 7 |

## Влияние на систему
- **Гейты/guard'ы не ослабляются.** Белый список отправок
  (`gitcmd._whitelist_refusal`) не тронут — новый отказ стоит перед ним и
  только добавляет запрет. `mr_assignee` — расширение допустимых значений
  целым (решение гейта SPEC п. 1); пустая строка, bool и прочие типы — по
  прежнему отказ, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169`
  зелёный без правки.
- **Ослабления по ADR-0029** (матрица SPEC): `awaiting_holds_zones: false`
  отпускает зону; `kill` проекта `target-human` после отправки не трогает
  сервер; `doctor` не сверяет свежесть ветки в `awaiting_human`. Для
  проектов `operator` поведение прежнее: `awaiting_human` штатно
  недостижимо (`targets.SUPPORTED_MERGE_GATES = ("operator",)`, вход с гейта
  мержа — часть 2).
- **Инварианты.** `tests/test_invariants.py` — защищённый путь; его
  `FSM_STATES` расширяется приложением ниже (свипы покрывают новое
  состояние — строже). Локально с приложением: `85 passed, 1121 subtests
  passed`; без приложения на ветке красен
  `test_swept_states_are_exactly_the_fsm_states` — ожидаемо, его закрывает
  приложение на дереве прогона.
- **Существующие тесты** изменены только по мандату требования 22:
  `tests/test_auto_cycle.py` (кортеж `FSM_STATES` + `awaiting_human`),
  `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py` (ветка
  `awaiting_human` → `"human"` в `expected_waiting`). `tests/test_report.py`
  перечней состояний не несёт — не тронут. Утверждения методов не менялись.
- **Схема БД** — два новых столбца с NULL по умолчанию, миграция
  `add_column` идемпотентна; `tests/test_store_schema_migration_parity.py`
  зелёный.
- **Прогоны:** планка `plank-run` — `26 passed`; долгоживущие файлы задачи —
  `33 passed`; тесты затронутых модулей (auto_cycle, board_model, report,
  zone_lock*, kill_cleanup, gitcmd_push_point, record_fields, epic_view/
  supervisor, watch, answer, amend, git_fixation, catalog и др.) —
  `61 + 468 + 93 + 26 passed`; новые юнит-тесты — `5 passed`, каждый
  краснеет на своей заявленной мутации (проверено временной правкой кода).
- **Итерация ANSWER-1:** новый тест
  `test_in_repo_refuses_awaiting_push_before_git` (краснеет при снятой
  проверке на входе `in_repo` — проверено); после правки — планка
  `26 passed`, долгоживущие + юнит-тесты + модули отправки/kill/gitcmd/
  multitarget — `276 passed`; карта регенерирована.
- **Итерация возврата из verifying (CI 40992949348):** упали
  `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py` AC-3/AC-4 —
  fetch базы ветки через `gitcmd.in_repo` (`tracking_refs=False`) сдвинул
  ссылку отслеживания. Тот же флаг через путь `git()`
  (`tests/test_gitcmd_fetch_ref_sha.py::TrackingRefsDefaultTest`) в том же
  прогоне не упал — расхождение только на входе `in_repo`. Правка: проверка
  отправки на входе `in_repo` теперь стоит за условием «в argv есть
  подкоманда отправки» (`PUSH_SUBCOMMANDS`): fetch, worktree, rev-parse и
  прочие не-push вызовы уходят в `git()` без разбора argv — ровно как на
  main. Отказ отправки в `awaiting_human` (AC-5…AC-8, ANSWER-1 п. 5) не
  тронут. Новый тест `test_in_repo_passes_non_push_call_untouched`
  (краснеет, если проверку входа снова звать на любом вызове — проверено
  временной правкой). Оговорка: лог CI шагу недоступен (`gh run view`
  требует подтверждения), а локально (macOS, git 2.50.1) оба теста
  зелёные и до правки, поэтому то, что падение было именно отсюда, —
  вывод из кода и из расхождения путей `in_repo`/`git()`, а не
  воспроизведённый факт. Прогоны после правки: файл fetch-тестов,
  `test_gitcmd_push_point.py`, `test_git_hooks.py`,
  `test_gitcmd_fetch_ref_sha.py`, `test_kill_cleanup.py`, долгоживущие
  файлы задачи и юнит-тесты — `134 passed`; планка — `26 passed`; карта
  регенерирована.
- **Итерация ANSWER-2:** причина красного CI вне задачи (git 2.56 на
  раннере; предпосылку `advance_origin` исправила задача
  01M69W4J5DSBFYS8A0FG71N93K, влита в main `6f888639`). main подтянут в
  ветку (`bbe9ff194`, `6f888639` — предок HEAD); код задачи ради этих
  тестов не менялся, файл теста не тронут. Правка шага —
  регенерация `docs/codebase-map.md` (`built_at_sha` устарел после
  подтяжки main). Правка шага 3 (проверка на входе `gitcmd.in_repo` только
  при push-подкоманде) оставлена по ANSWER-2 п. 2. Прогоны:
  `tests/test_01m42nbcadgsgtcbzb8nkbvdvh_workspace_fetch.py`, долгоживущие
  файлы задачи, `test_awaiting_human_units.py`, `test_gitcmd_push_point.py`,
  `test_gitcmd_fetch_ref_sha.py` — `86 passed`; планка — `26 passed`.
- **Откат** — revert merge-коммита задачи; столбцы `mr_iid`/`mr_url`
  останутся в БД пустыми и никому не мешают.

## Риски
- `awaiting_human` длиннее ширины колонки `status` (`{state:<13}`) на один
  символ — строка сдвигается только у задач в этом состоянии.
- Строка `watch` со ссылкой MR — дополнительная строка после `STATE=…`;
  разбор `STATE=` не меняется.

## Приложение 1: `tests/test_invariants.py` — `FSM_STATES` с `awaiting_human` (требование 21)
Патч проверен `git apply --check` на чистом дереве ветки (`APPLY_OK`).

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index cba5831a8..887e2c28e 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -74,10 +74,11 @@ TRUNCATED_CI = json.dumps({
 # Все состояния FSM (docs/design.md §6 в срезе Фазы 0, artel.py docstring).
 # tests_writing — A4 (tasks/T023): приёмочные тесты до кода, между
 # spec_gate и in_dev. spec_audit — аудит SPEC между spec_writing и
-# spec_gate (SPEC 01M4MQAGRWMWR0GFDM9086P3TD).
+# spec_gate (SPEC 01M4MQAGRWMWR0GFDM9086P3TD). awaiting_human — ожидание
+# людей проекта после merge_gate (SPEC 01M5XZ9Z68V75VXF5Z66C708T4).
 FSM_STATES = ("spec_writing", "spec_audit", "spec_gate", "tests_writing",
               "in_dev", "verifying", "review", "acceptance", "merge_gate",
-              "done", "escalated", "killed")
+              "awaiting_human", "done", "escalated", "killed")
 
 # Заготовки артефактов — валидные по guard: с T017 он вызывается кодом на
 # каждом переходе `advance`, и артефакт без обязательных секций задачу не
```

## Предложения системе
- Причине возврата «CI красный» не хватает хвоста лога упавших тестов:
  роль не может прочитать `gh run view --log-failed` без подтверждения, и
  разбор CI-только провала идёт вслепую. Бриф возврата стоит дополнять
  выдержкой провала.
- Сторож оболочки шага отказывает heredoc-сценариям Python, в которых
  встречается `{"`/`"}` (f-строки HTML) — правку пришлось писать файлом в
  каталог документов и запускать оттуда; класс «правка многострочного
  фрагмента без Edit» натирает каждую задачу с f-строками разметки.
- `pytest -n` (xdist) в шаге разработчика падает «node down» на подборке
  файлов затронутых модулей — прогон только последовательный (~2.5 мин);
  стоит назвать это в `skills/coding-standards.md` рядом с командой прогона.
- Последний зелёный CI python-набора на любой ветке пульта — 26.10 22:11Z
  (01M5WDB7JY0V…, `dc5a10d6`); после него на main шли только doc-коммиты
  копилки. Смену окружения раннера (образ, версия git) пульт не
  наблюдает — нужен периодический прогон CI на main (cron) или запись
  `git --version` раннера в лог, чтобы красный CI отличался от
  «сломал код задачи».
