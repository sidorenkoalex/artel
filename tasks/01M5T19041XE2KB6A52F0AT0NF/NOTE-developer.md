# Записка developer

## Выяснено
- Возврат 2 (CI 40235484958): `test_multitarget::SqlOnlyInStoreTest::test_no_sql_outside_store` —
  SQL в `workspace._note_unresolved_wrapper`. Вынесен в `store.journal_action_exists`
  (ANSWER-3 расширил зоны на store.py). 114 passed по затронутым файлам, карта регенерирована.
- Возврат 1 (CI 40230886175): `ensure` для проекта без записи в targets.yaml — не отказ, а
  стандартные маркеры + пометка `wrapper_markers_only` (журнал/stderr).
- Ранее: реализация готова (см. PLAN.md), планка 5/5, долгоживущие 50/50.

## Не сработало
- `pytest -n` (xdist) в шаге — воркеры падают; гонять последовательно.

## Где остановился
- Сдано: PLAN.md `ready`, guard ок, код в worktree незакоммичен (коммитит пульт).

## Чего не хватило
- Полный набор разработчику недоступен — инварианты вида «SQL только в store.py»
  (tests/test_multitarget.py) ловит только CI; стоит гонять test_multitarget.py при правке orchestrator/.
