## Выяснено
- Круг 2 (SPEC deba830b): решения Оператора №1 пп.1–3 перенесены в SPEC (Не входит, треб. 3, AC-3).
- Пять копий `?mode=ro`: store.py:337, knowledge_cards.py:767, suite_run.py:179, preflight.py:84, scripts/test_rule_stats.py:72; докстринги/комментарии пишут `mode=ro` без `?`.
- Шпионы существующих тестов патчат `sqlite3.connect` глобально; canary AC-11 разрешает вызывающего orchestrator.store — db_readonly в store совместим.
- test_rule_stats уже тянет store транзитивно через advance_gates.test_integrity.
- Замечание: AC-6 не задаёт `rows` у knowledge/suite_run/preflight — держится существующими тестами.

## Не сработало
- `cd … &&` с `$?` в Bash блокируется (simple_expansion) — звать guard абсолютным путём без переменных.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready; guard прогнан.

## Чего не хватило
- Ничего существенного.
