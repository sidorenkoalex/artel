---
task: 01M3XTF5506GF43HD51ECE230T
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Признак «процесс — шаг роли» не снимается ролью, и команды Оператора отказывают вызову из-под роли

# ТЗ: Признак «процесс — шаг роли» не снимается ролью, и команды Оператора отказывают вызову из-под роли

Источник: ревизия 02.10.2026 задачи 01M3SE87R3M7HGWX8HG1ANAKR0 (признак
шага роли для обоих провайдеров); `docs/retro/01M3SE87R3M7HGWX8HG1ANAKR0.md`.

Факты (origin/main 83a9c96e):
- Признак шага роли — `runner.in_role_environment()`
  (`orchestrator/runner.py:878-889`): истина, если `ARTEL_ROLE` непуст,
  ЛИБО одновременно `HOME == config.ROLE_HOME` и
  `CLAUDE_CONFIG_DIR == config.ROLE_CONFIG_DIR`. Маркер `ARTEL_ROLE` ставит
  `runner.role_env()` (`orchestrator/runner.py:869-870`); процесс роли
  снимает его сам одной приставкой к команде: `env -u ARTEL_ROLE …` или
  `ARTEL_ROLE= …`.
- Резервная пара работает только у Claude: `ClaudeProvider.environment`
  ставит `HOME` и `CLAUDE_CONFIG_DIR` (`orchestrator/providers/claude.py:188-191`),
  `CodexProvider.environment` — `HOME`, `CODEX_HOME`, `ZDOTDIR`, без
  `CLAUDE_CONFIG_DIR` (`orchestrator/providers/codex.py:465-469`). Шаг Codex
  со снятым маркером признаком не распознаётся вовсе. `HOME` у шагов обоих
  провайдеров равен `str(config.ROLE_HOME)`.
- Пустой маркер считается «не роль», и это закреплено долгоживущим тестом:
  `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`, `test_ac1`,
  последнее утверждение (`{"HOME": "/tmp/operator", ARTEL_ROLE: ""}` → ложь);
  файл заперт `tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests/long_lived.sha256.txt`.
  Правило «`HOME == ROLE_HOME` достаточно» этому утверждению НЕ противоречит
  (там `HOME` чужой); правило «маркер присутствует, даже пустой, — роль»
  противоречит.
- Второе определение признака: `artel._refuse_if_role_restricted`
  (`orchestrator/artel.py:1292-1299`) смотрит ТОЛЬКО на непустой
  `ARTEL_ROLE`, без `in_role_environment`. Через него отказывают
  (`_role_restricted_command`, `orchestrator/artel.py:1267-1289`): `init`,
  `observe register|add|remove|stop`, `watch --observation`,
  `hook-migrate apply|restore`, `run`/`auto` БЕЗ `--attach`,
  `doctor --restore`, `canary pool-seal`.
- Через общий признак `in_role_environment()` внутри самих команд отказывают:
  `answer` в состояниях `in_dev`/`review` (`orchestrator/answer.py:161-165`),
  `zones-extend` (`orchestrator/answer.py:223`), `note`
  (`orchestrator/notes.py:1178`), `doc-commit` (`orchestrator/notes.py:1294`),
  расшифровка пула канарейки (`orchestrator/pool_seal.py:198`).
- Отказа из-под роли НЕТ ни по одному признаку (таблица диспетчера
  `orchestrator/artel.py:1310-1360`): `new`, `advance`, `workspace`,
  `run --attach`, `auto --attach`, `stop`, `approve`, `reject`, `answer` в
  `escalated` (`orchestrator/answer.py:159-160`), `kill`, `release`,
  `pause`, `resume`, `budget`, `target-init`, `doctor --fix`, `alert-ack`,
  `canary` (запуск прогона), `prune --execute`, `amend-tests`, `ci-rerun`,
  `pin-update`, `pin --to`, `zone-release`, `zone-reorder`, `venv-sync`.
  Расхождение с ревизией: `run`/`auto` без `--attach` отказ уже имеют, с
  `--attach` — нет.
