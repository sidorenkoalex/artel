---
task: 01M5KNXGEMBAC1QRNHY3KC14JR
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/doctor/canary_pool.py, tests/
budget_usd: 25
---

# SPEC: Признак утечки пула канарейки — путь внутри пула, GUID шаблона и имя каталога в строках вызовов роли

## Контекст
Проверка `check_role_log_pool_leak` (`orchestrator/doctor/canary_pool.py:41`, вызов из `orchestrator/doctor/cli.py:146`) считает утечкой голую подстроку `config.CANARY_POOL_DIRNAME` (`.artel-canary`) в любом месте лога шага роли (`canary_pool.py:73`, `:82`) и поднимает incident-алерт `doctor.canary-pool-leak` со статусом `fail`. Ту же подстроку несут код и документы пульта (`orchestrator/config.py:414`, докстринги, правило `deny Read(~/.artel-canary/**)` в `docs/stack.md:577`, `docs/backlog.md`) и дом Codex канарейки `~/.artel-canary-codex` (`orchestrator/canary.py:516`). Поэтому роль, прочитавшая код, попадает под проверку без всякой утечки. Замер 23.10: подстроку несут 82 лога, а реальных путей внутри пула в логах шагов ролей — 0; в БД 61 алерт, из них 57 без подтверждения. Находка ревизии CR-2026-10-22-6.

Решение Оператора 23.10 (вариант Б): голое упоминание каталога пула остаётся признаком только в строках вызовов инструментов роли. В прочем тексте лога признаком служат путь внутри пула и GUID шаблона. Сужение признака оформлено поправкой Оператора к ADR-0017 от 23.10.2026 («Поправка 23.10.2026: признак утечки пула канарейки», `docs/adr/0017-role-providers.md`; в origin уходит через `doc-commit`, сейчас удержана окном мержа). Сама проверка (SPEC 01M1NEEWH5, требование 13б) сохраняется: для роли на Codex она единственный рубеж (`docs/stack.md:577`).

## Требования

1. Признак утечки в логе шага роли — любое из четырёх:
   а) путь внутри пула от домашнего каталога: `~/`, `$HOME/`, `${HOME}/` или `str(Path.home())` + `/` перед `config.CANARY_POOL_DIRNAME`, затем `/` и знак имени (`[A-Za-z0-9_]`), например `~/<CANARY_POOL_DIRNAME>/x.md`, `ls ~/<CANARY_POOL_DIRNAME>/templates`;
   б) абсолютный путь каталога пула `str(Path.home() / config.CANARY_POOL_DIRNAME)`, за которым конец текста или знак не из `[A-Za-z0-9_.-]`;
   в) значение любой метки `canary-guid: <значение>` из файлов `*.md` открытого пула `Path.home() / config.CANARY_POOL_DIRNAME`. Значение — непрерывная последовательность знаков без пробелов после `canary-guid:` и пробелов, без закрывающего `-->`. Метка с пустым значением — за двоеточием сразу `-->`, перевод строки или конец текста — значения не даёт: пустое значение признаком не является, а шаблон без других меток считается шаблоном без метки (требование 4);
   г) в строке лога, начинающейся с префикса вызова инструмента (`TOOL_CALL_LINE_PREFIX`, `orchestrator/providers/claude.py:63`; у Codex тот же текст префикса, `orchestrator/providers/codex.py:315`; признак берёт значение из модуля провайдера, а не литерал), подстрока `config.CANARY_POOL_DIRNAME`, за которой конец строки или знак не из `[A-Za-z0-9_-]` (например `· Bash ls ~/<CANARY_POOL_DIRNAME>`, `· Read ~/<CANARY_POOL_DIRNAME>`). `~/.artel-canary-codex` в строке вызова признаком не является.
   Голая подстрока `config.CANARY_POOL_DIRNAME` вне строк вызовов признаком больше не является. Не признак (в строке, не начинающейся с префикса вызова): строка `CANARY_POOL_DIRNAME = ".artel-canary"`, `` `~/.artel-canary` ``, `` `~/.artel-canary/*.md` ``, `Read(~/.artel-canary/**)`, `~/.artel-canary-codex/auth.json`, `/x/.artel/worktrees/T1/.artel-canary/y.py` (каталог с тем же именем не в домашнем каталоге), слово `canary-guid:` без значения из пула.
