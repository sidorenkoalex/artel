# Записка developer — 01M5NPKPWFEWTYMBYWVR797AM6

## Выяснено
- Модуль orchestrator/mutation_run.py написан по образцу suite_run.py; регистрация в artel.py (table, «Команды:», перечень модулей, импорт, _ROLE_ALLOWED_COMMANDS + комментарий).
- Долгоживущий tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py — 17 passed, 50 subtests (~2 мин).
- «profile is None» SPEC = ветка `suite_run._profile_command`, возвращающая список команды (pult-pytest); Profile-объект или runner != pult-pytest / multi — PROFILE_REFUSAL.
- Строка таблицы пишется до сброса копии: отказ «копия не чиста» строку мутации не теряет.

## Не сработало
- `cat`/heredoc в Bash недоступны — файлы писать инструментом Write.

## Где остановился
- Готово: карта перегенерирована, help_registry и suite_run тесты зелёные (30 passed), PLAN.md status: ready, guard ок. Код не закоммичен — коммит за пультом.
- Тесты под ARTEL_ROLE гонять без `-n`: сторож conftest роняет рабочие xdist.

## Чего не хватило
- Ничего существенного.
