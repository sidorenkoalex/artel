# Записка spec_auditor — 01M5NPKPWFEWTYMBYWVR797AM6 (круг 2)

## Выяснено
- SPEC blob 91ac5b6a… совпал с миссией. Все 11 решений гейта круга 1 внесены.
- Факты верны: suite_run.py:553/858/921–922, suite_lock.py:40/93/166/172(:178 сравнение run), acceptance.py:71/2343, appendix_tree.py:133 (переносит только неигнорируемые — коммит-основа исполним), outcome.py:145, config.py:132/223/230("auto")/238, artel.py:2181/2312/797/650/158. Сторож conftest.py:78 (SPEC пишет :80).
- run_full_suite отдаёт (green, output), без кода возврата; предел — по префиксу вывода acceptance.py:2448.
- Подпроцессный тест с FULL_SUITE_WORKERS: прецедент — копия orchestrator/ в песочницу с дописанной константой (tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py:208–211).
- Отклонения (concerns): О-1 источник refs/artifacts и sha ссылки без AC; О-2 porcelain-отказ без AC; О-3 неизменность docs/refs без AC; О-4 Codex/readonly БД не оговорён; О-5 нет строки инварианта 40 (invariants.md:70); О-6 перечень «трогает тесты» без .pytest.ini/pytest.toml/copy; О-7 «нормализация относительно копии» vs отказ до копии; пустой набор/кривой --patches не уточнён.

## Где остановился
- SPEC-AUDIT.md написан: verdict concerns, status ready; guard ок.

## Не сработало
- Bash с `$VAR`/`cd` в команде требует подтверждения — писать абсолютные пути.

## Чего не хватило
- Нет.
