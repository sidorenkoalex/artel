---
task: 01M1NSR5M5THYRC0RFWPMVE2DW
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: Пул канарейки в репозитории в зашифрованном виде: seal, restore, манифест GUID

## Подход

Часть 1 (01M1NEEWH5K1XPFRDGRMPYSBXJ) уже смержена в main (мерж-коммит
`a76836aa`) — блокер контекста SPEC снят; ветка задачи была на 256
коммитов позади origin/main (заведена ДО мержа части 1), первым шагом
подтянут main (`git merge origin/main`, без конфликтов) и перегенерирована
карта кодовой базы (`scripts/codebase_map.py`, sha-заголовок обновился,
содержание — нет).

Вся новая механика — в `orchestrator/canary.py` (владелец концепции
«пул», см. существующий v2-докстринг модуля), не в отдельном модуле:
зона задачи по SPEC называет `canary.py`/`catalog.py`/`doctor.py`/
`keychain.py`, отдельный файл добавил бы восьмой путь без выигрыша.
`catalog.py`/`doctor.py` зовут функции `canary.py` — обратный импорт
(`canary.py` уже импортирует `catalog` на уровне модуля) дал бы цикл,
поэтому `catalog.cmd_init()` берёт `canary` ленивым импортом внутри
функции (тот же приём уже есть в кодовой базе — `catalog.py:281`,
`runner.py:218`); `doctor.py` импортирует `canary` на уровне модуля
(проверено: ни один модуль, который `canary.py` импортирует
транзитивно, не импортирует `doctor` на уровне модуля — цикла нет).

Формат `pool.sealed` — решение разработчика (SPEC явно оставляет его на
усмотрение): первые 64 байта — hex ASCII тега HMAC-SHA256, дальше —
шифртекст целиком (без разделителя — фиксированная длина тега снимает
двусмысленность с байтом-переводом строки внутри шифртекста).
Сериализация пула в один payload — свой формат длина-префикс-имя/
длина-префикс-содержимое (`_serialize_pool`/`_deserialize_pool`), не
`tarfile`/`zipfile`: без временных меток/прав доступа, которые сделали
бы шифртекст менее предсказуемым без выигрыша (восстановление всё равно
идёт по именам файлов).

Расшифровка — ОДНА функция входа `canary._authorized_pool_payload`,
которую зовут ОБА пути: `restore_pool_if_missing` (реальное
восстановление, `init`/`doctor --restore`) и `pool_drift_warning`
(сверка `doctor` без флага, AC-8). Роль-отказ (`runner.
in_role_environment()`, новая функция рядом с `role_env()` — читает те
же два маркера, что тот выставляет процессу роли: `HOME`/
`CLAUDE_CONFIG_DIR` на курируемый слой) проверяется здесь один раз для
обоих путей — «второй, независимый от permissions.deny рубеж»
требования 5 действует даже если К пулу доберётся какой-то ещё код,
которому это не пришло в голову проверить самому. Аудит incident-алертом
(AC-14) — только у `restore_pool_if_missing` (аргумент `audit_conn`):
`pool_drift_warning` не кладёт расшифрованный пул на диск и звонится на
КАЖДОМ `doctor`, аудит-алерт на каждый такой вызов был бы шумом не по
адресу требования («аудит вызова команды расшифровки», не любого
internal-сравнения).

Манифест `canary/guids.txt` — `uuid.uuid4()` на каждый шаблон,
перезаписывается целиком на каждом `pool-seal` (AC-11), не дописывается.

CI-джоб `canary-guid-leak` (требование 6, AC-12) — защищённый путь,
диф-приложение ниже: второй шаг job'а сравнивает диф `skills/`/
`templates/`/`docs/` с содержимым `canary/guids.txt` ГОЛОВЫ ветки (не
нужен ключ расшифровки — сравнение по значениям GUID, не по
содержимому шаблонов), тем же приёмом (`grep -Ff`), что и
`id-format-greplint` использует `scripts/id_format_patterns.txt`.

### Правка по REVIEW.md итерации 1 (changes_requested)

Три major-замечания (R1-F1, R1-F2, R1-F3) закрыты в этой итерации,
R1-F4 (minor) — донесён отдельно (см. «Предложения системе»), код не
требовал правки:

