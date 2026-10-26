# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- R1-F1 (ревью, итерация 1) закрыт: `gitcmd._local_dest_path` — путь на диске для простого пути и `file://`-адреса; `_push_plan` определяет проект назначения по нему. Под белым списком `file://` отказан и проверкой «не origin и не url записи».
- Тест `tests/test_gitcmd_push_point.py::test_dest_into_project_clone_refused_as_path_or_file_url` — 4 варианта; мутация «путь только без схемы» краснит 2 `file://`-варианта.
- Прогон: push_point + долгоживущие задачи + А0 + test_multitarget — 118 passed; планка — 75 passed. Карта регенерирована.
- В REVIEW.md запись R1-F1 размечена `fixed`.

## Не сработало
- heredoc в Bash роли запрещён (cat/python3 - <<EOF) — правки только через Edit.

## Где остановился
- Шаг завершён: PLAN.md status: ready (шаг 6 в PLAN).

## Чего не хватило
- Ничего существенного.
