# Записка reviewer, итерация 1

## Выяснено
- Планка 27 passed; tests/test_role_nproc_limit.py + долгоживущий + test_doctor — 124 passed; карта свежа.
- Код по SPEC корректен: отказ внутри try/finally `_cmd_run`, снятие группы в `else` у `proc.wait` до `close_pump`, preexec только setrlimit.
- Временная мутация (снят отказ N≥M, снято снятие группы на обычном исходе, `_run_attempts` не передаёт nproc_limit) — tests/ (role_nproc_limit, долгоживущий, agent_log, liveness, auto_cycle) остаются зелёными: 130 passed. Эти свойства сторожит только разовая планка → R1-F1 major.
- Minor: `_read_maxprocperuid` зовётся дважды на шаг и в doctor (R1-F2).

## Где остановился
- Вердикт changes_requested, REVIEW.md записан.

## Чего не хватило
- Ничего существенного.
