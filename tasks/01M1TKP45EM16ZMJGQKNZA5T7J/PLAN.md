---
task: 01M1TKP45EM16ZMJGQKNZA5T7J
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: эталон лёгкой песочницы приёмочных планок в tests/sandbox.py

## Подход

Один эталонный класс `LightTransitionSandbox(TmpRootTest)` в
`tests/sandbox.py`, несущий ровно тот набор патчей/помощников, который
сегодня трижды продублирован в `tests/test_fsm_map_conflict_
autoresolve.py`/`tests/test_branch_freshness_gate.py` (и в `_sandbox.py`
приёмочных планок): `gitcmd.git` -> `fake_git` (идентичность без
реального git), `gitcmd.show`/`gitcmd.ls_tree_files` -> `disk_backed_
show`/`disk_backed_ls_tree_files` (артефакты с диска — `artifact_
source.resolve` теперь всегда `foreign=True`), `workspace.ensure` ->
временный подкаталог, `fsm._origin_main_sha` -> константный sha (не
вырожденный дефолт, требование 9), `gitcmd.in_repo` -> хуки `self.
in_repo_handlers` + дефолт-делегат в уже подменённый `gitcmd.git`
(белый список из требования 1 — `checkout`/`commit`/`add`/`reset`/
`diff --cached`/`status --porcelain` — уже покрыт этим делегатом
безусловно, не отдельным hardcoded списком: подмена ЛЮБОГО безобидного
вызова, не только шести перечисленных, устраняет самый класс дефекта
из «Контекста» — «поддельный git не знает новых безобидных вызовов»).
Плюс: `write_plan_ready`/`write_acceptance_plank`/`advance_from_in_dev`,
`assert_acceptance_run_called`.

`gitcmd.subprocess.run` НЕ патчится заново эталоном: унаследованный
`TmpRootTest.setUp` уже ставит `SpyRun(passthrough_unknown=True)`, и
поскольку `gitcmd.git` в этой песочнице подменён целиком (`fake_git`),
единственные вызовы, реально доходящие до `subprocess.run`, —
плотницкие (`hash-object`/`write-tree`/`commit-tree`/...) от `catalog.
cmd_new`, которые `SpyRun` уже обрабатывает независимо от флага
`passthrough_unknown` — второй `SpyRun()` (как было в обоих исходных
файлах) поведенчески эквивалентен, не нужен.

Оба целевых файла (`tests/test_fsm_map_conflict_autoresolve.py`,
`tests/test_branch_freshness_gate.py`) переводятся на наследование
этого класса: локальные копии `write_plan_ready`/`write_acceptance_
plank`/`advance_from_in_dev`/`task_row`/`state`/`set_state`/весь
одинаковый `setUp` удаляются, докстринги «Ловит мутацию» не тронуты
ни на символ (сверено побайтно хешем в приёмочном тесте AC-5).
`TargetSourcedRemoteTest` (второй класс `test_branch_freshness_gate.py`)
не переводится — он не входит в AC-5 (проверяет источник target'а
через реальный `catalog.cmd_new(..., target=...)`, не паттерн лёгкой
песочницы переходов, и своего локального копии из требования 2 не
несёт). `tests/test_fsm_merge_conflict_note.py` не тронут (ANSWER-1).

`scripts/guard.py::sandbox_reuse_check(tdir)` — предупреждение (не
ошибку) для планки, чей `_sandbox.py` определяет `disk_backed_*`/
`advance_from_in_dev` заново вместо импорта; вызывается из `main()` в
режиме `--all` по всем каталогам задач, печатается отдельным блоком
«предупреждения», не входит в код возврата/список ошибок.

