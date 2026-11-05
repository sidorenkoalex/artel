# Записка analyst

## Выяснено
- Итерация 2: возврат со spec_gate с 10 решениями Оператора; все внесены в SPEC (требования 12–15, 17; AC-1, AC-2, AC-4, AC-5, AC-6; «Не входит»; «Материалы» — карта решение → критерий).
- Якоря решений сверены по worktree 54fe44ebb: runner.py:1819-1827 (только OSError из role_env), merge_after.py:654-660, targets.py:83 (нет compose), doctor/cli.py:221-226.
- Метка пульта части 1 = тройка `artel.run-pid/host/started`, `<прогон>` = 8 строчных hex (SPEC части 1, требования 3–4, refs/artifacts/01M6PAJ61D4PYAP79ADRPA6MWV).
- Решение 4 «тома не удаляются» → `down --remove-orphans` без `-v` (прежде было `down -v`).
- Решение 9 (ссылка `<id>` на каталог версии) → починка doctor удаляет и ссылку, и её каталог версии (логическое следствие).

## Не сработало
- `cd … && python3 …` отклонён песочницей (simple_expansion); guard запускать без `cd`.

## Где остановился
- SPEC.md переписан, status: ready, guard ок.

## Чего не хватило
- Имени «метки пульта» в решении 4 — нашёл в SPEC части 1 (`git show refs/artifacts/<id>:tasks/<id>/SPEC.md`).
