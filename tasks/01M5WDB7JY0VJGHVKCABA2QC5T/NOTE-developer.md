# Записка developer

## Выяснено
- Зависимости (часть 1, А1.1) в ветке. Реализация: подпись коммита пульта и сверка автора — gitcmd.py (pult_message/pult_identity_args/journal_pult_commit/_author_check_refusal в _push_plan); сжатие/перебазирование — pull.prepare_branch/restore_branch; порядок перехода — fsm_advance.in_dev; перезапись — tests_writing._rewrite_push_gate; ревью — review.py (REWRITTEN_MARK).
- Возврат из verifying (CI 40404731283): сторож А0 tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac9_no_support_literals_outside_targets запрещает в orchestrator/ (кроме targets.py) сравнение значения forge с литералом хостинга. Исправлено: gitcmd._token_user_unimplemented — пропуск сверки только если ответ == «token_user: не реализовано для <forge.hosting>» и у forge.IMPLEMENTATIONS[хостинг] нет token_user. Подменённый ответ «не реализовано для gitlab» (у gitlab функция есть) — отказ.
- Проверено: сторож А0 + долгоживущие тесты задачи + test_pult_commit_signature — 84 passed; мутация (без проверки реестра) краснит test_ac12_author_check_on_transition[не реализовано].
- Тест AC-1 ищет «ветка отправлена: <sha>» → действие "ветка отправлена:" (PUSH_SENT_ACTION), старое читается как PUSH_SENT_LEGACY_ACTION.

## Не сработало
- `pytest -n 8` на этих файлах — воркеры падают; длинный heredoc в Bash — «Parser aborted».

## Где остановился
- Причина возврата закрыта, карта регенерирована, PLAN.md status: ready.

## Чего не хватило
- Прошлый шаг не знал о стороже А0 на литералы хостинга — его стоит прогонять при любом ветвлении по forge.
