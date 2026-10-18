# Записка test_author

## Выяснено
- AC-1..AC-4 — tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py (долгоживущий, через `report.cmd_report` → .artel/report.html, разбор разметки HTMLParser).
- AC-5..AC-7 — tests/test_01m57pmbhwk5egq8hpa5tqx72h_watch.py (долгоживущий, `artel.main`: observe register / watch --observation / observe events).
- AC-8 — acceptance_tests/test_ac8_artel_only_unchanged.py (разовый) + эталон-литералы acceptance_tests/_ac8_golden.py, сняты на коде c46d91d4 до правки разовым скриптом (не тестом). Время report заморожено подменой `report.datetime`, ts журнала/алертов — литералы.
- Алерт, заведённый ДО `observe register`, дозор не выводит: позиция наблюдения — максимум журнала на регистрации.
- Запуск test_author без завершения у задачи набора даёт строку «ход шага» с текущим временем — в фикстуре AC-8 он у T005 вне наблюдения.
- Стаб корректной реализации (report: метка `_lbl`, разбивка метрик при >1 проекте; watch: None в targets и `-`) — все мои тесты зелены, AC-8 зелен; мутация «метка каждой задаче» краснит AC-1 и AC-8. Стаб откачен `git checkout`.
- Стаб уронил 6 тестов tests/test_report.py: их фикстуры строк задач без ключа `target` (KeyError) — разработчику брать target как `_tile_html` (report.py:555).
- preflight: все проверки пройдены.

## Не сработало
- heredoc python со строками вида `{x["k"]}` отклоняется проверкой bash («brace with quote») — правки через Edit.

## Где остановился
- Шаг готов к сдаче.

## Чего не хватило
- Карта docs/codebase-map.md не регенерирована: правка вне tests/ test_author'у откатывается — регенерирует разработчик.
