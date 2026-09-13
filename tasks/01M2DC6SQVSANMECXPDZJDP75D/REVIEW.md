---
task: 01M2DC6SQVSANMECXPDZJDP75D
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Рефакторинг R8: общая песочница тестов — базовые классы вместо копий setUp и подмножеств PATCHED_ATTRS

## Фаза A: гейт плана

1. Покрытие требований SPEC в PLAN.md — таблица «Покрытие требований» полна: все 6 требований адресованы шагами 1–4 или самим документом (5) — проверено построчным сопоставлением с SPEC «Требования».
2. Шаги — проверяемые единицы (добавление классов в sandbox.py → перевод 46 файлов → разбор PATCHED_ATTRS → восстановление литерала-исключения → уборка рабочего мусора) — не микрооперации, не «сделать всё одним пунктом».
3. Подход не конфликтует с конвенциями: чистый перенос без изменения поведения (класс «рефакторинг», skills/coding-standards.md), кооперативная примесь `_ConnSetupMixin` для кросс-иерархийного дубля — обоснованное архитектурное решение, не спекулятивная абстракция (нужна ровно двум узлам с разными предками).

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (перенос дублей setUp/помощников в базовые классы sandbox.py) | OK | 16 новых базовых классов/примесей в tests/sandbox.py (включая `_ConnSetupMixin`); AC-1 (сканер по AST, побайтовое сравнение исходников, включая сам sandbox.py в общий пул) зелёный — прогнал сам, подтверждаю. Несколько узлов (`_HeadShaPatchedTest` в test_ci_status.py, `_SpecV2TmpDirTest`/`_CanaryBaselineTmpDirTest`/`_TwoTasksInitializedTest`/`_MutationClaimGateRowTest`) вынесены в локальный базовый класс файла, а не в sandbox.py — обоснованно (зависят от файл-локальных констант: `SHA`, `SPEC_V2`, `_task_row`) и не противоречит измеримому AC-1 (тот требует отсутствия дублей, а не обязательной прописки именно в sandbox.py).
| 2 (PATCHED_ATTRS: обоснование или расширение) | OK | 9 файлов расширены до `ALL_CONFIG_ATTRS` (override убран), `test_doctor.py::_RoleHomeReferenceTmpRootTest` оставлен подмножеством с содержательным обоснованием (реально читает настоящий `config.ROOT`), `test_git_fixation.py::_GitFixationTmpRootTest` — литерал восстановлен с обоснованием (защищённый `test_invariants.py` ссылается на AST-узел `PATCHED_ATTRS = (...)` этого класса по имени — проверил напрямую, ссылка подтверждена). AC-2 зелёный.
| 3 (ассерты/сценарии не меняются, tests/ зелёный) | OK | AC-3 (regex по дифу, ищет строки `assert`) зелёный — сам прогнал. Полный прогон всех 48 изменённых файлов + tests/test_invariants.py: 1185 passed, 359 subtests passed, 0 упавших (см. «Проверено исполнением»).
| 4 (AC-4: сохранение критерия «нет утечки worktrees») | OK | Не тронуто — `tests/test_invariants.py` не редактируется (AC-6), сам инвариант `SandboxPatchedAttrsCoverWorktreesInvariantTest` зелёный в моём прогоне.
| 5 (таблица переносов + откат в PLAN.md) | OK | PLAN.md несёт полную таблицу «Откуда → Куда» (16 строк) и явное описание отката («revert одного merge-коммита ветки задачи в main»); AC-5 зелёный.
| 6 (test_invariants.py не редактируется) | OK | Диф ветки не содержит `tests/test_invariants.py` (нет в git diff --stat, AC-6 зелёный).

## Замечания

Замечаний нет.

## Реестр замечаний

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M2DC6SQVSANMECXPDZJDP75D/acceptance_tests/ -v` — 10/10 зелёных (AC-1, AC-2, AC-3, AC-5, AC-6; AC-4 — `manual`, обоснованно, см. её файл и прецедент 01M2CN465WEDCF6D77V37FJ82E).
- `python3 -m pytest <48 изменённых файлов tests/*.py> tests/test_invariants.py -q` (полный список — все файлы из `git diff --stat 0b9b7b57...HEAD -- tests/`, кроме самого `sandbox.py`, плюс защищённый `test_invariants.py`) — `1185 passed, 359 subtests passed` за 301с, 0 упавших.
- `python3 scripts/codebase_map.py --check` (регенерация и сравнение с закоммиченной картой без строки `built_at_sha`) — расхождение только в `built_at_sha` (легитимно, skills/review-checklist.md), содержимое совпадает; откатил случайную правку `git checkout -- docs/codebase-map.md` после проверки.
- Точечно прогнал `python3 -c` с MRO (`SchemaConnTmpRootTest`, `ConnRealGitSandbox`, `PushSuccessTest`, `ArtifactBranchSyncSandbox`) — кооперативный `super()` в `_ConnSetupMixin`/`AutoOriginSandbox` разрешается через правильного родителя каждого потомка.
- Сверил числа в докстрингах sandbox.py («13 классов», «5 классов», «4 класса» и т.д.) прямым grep по использованию каждого нового базового класса в tests/*.py — совпадают с фактическим количеством классов-потребителей.
- Проверил напрямую (`grep`), что `tests/test_invariants.py::SandboxPatchedAttrsCoverWorktreesInvariantTest` действительно ищет AST-узел `PATCHED_ATTRS = (...)` внутри класса по имени `_GitFixationTmpRootTest` — обоснование восстановления литерала в PLAN.md подтверждено чтением защищённого файла (не редактировал).
- Не запускал: полный набор `tests/` целиком (решение Оператора 05.09, гоняет CI — коммит 0a252ca2 зелёный, 7 проверок).

## Предложения системе

- PLAN.md сам предлагает перенести сканер AC-1 (`_collect_setup_bodies`/`_collect_module_helper_bodies`) в постоянный `tests/test_invariants.py`, иначе следующий рефакторинг песочницы рискует тем же классом регрессии (кросс-иерархийный дубль внутри `sandbox.py`), что нашёлся здесь только благодаря планке самой задачи — присоединяюсь к этому наблюдению, стоит учесть при планировании следующего Р-шага ревизии.
