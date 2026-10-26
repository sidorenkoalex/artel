# Записка developer

## Выяснено
- Зависимости (часть 1, А1.1) уже в ветке. Реализация: подпись коммита пульта и сверка автора — gitcmd.py (pult_message/pult_identity_args/journal_pult_commit/_author_check_refusal в _push_plan); сжатие/перебазирование — pull.prepare_branch/restore_branch; порядок перехода — fsm_advance.in_dev; перезапись — tests_writing._rewrite_push_gate; ревью — review.py (REWRITTEN_MARK).
- Тест AC-1 ищет «ветка отправлена: <sha>» в `action + " " + detail` → действие стало "ветка отправлена:" (PUSH_SENT_ACTION), старое читается как PUSH_SENT_LEGACY_ACTION.
- При rebase стадии индекса обращены (:2: — main, :3: — ветка) — _union_merged_text(rebase=True).
- Долгоживущие тесты: 65 passed; затронутые модули: 1066 + 582 passed.

## Не сработало
- `pytest -n 8` на этих файлах — воркеры падают; длинный heredoc в Bash — «Parser aborted»; `$(…)`, `${…}` в Bash отказаны.
- targets.local_path без weakening_scope/mutation_claim_scope в записи с test_profile не грузится (TargetsError) — проверки «без поля» проходили бы впустую.

## Где остановился
- Всё сделано, PLAN.md status: ready, карта регенерирована.

## Чего не хватило
- SPEC «коммит закрытия snapshot.py:272» — на деле _history_commit; закрытие — commit_closing → artifact_branch._write.
