# Записка developer

## Выяснено
- Правка — `orchestrator/notes.py::_silence_window_reason` + помощник `_task_project`
  (is_artel первым, resolve только для не-артели; держатель — строка задачи прямым
  SELECT, без get_task/task_target). Внешний триггер пропускается, не закрывает окно.
- Тексты для неизвестного проекта: `<прежний текст>: проект задачи не определён`.
- tests/test_notes.py + долгоживущий файл задачи: 50+1 зелёные; новый тест
  `test_artel_task_and_holder_not_resolved_through_targets` проверен мутацией.
- Карта регенерирована.

## Не сработало
- plank-run: планки в acceptance_tests нет (вся проверка — долгоживущий файл tests/).
- suite-run: занято чужим прогоном гейта 01M55VGDHXQ55YR2YXXBPAHTNB.

## Где остановился
- PLAN ready; полный набор пульта не прогнан из-за занятости замка.

## Чего не хватило
- Нет.
