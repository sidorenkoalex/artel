---
task: 01M2CN42RV0EBBP7HS4HP2VNY1
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рефакторинг: canary.py — вынос запечатанного пула в pool_seal.py

Источник: отчёт ревизии №6 docs/audits/code-revision-2026-09-13.md, находка
CR-2026-09-13-4 ★ и ТЗ-черновик Р-4. Решение Оператора 13.09: волна
рефакторинга, задача класса «рефакторинг» по правилам T015.

Факты:
- orchestrator/canary.py (1358 строк) держит две несвязанные области:
  запечатанный пул шаблонов (:181–462 — `_pool_dir`, `sealed_path`,
  `guids_path`, `_mac_key`, `_secret_fd`, `_hmac_tag_hex`,
  `_openssl_encrypt`/`_openssl_decrypt`, `_serialize_pool`/
  `_deserialize_pool`, `_authorized_pool_payload`,
  `restore_pool_if_missing`, `pool_drift_warning`, `cmd_pool_seal`; ~280
  строк) и прогон (`_ephemeral_clone` :501, `_drive_task` :850,
  `_run_one_task` :1187).
- Единственная общая точка областей — `_pool_dir()` (:181; зовётся и из
  `cmd_canary` :1341).
- Потребители пула вне canary.py: orchestrator/artel.py:705
  (`canary pool-seal`), orchestrator/catalog.py:46–50 (`cmd_init`, ленивый
  импорт), orchestrator/doctor/cli.py:98, orchestrator/doctor/canary_pool.py:61,
  orchestrator/doctor/__init__.py:96. answer.py:113 и prune.py:80 — только
  комментарии, не правятся.
- Имя `canary_pool.py` занято (orchestrator/doctor/canary_pool.py).
- tests/test_canary.py: ~20 мест зовут имена пула напрямую (:1492–1636) и
  два патча `canary.keychain` (:1567, :1588);
  tests/test_doctor_canary_pool.py:149 — третий патч `canary.keychain`.

Требуется (поведение не меняется):
1. Новый модуль orchestrator/pool_seal.py: функции :181–462 переносятся
   дословно; `_pool_dir` живёт в новом модуле, canary.py его импортирует.
   Из canary.py уходят импорты `hashlib`, `hmac`, `struct`, `uuid`,
   `keychain`, если после переноса не используются. Докстринг :48–55 —
   ссылка на новое место.
2. Потребители переключаются на новый модуль: artel.py:705, catalog.py:46–50
   (ленивый импорт — теперь pool_seal), doctor/cli.py:98,
   doctor/canary_pool.py:61, doctor/__init__.py:96. Циклов импортов не
   появляется (проверить `python -X importtime` или прямым импортом).
3. `_run_one_task` — три приватные фазы внутри canary.py: прогон в клоне /
   сверка с бейзлайном / диагностика и запись canary_runs. Сигнатуры
   `cmd_canary`, `cmd_pool_seal`, `restore_pool_if_missing`,
   `pool_drift_warning` — как есть.
4. Поверхности неизменности: вывод `canary --k N [--sha]`, `canary
   pool-seal`, `init`, `doctor`; тексты и порядок записей журнала; схема
   БД (`canary_runs`); имена и пути файлов пула и диагностики; формат
   запечатанного пула байт-в-байт (HMAC, openssl, GUID-манифест).
   Зелёность полного набора tests/ = неизменность.
5. Тесты: ассерты не меняются; в tests/test_canary.py и
   tests/test_doctor_canary_pool.py правятся только импорты и пути патчей
   (в том числе три патча `canary.keychain` -> `pool_seal.keychain`).
6. docs/codebase-map.md регенерируется штатно (новый модуль).
7. PLAN: таблица переносов, откат revert'ом одного merge, смоук до/после:
   `artel.py doctor` без изменяющих флагов и `artel.py status` — сравнение
   в PLAN. Канарейку саму не гонять (стоимость).
8. Никаких попутных улучшений.

Зоны: orchestrator/pool_seal.py, orchestrator/canary.py,
orchestrator/catalog.py, orchestrator/artel.py, orchestrator/doctor/__init__.py,
orchestrator/doctor/cli.py, orchestrator/doctor/canary_pool.py,
docs/codebase-map.md, tests/.

Приложением: orchestrator/answer.py:113, orchestrator/prune.py:80
(комментарии — не правятся); orchestrator/runner.py
(`in_role_environment` — рубеж роли, не трогать).

Не входит: логика HMAC/шифрования и авторизации пула, рубеж роли,
`_ephemeral_clone` и `_drive_task`, поведение `--sha`.

Рамка: $35.
