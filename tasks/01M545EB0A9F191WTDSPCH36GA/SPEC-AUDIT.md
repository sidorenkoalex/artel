---
task: 01M545EB0A9F191WTDSPCH36GA
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/; в) пути-признаки (песочница ролей): orchestrator/providers/base.py, orchestrator/providers/claude.py, orchestrator/providers/codex.py, orchestrator/runner.py; в) защищённые пути: skills/; д) ТЗ ссылается на ADR: ADR-0023.
spec_sha: aed7b40f6f28c94890303b3d27e6138ef0e8dfea
schema_version: 5
---

# SPEC-AUDIT: D2-1 — проектные скилы и меры для роли внешнего проекта

## ТЗ и SPEC
ТЗ → SPEC: пп.1–6 ТЗ отражены требованиями 1–8 SPEC; «Не входит» ТЗ
(обходы через `git -c alias`/`core.fsmonitor`, правка `skills/`,
`roles.yaml`, `targets.py`) перенесено в «Не входит» SPEC.

Решение Оператора на гейте SPEC №1 (шесть пунктов) — все внесены:
- п.1 (П-2) → требование 9 и AC-8; AC-1/AC-4 сформулированы «на пути
  запуска шага роли (требование 9)».
- п.2 (А-1) → требование 2: источник — голова `main` пульта
  (`brief.py:521-526`, `:543`), решение Ф-5 родителя заменено. Это
  расходится с буквой ТЗ п.2 («файл на диске пульта,
  `config.ROOT/skills/<имя>.md`»), но решение Оператора имеет силу
  ANSWER и прямо заменяет это место — не отклонение.
- п.3 (П-1) → AC-1 и AC-4 сверяют значение `--allowedTools` целиком.
- п.4 (П-3) → AC-7.
- п.5 (П-4) → AC-3, второй пункт (`sub/name`).
- п.6 (П-5) → AC-6.

SPEC → ТЗ: требование 9 распространено и на сборку брифа
(`runner.py:476`), хотя решение Оператора называло только
`runner.py:1550` и `runner.py:964`. Это следствие требования 1 (бриф
должен знать проект, чтобы взять его `project_skills`), не новое
требование — не отклонение. Иных требований сверх ТЗ и решений не
найдено.

## Факты против кода
Подтвердилось:
- `orchestrator/targets.py:31` — `project_skills` проверяется только как
  `list`.
- `orchestrator/brief.py:519` `skills_text`; `:541-543` читает
  `skills/<имя>.md` через `gitcmd.show(config.MAIN_BRANCH, rel,
  repo=config.ROOT)` — голова `main`, не диск.
- `orchestrator/providers/claude.py:45` `ALLOWED_TOOLS =
  "Bash(git:*),Bash(python3:*)"`, используется в argv на `:165`.
- `orchestrator/runner.py:964` `def role_env(role, task_id, *, provider)`;
  `GIT_CONFIG*` в `orchestrator/` не встречается нигде.
- `orchestrator/runner.py:476` — вызов `brief.skills_text`;
  `:1457` — `env = role_env(role, task_id, provider=provider)`;
  `:1550` — `provider.command(model_id, docs_dir=…)`.
- `command(self, model=None, docs_dir=None)` — `providers/base.py:189`,
  `providers/claude.py:122`, `providers/codex.py:379`.
- Строка миссий `config.ROOT / "orchestrator" / "artel.py"` —
  `orchestrator/role_prompt.py:238`, `orchestrator/knowledge_cards.py:953`.
- Вызовы вне пути запуска: `runner.py:1204` (`role_cmd`),
  `orchestrator/doctor/isolation.py:201` (`provider.command()`),
  `tests/test_multitarget.py:702` (`runner.role_env("developer",
  "01ABCDEF")`) — на месте; также `providers/codex.py:652` и
  `providers/claude.py:309` зовут `self.command()` без аргументов (смок),
  SPEC их не перечисляет, но новый параметр со значением по умолчанию
  их не ломает.

