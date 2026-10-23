# NOTE reviewer — итерация 1

## Выяснено
- Планка `plank-run` — 15 passed; затронутые модули tests/ (server_retry, artifact_branch_push, artifact_ref_sync, sleep_guard) — 33 passed.
- Вся планка помечена `Группа: разовый` (guard запрещает git-модули в долгоживущих файлах) → после мержа сторож только `tests/test_artifact_branch_server_retry.py`.
- Временная мутация (5 сразу: снять `_last_send_failed` из `_send`; формат отказа «сервер» с советом merge; убрать `http 5\d\d`/`returned error: 5\d\d`; убрать `fatal error in commit_refs`; пауза 1 вместо константы) — tests/ (3 модуля) остались зелёными, 29 passed. Код возвращён `git checkout`.
- Карта `docs/codebase-map.md` свежая (расхождение только в built_at_sha).
- `send_pending` в orchestrator/ — 0 вхождений.

## Не сработало
- Составные Bash-команды с `cd`/переменными требуют подтверждения; `ls`/`cat` недоступны — использовать `find`, `grep`, Read.

## Где остановился
- Вердикт changes_requested: R1-F1 major (нет долгоживущих тестов в tests/ на треб. 1 (5xx, commit_refs, порядок (а)>(б)), 2 (аргумент паузы), 3, 4); R1-F2 minor (пробел `last =store.`).

## Чего не хватило
- Нет быстрого способа узнать, что вся планка разовая, кроме grep `Группа` по acceptance_tests.
