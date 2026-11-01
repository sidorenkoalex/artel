# Записка spec_auditor

## Выяснено
- Строки SPEC сверены, совпадают: fsm_advance.py in_dev :759, гейт :843, сжатие :855, отправка :868, verifying :441, review :469; outcome_integrity.py :1044, :1062-1063, :1084, :1148, :1336, :1396; test_ac9 :918.
- Вердикт concerns, 6 отклонений (SPEC-AUDIT.md, раздел «Вердикт»):
  1) отказ, записанный на verifying до `state -> in_dev`, не попадает в бриф developer (store.refusal_history :1185-1195 режет по последней записи `state -> in_dev`; brief.py:1413);
  2) «sha на входе в verifying» против pull-main на verifying (pull_main.py:1-9; ci.verifying_status берёт текущую голову, ci.py:1028);
  3) AC-2 «конвейер» — ядро пишет номера заданий (:1222-1227);
  4) граница «ждать / эскалировать сразу»: _judge_ci сворачивает все негодности головы в «нет отчёта головы» (:1159-1161), а pending/created по букве треб. 6 эскалируют сразу;
  5) AC-9: на базе перезапуск даёт «нет отчёта базы» (:1090-1108), сторону надо назвать;
  6) зона tests/ сужена против ТЗ, файл теста AC-11 не назван.
  Сверх них: записи из нескольких компонентов (_components_gate) в SPEC не упомянуты.
- Петли verifying→in_dev→verifying в auto нет: auto.py:391-469, :751-771.
- both на гейте мержа судится локально (:1343) — CI-часть на verifying для both новая.

## Не сработало
- grep после cd и сложные пайпы в Bash требуют подтверждения; rg с абсолютным путём проходит.

## Где остановился
- SPEC-AUDIT.md готов (status: ready, verdict: concerns), guard ок.

## Чего не хватило
- Как бриф developer получает причину возврата из не-агентского состояния: нашёл только через store.refusal_history и brief.advance_refusal_history.
