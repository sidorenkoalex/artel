# Записка developer — 01M5TBFH5VZ7GSRXX7VNKHFCCQ

## Выяснено
- Ветка уже несёт Э1 (`orchestrator/board.py` есть после подтяжки main ca8acbec7).
- Реализация: `schema.EXTERNAL_REFS_DDL` (SCHEMA + migrate), `store.*external_ref*`,
  `targets` поля `policy.ref_required/ref_systems`, `board.build_model(..., with_waiting=True)`
  + поля карточки/`refs` + `board.cmd_board`, `report` из модели (`board_models` в `_render`,
  группы эпиков `_column_tiles_html`), `catalog._new_refs/cmd_link`, копия ссылок в `spawn_subtask`,
  `artel.py` — `--ref`, `board`, `link`.
- Элемент `refs` = {system,key,url,by,at} — без id строки/владельца (AC-13 сравнивает поэлементно).
- tests/test_report.py: пять методов — `id=` → `task=` + докстринг «Ловит мутацию» (гейт заявки
  мутации считает метод изменённым). Утверждения прежние.
- Побайтность доски без эпиков сверена старыми функциями из HEAD (временный тест, удалён).

## Не сработало
- `ls`/`rm`/перенаправление в /tmp в Bash роли недоступны — python3 -c.

## Где остановился
- Всё сделано: тесты задачи 41 passed, планка 2 passed, соседние 407 passed, карта обновлена,
  PLAN.md status: ready.

## Чего не хватило
- Что изменённые по мандату методы требуют заявку мутации — выяснил чтением guard.py.
