# Записка developer, итерация 2

## Выяснено
- R1-F1 закрыт: tests/test_role_nproc_step.py (7 тестов, песочница DeveloperBriefTmpRootTest как в test_agent_log::CmdRunLoggingTest + ARTEL_ROLE_ENV="" и восстановление SIGTERM как в планке _step.py). Снятие группы проверено подменой liveness.terminate_process_group и FakeProc с целым pid.
- Семь временных мутаций runner.py (>=→>, передача из _run_attempts, failed→!=ok, нет предупреждения, leftover=0, if True, неловимое исключение счёта) — каждая красит тест; код восстановлен.
- R1-F2 размечен rejected: SPEC требует, чтобы шаг и doctor звали саму role_nproc_limit().
- Карта регенерирована; затронутые тесты — 104 passed; claims/lint нового файла чисты.

## Не сработало
- Bash: heredoc python с f-строкой отклоняется («brace with quote») — сценарий мутаций пришлось писать файлом и убирать task-rm.

## Где остановился
- Готово: тесты, REVIEW-реестр размечен, PLAN.md status: ready.

## Чего не хватило
- Ничего существенного.
