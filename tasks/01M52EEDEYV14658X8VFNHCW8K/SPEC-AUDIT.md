---
task: 01M52EEDEYV14658X8VFNHCW8K
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/; в) пути-признаки (песочница ролей): orchestrator/providers/; д) ТЗ ссылается на ADR: ADR-0023
spec_sha: f8e9c02153c9cd57b6368cb96c403edc94df88c5
schema_version: 5
---

# SPEC-AUDIT: D0-1: профиль test_profile — подполя runner, workdir, env и фиксация мест запуска

## ТЗ и SPEC
ANSWER-n.md у задачи нет, решений Оператора на гейте SPEC в брифе нет.

ТЗ → SPEC: все пункты ТЗ перенесены. ТЗ п.1 → требования 1–5 (SPEC.md:27–42);
ТЗ п.2 → требование 6 (SPEC.md:43–46); ТЗ п.3 → требование 7 (SPEC.md:47–53);
критерии приёмки ТЗ → AC-1…AC-5, AC-7; «Не входит» ТЗ (acceptance.py,
two_sided.py, вызывающие модули, targets.yaml, sandbox, yamlmini) — в «Не входит» SPEC.

SPEC → ТЗ: сверх ТЗ только AC-6 (SPEC.md:76) — положительный случай
`pytest-own` + доставка значений в `Profile`; он следует из ТЗ п.1–2, нового
требования не вносит. Строка «Правка `orchestrator/providers/` — только
читается» — уточнение, не новое требование.

Расхождение, перенесённое из ТЗ без уточнения: ТЗ п.3 и требование 7
(SPEC.md:47–53) требуют «по обоим путям команды» для КАЖДОГО из восьми мест,
а у части мест второго пути нет в коде (см. «Факты против кода», п.1).
Аналитик скопировал формулировку ТЗ, не сверив её с сигнатурами.

## Факты против кода
1. **Не подтвердилось — «оба пути команды» у каждого из восьми мест**
   (SPEC.md:52–53, SPEC.md:84–85):
   - `acceptance.run_plank(targets, cwd)` — параметра `command` нет, команда
     всегда `_pytest_command(*targets)` (orchestrator/acceptance.py:923, :933);
   - `two_sided._run_side(tree, nodes, plugin_dir, report, timeout)` —
     параметра `command` нет, команда всегда пульта
     (orchestrator/advance_gates/two_sided.py:222, :227);
   - `_run_full_suite_now`/`_run_full_suite_to_log` принимают готовый `argv`
     (orchestrator/acceptance.py:1313, :1361); `command` входит в него только
     через `run_full_suite(root, command=…)` (orchestrator/acceptance.py:1115,
     :1175).
   Буквально оба пути есть только у `run` (:384–386), `collect` (:512–514),
   `run_repeat` (:649–650). Править эти модули задача не может («Не входит»),
   так что для `run_plank` и `_run_side` второй путь записать нельзя, а для
   `_run_full_suite_*` он означает вызов через `run_full_suite`. Требование
   допускает два прочтения: тест-автор может зафиксировать только
   существующий путь, а может решить, что AC-7 невыполним.
2. Подтвердилось: `PROFILE_FIELDS`, `PROFILE_OPTIONAL`, `_check_profile`,
   `_profile_value_error` (orchestrator/targets.py:41, :53, :262, :284);
   неизвестное подполе — отказ (orchestrator/targets.py:268–272).
3. Подтвердилось: `secret_env_names()` у `base.py:256` (пусто), `claude.py:213`
   → `SECRET_ENV_NAMES = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")`
   (claude.py:50), `codex.py:500` → `()` (codex.py:514). Ключи Codex
   (`FORBIDDEN_KEY_ENV_NAMES`, codex.py:114: OPENAI_API_KEY, CODEX_API_KEY,
   CODEX_ACCESS_TOKEN) в перечень, названный ТЗ и SPEC, не входят.
4. Подтвердилось с оговоркой — «`yamlmini.mapping` уже разбирает блочное
   отображение третьего уровня» (SPEC.md:Материалы): разбор образца
   `test_profile.env` даёт словарь. Но `yamlmini.scalar` типизирует значения
   (orchestrator/yamlmini.py:42–63): `PYTHONHASHSEED: 0` → `int 0`,
   `FLAG: true` → `bool`, пустое `env:` → `None` (проверено разбором). SPEC об
   этом молчит (см. «Проверяемость», AC-1/AC-6).
5. Подтвердилось: места запуска и флаг `observe` есть
   (orchestrator/acceptance.py:179 `observed_full_suite`, :1316, :1321, :1364);
   `targets.yaml:46` — `command: [python3, -m, pytest]`.
