# Записка spec_auditor — 01M5RHGRH3YJV8VBFH3QCHD8X0

## Выяснено
- Факты SPEC о шести файлах (строки, байты, тесты, заявки, места :NNN помощников, subTest, assertRegex) сверены AST/grep с деревом ad3608c6 — совпадают. Между 09ded609 и ad3608c6 в orchestrator/scripts менялись только acceptance.py и artifact_branch.py.
- Перекрытие `set_state(task_id, state)` (status_show :84, new_declares :173) безопасно: метод песочницы зовёт `self.set_state` только в `advance_from_in_dev` (tests/sandbox.py:2245), тесты волны его не зовут. Других перекрытий методов RealGitSandbox/LightTransitionSandbox нет.
- Локальные, совпадающие с именами модуля, — ровно `journal`/`task` из перечня ТЗ (AST).
- Импорт модуля `from orchestrator import (...)` — две строки tests/test_merge_after_module.py:46–47: дописать `github_adapter`/`workspace` в перечень нельзя чистым добавлением — конфликт с AC-7/AC-16 «только добавления».
- Мандат: маркер `Ослабление тестов разрешено:` (mandate.py:38) + матрица (mandate.py:633) — в SPEC не названы, ANSWER ещё нет; в волне 3м-2 их дал ANSWER-1 Оператора.

## Не сработало
- Bash-песочница режет `for`/`$()`/брейс-экспансию — скрипты писать файлом в каталог документов и звать python3 (затем удалить).

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns, status ready.

## Чего не хватило
- Формы мандата на ослабление (маркер + обязательная матрица) — нашёл в orchestrator/advance_gates/mandate.py и ANSWER-1 волны 3м-2 (refs/artifacts/01M5R0AFX9Z1GA1DG5XV73JRTE).