- Читающие команды, которыми роли пользуются штатно: `status`
  (`skills/code-revision.md:33`), а также `show`, `log`, `version`,
  `models`, `report`, голый `doctor`, `watch` без `--observation`,
  `acceptance-dry-run` (по `orchestrator/dry_run.py` — только чтение).
  Голый `doctor` под ролью разрешён тестом
  `tests/test_artel_role_restricted_commands.py::test_bare_doctor_runs_under_role`.
- Пульт сам вызывает команды в двух видах, и оба идут из окружения
  Оператора, не роли: отвязанный `run`/`auto` порождает себя с `--attach`
  (`orchestrator/artel.py:703-713`, окружение процесса пульта); ведение
  канарейки (`orchestrator/canary_drive.py`, запуск
  `orchestrator/canary.py:2068-2075`, `env = {**os.environ}`) зовёт
  `catalog.cmd_new`, `auto.cmd_auto`, `fsm._cmd_approve` прямыми вызовами
  функций, минуя `artel.main`. `auto` зовёт `run`/`advance` тоже вызовами
  функций. `runner.role_env(None)` (без роли, `HOME == ROLE_HOME`, без
  `ARTEL_ROLE`) используют только проверки `doctor`
  (`orchestrator/doctor/preflight.py:79` и др.), команд пульта они не
  исполняют.
- Шаг роли, запускающий тесты, наследует `ARTEL_ROLE` и `HOME` роли. Тесты,
  которые зовут `artel.main()` с командами, получающими отказ по этому ТЗ:
  `tests/test_analyst_role.py:355` (`new`),
  `tests/test_approve_acceptance_full_suite.py:265` (`approve`),
  `tests/test_kill_live_cycle_refusal.py:136` (`kill`). `tests/test_invariants.py:1742`
  зовёт только `status` — не затрагивается. Песочницы тестов подменяют
  `config.ROOT`, а с ним и `config.ROLE_HOME` (`tests/sandbox.py:84`).
- `docs/stack.md:517` в таблице паритета подаёт «Отказ команд пульта из-под
  роли» как «да» у обоих провайдеров, а текст `docs/stack.md:492-494` — как
  «непустой `ARTEL_ROLE` достаточен для отказа команд пульта». Реальная
  граница — песочница клиента роли: у Claude `permissions.deny` курируемого
  `settings.json` (`docs/reference/role-home/claude/settings.json`), где
  из команд пульта запрещены только `init` и `doctor --restore`, и только
  в написании `python3 orchestrator/artel.py …` (вызов по абсолютному пути
  запретом не покрыт), плюс гейты пульта после шага. Таблицу стережёт
  `tests/test_stack_parity_table.py`: каждая строка называет живую проверку
  `doctor` либо несёт пометку «не закрыт» с компенсацией.
- Сейчас все роли исполняет Claude (с 02.10), но код Codex в строю.

