---
task: 01M1NBWTSXEJB24PXR417YF1VA
type: plan
author_role: developer
status: draft
schema_version: 3
---

# PLAN: WIP-чекпоинт после таймаута: зона роли и артефактная ветка

## Подход

`checkpoint.commit_timeout_checkpoint` разветвлён по мандату роли,
названному ANSWER-1: `developer` — единственная роль, чей WIP попадает в
кодовую ветку, и только по путям вне `tasks/<id>/`; `analyst`/
`test_author`/`reviewer` не коммитят в кодовую ветку ничего, их WIP вне
`tasks/<id>/` откатывается. `tasks/<id>/` при этом переносится в
артефактную ветку тем же механизмом, что и штатный автокоммит
(`_commit_external_step_artifacts`), для ЛЮБОЙ роли — независимо от
мандата кода.

Ключевые решения:

1. **Исключение `tasks/<id>/` из код-коммита developer** — не через
   pathspec-магию `git add`, а простой связкой `git add -A` +
   `git reset -- tasks/<id>` перед проверкой `git diff --cached --quiet`:
   тот же набор шагов, что уже был (`_commit_worktree_change`), плюс один
   `reset`. Параметр `exclude` — опциональный, остальные вызывающие
   (`commit_abnormal_checkpoint`, `commit_pause_now_checkpoint` — вне
   зоны этой задачи, SPEC не называет их) его не передают и работают
   байт-в-байт как раньше.

2. **Откат вне мандата для non-developer** — новая функция
   `_discard_out_of_mandate_changes`: `git status --porcelain=v1
   --untracked-files=all`, фильтр путей вне `tasks/<id>/`, для каждого —
   число строк (`git diff HEAD --numstat` для трекенных, длина файла для
   новых) и откат (`git checkout --` для трекенных — буквально то, что
   называет AC-2; `Path.unlink()` для новых — `checkout --` не властен
   над путём без истории в git). Возврат `commit_timeout_checkpoint`
   остаётся пустым для этой ветки (AC-2: «нечего коммитить в кодовую
   ветку»), но журнал получает отдельную запись с путями и числом строк
   (AC-3).

3. **Перенос `tasks/<id>/` — для любой роли, безусловно**: чекпоинт
   всегда зовёт `_commit_external_step_artifacts(..., timeout=True)`
   после ветки по мандату кода. Новый параметр `timeout` добавляет
   пометку «WIP после таймаута» к сообщению коммита артефактной ветки
   (AC-5) — при этом «свой ли это автокоммит той же роли» для логики
   удаления файлов (`_DELETABLE_ARTIFACT_TYPES`) сверяется ПРЕФИКСОМ
   сообщения (`own_commit_marker`), не точным текстом: иначе чередование
   обычного шага и обрыва по таймауту одной роли ломало бы удаление уже
   на второй итерации (закрыто отдельным тестом,
   `test_timeout_marker_carried_and_deletion_still_matches_across_flavors`).

4. **Возвращаемое значение `commit_timeout_checkpoint` — только про
   кодовую ветку**, как и раньше: перенос `tasks/<id>/` — побочный
   эффект, не отражённый в `detail`. Это сохраняет обратную совместимость
   с существующими юнит-тестами git-failure-веток (`_commit_worktree_
   change`), которые мокают `gitcmd.git` по конкретной подкоманде: сам
   перенос идёт через `artifact_branch.write_commit` (голый
   `subprocess`, не `gitcmd.git`), поэтому не задет этими моками — как и
   не должен быть, это раздельные операции по SPEC.

Архитектурно не значимо — расширение существующего чекпоинта разбором
роли, без новых сущностей/ADR.

## Шаги

