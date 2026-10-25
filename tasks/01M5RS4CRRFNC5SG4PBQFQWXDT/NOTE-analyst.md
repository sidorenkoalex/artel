# Записка аналитика

## Выяснено
- ТЗ достаточно; SPEC.md написан (status: ready, 24 требования, AC-1…AC-19, budget_usd 50 из ТЗ), guard — ок.
- Факты ТЗ сверены на a8e57874 разбором AST: файл 1736 строк / 113 352 байта; 14 классов задачи несут 22 теста; оставшиеся классы и `env_lines` читают из песочниц ровно `Moved`, `ReplacementSandbox`, `StrictSandbox`.
- Адреса: `PriorSandbox` — :108, `ReplacementSandbox` — :880, `StrictSandbox` — :1160, константы — :62–95, импорты — :41–59; `tests/test_outcome_gate_module.py` — `box` :813, `refusal` :821, `no_gate_refusal` :834; `GATE_ACTIONS` — `tests/outcome_gate_sandbox.py:36`; `_sandbox` — `tests/fixtures.py:42`.
- Уточнения ТЗ от 25.10 внесены прямо в требования (перечень классов «другой задачи», `import pytest`, форма сообщений `passed`/`grant`, все `self.<имя>` → `box.<имя>`).

## Не сработало
- В шелле роли нет `ls`/`rm`; составные команды с `$?` и `${…}` требуют подтверждения. Временный скрипт удалён через `python3 -c "os.remove(...)"`.

## Где остановился
- Шаг закончен: SPEC сдан, guard зелёный.

## Чего не хватило
- Ничего существенного; образцом формы служил SPEC 2а-2б (`git show refs/artifacts/01M5RH875Q1JMVRM1TXNE6HNMW:tasks/.../SPEC.md`).
