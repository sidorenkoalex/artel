# Записка analyst — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Шаг 3 (после ANSWER-1): SPEC.md переписан, status: ready, 15 AC (8 малых правил, 6 средних, 1 большой AC-15), budget 50, монолит обоснован. QUESTIONS.md удалён (os.remove; `task-rm` отказывает файлам из ссылки документов, `rm` в Bash нет).
- Все 12 пунктов SPEC-AUDIT закрыты; карта соответствия — в «Материалах» SPEC.
- Решения формы, записанные в SPEC: переменная окружения — `config.PYCACHE_TEMPLATES_ENV = "PYCACHE_TEMPLATES_DIR"`; место по умолчанию `<tmp>/pycache-templates-<uid>` через `config.pycache_templates_dir(environ, tmp_root, uid, root)`, под ROOT → None; отметка — `manifest.json` (отн. путь → sha256); отметка неудачи `<шаблон>.failed`; временные/выброшенные каталоги — имя с `.`; поверхности: pycache_source, template_admits (realpath), template_dir, manifest_intact, publish_template, template_decision, command_interpreter.
- Места наполнения в acceptance.py: `_place_env` (run :2158, collect :2322, run_repeat :2451, run_plank :2846, full suite :3363/:3385/:3440) и `_own_env` напрямую из `_report_env` :632. two_sided.py:304 — без run_dir → пусто.
- AC-15 (ответ 1): дочерний pytest с TMPDIR в песочницу и без переменной — место по умолчанию не появляется.

## Не сработало
- `ls`/`rm` в Bash нет; `task-rm` не удаляет сохранённые пультом документы.

## Где остановился
- SPEC готов, guard ок. Шаг закончен.

## Чего не хватило
- Перечня тестов, подменяющих `subprocess.run` глобально, в одном месте.
