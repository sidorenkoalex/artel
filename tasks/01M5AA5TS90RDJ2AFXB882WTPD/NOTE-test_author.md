# Записка test_author — 01M5AA5TS90RDJ2AFXB882WTPD

## Выяснено
- Прецеденты стенда: tests/test_01m5633wz3y3a0p4kkbzdb3ker_long_lived_imports.py (cmd_advance/preflight/amend внешнего проекта), tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py (шпион Popen для vitest), tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_mission.py (миссии).
- Гейты групп и долгоживущих в fsm_advance.tests_writing идут ДО сухого сбора.
- AC-10: построенный профиль — patch.object(project_profile, "decide") (публичное имя), dataclasses.replace с long_lived_template.
- Чекпоинт шага чистит каталог черновика: перед повторной записью планки/PLAN — mkdir.
- Ожидания тестов (не указания разработчику, только то, что тесты читают): AC-7 — фраза «в первом комментарии файла» в строке отказа о файле и для «нет строки», и для «иное значение»; AC-9 — «перенеси файл в frontend/src/<каталог>/<имя>.<id>.test.jsx кодовой ветки»; AC-6 — guard.acceptance_traceability_errors(tdir, extra_sources=[(путь, текст)], rule=rule).

## Сделано
- acceptance_tests/test_ac14_preflight_sentry.py (разовый, AC-14) — зелёный.
- tests/test_01m5aa5ts90rdj2afxb882wtpd_template_record.py (AC-1..4, 16, 13).
- tests/test_01m5aa5ts90rdj2afxb882wtpd_template_hints.py (AC-15, 13).
- tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py (AC-5..12, 13).
- Валидация: временный стаб реализации (откачен, git status чистый кроме трёх файлов) — все методы зелёные; мутация «без проверки заявки» краснит AC-8. AC-13 зелены на базе ветки.
- preflight пульта: все проверки пройдены; plank-run: 1 passed.

## Где остановился
Шаг завершён.

## Чего не хватило
Дольше всего — порядок гейтов выхода из tests_writing (fsm_advance.tests_writing:506) и то, что чекпоинт убирает черновик.
