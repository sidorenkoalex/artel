# Записка developer

## Выяснено
- `tests/fixtures.py`: переходник `_sandbox(cls)`, шесть фикстур; долгоживущий файл 43/43, планка 2/2.
- Возврат из verifying (CI 40028534489): безусловное `pytest_plugins` роняло ImportError в зеркале `CollectFromTestsDirTest::test_clean_long_lived_file_collects_from_tests_dir`. Приложение 1 PLAN заменено условным текстом Оператора (`importlib.util.find_spec`), `git apply --check` rc 0.
- Новый тест разработчика `tests/test_fixtures_plugin_conditional.py` (не в форме `test_<id>_*`, т.е. не долгоживущий): зеркало из настоящего conftest.py (+строки приложения, если не наложено) без/с `tests/fixtures.py`.
- С временно наложенным приложением: 54 passed (вкл. упавший в CI тест); мутация «безусловное подключение» — оба теста красные; conftest.py возвращён `git checkout`.
- Карта регенерирована.

## Не сработало
- Bash: `$?` в команде требует подтверждения — используй `&& echo OK`.

## Где остановился
- Готово: PLAN.md status: ready, guard ок, планка 2/2.

## Чего не хватило
- Команды пульта для `git apply --check` приложений PLAN (делал через `guard.plan_appendices` + `git apply -`).
