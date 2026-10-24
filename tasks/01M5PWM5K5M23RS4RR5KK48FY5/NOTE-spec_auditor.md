# Записка spec_auditor

## Выяснено
- Факты SPEC о файлах сверены на 921869bf (orchestrator/ и tests/ с a426605f не менялись): размеры, строки 47–899, 27 имён (вычислено по AST — совпадает), 3 расходящихся имени (GATE_ACTIONS, VITEST_KIND, spec_text — прочие общие имена совпадают по ast.dump), collect-only 122 и 11.
- guard видит базовый класс из другого модуля tests/ через TestModules стороны (scripts/guard.py:1841-1848, 1870-1888; test_integrity.py:783-784) — перенос песочницы гейту не мешает.
- Ветка кода пушится только на in_dev -> verifying (_origin_push_gate) — итог CI в PLAN к ready недостижим (AC-7).
- mutation_run: бюджет 1500 с на всю команду; исходы кроме CUT (NOT_RUN, UNKNOWN, NOT_APPLIED, TOUCHES) SPEC не разбирает.
- Вердикт: concerns, 8 пунктов.

## Не сработало
- `ls` в оболочке шага нет (PATH); пользовался python3/git.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Как pytest пишет в junit провал setUp у unittest.TestCase (failure или error) — от этого зависит, увидит ли mutation-run «убийство подготовкой»; проверял по памяти.
