---
task: 01M5K11D3284ZZGRHN39FGQVF2
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/artifact_branch.py, orchestrator/doctor/artifact_branches.py, tests/
budget_usd: 45
---

# SPEC: Отправка документов задачи: ответ сервера 5xx — отдельная причина с повтором, запись успеха после отказа, снятие send_pending

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-5. `orchestrator/artifact_branch.py:320`
(`_classify_push_failure`) относит к non-fast-forward любое вхождение
`rejected`, поэтому ответы сервера (`remote: Internal Server Error … [remote
rejected] … (Internal Server Error)`, `[remote rejected] … (failed)`,
`fatal error in commit_refs … (failure)`) — 47 записей журнала на 23.10 —
записаны как расхождение истории с советом «свести merge-коммитом», а строки
`HTTP 5xx`/`returned error: 5xx` — как «сеть». `_attempt_push`
(`orchestrator/artifact_branch.py:336`) делает один `git push` без повтора.
Успех отправки журналирует только `push` (её зовёт лишь `doctor --fix`),
все три вызова `_send` передают `journal_success=False` — по журналу не
отличить «дослано» от «не дослано». `send_pending`
(`orchestrator/artifact_branch.py:418`) не вызывается нигде, хотя докстринг
модуля (строки 24–27) обещает досылку через неё; фактически досылку на
переходе делает коммит паспорта (`store.set_state` → `_append_passport_line`
→ `append_passport_line` → `commit_files` → `_send`). Выбор Оператора в ТЗ —
снять `send_pending` вместе с обещанием, не вызывать её.

## Требования

1. В модуле `orchestrator/artifact_branch.py` появляется причина
   `PUSH_REASON_SERVER = "сервер"`. `_classify_push_failure` по `stderr`
   (без учёта регистра) проверяет признаки строго в порядке:
   - (а) `[rejected]` (локальный отказ git, не `[remote rejected]`),
     `fetch first` или `non-fast-forward` — non-fast-forward;
   - (б) признаки сервера: `internal server error`, `fatal error in
     commit_refs`, код HTTP 5xx в тексте git (`HTTP 5\d\d`, `returned
     error: 5\d\d`), строка отказа `[remote rejected] … (failed)` — точная
     форма: скобка с одним словом `(failed)` в конце строки отказа —
     «сервер»; `(failed to update ref)` и `(failure)` признаком «сервер» не
     являются (решение Оператора на гейте SPEC 23.10.2026, круг 1) и без
     других признаков (б) идут по пункту (в);
   - (в) любое другое вхождение `rejected` (например, `[remote rejected] …
     (pre-receive hook declined)`, `[remote rejected] … (failed to update
     ref)`, `[remote rejected] … (failure)`) — non-fast-forward, как прежде;
   - (г) остальное — «сеть».
   Намеренная смена поведения: строки с `HTTP 5xx` и `returned error: 5xx`
   сейчас дают «сеть», после правки — «сервер» с повтором требования 2.
2. Повтор при «сервер»: `_attempt_push` повторяет `git push` той же ссылки
   не более `PUSH_SERVER_RETRY_ATTEMPTS` раз всего (константа модуля
   `artifact_branch`, значение 3) с паузой
   `time.sleep(PUSH_SERVER_RETRY_PAUSE_SEC)` (константа модуля, значение 5)
   только между попытками: после последней попытки паузы нет, всего пауз не
   больше `PUSH_SERVER_RETRY_ATTEMPTS − 1`; модуль импортирует `time` на
   уровне модуля. Иные причины (non-fast-forward, «сеть») не повторяются:
   один вызов `git push`, без паузы. Повторы идут без силы: ни в одном
   вызове `git push` нет `--force`, `--force-with-lease` и `+` в refspec —
   как прежде.
   `_attempt_push` возвращает, кроме успеха, причины и stderr, число
   сделанных попыток `git push`; `push` и `_send` переходят на новую форму
   возврата, поведение `push` иначе не меняется.
3. Запись отказа «сервер»: действие «push артефактной ветки FAILED», деталь —
   `сервер (попыток N): <stderr до 300 символов>`, без совета свести историю
   и без пары sha. Запись отказа non-fast-forward — прежняя побайтно.
4. Запись успеха: `_send` журналирует успех (действие «push артефактной
   ветки», деталь называет ссылку; если успех пришёл после повтора, деталь
   содержит `попыток N`, где N — число сделанных вызовов `git push`) в двух
   случаях — успех пришёл после повтора в том же вызове, либо последняя
   запись исхода отправки этой задачи в журнале — «push артефактной ветки
   FAILED». Последняя запись читается
   `store.last_task_step_of(conn, task_id, ("push артефактной ветки", "push
   артефактной ветки FAILED"))` (`orchestrator/store.py:1185`); нового запроса
   к БД в модуле отправки нет. Прочие успехи не журналируются.
