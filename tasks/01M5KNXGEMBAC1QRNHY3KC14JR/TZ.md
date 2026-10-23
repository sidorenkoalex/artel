---
task: 01M5KNXGEMBAC1QRNHY3KC14JR
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Признак утечки пула канарейки: путь внутри пула, GUID шаблона и имя каталога в командах роли

# Признак утечки пула канарейки — путь внутри пула, GUID шаблона и имя каталога в командах роли, а не голая подстрока `.artel-canary` в любом тексте лога

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-6 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок; переоткрытие — строка бэклога «Точный признак утечки пула канарейки (CR-2026-10-22-6)»; строка копилки 21.09 «Проверка утечки пула канарейки…» о ложных срабатываниях, остаток (б′) «ловить только реальные пути пула» не сделан). Ссылки сверены с `origin/main` 906f0732 и пином 89732e3e; `orchestrator/doctor/canary_pool.py` и `tests/test_doctor_canary_pool.py` между пином и `origin/main` не менялись.

- Проверка — `orchestrator/doctor/canary_pool.py:41` (`check_role_log_pool_leak`), вызов из `orchestrator/doctor/cli.py:146`. Признак — голая подстрока: `marker = doctor.config.CANARY_POOL_DIRNAME` (`orchestrator/doctor/canary_pool.py:73`), `if marker in text` (`:82`); на совпадение — incident-алерт `doctor.canary-pool-leak` с текстом «лог роли {name} упоминает каталог пула канарейки ({marker}) — утечка контекста роли …» (`:88`–`:92`) и статус `fail`.
- Отбор файлов — по форме имени `<задача>-<роль>-<N>.log` (`orchestrator/doctor/canary_pool.py:23`, `_ROLE_LOG_STEM`; `:33`, `_is_role_step_log`), записи сессий Оператора `*.session.log` не читаются (SPEC 01M3F7BYE8, требование 7). Сужение отбора по списку ролей противоречит этому требованию и тесту `tests/test_doctor_canary_pool.py:161` — не делается.
- Подстроку `.artel-canary` несут исходный код и документы пульта: `orchestrator/config.py:414` (`CANARY_POOL_DIRNAME = ".artel-canary"`), докстринги `` `~/.artel-canary` `` и `` `~/.artel-canary/*.md` ``, правило `deny Read(~/.artel-canary/**)` дома роли (`docs/stack.md:577`), строки `docs/backlog.md` с «~/.artel-canary» в тексте; и постоянный дом Codex канарейки `~/.artel-canary-codex` (`orchestrator/canary.py:516`, `_canary_profile_home`). Роль, прочитавшая код или бэклог, попадает под проверку без всякой утечки.
- Замер 23.10 (чтение каталога `.artel/logs` главной копии): голую подстроку несут 82 файла `*.log` и 2829 из 3943 промптов `*.prompt.txt`; путь внутри пула от домашнего каталога (`~/.artel-canary/<имя>`, `$HOME/.artel-canary/<имя>`, абсолютный путь домашнего каталога + `/.artel-canary/<имя>`) — 0 логов шагов ролей; абсолютный путь каталога пула — только 2 записи сессий Оператора (`*.session.log`, не читаются); значения меток `canary-guid:` шаблонов открытого пула — 0 файлов. Алертов `doctor.canary-pool-leak` в БД 61, без подтверждения 57.
- Открытый пул — `Path.home() / config.CANARY_POOL_DIRNAME` (`orchestrator/pool_seal.py:34`, `_pool_dir`), файлы `*.md`. Каждый шаблон пула несёт метку `canary-guid: <значение>` HTML-комментарием (формат — докстринг `orchestrator/canary.py:43`); сейчас все 6 шаблонов открытого пула несут по одной метке. Расшифровка и чтение пула запрещены процессу роли (`runner.in_role_environment`, `orchestrator/pool_seal.py:185`, `_authorized_pool_payload`); команда `doctor` без `--fix`/`--restore` роли разрешена (`orchestrator/artel.py:2107`, `_ROLE_REFUSED_FLAGS`).
- Манифест `canary/guids.txt` (`orchestrator/pool_seal.py:351`: `guids = [str(uuid.uuid4()) for _ in files]`) — случайные значения, создаваемые при каждом `pool-seal`; меткам `canary-guid:` шаблонов они не равны (сверка 23.10: 0 из 6 меток в манифесте). Источником значений GUID для проверки манифест быть не может.
- Существующие тесты `tests/test_doctor_canary_pool.py::RoleLogPoolLeakCheckTest` закладывают утечку строкой пути внутри пула: `~/{config.CANARY_POOL_DIRNAME}/x.md` (`:65`, `:76`, `:175`), `ls ~/{marker}/templates` (`:94`–`:101`) и проверяют, что текст алерта называет `config.CANARY_POOL_DIRNAME` (`:71`, `:137`). Признак требования 1а их ловит — тесты не меняются.
- Строки вызовов инструментов в логе шага роли начинаются с `· ` у обоих провайдеров (`orchestrator/providers/claude.py:63`, `orchestrator/providers/codex.py:315`, `TOOL_CALL_LINE_PREFIX`); аргумент вызова обрезан до 100 знаков (`TOOL_ARGUMENT_LIMIT`, `claude.py:61`, `codex.py:316`). Остальной текст лога — ответы и рассуждения роли, в том числе пересказ прочитанного кода. Замер 23.10: из 80 логов шагов ролей с голой подстрокой только в одном она стоит в строке вызова (`git grep` по тексту правила `deny`), в 79 — в прочем тексте.
- Решение Оператора 23.10 (вариант Б): голое упоминание каталога пула остаётся признаком, но только в строках вызовов инструментов роли — то, что роль сама сделала с каталогом; в прочем тексте лога — нет.
- Защита, которую задача сохраняет: сама проверка (SPEC 01M1NEEWH5, требование 13б) — после шага роли, для обоих провайдеров; для роли на Codex это единственный рубеж (`docs/stack.md:577`: правил `deny` на чтение у `codex exec` нет).

