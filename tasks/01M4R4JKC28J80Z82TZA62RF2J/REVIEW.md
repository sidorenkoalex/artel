---
task: 01M4R4JKC28J80Z82TZA62RF2J
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Отвеченный батч вопросов аналитика не эскалирует задачу повторно

## Фаза A: план
- Таблица покрытия полна (требования 1-9 → шаги 1, 2, 4); шаги размера MR.
- Подход (строка журнала вместо колонки БД, переиспользование
  `auto._role_step_since_state_entry` в самом переходе) не конфликтует с
  архитектурой; «Влияние на систему» совпадает с diff: тронуты только
  `orchestrator/fsm.py`, `orchestrator/fsm_advance.py` и карта; `canary.py`,
  `auto.py`, `brief.py` и схема БД не тронуты. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `fsm.py` `_approve_escalated`: `_mark_questions_answered` вызывается после сверки baseline (`count <= baseline` → return) и до `update_task`/`set_state`; условие `escalated_from == "spec_writing" and baseline is not None`. Флаг `--no-answer` сверку baseline не обходит (проверил тело: проверка baseline стоит выше, флаг влияет только на `unanswered_role_step_escalation`) — признак без нового ANSWER не пишется. Источник — `artifact_source.resolve` + `artifact_branch.show`, диск только при `foreign=False`. Константа `QUESTIONS_ANSWERED_ACTION` в `fsm.py`. |
| 2 | OK | `_questions_text` → `None` при сбое/отсутствии; approve продолжается (AC-3 зелёный). |
| 3 | OK | `_latest_answer_number` — максимум `n`, разбор как в `brief._latest_answer_rel`; тот же источник. |
| 4 | OK | `_questions_batch_sha256` — одна функция, sha256 UTF-8; используется и в approve, и в обоих путях `spec_writing`. |
| 5 | OK | `_answered_batch_skip`: сравнение только с последней строкой (`rows[-1]`), затем проверка шага analyst через `auto._role_step_since_state_entry(..., "spec_writing", "analyst")`; встроено до `guard_refuses` в обоих путях (ветка: после `_read_branch_text_or_refuse`; диск: `_disk_questions_text`). Анкер — возврат из эскалации, помеченной `ARTIFACT_ESCALATION_ROLE_STEP_MARKER` (`_mark_artifact_escalation` пишется в той же ветке эскалации), — значит шаг до эскалации не засчитывается (AC-8/AC-9 зелёные, мутация проверена). |
| 6 | OK | Файл не трогается. |
| 7 | OK | Строка `QUESTIONS_SKIPPED_ACTION` на каждый пропуск; суффикс `; батч вопросов признан отвеченным (ANSWER-n)` в detail обоих переходов (`spec_audit`/`spec_gate`). |
| 8 | OK | Рубеж в `auto.py` не изменён, только переиспользован. |
| 9 | OK | Покрыто долгоживущим файлом задачи `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py` (заявки «Ловит мутацию» на (а)-(д) есть, наблюдаемы — состояние задачи/строки журнала/вызов guard). Существующие тесты не изменены (diff `tests/` пуст вне лока). |

Наблюдения без последствий (не замечания, в реестр не заносятся):
`fsm_advance._disk_questions_text` дублирует дисковую ветку
`fsm._questions_text` (можно было переиспользовать); `_mark_questions_answered`
при `number is None` молчит без print, в отличие от ветки «не прочитан» —
сценарий практически недостижим, т.к. сверка baseline уже увидела ≥1 ANSWER.

## Замечания

Нет замечаний уровня blocker/major/minor со сценарием последствий.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py tests/test_artifact_escalation_marker.py` — 28 passed, 28 subtests passed (11.9 с).
- Временная мутация 1 (`fsm_advance._answered_batch_skip`: убрана проверка `if not ran: return None`) — красные AC-8 (4 подтеста), AC-9 (2 подтеста), AC-10 (д): 7 failed. Код возвращён, `git status` чистый.
- Временная мутация 2 (`fsm._last_questions_answered`: `rows[-1]` → `rows[0]`, сравнение с ранней строкой признака) — красные AC-6 «возврат к раннему батчу» (2 подтеста) и AC-10 (в): 3 failed. Код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md`: расхождение только в строке `built_at_sha` — карта свежа; изменение откачено.
- `artel.py plank-run 01M4R4JKC28J80Z82TZA62RF2J` — «планки нет: в refs/artifacts нет файлов test_*.py; pytest не запускался» (все критерии вынесены в долгоживущий файл, ожидаемо).
- CI коммита 8514a8ca зелёный (16 проверок) — по пакету; полный набор `tests/` в шаге не запускался (решение Оператора 05.09).

## Предложения системе
- Шаблон REVIEW требует строку реестра на каждое замечание, а гейт `review -> verifying` не пускает `approved` с не-`accepted` записью — minor-замечание в первой итерации поэтому некуда положить, не блокируя аппрув (`templates/REVIEW.md`, `skills/review-checklist.md`, раздел «Реестр замечаний»): стоит разрешить статус/класс «к сведению» для minor.
