## Выяснено
- Планка: acceptance_tests/test_origin_push_checks.py (AC-1–AC-10, разовый) и test_ac11_plan_call_counts.py (AC-11, PLAN через `_pult.artifact_text`).
- AC-1–AC-10 сделаны разовыми: статика долгоживущего файла (`scripts/guard.py::_GIT_MODULES`, признак «git-модуль») запрещает импорт `orchestrator.artifact_branch`/`gitcmd`, а AC-1/AC-2 называют закрытый `_send`. Файл требования 3 (`tests/test_01m5qr7kgyznvwdp5h86s9py04_origin_push_checks.py`) test_author НЕ создавал — это файл разработчика; если на него ляжет статика долгоживущего, тот же импорт будет отклонён.
- Шпион — `mock.patch.object(subprocess, "run")`, подкоманда сквозь `-C` (`tests.sandbox.strip_dash_c`).
- Красные до кода: AC-1, AC-4, AC-6, AC-11; остальные зелёные (прежнее поведение).
- Стаб (`_attempt_push(..., origin_checked=False)`, сверка → досылка при `local and local != remote` → пересверка): 10/10 зелёные; мутации AC-3 (признак по умолчанию True) и AC-10 (без проверки `local`) краснят свои тесты. Стаб откачен.

## Не сработало
- `ls`/`cat`/`sed -i` в Bash недоступны или требуют подтверждения — Read/Edit.

## Где остановился
- Планка готова, прогон plank-run и предпроверка — в конце шага.

## Чего не хватило
- Конфликт требования 3 SPEC (долгоживущий файл) с запретом guard на импорт artifact_branch в долгоживущих файлах — не отражён в SPEC.