5. `send_pending` удаляется. Докстринг модуля `artifact_branch` и докстринг
   `_fix_unsent_closed_refs` (`orchestrator/doctor/artifact_branches.py`)
   называют фактический путь досылки — коммит паспорта на переходе
   (`store.set_state` → `append_passport_line`); упоминаний `send_pending` в
   коде пульта (`orchestrator/`) нет. В `orchestrator/doctor/artifact_branches.py`
   меняется только этот докстринг.
6. Тесты требований 1–5 детерминированы и без сети: ответ `git push`
   подменяется через модульную `artifact_branch._git`, пауза — через
   ссылку модуля `artifact_branch.time` (объект-заместитель с подменённым
   `sleep`; глобальная подмена `time.sleep` запрещена сторожем
   `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`), при
   необходимости — константы `PUSH_SERVER_RETRY_ATTEMPTS`/
   `PUSH_SERVER_RETRY_PAUSE_SEC`; песочницы — `tests/sandbox.py`, по образцу
   `tests/test_artifact_branch_push.py` и `tests/test_artifact_ref_sync.py`.
   Существующие тесты не правятся (в том числе их докстринги, упоминающие
   `send_pending`).

## Критерии приёмки

AC-1. `stderr` вида `remote: Internal Server Error … ! [remote rejected] …
(Internal Server Error)` классифицируется как «сервер»
(`PUSH_REASON_SERVER == "сервер"`); на коде до правки — non-fast-forward.

AC-2. `stderr` `! [remote rejected] … (failed)` и `remote: fatal error in
commit_refs … (failure)` классифицируются как «сервер».

AC-3. `! [rejected] … (fetch first)` — non-fast-forward, как прежде, и запись
отказа non-fast-forward побайтно прежняя (с парой sha и советом «свести
merge-коммитом»); `! [remote rejected] … (pre-receive hook declined)` —
non-fast-forward (порядок (в) требования 1) без повтора: `git push` вызван
один раз, пауза не вызвана.

AC-4. `fatal: unable to access …: The requested URL returned error: 503` и
`error: RPC failed; HTTP 502` классифицируются как «сервер» (на коде до правки
— «сеть»).

AC-5. `stderr`, где есть и `[rejected] … (fetch first)`, и `Internal Server
Error`, классифицируется как non-fast-forward (порядок (а) старше (б)).

AC-6. Отправка, получившая «сервер», затем успех: `git push` вызван дважды,
пауза — один раз с аргументом `PUSH_SERVER_RETRY_PAUSE_SEC` (значение
константы — 5); в журнале задачи запись успеха «push артефактной ветки» и нет
записи «push артефактной ветки FAILED».

AC-7. «Сервер» на всех попытках: `git push` вызван
`PUSH_SERVER_RETRY_ATTEMPTS` раз (значение константы — 3); в журнале ровно
одна запись «push артефактной ветки FAILED» с деталью, начинающейся с
`сервер (попыток 3): `, без «свести merge-коммитом» и без пары sha.

AC-8. Отказ «сеть», затем успешная отправка следующего коммита — в журнале
появляется запись успеха «push артефактной ветки»; две успешные отправки
подряд без отказа перед ними — записей успеха нет.

AC-9. `hasattr(artifact_branch, "send_pending")` ложно; в файлах
`orchestrator/` нет вхождения `send_pending`; досылка на переходе работает —
существующий
`tests/test_artifact_ref_sync.py::SendAfterCommitTest::test_refusal_is_journaled_commit_kept_and_retried_on_transition`
зелёный без правок.

AC-10. Отказ «сеть» (например, `fatal: unable to access …: Could not resolve
host`) не повторяется: `git push` вызван ровно один раз, пауза не вызвана.

AC-11. При повторе по «сервер» (сценарии AC-6 и AC-7) ни в одном вызове
`git push` нет аргумента `--force`, аргумента `--force-with-lease` (в любой
форме, в том числе `--force-with-lease=…`) и refspec, начинающегося с `+`.

AC-12. `! [remote rejected] … (failed to update ref)` и `! [remote rejected] …
(failure)` без иных признаков «сервер» классифицируются как non-fast-forward,
не «сервер»; `git push` вызван один раз, пауза не вызвана.

AC-13. Отправка, получившая «сервер», затем успех (сценарий AC-6): деталь
записи успеха «push артефактной ветки» содержит `попыток 2`.

AC-14. Число пауз равно числу сделанных попыток минус один: в сценарии AC-6
пауза вызвана 1 раз, в сценарии AC-7 — `PUSH_SERVER_RETRY_ATTEMPTS − 1` раз
(2); после последней попытки паузы нет.