## Требования

1. Признак утечки в логе шага роли — любое из четырёх:
   а) путь внутри пула от домашнего каталога: `~/`, `$HOME/`, `${HOME}/` или `str(Path.home())` + `/` перед `config.CANARY_POOL_DIRNAME`, затем `/` и знак имени (`[A-Za-z0-9_]`), например `~/<CANARY_POOL_DIRNAME>/x.md`, `ls ~/<CANARY_POOL_DIRNAME>/templates`;
   б) абсолютный путь каталога пула `str(Path.home() / config.CANARY_POOL_DIRNAME)`, за которым конец текста или знак не из `[A-Za-z0-9_.-]`;
   в) значение любой метки `canary-guid: <значение>` из файлов `*.md` открытого пула `Path.home() / config.CANARY_POOL_DIRNAME`; значение — непрерывная последовательность знаков без пробелов после `canary-guid:` и пробелов, без закрывающего `-->`;
   г) в строке лога, начинающейся с префикса вызова инструмента (`orchestrator/providers/claude.py:63`, `TOOL_CALL_LINE_PREFIX`; у Codex тот же текст префикса — признак берёт значение из модуля провайдера, а не литерал), подстрока `config.CANARY_POOL_DIRNAME`, за которой конец строки или знак не из `[A-Za-z0-9_-]` (например `· Bash ls ~/<CANARY_POOL_DIRNAME>`, `· Read ~/<CANARY_POOL_DIRNAME>`); `~/.artel-canary-codex` в строке вызова признаком не является.
   Голая подстрока `config.CANARY_POOL_DIRNAME` вне строк вызовов признаком больше не является. Не признак (в строке, не начинающейся с префикса вызова): строка `CANARY_POOL_DIRNAME = ".artel-canary"`, `` `~/.artel-canary` ``, `` `~/.artel-canary/*.md` ``, `Read(~/.artel-canary/**)`, `~/.artel-canary-codex/auth.json`, `/x/.artel/worktrees/T1/.artel-canary/y.py` (каталог с тем же именем не в домашнем каталоге), слово `canary-guid:` без значения из пула.
