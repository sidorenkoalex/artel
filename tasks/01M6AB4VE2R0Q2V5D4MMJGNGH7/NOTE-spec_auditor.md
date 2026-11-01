# NOTE spec_auditor

## Выяснено
- Факты SPEC о коде в основном верны (fsm.py:43, config.py:942, forge.MergeRequest, gitlab_adapter.py:497/545, schema.py:244, fsm_merge_gate.py:1337/1367/1549-1552/1576, cleanup.py:718/736, snapshot.py:96, retro.py:551/571, gitcmd.py:233, targets.py:559).
- config.py (подсказка :942) — не в zones SPEC, а требование 6 её меняет.
- Подтверждённая голова — `fsm_merge_gate._confirmed_code_head` (поле `код=` записи фиксации), а не sha approve; SPEC называет «sha approve».
- `gitcmd.diff_base` после вливания merge-коммитом = голова задачи: «точка ответвления» SPEC не определена.
- Инцидент «чужой коммит» по `last_sent_sha`: ветку на сервере GitLab может удалить/переписать (rebase) при вливании — SPEC не говорит, что тогда.
- ANSWER-файлов нет; мандат на правку HINT отсутствует.

- Путь --confirm теряет сверку refs/artifacts с origin (fsm_merge_gate.py:1596, cleanup.py:700-715) — в матрице нет.
- Свип commands() test_invariants идёт на песочнице artel (operator) — mr-sync там пусто отказывает.

## Не сработало
- Составные bash-команды с `cd`/переменными требуют подтверждения — только одиночные grep/find по абсолютным путям.

## Где остановился
SPEC-AUDIT.md написан (verdict: concerns, status: ready), guard ок. Шаг завершён.

## Чего не хватило
Где живёт механика «эскалация из awaiting_human возвращается туда же» — нашлась в тесте awaiting_commands.py:144 (escalated_from + approve), не в answer.py.
