---
task: 01M2CN3VV99BTAJF2JBTNADQPH
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/checkpoint.py, tests/
budget_usd: 35
---

# SPEC: Рефакторинг R7: checkpoint.py — общий WIP-чекпоинт и фазы переноса артефактов

## Контекст
Источник: отчёт ревизии №6 `docs/audits/code-revision-2026-09-13.md`,
находка CR-2026-09-13-2 ★ и ТЗ-черновик Р-1; роадмап §3 фаза R, пункт R7
(остаток по `checkpoint.py`). `orchestrator/checkpoint.py` несёт два
дефекта дублирования без изменения поведения:

- `commit_timeout_checkpoint` (:159–184), `commit_abnormal_checkpoint`
  (:319–342) и `commit_pause_now_checkpoint` (:375–398) построчно
  одинаковы (target -> `_commit_worktree_change` -> журнал /
  `record_fixation` либо `_discard_out_of_mandate_changes` ->
  `_commit_external_step_artifacts`), различаются четырьмя строками
  текста и флагом `timeout`.
- `_commit_external_step_artifacts` (:534–785, 252 строки, из них
  докстринг :535–649 — 115) несёт пять фаз в одном теле: сбор файлов с
  фильтром `.gitignore`; журнал посторонних файлов планки и корня;
  конфликт-гвард против baseline; кандидаты на удаление по
  `own_commit_marker`; коммит в артефактную ветку. Переменная `files`
  мутируется в четырёх фазах.

Решение Оператора 13.09: волна рефакторинга, задача класса
«рефакторинг» по правилам T015.

## Требования

1. Общий приватный помощник `_wip_checkpoint(conn, task_id, role,
   message, action, discard_action, discard_detail, timeout)` заменяет
   три одинаковых тела `commit_timeout_checkpoint`,
   `commit_abnormal_checkpoint`, `commit_pause_now_checkpoint`; все три
   публичных имени остаются с прежними сигнатурами и прежними текстами
   сообщений/журнала.
2. `_commit_external_step_artifacts` разбита на пять фаз приватными
   функциями с явными аргументами (`files`, `existing`, `baseline_sha`,
   `own_commit_marker`, строка задачи); сигнатура, строка возврата,
   ранние `return ""` (:679–684, :771–776) и порядок записей журнала
   сохраняются дословно; докстринг переносится к фазам без потери
   содержания.
3. Поведение не меняется ни по одной из поверхностей: вывод команд
   пульта, тексты и порядок записей журнала, алерты, схема БД, имена и
   пути файлов на диске и в артефактной ветке. Зелёность полного
   набора `tests/` подтверждает неизменность.
4. Существующие тесты (`tests/test_timeout_checkpoint.py`,
   `tests/test_checkpoint_external_step_artifacts.py`,
   `tests/test_pause_now.py`, `tests/test_step_autocommit.py`,
   `tests/test_checkpoint_zone_filter.py`) не меняют сценарии и
   ассерты — допустимы только правки импортов и путей патчей. Новых
   тестов на приватные фазы не требуется; если разработчик их
   добавляет, они только фиксируют неизменность (например, что три
   публичных имени существуют и делегируют общему помощнику).
5. `orchestrator/fsm_advance.py` (в т.ч. строка :459, сверяющая порядок
   журнала) не правится.

## Критерии приёмки

AC-1. Три публичные функции `commit_timeout_checkpoint`,
`commit_abnormal_checkpoint`, `commit_pause_now_checkpoint` сохраняют
прежние сигнатуры и прежние тексты сообщений коммитов/журнала и
делегируют общему приватному помощнику `_wip_checkpoint(conn, task_id,
role, message, action, discard_action, discard_detail, timeout)`.

AC-2. `_commit_external_step_artifacts` разбита на пять приватных
функций-фаз (сбор файлов с фильтром `.gitignore`; журнал посторонних
файлов планки и корня; конфликт-гвард против baseline; кандидаты на
удаление по `own_commit_marker`; коммит в артефактную ветку) с явными
аргументами (`files`, `existing`, `baseline_sha`, `own_commit_marker`,
строка задачи), при этом сигнатура `_commit_external_step_artifacts(conn,
task_id, role, target, timeout)`, строка возврата, ранние `return ""`
(:679–684, :771–776 исходного файла) и порядок записей журнала не
меняются.

AC-3. Полный набор `tests/` зелёный без правки сценариев/ассертов
существующих тестов — допустимы только правки импортов и путей
патчей.

AC-4. Смоук на живых данных пульта (`artel.py status`, `artel.py
report`, `artel.py doctor` без изменяющих флагов) до и после
рефакторинга даёт совпадающий вывод; сравнение зафиксировано в PLAN.

AC-5. PLAN несёт таблицу переносов кода (откуда -> куда, строки
исходного файла) и описывает откат — revert одного merge-коммита.

AC-6. `orchestrator/fsm_advance.py` не изменён; дедупликация
затрагивает только побайтно идентичные куски — без попутных
улучшений, изменения поведения фильтра посторонних файлов,
конфликт-гварда, критерия удаления файлов или
`_discard_out_of_mandate_changes` (:186–279).

## Не входит

- Фильтр посторонних файлов, конфликт-гвард, критерий удаления файлов,
  `_discard_out_of_mandate_changes` (:186–279) — защита, не трогать.
- Любая правка `orchestrator/fsm_advance.py`.
- Любые попутные улучшения и дедупликация не побайтно идентичных
  кусков.

## Материалы

- `docs/audits/code-revision-2026-09-13.md`, находка CR-2026-09-13-2.
- Роадмап §3, фаза R, пункт R7.
- Контракты: `tests/test_checkpoint_external_step_artifacts.py:251`
  (сигнатура и строка возврата), `orchestrator/fsm_advance.py:459`
  (порядок записей журнала — сверка с `STRAY_ACCEPTANCE_FILES_ACTION`),
  `tests/test_pause_now.py:61` (патч публичного имени
  `commit_pause_now_checkpoint`).