2. Значения меток (1в) читаются только вне окружения роли. При `doctor.runner.in_role_environment()` файлы пула не открываются, признаки 1а, 1б и 1г проверяются, а `Check.detail` называет «GUID шаблонов не сверялись: процесс роли». Если открытого пула нет (каталог не развёрнут), признаки 1а, 1б и 1г тоже проверяются, `Check.detail` называет «GUID шаблонов не сверялись: открытый пул не развёрнут»; статус по логам — как обычно.
   Известное ограничение (решение Оператора на гейте SPEC 23.10.2026): под `in_role_environment()` `Path.home()` возвращает дом роли (`HOME` = `config.ROLE_HOME`, `orchestrator/providers/claude.py:223`). Поэтому форма 1а с `str(Path.home())` и признак 1б в этом режиме сверяют каталог в доме роли, а не пул Оператора. Абсолютный путь пула Оператора в обычном тексте лога там не ловится — рубеж для него `doctor` Оператора после шага. Формы `~/`, `$HOME/`, `${HOME}/` признака 1а и признак 1г от `Path.home()` не зависят и работают в обоих режимах.
3. Значения GUID не попадают ни в текст алерта, ни в `Check.detail`, ни в вывод. Срабатывание по 1в называет файл лога и вид признака («GUID шаблона пула канарейки»), текст алерта называет `config.CANARY_POOL_DIRNAME`. Текст алерта по признакам 1а, 1б и 1г — прежний побайтно, чтобы не ломалась дедупликация `alerts.raise_alert` с открытыми алертами по тому же файлу. У признака 1в свой постоянный текст на файл. Лог, давший и признак 1в, и любой из 1а, 1б, 1г, поднимает оба алерта.
4. Шаблон открытого пула без метки `canary-guid:` — в том числе с единственной меткой пустого значения (требование 1в) — даёт статус проверки не ниже `warn` с именем файла шаблона (не содержимым) в `Check.detail`. Алерт на это не поднимается. При утечке в логах статус `fail`, как прежде.
5. Без изменений: отбор файлов по форме имени `<задача>-<роль>-<N>.log` (`_ROLE_LOG_STEM`, `_is_role_step_log`), исключение `*.session.log` до чтения, отсутствие `_auto_ack_gone`, тип и источник алерта (`incident`, `doctor.canary-pool-leak`).
6. Тесты детерминированные, без сети, с подменой `Path.home` на временный каталог (`mock.patch.object(Path, "home", …)`, как в `CanaryPoolDriftCheckTest`), `doctor.runner.in_role_environment` и `config.LOGS`/`config.DB`/`config.ROOT`. Образцы утечки собираются из `config.CANARY_POOL_DIRNAME` и `TOOL_CALL_LINE_PREFIX` во время прогона, а не пишутся литералом. В `setUp` класса `RoleLogPoolLeakCheckTest` (`tests/test_doctor_canary_pool.py`) добавляется только подмена `Path.home` на временный каталог. Утверждения существующих тестов этого файла не меняются; мандат на эту правку не нужен (решение Оператора на гейте SPEC 23.10.2026).

## Критерии приёмки