- **R1-F1** (ключ пула виден в argv `openssl` через `ps`/`ps aux`) —
  `_openssl_encrypt`/`_openssl_decrypt` переведены на `-pass fd:N`
  (файловый дескриптор пайпа, `subprocess.run(..., pass_fds=(fd,))`),
  не `-pass pass:{key}` литералом; закрыто ПОЛНОСТЬЮ для ключа
  шифрования пула (проверено эмпирически на локальной LibreSSL,
  закреплено регресс-тестом `OpensslSecretPassingTest`). Для
  `_hmac_tag_hex` (MAC-ключ, `openssl dgst -hmac`) технической
  альтернативы НЕТ: `openssl dgst -help` не несёт fd/env-аналога
  `-passin` для опции `-hmac`, а `openssl mac` (OpenSSL 3.x, несёт
  `-macopt`) на этой машине (LibreSSL) отсутствует вовсе — оба факта
  проверены эмпирически в этом же шаге. Локальный приёмочный тест
  `test_pool_seal.py::test_ac1_...` (залочен — developer его не
  правит) буквально требует подстроку `-hmac` в argv вызова `openssl
  dgst`, что структурно требует передачи ключа аргументом. Остаточный
  риск сужен производным MAC-ключом (не равен ключу шифрования пула,
  ANSWER-1 п.1) — утечка позволила бы подделать тег целостности, не
  расшифровать пул. Решение о судьбе остатка (принять риск / отдельная
  задача на правку локальной планки test_author'ом) — за
  ревьювером/Оператором, зафиксировано в реестре замечаний REVIEW.md.
- **R1-F2** (`pool_drift_warning` без фильтра `.md` — ложное
  предупреждение AC-8 на постороннем файле типа `.DS_Store`) —
  применён тот же фильтр `p.suffix == ".md"`, что и `cmd_pool_seal`;
  добавлен регресс-тест
  `test_foreign_non_md_file_in_pool_dir_is_not_a_false_drift`.
- **R1-F3** (нет заявки «Ловит мутацию: …» в 6 классах трёх файлов
  `tests/*.py`) — дописана заявка во всех шести классах/их методах.

## Шаги

1. `orchestrator/config.py`: константа `CANARY_POOL_KEY_SLOT`. Низкоуровневые
   крипто-примитивы в `orchestrator/canary.py`: `_mac_key`, `_hmac_tag_hex`
   (`openssl dgst -sha256 -hmac`), `_openssl_encrypt`/`_openssl_decrypt`
   (`openssl enc -aes-256-cbc -pbkdf2`), `_serialize_pool`/`_deserialize_pool`.
2. `cmd_pool_seal()` (AC-1, AC-3, AC-4) + манифест GUID (AC-9..AC-11);
   CLI-диспетчер `_cmd_canary` в `orchestrator/artel.py` (маршрутизирует
   `pool-seal` до разбора `--k`), обновлён usage/докстринг.
3. Единая точка расшифровки `_authorized_pool_payload` (тег ДО
   расшифровки — AC-1 тампер-случай; ключ из keychain — AC-2; отказ
   `role_env` — AC-15) + `restore_pool_if_missing`; подключение к
   `catalog.cmd_init()` (AC-5) и `doctor.cmd_doctor(restore=True)`
   (AC-6); no-op при уже существующем каталоге до обращения к keychain
   (AC-7, закреплено юнит-тестом).
4. `pool_drift_warning`/`doctor.check_canary_pool_drift`, регистрация в
   `doctor.all_checks()` (AC-8).
5. Изоляция роли: `runner.in_role_environment()`; 4 литерала
   `permissions.deny` в `docs/reference/role-home/claude/settings.json`
   (AC-13, файл НЕ защищённый путь — правит developer напрямую, как и
   часть 1); аудит incident-алертом вызова восстановления (AC-14).
6. Юнит-тесты разработчика: `tests/test_canary.py` (сериализация,
   `_mac_key`, рубеж role_env до keychain, no-op restore),
   `tests/test_new_argv_parsing.py` (маршрутизация `pool-seal`/`--k`),
   `tests/test_doctor_canary_pool.py` (`check_canary_pool_drift`, три
   исхода). Полная локальная приёмочная планка (19 тестов, все AC кроме
   AC-12/AC-18) прогнана и зелёная.
7. Диф-приложение `.github/workflows/ci.yml` (AC-12, требование 6) —
   защищённый путь, ниже; применяет Оператор отдельным шагом.

## Покрытие требований

| Требование (SPEC) | Шаг |
|---|---|
| 1 (шифрование openssl+PBKDF2+HMAC-SHA256, ключ в keychain) | 1, 3 |
| 2 (`canary pool-seal`) | 2 |
| 3 (восстановление `init`/`doctor --restore`, no-op при наличии каталога, предупреждение о расхождении) | 3, 4 |
| 4 (манифест GUID) | 2 |
| 5 (изоляция роли: запрет CLI, аудит incident, отказ role_env) | 3, 5 |
| 6 (CI-сторож читает манифест) | 7 (manual) |

## Влияние на систему

Новый код только ДОБАВЛЯЕТ: существующий `canary --k <N>` (v2 прогон
конвейера), `init`/`doctor` без пула, `role_env()` — поведение не
меняется (проверено прогоном `tests/test_canary.py`,
`tests/test_doctor.py`, `tests/test_doctor_canary_pool.py`,
`tests/test_catalog_status_log.py`, `tests/test_catalog_new_race.py`,
`tests/test_new_argv_parsing.py`, `tests/test_invariants.py`,
`tests/test_coldstart.py`, `tests/test_analyst_role.py`,
`tests/test_agent_prompt.py`, `tests/test_git_fixation.py`,
`tests/test_auto_cycle.py`, `tests/test_workspace.py`,
`tests/test_amend.py`, `tests/test_review_freshness.py`,
`tests/test_multitarget.py`, `tests/test_multitarget_invariants.py` —
все зелёные). `catalog.cmd_init()` получает один дополнительный вызов
(`canary.restore_pool_if_missing`) — безопасен для ~40 существующих
тестовых файлов, которые зовут `cmd_init()` на патченном `config.ROOT`:
`sealed_path()` там не существует, вызов возвращает `None` до
обращения к keychain (короткое замыкание проверено юнит-тестом
`RestorePoolIfMissingNoOpTest`).

Правка по REVIEW.md итерации 1 (fd-based `-pass`, фильтр `.md` в
`pool_drift_warning`) перепрогнана тем же списком модулей плюс полная
приёмочная планка задачи (19 тестов, файл за файлом) — все зелёные,
регрессий не внесено.

Ни один существующий тест/гейт/лимит/инвариант не ослаблен: 4 новых
литерала `permissions.deny` — расширение существующего запрета части 1
(тем же файлом, тем же ключом списка), не замена; новый CI-джоб —
дополнительная проверка, не отмена существующей. Ключ шифрования пула
нигде не появляется в репозитории/окружении роли — закреплено AC-17
(приёмочный тест, зелёный).

Откат — один MR: `git revert` кодового коммита; диф-приложение к
`ci.yml` (шаг 7) — отдельный коммит Оператора, откатывается независимо.

### Защищённый путь — дифф-приложение (для Оператора, `git apply --check` пройден)

**`.github/workflows/ci.yml`** (требование 6/AC-12 — новый шаг в
существующем job'е `canary-guid-leak`, сразу после уже существующего
шага «diff не добавляет отметку canary-guid…», тот же приём: diff
только новых строк, база — `github.event.before`/PR base):

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index ab0d1730..18571fad 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -101,6 +101,34 @@ jobs:
             echo "$ADDED"
             exit 1
           fi
+      - name: diff не добавляет значение GUID запечатанного пула в skills/, templates/, docs/
+        env:
+          BASE_SHA: ${{ github.event_name == 'pull_request' && github.event.pull_request.base.sha || github.event.before }}
+        run: |
+          if [ -z "$BASE_SHA" ] || [ "$BASE_SHA" = "0000000000000000000000000000000000000000" ] \
+             || ! git cat-file -e "$BASE_SHA" 2>/dev/null; then
+            echo "базы для диффа нет (новая ветка или принудительный пуш) — пропуск"
+            exit 0
+          fi
+          # SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 4/6: манифест
+          # canary/guids.txt — открытый список GUID запечатанного пула
+          # (ключа расшифровки в CI нет и не нужен — сравнение по
+          # значениям GUID, не по содержимому шаблонов). Появление
+          # любого значения манифеста в skills/, templates/ или docs/
+          # пульта — та же утечка контекста роли в пул, что и общий
+          # маркер canary-guid: выше, только по конкретному значению.
+          if [ ! -f canary/guids.txt ] || [ ! -s canary/guids.txt ]; then
+            echo "canary/guids.txt ещё нет или пуст — пропуск (пул ещё не запечатан)"
+            exit 0
+          fi
+          ADDED=$(git diff "$BASE_SHA"...HEAD -- 'skills/*' 'templates/*' 'docs/*' \
+            | grep -E '^\+' | grep -Ev '^\+\+\+' \
+            | grep -Ff <(grep -v '^[[:space:]]*$' canary/guids.txt) || true)
+          if [ -n "$ADDED" ]; then
+            echo "::error::диф добавляет значение GUID запечатанного пула канарейки в skills/, templates/ или docs/ — утечка (SPEC 01M1NSR5M5THYRC0RFWPMVE2DW, требование 4):"
+            echo "$ADDED"
+            exit 1
+          fi
 
   python:
     name: Синтаксис и тесты оркестратора
```

`git apply --check` подтверждение: диф перепроверен на ГОЛОВЕ ветки
задачи этой итерации (sha `9ebd9fa6` — после повторной подтяжки main,
включающей операторские коммиты `b81be635`/`952e846e`, применившие диф-
приложение части 1 к тому же файлу) командой `git apply --check
<файл-с-диффом>` → без вывода (успех) — хунк не зависит от участка
`ci.yml`, который трогали эти коммиты. Правка не тронула сам `canary/
guids.txt` не существующим до `pool-seal` — оба условия `[ ! -f ]`/
`[ ! -s ]` держат джоб no-op до первого боевого seal, тем же приёмом,
что часть 1 использовала для собственного джоба до появления пула.

## Риски

- `pool_drift_warning` расшифровывает пул НА КАЖДОМ вызове `doctor`
  (без флага), если и `~/.artel-canary`, и `canary/pool.sealed`
  существуют — расшифровка только в памяти (ничего не пишет на диск),
  но это более частый повод обратиться к keychain, чем «команда
  расшифровки», которую называет требование 5 буквально. Решение
  осознанное (см. «Подход»/докстринг `_authorized_pool_payload`) — если
  Оператор сочтёт это лишним поводом трогать keychain, дешёвая правка:
  кэшировать сравнение по mtime `pool.sealed`.
- Первый боевой `pool-seal` требует, чтобы Оператор вручную завёл слот
  keychain `artel-canary-pool-key` (`security add-generic-password`,
  тот же ручной шаг, что и токены ролей) — код только читает, ничего не
  создаёт; без слота `pool-seal`/восстановление отказывают именованно.
- Диф-приложение `ci.yml` (AC-12) — до применения Оператором джоб
  `canary-guid-leak` защищён только первой (частью 1) проверкой
  общего маркера `canary-guid:`, не значениями манифеста; тот же класс
  временного окна, что и у части 1 (её собственный джоб тоже дожидался
  отдельного применения Оператором).
- REVIEW.md итерации 1, R1-F1 (остаток): производный MAC-ключ
  (`_mac_key`) неизбежно виден в argv `openssl dgst -hmac` во время
  жизни подпроцесса `_hmac_tag_hex` — технической альтернативы нет
  (`openssl dgst`/`-hmac` не несёт fd/env-источника секрета, `openssl
  mac` в OpenSSL 3.x отсутствует на этой LibreSSL; оба факта проверены
  эмпирически), а локальный приёмочный тест `test_pool_seal.py`
  буквально требует эту литеральную форму вызова. Ключ шифрования пула
  (более ценная цель) этим НЕ затронут — переведён на `-pass fd:N`.
  Подробности и предложенные пути закрытия — реестр замечаний
  REVIEW.md, R1-F1.

## Предложения системе

- SPEC 01M1NSR5M5THYRC0RFWPMVE2DW («Оценка объёма и деление») не
  называет `orchestrator/runner.py` в зоне задачи, хотя реализация
  требования 5 (AC-15, отказ `role_env`) естественно легла именно туда
  (одна функция рядом с существующим `role_env()`, реализующим
  симметричную запись тех же маркеров) — REVIEW.md итерации 1, R1-F4.
  Стоит донести до аналиста/Оператора для сверки зоны SPEC на входе в
  `in_dev` (тот же класс, что и SPEC 01M1P9QAG65GVF69YJEV0V18D9).
