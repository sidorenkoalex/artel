# NOTE analyst — 01M6AB4VE2R0Q2V5D4MMJGNGH7 (Б2.2 mr-sync)

## Выяснено
- Подсказка «(шаг Б2.2)»: `orchestrator/fsm.py:43` (AWAITING_HUMAN_HINT), `orchestrator/config.py:942` (подсказка состояния status). Тест: `tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_commands.py:24` — модульная константа HINT, утверждение `assert HINT in out` (имя, не литерал) → раздел «Меняемое поведение» guard не примет (было должно быть литералом в утверждении).
- Образец формы SPEC — SPEC Б2.1б в refs/artifacts/01M5XZ9Z68XE2EKPDHYCAK25KF (монолит, матрица неослабления).

- Путь done гейта мержа: `fsm_merge_gate.py:1549-1552` (_finalize_done_state :1337 → cleanup._commit_closing cleanup.py:736 → snapshot.commit_closing snapshot.py:96 → retro.build_done retro.py:551 «Итог: done, sha …»; _cleanup_merged_task :1367 удаляет и ветку на сервере — для mr-sync нельзя). Зоны освобождаются по терминальному состоянию (zone_lock.py:111-116), merge_after — по done.
- Инвариант 18 в docs/invariants.md:48 держит `test_auto_cycle.AutoNeverPassesAGateTest`; обход команд — `tests/test_invariants.py:400` `commands()`. docs/invariants.md защищён, в зонах ТЗ его нет.
- Гейт target-human: `fsm_merge_gate._approve_for_project_people` :1576; last_sent_sha — gitcmd.py:233; MergeRequest — forge.py:67; _merge_request — gitlab_adapter.py:497.
- watch.py нужен для уведомления о смене итога (требование 5) — внесён в зоны как прямое следствие.
- Решение: ТЗ достаточно → SPEC (монолит-материал + возможный разрез), budget 50 (рамка ТЗ).

## Не сработало
- `ls` в shell недоступен (command not found) — пользуйся Read/grep.

## Где остановился
- SPEC.md написан (16 AC, status ready, budget 50, merge_after Б2.1б), guard ок. Смена HINT теста Б2.1а оформлена матрицей неослабления + мандатом ТЗ (строку мандата вписывает Оператор на гейте), не «Меняемым поведением» (HINT — имя, не литерал).
- Свои уточнения сверх буквы ТЗ (на проверку аудитору): «MR не найден» не расшифрован (404 vs «неизвестно» — решает разработчик), отсутствие ветки на сервере инцидентом не названо явно; опрос надзора эскалирует чужой коммит тем же mr-sync без --confirm.

## Чего не хватило
- Где держится инвариант 18: ТЗ называет tests/test_invariants.py, по docs/invariants.md:48 — test_auto_cycle.AutoNeverPassesAGateTest.
