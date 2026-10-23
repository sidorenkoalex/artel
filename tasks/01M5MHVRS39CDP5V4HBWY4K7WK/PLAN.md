---
task: 01M5MHVRS39CDP5V4HBWY4K7WK
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

## Подход
В `orchestrator/lease.py` сразу после `run_locked` добавлена
`run_task_command(task_id, session_id, body)`: `store.db()` ->
`store.resolve_task_id` -> `run_locked(conn, task_id, session_id,
lambda sid: body(conn, task_id))`, возврат — возврат `run_locked`;
именованные аргументы `run_locked` не передаются. Семь команд таблицы SPEC
заменяют три строки обвязки одним вызовом `lease.run_task_command(task_id,
session_id, <тело>)`. Где тело принимает ровно `(conn, task_id)`
(`_cmd_spec_audit`, `_cmd_pull_main`, `_cmd_workspace`, `_cmd_run`) — функция
передаётся по имени (поиск глобала в момент вызова команды, поэтому
`mock.patch.object(<модуль>, "_cmd_…")` действует); где есть добавочные
аргументы (`_cmd_reject`, `_cmd_ci_rerun`, `_cmd_zones_extend`) —
лямбда `lambda conn, tid: _cmd_X(conn, tid, …)`, id — параметр лямбды.
`cmd_run` возвращает результат обвязки. В докстрингах `cmd_reject`,
`cmd_workspace`, `cmd_ci_rerun`, `cmd_run` «ЗДЕСЬ» заменено ссылкой на
`lease.run_task_command`; остальные три докстринга не тронуты. Импорты
`store` во всех шести модулях остаются используемыми — не удалялись.

## Шаги
1. `lease.run_task_command` + перевод семи команд + правка четырёх
   докстрингов; новый `tests/test_lease_run_task_command.py` с проверками
   (а)–(г); регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (функция в lease.py) | 1 |
| 2 (делегирование семи команд) | 1 |
| 3 (докстринги) | 1 |
| 4 (тестовый файл (а)–(г)) | 1 |
| 5 (существующие тесты не правятся) | 1 |
| 6 (ограничение зон) | 1 |

Проверка:
- `python3 -m pytest tests/test_lease_run_task_command.py
  tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py` — 9 passed.
- `artel.py plank-run 01M5MHVRS39CDP5V4HBWY4K7WK` — 5 passed (в т.ч. AC-8:
  новый файл красен на базе ≥3 проверками).
- Тесты, держащие поведение (SPEC «Материалы»): `test_workspace`,
  `test_01m3xtf5506gf43hd51ece230t_role_refusal`,
  `test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main`,
  `test_pull_conflict_marker_states`,
  `test_01m52eehsrd93wmphwb5vjyrkd_profile_callers`,
  `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow`,
  `test_task_id_prefix_regression`, `test_lease` — 165 passed.
- Мутация: лямбда `cmd_reject` с внешним `task_id` -> краснеют (в) и (г);
  код возвращён.

## Влияние на систему
Поведение команд не меняется: порядок «резолв префикса -> lease -> тело ->
release» и умолчания `run_locked` (`on_refusal="exit"`, `same_host_ok=False`,
`force=False`) прежние, тело получает то же соединение и полный id.
`run_locked` и прочие функции `lease.py` не тронуты; `answer.py` — только
`cmd_zones_extend`. Гейты, лимиты, существующие тесты не меняются (только
новый файл в `tests/`). Откат — revert коммита ветки.

## Риски
- Передача тела по имени вместо лямбды: если тест подменяет `_cmd_*` через
  `patch.object` модуля — подмена видна (глобал ищется при вызове команды);
  проверено (г) и планкой AC-10.

## Предложения системе
- В Bash шага роли команды с `$VAR`/циклами/`;` с `sed -i` упираются в
  подтверждение — временную мутацию сторожа удобнее делать Edit'ом; скил
  coding-standards («проверяй временной мутацией») об этом не говорит.
