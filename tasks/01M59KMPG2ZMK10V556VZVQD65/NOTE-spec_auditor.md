# Записка spec_auditor

## Выяснено
- sha SPEC = 38de666f… подтверждён (git hash-object).
- Адреса строк SPEC/ТЗ в guard.py, checkpoint.py, preflight.py, fsm.py, amend.py, dry_run.py, fsm_autogate.py, fsm_merge_gate.py, acceptance.py сверены — сходятся.
- Неверный факт: retro.py:490 зовёт guard.scan_acceptance_tests, НЕ scan_ac_content (SPEC треб. 3).
- Сторож предпроверки (tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py:220-261, 1079): функции guard в теле перехода минус INPUT_FILTERS == функции preflight; фильтр is_extraneous_acceptance_test_file должен остаться в checkpoint; preflight._filtered зовёт фильтр одним аргументом (preflight.py:105) — значит фильтру нужен параметр правила; ссылка на guard.is_extraneous_acceptance_test_file в теле _tests_writing_ac_state покрасит сторож.
- Промежуток G2а-1→G2а-2: автогейт сегодня у .jsx-планки «пуст» (fsm_autogate.py:263) → Оператор; после G2а-1 видит .jsx, а прогона .jsx ещё нет — вопрос Оператору.
- docs/codebase-map.md в COMMON_ZONES (config.py:809).

## Не сработало
- grep с `cd` и `$W`-подстановками отклоняется песочницей — использовать абсолютные пути и Read.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, guard ок. Главное — Е1 (автогейт до G2а-2), Б1 (retro), пробелы AC-3/AC-10/В1–В3, Г1 (сторож).

## Чего не хватило
- Как acceptance.run ведёт себя на планке только из .jsx до G2а-2 (зелено/красно) — по коду не установил за разумное время.
