---
task: 01M3XTF5506GF43HD51ECE230T
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/runner.py, orchestrator/artel.py, docs/stack.md, tests/
budget_usd: 25
---

# SPEC: Признак «процесс — шаг роли» не снимается ролью, и команды Оператора отказывают вызову из-под роли

## Контекст
Признак шага роли сейчас определён в двух местах, и определения расходятся.
`runner.in_role_environment()` (`orchestrator/runner.py:878-889`) истинен
при непустом `ARTEL_ROLE` либо при паре `HOME == config.ROLE_HOME` и
`CLAUDE_CONFIG_DIR == config.ROLE_CONFIG_DIR`. Пара работает только у Claude:
у Codex `CLAUDE_CONFIG_DIR` нет, поэтому шаг Codex со снятым маркером
признаком не распознаётся вовсе. Диспетчер `artel._refuse_if_role_restricted`
(`orchestrator/artel.py:1292-1299`) смотрит только на непустой `ARTEL_ROLE`,
и процесс роли снимает маркер одной приставкой (`env -u ARTEL_ROLE …`).
Кроме того, большинство команд, меняющих состояние пульта (`new`, `advance`,
`approve`, `kill`, `budget` и т.д.), из-под роли не отказывают ни по одному
из признаков. `docs/stack.md` подаёт отказ команд пульта из-под роли как
«да» у обоих провайдеров, хотя признак окружения — защита от ошибочного
вызова, а не граница.

## Требования
1. Признак один: `runner.in_role_environment(env=None)` — единственное
   место, где решается «процесс — шаг роли». `artel._refuse_if_role_restricted`
   вызывает его, а не читает `ARTEL_ROLE` сам. Текст отказа называет роль,
   если маркер есть, иначе пишет «окружение роли».
2. Признак истинен, если `HOME` окружения совпадает с `config.ROLE_HOME`.
   Оба пути сравниваются после приведения к абсолютному виду без
   завершающей черты. Значения `CLAUDE_CONFIG_DIR` и `ARTEL_ROLE` на это
   правило не влияют. Прежние основания (непустой `ARTEL_ROLE`; пара
   `HOME`+`CLAUDE_CONFIG_DIR`) остаются достаточными.
3. Поведение «`ARTEL_ROLE` присутствует, но пуст, а `HOME` чужой — не роль»
   сохраняется без изменений.
4. Отказ из-под роли распространяется на все команды, меняющие состояние
   пульта, задачи, репозитория или расход: `new`, `advance`, `workspace`,
   `stop`, `approve`, `reject`, `answer` в любом состоянии, `zones-extend`,
   `kill`, `release`, `pause`, `resume`, `budget`, `target-init`,
   `doctor --fix`, `alert-ack`, `canary` (в диспетчере у `canary` читающих
   форм нет: есть только запуск прогона и `pool-seal`, который уже
   отказывает), `prune --execute`, `amend-tests`, `ci-rerun`, `pin-update`,
   `pin --to`, `zone-release`, `zone-reorder`, `venv-sync`. Этот список
   добавляется к уже имеющимся отказам: `init`, `observe register|add|remove|stop`,
   `watch --observation`, `hook-migrate apply|restore`, `run`/`auto` без
   `--attach`, `doctor --restore`, `canary pool-seal`.
   Отказ ставится в диспетчере `artel.main` до вызова реализации, а не
   внутри функций `fsm`/`auto`/`catalog`. Прямые вызовы функций пультом
   (`auto` → `run`/`advance`, ведение канарейки → `cmd_new`/`cmd_auto`/
   `_cmd_approve`) отказом не останавливаются. Существующие отказы внутри
   `orchestrator/answer.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`
   не снимаются.
5. Команды без отказа под ролью заданы явным белым списком: `status`,
   `show`, `log`, `version`, `models`, `report`, голый `doctor`, `watch` без
   `--observation`, `acceptance-dry-run`, `prune` без `--execute`,
   `observe show`, `hook-migrate inspect`. Команда диспетчера, которой нет ни в
   белом списке, ни в списке отказа, под ролью отказывает: список закрыт по
   умолчанию. Из этого правила следует, что `note` и `doc-commit` теперь
   отказывают уже в диспетчере, хотя их внутренние отказы и раньше
   срабатывали под ролью. Единственное исключение из закрытости по
   умолчанию — `run --attach`/`auto --attach` (требование 6).
6. Поведение `run --attach` и `auto --attach` под ролью не меняется:
   отказа нет, как и сейчас.
7. Штатные пути не ломаются. Отвязанный `run`/`auto` (родитель — процесс
   Оператора, ребёнок с `--attach`) исполняется. Ведение канарейки в клоне
   исполняется. Проверки `doctor` `isolation-smoke` и `codex-isolation-smoke`
   зелёные.
