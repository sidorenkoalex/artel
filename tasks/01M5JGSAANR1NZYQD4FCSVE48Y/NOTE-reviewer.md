## Выяснено
- Итерация 1: changes_requested, одна запись R1-F1 (major). Код по SPEC замечаний не получил; планка 69 passed.
- R1-F1: места таблицы SPEC (fail-closed отказы вместо пропуска: acceptance_suite, _test_integrity_diff_gate, _external_helpers, matrix_refusals, предел full_suite/suite-run; плюс pull, preflight, amend, checkpoint, zones, mutation claim, runner, autogate, review) покрыты только планкой test_places_*.py с пометкой «Группа: разовый». Временная мутация acceptance_suite (profile=None) + _test_integrity_diff_gate (elif False) — 108 тестов tests/ остались зелёными.
- Оставшиеся вызовы decide() сверены: недостижимые fsm_merge_gate:865/:919, _bounds/suite_run._profile_command (только не-multi), brief без task_id. Команда knowledge профиль не читает.

## Не сработало
- Bash: `cd … && …` и `$f` в цикле требуют подтверждения — читать файлы планки через Read.

## Где остановился
- REVIEW.md записан. Следующая итерация: проверить новые тесты в tests/ на места (минимум fail-closed), их заявки «Ловит мутацию» — временной мутацией тех же двух мест.

## Чего не хватило
- Быстрого способа узнать, какие места таблицы покрывают долгоживущие тесты: пришлось grep'ать tests/ по текстам отказов.
