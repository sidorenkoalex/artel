# NOTE reviewer, итерация 1

## Выяснено
- Diff = 2 тестовых файла, соответствует SPEC/ANSWER-1. Правка stop_everything корректна (tree(): probe/tree-<label>, release_path: release-<label>).
- ac8: медиана 8 записей (7×0.28 + настоящий) = 0.28 при любом настоящем; порог 0.448 < 0.48. _series исключает ts <= ack_ts (секундная точность store.now) — сбой в безопасную сторону, флака нет.

## Не сработало
-

## Где остановился
- Готово: два файла задачи — 23 passed, plank-run — 10 passed, REVIEW.md iteration 1 — approved, замечаний нет.

## Чего не хватило
-
