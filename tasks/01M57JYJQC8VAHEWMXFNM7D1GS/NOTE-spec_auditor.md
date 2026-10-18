# Записка spec_auditor — 01M57JYJQC8VAHEWMXFNM7D1GS

## Выяснено
- Визит 2 (spec_sha b22a5dae…): все 14 решений гейта SPEC отражены в SPEC; места кода подтверждены (acceptance.py :600/:737/:929/:1083/:1134/:1146/:1166/:1454/:1798/:1951, amend.py :535-565/:684/:723-728, plank_run.py :66-77/:227/:241, checkpoint.py:1796, runner.py:1217, config.py:763, guard.py:3238-3250, targets.yaml:85/:87, тест :345-348/:471/:472/:480).
- `git rev-parse --git-path info/exclude` в worktree → `<клон>/.git/info/exclude` (общий для всех worktree проекта); в worktree `.git` — файл. Треб. 6 SPEC пишет «`.git/info/exclude` рабочей копии».
- Гейт зон видит неотслеживаемые файлы с диска (zones.py:150-158) — AC-9 не пустой; гейт неослабления — по git-диффу (test_integrity._compare) — AC-10 без коммита остатка пустой.
- `_pult.changed_paths()` берёт `ls-files --others --exclude-standard` (plank_helper.py:118-125) — выкладка должна быть исключена ДО записи файлов, иначе планка видит свои файлы как изменения задачи.
- Существующие тесты pytest-own, кроме мандатного файла, путь планки в argv не закрепляют (Explore по 13 файлам); риск — profile_callers.py:269 фильтр `acceptance_tests` для полного набора.

## Не сработало
- python -c / mktemp с подстановкой в Bash песочница не пускает — эмпирику pytest по каталогу с точкой не прогнал.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, 6 отклонений; guard.py — ок.

## Чего не хватило
- Нет готового ответа, общий ли info/exclude у worktree пульта — проверил `git rev-parse --git-path`.
