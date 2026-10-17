# Записка test_author

## Выяснено
- Публичные входы: задание — `role_prompt.mission_brief_package(conn, id, t, role, cwd)` (брифы `brief.*` подменены пустыми); чекпоинт — `checkpoint.commit_success_checkpoint(conn, id, "test_author")`; проверка артефакта — `runner.run_agent_once` с подменой `runner.spawn_agent`.
- Отказ профиля (`Decision.refusal`) в тестах — артель без `test_profile` в targets.yaml; пропуск (`Decision.skip`) — внешний проект без него.
- «git не ответил» на чекпоинте — порча индекса рабочей копии (`rev-parse --git-path index`), без подмен (литерал gitcmd в долгоживущем файле запрещён).
- Стаб проверен и откачен (`git checkout` трёх модулей): `_missing_required_artifact` в стабе получал `conn` новым kwarg — тесты устройство не навязывают, ходят через `run_agent_once`.
- Зонный фильтр (AC-4): стаб без своей зоны краснит AC-4 — мутация ловится.

## Не сработало
- Составные Bash-команды (`;`, `|` с grep) и `ls` требуют подтверждения.

## Где остановился
- Готово: tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_{mission,checkpoint,required_artifact}.py (долгоживущие, AC-1..AC-7), acceptance_tests/test_ac8_skill_patch_text.py (разовый, зелёный). preflight — все проверки пройдены; plank-run — 1 passed.

## Чего не хватило
- Как получить refusal у внешнего проекта без поломки всего targets.yaml — нет; взял артель без профиля.