8. `docs/stack.md`, раздел «Паритет безопасности роли». Текст и строка
   «Отказ команд пульта из-под роли» говорят как есть: признак окружения
   отсекает ошибочный вызов, но границей не является. Процесс роли, сменивший
   и `HOME`, и `ARTEL_ROLE`, признак обходит. Граница — песочница клиента
   роли и гейты пульта после шага. У Claude песочница — `permissions.deny`
   курируемого `settings.json`, раздел называет перечень того, что этот
   запрет реально запрещает. Ячейки строки — не голое «да». Строка проходит
   `tests/test_stack_parity_table.py`: она называет живую проверку `doctor`
   либо несёт пометку «не закрыт» с компенсацией.
9. Новый тестовый файл задачи в `tests/` покрывает требования 1-2 и 4-7
   (пункт 9 ТЗ, подпункты а-е).
10. Тесты, которые зовут `artel.main()` с командами из списка требования 4
    (`tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`,
    `tests/test_kill_live_cycle_refusal.py`, при необходимости и другие),
    явно убирают признак роли из окружения своего вызова (`ARTEL_ROLE` и
    `HOME`). Проверки этих тестов при этом не ослабляются.

## Критерии приёмки
AC-1. `artel._refuse_if_role_restricted` решает «процесс — шаг роли»
вызовом `runner.in_role_environment`, а не собственным чтением `ARTEL_ROLE`.
Если окружение распознано ролью по `HOME == config.ROLE_HOME` без
`ARTEL_ROLE`, команда из списка отказа отказывает, и текст отказа содержит
«окружение роли». Если маркер есть, текст отказа называет роль. Ловит
мутацию: `artel.py` снова читает только `ARTEL_ROLE`.

AC-2. `runner.in_role_environment` даёт следующие ответы:
- `{"HOME": str(config.ROLE_HOME)}` без `ARTEL_ROLE` и без
  `CLAUDE_CONFIG_DIR` — истина;
- то же окружение, но `HOME` записан с завершающей чертой, — истина;
- `HOME` Оператора без маркера — ложь.

Ловит мутацию: резервная ветка снова требует `CLAUDE_CONFIG_DIR`, и
собранное окружение Codex со снятым `ARTEL_ROLE` не распознаётся.

AC-3. Прежние основания признака остаются достаточными: непустой
`ARTEL_ROLE` и пара `HOME`+`CLAUDE_CONFIG_DIR`. Окружение
`{"HOME": "/tmp/operator", "ARTEL_ROLE": ""}` по-прежнему не роль. Файл
`tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py` (включая
`test_ac1` и `test_ac5`) проходит без правки и сохраняет хэш, запертый в
`tasks/01M3SE87R3M7HGWX8HG1ANAKR0/acceptance_tests/long_lived.sha256.txt`.

AC-4. Для каждой команды списка требования 4 вызов `artel.main()` под
ролью отказывает до вызова реализации: подменённая реализация не вызвана.
Проверяются оба варианта окружения роли: с маркером `ARTEL_ROLE`, а также
без маркера, но с `HOME == config.ROLE_HOME`. Ловит мутацию: пропущена одна
команда списка.

AC-5. Каждая команда белого списка требования 5 под ролью исполняется:
`status`, `show`, `log`, `version`, `models`, `report`, голый `doctor`,
`watch` без `--observation`, `acceptance-dry-run`, `prune` без `--execute`,
`observe show`, `hook-migrate inspect`. При этом формы с флагом
(`doctor --fix`, `doctor --restore`, `prune --execute`,
`watch --observation`) отказывают. Команда-заглушка, которую тест добавил
в таблицу диспетчера без записи в каком-либо списке, под ролью отказывает.
Ловит две мутации: отказ по имени команды без учёта флага и новую команду
таблицы, которая без записи в списке исполняется под ролью.

AC-6. Отвязанный запуск работает. Родитель без признака роли порождает
`run --attach`/`auto --attach`: подменённый `subprocess.Popen` получает
аргументы, отказа нет. Под ролью `run --attach` и `auto --attach` отказа
также не получают, как и до задачи. Ловит мутацию: отказ поставлен в общий
путь `_launch_detached`.

AC-7. Прямой вызов функций пульта под окружением роли не останавливается
отказом пульта: `fsm.cmd_approve`, `catalog.cmd_new`, `auto.cmd_auto`.
Отказ стоит только в диспетчере. Ловит мутацию: отказ перенесён внутрь
функций, и ведение канарейки сломалось бы. Существующие внутренние отказы
`answer.py`, `notes.py` и `pool_seal.py` под ролью по-прежнему срабатывают.

AC-8. В `docs/stack.md`, раздел «Паритет безопасности роли», текст и
строка «Отказ команд пульта из-под роли» не подают признак окружения как
границу. В них сказано:
- признак отсекает ошибочный вызов;
- процесс роли, сменивший и `HOME`, и `ARTEL_ROLE`, признак обходит;
- граница — песочница клиента роли и гейты пульта после шага; у Claude
  песочница — `permissions.deny` с перечнем того, что он реально
  запрещает.

Ни одна ячейка строки не равна голому «да».
`tests/test_stack_parity_table.py` проходит без правки.