6. Подтвердилось: `Profile` — frozen dataclass
   (orchestrator/project_profile.py:63–85). Его строят именованными
   аргументами без новых полей tests/test_project_profile_gates.py:210,
   tests/test_network_address_gate.py:178 — новым полям нужны умолчания. SPEC
   умолчание называет только для `runner` (SPEC.md:44–45); для `workdir` и
   `env` при отсутствии подполя его нет (None? `""`? `{}`?), хотя на это поле
   опираются следующие части D0.
7. Импорт реестра провайдеров из `targets.py` на уровне модуля даёт цикл
   targets → providers → roles → models → store → targets (карта:
   providers/__init__ импортирует roles.py, roles — models.py, models —
   store.py, store — targets.py). Годен только ленивый импорт. SPEC это не
   запрещает и не предписывает; сказано для разработчика.

## Проверяемость критериев
| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да, с пробелом | Поймает: проверка имён секретов в `env` удалена либо сверка ведётся без учёта регистра или по подстроке. Не поймает: перечень записан литералом `("CLAUDE_CODE_OAUTH_TOKEN","ANTHROPIC_API_KEY","GITHUB_TOKEN","GH_TOKEN")`, а не взят из `secret_env_names()` реестра. Тест на текущие имена литерал от реестра не отличит; нужен тест, где провайдер возвращает новое имя (подмена `secret_env_names`) и оно получает отказ. AC-1 этого не требует. |
| AC-2 | да | `workdir` абсолютный или с `..` проходит (например, проверка `startswith("/")` удалена). |
| AC-3 | да | `runner` не сверяется с перечнем значений. |
| AC-4 | да | Запрет `workdir`/`env` срабатывает только при явном `runner: pult-pytest`, а при умолчании — нет. |
| AC-5 | да | `Profile.runner` при отсутствии подполя — `None`/`""`; новые подполя стали обязательными. |
| AC-6 | да, с пробелом | Поймает: `Profile` не несёт `workdir`/`env`. Не поймает: `env` со значением не-строкой (`PYTHONHASHSEED: 0` → int, `true` → bool, `env:` → None, `env` списком) принимается. Требование 4 говорит «отображение строк» (SPEC.md:34), но ни один AC не требует отказа не-строке или не-отображению, и SPEC не решает, отказывать ли такому значению или приводить его к строке. |
| AC-7 | слабо | Строгость фиксации не названа: «зафиксированы argv, cwd и окружение» (SPEC.md:81–85) выполняет и тест, сверяющий только тип или наличие ключей. Мутация «убрать `PYTHONPYCACHEPREFIX` из `_pytest_env` (acceptance.py:86)», «убрать `PYTHONUNBUFFERED` (acceptance.py:1372)» или «сменить `cwd=run_cwd` на `cwd=tdir`» поймается, только если тест сравнивает argv целиком на равенство, `cwd` на равенство и окружение как разницу с `os.environ` (добавленные и изменённые ключи по имени; значение временного каталога — по форме). AC этого не требует. Кроме того, «по обоим путям» неисполним для `run_plank` и `_run_side` (см. «Факты», п.1). |

## Зоны
Зоны SPEC: `orchestrator/targets.py, orchestrator/project_profile.py, tests/`
совпадают с ТЗ и покрывают то, что заставляют менять требования: проверку в
targets.py, поля в project_profile.py, тесты в tests/. Защищённые пути
(`targets.yaml`, `templates/`, `skills/`…) не меняются: `targets.yaml`
только читается (SPEC «Не входит»). Песочница ролей не расширяется:
`orchestrator/providers/` только читается (сигнал «песочница ролей»
сработал по упоминанию, правки там нет). Поле `sandbox` записи
(`targets.yaml:43`) задача не трогает. Карта кодовой базы при правке `*.py`
регенерируется по conventions-core — это не зона, а обязанность разработчика.

## Матрица неослабления
| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `PROFILE_FIELDS` получает `runner`, `workdir`, `env` (targets.py:41) | Отказ неизвестному подполю профиля — targets.py:268–272; tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103–104, :132–152 (случайный выбор из `timeout`, `runner`, `lang`, `paths`) | Да, но для `runner` оно сменится: `runner: "x"` получит отказ уже по новому правилу (AC-3), а не как неизвестное подполе | Тот же тест останется зелёным, только если отказ нового правила называет `test_profile` и `runner` (:151–152); SPEC этого не требует. Ветку «неизвестное подполе» тест при выборе `runner` больше не проходит: охват — 3 из 4 запусков | Concerns: требовать, чтобы отказ `runner` называл `test_profile.runner` (как targets.py:281) |
| `_check_profile` получает вид `mapping` и проверки связок (targets.py:262–312) | Профиль без новых подполей проходит, как сейчас: tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:107–130 | Да | Тот же тест + AC-5 | Остаётся |
| Новые поля `Profile` (project_profile.py:63–85) | Построение `Profile` именованными аргументами в tests/test_project_profile_gates.py:210, tests/test_network_address_gate.py:178; `from_values` в tests/test_project_profile.py:27 | Да, если у новых полей есть умолчания | Существующие тесты; умолчания `workdir`/`env` SPEC не называет | Concerns (см. «Факты», п.6) |
| Места запуска (acceptance.py, two_sided.py) | Не меняются: задача только добавляет фиксирующие тесты | Да | AC-7 (новые тесты) | Остаётся |