Планка `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
диагностирована: 6 из 9 тестов красны классом дефекта (б) — `_sandbox.
py::OriginDivergedSandbox` заводит задачу голым `catalog.cmd_new` без
материализованной приёмочной планки; черновой SPEC.md по умолчанию
(`templates/SPEC.md`, `schema_version: 4`, без `skip_tests`) требует
AC-разметку (`guard.requires_ac_markup`), а `acceptance_tests/` пуст —
`_pull_main_or_escalate` отказывает «планка не найдена в источнике» ДО
предмета проверки самих тестов. Контракт изменился ПОСЛЕ того, как эта
планка была написана (SPEC 01M1R9YEK08XEQWBFX0929WFVJ добавила
материализацию/сверку планки в узел подтяжки уже после того, как
01M1NBWP была `done`). Правка: `OriginDivergedSandbox.setUp` коммитит
непустую `acceptance_tests/` со SPEC.md `schema_version: 2` без
`skip_tests` в артефактную ветку задачи плотницки (`artifact_branch.
commit_files`, тот же приём, что уже несёт `write_plan_ready` этого же
класса) ДО прогона сценариев — ни один существующий assert не тронут,
только исправлена подготовка песочницы под уже сдвинувшийся контракт.
Правка внесена своим отдельным коммитом (см. «Шаги», шаг 3), с пометкой
в `docs/retro/01M1NBWPKNBXP9ZXXQDJM7AXPJ.md`, называющей эту задачу
источником.

`skills/test-authoring.md` — изначально трактовался как защищённый путь
(`skills/`, правит только Оператор отдельным MR по conventions-core.md);
требуемое правило было подготовлено unified-диффом
(`tasks/01M1TKP45EM16ZMJGQKNZA5T7J/skill-test-authoring-sandbox-rule.diff`)
без прямой правки файла, из-за чего AC-7 оставался красным. Ответ
Оператора (ANSWER-3) уточнил: `skills/test-authoring.md` явно назван в
поле `zones:` SPEC этой задачи — файл в зоне задачи, а не вне её, и
Оператор прямо распорядился внести правило в скил в рамках этого шага
разработчика. Приложенный диф применён напрямую (см. «Возврат — AC-7
не реализован (закрыт)»): правило внесено, диф-файл при этом оставлен
рядом с PLAN.md как исторический артефакт подготовки.

## Шаги

1. `tests/sandbox.py`: добавить `LightTransitionSandbox`,
   `assert_acceptance_run_called`, шаблоны `_PLAN_READY_TEMPLATE`/
   `_ACCEPTANCE_PLANK_SPEC_TEMPLATE`/`_ACCEPTANCE_PLANK_STUB_TEST`;
   импортировать `catalog`, `fsm`, `workspace` из `orchestrator`.
2. `tests/test_fsm_map_conflict_autoresolve.py` и `tests/test_branch_
   freshness_gate.py`: перевести на `LightTransitionSandbox`, удалить
   локальные копии, докстринги «Ловит мутацию» не трогать.
3. `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/_sandbox.py`:
   добавить `OriginDivergedSandbox.write_acceptance_plank`, звать из
   `setUp`; `docs/retro/01M1NBWPKNBXP9ZXXQDJM7AXPJ.md`: секция «Правка
   планки (amend-tests)» с ссылкой на эту задачу.
4. `scripts/guard.py`: `sandbox_reuse_check`, вызов из `main()` в
   режиме `--all` (предупреждения отдельным блоком, не влияют на код
   возврата).
5. Unified-диф `skills/test-authoring.md` — подготовлен файлом рядом с
   этим PLAN.md, НЕ применён к дереву (защищённый путь, только
   Оператор).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (эталонный класс `tests/sandbox.py`) | 1 |
| 2 (перевод существующих тестов) | 2 |
| 3 (правило скила + предупреждение guard) | 4, 5 |
| 4 (диагностика и починка планки 01M1NBWP) | 3 |

## Влияние на систему

- Новый класс в `tests/sandbox.py` — аддитивная правка, ничего не
  удаляет и не переопределяет из уже существующих `TmpRootTest`/
  `RealGitSandbox`/помощников: остальные ~65 файлов, импортирующих
  `tests.sandbox`, не затронуты (проверено прогоном образца из шести
  файлов + полным набором двух переведённых файлов).
- `_in_repo_side_effect` эталона делегирует НЕОПОЗНАННЫЕ вызовы
  `gitcmd.in_repo` в уже подменённый `gitcmd.git` (`fake_git`), а не
  бросает исключение на неизвестной подкоманде: это НАМЕРЕННО шире
  буквального «белого списка шести» из AC-3 — сам класс дефекта из
  «Контекста» SPEC («поддельный git не знает новых безобидных вызовов
  … падает „неожиданный вызов“») в точности про хрупкость
  hardcoded-перечня; заменять его новым hardcoded-перечнем внутри
  эталона значило бы воспроизвести тот же дефект на шаг позже. Прежнее
  поведение (тест без явного `mock.patch.object(gitcmd, "in_repo",
  ...)`) уже опиралось на такую же неявную деградацию через
  `gitcmd.git`/`fake_git` — эталон её не меняет, только оформляет
  точкой расширения `in_repo_handlers` вместо копипасты if/elif в
  каждом сценарии.
- `scripts/guard.py::sandbox_reuse_check` — новая проверка, warnings
  не входят в код возврата `main()` ни в одном из двух режимов (обычном
  и `--artifact-branch`): существующие гейты, читающие код
  возврата/список ошибок guard'а, поведения не меняют. Прогон `python3
  scripts/guard.py --all` на реальном дереве подтвердил: 2 предупреждения
  (`tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/acceptance_tests/_sandbox.py`,
  `tasks/T067/acceptance_tests/_sandbox.py` — обе планки старше эталона,
  несут собственные копии `disk_backed_*`, что и ожидается требованием
  3), код возврата не изменился (прежние, не связанные с этой задачей,
  нарушения `tasks/01M1REVMB50SND1KJ3CYQMV2ST/_*_map*.md` остаются как
  были).
- `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/_sandbox.py` —
  правка `setUp` (добавление `write_acceptance_plank`), ни один
  существующий `assert` не ослаблен и не удалён; полный набор планки
  (9/9) и оба целевых теста (`test_ac9_plank_acceptance_tests_all_pass`,
  `test_ac9_retro_carries_note_about_this_fix`) зелёные.
- `skills/test-authoring.md` изменён этой задачей: `zones:` SPEC
  явно называет этот файл, и ANSWER-3 Оператора прямо распорядился
  внести правило в рамках шага разработчика (см. «Возврат — AC-7 не
  реализован (закрыт)») — приложенный unified-диф применён напрямую,
  критерий AC-7 зелёный.
- Откат: `git revert` коммитов этой ветки; правка планки 01M1NBWP и
  правка скила — отдельные коммиты, каждый откатывается независимо.

## Риски

(риск AC-7 снят — см. «Возврат — AC-7 не реализован (закрыт)»)

## Предложения системе

- Скил `conventions-core.md` описывает протокол «unified-диф вместо
  правки защищённого пути» текстом, но не даёт роли developer
  механизма пометить ОДИН конкретный AC как «красный по протоколу, не
  по дефекту» — гейт приёмки (насколько видно из этой задачи) не
  различает эти два случая. Класс: «протокол для защищённых путей не
  стыкуется с автогейтом acceptance» — возможно, годится точка
  расширения по образцу `# AC-n: manual/skip` test_author, но для
  случая «зона SPEC легитимно требует защищённый путь».