2. Значения меток (1в) читаются только вне окружения роли: при `doctor.runner.in_role_environment()` файлы пула не открываются, признаки 1а, 1б и 1г проверяются, деталь проверки называет «GUID шаблонов не сверялись: процесс роли». Пула нет (каталог не развёрнут) — признаки 1а, 1б и 1г проверяются, деталь называет «GUID шаблонов не сверялись: открытый пул не развёрнут»; статус по логам — как обычно.
3. Значения GUID не попадают ни в текст алерта, ни в `Check.detail`, ни в вывод: срабатывание по 1в называет файл лога и вид признака («GUID шаблона пула канарейки»), а текст алерта называет `config.CANARY_POOL_DIRNAME`. Текст алерта по признакам 1а, 1б и 1г — прежний побайтно (дедупликация `alerts.raise_alert` с открытыми алертами по тому же файлу не ломается); по признаку 1в — свой постоянный текст на файл. Лог, давший и признак 1в, и любой из 1а, 1б, 1г, поднимает оба алерта.
4. Шаблон открытого пула без метки `canary-guid:` — статус проверки не ниже `warn` с именем файла шаблона (не содержимым): утечку его содержимого признак 1в не увидит. Алерт на это не поднимается. При утечке в логах статус `fail`, как прежде.
5. Отбор файлов, исключение `*.session.log` до чтения, отсутствие `_auto_ack_gone`, тип и источник алерта (`incident`, `doctor.canary-pool-leak`) — без изменений.
6. Тесты, детерминированные, без сети, с подменой `Path.home` на временный каталог (`mock.patch.object(Path, "home", …)`, как в `CanaryPoolDriftCheckTest`), `doctor.runner.in_role_environment` и `config.LOGS`/`config.DB`/`config.ROOT`:
   - лог шага роли, несущий только строки «не признак» требования 1, — статус `ok`, алертов нет (на текущем коде — красный: `fail` и алерт);
   - лог шага роли с `~/.artel-canary-codex/auth.json` — `ok`, в том числе в строке вызова `· Bash cat ~/.artel-canary-codex/auth.json` (на текущем коде — красный);
   - строка вызова `· Bash ls ~/<CANARY_POOL_DIRNAME>` (префикс собирается из `TOOL_CALL_LINE_PREFIX`, имя — из `config.CANARY_POOL_DIRNAME`) — `fail`, один incident-алерт с прежним текстом; та же подстрока в строке без префикса вызова — `ok`;
   - лог шага роли без имени каталога пула, несущий значение метки `canary-guid:` шаблона временного пула, — `fail`, один incident-алерт, текст алерта и `Check.detail` не содержат значения GUID (на текущем коде — красный: `ok`);
   - тот же лог при `in_role_environment() == True` — файлы `*.md` пула не читаются (слежка за `Path.read_text`, `Path.read_bytes` и `builtins.open`, как `read_names` в `tests/test_doctor_canary_pool.py`), деталь называет «процесс роли»;
   - строка `текст · Bash ls ~/<CANARY_POOL_DIRNAME>` (префикс вызова не в начале строки) — `ok`; `str(Path.home())` + `/<CANARY_POOL_DIRNAME>-codex/auth.json` — `ok`;
   - лог с абсолютным путём каталога пула и пробелом после — `fail`; с `str(Path.home())` + `/<CANARY_POOL_DIRNAME>/x.md` — `fail`;
   - пул не развёрнут — признаки 1а и 1б работают, деталь называет «открытый пул не развёрнут»;
   - шаблон пула без метки — статус `warn` с именем файла, деталь не содержит текста шаблона, алертов нет;
   - сторож дерева: ни один отслеживаемый git файл в каталогах `orchestrator`, `scripts`, `skills`, `templates` и `tests` не содержит литерала признака 1а с префиксом `~/`, `$HOME/` или `${HOME}/` — образцы утечки в тестах собираются из `config.CANARY_POOL_DIRNAME` во время прогона, а не пишутся литералом.
   Утверждения существующих тестов `tests/test_doctor_canary_pool.py` не меняются; в `setUp` класса `RoleLogPoolLeakCheckTest` добавляется только подмена `Path.home` на временный каталог (тест не читает настоящий пул Оператора); тесты остаются зелёными.

Зоны: orchestrator/doctor/canary_pool.py, tests/

Ограничение зон по смыслу: в `orchestrator/doctor/canary_pool.py` — только `check_role_log_pool_leak` и новые вспомогательные функции признаков; `check_canary_pool_drift`, `check_token_repo_scope`, `check_canary_trigger`, `check_canary_live` не меняются.

Только чтение: orchestrator/providers/claude.py, orchestrator/providers/codex.py (`TOOL_CALL_LINE_PREFIX`, `TOOL_ARGUMENT_LIMIT` — не меняются), orchestrator/config.py (`CANARY_POOL_DIRNAME` — не меняется), orchestrator/pool_seal.py (`_pool_dir`, манифест — не меняются), orchestrator/canary.py, orchestrator/runner.py (`in_role_environment`), orchestrator/alerts.py, orchestrator/doctor/__init__.py, orchestrator/doctor/cli.py (вызывающий проверку — не меняется), orchestrator/providers/base.py (читает `CANARY_POOL_DIRNAME` — не меняется), orchestrator/artel.py, docs/stack.md, docs/backlog.md, .github/workflows/ci.yml (защищённый путь; джоб `canary-guid-leak` — не меняется).

Не входит: подтверждение 57 открытых алертов `doctor.canary-pool-leak` (разовый `alert-ack` Оператора — строка очереди Оператора по ревизии 22.10); проверка промптов ролей `*.prompt.txt` (3943 файла, 40–95 КиБ — место такой проверки при сборке промпта, отдельная задача); имя репозитория пула как третий сигнал требования 13б; расхождение манифеста `canary/guids.txt` с метками шаблонов и сторожа CI по нему (решение Оператора о формате манифеста); упоминание каталога в той части аргумента вызова, которая обрезана пределом 100 знаков (`TOOL_ARGUMENT_LIMIT` не меняется); правка строки `docs/stack.md:577` о признаке — приложением Оператора после мержа.

Бюджет: $20.
