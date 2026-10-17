# Записка developer — 01M545EB0A9F191WTDSPCH36GA

## Выяснено
- Реализация: `runner._step_project(t)` (артель — без targets.yaml; пустой target/TargetsError — `StepProjectError` → отказ `run отклонён: проект задачи не определён`), проект пробрасывается `_run_attempts` → `run_agent_once(project=)` → `role_env(project=)`/`role_cwd`/`_step_docs_dir(…, project)`/`provider.command(project=)`.
- `brief._project_skills_read` — общий для `project_skills_refusal` и `project_skills_text`; имя без `/`, `\`, не `.`/`..`; текст — `gitcmd.show(MAIN_BRANCH, skills/<имя>.md, repo=ROOT)`.
- Claude: `providers/claude.external_allowed_tools()`; base/codex — только сигнатура.
- Долгоживущий файл задачи 7/7 зелёный, plank-run 5/5 зелёный.

- Свои тесты: tests/test_step_project.py (пустой target, артель без targets.yaml, имена ''/./.., прямой run_agent_once) — мутации пойманы.

## Не сработало
- pytest `-n 8` по списку файлов затронутых модулей падает (узлы xdist «not properly terminated») — гонял без `-n`.

## Где остановился
- Всё сделано: plank-run 5/5, suite-run №1 зелёный (5553/0/2), карта регенерирована, PLAN.md status: ready.

## Чего не хватило
- Ничего существенного: путь шага (`_refuse_before_start` → `_run_attempts` → `run_agent_once` → `_prepare_step`/`_spawn_and_wait`) читается за минуты.
