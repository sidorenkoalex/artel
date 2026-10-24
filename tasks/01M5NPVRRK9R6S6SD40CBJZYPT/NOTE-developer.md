# Записка developer — 01M5NPVRRK9R6S6SD40CBJZYPT

## Выяснено
- Правка — только `pull._materialize_and_run_plank`: `ExitStack` +
  `appendix_tree.suite_tree` перед `acceptance.run`; `tree.root is None` →
  journal по `tree.fixable` + `Refused`; `tree.root != wt_path` →
  `plank_in_code_copy(task_id, artifact_branch_name, tree.root)`, cwd=tree.root.
- Долгоживущий файл задачи 7/7 зелёный; test_pull + 20 файлов вызывающих
  pull — 365 passed. Карта регенерирована.

## Не сработало
- `pytest -n 4` — все воркеры «node down»; гонять последовательно.
- `plank-run` — «планки нет» (планка целиком долгоживущая) — ожидаемо.

## Где остановился
- PLAN.md status: ready; код не закоммичен (коммитит пульт).

## Чего не хватило
- Ничего существенного.
