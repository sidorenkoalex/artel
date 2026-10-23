# Записка spec_auditor

## Выяснено
- Факты SPEC о `tests/sandbox.py`, `conftest.py:24-29` и `config.py:774` верны. Приложение 1 проходит `git apply --check`, `index ada960f` = `HEAD:conftest.py`.
- Пробой на Python 3.13.12: `doCleanups()` вне раннера теряет исключение (возвращает `False`, `_outcome` = None), поэтому «текст причины» из него не получить.
- `config.TWO_SIDED_OBSERVATION` по умолчанию `True` (`config.py:217`), так что проверка AC-6 различает импорт с побочным эффектом и без.
- Импорт `tests.fixtures` исполняет `tests/__init__.py` — на macOS это `prefer_direct_git` (меняет PATH).
- Вердикт `concerns`. Отклонения: A-1 (тесты (а)–(е) ТЗ п.3 не привязаны к файлу `tests/`), B-1/C-2 (текст причины), C-1 (AC-1: isinstance пропускает подкласс), B-2 (PATH).

## Не сработало
- `cat`/`ls`/`rm` в оболочке шага недоступны; файл удалял через `python3 -c os.remove`.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Нигде не записано, что `doCleanups()` вне раннера теряет текст исключения; проверял пробой.