Требуется:
1. Признак один: `runner.in_role_environment(env=None)` — единственное место, где решается «процесс — шаг роли». `artel._refuse_if_role_restricted` вызывает его, а не читает `ARTEL_ROLE` сам; текст отказа по-прежнему называет роль, если маркер есть, иначе пишет «окружение роли». Ловит мутацию: `artel.py` снова читает только `ARTEL_ROLE`.
2. Признак истинен, если `HOME` окружения совпадает с `config.ROLE_HOME` (сравнение после приведения обоих путей к абсолютному виду без завершающей черты), независимо от `CLAUDE_CONFIG_DIR` и от `ARTEL_ROLE`. Прежние основания (непустой `ARTEL_ROLE`; пара `HOME`+`CLAUDE_CONFIG_DIR`) остаются достаточными. Утверждения действующего `test_ac1` и `test_ac5` задачи 01M3SE87 при этом остаются истинными — проверить прогоном файла без правки.
3. Пустой `ARTEL_ROLE` при чужом `HOME` — НЕ решается в этой задаче: см. «Вопросы Оператору», п.1. Без мандата Оператора поведение «пустой маркер и чужой `HOME` — не роль» сохраняется.
4. Отказ из-под роли распространяется на все команды, меняющие состояние пульта, задачи, репозитория или расход: `new`, `advance`, `workspace`, `stop`, `approve`, `reject`, `answer` в любом состоянии, `zones-extend`, `kill`, `release`, `pause`, `resume`, `budget`, `target-init`, `doctor --fix`, `alert-ack`, `canary` (кроме читающих форм, если такие есть), `prune --execute`, `amend-tests`, `ci-rerun`, `pin-update`, `pin --to`, `zone-release`, `zone-reorder`, `venv-sync` — вдобавок к уже имеющимся. Отказ ставится в диспетчере `artel.main` до вызова реализации, а не внутри функций `fsm`/`auto`/`catalog`: прямые вызовы функций пультом (`auto` → `run`/`advance`, ведение канарейки → `cmd_new`/`cmd_auto`/`_cmd_approve`) не затрагиваются. Существующие отказы внутри `answer.py`, `notes.py`, `pool_seal.py` не снимаются.
5. Команды без отказа под ролью перечисляются явно (белый список читающих команд: `status`, `show`, `log`, `version`, `models`, `report`, голый `doctor`, `watch` без `--observation`, `acceptance-dry-run`, `prune` без `--execute`, `observe show`, `hook-migrate inspect`); команда, не попавшая ни в белый список, ни в список отказа, под ролью отказывает (закрытый по умолчанию). Ловит мутацию: новая команда в таблице диспетчера без записи в одном из списков исполняется под ролью.
6. `run --attach` и `auto --attach`: см. «Вопросы Оператору», п.2. До ответа Оператора поведение не меняется.
7. Штатные пути не ломаются: отвязанный `run`/`auto` (родитель — процесс Оператора, ребёнок с `--attach`) исполняется; ведение канарейки в клоне исполняется; `doctor` с проверками `isolation-smoke`/`codex-isolation-smoke` зелёный. Проверяется тестами п.9.
8. `docs/stack.md`, раздел «Паритет безопасности роли»: текст и строка «Отказ команд пульта из-под роли» говорят как есть — признак окружения отсекает ошибочный вызов, но не является границей: процесс роли, сменивший и `HOME`, и `ARTEL_ROLE`, признак обходит. Граница — песочница клиента роли (у Claude — `permissions.deny` с перечнем того, что он реально запрещает) и гейты пульта после шага. Ячейки таблицы перестают быть голым «да»; строка проходит `tests/test_stack_parity_table.py` (живая проверка `doctor` либо «не закрыт» с компенсацией).
9. Тесты в `tests/` (новый файл задачи):
   а) окружение `{"HOME": str(config.ROLE_HOME)}` без `ARTEL_ROLE` и без `CLAUDE_CONFIG_DIR` — роль; то же с `HOME`, записанным с завершающей чертой, — роль; `HOME` Оператора без маркера — не роль. Ловит мутацию: резервная ветка снова требует `CLAUDE_CONFIG_DIR` — собранное окружение Codex со снятым `ARTEL_ROLE` не распознаётся.
   б) для каждой команды списка п.4 вызов `artel.main()` в окружении роли (оба варианта: с маркером; без маркера, но с `HOME == ROLE_HOME`) отказывает до реализации (реализация подменена и не вызвана). Ловит мутацию: пропущена одна команда списка.
   в) каждая команда белого списка п.5 под ролью исполняется. Ловит мутацию: отказ по имени команды без учёта флага (`doctor`, `prune`, `watch`).
   г) неизвестная диспетчеру команда-заглушка, добавленная в таблицу тестом, под ролью отказывает. Ловит мутацию п.5.
   д) отвязанный запуск: родитель без признака роли порождает `run --attach`/`auto --attach` (подменённый `subprocess.Popen` получает аргументы), отказа нет. Ловит мутацию: отказ поставлен в общий путь `_launch_detached`.
   е) прямой вызов `fsm.cmd_approve`/`catalog.cmd_new`/`auto.cmd_auto` под окружением роли отказом пульта не останавливается (отказ только в диспетчере). Ловит мутацию: отказ перенесён внутрь функций — ведение канарейки сломалось бы.
