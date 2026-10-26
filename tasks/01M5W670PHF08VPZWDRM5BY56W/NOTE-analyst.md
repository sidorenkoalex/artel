# Записка analyst

## Выяснено
- ANSWER-1: 1A, 2A, 3A, 4A (часть 1 $50, часть 2 $25, зона doctor/__init__.py в часть 2), 5A, 6A, 7A, 8A, 9A, 10A, 11A, 12B (`gitlab_adapter.TOKEN_NO_EXPIRY_TASKS_WARN = 10`), 13A.
- Контракты текстов `ci` (ci.py): `verifying_is_red` — подстрока «не зелёный:» (:1084); `red_status_sha` — «CI коммита <sha> не зелёный» (:1097); `status_kind` — «ещё идёт» → running, «неизвестен» → unknown, иначе red (:1267-1271); `rerun_started` — «не запущен» (:1694); `MAIN_UNKNOWN = "unknown"` (:1282).
- Факты А0 — в origin/main (5705cfd), рабочий каталог позади.

## Не сработало
- Составные Bash-команды и `ls` недоступны — пользуйся Read/grep.

## Где остановился
- SPEC.md переписан по ANSWER-1 (18 AC, деление: часть 1 AC-1…15 $50, часть 2 AC-12/16–18 $25, зона doctor/__init__.py добавлена в родителя и часть 2), status: ready, guard — ок. QUESTIONS.md удалён.
- Тест А0 и test_doctor.py:670 остаются без правки: там токена нет (keychain подменён кодом 127 / нет token_slot) → skip.

## Чего не хватило
- В шаге нет `ls`/`rm` (command not found) — удаление файла сделано через `python3 -c "os.remove(...)"`.
