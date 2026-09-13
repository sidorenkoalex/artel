# AC-7: manual — две половины критерия, обе вне досягаемости теста этой
# планки. «status/report не изменены этой задачей» — факт диффа
# разработчика; zones SPEC (orchestrator/runner.py, orchestrator/roles.py,
# tests/) уже не включают status.py/report.py, и существующий зонный гейт
# (tests/test_zones_gate.py, tests/test_protected_paths_gate.py — не
# переписываются здесь) отбивает правку туда структурно, ревьювер сверяет
# диффом на приёмке. «Канарейка не ломается отсутствием поля model» —
# канарейка (`orchestrator/canary.py`) не содержит ветвления по role/model
# (grep подтверждает) и зовёт тот же `runner.cmd_run`/`role_cmd`, что уже
# напрямую покрыт test_ac3_ac4_command_flag.py::test_ac4_no_model_flag_
# when_the_field_is_absent и test_ac4_missing_model_warns_exactly_once_
# without_failing_the_step (роль без `model` не останавливает и не
# проваливает шаг); отдельный тест тяжёлой песочницей канарейки
# (tests/test_canary.py, не переписывается здесь) повторил бы ту же
# проверку без нового сигнала — регрессию ловит штатный прогон этого
# файла в CI.

# AC-9: manual — критерий про unified diff в PLAN.md, которого на шаге
# test_author ещё физически нет: PLAN.md — артефакт роли developer,
# `roles.yaml` — защищённый путь, который правит только Оператор.
# Тестировать нечего до появления файла; `git apply --check` самого
# диффа — обязанность разработчика перед сдачей (skills/
# conventions-core.md) и ревьювера на приёмке, не предмет для планки,
# написанной раньше кода.