AC-9. `tests/test_analyst_role.py`, `tests/test_approve_acceptance_full_suite.py`,
`tests/test_kill_live_cycle_refusal.py` (и другие тесты, зовущие
`artel.main()` с командами списка требования 4) убирают признак роли
(`ARTEL_ROLE` и `HOME`) из окружения своего вызова, а их проверки не
ослаблены. Эти файлы и новый файл задачи зелёные при запуске pytest с
`ARTEL_ROLE=developer` и `HOME=<config.ROLE_HOME главной копии>` в
окружении.

## Оценка объёма и деление
Сработавший сигнал — «число затрагиваемых модулей/файлов». Guard считает
пути, упомянутые в тексте SPEC. Большая часть упоминаний — файлы, которые
ТЗ отдаёт только на чтение (раздел «Не входит»). Изменяемых зон четыре:
`orchestrator/runner.py`, `orchestrator/artel.py`, `docs/stack.md`,
`tests/`. Прогноз диффа: 40 КиБ — ниже половины потолка гейта ёмкости
(128 КиБ).

Материал для решения Оператора — обоснование монолита.
- Неразрезаемое ядро — требования 4-5 и 10. Расширенный отказ в диспетчере
  и правка тестов, зовущих `artel.main()` с этими командами, должны прийти
  в одном коммите. Если отказ идёт без правки тестов, `tests/` краснеет при
  прогоне из-под роли (`ARTEL_ROLE`/`HOME` роли наследуются шагом). Если
  правка тестов идёт без отказа, ей нечего проверять.
- Требования 1-2 (единый признак и правило `HOME`) питают отказ диспетчера
  во втором варианте окружения (AC-1, AC-4). Без них ядро не закрывает
  обход со снятым маркером, ради которого задача и заведена.
- Требование 8 (`docs/stack.md`) отделимо технически, но это один абзац и
  одна строка таблицы. Отдельная задача стоит не меньше пола $25 —
  дороже самой части.

Нарезка на подзадачи поэтому не предлагается.

## Не входит
- Признак по предкам процесса (вопрос 3 ТЗ, дефолт — не входит).
- Расширение `permissions.deny` курируемого `settings.json` роли Claude
  (вопрос 4 ТЗ, дефолт — не входит). `docs/reference/role-home/` — только
  чтение.
- Поведение пустого `ARTEL_ROLE` при чужом `HOME` (вопрос 1 ТЗ): без мандата
  Оператора сохраняется нынешнее «не роль», `amend-tests` долгоживущего
  файла 01M3SE87 не делается.
- Смена политики `run --attach`/`auto --attach` (вопрос 2 ТЗ).
- Смена признака в `conftest.py`: его сторож полного прогона по-прежнему
  читает только `ARTEL_ROLE`.
- Правка ADR-0017; гейты пульта после шага.
- Правка файлов, которые ТЗ отдаёт только на чтение:
  - `orchestrator/answer.py`, `orchestrator/notes.py`, `orchestrator/pool_seal.py`;
  - `orchestrator/providers/claude.py`, `orchestrator/providers/codex.py`;
  - `orchestrator/config.py`;
  - `orchestrator/canary.py`, `orchestrator/canary_drive.py`, `orchestrator/dry_run.py`;
  - `orchestrator/doctor/`;
  - `orchestrator/fsm.py`, `orchestrator/auto.py`, `orchestrator/catalog.py`;
  - `tests/test_01m3se87r3m7hgwx8hg1anakr0_role_environment.py`,
    `tests/test_stack_parity_table.py`, `tests/test_invariants.py`,
    `tests/sandbox.py`;
  - `docs/retro/`, `docs/adr/`, `docs/invariants.md`;
  - `skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `models.yaml`,
    `targets.yaml`, `.github/`;
  - `CLAUDE.md`, `AGENTS.md`, `tasks/`.

## Материалы
- ТЗ: `tasks/01M3XTF5506GF43HD51ECE230T/TZ.md`. Источник — ревизия 02.10.2026
  задачи 01M3SE87R3M7HGWX8HG1ANAKR0, `docs/retro/01M3SE87R3M7HGWX8HG1ANAKR0.md`.
- Диспетчер: `orchestrator/artel.py:1267-1299` (`_role_restricted_command`,
  `_refuse_if_role_restricted`), таблица — `orchestrator/artel.py:1310-1360`.
  В таблице, кроме перечисленных в ТЗ, есть `note`, `doc-commit`, `init`,
  `observe`, `hook-migrate`, `watch`. `note`/`doc-commit` по требованию 5
  попадают под закрытость по умолчанию.
- Отвязанный запуск: `orchestrator/artel.py:703-713`. Ведение канарейки:
  `orchestrator/canary_drive.py`, `orchestrator/canary.py:2068-2075`.
- Бюджет $25 взят по рамке Оператора из ТЗ. Калибровочная таблица для
  этого класса (9 критериев, 4 файла зоны) рекомендует ~$40.
