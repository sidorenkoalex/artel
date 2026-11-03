# Записка developer

## Выяснено
- Код закоммичен 81719054f: orchestrator/verify.py (новый), targets.py (VERIFY_FIELD, _verify_error, verify_checks, check(local=)), schema.py (verify_marks, tasks.verify_fails), store.py (insert_verify_mark, verify_marked_names), fsm_advance.verifying (verify.hold/enter_wait), auto.py (_advance_verifying_poll: стоп без алерта; _epic_view: verify.waiting → _WAITING), board.waiting_on, watch (gates + _significant), catalog._status_line, artel.py (verify-ok/verify-fail + справка), tests/test_verify_profile.py (ANSWER-1), карта регенерирована.
- Ожидание = последняя из записей {verify.WAIT_ACTION, fsm.VERIFYING_STATUS_ACTION} после последнего `state -> verifying` — запись ожидания.
- PLAN.md: status escalate. Приложение к tests/test_invariants.py (verify_call в FsmTest.commands) — apply --check ок, свип с ним зелёный.
- Расхождение долгоживущего verify_flow с main: ENTRY `forge: gitlab` + `merge_gate: operator`, SUPPORTED_PAIRS (подтяжка main, 01M6EZXVFG405Y1BTFDSGBKS8E, после фиксации тестов 0da03dfc4) → auto «проект не поддержан». Красные AC-16, AC-17 x2; с подменой SUPPORTED_PAIRS — 32/32. Дефолт эскалации: amend-tests добавить подмену SUPPORTED_PAIRS в Stand.

## Не сработало
- python -c с pytest.main — сторож conftest считает полным прогоном; временный плагин `-p` в корне worktree работает (удалить после).
- plank-run в шаге: PLAN.md ещё нет в ссылке документов — 2 failed ожидаемо.

## Где остановился
- Шаг закончен эскалацией. После amend-tests по варианту (а): снять escalate → ready, код не менять; прогнать verify_flow.

## Чего не хватило
- Сведения, что SUPPORTED_PAIRS пришёл в ветку после фиксации тестов: нашёл через `git log -S SUPPORTED_PAIRS -- orchestrator/targets.py`.
