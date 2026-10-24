# Записка spec_auditor — 01M5NPKPWFEWTYMBYWVR797AM6

## Выяснено
- Факты SPEC о коде в основном верны: suite_run.py:553 `_base_copy`, :858 `cmd_suite_run`, :921–922 env без ARTEL_ROLE; suite_lock.py:40/93/166/172; acceptance.py:71/2343; appendix_tree.py:133; outcome.py:145; project_profile.py:379; artel.py:2181; config.py:132 = 2700.
- Неверно/неточно: config.py:230 `FULL_SUITE_WORKERS = "auto"`, не 2 (в SPEC п.11 — читать как подмену в тестах).
- Главная находка: `_carry_uncommitted` (appendix_tree.py:133–166) копирует файлы без коммита, а п.5 SPEC велит `git reset --hard HEAD && git clean -ffdx` после каждого патча — при `--ref worktree` со второго патча незакоммиченные файлы стёрты.
- outcome.verdict (outcome.py:271–273): все passed + ненулевой код → «неизвестно»; SPEC п.6 даёт «не убита».
- run_full_suite с профилем-отчётом игнорирует `extra` (acceptance.py:2416–2418).
- Импорт mutation_run в artel.py (:797) и строка списка модулей (:650) — вне буквального ограничения зоны artel.py.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns, status ready; guard ок; blob-sha SPEC.md = d7decd89… совпал с миссией.
- Прочие отклонения: отказ `--tests` только для литерала `tests` (обход `tests/`, `./tests`); «остаток предела» не определён; «красный» контроль не определён; нет матрицы неослабления.

## Чего не хватило
- Нет.
