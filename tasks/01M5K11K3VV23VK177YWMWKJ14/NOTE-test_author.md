# Записка test_author — 01M5K11K3VV23VK177YWMWKJ14

## Выяснено
- Прошлая попытка сдала шаг без тестов (отказ трассируемости AC-1..AC-17); этот шаг написал планку заново.
- Долгоживущий файл: tests/test_01m5k11k3vv23vk177ywmwkj14_kill_reason.py — AC-1..AC-17 сквозь `artel.main` в песочнице `TmpRepoTest` (tests/test_kill_cleanup.py), без подмен уборки. Живой цикл — lease на pid дочернего процесса `sleep` на `in_dev` (не os.getpid(): ошибочный kill с SIGKILL снял бы сам pytest).
- Разовый: acceptance_tests/test_ac16_existing_dispatch_tests_untouched.py — tests/test_kill_live_cycle_refusal.py не в changed_paths().
- Тесты ждут отказы по причине как SystemExit, текст ищется в stdout+stderr+тексте выхода; подсказку — отдельной строкой вывода.
- Стаб (reason в cmd_kill/_cmd_kill, return won, `_reason_arg` + условный kwarg в диспетчере, подсказка в диспетчере, строка справки) — 17/17 зелёные; стаб откачен.
- До реализации: 14 красны по верной причине, AC-4/5/14/15 зелены (держат прежнее поведение).

## Не сработало
- `ls`/`cat` в Bash нет — пользоваться python3/Read.

## Где остановился
- preflight пройдена целиком, plank-run зелёный (1 passed). Шаг завершён.

## Чего не хватило
- Ничего существенного; карту docs/codebase-map.md не регенерировал — правка вне tests/ откатилась бы пультом (это сделает разработчик).
