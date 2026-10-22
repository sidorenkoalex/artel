# Записка аналитика 01M5J0JYW3

## Выяснено
- Возврат аудита (fail) принят: противоречие ТЗ п. 2 (TZ.md:29) и п. 8 (TZ.md:37) о C у компонента без `tests` реально. junit_project (outcome_gate.py:563-602) без `tests`, vitest_project с `tests` (:614). `junit_project(` — 65 вызовов: outcome_gate 29, merge_outcome_gate 18, file_level 11, fail_to_pass 7.
- По прочтению п. 2 краснеют Ac6RerunTest :1552-1556 и :1573 (третья выписка метится side=head). По прочтению п. 8 (у junit_project нет test_support) C пуст, правок нет.
- Записан QUESTIONS.md (3 вопроса: C без tests; сбой диффа → _Prepare; канарейка в предикате автогейта), guard ок. SPEC.md не тронут.
- `_bounds(is_canary, target)` — outcome_integrity.py:536; ядро fail-closed через `except Exception` (:578).

## Где остановился
- Батч сдан, задача эскалирует. После ANSWER в SPEC нужно: (1) C по ответу на вопрос 1, AC-9; (2) AC-16 переписать — у исчезнувшего теста только «исчез … замена SPEC», а снятие «прежняя версия красная» проверить на заменяемом тесте, который на ветке есть; (3) раздел «Матрица неослабления» — строки на `_plank_rule_refusal` (fsm_autogate.py:236-253) и `_weakening_scope_refusal` (mandate.py:214-218, тесты weakening_mandate_scope.py:49, id_mandate_answer.py:462); (4) сбой диффов → _Prepare (вопрос 2); (5) предикат автогейта с канарейкой (вопрос 3); (6) AC-12 усилить (маркер до третьей выписки, а не только до первой); (7) убрать вывод «правок не нужно» из «Материалов», если выбран не A; удалить QUESTIONS.md.

## Не сработало
- pytest -n в шаге падает (node down) — гонять с -p no:xdist.

## Чего не хватило
- Опись прогонов фикстуры outcome_gate (subset_runs/side_of по app.py) — без неё вывод о совместимости в прошлом SPEC оказался ложным.
