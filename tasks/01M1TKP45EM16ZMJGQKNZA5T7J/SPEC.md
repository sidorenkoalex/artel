---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: spec
author_role: analyst
status: ready
schema_version: 4
zones: tests/sandbox.py, tests/test_fsm_map_conflict_autoresolve.py, tests/test_branch_freshness_gate.py, skills/test-authoring.md, scripts/guard.py, tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/
budget_usd: 30
---

# SPEC: эталон лёгкой песочницы приёмочных планок в `tests/sandbox.py`

## Контекст

Копилка 06.09: за один вечер три приёмочные планки упали не по коду, а
из-за устаревшей копии песочницы, которую тест-автор каждый раз
переписывал заново — «карта и подтяжка» (01M1RA0R9A), «причина
конфликта подтяжки» (01M1REVMB5), «свежесть ветки» (01M1NBWP, на main
до сих пор красна). Три класса одного и того же дефекта: (а) песочница
не кладёт на диск `tasks/<id>/SPEC.md` и непустой `acceptance_tests/`,
а `disk_backed_show`/`disk_backed_ls_tree_files` читают «ветку» именно
с диска — переход отказывает «планка не найдена в источнике»/«SPEC.md
ветки не прочитан»; (б) ожидание `acceptance.run(tdir)` без
`code_root` — контракт изменился после hotfix регрессии №14
(ADR-0013); (в) поддельный git не знает новых безобидных вызовов
(`reset -q -- tasks/<id>` из очистки worktree перед merge) и падает
«неожиданный вызов». Пять правок `amend-tests` за вечер — цена
отсутствия общего эталона.

## Требования

1. `tests/sandbox.py` несёт эталонный класс лёгкой песочницы переходов
   (имя по месту разработчика, например `LightTransitionSandbox
   (TmpRootTest)`): подмены `gitcmd.show`/`gitcmd.ls_tree_files`
   дисковыми, `workspace.ensure`, помощники `write_plan_ready`,
   `write_acceptance_plank` (кладёт `SPEC.md` с `schema_version: 2`
   без поля `skip_tests` и минимум один stub-тест), `advance_from_
   in_dev`, поддельный git с белым списком безобидных no-op вызовов
   (`checkout`, `commit`, `add`, `reset`, `diff --cached`, `status
   --porcelain`) и явными точками расширения для сценариев merge/
   конфликт/fixation; помощник `assert_acceptance_run_called(acc_run,
   tdir, code_root)`.
2. `tests/test_fsm_map_conflict_autoresolve.py` и `tests/test_branch_
   freshness_gate.py` переводятся на эталон из требования 1 без
   изменения существующих утверждений (докстринги «Ловит мутацию»
   сохраняются дословно). Для `tests/test_fsm_merge_conflict_note.py`
   требование считается выполненным без правки файла — по ответу
   Оператора (ANSWER-1, вопрос 1) этот путь назван в ТЗ по ошибке: файл
   несёт только чистые unit-тесты `fsm._merge_conflict_note` без единой
   копии песочницы, переводить в нём нечего.
3. Скил `test-authoring` (`skills/test-authoring.md`) фиксирует правило:
   лёгкую песочницу не переписывать заново — импортировать из `tests/
   sandbox.py`; локальный `_sandbox.py` планки — только тонкая
   надстройка сценария. `scripts/guard.py` выдаёт предупреждение (не
   ошибку, не блокирует переход гейта), если `_sandbox.py` планки
   определяет собственные функции `disk_backed_*`/`advance_from_in_dev`
   вместо импорта из эталона.
4. Планка `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/` (красна
   на main) диагностируется; если причина относится к классу (а) или
   (б) из «Контекста», планка чинится штатной правкой (`amend-tests`,
   отдельный коммит в main с пометкой в RETRO задачи
   01M1NBWPKNBXP9ZXXQDJM7AXPJ — она уже `done`). Зелёный main по этой
   планке — часть критерия приёмки.

## Критерии приёмки

AC-1. `tests/sandbox.py` содержит класс лёгкой песочницы переходов,
наследующий `TmpRootTest`, с подменами `gitcmd.show`/`gitcmd.
ls_tree_files` на дисковые реализации и подменой `workspace.ensure`.

AC-2. Тот же класс/модуль несёт помощники `write_plan_ready`,
`write_acceptance_plank` (кладёт `acceptance_tests/` c `SPEC.md`
`schema_version: 2` без поля `skip_tests` и минимум одним stub-тестом)
и `advance_from_in_dev`.

