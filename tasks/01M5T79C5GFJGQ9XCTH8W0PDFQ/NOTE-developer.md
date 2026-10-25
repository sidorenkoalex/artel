# Записка developer — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- В `gitcmd` добавлены `read` (subprocess.run; места 2, 3, 5, 6, 7), `read_env` (Popen, cwd=ROOT, своё env; место 1) и `read_stream` (Popen-поток; место 4), а также отказы `Timeout`, `OverLimit`, `LaunchFailed(error)`. В `read` в `subprocess.run` передаются только ключевые аргументы, заданные местом.
- Планка: 94/94. Сторож и тесты AC-3: 174 passed. Файлы с подменой `acceptance.subprocess` и прочие вызывающие: 174 passed. test_invariants + codebase_map: 118 passed.
- Свои тесты — `tests/test_gitcmd_reads.py` (5 штук). Каждый проверен временной мутацией и краснеет на ней.
- Карта регенерирована. PLAN — status: ready.

## Не сработало
- Первая мутация «без kill в потоке» не покраснела: без kill чтение ждёт конца sleep, но expired всё равно ставится. Теперь тест проверяет, что код возврата процесса отрицательный (процесс убит сигналом).
- `time.monotonic` в тестах запрещён линтом детерминизма (orchestrator/test_lint.py).

## Где остановился
- Шаг завершён.

## Чего не хватило
- guard.py на файле tests/ ругается на отсутствие frontmatter: его гонять только на артефактах. Заявку мутации проверял через `guard.test_functions_without_mutation_claim('', src)`.
