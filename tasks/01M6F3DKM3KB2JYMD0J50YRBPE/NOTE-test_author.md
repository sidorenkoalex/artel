# Записка test_author

## Выяснено
- Планка: tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_record.py (AC-1, AC-2, AC-3 загрузка; чистая загрузка записи, tmp_root), tests/test_01m6f3dkm3kb2jymd0j50yrbpe_verify_flow.py (AC-3 переход, AC-4..AC-19; настоящий git, проект gitlab в локальном слое), acceptance_tests/test_ac20_invariants_appendix.py (разовый: приложение PLAN к tests/test_invariants.py — разбор guard.plan_appendices, apply_check, прогон test_invariants.py в отвязанной рабочей копии HEAD, ~45 с).
- Стенд flow-файла по образцу tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py: CI — FakeForge.pipeline_status по sha; «гейт по исходам не пройден» — подмена публичной verifying_gate во всех модулях orchestrator, держащих её; вход в verifying — store.set_state; отметка в БД ищется без знания схемы (строка любой таблицы, кроме steps, с id задачи и именем проверки).
- Отказ команды = ненулевой код выхода (SystemExit) + текст в выводе; успех — код 0.
- Запись ожидания ищется регуляркой «ждёт проверки <имя> по sha <7–40 hex, префикс головы>» в action+detail; строка status — блок задачи в выводе catalog.cmd_status.
- Уведомление watch — строка «уведомление: …» с id задачи (watch --observation --notify, sys.platform=linux).
- Временный стаб реализации (удалён, рабочая копия чистая): все 51 метод долгоживущих файлов зелёные на трёх прогонах; мутации стаба (ожидание без визита, запись на каждом опросе, отметка без sha, verify-ok без записи ожидания, review после первой отметки, verify-fail меняет review_iters, предел «>», без остановки auto, без _WAITING надзора, verifying в _NOT_HOLDING_STOP_STATES, запись ожидания не значима для watch, waiting_on всегда ci) краснят свои тесты.
- Без реализации: 49 из 51 красные (слой с verify не загружается, команд нет); зелёные с рождения — AC-19[красный CI] и AC-3[0].

## Не сработало
- Составные команды Bash (`;`, `|`) и `rm`, `cp` вне каталогов требуют подтверждения — только одиночные команды, удаление через python.
- yamlmini: кавычки в потоковом списке и блочные списки не разбираются — значения verify без кавычек.

## Где остановился
- Шаг закончен: plank-run (2 failed — PLAN.md нет, ожидаемо), preflight — все проверки «пройдена». Карту docs/codebase-map.md не регенерировал (правка вне tests/ откатывается пультом).

## Чего не хватило
- Публичного входа в разбор задач эпика надзором (`_epic_view` закрыт) — наблюдаемое построено через auto.cmd_auto_epic и факт запуска дочернего.
