# Записка analyst

## Выяснено
- Итерация 3 (второй возврат с spec_gate, 8 пунктов об обходах защиты): все внесены без вопросов; QUESTIONS.md не нужен.
- Число AC оставлено 9 (порог деления 10, бюджетный сигнал — 60): пункты влиты в AC-2 (ci_required_jobs через targets.target()), AC-3/AC-4 (нет refs/artifacts при отказе), AC-5 (4-й случай — {id}-шаблон, id до проверки), AC-6 (-o норма, -c/--git-dir, контекст ARTEL_TASK/task_id/incident-алерт), AC-7 (нечитаемый слой/нет записи, отправка по URL-пути из корня пульта).
- doctor 5.2 (project_checks.py:98, push --dry-run) — в «Не входит», пересматривает Б2.
- Факты: _flatten — targets.py:579; cmd_new: ensure_clone → idgen → _new_task_row (catalog.py:848); spawn_subtask выдаёт id внутри (catalog.py ~1027) — разработчику придётся выдать id заранее.

## Не сработало
- Bash с `$?` требует подтверждения — запускать простые команды.

## Где остановился
- SPEC обновлён (status: ready, 9 AC, budget 40), guard: ок. Шаг завершён.

## Чего не хватило
- Толкование «URL относится к области проектов» при нечитаемом targets: взят URL-путь под repo_context.projects_root(); https-URL без записи распознать нельзя.