## Оценка объёма и деление

Прогноз диффа: 20 КиБ

Сработавшие сигналы: «число затрагиваемых модулей/файлов» — guard считает
пути `orchestrator/*.py` по всему тексту, а SPEC называет ради границ
(«Не входит») больше десятка файлов только для чтения; фактически
меняются два файла кода (`orchestrator/artifact_branch.py` и докстринг в
`orchestrator/doctor/artifact_branches.py`) и новые тесты в `tests/`.
«Затронут инвариантный механизм» — `docs/invariants.md`, инвариант 33,
называет `artifact_branch.write_commit`/`commit_files` как плотницкую запись
через единую точку подмены `gitcmd`; задача эту точку не трогает: повтор
`git push` идёт тем же модульным `_git`. «Прогноз диффа не дан» снят
строкой выше (порог — 128 КиБ). «Число критериев ≥ 10» и «`budget_usd` ≥
$30» — после дополнений Оператора на гейте SPEC 23.10.2026 (круг 1)
критериев 14; пять новых (AC-10–AC-14) — негативные и уточняющие проверки
того же повтора и той же классификации, не новая механика.

**Обоснование монолита.** Причина «сервер» (требование 1), повтор по ней
(требование 2), запись отказа с числом попыток (требование 3) и запись
успеха (требование 4) — одна смена формы `_attempt_push` (новое значение в
возврате) и её двух вызывающих (`push`, `_send`) в одном модуле: часть
без повтора оставляет запись «сервер (попыток N)» без смысла, часть без
классификации — повтор без причины. Снятие `send_pending` (требование 5) —
несколько строк того же модуля и докстринг; отдельная задача ради него
стоила бы больше самой правки. Объём — одна задача класса ~$45 (14
критериев, 3 зоны: `config.BUDGET_CALIBRATION_TABLE`, уровень «до 15
критериев и до 7 файлов»). Решение по
монолиту — за Оператором на гейте SPEC.

## Не входит

- Отдельная причина «отказ прав/хука» для прочего `[remote rejected]`.
- Автоматическая досылка коммита закрытия после гейта без `doctor --fix`.
- Переклассификация прежних записей журнала.
- Признаки «main сдвинулся» гейта мержа (`_MAIN_MOVED_PUSH_MARKERS`,
  `orchestrator/fsm_merge_gate.py`).
- Логика `doctor` (`orchestrator/doctor/artifact_branches.py` — только
  докстринг `_fix_unsent_closed_refs`; `orchestrator/doctor/cli.py` не
  меняется).
- Правки вызывающих `commit_files`/`commit_change`/`origin_sync_refusal`/
  `push` (`orchestrator/store.py`, `snapshot.py`, `cleanup.py`,
  `fsm_merge_gate.py`, `catalog.py`, `answer.py`, `amend.py`, `checkpoint.py`,
  `fixation.py`, `canary.py`, `advance_gates/tests_writing.py`,
  `doctor/ignored_artifacts.py`) и `orchestrator/watch.py`,
  `orchestrator/schema.py`, `scripts/guard.py`, `orchestrator/gitcmd.py`,
  `orchestrator/config.py` — только чтение; их поведение меняется лишь паузой
  повтора при ответе сервера.
- Изменение ожиданий существующих тестов `tests/` (раздела «Меняемое
  поведение» нет): случаи `tests/test_artifact_branch_push.py::ClassifyPushFailureTest`
  не содержат строк `HTTP 5xx`/`returned error: 5xx` и остаются прежними.
- Полный зелёный набор `tests/` и зелёный CI ветки — их держит пульт.

## Материалы

- ТЗ: `tasks/01M5K11D3284ZZGRHN39FGQVF2/TZ.md`; ревизия кода 22.10,
  CR-2026-10-22-5 (`docs/audits/code-revision-2026-10-22.md` копии ревизии).
- Бюджет: ТЗ называет $20; поставлено $45 — класс калибровки для 14
  критериев и 3 зон (`orchestrator/config.py::BUDGET_CALIBRATION_TABLE`),
  ниже дефолта пульта $50; пол калибровки $25
  (`BUDGET_CALIBRATION_FLOOR_USD`) ТЗ-шные $20 не пропускает.
- Решения Оператора на гейте SPEC 23.10.2026, круг 1 (по SPEC-AUDIT.md,
  вердикт concerns): критерии AC-10–AC-14 и точная форма признака `(failed)`
  в требовании 1 (б); существующие тесты не правятся, мандат не нужен.
- Карта `docs/codebase-map.md` перечисляет `send_pending` — правка `*.py`
  в `orchestrator/` требует регенерации карты (общая зона).
