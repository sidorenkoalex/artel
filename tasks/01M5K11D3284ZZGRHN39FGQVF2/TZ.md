---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

# Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-5 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии; строка бэклога «Отправка документов задачи: ответ 5xx — не расхождение истории (CR-2026-10-22-5)», сливает копилку 02.10 01M3XTF1CE, 21.10 01M5FGJW4R и 20.09). Ссылки сверены с `origin/main` bd01a928; файлы ниже между пином и `origin/main` не менялись.

- Классификация отказа: `orchestrator/artifact_branch.py:320` (`_classify_push_failure`) — подстрока `"rejected"` (а с ней и `[remote rejected]`), `"fetch first"` или `"non-fast-forward"` → `PUSH_REASON_NON_FAST_FORWARD`, остальное → `PUSH_REASON_NETWORK`; причины — `orchestrator/artifact_branch.py:55`–`57`. Запись отказа non-fast-forward добавляет совет «свести merge-коммитом» — `orchestrator/artifact_branch.py:353` (`_journal_push_outcome`).
- Журнал БД (только чтение, по состоянию на 23.10): отказов «push артефактной ветки FAILED» с текстом `remote: Internal Server Error … [remote rejected] … (Internal Server Error)` — 15, с `[remote rejected] … (failed)` — 31, с `remote: fatal error in commit_refs … (failure)` — 1; все записаны как non-fast-forward с советом свести историю. Причина «сеть» (`SSL_connect` и подобное) — 10 записей, классифицируется верно.
- Попытка отправки: `orchestrator/artifact_branch.py:336` (`_attempt_push`) — один вызов `git push` без повтора. Отправка после коммита и на сверке: `orchestrator/artifact_branch.py:404` (`_send`); все три вызова передают `journal_success=False` — `orchestrator/artifact_branch.py:315` (после `update-ref` в записи коммита), `orchestrator/artifact_branch.py:425` (тело досылки на переходе), `orchestrator/artifact_branch.py:444` (досылка перед сверкой с origin).
- Успех журналирует только `push` (`orchestrator/artifact_branch.py:378`), которую зовёт лишь `doctor --fix` (`orchestrator/doctor/artifact_branches.py:165`). Последняя запись «push артефактной ветки» (успех) — 03.10 06:29Z: по журналу не отличить «дослано» от «не дослано».
- `send_pending` (`orchestrator/artifact_branch.py:418`) не вызывается нигде (`git grep "send_pending(" origin/main -- orchestrator` — только определение), хотя докстринг модуля (`orchestrator/artifact_branch.py:24`–`27`) обещает «повтор — на следующем переходе (`send_pending` из `store.set_state`)». **Выбор: снять `send_pending` вместе с обещанием, не вызывать.** Обоснование по коду: обещанная досылка на переходе уже исполняется другим путём — `store.set_state` на каждом переходе зовёт `orchestrator/store.py:960` (`_append_passport_line`) → `orchestrator/artifact_branch.py:694` (`append_passport_line`) → `commit_files` → запись коммита со сверкой головы → `_send`, и коммит паспорта отправляет всю ссылку вместе с недосланными коммитами (докстринг `_append_passport_line` прямо называет это повтором отправки; тест `tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition` это закрепляет). Вызов `send_pending` в `set_state` дал бы второй `git push` той же ссылки на каждом переходе без нового результата; закрытая задача переходов не имеет и досылается `doctor --fix` (`orchestrator/doctor/artifact_branches.py:180`, `_fix_unsent_closed_refs`), её докстринг упоминает `send_pending`.
- Страховки, которые не меняются: `orchestrator/artifact_branch.py:428` (`origin_sync_refusal` — сверка с origin на гейте мержа и при закрытии); `_fix_unsent_closed_refs` в `doctor --fix`. Отказ, пришедший на коммит закрытия после гейта (01M42NB9GK, 01M4XVM49P), ловит только ручной `doctor --fix` — повтор при ответе сервера уменьшает такие случаи.
- Вызывающие `commit_files`/`commit_change`/`origin_sync_refusal`/`push` вне зон (их поведение меняется только паузой повтора при ответе сервера): `orchestrator/store.py`, `orchestrator/snapshot.py`, `orchestrator/cleanup.py`, `orchestrator/fsm_merge_gate.py`, `orchestrator/catalog.py`, `orchestrator/answer.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/fixation.py`, `orchestrator/canary.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/doctor/ignored_artifacts.py`. Признаки «main сдвинулся» гейта мержа — отдельный набор `orchestrator/fsm_merge_gate.py` (`_MAIN_MOVED_PUSH_MARKERS`), им не пользуется.
- Строки с `HTTP 5xx` и `returned error: 5xx` без слова `rejected` сейчас классифицируются как «сеть» (остаток `_classify_push_failure`).
- Чтение последней записи журнала задачи по набору действий есть готовое: `orchestrator/store.py:1185` (`last_task_step_of(conn, task_id, actions)` — одна запись, `ORDER BY id DESC LIMIT 1`).
- `_attempt_push` возвращает тройку (успех, причина, stderr); её зовут `_send` и `push` (`orchestrator/artifact_branch.py:390`).
- `docs/codebase-map.md` перечисляет `send_pending`; карта пересобирается на мерже (общая зона пульта, перечень общих зон в `orchestrator/config.py`).

