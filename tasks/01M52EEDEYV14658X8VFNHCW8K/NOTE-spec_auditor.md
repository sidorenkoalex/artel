# Записка spec_auditor — 01M52EEDEYV14658X8VFNHCW8K

## Выяснено
- Второй визит (spec_sha 3ba65fac…): все шесть решений Оператора 16.10 внесены в SPEC; ссылки SPEC на код подтвердились (targets.py:281, acceptance.py:86/923/1115/1372, two_sided.py:222/230-232, yamlmini.py:57-62, targets.yaml:46, тесты :210/:178, test_profile.py:103/151-152).
- `_pytest_command` заменяет `python3` на интерпретатор venv (acceptance.py:61-62) — argv путей `command=None` и `command=[python3,-m,pytest]` совпадают.
- Профиль хешем не используется (lru_cache/hash по Profile не найдено) — dict-поле `env` во frozen dataclass не ломает потребителей.
- docs/codebase-map.md — в config.COMMON_ZONES (config.py:799).

## Не сработало
- Составные команды bash (`W=…; sed …`) режет разрешение — по одной команде.

## Где остановился
- Вердикт concerns: AC-7 допускает тавтологическое ожидание (expected из `_pytest_command`/`_pytest_env`) и не называет значения переменных; «содержит `..`» — подстрока или сегмент.

## Чего не хватило
- —
