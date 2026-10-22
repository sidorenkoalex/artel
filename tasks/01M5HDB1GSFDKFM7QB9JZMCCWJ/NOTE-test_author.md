# Записка test_author

## Выяснено
- Порядок `cmd_suite_run` (orchestrator/suite_run.py:771): `_db` → `resolve_task_id` → `deliver_journal` → `--wait` → профиль → рабочая копия → `--failed` → `_running` → замок → лог → Popen → run.json.
- Рабочая копия `workspace.path(id, "artel")` лежит под `config.PROJECTS` песочницы — хватает mkdir, патч не нужен.
- Фоновый процесс в тесте исполняется в процессе теста (как `run_child` в стенде `readonly_db`), `acceptance.run_full_suite` подменён готовым выводом pytest, `appendix_tree.suite_tree` — сама рабочая копия.
- Отказ developer (AC-1) по критерию не должен вызывать `store.db` ни при обычной БД, ни при подмене на БД только на чтение; id разрешается своим `sqlite3.connect(...?mode=ro, uri=True)`.

## Что сделано
- Долгоживущий: tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py — AC-1…AC-7 (8 методов). Красные AC-1, AC-2, AC-5, миссия AC-7; зелёные с рождения AC-3, AC-4, AC-6, ревьювер внешнего проекта.
- Разовый: acceptance_tests/test_task_facts.py — AC-7 (файл test_01m462… не тронут), AC-8 (в файле readonly_db изменён только `ROLES`, у пяти методов те же утверждения; матрица в PLAN — строка таблицы на каждый метод), AC-9 (статический разбор нового файла).
- Проверено временным стабом (откачен): всё зелёное, включая `MissionTest::test_ac25`; мутации «отказ любой роли» и «отказ после deliver_journal» красят AC-6 и AC-1. preflight пройдена.

## Где остановился
- Шаг завершён.

## Не сработало
- `ls` и составные команды Bash (`for`, `sed -i` вместе с `;`) требуют подтверждения — делал по одной команде.
- Карту кодовой базы не регенерировал: `docs/codebase-map.md` лежит вне `tests/`, такую правку пульт откатит.

## Чего не хватило
- —