## Требуется

1. Новая причина `PUSH_REASON_SERVER = "сервер"`. `_classify_push_failure` по `stderr` (регистр не важен) проверяет признаки строго в таком порядке:
   - (а) `[rejected]` (локальный отказ git, не `[remote rejected]`), `fetch first` или `non-fast-forward` — non-fast-forward;
   - (б) признаки сервера: `internal server error`, `fatal error in commit_refs`, код HTTP 5xx в тексте git (`HTTP 5\d\d`, `returned error: 5\d\d`), строка `[remote rejected] … (failed)` или `(failure)` — «сервер»;
   - (в) любое другое вхождение `rejected` (например, `[remote rejected] … (pre-receive hook declined)`) — non-fast-forward, как прежде;
   - (г) остальное — «сеть».
   Намеренная смена поведения: строки с `HTTP 5xx` и `returned error: 5xx` сейчас дают «сеть», после правки — «сервер» с повтором требования 2; существующие случаи `tests/test_artifact_branch_push.py::ClassifyPushFailureTest` этих строк не содержат, не меняются и остаются зелёными.
2. Повтор при «сервер»: `_attempt_push` повторяет `git push` той же ссылки не более `PUSH_SERVER_RETRY_ATTEMPTS` раз всего (константа модуля `artifact_branch`, значение 3) с паузой `time.sleep(PUSH_SERVER_RETRY_PAUSE_SEC)` (константа модуля, значение 5) между попытками; модуль импортирует `time` на уровне модуля. Иные причины не повторяются. Без `--force` в любой форме — как прежде. `_attempt_push` возвращает, кроме успеха, причины и stderr, число сделанных попыток `git push` (для детали «попыток N» требований 3 и 4); `push` и `_send` переходят на новую форму возврата, поведение `push` иначе не меняется.
3. Запись отказа «сервер»: действие «push артефактной ветки FAILED», деталь — `сервер (попыток N): <stderr до 300 символов>`, без совета свести историю и без пары sha. Запись non-fast-forward — прежняя побайтно.
4. Запись успеха: `_send` журналирует успех (действие «push артефактной ветки», деталь называет ссылку и, если были, число попыток) в двух случаях — успех пришёл после повтора в том же вызове, либо последняя запись исхода отправки этой задачи в журнале — «push артефактной ветки FAILED». Последняя запись читается `store.last_task_step_of(conn, task_id, ("push артефактной ветки", "push артефактной ветки FAILED"))` (`orchestrator/store.py:1185`); нового запроса к БД в модуле отправки нет. Прочие успехи по-прежнему не журналируются (журнал не засоряется строкой на каждую строку паспорта).
5. `send_pending` удаляется; докстринг модуля `artifact_branch` и докстринг `_fix_unsent_closed_refs` (`orchestrator/doctor/artifact_branches.py`) называют фактический путь досылки — коммит паспорта на переходе (`store.set_state` → `append_passport_line`); упоминаний `send_pending` в коде пульта нет.
6. Тесты, детерминированные, без сети (подменяются модульная `artifact_branch._git` для ответа `git push`, `artifact_branch.time.sleep`, при необходимости константы `PUSH_SERVER_RETRY_ATTEMPTS`/`PUSH_SERVER_RETRY_PAUSE_SEC`; песочницы — `tests/sandbox.py`, по образцу `tests/test_artifact_branch_push.py` и `tests/test_artifact_ref_sync.py`):
   - stderr с `remote: Internal Server Error … ! [remote rejected] … (Internal Server Error)` — причина «сервер» (на текущем коде — красный: non-fast-forward);
   - stderr `! [remote rejected] … (failed)` и `remote: fatal error in commit_refs … (failure)` — «сервер»;
   - `! [rejected] … (fetch first)` — non-fast-forward, как прежде; `! [remote rejected] … (pre-receive hook declined)` — non-fast-forward (порядок (в) требования 1), без повтора: `git push` вызван один раз;
   - `fatal: unable to access …: The requested URL returned error: 503` и `error: RPC failed; HTTP 502` — «сервер» (на текущем коде — «сеть»);
   - stderr, где есть и `[rejected] … (fetch first)`, и `Internal Server Error`, — non-fast-forward (порядок (а) старше (б));
   - «сервер», затем успех — `git push` вызван дважды, `sleep` — один раз с `PUSH_SERVER_RETRY_PAUSE_SEC`, в журнале запись успеха и нет записи FAILED;
   - «сервер» на всех попытках — `PUSH_SERVER_RETRY_ATTEMPTS` вызовов push, одна запись FAILED с деталью требования 3 (`сервер (попыток 3): …`), без «свести merge-коммитом»;
   - отказ «сеть», затем успешная отправка следующего коммита — запись успеха; два успеха подряд без отказа — записей успеха нет;
   - `send_pending` в модуле нет (`hasattr(artifact_branch, "send_pending")` ложно), а досылка на переходе работает — существующий `tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition` зелёный без правок.
   Существующие тесты не правятся и остаются зелёными (их докстринги, упоминающие `send_pending`, не правятся).

