# Записка developer

## Выяснено
- Правка — `orchestrator/review.py::review_package`. Развилка
  `brief.is_artel_task`. У внешней задачи после формы вердикта идут куски
  `brief._project_conventions_parts(..., "reviewer", run_id, _conventions_component)`,
  а абзац исключений — короткий, без джоба и команды карты. Ветка артели — прежний текст.
- Долгоживущий тест задачи (коммит ba3c8a3d) и 7 соседних файлов review-тестов
  зелёные: 209 passed. Планки acceptance_tests нет.
- Карта `docs/codebase-map.md` регенерирована (изменилась из-за нового файла tests/).

## Не сработало
- `cd ... && sed` / `ls` требуют подтверждения — читать через Read.

## Где остановился
- PLAN.md status: ready, guard ок. Код не закоммичен — коммит за пультом.

## Чего не хватило
- Ничего существенного.
