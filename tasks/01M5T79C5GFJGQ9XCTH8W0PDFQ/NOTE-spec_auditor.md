# Записка spec_auditor — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- Второй аудит, SPEC sha 22d03b26…: SPEC-AUDIT.md сдан, status ready, verdict concerns.
- Все шесть пунктов решения Оператора на гейте 26.10 в SPEC отражены.
- Осталось три мелочи:
  - AC-4 у места 1 не требует `kill` процесса по сроку (`acceptance.py:2951-2952`);
  - AC-7 не называет `cwd=config.ROOT` места 1 (`:2945`);
  - подмена всего модуля `mock.patch.object(acceptance, "subprocess", fake)` (10 мест) не названа в требовании 4. По коду она безвредна: до `suite_tree_hash` доходят только `PytestSpy` (`profile_callers.py:727`, `test_report_outcome_module.py:1336/1344`), а они передают git в настоящий `Popen`.
- `explicit_repo.py:63` требует, чтобы первый параметр новой публичной функции `gitcmd` назывался `repo`/`path`/`root`/`cwd`/`repo_path`; иначе `:208` краснеет.

## Не сработало
- `cd … && grep` с относительными путями, а также `awk`/`sed` в конвейере отклоняются правами. Пиши абсолютные пути, команды по одной.

## Где остановился
- Аудит закончен.

## Чего не хватило
- Перечня тестов, которые подменяют атрибут `subprocess` модулей целиком: искал grep по `(acceptance|brief|…)\.subprocess`.