Зоны: orchestrator/artifact_branch.py, orchestrator/doctor/artifact_branches.py, tests/

Ограничение зон по смыслу: в `orchestrator/doctor/artifact_branches.py` — только докстринг `_fix_unsent_closed_refs`; логика `doctor` не меняется.

Только чтение: orchestrator/doctor/cli.py (вызывающий `_fix_unsent_closed_refs` — не меняется), orchestrator/schema.py, scripts/guard.py, orchestrator/store.py, orchestrator/snapshot.py, orchestrator/cleanup.py, orchestrator/fsm_merge_gate.py, orchestrator/catalog.py, orchestrator/answer.py, orchestrator/amend.py, orchestrator/checkpoint.py, orchestrator/fixation.py, orchestrator/canary.py, orchestrator/advance_gates/tests_writing.py, orchestrator/doctor/ignored_artifacts.py, orchestrator/gitcmd.py, orchestrator/config.py, orchestrator/watch.py (вызывающий `last_task_step_of` — не меняется).

Не входит: отдельная причина «отказ прав/хука» для прочего `[remote rejected]`; автоматическая досылка коммита закрытия после гейта без `doctor --fix`; переклассификация прежних записей журнала; признаки «main сдвинулся» гейта мержа (`_MAIN_MOVED_PUSH_MARKERS`).

Бюджет: $20.
