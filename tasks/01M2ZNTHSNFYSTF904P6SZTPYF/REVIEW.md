---
task: 01M2ZNTHSNFYSTF904P6SZTPYF
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Интерфейс исполнителя роли, часть 1: команда, окружение, дом, предполётные проверки

## Фаза A: гейт плана

1. **Покрытие SPEC шагами.** Таблицы «Покрытие требований» PLAN.md:152-179
   полны: требования 1-9 и критерии AC-1..AC-14 каждый назван хотя бы одним
   шагом, шагов без требования нет. Замечаний нет.
2. **Размер шагов.** Восемь шагов — модуль/пакет за шаг (пакет провайдеров,
   `roles.py`, `stack.py`, `runner.py`, `catalog.py`, `doctor/`, `docs/`,
   тесты); ни микроопераций, ни «сделать всё». Обоснование монолита
   (SPEC.md:145-159) ревью принимает: разрез оставил бы merge-окно с двумя
   источниками истины — ровно тем дефектом, который задача устраняет.
3. **Конфликт с конвенциями/архитектурой.** Не вижу. Направление импортов
   (PLAN.md:34-45) разобрано правильно и является главным риском задачи:
   `orchestrator/stack.py` читается точкой входа до проверки версии
   интерпретатора, поэтому пакет провайдеров обязан оставаться
   3.9-совместимым и на уровне модуля тянуть только stdlib. В коде это
   выдержано (`providers/base.py` — только `collections`,
   `providers/claude.py` — только `os` и `.base`, весь пульт читается
   лениво внутри методов); проверено прогоном `tests/test_artel_bootstrap.py`
   (зелёный).
