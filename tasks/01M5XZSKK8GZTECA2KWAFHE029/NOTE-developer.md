# NOTE-developer

## Выяснено
- forge.py вне зоны (только чтение), а AC-3 требует отказа загрузки по
  реестру forge.IMPLEMENTATIONS. Решение: `targets.hosting_registry` —
  атрибут, который выставляет ci.py (импортирует и forge, и targets):
  `targets.hosting_registry = lambda: forge.IMPLEMENTATIONS`. Цикла нет.
- Итог задания CI — `ci.job_full_suite(target, sha, job)`; три условия —
  `acceptance._ci_result_conditions(root, branch, repo, base)` (общие с артелью).
- Режим ci/both — `acceptance._ci_job_suite_run`, вызывается из
  `_acceptance_suite_run` по `profile.full_suite`.
- Автогейт: `acceptance.is_ci_result(run)` вместо подстроки.
- Долгоживущие файлы задачи: 51/51 зелёные.

## Не сработало
- (пока ничего)

## Где остановился
- Код готов; прогон тестов затронутых модулей, PLAN.md.

## Чего не хватило
- В PATH шага нет ls.
