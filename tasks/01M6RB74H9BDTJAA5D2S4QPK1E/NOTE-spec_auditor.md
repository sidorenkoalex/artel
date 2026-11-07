# Записка spec_auditor

## Выяснено
- Визит по spec_sha 7e7c818b. Ветка задачи отстаёт от main (main 6bde2b9e6); факты SPEC сверены по `git show main:` — все подтвердились: projects.py:380/:451-512/:894-898/:905-932/:965/:991, gitlab_adapter.py:579-586, forge.py:96-98/:452, gitcmd.py:559-582/:625-660, targets.py:715-720, catalog.py:856, epics.py:796, project_checks.py:48-66, cli.py:312-355.
- Песочница: `isolate_keychain_and_role` (tests/sandbox.py:676) ставит `refused_gitlab_transport` → URLError без повтора → сторож `warn`; pair_support/unsupported_project зелёные без правки.
- Ловушки для разработчика (не отклонения SPEC): новую строку не добавлять в `_names()` (test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py:813 точный список для github/артели); поля TokenUser — после username с дефолтом None (forge_probe_ref_sha.py:82 позиционно); только один GET /user (gitlab_forge.py:1623, test_forge_gitlab_request.py:174-187).
- `spawn_subtask` (catalog.py:1082) заводит задачу через `_new_task_row` в обход cmd_new — вне ТЗ, отмечено как наблюдение.

## Не сработало
- Записи в /tmp и `$(...)` в Bash отклоняются — читать через `git show main:<путь> | sed`.

## Где остановился
- SPEC-AUDIT.md сдан: pass, ready.

## Чего не хватило
- Карта существующих тестов, задевающих project_entry_checks для GitLab, — собрал поиском по tests/.
