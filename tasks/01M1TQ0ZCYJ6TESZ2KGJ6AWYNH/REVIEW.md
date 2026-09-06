---
task: 01M1TQ0ZCYJ6TESZ2KGJ6AWYNH
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 5
---

# REVIEW: артефактная ветка новой задачи заводится от origin/main, а не от пина

## Замечание к пакету ревью (диагностика перед вердиктом)

Инкрементальный diff пакета (от sha предыдущего вердикта
`51db90007811af9b9e61676a3a776df448fd97f4` до HEAD) — пуст: HEAD кодовой
ветки не сдвинулся с этого коммита. Это тот самый sha, на котором был
вынесен предыдущий вердикт (iteration 3, `approved`) — то есть после
итерации 3 в коде и артефактах задачи не изменилось ничего; ветка
осталась ровно там, где её оставил разработчик после iteration 3.
Отказ advance («вердикт REVIEW.md (status=approved, iteration=3) уже
учтён — жду новый прогон ревьювера с iteration: 4») требует не нового
материала, а нового ПРОГОНА проверки на том же материале — что и
сделано этим шагом: код и тесты перепроверены заново, а не переписан
вердикт по памяти.

Проверка `git log` подтверждает: HEAD (`51db9000`) — коммит «карта
кодовой базы после подтяжки main (сведение Оператором)», предыдущий
(`4ea79328`) — «подтяжка main (сведение Оператором...)». Оба сделаны
ПОСЛЕ вынесения iteration-3 вердикта Оператором при сведении подтяжки
main (принесла параллельно смёржённую задачу 01M1TQ0X14, независимую от
этой). `git diff fbc398e0 HEAD -- orchestrator/artifact_branch.py
orchestrator/catalog.py orchestrator/doctor.py orchestrator/gitcmd.py`
показывает добавление кода push-журналирования (`_attempt_push`,
`_classify_push_failure`, `_journal_push_outcome`,
`PUSH_REASON_*`) — это код параллельной задачи 01M1TQ0X14
(SPEC 01M1TQ0X14Y5B3C87WC0Q31PK2, требование 1), не этой; функции этой
задачи (`_new_branch_parent`, `gitcmd.fetch_head_sha`,
`gitcmd.has_no_remote`, `doctor.check_artifact_branch_parent_ancestry`,
`doctor._artifact_branch_first_commit_parent`) присутствуют без
изменений (`grep -n` подтверждает наличие всех сигнатур на прежних
местах).

## Фаза A: проверка плана

PLAN.md не менялся с iteration 3 (сверено — тот же текст, та же
таблица покрытия требований 1↔1,2; 2↔2; 3↔3; 4↔4). Замечаний к плану
нет.

## Соответствие SPEC

Код зоны задачи не менялся с iteration 3 (см. диагностику выше) —
таблица воспроизводит вердикт iteration 3, перепроверенный заново
прогоном, а не списанный без проверки.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `gitcmd.fetch_head_sha` + `_new_branch_parent` (`orchestrator/artifact_branch.py:117-150`) реализуют предпочтение `origin/main`, без изменений с iteration 3. |
| 2 | OK | `commit_files` коммитит любой target в `config.ROOT` безусловно — без изменений. |
| 3 | OK | `doctor.check_artifact_branch_parent_ancestry`/`_artifact_branch_first_commit_parent` (`orchestrator/doctor.py:827-883`) — без изменений, по-прежнему отдельная запись в `all_checks`, не растворилась в `check_artifact_branch_sync` параллельной задачи 01M1TQ0X14, вписанной той же подтяжкой main. |
| 4 | OK | 4а/4в/4г/AC-2(переинтерпретация ANSWER-2)/AC-7(ANSWER-2 п.2) — без изменений; акцептанс-планка (7 файлов) не редактировалась с iteration 3 (тот же список файлов, тот же прогон 7/7). |

## Замечания

Нет новых замечаний. Реестр итерации 2 закрыт полностью на iteration 3
(`accepted`) и не переоткрывается — код, который он покрывал, не
менялся.

## Реестр замечаний

Все записи из прошлых итераций (R2-F1, R2-F2, R2-F3) уже в статусе
`accepted` на iteration 3 — восстановимы из git-истории файла, не
повторяю по правилу «уже accepted можно не повторять». Новых записей
этой итерацией не заведено.

Реестр закрыт целиком (пуст незакрытых записей).

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/acceptance_tests/ -q` — 7 passed.
- `python3 -m pytest tests/test_artifact_branch_new_parent.py tests/test_branch_freshness_gate.py tests/test_doctor_fix_ignored_artifacts.py tests/test_gitcmd_branch_reads.py tests/test_gitcmd_carpentry.py tests/test_gitcmd_check_ignore.py tests/test_git_fixation.py tests/test_catalog_new_race.py tests/test_catalog_status_log.py tests/test_artifact_materialization.py tests/test_multitarget.py tests/test_multitarget_invariants.py tests/test_doctor.py -q` — 292 passed, 17 subtests passed (135.11s).
- `python3 scripts/guard.py tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/SPEC.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/PLAN.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/REVIEW.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/ANSWER-1.md tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/ANSWER-2.md` — «GUARD: ок (5 файлов)».
- `python3 scripts/codebase_map.py` (регенерация на месте) + `git diff --stat -- docs/codebase-map.md` — только строка `built_at_sha` расходится с закоммиченной картой (метка коммита регенерации, не признак дефекта — review-checklist); содержимое совпадает. `git checkout -- docs/codebase-map.md` вернул рабочее дерево в чистое состояние.
- `git diff fbc398e0 HEAD -- orchestrator/artifact_branch.py orchestrator/catalog.py orchestrator/doctor.py orchestrator/gitcmd.py` — правки принадлежат параллельной задаче 01M1TQ0X14 (push-журналирование); `grep -n` по сигнатурам `_new_branch_parent`/`fetch_head_sha`/`has_no_remote`/`check_artifact_branch_parent_ancestry`/`_artifact_branch_first_commit_parent` подтверждает, что код ЭТОЙ задачи присутствует без изменений.
- `git status --short` — чисто (кроме материализованного untracked `tasks/01M1TQ0ZCYJ6TESZ2KGJ6AWYNH/`).
- Полный набор `tests/` не гонял (решение Оператора 05.09 — гоняет CI на каждый пуш) — прогнаны планка задачи и все модули, реально пересекающиеся с зоной задачи.

## Предложения системе

- Класс «отказ advance просит новый прогон ревьювера при iteration уже
  approved» — здесь причина оказалась безобидной (подтяжка main поверх
  уже одобренного HEAD чужой параллельной задачей, код зоны не
  тронут), но диагностировать это пришлось вручную (`git log`, `git
  diff` по сигнатурам). Стоило бы, чтобы отказ advance сам указывал,
  сдвинулся ли HEAD кодовой ветки с sha предыдущего вердикта — тогда
  ревьюверу не нужно каждый раз восстанавливать этот факт заново.
