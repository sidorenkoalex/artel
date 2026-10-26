# Записка test_author

## Выяснено
- Визит 2 (после ANSWER-1, В-1…В-4: A, В-5: B). Дописаны в
  tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py: AC-1 (9 запрещённых
  пар через `gitlab_adapter.request`), AC-2 (10 чтений, 4 записи, 6 отказов
  правки MR без PUT), AC-31 (`forge.project_info`), AC-32
  (`forge.branch_pipeline`); обе новые функции добавлены в GL_CALLS (AC-3,
  AC-18) и GH_CALLS (AC-13).
- Сторож AC-17 (…_forge_guards.py): `urllib.parse` вне транспорта законен,
  `socket` — сеть; добавлены мутанты socket и urllib.request рядом с parse.
- Временный стаб forge/gitlab_adapter под новые тесты: 42+12 зелёных;
  6 мутаций стаба (префикс пары, заголовок без сверки, sort=asc, без ref,
  весь ответ проекта, github→gitlab) пойманы. Стаб удалён.
- markers.py — без пометок, только докстрока со ссылкой на файлы tests/.

## Не сработало
- heredoc/команды с `{"` отклоняет песочница — скрипт писать файлом и удалять.

## Где остановился
- Шаг завершён: preflight пройдена; оба файла tests/ красны по верной
  причине (ImportError `forge` / FileNotFoundError модулей). plank-run
  отвечает «нет файлов test_*.py» — планка состоит только из markers.py.
- Карту `scripts/codebase_map.py` не регенерировал: правка вне файлов с
  префиксом задачи у test_author откатывается.

## Чего не хватило
- Ничего нового: контракт пришёл в ANSWER-1.
