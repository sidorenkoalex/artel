# Записка developer

## Выяснено
- Итерация 3 (возврат из merge_gate): код orchestrator/ не менялся; добавлен tests/test_epic_draft_promote_unsupported_project.py (gitlab, target-human): epic draft promote → код 1, причина unsupported_reason, tasks прежние, черновик draft, клона и git нет. Эпик/черновик — store.insert_epic/insert_draft + conn.commit().
- Мутация «проверка в new_cli_target вместо cmd_new» → новый тест красный (вывод — сбой клона), долгоживущий файл задачи зелёный: пробел был реален.
- Причина возврата просила положить тест в долгоживущий файл задачи; он под локом сумм (_long_lived_manifest_refuses отклонит переход) — тест в отдельном файле, расхождение описано в PLAN (итерация 3), перенос — amend-tests по решению Оператора.
- Ранее: targets.unsupported_reason; отказы в catalog.cmd_new, runner._cmd_run, auto._cmd_auto, fsm._cmd_approve; doctor project-support-<проект>.

## Не сработало
- Bash шага: составные команды/пайпы иногда требуют подтверждения — одиночные команды.

## Где остановился
- Шаг закончен: 33 passed (новый + долгоживущий + drafts), карта регенерирована, PLAN status: ready.

## Чего не хватило
- Причина возврата не учитывала лок долгоживущего файла; правила «куда класть тест, если причина возврата называет залоченный файл» нет.
