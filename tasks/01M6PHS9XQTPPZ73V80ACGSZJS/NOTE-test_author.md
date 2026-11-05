## Выяснено
- Образец песочницы — tests/test_01m6kbd9fc36warwsy9z0jdmg5_target_set.py (cli через artel.main, локальный слой config.TARGETS.parent/.artel/targets.yaml, копии config.LOGS/targets-*.yaml, журнал steps action=target-set).
- Прецедент закрытого шва: refs/artifacts/01M6KBD9FC36WARWSY9Z0JDMG5 test_ac2_backup_same_second.py — «Группа: разовый» в планке с объяснением.
- Долгоживущий tests/test_01m6phs9xqtppz73v80acgszjs_target_set_key.py: AC-1..4, 6..11, публичная часть AC-12 (отказы прежней формы для новых; сохранность строк вне поля; значения a#b / a # b другой записи).
- Планка acceptance_tests/test_ac5_ac12_seams.py (разовый): AC-5 — текст targets._submodule_tokens_error({ключ: значение}) в отказе; AC-12 — прямой вызов projects._drop_key_mismatches, подмена projects._drop_key_mismatches и projects._target_set_mismatches.
- Запись слоя для загрузчика: description.test_profile с command/long_lived_dir/long_lived_name и policy.weakening_scope + mutation_claim_scope обязательны; такой текст совпадает с выводом _render побайтно.
- Строка журнала, которую ждут тесты: `machine.submodule_tokens[<ключ>]: <было|(нет)> → <значение|(нет)>`; в выводе печатается `target-set: <деталь>`.
- Проверено стабом (потом убран, projects.py восстановлен, git status чист): все 36 долгоживущих + 10 планки зелёные, прежний файл target-set тоже зелёный; со снятой проверкой ключа или комментария AC-4/AC-12 краснеют.
- Красная фаза: 15 из 36 долгоживущих красные, 10 из 10 планки красные; предпроверка пройдена.

## Не сработало
- Нет cp/ls в PATH шага — копировал файлы через python3 shutil.

## Где остановился
- Шаг завершён, сдаю.

## Чего не хватило
- Какие обязательные поля нужны записи слоя для загрузки — нашёл, запустив загрузчик и прочитав отказы.