10. Тесты, которые зовут `artel.main()` с командами списка п.4 (`tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_kill_live_cycle_refusal.py`, при необходимости другие), явно убирают признак роли из окружения своего вызова (`ARTEL_ROLE` и `HOME`), не ослабляя проверок. Проверка: эти файлы и файлы п.9 зелёные при запуске с `ARTEL_ROLE=developer` и `HOME=<config.ROLE_HOME главной копии>` в окружении pytest.

Вопросы Оператору (до SPEC, решения вне зоны роли):
1. Считать ли ролью окружение, где `ARTEL_ROLE` присутствует, но пуст (`ARTEL_ROLE= …`) при чужом `HOME`? Это меняет последнее утверждение `test_ac1` долгоживущего `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py` — нужен мандат Оператора и `amend-tests`. Без мандата п.3 сохраняет нынешнее поведение; обход «снял маркер» и так закрыт п.2, пока роль не меняет `HOME`.
2. Отказывать ли `run --attach`/`auto --attach` из-под роли? Пульт сам с `--attach` себя порождает, но из окружения Оператора, так что отказ штатный путь не ломает. Политика наблюдения (SPEC 01M3SX69E8P64D77J1XTHMHE40, требование 5, AC-7) `--attach` не ограничивает намеренно — нужно подтверждение, что это решение про свежесть наблюдения, а не про роль.
3. Нужен ли признак, который не снимается сменой окружения: проверка предков процесса (цепочка родителей содержит процесс агента, запущенный пультом с `ARTEL_ROLE`). Обходится двойным порождением процесса с переходом к корневому родителю, стоит заметно дороже; без него п.8 честно называет признак защитой от ошибки, а не границей. По умолчанию — не входит.
4. Расширять ли `permissions.deny` курируемого `settings.json` роли Claude на команды списка п.4 (прочие написания вызова запретом префикса всё равно не покрываются). По умолчанию — не входит.

Зоны: orchestrator/runner.py, orchestrator/artel.py, docs/stack.md, tests/.

Приложением: нет.

Только чтение (не менять): orchestrator/answer.py, orchestrator/notes.py,
orchestrator/pool_seal.py, orchestrator/providers/claude.py,
orchestrator/providers/codex.py, orchestrator/config.py,
orchestrator/canary.py, orchestrator/canary_drive.py, orchestrator/dry_run.py,
orchestrator/doctor/ (включая preflight.py, isolation.py), orchestrator/fsm.py,
orchestrator/auto.py, orchestrator/catalog.py, docs/reference/role-home/,
tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py (долгоживущий,
заперт), tests/test_stack_parity_table.py, tests/test_invariants.py,
tests/sandbox.py, conftest.py (защищённый путь: его сторож полного прогона
pytest по-прежнему читает только `ARTEL_ROLE`), docs/retro/, docs/adr/,
docs/invariants.md, skills/, templates/, gates.yaml, roles.yaml, models.yaml,
targets.yaml, .github/, CLAUDE.md, AGENTS.md, tasks/ (в том числе
tasks/01M3SE87R3M7HGWX8HG1ANAKR0/, tasks/01M3SX69E8P64D77J1XTHMHE40/).

Не входит: признак по предкам процесса и расширение `permissions.deny` (до
решения Оператора по вопросам 3-4); смена признака в `conftest.py`;
поведение пустого `ARTEL_ROLE` (вопрос 1); `--attach` (вопрос 2);
правка ADR-0017; гейты пульта после шага.

Рамка: $25.
