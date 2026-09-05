---
task: 01M1NSR5M5THYRC0RFWPMVE2DW
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: Пул канарейки в репозитории в зашифрованном виде: seal, restore, манифест GUID

## Фаза A: план

PLAN.md (`status: ready`) не поменял подход относительно итерации 1
(тот же обзор одобрен: ленивый импорт `canary` в `catalog.cmd_init()`,
`doctor.py` импортирует `canary` на уровне модуля без цикла, единая
точка расшифровки `_authorized_pool_payload`) — добавлен только раздел
«Правка по REVIEW.md итерации 1», описывающий закрытие R1-F1/R1-F2/
R1-F3. Раздел совпадает с фактическим диффом коммита `f1c25367`
(проверено построчно, см. ниже) — план не разошёлся с кодом.

Диф-приложение `.github/workflows/ci.yml` (требование 6/AC-12) не
менялось со времени итерации 1; перепроверил `git apply --check`
заново на ТЕКУЩЕЙ голове ветки (`3364f9bd`, после повторной подтяжки
main Оператором) — применяется чисто (пустой вывод, код 0). Карта
кодовой базы (`docs/codebase-map.md`) свежая: локальный прогон
`scripts/codebase_map.py` дал расхождение только в строке
`built_at_sha` (`ea1d4787` → `3364f9bd`), содержимое карты не
разошлось с кодом (изменение отката не потребовало — `git checkout --
docs/codebase-map.md` вернул файл к закоммиченному виду перед
завершением ревью).

## Соответствие SPEC

Диф этой итерации (коммит `f1c25367`) правит три пункта из итерации 1
— пересматриваю их предметно, остальные 15 AC не менялись со времени
итерации 1 (там же подтверждены OK) и повторно код не читал за
исключением мест, задетых диффом.

| AC | Вердикт | Комментарий |
|---|---|---|
| AC-1 | OK, см. R1-F1 (закрыт частично, остаток принят) | ключ шифрования пула теперь передаётся `openssl enc -pass fd:N` через наследуемый пайп (`orchestrator/canary.py:150-164,191-213`) — argv `ps`/`ps aux` больше не несёт ключ пула, закреплено `OpensslSecretPassingTest` (tests/test_canary.py:612-658), обе assert-проверки (`assertNotIn(self.KEY, cmd)`, `assertIn("pass_fds", kw)`) прогнаны зелёными. Производный MAC-ключ (`_hmac_tag_hex`) остаётся аргументом `openssl dgst -hmac` — технической альтернативы нет НА ЭТОЙ машине (`openssl dgst -help` не несёт fd/env-аналога `-passin` для `-hmac`, `openssl mac` отсутствует на LibreSSL) И это же прямо мандатировано ANSWER-1 п.1 («тег HMAC-SHA256 ... через openssl dgst -sha256 -hmac») и закреплено ЗАЛОЧЕННЫМ приёмочным тестом `test_pool_seal.py:136-143` (`assertIn("-hmac", dgst_argv)`) — переход на `hmac`/`hashlib` стандартной библиотеки Python обошёл бы это ограничение технически, но сломал бы залоченную планку и противоречил бы уже принятому решению Оператора; не переоткрываю закрытую эскалацию. Блast-радиус остатка ограничен: `_mac_key` — производный SHA-256 хэш ключа пула (необратим), утечка MAC-ключа позволяет подделать тег целостности запечатанного файла, не расшифровать пул |
| AC-2..AC-12 | без изменений с итерации 1 (OK/OK/OK/OK/OK/OK, AC-8 см. ниже, OK/OK/OK/manual) | код не менялся, повторно не перечитывал |
| AC-8 | OK, R1-F2 закрыт | `pool_drift_warning` (orchestrator/canary.py:325-335) теперь фильтрует `p.suffix == ".md"`, тот же фильтр, что `cmd_pool_seal` — регресс-тест `test_foreign_non_md_file_in_pool_dir_is_not_a_false_drift` (tests/test_doctor_canary_pool.py:178-193) кладёт `.DS_Store` в каталог пула и проверяет отсутствие ложного drift-предупреждения; прогнан, зелёный |
| AC-13..AC-17 | без изменений с итерации 1 (OK) | перепроверил AC-13 точечно (4 литерала `permissions.deny` в `docs/reference/role-home/claude/settings.json` присутствуют буквально) и AC-17 (`test_pool_key_not_leaked.py` зелёный) в рамках регрессии — без изменений кода |
| AC-18 | skip, обоснованно (без изменений) | класс «ci-covered»; регрессию затронутых модулей прогнал сам (см. «Проверено исполнением») |

