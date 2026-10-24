# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтвердились: `read_tree` artifact_branch.py:654, `_head` :132, `_git` :126, `carpentry` gitcmd.py:339 (ловит OSError → rc 1), `show` :611 (ловит UnicodeDecodeError), `ls_tree_files` :761, `branch_head_sha` :582, `suite_tree_hash` acceptance.py:2905 (второй rev-parse :2924), sandbox.py :821/:850/:1268/:1284/:1418, `Ac5ProofMismatchTest` в test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:611.
- Кодировка текстового режима subprocess = `io.TextIOWrapper(io.BytesIO()).encoding` (UTF-8 strict на 3.13.12), `_translate_newlines` — тот же replace.
- Объединённый rev-parse на git 2.50.1 даёт 2 строки и в linked worktree, и в подкаталоге; вне git — rc 128.
- SpyRun и fake_git отказывают `rev-parse --verify refs/artifacts/*` → `_head` пуст → прежний путь в лёгких песочницах.
- `reference_cache._cat_blobs` зовёт subprocess.run напрямую (обход carpentry возможен через импорт).
- Внутренний `git()` в suite_tree_hash — subprocess.Popen, счётчик по subprocess.run его не видит.
- Карта включает секции tests/* и «Импортируется»: регенерация меняет больше строк, чем «только новые помощники».

## Не сработало
- `cd … &&` и `$VAR` в Bash требуют одобрения; абсолютные пути работают.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- —
