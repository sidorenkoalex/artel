# Записка test_author — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- guard (scripts/guard.py:4134 `_GIT_MODULES`) запрещает долгоживущему файлу импорт `orchestrator.gitcmd` — поэтому AC-6..AC-9 (точки отправки gitcmd) лежат в планке `acceptance_tests/test_push_point.py` (Группа: разовый, довод в докстринге), AC-1..AC-5 — долгоживущие tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py (AC-1, AC-2) и ..._branch_template.py (AC-3..AC-5).
- Прогоны до кода: record_fields 21 красный / 1 зелёный; branch_template 18/4 (зелёные — «нет ls-remote при шаблоне по умолчанию»); планка 66/9 (зелёные — AC-8 и подставы у `operator`, клон артели).
- Временный стаб targets/catalog/fsm/gitcmd: всё зелёное (22 + 22 + 75), стаб откачен `git checkout`, в рабочей копии только два новых файла tests/.
- Планка шпионит `subprocess.run`/`Popen`: отправку (push/send-pack/псевдоним) не исполняет, прочий локальный git — настоящий. Параметр `task_id` ищется по сигнатурам точек `gitcmd` (in_repo, git, carpentry, read, read_env, read_stream) — хотя бы у одной должен быть.
- Запись «ветка отправлена» тест ищет как текст `action detail`, содержащий «ветка отправлена» и sha.
- preflight: все проверки пройдены.

## Не сработало
- `ls`, `sed -i` в Bash недоступны/требуют подтверждения — пользовался `find` и Edit.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Запрет gitcmd в долгоживущих файлах нашёлся только в guard.py; в скиле нет правила для случая, когда предмет критерия — сам gitcmd.
