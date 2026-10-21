---
task: 01M5FGJW4RBN9C9P48Q8MDHJX1
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Ветка задачи task/… удаляется из origin после мержа

## Фаза A: план
- Таблица покрытия полна (требования 1–8 → шаги 1–5); строка 8 теперь
  разделяет долгоживущий файл test_author (свойства уборки) и шаг 5 —
  сторож проводки гейта в `tests/` (закрывает R1-F1).
- Шаги размера MR; подход не конфликтует с архитектурой.
- «Влияние на систему» = diff ветки (`git diff --stat main...HEAD`):
  `orchestrator/cleanup.py`, `orchestrator/fsm_merge_gate.py`,
  `docs/retention.md`, карта, долгоживущий файл задачи и новый
  `tests/test_fsm_merge_gate_remote_branch_cleanup.py`. Изменения
  `orchestrator/canary.py`, `artel.py`, `doctor/*` в диапазоне
  `e2f79120..HEAD` пришли подтяжкой main (`main...HEAD` их не несёт).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Код не менялся с итерации 1 (`git diff e2f79120 HEAD -- orchestrator/cleanup.py orchestrator/fsm_merge_gate.py docs/retention.md` пуст): вызов `cleanup.cleanup_merged_remote` последним в `_cleanup_merged_task` (`fsm_merge_gate.py:1365`), `final_sha` из `_cmd_approve_merge_gate` (`:1533`) после `"ok"`/`_finalize_done_state`. |
| 2 | OK | Как в итерации 1: `ls-remote` и `push --force-with-lease … --delete` с `-c`-парами, три исхода, `is_ancestor`, разбор `None` в `_delete_origin_branch`. |
| 3 | OK | Перехват исключения, одна запись «уборка», подсказки только в выводе. |
| 4 | OK | Вызов после `done`; на `"moved"` (`:1528`) — выход до уборки. Теперь держится сторожем в `tests/` (см. R1-F1). |
| 5 | OK | Только `refs/heads/<branch>`, `gh` не зовётся. |
| 6 | OK | Абзац в `docs/retention.md`. |
| 7 | OK | В гейте — только подпись `_cleanup_merged_task` и её вызов. |
| 8 | OK | Долгоживущий файл задачи — свойства уборки; `tests/test_fsm_merge_gate_remote_branch_cleanup.py` — проводка гейта у артели и внешнего проекта на настоящем git с bare-`origin`. Существующие тесты не правились (diff `tests/` — только два новых файла). |

## Замечания

Новых замечаний нет. Новый тест не повторяет долгоживущий файл задачи
(тот зовёт `cleanup_merged_remote` напрямую, этот — тело
`_cmd_approve_merge_gate`); оба метода несут «Ловит мутацию: …» с
наблюдаемым расхождением (ветка в `origin` / запись «уборка»), заявки
подтверждены временными мутациями (см. «Проверено исполнением»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_merge_gate.py:1365; tests/test_fsm_merge_gate_remote_branch_cleanup.py | Проводка уборки в гейте мержа держалась только разовой планкой | Регресс проводки не ловил бы CI | Принято: добавлен сторож в `tests/` через тело гейта (артель и внешний проект; done → ветки нет, запись «удалена»; moved → ветка на месте, записи нет). Проверено ревьювером: мутация «вызов удалён» → 2 красных (оба done), «уборка до проверки исхода push» → 4 красных; код возвращён |

## Вердикт
approved: R1-F1 закрыт, код уборки соответствует SPEC по требованиям 1–8.

## Проверено исполнением
- `python3 -m pytest -q -p no:xdist tests/test_fsm_merge_gate_remote_branch_cleanup.py`
  — 4 passed.
- Временная мутация 1: строка `cleanup.cleanup_merged_remote(...)` в
  `_cleanup_merged_task` заменена на `pass` — 2 failed
  (`External/ArtelGateWiringTest::test_done_removes_task_branch_from_origin`),
  2 passed; код возвращён `git checkout`.
- Временная мутация 2: `cleanup.cleanup_merged_remote(conn, task_id, branch,
  final_sha)` вставлен между `_push_merged_main` и проверкой `== "moved"` в
  `_cmd_approve_merge_gate` — 4 failed (оба done — две записи «уборка», оба
  moved — ветка удалена); код возвращён, `git status` чист.
- `python3 …/artel.py plank-run 01M5FGJW4RBN9C9P48Q8MDHJX1` — 13 passed, код
  выхода pytest 0.
- `python3 -m pytest -q -p no:xdist tests/test_01m5fgjw4rbn9c9p48q8mdhjx1_merged_remote_cleanup.py
  tests/test_01m568xfym68eyhh0c16y7d7f0_project_kill_cleanup.py
  tests/test_fsm_merge_gate_done_snapshot.py tests/test_merge_gate_ci_wait.py`
  — 48 passed, 26 subtests passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строки `built_at_sha` — пусто (карта свежа, новый тест в ней учтён);
  возвращено `git checkout`.
- `git diff e2f79120 HEAD -- orchestrator/cleanup.py orchestrator/fsm_merge_gate.py docs/retention.md`
  — пусто (код с итерации 1 не менялся); `git diff --stat main...HEAD` —
  6 файлов, ровно зона задачи.
- CI коммита ca1f0120 — зелёный (16 проверок, по пакету).

## Предложения системе
- Инкрементальный diff пакета от sha вердикта захватывает пути, тронутые
  подтяжкой main (`canary.py`, `doctor/*` в `git diff e2f79120 HEAD`), хотя
  пакет обещает «только собственные коммиты» — ревьюверу приходится
  отделять их сверкой с `main...HEAD` вручную.
