# Записка test_author — 01M5PCB66D936FDGG7H09CVGA1

## Выяснено
- Образец — планка волны 1а (refs/artifacts/01M5NNDYGQ8G6VFDEEXYBB0W3D, acceptance_tests/), прошла приёмку; 1б — её адаптация под 15 AC.
- Планка (все «Группа: разовый», пометок manual/skip/escalate нет): `_plan.py` (разбор, без импорта `_pult`);
  `test_mutation_patches.py` (AC-1), `test_mutation_tables.py` (AC-2, 3, 4, 9, 10, 11, 12),
  `test_module_form.py` (AC-5, 6, 7, 8, 14), `test_branch_diff.py` (AC-13, 15).
- Соглашения разбора PLAN — докстринг `_plan.py` (как в 1а) + ссылка на узел «после» для отметки setUp:
  `test_doc_commit_module.py::<функция>[<вариант>]` в строке со словом setUp/«подготовк» и ссылкой на мутацию.
- База: 6 файлов, 71 тест (все в классах, у всех «Ловит мутацию»), 2271 строка; 3 места проверки текста исключения;
  перебор константы — только `notes.DOC_COMMIT_CONFIG_PATHS`; литеральных наборов subTest нет.
- AC-5 в планке: утверждения (assert/pytest.raises/fail/self.assert*) запрещены в фикстурах И в методах классов —
  помощники `origin_show_bytes`, `hold_doc_commit`, `hold_note`, `hold_config_without_base`, `assert_refused`,
  `_stale_scenario`, `assert_nothing_sent`, `refuse_config` должны стать функциями модуля.
- AC-6 в планке: тест без фикстур (параметры — только parametrize) не держит `for` по литеральному набору
  (PathRefusalTest → parametrize); зерно печатает каждая функция с `random.SystemRandom/Random`, не тестовая.
- Формат таблицы — orchestrator/mutation_run.py::_header/_Run.row.

## Не сработало
- `ls`/`cat` в Bash нет (PATH), команды с `$` требуют подтверждения.

## Где остановился
- Шаг завершён: plank-run — 31 failed / 1 passed (зелёный AC-15 «orchestrator/фикстуры не тронуты» — корректно до кода),
  краснота по причине «нет PLAN/патчей/нового файла». Стаб в памяти: корректный сценарий 28/28 зелёный,
  31 мутация сценария поймана своими тестами; скрипт стаба удалён. preflight — всё «пройдена».

## Чего не хватило
- Ничего существенного; перечня файлов ссылки документов в `_pult` нет — `git ls-tree` по DOCS_REPO/DOCS_REVISION.
