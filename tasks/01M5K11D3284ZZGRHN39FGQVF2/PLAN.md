---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## Подход
Одна правка `orchestrator/artifact_branch.py`:
- `PUSH_REASON_SERVER = "сервер"`; `_classify_push_failure` проверяет признаки
  по порядку (а) `[rejected]`/`fetch first`/`non-fast-forward` → (б) признаки
  сервера (`internal server error`, `fatal error in commit_refs`,
  `http 5\d\d`, `returned error: 5\d\d`, строка `[remote rejected] … (failed)`
  в конце строки — regex с `re.MULTILINE`) → (в) прочий `rejected` → (г) «сеть».
- `_attempt_push` возвращает четвёрку `(ok, reason, stderr, attempts)`; при
  «сервер» повторяет тот же `git push -q origin ref:ref` (без силы) до
  `PUSH_SERVER_RETRY_ATTEMPTS` (3) раз, `time.sleep(PUSH_SERVER_RETRY_PAUSE_SEC)`
  (5) только между попытками. Константа читается в момент вызова.
- `_journal_push_outcome` получает `attempts`: отказ «сервер» —
  `сервер (попыток N): <stderr[:300]>` без пары sha и совета; non-fast-forward —
  побайтно прежний; успех после повтора — суффикс ` (попыток N)`.
- `_send(task_id, repo)` без флага `journal_success`: успех пишется, если
  `attempts > 1` или последняя запись исхода отправки задачи
  (`store.last_task_step_of`) — FAILED. При непригодной БД (`store.db_usable`)
  чтение не делается: успешная отправка раньше БД не трогала.
- `send_pending` удалена; докстринги модуля и `_fix_unsent_closed_refs`
  называют досылку коммитом паспорта на переходе.

## Шаги
1. Правка `orchestrator/artifact_branch.py` и докстринга
   `orchestrator/doctor/artifact_branches.py::_fix_unsent_closed_refs`;
   регенерация `docs/codebase-map.md`.
2. Юнит-тесты `tests/test_artifact_branch_server_retry.py` (форма признака
   `(failed)`, регистр и старшинство (б) над (в), HTTP 4xx — «сеть», счёт
   попыток и чтение потолка в момент вызова, прекращение повтора при смене
   причины). Мутации проверены вручную: `\(failed` без привязки к концу строки
   и потолок `3` вместо константы — оба красят свой тест.
3. Итерация 2 (R1-F1, R1-F2): планка целиком разовая, поэтому свойства
   требований 1–4 перенесены сторожами в `tests/test_artifact_branch_server_retry.py`:
   `ClassifyServerSignsTest` (5xx, `fatal error in commit_refs`, (а) старше (б)),
   `test_pause_uses_module_constant` (аргумент паузы), `SendJournalTest`
   (песочница БД `SchemaSeededTmpRootTest`: деталь отказа «сервер», успех
   после повтора с `попыток 2`, успех после записанного FAILED, тишина двух
   успехов). Восемь мутаций по одной — каждая красит ровно один тест.
   Пробел `last = store.…` поправлен.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1, 3 |
| 4 | 1, 3 |
| 5 | 1 |
| 6 | 2 (планка AC-1..AC-14 — test_author) |

## Влияние на систему
- Вызывающие `commit_files`/`push`/`origin_sync_refusal` не меняются; их
  поведение меняется только паузой до 2×5 с при ответе сервера.
- Инвариант 33 (плотницкая запись через `gitcmd`) не затронут: повтор идёт
  тем же модульным `_git`. Силы в push нет ни в одной попытке.
- Существующие тесты не правились; `tests/test_artifact_branch_push.py`,
  `tests/test_artifact_ref_sync.py` (включая AC-9 тест досылки на переходе),
  `tests/test_01m409…_project_docs_ref.py`, `tests/test_01m484…_artel_docs_ref.py`,
  `tests/test_merge_gate_ci_wait.py` — 64 passed. Планка `plank-run` — 15 passed.
  Итерация 2: server_retry + artifact_branch_push + artifact_ref_sync — 37 passed;
  server_retry + sleep_guard — 18 passed; планка — 15 passed.
- Откат — revert merge-коммита.

## Риски
- Успешная отправка теперь читает журнал (один `SELECT … LIMIT 1`) на каждом
  коммите документов — дешёвый запрос по индексу задачи.

## Предложения системе
- Запись во `/tmp` из Bash роли требует подтверждения, которого в шаге никто
  не даёт; скрипт-правка через heredoc в `/tmp` молча неприменима — стоит
  упомянуть в conventions-core, что временные файлы пишутся только в рабочий
  каталог.