AC-1. Лог шага роли, несущий только строки «не признак» требования 1 (`CANARY_POOL_DIRNAME = ".artel-canary"`, `` `~/.artel-canary` ``, `` `~/.artel-canary/*.md` ``, `Read(~/.artel-canary/**)`, `~/.artel-canary-codex/auth.json`, `/x/.artel/worktrees/T1/.artel-canary/y.py`, `canary-guid:` без значения из пула), а также строку `текст · Bash ls ~/<CANARY_POOL_DIRNAME>` (префикс вызова не в начале строки) и `str(Path.home())` + `/<CANARY_POOL_DIRNAME>-codex/auth.json`, — статус `ok`, алертов нет (на текущем коде — `fail` и алерт).

AC-2. Строка вызова `· Bash cat ~/<CANARY_POOL_DIRNAME>-codex/auth.json` (префикс из `TOOL_CALL_LINE_PREFIX`) — статус `ok`, алертов нет (на текущем коде — `fail`).

AC-3. Строка вызова `<TOOL_CALL_LINE_PREFIX>Bash ls ~/<CANARY_POOL_DIRNAME>` (конец строки после имени каталога) — статус `fail`, ровно один incident-алерт `doctor.canary-pool-leak` с прежним побайтно текстом. Та же подстрока `ls ~/<CANARY_POOL_DIRNAME>` в строке без префикса вызова — статус `ok`, алертов нет.

AC-4. В строках без префикса вызова каждая из форм даёт статус `fail` с прежним побайтно текстом алерта (каждая — отдельным логом):
- абсолютный путь каталога пула `str(Path.home() / CANARY_POOL_DIRNAME)` с пробелом после;
- `str(Path.home())` + `/<CANARY_POOL_DIRNAME>/x.md`;
- `$HOME/<CANARY_POOL_DIRNAME>/x.md`;
- `${HOME}/<CANARY_POOL_DIRNAME>/x.md`.

AC-5. Лог шага роли без имени каталога пула, несущий значение метки `canary-guid:` шаблона временного открытого пула, даёт статус `fail` и ровно один incident-алерт `doctor.canary-pool-leak` (на текущем коде — `ok`). Ни текст алерта, ни `Check.detail` не содержат значения GUID; деталь называет файл лога и «GUID шаблона пула канарейки», текст алерта называет `config.CANARY_POOL_DIRNAME`. Кроме того:
- лог, несущий и значение GUID, и признак 1а, поднимает два алерта;
- два прогона проверки над одним и тем же логом с GUID оставляют ровно один открытый алерт по этому файлу;
- в пуле два шаблона, у каждого своя метка: лог со значением метки второго шаблона — `fail`;
- шаблон с двумя метками: лог со значением второй метки — `fail`.

AC-6. Тот же лог, что в первом предложении AC-5, при `in_role_environment() == True`: файлы `*.md` пула не читаются (слежка за `Path.read_text`, `Path.read_bytes` и `builtins.open`, как `read_names` в `tests/test_doctor_canary_pool.py`), а `Check.detail` содержит «GUID шаблонов не сверялись: процесс роли». В этом режиме формы `~/`, `$HOME/`, `${HOME}/` признака 1а и признак 1г (строка вызова `<TOOL_CALL_LINE_PREFIX>Bash ls ~/<CANARY_POOL_DIRNAME>`) дают `fail`.

AC-7. Открытый пул не развёрнут (каталога `Path.home() / CANARY_POOL_DIRNAME` нет): признаки 1а и 1б дают `fail`, `Check.detail` содержит «GUID шаблонов не сверялись: открытый пул не развёрнут».

AC-8. Шаблон открытого пула `*.md` без метки `canary-guid:` при чистых логах даёт статус `warn`; `Check.detail` называет имя файла шаблона и не содержит его текста; алертов нет. При утечке в логах статус `fail`. Шаблон, чья единственная метка пуста (за `canary-guid:` сразу `-->`, перевод строки или конец текста), считается шаблоном без метки: `warn` с именем файла. Для такого шаблона любой лог шага роли без признаков 1а, 1б, 1г не даёт ни `fail`, ни алерта.

