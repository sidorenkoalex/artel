# Записка spec_auditor (аудит SPEC sha 0020cce9…)

## Выяснено
- Требование 7 кладёт `tools` в `Profile` только через `decide`, но ключ кэша считают по `Profile` из `Profile.from_values(profile_of.values)` в обход `decide`: acceptance.py:2407 (`_task_own_profile` — автогейт приёмки, pull.py:665, plank_run.py:220, amend.py:548/723) и suite_run.py:294 (`_profile_command` — поиск ключа базы, suite_run.py:523). Через `decide` идёт только гейт мержа (fsm_merge_gate.py:832-837). Итог: в проде `tools` в ключ приёмки не попадут, ключ базы гейта мержа (с tools) и suite-run (без) разойдутся — AC-12 невыполним без правки suite_run.py (вне зон).
- AC-3 не ловит мутацию «сравнение строковым префиксом» (все 4 случая проходят).
- Имена/гранулярность новых строк doctor и шов подмены запуска инструментов не названы.
- Факты SPEC о строках кода (cli.py:13-20/94, acceptance.py:2150/2318-2322/2041-2048, suite_run.py:521-524, project_profile.py:184-188, repo_context.py:161-163) подтвердились.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан.

## Чего не хватило
- Карта не показывает, кто строит `Profile` в обход `decide` — нашёл grep'ом `Profile.from_values`.
