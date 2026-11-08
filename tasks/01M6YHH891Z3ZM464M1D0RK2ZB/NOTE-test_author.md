# Записка test_author — 01M6YHH891Z3ZM464M1D0RK2ZB

## Выяснено
- Прошлый визит не оставил ни одного файла планки (отказ трассируемости по всем AC-1..AC-10).
- Bash роли урезан: grep/wc/python3/git работают, ls/cat — нет.
- Файлы: долгоживущий tests/test_01m6yhh891z3zm464m1d0rk2zb_poll_step.py (AC-1, AC-2: шаг первой паузы опроса == подменённый config.SUITE_RUN_POLL_SEC; пауза через tests/sandbox.py::patch_sleep у suite_run и mutation_run; прогон «идёт» — run.json / mutation-run.json под suite_lock.directory()/<id> с pid процесса теста). Разовый acceptance_tests/test_suite_run_file_shape.py: AC-1 статика, AC-3 (настоящий SuiteRunSandbox.setUp, AST копии config.py), AC-4 (stop_everything на журнале из os.getpid() и своих /bin/sleep, обёрнутая pid_alive модуля), AC-5..AC-9 — AST тестового файла с разворачиванием вызовов помощников self.<имя>; AC-9 сравнивает утверждения с базой через git show DIFF_BASE. AC-10 — manual (прогон mutation-run пульта).
- Красная фаза: 7 failed/1 passed (ac9 зелён с рождения), долгоживущий — 3 failed (AttributeError SUITE_RUN_POLL_SEC).
- Стаб (config, suite_run, mutation_run, правка тестового файла: process_snapshot/assert_no_process, ppid-цепочка от holder в ac21, лог базы = run.json["log"] без .log + "-base.log") — планка 8 passed, долгоживущий 3 passed, тесты файла ac3/ac9/ac16 гейт/ac21/ac24 на стабе зелёные (47 с). Стаб откачен git restore, дерево чистое.
- preflight: все проверки пройдены.

## Не сработало
- Первый вариант AC-9 считал свой помощник assert_no_run утверждением unittest — исправлено (методы файла исключены).

## Где остановился
- Шаг завершён: планка и долгоживущий файл готовы, preflight пройден.

## Чего не хватило
- Где лежит лог базы: suite_run._log_path(task, n, "-base") — в каталоге задачи хозяйства suite-run рядом с run.json.
