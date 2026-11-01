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
- Шаг 2 (после rc=1 первого): код из WIP-чекпоинта проверен по SPEC и
  ANSWER-1; долгоживущие + свой тест 55/55, 17 файлов затронутых модулей —
  419 passed; поправлен комментарий `targets.hosting_registry` (выставляет
  `ci`, не `forge`); карта регенерирована; guard PLAN ок; PLAN status: ready.

## Чего не хватило
- В PATH шага нет ls.
