# Записка test_author — 01M5NHXJA3X7C66XTJN4J3E25W

## Выяснено
- Гейт приёмки гоняет планку и долгоживущие файлы на дереве «HEAD + приложения PLAN» (`orchestrator/advance_gates/acceptance.py:598`, `appendix_tree.suite_tree`); приложения ложатся незакоммиченными, HEAD = база.
- AC-2, AC-3, AC-4 — долгоживущий `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py` (стиль pytest; он же — «новый файл тестов задачи» для AC-5). Без приложений: AC-2 красен (код 4, ModuleNotFoundError 'tests'), AC-4 красен (нет класса инварианта), AC-3 зелёный с рождения.
- AC-1, AC-5, AC-6 — разовый `acceptance_tests/test_task_facts.py` (через `_pult`). AC-1 накладывает приложения PLAN (`guard.plan_appendices`) и эталон (блоки ```diff TZ.md для conftest/skills, SPEC.md для test_invariants/docs/invariants) во временный индекс от HEAD и сравнивает sha блобов пяти файлов.
- Валидация стабом: дерево `git archive HEAD` + Приложения 1–3 ТЗ и 4–5 SPEC — долгоживущий файл 9 passed; со слабым Приложением 4 из ТЗ — 4 варианта мутаций красные. AC-1: PLAN из эталонных блоков — зелёный, PLAN с Приложением 4 ТЗ — красный (tests/test_invariants.py).
- preflight: все проверки пройдены.

## Не сработало
- `ls` в Bash недоступен (command not found) — каталоги смотрю через python/os.walk.
- heredoc python со `{` и кавычками рядом отклоняется — писать без словарных литералов.

## Где остановился
- Шаг завершён: планка и долгоживущий файл написаны, прогнаны, preflight пройден.
- Карту `docs/codebase-map.md` не регенерировал: правка вне tests/ test_author'у откатывается — регенерирует разработчик.

## Чего не хватило
- Как гейт исполняет планку относительно приложений PLAN — нашёл в `advance_gates/acceptance.py` docstring ~строки 528–533.
