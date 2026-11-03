# NOTE-reviewer (итерация 2)

## Выяснено
- Итерация 2: diff — только tests/test_push_hook_stand.py (новый) и +2 метода в tests/test_push_hook_units.py; код не менялся.
- 32 passed (два файла задачи); 98 passed вместе с test_git_hooks/hosting_token_units/gitcmd_push_point; ac9 — 16 passed; plank-run — 68 passed.
- Временные мутации (gitcmd.py:1126, GIT_TRANSPORT_ENV_NAMES, PUSH_REDIRECT_CONFIG, бит исполнения в doctor, submodule мимо gitcmd, pre-push:85) — все красные; код возвращён, дерево чистое.
- R1-F1 → accepted. Вердикт approved.

## Не сработало
- `sed -i` и цепочки команд требуют подтверждения — мутации делать инструментом Edit, откат `git checkout --`.

## Где остановился
- REVIEW.md записан (iteration 2, approved).

## Чего не хватило
- Номера строк кода для мутаций брал из прошлого REVIEW: в пакете итерации 2 кода нет.
