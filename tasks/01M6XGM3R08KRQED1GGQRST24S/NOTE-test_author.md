# Записка test_author

## Выяснено
- AC-2…AC-5 — долгоживущий `tests/test_01m6xgm3r08krqed1ggqrst24s_criterion_form.py` (pytest, случайные SPEC в памяти, зерно печатается); зелёный с рождения: guard задача не меняет. AC-5 зовёт функцию теста AC-2 под `monkeypatch.setattr(guard, "PLAIN_NUMBERED_ITEM", …)` и ждёт AssertionError.
- AC-1 — разовый `acceptance_tests/test_ac1_appendices.py` по образцу планки 01M5NHXJA3X7 (refs/artifacts/…:test_task_facts.py): временный индекс от HEAD, приложения PLAN (`guard.plan_appendices`) против блоков ```diff TZ.md, сравнение sha блобов пяти файлов. Красен до PLAN.md.
- Приложения PLAN в ветку не коммитятся — пульт накладывает их на временное дерево (orchestrator/appendix_tree.py), поэтому тест накладывает их сам на HEAD.

## Не сработало
- `ls`, `$VAR`, `cd …;` в Bash отклоняются сторожем; `cat <<EOF` с `{` тоже — писать файлы Write.

## Где остановился
Шаг готов: долгоживущий файл 7 passed; планка AC-1 5 failed (нет PLAN.md — честная краснота). Стаб (PLAN = текст TZ) — 5 зелёных, мутант (правка строки приложения 1) — красен; стаб убран task-rm. preflight — все проверки пройдены. `docs/codebase-map.md` не регенерировал: правка вне `tests/` у test_author откатывается — карту обновляет разработчик (требование 3 SPEC).

## Чего не хватило
Где пульт накладывает приложения (не в ветку) — appendix_tree.py, нашёл grep'ом «appendix».
