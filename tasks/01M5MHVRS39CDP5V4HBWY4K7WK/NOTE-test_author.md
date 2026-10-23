# Записка test_author

## Выяснено
- Раскладка планки: долгоживущий `tests/test_01m5mhvrs39cdp5v4hbwy4k7wk_run_task_command.py` — AC-1, AC-2, AC-3, AC-4 (AST), AC-6 (сигнатуры); разовые `acceptance_tests/test_commands_reach_body.py` — AC-5, AC-10 (нужен patch закрытых `_cmd_*`, в долгоживущем guard его запрещает), `acceptance_tests/test_branch_facts.py` — AC-7, AC-8, AC-9 (база — `_pult.DIFF_BASE`).
- Возраст heartbeat в AC-3 фиксируется `mock.patch.object(liveness, "datetime", FrozenDatetime)` — имя публичное.
- AC-8 ищет файл разработчика среди НОВЫХ файлов tests/ по строке «Ловит мутацию: в команде возвращена своя копия обвязки или потерян `session_id`» (пробелы схлопываются) в докстринге тестового метода; требует в тексте `run_task_command`, `run_locked`, `SystemExit`, `patch.object` и имена всех семи `_cmd_*`; затем гоняет файл на выгрузке дерева базы (`git archive DIFF_BASE`): ожидает красноту (код 1 и ≥3 failed, либо код 2).
- AC-9: дифф tests/ — только статус A (`--no-renames`); функции lease.py базы — тот же текст; answer.py — всё, кроме cmd_zones_extend и импортов, тот же текст, импорты — подмножество базы.
- Стаб-валидация сделана: временная реализация + стаб файла разработчика -> всё зелёное (долгоживущий 9 passed, планка 5 passed); мутация `same_host_ok=True` в обвязке краснит AC-2/AC-3. Стаб откачен, рабочая копия чистая, кроме долгоживущего файла.
- Красное до кода: долгоживущий (AC-1..AC-4; AC-6 зелёный), test_branch_facts (AC-7, AC-8; AC-9 зелёный на пустом диффе). test_commands_reach_body зелёный с рождения.
- preflight: все проверки пройдены.

## Не сработало
- `ls`/`cat`/heredoc в Bash шага недоступны — только Read/grep/sed/Edit.

## Где остановился
Планка готова, шаг сдан.

## Чего не хватило
- Карта `docs/codebase-map.md` для нового файла tests/ не регенерирована: test_author правит только tests/ (прочее пульт откатит) — регенерирует разработчик.