Докстринг-заявка «Ловит мутацию: …» (R1-F3) — проверил все шесть
классов/методов, ранее её не несших:
- `tests/test_canary.py`: `PoolSerializationRoundtripTest` (:508-541),
  `MacKeyTest` (:544-567), `AuthorizedPoolPayloadRoleEnvTest`
  (:570-589), `RestorePoolIfMissingNoOpTest` (:592-609) — у каждого
  метода есть «Ловит мутацию: …», формулировки называют конкретную
  мутацию (перестановку длины-префикса, недетерминированную соль,
  забытый `hashlib.sha256`, переставленную проверку `role_env`), не
  пересказ имени метода.
- `tests/test_doctor_canary_pool.py`: `CanaryPoolDriftCheckTest` —
  все три метода несут заявку, включая новый
  `test_foreign_non_md_file_in_pool_dir_is_not_a_false_drift` (R1-F2).
- `tests/test_new_argv_parsing.py`: `CmdCanaryDispatchTest` — оба
  метода несут заявку («`--k` ошибочно маршрутизируется…»,
  «`pool-seal` падает в общую ветку разбора `--k`…»).

Новый класс `OpensslSecretPassingTest` (регресс-тест R1-F1) тоже несёт
заявку в обоих методах — сверил формулировку с реальной проверкой
(греп ключа в argv + наличие `pass_fds` в kwargs), заявка описывает
именно то, что тест ловит.

## Замечания

Замечаний нет — три major (R1-F1, R1-F2, R1-F3) итерации 1 закрыты по
существу (см. реестр), R1-F4 закрыт как информационная передача
аналитику/Оператору (правка SPEC не в зоне роли developer). Новый
диф (коммит `f1c25367`) не вносит собственных дефектов: `_secret_fd`
корректно закрывает оба конца пайпа (`os.close(w)` сразу после записи,
`os.close(r)` в `finally` после завершения `subprocess.run`, который
синхронно дожидается процесса) — утечки файловых дескрипторов не вижу;
`pass_fds=(fd,)` — обязательный аргумент для наследования дескриптора
через `exec` в Python 3 (fd, созданный `os.pipe()`, по умолчанию
non-inheritable), присутствует в обоих новых вызовах.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/canary.py:150-164,191-213 | ключ пула/MAC-ключ передавались `openssl` аргументом командной строки | секрет виден в `ps`/`ps aux` во время seal/restore | ключ шифрования пула переведён на `-pass fd:N` — закрыто полностью, проверено `OpensslSecretPassingTest` (зелёный). Производный MAC-ключ остаётся в argv `openssl dgst -hmac` — технически неустранимо на этой машине И структурно зафиксировано ANSWER-1 п.1 + залоченным `test_pool_seal.py:142-143`; блast-радиус ограничен подделкой тега целостности (SHA-256 необратим, ключ пула не восстановить). Принимаю закрытие: дальнейшая правка потребовала бы либо новой эскалации к Оператору на пересмотр ANSWER-1/локальной планки, либо она не оправдана против уже принятого и обоснованного риска |
| R1-F2 | accepted | orchestrator/canary.py:325-335 | `pool_drift_warning` сравнивал ВСЕ файлы каталога без фильтра `.md`, `cmd_pool_seal` — только `*.md` | ложное предупреждение AC-8 на постороннем файле (`.DS_Store`) | применён тот же фильтр `p.suffix == ".md"`; регресс-тест `test_foreign_non_md_file_in_pool_dir_is_not_a_false_drift` зелёный |
| R1-F3 | accepted | tests/test_canary.py (4 класса), tests/test_doctor_canary_pool.py:`CanaryPoolDriftCheckTest`, tests/test_new_argv_parsing.py:`CmdCanaryDispatchTest` | нет заявки «Ловит мутацию: …» (2 класса — вовсе без докстринга) | тест не документировал ловимую поломку | заявка дописана во всех шести классах/их методах; формулировки называют конкретную мутацию, сверил каждую с телом теста |
| R1-F4 | accepted | tasks/01M1NSR5M5THYRC0RFWPMVE2DW/SPEC.md («Оценка объёма и деление») | зона задачи не называла `orchestrator/runner.py` | минорная неточность зоны SPEC, не блокирует мерж | developer не правит SPEC.md — передано аналитику/Оператору через «Предложения системе» PLAN.md; принимаю как достаточное закрытие для minor-замечания без изменения кода |