4. **Расхождение PLAN с буквой AC-7** (`_resolved_role_model`, PLAN.md:59-71,
   230-232) разобрано и, на мой взгляд, разрешено верно: залоченная планка
   `test_ac7_resolved_role_model_keeps_its_contract`
   (`acceptance_tests/test_ac7_model_verdict_via_provider.py:51-63`) прямо
   требует прежней сигнатуры и возврата модели, а буквальное чтение AC-7
   добавило бы подпроцесс `claude --version` на каждую попытку шага — это
   уже нарушение требования 9. Эскалацию не завожу: наблюдаемая часть AC-7
   (`_refuse_before_start` берёт вердикт у провайдера) реализована, планка
   зелёная.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/providers/base.py:36-115` — все шесть методов (`command`, `environment`, `home_reference`, `preflight`, `cli_tool`, `model_verdict`) плюс составные части предполёта. AC-1 зелёный. |
| 2 | OK | `orchestrator/providers/claude.py` — значения те же: сверено построчно с прежними телами `runner.role_cmd`/`role_env`, `stack.REQUIRED_TOOLS["claude"]`, `catalog._deploy_role_home_reference`. |
| 3 | OK | `orchestrator/roles.py:74-98`; `roles.yaml` не тронут (`git diff --stat` — файла нет в списке). |
| 4 | OK | Реестр `orchestrator/providers/__init__.py:22-24`, отказ шага `orchestrator/runner.py:317-321` (агент не стартует — проверено `tests/test_providers.py::UnknownProviderStepTest` и планкой AC-4), красная строка `doctor` — `preflight.py:234-244`. |
| 5 | OK | `role_cmd()` осталась зеро-арг и argv совпал с зафиксированным списком (AC-5 зелёный); `role_env()` сигнатуру сохранила, ключи/значения прежние (AC-6 зелёный). `_model_unsupported_after_attempt` берёт версию у провайдера (`runner.py:480`). |
| 6 | реализовано не так (частично) | Манифест (`stack.py:86-99`), предполёт через `preflight()` каждой agent-роли, смоки и строка «провайдеры ролей» — на месте. Но новая строка `doctor` зелена при нечитаемом `roles.yaml` (R1-F2), а склейка молча теряет проверки с именем вне четырёх ожидаемых (R1-F4). |
| 7 | OK | `catalog.py:65-86` + `doctor/preflight.py:128-160` смотрят на одну и ту же пару путей от `home_reference()`; AC-12 зелёный, `tests/test_coldstart.py` зелёный. Сегодня в `docs/reference/role-home/` лежит ровно `claude/`, так что поведение `init` не изменилось. |
| 8 | OK | `docs/stack.md:32-67` — раздел «Провайдер исполнителя роли» с составом интерфейса и границей «что остаётся общим у runner». Карта регенерирована: пересобрал `scripts/codebase_map.py`, содержимое совпало байт-в-байт (кроме `built_at_sha`). |
| 9 | реализовано с оговорками | argv шага, окружение роли и дом роли для `claude` совпали (AC-5/AC-6/AC-12). Два отступления: argv[0] живого смоука стал абсолютным путём (следствие AC-10, заявлено в PLAN.md:215-222 — принимаю) и строка `token` в `doctor` при ambient-токене схлопывается с N одинаковых в одну (следствие дедупликации, см. R1-F1 — это же ломает тест). |

| Критерий | Вердикт |
|---|---|
| AC-1..AC-14 | все 32 теста планки зелёные (прогон ниже) |

## Замечания

- **major — tests/test_providers.py:200, tests/test_providers.py:374 —
  два новых теста падают, если в окружении прогона задан
  `CLAUDE_CODE_OAUTH_TOKEN` (или `ANTHROPIC_API_KEY`)** — то есть
  штатный ambient-канал токена, который сам же пульт объявляет в
  `stack.ROLE_ENV_ALLOWLIST` и который `runner.role_env()` кладёт в
  окружение КАЖДОГО шага роли. Воспроизвёл:

  ```
  CLAUDE_CODE_OAUTH_TOKEN=tok-ambient python3 -m pytest tests/test_providers.py -q
  → 2 failed, 20 passed
  ```

  - `:200` `StepEnvironmentTest::test_provider_part_sits_on_top_of_the_manifest_allowlist`
    ждёт `env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-test"` (подменённый
    keychain), но провайдер по своему же контракту отдаёт ambient
    (`AssertionError: 'tok-ambient' != 'tok-test'`) — ровно тот приоритет,
    который утверждает соседний тест `:216`.
  - `:374` `DoctorProviderLinesTest::test_provider_preflight_is_collected_without_duplicates`
    ждёт `len(grouped["token"]) == len(agent_roles())`, но при ambient-токене
    `doctor.check_token(role)` отдаёт для всех ролей один и тот же
    `Check("token","ok","токен уже в окружении (ambient)")`
    (`doctor/preflight.py:56-57`), дедупликация по значению в
    `provider_preflight_checks` схлопывает их в одну запись
    (`AssertionError: 1 != 3`).

  Сценарий поломки: Оператор (или роль, гоняющая набор внутри шага —
  её окружение несёт эту переменную по построению) запускает `tests/`
  и получает два красных теста без единого дефекта в коде; следующее
  ревью списывает их на «предсуществующий сбой». Существующие тесты
  этим не страдают — прогнал `tests/test_doctor.py`,
  `tests/test_runner_model_preflight.py`, `tests/test_stack.py` с той же
  переменной: 173 passed. То есть класс внесён этой задачей.

  Предложение: в обоих тестах вычистить обе переменные из `os.environ`
  на время прогона (`mock.patch.dict(os.environ, {...})` с удалением
  ключей — тем же приёмом, каким `:216` намеренно её ставит), чтобы
  проверяемое свойство не зависело от машины Оператора.

- **major — orchestrator/doctor/preflight.py:228-233 — ветка
  `except doctor.roles.RolesError` в `check_role_providers` недостижима,
  и на нечитаемом `roles.yaml` `doctor` печатает выдуманную зелёную
  строку.** `providers.role_providers` (`providers/__init__.py:70-75`)
  зовёт `name_for_role`, а тот уже сам глотает `RolesError` и
  подставляет `DEFAULT_PROVIDER` (`providers/__init__.py:47-64`) — до
  `except` в `check_role_providers` исключение не доходит никогда.
  Проверил исполнением на сломанном и на отсутствующем `roles.yaml`:

  ```
  check_role_providers -> Check(name='role-providers', status='ok',
    detail='провайдеры ролей: developer → claude, reviewer → claude,
            test_author → claude')
  ```

  Сценарий поломки: Оператор сломал `roles.yaml` (опечатка в YAML, файл
  не на месте) — `doctor` утверждает зелёным, что карта исполнителей
  прочитана и все роли идут на `claude`, хотя ни одного имени из файла
  не читалось. Докстринг тут же обещает обратное («Нечитаемая карта —
  WARN, не исключение… тот же приём, что `stack._model_checks`») — и
  `stack._model_checks` в той же ситуации честно даёт
  `StackCheck(name='model-roles', status='warn', …не разобран…)`
  (проверил), то есть образец, на который ссылается докстринг, ведёт
  себя не так, как эта проверка.

  Предложение: резолвить имена в `check_role_providers` так, чтобы
  `RolesError` доходил сюда (отдельный вариант `role_providers` без
  деградации либо прямой `roles.provider(role)` в цикле проверки) —
  либо убрать мёртвую ветку вместе с обещанием в докстринге. Первое
  лучше: диагностическая команда обязана отличать «прочитал и там
  claude» от «не смог прочитать».

