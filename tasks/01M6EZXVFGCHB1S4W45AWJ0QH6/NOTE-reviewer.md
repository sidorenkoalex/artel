# NOTE-reviewer (итерация 1)

## Выяснено
- plank-run: 68 passed; tests/test_push_hook_units.py + test_git_hooks + test_hosting_token_units + test_gitcmd_push_point — 76 passed.
- Все 4 файла планки помечены «Группа: разовый». В tests/ нет сторожей для: строки doctor clone-push-hook, `-c core.hooksPath` в _push_plan, отказов по GIT_SSH_COMMAND/GIT_CONFIG_GLOBAL/SYSTEM, remote.origin.url, insteadOf/sshCommand, ensure_clone (hooksPath + политика), pre-commit target-human, клона и подмодулей с токеном, отказов хука на tags/notes.
- Временная мутация gitcmd.py:1126 (`if False and …`) выжила в tests/ (131 passed); код возвращён.
- Функциональных дефектов по SPEC не найдено. gitcmd.read по умолчанию отдаёт байты, поэтому sha256 в doctor считается верно. Правка url в MR-стендах ничего не сужает: строки grp%2F — тексты отказа поддельного forge.
- Вердикт: changes_requested, одно замечание R1-F1 (major).

## Не сработало
- Bash-команды с `cd` и цепочками через `;` требуют подтверждения — вызывать по одной, с абсолютными путями.

## Где остановился
- REVIEW.md записан (iteration 1, changes_requested).

## Чего не хватило
- Как планка помечает группы: проверил grep "Группа:" по acceptance_tests.
