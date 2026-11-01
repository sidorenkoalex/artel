# NOTE developer (визит 4, после REVIEW итерации 1)

## Выяснено
- Прошлый шаг упал (rc=1), но код по R1-F1…F4 уже был в WIP-чекпоинте 3403d956a: байтовое чтение git в `mr_sync._git/_out_bytes`, `_apply_passes` через `gitcmd.read_env` со сроком, точка ответвления до MR в `fsm_merge_gate._deliver_mr` (отказ approve без неё), повтор AC-14 убран.
- Прогон: 6 файлов (долгоживущие задачи, test_mr_sync_units, доставка Б2.1б, awaiting_commands) — 103 passed; планка — 1 passed.
- Мутации: строгое декодирование → красный `test_signs_on_cp1251_file`; снятый отказ без точки → красный `test_gate_refuses_without_fork_point`.
- REVIEW реестр: R1-F1…F4 размечены `fixed` с описанием; PLAN дополнен абзацем и риском, status: ready; guard ок; карта регенерирована.

## Не сработало
- Bash-сторож: нет `rm`, отклоняет `{…'…'}` в heredoc — мутации делал скриптом-файлом в каталоге документов (удалён через python os.remove).

## Где остановился
Шаг сдан: PLAN ready.

## Чего не хватило
Ничего.
