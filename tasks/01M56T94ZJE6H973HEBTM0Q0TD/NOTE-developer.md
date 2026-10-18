# Записка developer — 01M56T94ZJE6H973HEBTM0Q0TD

## Выяснено
- Возврат из verifying: линт `tests/test_invariants.py::DeterministicTestsLintTest` ловил цикл `while … time.monotonic() < deadline` в `CopyClockOrderTest::test_probe_started_before_first_clock_read_is_cut`. Заменён каналом готовности: пробник `CLOCK_PROBE` печатает `started` после записи «start», тест читает `proc.stdout.readline()` (stdout — пайп в `spawn`). Код внутри строки `CLOCK_PROBE` линт не разбирает (это строка, не AST функции).
- После правки: линт 5 passed, файл 11 passed (60 с), планка 11 passed. Карта регенерирована.
- Ранее: правка — только файл теста и `docs/codebase-map.md`; `COPY_CLOCK`, `ID_LETTERS`, `run_traces`, классы `SuiteRunFixtureIdTest`, `CopyClockOrderTest`.

## Не сработало
- Ранее `suite-run` отказывал из-за чужого полного прогона.

## Где остановился
- PLAN.md status: ready, раздел «Возврат из verifying» добавлен. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Прошлый шаг не прогнал `DeterministicTestsLintTest` на новом файле — стоит гонять его при любой правке tests/ с ожиданиями.
