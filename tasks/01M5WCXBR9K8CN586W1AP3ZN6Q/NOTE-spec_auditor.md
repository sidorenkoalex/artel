# Записка spec_auditor — 01M5WCXBR9K8CN586W1AP3ZN6Q

## Выяснено
- Факты SPEC о коде сходятся: misc_checks.py:90/98-100, forge.py:169/193, gitlab_adapter.py:40-41/90/552-622, sandbox.py:663-680.
- Сторож А0 `test_ac9_no_support_literals_outside_targets` ИСКЛЮЧАЕТ `doctor/misc_checks.py::check_base_branch` (tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:418) — литерал в нём сторож не ловит.
- Тесты части 1 `test_ac14_*`, `test_ac15_*`, `test_ac16_red_*` (tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:1229,1266,1293,1347) запрашивают `lab` (подмена transport) ДО `gl_clone`→`real_git` (песочница): наивный mock.patch transport в isolate_keychain_and_role перекроет подмену теста.
- `BaseBranchCheckTest` не подменяет config.TARGETS; forge читает запись по имени через targets.target, не переданный entry.

## Не сработало
- Цепочки `cd ... && ...`/переменные в Bash требуют подтверждения — писать абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан (status ready, verdict concerns, 5 отклонений); guard: ок.

## Чего не хватило
- Как гейт неослабления трактует смену тела помощника tests/sandbox.py (guard.weakened_helpers / _changed_fixture_names) — не доразобрал.