AC-3. Поддельный git эталона принимает без ошибки как минимум вызовы
`checkout`, `commit`, `add`, `reset`, `diff --cached`, `status
--porcelain` и несёт точки расширения (переопределяемые хуки/
параметры, не жёстко зашитый список) для сценариев merge/конфликт/
fixation.

AC-4. Эталон несёт помощник `assert_acceptance_run_called(acc_run,
tdir, code_root)`, проверяющий вызов `acceptance.run` с обоими
аргументами.

AC-5. `tests/test_fsm_map_conflict_autoresolve.py` и `tests/test_
branch_freshness_gate.py` используют эталон из AC-1..AC-4 (импорт из
`tests/sandbox.py`, без собственной копии `write_plan_ready`/
`write_acceptance_plank`/`advance_from_in_dev`), и все существующие
тесты в обоих файлах проходят с сохранёнными докстрингами-
утверждениями «Ловит мутацию».

AC-6. `tests/test_fsm_merge_conflict_note.py` не изменён этой задачей.

AC-7. `skills/test-authoring.md` несёт правило: лёгкую песочницу не
переписывать — импортировать из `tests/sandbox.py`; локальный `_
sandbox.py` планки — только тонкая надстройка сценария.

AC-8. `scripts/guard.py` выдаёт предупреждение (элемент результата
`warnings`, не `errors` — не блокирует переход гейта) для планки, чей
`_sandbox.py` определяет собственные функции `disk_backed_*` или
`advance_from_in_dev` вместо импорта из `tests/sandbox.py`.

AC-9. Планка `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
зелёная на main (все её тесты приёмки проходят); правка внесена
отдельным коммитом в main с пометкой в RETRO задачи
01M1NBWPKNBXP9ZXXQDJM7AXPJ.

## Оценка объёма и деление

Сработавший сигнал: бюджет (`budget_usd: 30` ≥ порог `$30`,
`SPLIT_SIGNAL_BUDGET_USD` в `orchestrator/config.py`). Число файлов
зоны (6) и число критериев (9) ниже соответствующих порогов (5 по
формуле пути `orchestrator/*.py`/`scripts/*.py` — здесь зоне
соответствует только `scripts/guard.py`; 10 по AC).

Обоснование монолита: четыре требования ТЗ — одна связная правка
тестовой инфраструктуры, не 2-4 независимо мержимых куска.
Требование 2 (перевод существующих тестов) не имеет смысла мержить
раньше требования 1 (эталонного класса) — переводить будет не на что;
требование 3 (правило скила + предупреждение guard) — сам механизм,
который не даёт дефекту снова расползтись копиями, и формулировать его
раньше появления эталона (требование 1) нечем. Требование 4
(диагностика и починка планки 01M1NBWP) диагностически привязано к тем
же трём классам дефекта (а/б/в) из «Контекста», сформулированным именно
в связи с введением эталона: разнести её на отдельный шаг разработчика/
ревью рискует разъехавшимся заключением о причине красноты по
сравнению с тем, что уже установлено при разборе классов (а)/(б) для
требований 1-2. Дробление на подзадачи при текущем объёме (6 файлов
зоны, 9 критериев) добавило бы минимум ещё один полный цикл
SPEC+PLAN+REVIEW сверх и без того двух ожидаемых итераций ревью,
превысив рамку Оператора ($30) сильнее, чем один монолитный проход с
той же рамкой.

## Не входит

- Правка залоченных планок задач «в работе» — это `amend-tests`
  Оператора, не эта задача.
- Планка `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/
  test_pull_conflict_detail.py` не входит в зоны и не трогается этой
  задачей: задача 01M1REVMB50SND1KJ3CYQMV2ST уже `done`, планка зелёная
  после прежней правки `amend-tests`, а расширять периметр ради
  дедупликации в уже сданной планке Оператор счёл ненужным (ANSWER-1,
  вопрос 1). Перевод этой планки на эталон, если понадобится, — предмет
  отдельной документной правки Оператора.
- Изменение поведения переходов FSM.

## Материалы

- Копилка 06.09 (роадмап §4): «лёгкие песочницы планок устаревают
  одинаково (три планки за вечер, эталон в tests/sandbox.py)».
- ADR-0013 — контракт `acceptance.run(tdir, code_root)` после hotfix
  регрессии №14.
- `tasks/01M1TKP45EM16ZMJGQKNZA5T7J/QUESTIONS.md` и `ANSWER-1.md` —
  разбор адреса третьего файла требования 2.
