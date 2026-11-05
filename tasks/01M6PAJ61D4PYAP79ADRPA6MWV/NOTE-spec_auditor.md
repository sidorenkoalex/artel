# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Якоря acceptance.py (_own :121, _OWN_SYSTEM_PATH_DIRS :156, _report_run :806, _report_suite_result_key :3069) совпадают.
- suite_run (только чтение) берёт профиль при `report` — compose пройдёт через acceptance.reported; mutation_run отказывает любому не pult-pytest — согласовано с «не входит».
- test_integrity._own_profile (:1651) — compose без правки ушёл бы раннером пульта; зона есть.
- _check_profile (targets.py:1096-1103): после сведения machine.path лежит в env → правило PROFILE_OWN_RUNNER_ONLY нужно расширить на compose.

- repo_context.profile_of (:183-188, вне зон) отказывает единственному компоненту без `command` — умолчание `["pytest"]` для compose без канала в зонах (targets.load?) не названо.
- Перенос требований 1–11/16/17 и AC из SPEC родителя сверен difflib: дословно, убраны только части 2.
- Пробелы: нет поведения при зависании/провале `config`; нет AC на отсутствие обязательных compose_*; обход сокета через именованный том driver_opts bind и secrets/configs file:; сокет из контекста Docker без DOCKER_HOST не сверяется; «снятие группы» без AC и канала.
- docker в окружении роли нет — опытом Compose не проверить.

## Не сработало
- ls/echo в Bash отклоняются; пользуюсь grep/sed/Read.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Шесть пунктов вердикта (канал умолчания command, исход config, обход правила сокета, AC-2 без обязательности compose_*, «снятие группы» без AC, мелкое).

## Чего не хватило
- Docker в окружении шага — нет, поэтому утверждения о выводе `config --format json` опытом не проверены. Дольше всего искал, где читается обязательность `command` у единственного компонента: repo_context.profile_of :183.
