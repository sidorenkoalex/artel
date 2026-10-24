# Записка test_author

## Выяснено
- Все 7 AC — факты задачи (дифф двух тестовых файлов, PLAN, патчи мутаций): один разовый файл планки `acceptance_tests/test_speed_cleanup.py`, долгоживущих файлов нет.
- AC-1/AC-6 проверяются поведенчески: `LockSandbox.stop_everything` вызывается на поддельном объекте (AC-1) и оборачивается при прогоне трёх тестов full_suite_lock (AC-6: к первому `kill_group` все дети уже завершились, живых pid нет).
- AC-3: ac8 прогоняется с обёртками `measured_run`/`journal_measurement`, записывающими последовательность вызовов.
- Формат вывода mutation-run: шапка `# mutation-run №N задачи <id>`, `# ревизия прогона: <ref> <sha>`, `# патч N mutation-00N.diff sha256 <hex>`, строки `N\tубита\t<узлы>` (orchestrator/mutation_run.py:539–556, :499–501).

- До правки: 7 failed, 3 passed (ac2, ac4 и параметр ac9 test_ac6_cleanup — зелёные с рождения; ac9 к снятию групп и так без живых детей). На стабе (removeprefix + measured_run(0.01) первым, journal 1.12 / сигнал 1.92) все код-тесты зелёные; стаб убран, дерево чистое.
- AC-3 требует калибровку ровно 0,28 с на тест (образец 1.12 при 4 тестах) и сигнал от 0,48 с на тест; ac8 обязан пройти.
- AC-5 разбирает в PLAN дословный вывод mutation-run (шапка + строки `N\tубита\t<узел ac8>`) для ref base и worktree, sha256 патчей = sha256 файлов документов, `git rev-parse <sha>:orchestrator` равны, строка `FAILED … test_ac8_…`.
- AC-7: changed_paths ⊆ {два тестовых файла, docs/codebase-map.md}; PLAN содержит `--wait-lock`.

## Не сработало
- `cat`/`ls` в Bash недоступны — Read/find/sed; heredoc с `{"` песочница отклоняет — скрипт файлом.

## Где остановился
- Планка готова, plank-run и preflight пройдены (preflight: все проверки «пройдена»).

## Чего не хватило
- —
