---
task: 01M2CN3VV99BTAJF2JBTNADQPH
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рефакторинг R7: checkpoint.py — общий WIP-чекпоинт и фазы переноса артефактов

Источник: отчёт ревизии №6 docs/audits/code-revision-2026-09-13.md, находка
CR-2026-09-13-2 ★ и ТЗ-черновик Р-1; роадмап §3 фаза R, пункт R7 (остаток
по checkpoint.py). Решение Оператора 13.09: волна рефакторинга, задача
класса «рефакторинг» по правилам T015.

Факты:
- orchestrator/checkpoint.py: `_commit_external_step_artifacts` (:534–785,
  252 строки, из них докстринг :535–649 — 115) — пять фаз в одном теле:
  сбор файлов с фильтром .gitignore; журнал посторонних файлов планки и
  корня; конфликт-гвард против baseline; кандидаты на удаление по
  `own_commit_marker`; коммит в артефактную ветку. Переменная `files`
  мутируется в четырёх фазах. Вызовы только внутри модуля (:181, :341,
  :397, :531).
- Тела `commit_timeout_checkpoint` :159–184, `commit_abnormal_checkpoint`
  :319–342, `commit_pause_now_checkpoint` :375–398 построчно одинаковы
  (target -> `_commit_worktree_change` -> журнал / `record_fixation` либо
  `_discard_out_of_mandate_changes` -> `_commit_external_step_artifacts`),
  различаются четырьмя строками текста и флагом `timeout`.
- Контракты, которые сверяют тесты: сигнатура
  `_commit_external_step_artifacts(conn, task_id, role, target, timeout)`
  и строка возврата (tests/test_checkpoint_external_step_artifacts.py:251);
  ПОРЯДОК записей журнала — orchestrator/fsm_advance.py:459 сверяет последнюю
  запись визита с `STRAY_ACCEPTANCE_FILES_ACTION`; tests/test_pause_now.py:61
  патчит публичное имя `commit_pause_now_checkpoint`.

Требуется (поведение не меняется):
1. Общий приватный помощник `_wip_checkpoint(conn, task_id, role, message,
   action, discard_action, discard_detail, timeout)` для трёх одинаковых
   тел; три публичных имени `commit_timeout_checkpoint`,
   `commit_abnormal_checkpoint`, `commit_pause_now_checkpoint` остаются с
   прежними сигнатурами и текстами.
2. `_commit_external_step_artifacts` — пять фаз приватными функциями с
   явными аргументами (`files`, `existing`, `baseline_sha`,
   `own_commit_marker`, строка задачи); сигнатура, строка возврата, ранние
   `return ""` (:679–684, :771–776) и порядок записей журнала — дословно;
   докстринг переносится к фазам без потери содержания.
3. Поверхности неизменности: вывод команд пульта, тексты и порядок записей
   журнала, алерты, схема БД, имена и пути файлов на диске и в артефактной
   ветке. Зелёность полного набора tests/ = неизменность.
4. Тесты: сценарии и ассерты существующих тестов не меняются; допустимы
   только импорты и пути патчей (ожидаемо — нулевые правки). Новых тестов
   на приватные фазы не требуется; если автор тестов добавляет проверки,
   они только фиксируют неизменность (например, что три публичных имени
   существуют и вызывают один помощник).
5. PLAN: таблица переносов (откуда -> куда, строки), откат revert'ом одного
   merge-коммита, смоук до/после на живых данных пульта: `artel.py status`,
   `artel.py report`, `artel.py doctor` без изменяющих флагов —
   сравнение вывода зафиксировать в PLAN.
6. Никаких попутных улучшений; дедупликация только побайтно идентичных
   кусков.

Зоны: orchestrator/checkpoint.py, tests/.

Приложением: orchestrator/fsm_advance.py (:459, сверка порядка журнала —
не правится), tests/test_timeout_checkpoint.py,
tests/test_checkpoint_external_step_artifacts.py, tests/test_pause_now.py,
tests/test_step_autocommit.py, tests/test_checkpoint_zone_filter.py
(контракты; ассерты не меняются).

Не входит: фильтр посторонних файлов, конфликт-гвард, критерий удаления
файлов, `_discard_out_of_mandate_changes` (:186–279) — защита, не трогать;
любая правка fsm_advance.py.

Рамка: $35.
