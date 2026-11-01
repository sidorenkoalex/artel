# NOTE test_author (визит 2)

## Выяснено
- Стенд target-human скопирован из tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py (Stand, FakeForge); задача доходит до awaiting_human настоящим approve.
- CLI `mr-sync` вызывается через `artel.main` с подменой sys.argv.
- На approve target-human origin/base — предок головы (`_base_moved_returns`), поэтому точка ответвления = голова origin/base на момент approve.
- «MR не найден» в тестах — пустой mr_iid в БД (404 — отказ forge, по строке 1 таблицы это «неизвестно»).
- Несинхрон ссылки документов: хук pre-receive bare, отвергающий refs/artifacts/*, + локальный коммит в ссылку.
- Подсказка `config.AUTO_STOP["awaiting_human"]` в `status` не печатается — её показывает `auto.auto_stop_advice`; тест проверяет её там.
- Токен GitLab в тесте AC-1 — подмена keychain.token (без gitcmd).

## Написано
- tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_fields.py — AC-1.
- tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py — AC-2..AC-16, AC-19 (показ итога и времени, store.now подменён).
- tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_awaiting_hint.py — AC-19 (подсказки без «(шаг Б2.2)»).
- acceptance_tests/test_ac20_invariants_appendix.py — AC-20; там же пометки `escalate` для AC-17 и AC-18 (вопросы Б-4: жить ли циклу `auto <id>` в awaiting_human, какие часы и какой сон подменять; что считать уведомлением watch).
- Валидация стабом: все 36 методов основного файла + AC-1 + подсказки зелёные; 5 мутаций стаба пойманы. Стаб удалён, `git status` — только три новых файла tests/.
- preflight: всё «пройдена». На чистом коде все файлы красны по своей причине («Неизвестная команда mr-sync», нет полей MergeRequest, «(шаг Б2.2)» в подсказке, нет PLAN).

## Не сработало
- `cd X && …`, `ls`, `rm`, запись в /tmp — недоступны; удаление файлов — через python pathlib.

## Где остановился
Шаг сдан с эскалацией AC-17/AC-18. После ANSWER: дописать тесты AC-17 (опрос надзора + проверка загрузки поля mr_sync_interval_min) и AC-18, снять обе пометки escalate.

## Чего не хватило
Где показывается подсказка config.AUTO_STOP (не в status, а в auto.auto_stop_advice) — SPEC называл status.
