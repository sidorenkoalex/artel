# NOTE spec_auditor

## Выяснено
- Визит 3 (SPEC sha f72c7470…). Рабочий каталог (HEAD 761b646) старше Э1 — сверка по `git show origin/main:<файл>` (литералом, без `$VAR`/`>`/`sed '/re/'`).
- Факты SPEC подтверждены: zone_lock.py:157-159, stale_cycles.py:42, alerts.py:116, epics.py cmd_epic без parallel/stop, EPICS_DDL без колонки лимита.
- alert-ack (doctor/cli.py:278 → alerts.ack:290 → store.ack_alert:1591) журнал НЕ пишет — треб. 4 «запись журнала … alert-ack» неисполнима в зонах.
- resume на не-паузной задаче журнал не пишет (pause.py:95-116) — после stop/лимита шагов естественной команды «перезапусти» нет; после `epic stop` + новый `auto --epic` все остановленные дети ждут Оператора.
- watch доставляет алерт только при target ∈ задачи набора/проекты (watch.py:300-315); raise_attention_alert(conn, epic_id) с target=id эпика в сессию не придёт. Журнал эпика (task_id=id эпика) тоже не доставляется (store.py:118).
- Правило (б) треб. 8 без ограничения сессии; _launch_observation (artel.py:922) отказывает наблюдению чужой сессии.

- Аварийный выход дочернего auto (CYCLE_ABORTED, auto.py:643-651) в треб. 5 не классифицирован — риск цикла перезапусков.
- Тест миграции Э1 требует ровно одну запись журнала миграции (tests/test_01m5tbbdfs6dwqy6ms263t1kpy_migration.py:122).

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Правила, какие команды Оператора пишут журнал задачи, нет — искал по `git grep "journal(" origin/main` по модулям команд.