Не названо SPEC, но существенно для требования 9 (см. «Проверяемость»,
AC-8):
- `orchestrator/store.py:701-707` `task_target` — нынешний источник
  проекта на пути шага (`runner.py:1469` для `role_cwd`, `runner.py:1184`
  для каталога документов) — сам по себе fail-open: задачи нет в БД →
  `config.DEFAULT_TARGET` (артель). `store.py` вне зон SPEC и вне
  `config.COMMON_ZONES` (`config.py:799`).
- `orchestrator/runner.py:208` (`_cmd_run`) и `:1376` (`run_agent_once`)
  зовут `store.get_task`, который при отсутствии задачи делает
  `sys.exit` (`store.py:1010-1015`) раньше `:476`/`:1457`/`:1550`.
- Колонка `tasks.target` — `NOT NULL` (`orchestrator/schema.py:47`).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `project_skills` артели/признак внешнего проекта применён к артели: в argv `--allowedTools` ≠ `Bash(git:*),Bash(python3:*)`, в env появился `GIT_CONFIG_NOSYSTEM`, бриф получил лишний блок. Замечание: бриф несёт случайный `run_id` границ (`brief.new_run_id`) — «совпадает с main» проверяемо только с подменой `new_run_id` либо сравнением блока скилов; это вопрос формы теста, не отклонение. |
| AC-2 | да | проектные скилы не добавлены / добавлены до скилов роли / в обратном порядке / прочитаны с диска вместо `main` (тест с расхождением диск≠main). |
| AC-3 | да | нет проверки `..`/абсолютного пути; разрешён подкаталог; проверка по диску (`Path.exists`) вместо `main`; текст отказа без проекта/поля/имени; `targets.check` начинает отказывать по полю (`targets.yaml` негоден); отказ одного проекта ломает бриф другого. |
| AC-4 | да | правило с относительным путём, с `str(config.ROOT)` иной формы, `python3:*` оставлен рядом, `git:*` потерян; `GIT_CONFIG_NOSYSTEM` не выставлен или ≠ `1`. |
| AC-5 | да | Codex начал менять argv по проекту задачи. |
| AC-6 | да | `GIT_CONFIG_NOSYSTEM` выставлен в `claude.environment`, а не в общей части `role_env` — шаг Codex его не получает. |
| AC-7 | да | проверка существует только внутри сборки брифа; у отдельной проверки другой источник (диск) или другой текст отказа. |
| AC-8 | частично — отклонение | см. ниже. |

**Отклонение В-1 (AC-8).** Пример «задачи нет в БД» на публичном пути
запуска шага недостижим: `store.get_task` в `runner.py:208` и
`runner.py:1376` завершает процесс `sys.exit` до сборки брифа, окружения
и argv. Тест AC-8 через `cmd_run`/`run_agent_once` с отсутствующей
задачей зелёный и на main, и на коде, который определяет проект
fail-open через `store.task_target` (`store.py:701-707`, возврат
`DEFAULT_TARGET`) — мутацию «правила артели по умолчанию» он не ловит.
Ловит её только тест, зовущий внутренние `_prepare_step`/`_spawn_and_wait`
напрямую, — а это навязывание устройства. Реально достижимые случаи
сбоя определения проекта на этом пути SPEC не называет: в строке задачи
`target`, не объявленный в `targets.yaml` (`targets.target` →
`TargetsError`, `orchestrator/targets.py:117-125`), и `targets.yaml`,
который не читается. «Чтение проекта задачи падает» — без указания, что
именно падает, автор тестов выберет инъекцию по своему вкусу.