- ADR-0015 («приёмка в `in_dev` до `verifying`, не после в `review`»)
  докатилась в main уже ПОСЛЕ того, как локальный SPEC/PLAN
  диагностировали планку 01M1NBWP по классам (а)/(б)/(в) из
  «Контекста»; подтяжка main вскрыла ЧЕТВЁРТЫЙ красный тест той же
  планки (`test_ac3_entry_points_ignore_local_pin.py`, assert
  `in_dev -> review`), не входивший ни в один из трёх названных
  классов на момент SPEC. Диагностика «класс дефекта» в SPEC —
  снимок на момент анализа, не инвариант: планка, зависящая от
  промежуточного состояния FSM, может устареть повторно между
  диагностикой и мержем, если в main тем временем катится
  поведенческий ADR. Отдельного механизма системы для этого не нужно —
  фиксирую как наблюдение для будущих диагностик такого рода.

## Возврат — конфликт подтяжки main (закрыт)

Ответ Оператора: `tasks/01M1TKP45EM16ZMJGQKNZA5T7J/ANSWER-2.md`.
`git merge main` выполнен в этом worktree; конфликты разрешены по
инструкции ANSWER-2:

- `scripts/guard.py` — обе стороны объединены: список ошибок
  `extraneous`/`task_root_extraneous` из main (01M1TNN4TMWAQSQ9Y1PW37J5H0)
  сохранён, сбор `sandbox_reuse_warnings` по каталогам задач (эта
  задача) добавлен следом, оба списка идут в `main()` независимо
  (ошибки — в код возврата, предупреждения — нет).