Раздела «Меняемое поведение» в SPEC нет, и он не нужен: ожидания
существующих тестовых методов задача не меняет.

## Пути обхода гейтов
1. AC-1, литерал вместо реестра. Перечень секретов можно записать в
   targets.py константой из текущих четырёх имён (ленивый импорт реестра
   неудобен из-за цикла, «Факты», п.7). Тесты AC-1 пройдут, а секрет
   следующего провайдера проверка не увидит. Требование 4 («имена
   `secret_env_names()` провайдеров») такой подход запрещает, но AC-1 его
   не ловит.
2. AC-7, пустая фиксация. Тест «зелёный на текущем коде», сверяющий
   argv/cwd/env нестрого, буквально выполняет AC-7. Тогда следующие части D0
   смогут менять места запуска ненаблюдаемо, а ради наблюдаемости фиксация и
   вводилась (SPEC «Контекст»).
3. AC-7, «оба пути» для `run_plank`/`_run_side`. Пути `command=[python3, -m,
   pytest]` там нет. Исполнитель может «зафиксировать» его тестом, который
   зовёт `_pytest_command(command=…)` напрямую, мимо места запуска, и
   формально закрыть пункт без фиксации самого места.
4. `env` с не-строкой. `PYTHONHASHSEED: 0` уйдёт в `Profile.env` числом, и
   потребитель следующей части получит в окружении процесса int. AC это не
   ловит.

Для Оператора, не отклонение SPEC: перечень секретов, как его задало ТЗ
(«`secret_env_names()` провайдеров»), не включает ключи Codex
`FORBIDDEN_KEY_ENV_NAMES` (codex.py:114), потому что `CodexProvider.secret_env_names()`
пуст (codex.py:514). Имя `OPENAI_API_KEY` в `env` пройдёт `targets.check`.

## Вердикт
**concerns** — SPEC соответствует ТЗ и зонам, защищённые пути и песочница не
затронуты. Есть отклонения проверяемости и одна неточность о коде; их может
снять Оператор на гейте (уточнением SPEC или решением):

1. Требование 7 / AC-7 (SPEC.md:47–53, :81–85): «по обоим путям команды» для
   каждого из восьми мест не соответствует коду. У `run_plank` нет `command`
   (orchestrator/acceptance.py:923), у `two_sided._run_side` тоже нет
   (orchestrator/advance_gates/two_sided.py:222); `_run_full_suite_now`/
   `_run_full_suite_to_log` принимают готовый argv (orchestrator/acceptance.py:1313,
   :1361), второй путь у них — через `run_full_suite` (:1115). Нужно указание:
   у мест без `command` фиксируется единственный путь, а `_run_full_suite_*`
   по `command` фиксируются через `run_full_suite`.
2. AC-7 (SPEC.md:81): строгость фиксации не названа. Нужно требовать
   равенство argv и cwd и сверку окружения как разницы с `os.environ`
   (`PYTHONPYCACHEPREFIX` acceptance.py:86, `PYTHONUNBUFFERED` acceptance.py:1372,
   `PYTHONPATH`/`REPORT_ENV` two_sided.py:230–232).
3. AC-1 (SPEC.md:57): критерий не отличает перечень из реестра
   `secret_env_names()` от литерала. Нужен случай с подменённым набором имён
   провайдера.
4. Требование 4 / AC-6 (SPEC.md:34, :76): `env` как «отображение строк» без
   критерия отказа не-строке и не-отображению. При этом `yamlmini`
   типизирует значения (orchestrator/yamlmini.py:57–62): `0` → int,
   `true` → bool, пустое → None.
5. Требование 6 (SPEC.md:43–46): умолчания `Profile.workdir`/`Profile.env`
   при отсутствии подполя не названы (orchestrator/project_profile.py:63–85;
   kwargs-построение — tests/test_project_profile_gates.py:210,
   tests/test_network_address_gate.py:178).
6. Матрица: tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103 берёт
   `runner` как неизвестное подполе. После задачи этот случай проходит по
   правилу AC-3 и остаётся зелёным, только если отказ называет `test_profile`
   и `runner` (:151–152). SPEC не требует такого текста отказа (образец —
   orchestrator/targets.py:281).
