## Выяснено
- Аудит 2 (sha 6de28bb8): отклонения возврата 1 закрыты; вердикт concerns, 9 пунктов.
- Главное новое: YAML-разборщика для .gitlab-ci.yml в пульте нет (PyYAML не берётся, yamlmini без блочных списков, yamlmini.py вне зон).
- Все тексты gitlab_adapter._status_reason несут код → AC-12 не отличает http_status из текста от Reply.status.
- AC-9 пуст без подмены shutil.which("gh") (код main выходит раньше вызова gh).
- targets.py:563 — второе сравнение merge_gate с литералом (SPEC пишет «единственное»).
## Не сработало
- Bash с cd + относительные пути и конвейеры (| head, xargs) требуют подтверждения — только абсолютные пути, по одной команде.
## Где остановился
- SPEC-AUDIT.md записан (status ready, verdict concerns), guard — ок. Шаг завершён.
## Чего не хватило
- Не знал, какой YAML-разбор допустим в пульте — нашёл в докстринге orchestrator/yamlmini.py:1-24.