- `tests/test_fsm_map_conflict_autoresolve.py` — импорт эталона
  `LightTransitionSandbox` (эта задача) сохранён, добавлен `agent_log`
  (используется в теле теста веткой main под ADR-0015); неиспользуемые
  после перевода на эталон импорты main (`catalog`, `config`,
  `workspace`, `SpyRun`, `capture*`, `disk_backed_*`, `fake_git`,
  `PLAN_READY`, `REPO_ROOT`) убраны — тела тестов автомерж main уже
  подтянул целиком (эта задача их не трогала).
- `docs/codebase-map.md` — взят из main, перегенерирован `python3
  scripts/codebase_map.py`.

Дополнительно обнаружено при проверке планки 01M1NBWP после подтяжки
(см. «Предложения системе»): ADR-0015 сделала красным ещё один тест
той же планки — исправлен отдельным коммитом `amend-tests` с пометкой
в RETRO (см. «Влияние на систему»).

Прогнано после слияния (передний план, с таймаутом): планка задачи
(`tasks/01M1TKP45EM16ZMJGQKNZA5T7J/acceptance_tests/`, 17/17),
`tests/test_fsm_map_conflict_autoresolve.py` +
`tests/test_branch_freshness_gate.py` (17/17), `tests/test_guard_*.py`
(137/137), планка 01M1TNN4TMWAQSQ9Y1PW37J5H0 (16/16), планка 01M1NBWP
(9/9), `python3 scripts/guard.py --all` (0/644, 2 ожидаемых
предупреждения). Полный `tests/` не запускался (решение Оператора
05.09).

## Возврат — AC-7 не реализован (закрыт)

Ответ Оператора: `tasks/01M1TKP45EM16ZMJGQKNZA5T7J/ANSWER-3.md`. Причина
возврата: планка на коде ветки 322afccc — 17/18, красен
`test_ac7_skill_names_sandbox_module_and_thin_overlay_rule` — требование
3 SPEC (правило скила) не было реализовано, только подготовлено
unified-диффом рядом с PLAN.md (прежняя трактовка `skills/` как
безусловно защищённого пути). ANSWER-3 указал: `skills/test-authoring.md`
явно назван в поле `zones:` SPEC этой задачи — файл в зоне задачи, а не
вне её; Оператор прямо распорядился внести правило текстом, содержащим
проверяемые тестом подстроки (`tests/sandbox.py`, `_sandbox.py`, «не
переписывать», «надстройк»).

Правка: содержимое приложенного диффа
(`tasks/01M1TKP45EM16ZMJGQKNZA5T7J/skill-test-authoring-sandbox-rule.diff`)
внесено в `skills/test-authoring.md` напрямую (новая секция «Лёгкая
песочница переходов — не копия, импорт» после раздела «Лок», перед
«Запрещено») — без отклонения от согласованной ранее формулировки.

Прогнано после правки (передний план, с таймаутом):
`test_skill_test_authoring_sandbox_rule.py` отдельно (1/1), полная
планка задачи `tasks/01M1TKP45EM16ZMJGQKNZA5T7J/acceptance_tests/`
(18/18), `tests/test_fsm_map_conflict_autoresolve.py` +
`tests/test_branch_freshness_gate.py` (17/17), `python3 scripts/guard.py
--all` (0 ошибок/645 файлов, те же 2 ожидаемых предупреждения, что и
раньше). Полный `tests/` не запускался (решение Оператора 05.09).
Единственная правка кода этого шага — `skills/test-authoring.md`;
диф-файл рядом с PLAN.md оставлен как исторический артефакт подготовки
патча, самим SPEC не запрещён.
