# Записка spec_auditor — 01M5KJNE39PHV9EAWJCHK7QDFS (круг 2, spec_sha 5a5f5a00)

## Выяснено
- Код между 89732e3e и HEAD по всем адресам SPEC не менялся (git diff --stat пуст) — факты круга 1 в силе.
- Решения Оператора 1–8 перенесены в SPEC полностью; адреса runner.py:907/:929/:945/:1021/:1091–1106, guard.py:3767/:3849 верны.
- runner.role_env() вне песочницы: реальный keychain (providers/claude.py:226–230 → runner.role_token), mkdir config.ROLE_CONFIG_DIR (claude.py:221), реальный stack.check_stack (runner.py:1013) → OSError «venv не готов» (:1017) — тоже OSError, SPEC пропускает любой OSError → AC-8 может молча пропускаться всегда. Изоляция есть в TmpRootTest: sandbox.py:1619 (keychain/ROLE_HOME), :1643 (check_stack).
- Подмена shutil.which в модульных случаях: SPEC не требует, чтобы подмена зависела от/сверяла `path=`; мутация `shutil.which("git")` без path проходит.

## Не сработало
- `ls` в Bash не найден (PATH шага без /bin) — пользуйся Read/grep.

## Где остановился
- SPEC-AUDIT.md: status ready, verdict concerns (2 пункта: изоляция/пропуск AC-8; подмена which без сверки path).

## Чего не хватило
- Побочные эффекты role_env: providers/claude.py:199–231 и изоляция sandbox.py:663 — искал дольше всего.
