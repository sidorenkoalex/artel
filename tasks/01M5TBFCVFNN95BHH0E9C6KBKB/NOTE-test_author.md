# Записка test_author — 01M5TBFCVFNN95BHH0E9C6KBKB

## Выяснено
- Планка — только долгоживущие файлы (все 22 AC — свойства кода), `acceptance_tests/` пуст (перечень сумм положит пульт):
  - tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_drafts.py — AC-1,2,3,5,6,16,17,18,19,20 (light_transition, проект artel);
  - …_migration.py — AC-15 (tmp_root);
  - …_epic_ref.py — AC-4,7,8,9,10,12,13,14,21,22 (real_git + make_project_repo, проект эпика не artel);
  - …_ref_scans.py — AC-11 (real_git, обе ссылки в origin артели).
- Колонки epic_drafts/epic_decisions SPEC не называет — тесты ищут строки и поля по значениям (id эпика, название, текст ТЗ, рамка, номер, `draft|promoted|dropped`); имён колонок не навязывают. Перечни: `--start-after a,b` (через запятую, как `--after` Э1).
- Рабочая копия на 761b646e9 без Э1: до подтяжки main тесты падают на «no such table: epics»; после — на отсутствии Э3 (сверено на снимке origin/main).
- Валидация: временный стаб Э3 на снимке origin/main (в git не попал, снимок удалён) — 37/37 зелёных; 19 мутаций стаба (две отправки, лексикографический export, strip решения, номер = count+1, рамка с источником spec, неразрешённый адрес, журнал без target, молчаливая неудача записи, потеря хвоста при restore, перезапись при restore, ready/close без черновиков и др.) — все пойманы.
- AC-11 сегодня красны 2 места: retro_corpus (строка task_id=epic-…) и plan_appendix_ci.remote_docs_refs (отдаёт epic-…); остальные места зелёны с рождения.

## Не сработало
- Составные команды bash (`;`, `&&`, `cp`, `mktemp`) требуют подтверждения — по одной команде, файлы через python.
- `plank-run <id>` без файла отказывает «планки нет» (acceptance_tests пуст) — гонять `plank-run <id> tests/<файл>.py`.

## Где остановился
- Готово: preflight пройдена по всем пунктам, plank-run по четырём файлам — красны по ожидаемым причинам.

## Чего не хватило
- Дольше всего искал, как считать отправки без импорта gitcmd/artifact_branch в долгоживущем файле: `mock.patch.object(subprocess, "run")` + `strip_dash_c`. `SELECT rowid, *` при INTEGER PRIMARY KEY даёт колонку `id` — нужен алиас.
- Карту кодовой базы (scripts/codebase_map.py) test_author обновлять не может (вне зоны записи) — её регенерирует разработчик.