1. `orchestrator/checkpoint.py`: мандат роли в `commit_timeout_checkpoint`
   (`_discard_out_of_mandate_changes`, параметр `exclude` у
   `_commit_worktree_change`, параметр `timeout` у
   `_commit_external_step_artifacts`) + обновление/добавление юнит-тестов
   `tests/test_timeout_checkpoint.py`,
   `tests/test_checkpoint_external_step_artifacts.py`. Один MR — вся
   задача уместилась в один файл кода.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (мандат роли в код-коммите, откат вне мандата) | 1 |
| 2 (перенос tasks/<id>/ в артефактную ветку для любой роли) | 1 |
| 3 (сообщение/журнал называют роль и причину «таймаут») | 1 |
| 4 (минимум тестов, существующие тесты зелёные) | 1 |

## Влияние на систему

Затронута только `orchestrator/checkpoint.py` (и её юнит-тесты) —
единственная функция изменения поведения: `commit_timeout_checkpoint`.
`commit_abnormal_checkpoint`/`commit_pause_now_checkpoint` НЕ тронуты
(SPEC их не называет, «Не входит» подтверждает границу зоны через
`STATE_ROLE`/таймаут-поведение — эти две функции таймаута не касаются,
но по духу той же границы «не входит» я их не расширял мандатом без
явного требования). `commit_step_artifacts` (штатный путь) поведенчески
не меняется: новый параметр `timeout` дефолтится в `False`, сообщение и
логика удаления byte-в-byte как раньше для этого пути — подтверждено
существующими `tests/test_checkpoint_external_step_artifacts.py` (10
тестов, все зелёные без изменений) и новым тестом на пересечение двух
формулировок сообщения.

Ни один существующий тест/гейт/лимит/инвариант не ослаблен. Три теста
`tests/test_timeout_checkpoint.py::CommitTimeoutCheckpointTest`
(`test_dirty_tree_commits_with_message_sha_and_journal_entry`,
`test_git_diff_failure_commits_nothing_and_journals_nothing`,
`test_git_commit_failure_commits_nothing_and_journals_nothing`)
обновлены: их прежний сценарий («developer, изменён только
`tasks/<id>/`») под новым, корректным мандатом больше не производит
код-коммит вообще (это и есть баг, который чинит эта задача) — тесты
дополнены реальной правкой ВНЕ `tasks/<id>/`, чтобы продолжать
проверять именно то, что называют их докстринги (git-failure ветки
`add`/`diff`/`commit`), без ослабления ни одной проверки. Полный набор
`tests/` — 1355 тестов (было 1352 до задачи, AC-9/акс. тест AC-8
докстринг), из них новых — 3
(`test_developer_mandate_excludes_task_dir_from_code_commit`,
`test_non_developer_role_discards_change_outside_task_dir`,
`test_timeout_marker_carried_and_deletion_still_matches_across_flavors`).

Откат — `git revert` коммита(ов) этой ветки; чекпоинт возвращается к
безусловному `git add -A` всего дерева.

## Риски

- Откат вне мандата (`_discard_out_of_mandate_changes`) не обрабатывает
  переименования отдельной веткой (только путь назначения из `R old ->
  new`) — не покрыто тестами, маловероятный сценарий для WIP таймаута.
  Если проявится на практике — отдельный узкий фикс, не блокер этой
  задачи.

## Предложения системе

- `orchestrator/checkpoint.py::commit_timeout_checkpoint` docstring
  ссылается на «Только догфуд... `check_integrity` смотрит в
  `.artel/projects/<target>/`» и одновременно на «повторная фиксация
  (`record_fixation`) не даёт `check_integrity` увидеть сдвиг HEAD
  ветки задачи как расхождение» — эти два утверждения формально не
  согласуются (фиксация читает СОВСЕМ ДРУГОЙ репозиторий,
  `config.PROJECTS/artel/`, не worktree кодовой ветки, чей HEAD
  реально двигает чекпоинт): расхождение существовало до этой задачи,
  не тронуто ей, но заметно затрудняет понимание границы «что чекпоинт
  реально чинит» — кандидат на отдельную ревизию докстринга.
