# Записка analyst

## Выяснено
- Второй возврат со spec_gate (5 решений) закрыт правкой SPEC.md:
  - треб. 3: новый параметр `sandbox_sources` (путь → текст tests/sandbox.py, tests/*_sandbox.py дерева проверки; None → config.ROOT); правила размера только на путях долгоживущих файлов tests_writing:643, amend:317, amend:725, preflight:213; пути планки 518/198/293 получают флаги, правил не исполняют; lint_base — на amend:317 тем же механизмом, что :725;
  - треб. 2: межфайловые цепочки и независимость от порядка словаря; «несколько меток размера»; `pytestmark: list = [...]`;
  - AC-2/AC-5/AC-6/AC-7/AC-9 дополнены; «Не входит» — обходы статики (`_sandbox(...)`, isolate_pult_db/init_bare_origin/make_project_repo, `-m orchestrator.artel`).
- Сверено: guard.py:4425-4431 (параметров sandbox нет), merge_outcome_sandbox.py:61, amend.py:293/317 без lint_base, :725 с ним. Строки решения 3 sandbox.py:720/1160/1246 — это isolate_pult_db(:718)/init_bare_origin/make_project_repo, не `_sandbox`; в SPEC указаны имена функций.
- AC по-прежнему 9, budget 55; guard — ок, status: ready.

## Не сработало
- Bash с `$?` отклоняется («simple_expansion»).

## Где остановился
- Готово.

## Чего не хватило
- Ничего существенного.
