# NOTE spec_auditor

## Выяснено
- Факты SPEC о коде подтверждены: projects.py:379-380 BLOCK_PATHS, :655-670 _block_keys (два вида), :617-652 _target_set_block, :900-927 сверка, :960-983 _merge_mismatches ловит TargetsError merge_local до копии (:500-502 выход до _backup_copy :504).
- targets.py:715-720 проверка commit_author, :668 текст «поле 'machine.commit_author' — нужно {name, email} — обе непустые строки»; machine — обязательный раздел (targets.py:408, required forge/url/token_slot), holder всегда есть.
- gitcmd.commit_author — gitcmd.py:559-564 (SPEC пишет 567-582 — там pult_identity/pult_identity_args).
- tests/test_01m6qz4rr80b...block.py: 37 passed на ветке; ac4 (:391-421) проверяет вхождение PATHS_LITERAL — дописывание в конец его не ломает; machine.submodule_tokens там остаётся отказом.
- Других тестов --from-file/_block_keys в tests/ нет.

## Не сработало
- grep с cd в составной команде — отказ песочницы; абсолютные пути работают.

## Где остановился
- Вердикт concerns (мелкие: адрес gitcmd, budget 25 > рамки 20, AC-3 только подстрока). Записан SPEC-AUDIT.md.

## Чего не хватило
- Нет.