AC-9. Сторож дерева: ни один отслеживаемый git файл в каталогах `orchestrator`, `scripts`, `skills`, `templates` и `tests` не содержит литерала признака 1а с префиксом `~/`, `$HOME/` или `${HOME}/` (на ветке-основе `git grep` по этому образцу пуст).

## Оценка объёма и деление
Сигналов нет: 2 зоны, 9 критериев приёмки, `budget_usd` 25. Секция для сведения.

## Не входит
- Подтверждение 57 открытых алертов `doctor.canary-pool-leak` — разовый `alert-ack` Оператора (очередь Оператора по ревизии 22.10).
- Проверка промптов ролей `*.prompt.txt` — место такой проверки при сборке промпта, отдельная задача.
- Имя репозитория пула как третий сигнал требования 13б.
- Расхождение манифеста `canary/guids.txt` с метками шаблонов и сторож CI по нему (решение Оператора о формате манифеста); манифест источником значений GUID не служит.
- Упоминание каталога в части аргумента вызова, обрезанной пределом `TOOL_ARGUMENT_LIMIT` (100 знаков, не меняется).
- Источник дома Оператора для формы 1а с `str(Path.home())` и признака 1б под `in_role_environment()` — известное ограничение требования 2, рубеж — `doctor` Оператора.
- Правка строки `docs/stack.md:577` о признаке — приложением Оператора после мержа.
- Сужение отбора логов по списку ролей (противоречит SPEC 01M3F7BYE8, требование 7, и тесту `tests/test_doctor_canary_pool.py:161`).
- В `orchestrator/doctor/canary_pool.py` меняются только `check_role_log_pool_leak` и новые вспомогательные функции признаков; `check_canary_pool_drift`, `check_token_repo_scope`, `check_canary_trigger`, `check_canary_live` не меняются.
- Только чтение: `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py` (`TOOL_CALL_LINE_PREFIX`, `TOOL_ARGUMENT_LIMIT`), `orchestrator/config.py` (`CANARY_POOL_DIRNAME`), `orchestrator/pool_seal.py` (`_pool_dir`, манифест), `orchestrator/canary.py`, `orchestrator/runner.py` (`in_role_environment`), `orchestrator/alerts.py`, `orchestrator/doctor/__init__.py`, `orchestrator/doctor/cli.py`, `orchestrator/providers/base.py`, `orchestrator/artel.py`, `docs/stack.md`, `docs/backlog.md`, `docs/adr/0017-role-providers.md`, `.github/workflows/ci.yml` (джоб `canary-guid-leak` не меняется).
- Зелёный полный набор `tests/` (существующие тесты `tests/test_doctor_canary_pool.py` остаются зелёными) — её держит пульт.

## Материалы
- ТЗ: `tasks/01M5KNXGEMBAC1QRNHY3KC14JR/TZ.md` (факты сверены Оператором с `origin/main` 906f0732 и пином 89732e3e).
- Аудит SPEC круга 1: `tasks/01M5KNXGEMBAC1QRNHY3KC14JR/SPEC-AUDIT.md` (вердикт `concerns`); решения Оператора по нему на гейте SPEC 23.10.2026 внесены: требование 1в и AC-8 — пустая метка; требование 2, AC-6 и «Не входит» — дом роли; AC-4 — формы `$HOME/`, `${HOME}/`; AC-5 — постоянство текста алерта 1в и «любая метка»; «Контекст» — поправка к ADR-0017.
- Существующие тесты `tests/test_doctor_canary_pool.py::RoleLogPoolLeakCheckTest` закладывают утечку путём внутри пула (`~/{config.CANARY_POOL_DIRNAME}/x.md`, `ls ~/{marker}/templates`) — признак 1а их ловит.
- Бюджет: ТЗ называет $20, это ниже пола калибровки `config.BUDGET_CALIBRATION_FLOOR_USD = 25.0` (`orchestrator/config.py:654`) и правила скила «планка не ниже $25». Поставлен пол $25, Оператор принял его на гейте SPEC 23.10.2026.
