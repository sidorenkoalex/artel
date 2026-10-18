## Выяснено
- ТЗ достаточно — пишу SPEC без батча.
- sled сегодня — `test_profile` с `runner: pytest-own`, `workdir: backend` (uv.lock отслеживается): ключ идёт через `acceptance._own_suite_result_key` (acceptance.py:2150). Требование 4 ТЗ требует прежний ключ и у sled → новый элемент ключа (файлы блокировки + tools) только у профиля из записи с `components:`; у `test_profile` — байт в байт прежний.
- Вызовы `suite_result_key`: acceptance.py:2269 (рабочее дерево), :2319 (база), suite_run.py:523 (база, вне зоны) — корня рабочей копии нет ни у одного.
- `depends_on` — `via` ∈ paths|files|contract (targets.py:108); в сверку paths_source идут только paths/files.
- `tests/` — общая зона (config.COMMON_ZONES) → 4 файла зоны, сигналов деления нет при ≤9 AC и бюджете < 60.

## Не сработало
- Bash с `cd …; sed` и цепочками команд требует подтверждения — читать через Read/одиночный grep с абсолютным путём.

## Где остановился
- SPEC написан (9 AC, budget 30, status ready), guard ок. Guard считает `tests/` в сигнале «файлов зоны ≥5» — пришлось дать секцию «Оценка объёма» (обоснование монолита + прогноз диффа 60 КиБ).

## Чего не хватило
- Как профиль одного компонента получает поле tools (repo_context.profile_of берёт только PROFILE_FIELDS) — решает разработчик.
