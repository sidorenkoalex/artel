# Записка spec_auditor — 01M6EXF3TMNRKCZH8CS9BXXG1Z

## Выяснено
- SPEC sha 2ce503df… проверен полной глубиной, вердикт fail (SPEC-AUDIT.md).
- gitcmd: fail-open три места — :774 (in_flight_refusal), :960-961 (_push_plan, max_in_flight), :1244-1245 (in_repo). ТЗ называет :774 и :960; SPEC заменил :960 на :1244 — место :960 потеряно.
- Клоны УЖЕ имеют core.hooksPath = <ROOT>/scripts/git-hooks (workspace.set_clone_hooks :68, doctor/git_hooks.check_clone_hooks :148, warn). Существующий scripts/git-hooks/pre-push пропускает всё при ARTEL_PULT_GIT=1 (:14). git зовёт только файл с именем pre-push — «новый файл хука» сам не сработает.
- gitcmd сейчас НЕ задаёт -c core.hooksPath при отправке (grep пуст) — «по-прежнему» в ТЗ/SPEC неверно.
- Сторож ac9 (tests/test_01m5w27…:474) запрещает сравнения forge/merge_gate с литералами вне targets.py — выбор по forge в doctor/gitcmd упрётся в него.
- check_project_token зовёт `gh auth token` (project_checks.py:211-239) — AC-6 «ни одна строка не вызывает gh» требует правки строки, не названной в требовании 4.
- Подмодули: в workspace.py нет ничего, «клон подмодулей тем же слотом» в части 3 без зоны workspace.py.

## Не сработало
- `cd … ; sed` и составные команды с `ls`/`head` — отказ песочницы; работают одиночные grep/Read абсолютными путями.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: fail, 12 пунктов), guard — ок. Шаг завершён.

## Чего не хватило
- ANSWER-1 п. 4: «сумма до .» — число рамки пропущено в ответе Оператора.
