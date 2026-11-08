# Записка spec_auditor 01M6XHJH6EJ8D0BR5PRNGZAY8C

## Выяснено
- Места SPEC сверены: guard.py:4425/4507/1400/1450/1977, test_lint.py:190, targets.py:60/93/1244, project_profile.py:66, вызывающие tests_writing:518/643, amend:293/317/725, preflight:198/213 — совпадают.
- amend.py:293, :317 зовут long_lived_errors_from_files БЕЗ lint_base — исключение залоченных файлов (треб. 3) там не сработает.
- Песочницы sandbox.py: кроме названных есть ConnRealGitSandbox:2018, SyncedOriginConnSandbox:2027, AutoOriginSandbox:2057, GitignoreCommittedRealGitSandbox:2076, SchemaConnTmpRootTest:1861; вне sandbox.py — ReportSandbox (report_outcome_sandbox.py:335), OutcomeGateSandbox (outcome_gate_sandbox.py:251). Перечень имён в SPEC не замкнут.
- OriginRealGitSandbox — класс sandbox.py, не «локальный подкласс» (AC-2 путает).
- Приложения 1,2 применяются к дереву ветки; 3 — к origin/main (там 7aef13ab1, blob 91d08479f).
- Песочница артели (sandbox.ARTEL_TEST_PROFILE:1123) без size_marks — существующие тесты не краснеют.
- test_lint.py не импортирует guard, guard импортирует test_lint: «переиспользовать разбор pytestmark из guard» в test_lint — цикл импорта (решаемо ленивым импортом).

- Не закрыты: AC-2/AC-4 покрывают часть перечня треб. 2; подключение у amend/preflight (5 из 7 вызывающих) без критерия; обходы usefixtures("real_git"), from subprocess import, псевдоним, команда в локальной переменной.

## Где остановился
SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.

## Не сработало
- grep/sed с `cd …;` в той же команде отклоняются — нужны абсолютные пути без cd и без `$W`.

## Чего не хватило
- Замкнутого перечня подклассов песочниц: искал по всем tests/*.py (grep `^class \w+\(.*Sandbox`).
