# Записка test_author

## Выяснено
- Планка: долгоживущий tests/test_01m6kb0sjhda4d4gnem7pgz40p_decision_reject.py (AC-1…9, 11…15; 44 метода, ~3 мин) + разовый acceptance_tests/test_ac10_reject_signature.py (сигнатура cmd_reject; три названных SPEC теста обвязки lease исполняются в процессе загрузчиком unittest; их файлы не в changed_paths()).
- Песочница: `ComponentsOutcomeSandbox` (через `tests.fixtures._sandbox`), задача — строка БД в `spec_writing` → `store.set_state(..., "spec_gate")` с записью журнала (без неё `brief._spec_gate_reasons` не видит первый возврат и бриф аналитика не находит «Причину возврата»), зоны `box.zones_of("frontend")` (без зон answer отказывает), SPEC.md + `checkpoint.commit_step_artifacts`. `config.TEMPLATES` подменён каталогом песочницы с шаблоном из ТЗ.
- Команды — `artel.main()` с подменой sys.argv; подсказка остановки — `auto.cmd_auto` напрямую (CLI `auto` требует наблюдения).
- Перечень прежних решений тест ищет так: каждое решение — в одной строке вывода вместе со своим номером («k.n»/«k» отдельным токеном); формат строки свободный.
- Провалидировано стабом (удалён, откачен `git checkout --`): 44+2 зелёные; мутант elements вместо id_elements красит test_ac7_id_mandate_prefix_before_comma_refused. До реализации — все 44 красные, планка — 1 из 2.
- preflight пройден.

## Не сработало
- Составные Bash-команды (`cd … &&`, `sed -i … &&`) отклоняются — одиночные команды.
- Песочница на каждый вариант parametrize — ~3 с; варианты отказа свёл в циклы по одной задаче.

## Где остановился
- Шаг завершён; docs/codebase-map.md не регенерировал (правка вне префикса откатится) — это сделает developer.

## Чего не хватило
- Факт, что `_spec_gate_reasons` требует записи `state -> spec_gate` перед возвратом, — нашёл только на стабе.
