## Выяснено
- Места кода в SPEC (artifact_branch.py :367/:378/:425/:442/:451/:458/:461/:477–494) верны на 9c0e8b8c.
- `Ac5PassToPassTest` нет в tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py (там Ac5ProofMismatchTest :611); одноимённый класс — tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py:616.
- `gitcmd.has_no_remote` зовёт `gitcmd.in_repo` напрямую (gitcmd.py:573), не через `artifact_branch._git` — шпион только на `_git` её не видит.
- Нет AC на «ссылки нет в origin, досылка удалась → None».
- Вердикт: concerns, 6 пунктов в SPEC-AUDIT.md; guard ок.

## Не сработало
- grep с `--include=*.py` в zsh без кавычек падает (no matches found).

## Где остановился
- SPEC-AUDIT.md сдан со status: ready.

## Чего не хватило
- Ничего существенного; дольше всего искал реальный адрес Ac5PassToPassTest.
