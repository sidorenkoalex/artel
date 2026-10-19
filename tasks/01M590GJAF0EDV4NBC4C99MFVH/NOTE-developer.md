# Записка developer — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Визит 1. Долгоживущий tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py прочитан (1890 строк); узел — `acceptance.full_suite(root, task, command=<профиль>, fresh=True)`, итог по тестам — `FullSuiteRun.tests`.

- Новые поля Profile — `compare=False`: tests/test_01m58fnwbv25ff26e7az9q9912_components.py сравнивает профиль decide с вручную собранным и профиль test_profile с профилем единственного компонента.
- Зона SPEC не включает новых модулей кроме `orchestrator/reporters/` — разбор отчётов там (`reporters/outcome.py`), узел прогона — в acceptance.py.
- test_integrity.py (вне зоны) передаёт two_sided профиль только при pytest-own — двусторонний прогон компонента без runner через гейт идёт раннером пульта (риск в PLAN).

## Не сработало

## Где остановился
- PLAN.md черновик; сделано: project_profile.py, reporters/ (js + outcome.py), acceptance.py (`_report_run`, установка/подключение, `components_full_suite`, `run_checks_local`, ключ, `place_channel`), сторож. Долгоживущий файл задачи — 26/26 зелёный.
- Вызывающие сделаны. plank-run: 14/15 зелёные; красный только AC-21 — `artifact_text("PLAN.md")` читает PLAN из ссылки документов, до автокоммита шага его там нет (ожидаемо).
- Сделано: приложения инв. 41 в PLAN.md (guard.plan_appendices — без ошибок, `git apply --check` — проходит, метод зелёный, ловит обе мутации); свои тесты tests/test_component_report_run.py (5, мутации проверены).
- suite-run №1 запущен до мутационных проверок (мутации на секунды правили outcome.py/acceptance.py — краснота в №1 по ним возможна, повтор --failed).
- Дальше: отчёт suite-run, карта (`scripts/codebase_map.py`), guard, PLAN status: ready.

## Чего не хватило
