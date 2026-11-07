# Записка developer

## Выяснено
- Реализация: `targets.COMMIT_TRAILER` (regex `[A-Za-z0-9-]+: …\S…` без перевода строки), поле в `LOCAL_FIELDS.policy` и `DELIVERY_POLICY_FIELDS`, проверка в `_check_delivery` после `co_author`; `gitcmd.pult_message` берёт `entry.get("commit_trailer", PULT_ACTOR_TRAILER)`, пустые строки — без абзаца.
- Планка 8/8; долгоживущий + signature + entry_checks + targets_field + template_field + role_author + rewrite_flow — 114 passed (rewrite_flow долгий, ~6 минут).
- Карта регенерирована.

## Не сработало
- —

## Где остановился
- PLAN status: ready, guard ок. Шаг сдан.

## Чего не хватило
- —
