# Записка spec_auditor (визит 3, SPEC sha 9aae3c0c)

## Выяснено
- sha SPEC = 9aae3c0c (git hash-object) — совпадает с миссией. ANSWER-n нет; решения гейта №1, №2 внесены в SPEC.
- Ссылки SPEC сверены: misc_checks.py:91-94 (gh repo view), artifact_branches.py:126-146/137/171-174, runner.py:1116-1141, sandbox.py:1057-1065, brief.py:593, targets.yaml:28 (artel-token), :73 (sled-github-token), config.py:50 PROJECTS, :799 COMMON_ZONES (config.py — общая зона артели, порог 5.1 вне зон не вылезает).
- Все хостинговые git-вызовы идут через gitcmd.in_repo → git("-C", …); carpentry — только локальные.
- ci.gh с repo= в проде — только github_adapter.py:168,193,306.
- Тесты под окружением роли: conftest пускает адресный pytest под ARTEL_ROLE; suite_run.py:781 снимает только ARTEL_ROLE, HOME дома роли остаётся → in_role_environment True → треб.7 отказал бы хостингу внешних проектов в тестах песочницы; sandbox.py HOME/ARTEL_ROLE не трогает. SPEC молчит.
- targets.yaml sled no_paths несёт маски (`**/conftest.py`) — 5.6 «путь существует» для маски не определён.
- BaseBranchCheckTest (test_doctor.py:629-692) — plain TestCase, имя "sled" — реальная запись с token_slot; условие О-5 «остаётся зелёным без правки» в SPEC не перенесено.
- AC-7/AC-8 5.2 не требуют токена в окружении fetch/push --dry-run doctor (с file:// origin токен не нужен — мутация «doctor мимо механизма» не ловится).

## Не сработало
- `ls` в Bash не найден — find -maxdepth 1.

## Где остановился
- SPEC-AUDIT.md готов: verdict concerns, status ready, guard ок. Отклонения: П-1 (тесты под ролью), А-1/П-2 (О-5 потеряно, источник token_slot), В-1 (doctor fetch/dry-run мимо токена), Ф-1 (маски no_paths), В-2 (AC-2 не называет вызовы gh).

## Чего не хватило
- Нет справки, как песочница тестов нейтрализует признак роли (HOME/ARTEL_ROLE) — искал по tests/sandbox.py, conftest.py.
