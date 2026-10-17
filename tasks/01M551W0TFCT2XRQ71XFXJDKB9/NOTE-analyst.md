# Записка analyst

## Выяснено
- ANSWER-1: вариант A — runner.py (только _missing_required_artifact/_has_own_long_lived_test, :1310-1346) в зонах, потолок прежний $25.
- Возврат со spec_gate 17.10: Ф-1 (б) — своя зона test_author в зонном фильтре коммита (checkpoint.py:424-425 → _zone_paths :1550, _stray_staged_paths :1731) по long_lived_dir + префикс задачи, COMMON_ZONES не трогать; Ф-2 — refusal: не коммитить/не засчитывать + журнал, задание без каталога; skip: без умолчаний артели, отбор пуст; П-1 — AC-3/AC-5 расширены.
- Места без профиля: role_prompt.py:36, :78-80, :94, :114; checkpoint.py:376, :384, :412, :497; runner.py:1317-1319, :1338, :1340, :1345.
- Источник профиля — project_profile.for_task(conn, task_id) → Decision (project_profile.py:121-163).

## Не сработало
- Первый прогон guard (прошлый шаг): сигналы объёма — закрыто секцией «Оценка объёма» (монолит, прогноз диффа).

## Где остановился
- SPEC.md переписан под решения 17.10: 8 требований, 8 AC (AC-4 — зоны вне backend/tests, AC-6 refusal, AC-7 skip), status: ready, guard ок, budget 25.

## Чего не хватило
- Связь чекпоинта test_author с зонным фильтром видна только чтением _commit_worktree_change (checkpoint.py).
