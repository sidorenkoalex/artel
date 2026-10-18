# Записка spec_auditor — 01M56TNX1WWKV8PVQ94FT4ZJQB

## Выяснено
- SPEC sha 991e5412 сверен. Факты guard.py подтверждены: SKIP_DECORATOR_NAMES 649-650, _decorator_skip_markers 673-681, _body_skip_markers 684-697, TEST_METHOD 178 (якорь `^\s*def`), сборщик 621/626 уже берёт AsyncFunctionDef.
- test_integrity.py: _CONDITIONAL_DECORATORS 142 (SPEC пишет 141), _decorator_occurrence 294-313, _skip_calls 316-337, сравнение маркеров 441-457. Журнал условных пропусков — _journal_pass 1236-1239, НЕ 854-866 (там assertion_observation).
- _compare (665-811) идёт только по файлам диффа; файлы вне диффа видны лишь через поиск вызывающих помощника (_helper_callers 631-662) — для AC-4 (меняется только модуль метки) нужен аналогичный поиск импортёров метки.
- guard.TestModules (989-1041): у артели модуль импорта — только tests/<…>, функции — только tests/sandbox.py; у внешнего — путь от workdir, в области.
- Тестов, утверждающих обратное новому поведению, в tests/ нет (test_guard_test_ast.py SkipMarkersTest — совместимы).
- Вердикт: concerns (пробелы AC для условных модульных пропусков на методах базы, AC-8 без импорта/AC-3 у артели, незаявленный пробел «метка из tests/<не sandbox>.py у артели», неверная ссылка журнала).

## Не сработало
- Составные bash-команды с `;`/`|` требуют подтверждения — только одиночные grep/sed с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Где пишется журнал условного пропуска (нашёл grep по `cmp.passed` → test_integrity.py:1236).
