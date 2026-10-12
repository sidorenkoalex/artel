---
task: 01M4R4JKC28J80Z82TZA62RF2J
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Отвеченный батч вопросов аналитика не эскалирует задачу повторно

## Подход
Две стороны одной механики, связанные строкой журнала (схема БД не
меняется).

**Запись (approve).** `orchestrator/fsm.py`:
- константа `QUESTIONS_ANSWERED_ACTION = "батч вопросов отвечен"` и
  разборщик detail `_QUESTIONS_ANSWERED_DETAIL`
  (`sha256=<64 hex>; ANSWER-<n>`);
- `_questions_batch_sha256(text)` — sha256 UTF-8 байтов текста, одна
  функция для обоих путей (требование 4);
- `_questions_text` — `QUESTIONS.md` тем же источником, что
  `spec_writing`: `artifact_source.resolve` → `artifact_branch.show` на
  ветке документов, диск `config.TASKS` только при `foreign=False`; сбой
  чтения → `None` без отказа (требование 2);
- `_latest_answer_number` — максимум `n` среди `ANSWER-*.md` тем же
  источником и тем же разбором, что `brief._latest_answer_rel`
  (требование 3);
- `_mark_questions_answered` вызывается в `_approve_escalated` после
  сверки числа ANSWER и проверки «ответ роли» и до `update_task`/
  `set_state` — только при `escalated_from == "spec_writing"` и
  непустом `answer_baseline` (требование 1, AC-1/AC-2);
- `_last_questions_answered` — (хэш, n) только ПОСЛЕДНЕЙ строки признака.

**Чтение (spec_writing).** `orchestrator/fsm_advance.py`:
`_answered_batch_skip(conn, task_id, text)` — хэш текущего батча равен
хэшу последней строки признака И `auto._role_step_since_state_entry(conn,
id, "spec_writing", "analyst")` даёт «шаг был» (тот же рубеж, что
пред-advance `auto`, но вызывается в самом переходе — ручной `advance`
тоже держится, требования 5, 8). Тогда пишется строка
`QUESTIONS_SKIPPED_ACTION` («батч вопросов признан отвеченным») с detail
«батч вопросов признан отвеченным (ANSWER-n): sha256=…», guard на
`QUESTIONS.md` не вызывается, переход идёт по SPEC.md; при переходе в
`spec_audit`/`spec_gate` формулировка дописывается в detail перехода
(требование 7). Проверка встроена в оба пути (ветка и диск) ДО guard;
непрочитанный с диска файл — `None`, ведёт себя как сегодня. Сам файл
не трогается (требование 6). `auto` импортируется лениво внутри функции
— тем же приёмом, что `runner` в этом же обработчике.

Расхождения с оценкой SPEC нет: две функции, константа, без новых
модулей; `budget_usd` не переоценивается.

## Шаги
1. `orchestrator/fsm.py`: константа, хэш, чтение батча и номера ANSWER,
   запись признака в `_approve_escalated`, разбор последнего признака.
2. `orchestrator/fsm_advance.py`: `_answered_batch_skip`,
   `_disk_questions_text`, встраивание в оба пути `spec_writing` и в
   detail перехода.
3. `docs/codebase-map.md` — регенерирован `scripts/codebase_map.py`.
4. Тесты: долгоживущий файл задачи
   `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py` (AC-1 —
   AC-10, мутации (а)-(д)) — зелёный, 15 passed / 28 subtests; свои тесты
   не добавлялись: все требования покрыты этим файлом (правило
   coding-standards «только на свойства, не покрытые долгоживущими»).
   Тесты затронутых модулей (13 файлов: answer*, approve*, analyst_role,
   artifact_escalation_marker, spec_audit_flow, questions_matrix,
   fsm_branch_correct_status_reads и др.) — 136 passed. Полный набор —
   `suite-run` (итог ниже, в «Риски»).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 4 |

## Влияние на систему
- Рубеж «сначала шаг аналитика» (`ARTIFACT_ESCALATION_ROLE_STEP_MARKER`,
  `auto._role_step_since_state_entry`) не меняется — только
  переиспользуется; пропуск батча строго требует шага аналитика после
  анкера, так что рубеж не ослабляется, а дублируется в переходе.
- Guard на `QUESTIONS.md` не вызывается только для батча, совпадающего
  побайтно с уже прошедшим guard и отвеченным батчем; любой иной текст —
  прежний путь (эскалация + guard).
- Новая строка журнала на approve только у эскалаций `spec_writing` с
  baseline; detail переходов `spec_writing -> spec_audit/spec_gate`
  меняется только при пропуске (точных читателей этих detail в
  `orchestrator/`/`scripts/` нет — проверено grep).
- Схема БД, `canary.py`, `auto.py`, `brief.py` не тронуты.
- Откат — revert одного merge-коммита: строки признака в журнале
  останутся мёртвыми и безвредными.

## Риски
- После возврата в `spec_writing` не из эскалации (reject/возврат аудита)
  анкером рубежа становится этот вход: ручной `advance` до шага
  аналитика эскалирует отвеченный батч снова — это буква требования 5
  («после последнего входа в spec_writing»), пред-advance `auto` в этом
  случае и так ждёт шага роли.
- Полный набор: `suite-run` №1 — 5116 passed, 5 failed (все «новые на
  ветке», но вне зоны задачи: `test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock`
  ×3, `test_01m462qaceh29rprd2rzhghqfm_suite_run`,
  `test_01m4araxf7vss5xz8c99bx8de2_suite_observation` — замок/тайминги
  прогона, шёл параллельно с моим модульным прогоном); повтор
  `suite-run --failed` №2 — 5 passed, 0 failed.
- Тесты затронутых модулей (20 файлов + долгоживущий файл задачи):
  196 passed, 1 subtest упал по таймауту 120 с под нагрузкой
  (`test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py::AcceptAuditFailTest::test_ac20_fail_verdict_needs_flag_in_both_forms`),
  отдельно — зелёный (90 с).
- Планка: `plank-run` — «в refs/artifacts нет файлов test_*.py», pytest не
  запускался; требования покрыты долгоживущим файлом задачи (15 passed /
  28 subtests).

## Предложения системе
- `ls`/`cat` в песочнице роли отказаны («command not found»/требует
  подтверждения) — листинг каталога документов пришлось делать
  `python3 -c os.walk`; копилке стоит знать, что роль лишена базового
  листинга (`.artel/home/.claude/settings.json`).