## Зоны
Зоны SPEC: `orchestrator/brief.py`, `orchestrator/runner.py`,
`orchestrator/providers/{claude,base,codex}.py`, `tests/`; плюс
`config.COMMON_ZONES` (`orchestrator/config.py:799`: `config.py`,
`docs/codebase-map.md`, `tests/`). Требования 1–9 реализуемы в этих
файлах: проверка имени и сборка проектных скилов — `brief.py`;
определение проекта, `GIT_CONFIG_NOSYSTEM`, проброс проекта в
`command` — `runner.py`; белый список — `claude.py`; сигнатура — `base.py`,
`codex.py`. Вставка скилов в промпт возможна без `role_prompt.py`
(вне зон и в «Не входит»): текст скилов уходит из `runner.py:476`.
Чтение проекта задачи без fail-open должно идти мимо
`store.task_target` и не может править `store.py` (вне зон) — выполнимо
в `runner.py` (строка `t` уже есть на `runner.py:208`/`:1376`).
Защищённые пути (`skills/`, `roles.yaml`, `templates/`) не трогаются —
«Не входит». Песочница ролей сужается (внешний проект), для артели не
меняется — расширения нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `ALLOWED_TOOLS`/argv Claude (`providers/claude.py:45`, `:165`) | хвост argv артели — `tests/test_providers.py:55-61` (`Bash(git:*),Bash(python3:*)`) | да, для артели (требование 6) | тот же тест + AC-1 | остаётся |
| то же | ревьювер артели может запускать тесты — `tests/test_review_package.py:1302` | да (задача на `DEFAULT_TARGET`) | тот же тест | остаётся |
| сигнатура `command` (`providers/base.py:189`, `codex.py:379`) | смок изоляции Codex — `doctor/isolation.py:201` зовёт `command()` без аргументов | да, при значении параметра по умолчанию | существующие тесты смока + AC-5 | остаётся |
| `role_env` (`runner.py:964`) | `ARTEL_ROLE`/`ARTEL_TASK` — `tests/test_multitarget.py:702` | да (вне пути шага, «Не входит») | тот же тест | остаётся |
| `Bash(python3 <корень>/orchestrator/artel.py:*)` для внешнего проекта | допуск команд CLI роли — `orchestrator/artel.py:1877-1901` `_ROLE_ALLOWED_COMMANDS` | да, не трогается; становится единственным рубежом подкоманд `artel.py` | существующие тесты рубежа | остаётся |

Раздела «Меняемое поведение» в SPEC нет — и не нужно: ни одно
ожидание существующего метода `tests/` не меняется (артель — как на
main).

## Пути обхода гейтов
- **О-1 (= В-1).** Буквальное исполнение требования 9 через
  `store.task_target` (fail-open на артель) проходит тест AC-8,
  написанный на пример «задачи нет в БД» через публичный вход шага, —
  смысл требования (не уходить с правилами артели) не проверен.
- Проверено, обхода нет: проверка имени на диске вместо `main` (ловит
  AC-3 п.4, AC-7); два разных источника у брифа и `doctor` (AC-7 «тем же
  текстом»); `GIT_CONFIG_NOSYSTEM` только у Claude (AC-6); правило
  `artel.py:*` открывающее опасные подкоманды — их режет
  `_ROLE_ALLOWED_COMMANDS` (`artel.py:1877`), это не меняется.
- Остаточный риск кода, исполняемого `suite-run`/`plank-run`, и
  `git -c alias` — принят ADR-0023 (вторая поправка, п.5), не отклонение.

## Вердикт
concerns. Все шесть замечаний прошлого аудита по решению Оператора
внесены; факты о коде подтвердились. Отклонения:

1. **В-1 / О-1 — AC-8 не ловит fail-open** (SPEC.md, AC-8; требование 9).
   Пример «задачи нет в БД» недостижим на публичном пути шага
   (`orchestrator/runner.py:208`, `:1376` → `store.get_task` с `sys.exit`,
   `orchestrator/store.py:1010-1015`). Тест на этот пример зелёный и при
   определении проекта через `store.task_target`, который возвращает
   артель (`orchestrator/store.py:701-707`). Реальные случаи —
   `target` задачи не объявлен в `targets.yaml`
   (`orchestrator/targets.py:117-125`) или `targets.yaml` не читается —
   в SPEC не названы. Предложение Оператору на гейте: в AC-8 заменить
   пример на «`target` задачи не объявлен в `targets.yaml` / `targets.yaml`
   не читается», убрать «задачи нет в БД» и назвать
   `store.task_target` (fail-open) как недопустимый источник на пути
   шага.
2. **Мелкое (не блокирует).** SPEC не называет `store.task_target`
   (`orchestrator/store.py:701`) нынешним fail-open источником проекта на
   пути шага (`runner.py:1184`, `:1469`). `store.py` вне зон, так что
   обход должен лечь в `runner.py`. Это выполнимо, но разработчику
   придётся догадаться самому.