## Вердикт

approved — все замечания итерации 1 (R1-F1..R1-F4) закрыты по
существу, диф закрытия (`f1c25367`) не вносит новых дефектов, полная
локальная приёмочная планка и регрессия затронутых модулей зелёные.

## Проверено исполнением

- `python3 -m unittest tests.test_canary tests.test_doctor_canary_pool
  tests.test_new_argv_parsing` — 69 тестов, все зелёные (включая новый
  `OpensslSecretPassingTest` и регресс-тест `test_foreign_non_md_
  file_in_pool_dir_is_not_a_false_drift`).
- Приёмочная планка задачи, файл за файлом (полный `discover`
  запрещён guard'ом — прогнано поштучно через `unittest discover -s
  tasks/01M1NSR5M5THYRC0RFWPMVE2DW/acceptance_tests -p "<файл>"`):
  `test_pool_seal.py` (4), `test_pool_key_keychain.py` (2),
  `test_pool_seal_roundtrip.py` (1), `test_pool_restore.py` (3),
  `test_pool_role_isolation.py` (4), `test_pool_doctor_warning.py` (1),
  `test_pool_key_not_leaked.py` (1), `test_pool_guid_manifest.py` (3),
  `test_pool_manual_and_skip_markers.py` (0, пометка) — 19 тестов, все
  зелёные, включая тампер-тест AC-1
  (`test_ac1_tampered_hmac_tag_refuses_decryption_before_reading_
  ciphertext`).
- `python3 -m unittest tests.test_doctor tests.test_catalog_new_race
  tests.test_coldstart tests.test_invariants
  tests.test_catalog_status_log` — 156 тестов, все зелёные (регрессия
  после повторной подтяжки main Оператором до `3364f9bd`, включающей
  несвязанный код других задач — `stack.py`, `zone_lock.py`).
- `openssl dgst -help`/`openssl mac -help` — не запущены напрямую в
  этом шаге (permission-запрос на выполнение отклонён средой
  выполнения без ответа пользователя); опираюсь на независимо
  установленный факт (feedback_openssl_dgst_hmac_no_secret_source.md,
  проверен в этом же репозитории ранее эмпирически на этой машине) и
  на то, что вся приёмочная планка/юнит-тесты, зависящие от реального
  вызова `openssl dgst -hmac`/`openssl enc -pass fd:N`, зелёные —
  поведение подтверждено сквозным прогоном, не только докстрингом
  разработчика.
- `git apply --check` диф-приложения `.github/workflows/ci.yml` из
  PLAN.md — на ТЕКУЩЕЙ голове ветки (`3364f9bd`, после повторной
  подтяжки main) применяется чисто (пустой вывод, код 0) — перепроверил
  независимо, не только по заявке PLAN.
- `python3 scripts/codebase_map.py` (локальный прогон для сверки
  свежести) — расхождение только в строке `built_at_sha`, содержимое
  карты совпадает с закоммиченным; откатил правку `git checkout --
  docs/codebase-map.md` перед завершением ревью (карта не относится к
  предмету ревью, менять её не мой мандат).

## Предложения системе

- Класс «докстринг без заявки "Ловит мутацию:"» в новых `tests/*.py`
  (не в приёмочных) — третий раз подтверждён и в этой же итерации
  закрыт полностью (см. feedback_test_authoring_mutation_claim_gap.md)
  — подтверждаю наблюдение прошлой итерации: стоит вынести в
  проверяемый пункт до сдачи шага test_author/developer, а не
  полагаться только на ревью.
