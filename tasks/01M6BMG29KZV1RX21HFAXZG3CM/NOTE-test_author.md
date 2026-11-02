# Записка test_author

## Выяснено
- Долгоживущий файл: tests/test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py — AC-1..13, AC-15 (local), AC-16..19; 45 сценариев, ~110 с. Стенд VerifyingBox поверх MergeOutcomeSandbox, хостинг ScenarioForge (вердикт GREEN принудительно — поле green; сбои чтения статуса/отчёта, перезапуск задания, исключение).
- На текущем коде: 39 красных (на in_dev ci судится выписками; на verifying гейта нет), 6 зелёных — методы, держащие прежнее поведение (local, both локально, гейт мержа при перезапуске).
- Разовые файлы планки: test_ac14_* (переписанный test_ac9 файла 01M5XZ: ast-статика + прогон узла; сейчас 2 красных), test_ac15_* (changed_paths: из tests/ меняется только файл 01M5XZ и файлы с префиксом задачи; зелёный с рождения).
- Стаб (fsm_advance.verifying после зелёного CI → гейт по _judge_ci с _diff_base; пропуск ci в гейте in_dev; повтор/предел) + временная перепись test_ac9 — всё зелёное; мутации no_gate/base_tip/wait_all/journal_first/operator_returns/repeat_boundary/no_limit/first_only/both_as_ci/skip_all краснят свои методы. Стаб снят git checkout, скрипты удалены.
- Причины ожидания тест ищет в любой записи опроса, причины эскалации — в детали записи `state -> escalated`.
- preflight: все проверки пройдены.

## Не сработало
- `ls`, heredoc, префикс `VAR=…` в Bash запрещены — скрипты через Write, флаг мутации файлом.
- gitcmd в долгоживущем файле — признак «git-модуль»: база считается `git merge-base refs/remotes/origin/main <ветка>` песочницы.

## Где остановился
- Шаг завершён: планка и долгоживущий файл готовы.

## Чего не хватило
- Мультикомпонентная задача через tests_writing: образец tests/components_outcome_sandbox.py::writing_task (зоны до выхода, mkdir docs после set_state).
