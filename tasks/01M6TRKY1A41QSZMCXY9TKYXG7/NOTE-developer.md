# NOTE developer 01M6TRKY1A41QSZMCXY9TKYXG7

## Выяснено
- Возврат из verifying (CI 42397568738): литерал `merge_gate == "operator"` в `acceptance._freshness_held` → заменён на `not targets.push_whitelisted(entry)` (существующий предикат targets). Сторож `test_ac9_no_support_literals_outside_targets` и тесты задачи зелёные (115 passed). Литералов forge/merge_gate в diff orchestrator/ больше нет.
- Реализовано: `scripts/plan_appendix_ci.py` (сверка FETCH_HEAD, `publication_line`, `appendix_digests`), `orchestrator/ci.py` (`full_suite_publication`, `parse_publication`, `PUBLICATION_*`), `orchestrator/acceptance.py` (`_ci_result_conditions` → 3 значения, `_appendix_ci_refusal`, `_freshness_held`, `_basis_suffix`, `appendix_digests`).
- Долгоживущие файлы задачи: ci_result 41/41, ci_publication 5/5 зелёные.
- `python3 -c "from orchestrator import checkpoint"` падает циклом импорта и на базе — файл `tests/test_01m443…_plan_appendix_ci.py` один не собирается; ставить после файла, импортирующего `catalog`.
- `test_ac4_script_creates_no_commits_and_moves_no_refs` (01m443) виснет в шаге роли: `shutil.which("git")` = обёртка роли `role_bin/git`, которая через PATH находит прокладку теста — рекурсия. Окружение, не код.
- `pytest -n` в шаге роли падает (node down) — гонять последовательно.

- Три существующих случая несвежей ветки при `operator` переведены на `target-human` (мандат ANSWER-1): `test_01m4begq…::test_ac4…` подслучай `stale`, `test_01m5xzskk…::break_condition` ветка `stale_base`.
- Свой тест `tests/test_ci_publication_parse.py` (11), мутации проверены.

## Не сработало
- `sed -i`, `echo $?`, `PATH=…` в Bash роли требуют подтверждения — правки через Edit.

## Где остановился
- Шаг готов: PLAN.md `status: ready`, guard ок, карта регенерирована. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Знания, что `role_bin/git` ломает тесты с `GIT_SHIM` (ушло ~5 минут на тайм-аут).