- **minor — tests/test_providers.py:134 —
  `test_for_role_degrades_to_the_default_on_an_unreadable_map`:
  заявка `Ловит мутацию` говорит про «нечитаемую карту исполнителей», а
  тест нечитаемой карты не создаёт** — он спрашивает роль `delta`,
  отсутствующую во вполне валидном `ROLES_YAML` (`:57-72`), и `None`.
  Путь `RolesError` действительно задевается, но именно ветка
  «файл не прочитан / не разобран» в наборе не проверена ни разу — и
  это ровно та ветка, на которой сидит R1-F2. Предложение: добавить
  подслучай с реально битым файлом (`config.ROLES` → файл с мусорным
  YAML) либо переписать заявку под то, что тест действительно ловит.

- **minor — orchestrator/doctor/cli.py:25-32 (в паре с
  orchestrator/doctor/preflight.py:246-270) — `all_checks` достаёт
  провайдерские проверки из словаря по четырём захардкоженным именам,
  и проверка с любым другим именем исчезает из вывода `doctor`
  молча.** `provider_preflight_checks()` возвращает `{имя: [проверки]}`,
  а `all_checks` делает четыре `.get("cli-found"/"cli-version"/"token"/
  "role-home-reference", [])`; ничего не проверяет, что набор имён
  провайдера этим исчерпан. Сценарий поломки — ровно тот, ради которого
  задача и затевалась: провайдер `codex` (задача 4 плана) называет
  проверку своего секрета `api-key`, `preflight()` её честно отдаёт,
  `doctor` её не печатает, и Оператор видит зелёный прогон при
  отсутствующем ключе. Предложение: после четырёх именованных
  `extend` дописывать остаток словаря (имена, не разобранные выше) —
  или зафиксировать состав имён контрактом в
  `base.RoleExecutorProvider.preflight` и проверить его тестом.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_providers.py:200, tests/test_providers.py:374 | Два новых теста зависят от ambient `CLAUDE_CODE_OAUTH_TOKEN`/`ANTHROPIC_API_KEY` в окружении прогона | Набор краснеет двумя тестами на машине Оператора с заданным токеном и внутри любого шага роли (там переменная стоит по построению) без единого дефекта в коде | Вычистить обе переменные из `os.environ` на время этих двух тестов (`mock.patch.dict` с удалением ключей), сохранив предмет проверки |
| R1-F2 | open | orchestrator/doctor/preflight.py:228-233 | `except doctor.roles.RolesError` недостижим: `providers.name_for_role` уже деградирует к `DEFAULT_PROVIDER`, поэтому обещанный докстрингом WARN невозможен | На сломанном/отсутствующем `roles.yaml` `doctor` даёт зелёную строку «провайдеры ролей: … → claude», утверждая прочитанным файл, который не читался | Дать `RolesError` дойти до `check_role_providers` (вариант `role_providers` без деградации либо прямой `roles.provider` в проверке) — либо снять мёртвую ветку вместе с обещанием докстринга |
| R1-F3 | open | tests/test_providers.py:134 | Заявка `Ловит мутацию` называет «нечитаемую карту исполнителей», тест же подаёт отсутствующую роль в валидной карте | Ветка «файл не прочитан/не разобран» не покрыта ни одним тестом — на ней и сидит R1-F2 | Добавить подслучай с реально битым `config.ROLES` либо привести заявку в соответствие тому, что тест ловит |
| R1-F4 | open | orchestrator/doctor/cli.py:25-32 | Провайдерские проверки вынимаются из словаря по четырём захардкоженным именам, остаток отбрасывается без сигнала | Проверка второго провайдера с другим именем (`api-key` у `codex`) исчезает из вывода `doctor`: зелёный прогон при отсутствующем секрете | Дописывать неразобранный остаток словаря в конец списка либо зафиксировать состав имён контрактом `base.RoleExecutorProvider.preflight` и проверить тестом |

## Вердикт

