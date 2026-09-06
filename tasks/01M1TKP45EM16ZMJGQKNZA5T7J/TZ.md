---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: эталон лёгкой песочницы приёмочных планок в tests/sandbox.py

# ТЗ: эталон лёгкой песочницы приёмочных планок в `tests/sandbox.py`

Источник: копилка 06.09. За один вечер три планки упали не по коду, а
из-за устаревшей копии песочницы, которую тест-автор переписал заново:
«карта и подтяжка» (01M1RA0R9A), «причина конфликта подтяжки»
(01M1REVMB5), «свежесть ветки» (01M1NBWP, красна на main). Три класса
одного дефекта: (а) песочница не кладёт на диск `tasks/<id>/SPEC.md` и
непустой `acceptance_tests/`, а `disk_backed_show`/`disk_backed_ls_tree_
files` читают «ветку» с диска — переход отказывает «планка не найдена в
источнике» / «SPEC.md ветки не прочитан»; (б) ожидание
`acceptance.run(tdir)` без `code_root` — контракт после hotfix регрессии
№14 (ADR-0013); (в) поддельный git не знает новых безобидных вызовов
(`reset -q -- tasks/<id>` из очистки worktree перед merge) и падает
«неожиданный вызов». Пять правок `amend-tests` за вечер.

Требуется:
1. В `tests/sandbox.py` — эталонный класс лёгкой песочницы переходов
   (имя по месту, например `LightTransitionSandbox(TmpRootTest)`):
   подмены `gitcmd.show`/`ls_tree_files` дисковыми, `workspace.ensure`,
   `write_plan_ready`, `write_acceptance_plank` (SPEC.md schema_version 2
   без skip_tests + stub-тест), `advance_from_in_dev`, поддельный git с
   белым списком безобидных no-op вызовов (`checkout`, `commit`, `add`,
   `reset`, `diff --cached`, `status --porcelain`) и явными точками
   расширения для сценариев merge/конфликт/fixation; помощник
   `assert_acceptance_run_called(acc_run, tdir, code_root)`.
2. Существующие модули `tests/test_fsm_map_conflict_autoresolve.py`,
   `tests/test_branch_freshness_gate.py`, `tests/test_fsm_merge_conflict_
   note.py` переводятся на эталон без изменения утверждений (докстринги
   «Ловит мутацию» сохраняются).
3. Скил `test-authoring`: правило «лёгкую песочницу не переписывать —
   импортировать из `tests/sandbox.py`; локальный `_sandbox.py` планки —
   только тонкая надстройка сценария». `scripts/guard.py` — предупреждение
   (не ошибка), если `_sandbox.py` планки определяет собственные
   `disk_backed_*`/`advance_from_in_dev`.
4. Планка 01M1NBWP (`tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests`,
   красна на main) — разобрать причину и, если это класс (а)/(б),
   починить через штатную правку планки (задача done — правка через
   отдельный коммит в main с пометкой в RETRO); зелёный main —
   критерий приёмки.

Зоны: tests/sandbox.py, tests/, скил test-authoring (каталог скилов),
scripts/guard.py, tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/.
Не входит: правка залоченных планок задач в работе (это `amend-tests`
Оператора), изменение поведения переходов.

Рамка: $30.
