# Записка developer — 01M5TBFCVFNN95BHH0E9C6KBKB

## Выяснено
- Возврат из verifying (CI 40266189759): `scripts/plan_appendix_ci.py` импортировал `orchestrator.config` — запрещено тестом `test_ac9_ci_script_does_not_import_orchestrator`. Исправлено: литерал `EPIC_REF_NAME_PREFIX = "epic-"`, равенство с config держит `tests/test_epic_drafts_units.py::test_ci_script_epic_prefix_matches_config` (красный на мутации). Карта перегенерирована.
- Дизайн в PLAN.md: таблицы `epic_drafts`/`epic_decisions` с ключом (epic_id, number); файлы ссылки — Markdown + первая строка `<!-- artel-epic-…: JSON -->`; запись `epics._write_ref` → `artifact_branch.commit_files("epic-<id>", …, target=project)`; `cmd_epic` в `deferred_sends()`.
- Прогон после правки: 84 passed (ci_in_base, все plan_appendix*, ref_scans, drafts, свой файл).

## Не сработало
- `pytest -n` — сторож роли считает полным прогоном; гонять с `-p no:xdist`.
- `tests/test_01m443hv9sjyvyqthjsq87qv68_plan_appendix_ci.py` первым в прогоне падает циклом импорта (checkpoint→fixation→…→artifact_branch); есть и на origin/main — ставить после другого файла.
- sed/heredoc/`$(…)` в Bash отклоняются — правки Edit'ом.

## Где остановился
- Готово, PLAN status: ready.

## Чего не хватило
- Правила «CI-скрипты не импортируют пульт» не было в брифе — узнал только из красного CI.