`changes_requested`. Рефакторинг по существу сделан правильно: argv, окружение
и дом роли для `claude` совпали с сегодняшними (планка AC-5/AC-6/AC-12
зелёная), ни один тест, гейт, лимит или guard не ослаблен — дифф `tests/`
состоит из нового файла и одной правки фикстуры (`cmd[0] == "claude"` →
`is_claude_call(cmd)`), которая расширяет, а не сужает опознание процесса;
ассерт не тронут, правка предусмотрена докстрингом планки AC-14. Карта
кодовой базы свежая, посторонних файлов и правок защищённых путей в диффе
нет, откат — revert одного merge-коммита, как заявлено в PLAN.

Исправить до мержа:
1. R1-F1 — зависимость двух новых тестов от ambient-токена (воспроизводимо).
2. R1-F2 — мёртвая ветка и ложно-зелёная строка `doctor` на нечитаемом
   `roles.yaml` (воспроизводимо).
3. R1-F3, R1-F4 — minor, но чинятся в ту же итерацию дёшево.

## Проверено исполнением

Рабочий каталог — worktree задачи, интерпретатор `python3` шага.

- `python3 -m pytest tasks/01M2ZNTHSNFYSTF904P6SZTPYF/acceptance_tests -q` —
  **32 passed, 21 subtests passed** (17 с). Планка AC-1..AC-14 зелёная.
- `python3 -m pytest tests/test_doctor.py tests/test_stack.py
  tests/test_runner_role_model.py tests/test_runner_model_preflight.py
  tests/test_doctor_canary_pool.py tests/test_artel_bootstrap.py
  tests/test_yaml_parsing.py tests/test_invariants.py -q` —
  **291 passed, 253 subtests passed** (128 с). Это AC-14 плюс бутстрап
  (3.9-совместимость пакета провайдеров на пути импорта `stack.py`).
- `python3 -m pytest tests/test_coldstart.py tests/test_catalog_status_log.py
  tests/test_catalog_new_race.py tests/test_agent_prompt.py
  tests/test_git_hooks.py tests/test_step_cost.py tests/test_agent_failure.py
  tests/test_doctor_wave_breaker.py tests/test_doctor_fix_ignored_artifacts.py -q`
  — **145 passed, 32 subtests passed** (27 с). Затронутые модули
  `catalog`/`runner`/`doctor`.
- `python3 -m pytest tests/test_providers.py -q` — **22 passed** в чистом
  окружении; тот же файл с `CLAUDE_CODE_OAUTH_TOKEN=tok-ambient` —
  **2 failed, 20 passed** (R1-F1, тексты падений приведены в замечании).
  Контроль на «класс внесён этой задачей»: `tests/test_doctor.py
  tests/test_runner_model_preflight.py tests/test_stack.py` с той же
  переменной — **173 passed**.
- Проба R1-F2 в интерпретаторе: `config.ROLES` подменён на файл с битым
  YAML и на несуществующий путь → `doctor.check_role_providers()` в обоих
  случаях `status='ok'` с перечнем ролей; для сравнения
  `stack._model_checks(None)` на том же файле → `status='warn'` с текстом
  «не разобран».
- `python3 scripts/codebase_map.py` с последующим сравнением содержимого
  без строки `built_at_sha` — **идентично** тому, что в ветке; файл
  восстановлен, дерево не изменено.
- `python3 scripts/guard.py --all` — **GUARD: ок (955 файлов)**, два
  предупреждения относятся к чужим задачам (T067, 01M1RA0R9A).
- `git status --porcelain` — чисто, кроме неотслеживаемого
  `tasks/01M2ZNTHSNFYSTF904P6SZTPYF/` (артефакты в кодовую ветку не
  коммитятся — так и должно быть).
- `git diff c4f7e794...HEAD --stat -- tests/` — только
  `tests/test_doctor.py | 8 +-` (комментарий + одна строка фикстуры) и
  новый `tests/test_providers.py`; удалённых или ослабленных ассертов нет.

## Предложения системе

- Ревью-пакет этой задачи не смог включить SPEC.md и PLAN.md («в ветке —
  path does not exist; в дереве — файл не найден»), хотя оба лежат в
  рабочем каталоге шага и материализованы штатно. Сборщик пакета,
  похоже, ищет артефакты в кодовой ветке и в корне пульта, но не в
  worktree шага. Класс: «ревьювер получает пакет без главного предмета
  Фазы A» — без ручного дочитывания с диска гейт плана было бы не
  провести вовсе.
- Класс «мутационная заявка теста называет сценарий, которого тест не
  ставит» (R1-F3) `skills/test-authoring.md` прямо не запрещает: там есть
  требование нести заявку, но нет требования, чтобы описанный в ней
  триггер был фактически воспроизведён в теле теста. Оба раза, что я это
  вижу, заявка звучит убедительнее покрытия.
