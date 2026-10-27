# Записка spec_auditor — 01M5XXA2HY73D3WTXDR19Z5SWW (аудит №2, SPEC b735cef)

## Выяснено
- Решения Оператора 1–14 в SPEC отражены; адреса строк SPEC сверены — верны.
- Б1-тест tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169 держит mr_assignee "alice" как допустимое — правило «только цифры» (треб. 1) его ломает, в мандате треб. 11 его нет.
- yamlmini.py:59-60: `mr_assignee: 42` без кавычек → int → нынешняя проверка targets.py:650 отказывает.
- 409 в forge не различим структурно: forge.MergeRequest (forge.py:67-74) без кода, только reason-текст gitlab_adapter.py:209.
- AC-26: для target-human (белый список) `push --delete` ветки уже отказывает gitcmd.py:675-679 до subprocess; для GitLab PR и так не закрывается (cleanup.py:303) → AC-26 проходит на неизменном коде при шпионе на subprocess.
- Не классифицированы шаги гейта для target-human: _refuse_during_canary (fsm_merge_gate.py:1541), мьютекс merge-окна (:1581+), публикация головы (:1513) не в списке «исполняются».
- max_in_flight: обходы — ensure_draft_mr пушит на входе in_dev для GitHub (github_adapter.py:167), amend-tests в in_dev (amend.py:834), путь сжатия _rewrite_push_gate (tests_writing.py:67).

## Не сработало
- Bash с `cd …;`/составные grep — отказ песочницы; простые команды из cwd.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns, 8 пунктов вердикта; guard — ок.

## Чего не хватило
- Перечня «точки первой отправки ветки задачи» — искал грепом ensure_head_in_origin/in_repo push.
