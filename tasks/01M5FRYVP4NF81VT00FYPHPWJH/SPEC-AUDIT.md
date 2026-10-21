---
task: 01M5FRYVP4NF81VT00FYPHPWJH
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/; в) пути-признаки (гейты): orchestrator/advance_gates/mandate.py, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/refusal_classes.py, orchestrator/advance_gates/two_sided.py; д) ТЗ ссылается на ADR: ADR-0026"
spec_sha: d786169c8f5d6977d261804e0afc874ef14ea173
schema_version: 5
---

# SPEC-AUDIT: G3а-2б-2: запрет повторов через плагины pytest и переносы из приёмок

## ТЗ и SPEC
ТЗ → SPEC: требование ТЗ 1 разложено на требования SPEC 1–3 и AC-1..AC-4;
переносы 11, 18, 20, 21, 22, 23 — требования 4–10 и AC-5..AC-12; п. 3 ТЗ
(детерминизм, существующие тесты без правок) — требование 11. Граница
задачи, исключения (перенос 11 — текст не меняется, перенос 18 — маркер и у
артели), «Не входит», «Только чтение», бюджет ($40 = верх рамки) перенесены
без потерь. ANSWER-n нет, решений Оператора на гейте SPEC в брифе нет.

Расхождения:
- **а1.** ТЗ п. 2 (18) требует тесты уборки, которые «зовут
  `doctor._fix_orphan_temp_dirs()` напрямую, не `cmd_doctor(fix=True)`»; в
  SPEC это осталось только в AC-8 («прямой вызов»), а требование 6
  (SPEC.md:73-83) этого не несёт. Потери смысла нет — замечание формы.
- **а2.** AC-4 (SPEC.md:116) добавляет то, чего нет в ТЗ: «та же запись под
  `test_profile` отказа не получает». ТЗ говорит только «запись
  `test_profile` не проверяется». В буквальном виде критерий невыполним
  (см. б4).
- SPEC без требований сверх ТЗ. Пункт «Не входит» про `auto.py`,
  `tests_writing.py`, `doctor/cli.py`, `doctor/__init__.py` повторяет список
  «Только чтение» ТЗ.
- Порядок «после G3а-2б-1» из «Фактов» ТЗ выполнен по факту: мерж 8b47a1f5
  (01M5EDW6KD) — предок HEAD ветки. Отсутствие `merge_after` (SPEC
  «Материалы») ничему не мешает.

## Факты против кода
Подтвердилось:
- `_pytest_command` — orchestrator/acceptance.py:37; `is_pytest_command` —
  :709; `_report_argv` — :725; `_report_suite_result_key` — :3170. Данные
  ключа (:3184-3192) аргументов пульта не несут.
- `in_outcome_bounds` — orchestrator/advance_gates/acceptance.py:213-217:
  `reported(profile) and from_components`.
- Литерал детали — orchestrator/fsm.py:1266; константа —
  orchestrator/advance_gates/tests_writing.py:623; третья копия —
  orchestrator/auto.py:314.
- `mkdtemp` в outcome_integrity.py:564 (`_gate` :556) и two_sided.py:452
  (`run` :433); `git worktree add` — outcome_integrity.py:364 (в `_checkouts`,
  внутри `try` `_gate`) и two_sided.py:457. Выписки ложатся в подкаталоги
  `scratch/base`/`scratch/head`, поэтому маркер в корне `scratch` git не
  мешает.
- `MERGE_REFUSAL_ACTION`/`MERGE_PREPARE_ACTION` — outcome_integrity.py:65-66;
  `OUTCOME_MERGE_REFUSAL_ACTION` — refusal_classes.py:92; у модуля
  refusal_classes импортов нет (refusal_classes.py:1-157).
- `_temp_owner_alive` — doctor/orphans.py:82; `_orphan_temp_dirs` — :106
  (фильтр префиксов `artel-canary-`/`artel-suite-base-`, :114);
  `_fix_orphan_temp_dirs` — :118; `liveness.owner_alive(directory, marker)` —
  liveness.py:39.
- `_component_covered` — mandate.py:495-510: сейчас признаёт любой токен
  или фрагмент в кавычках, который подходит под маску области (:508-510);
  `_PY_PATH_RE` — :402.
- Все прогоны по отчёту идут через `_report_argv`, то есть «каждый прогон»
  достижим одной правкой: вызовы `_report_run` — acceptance.py:1595, :1761,
  :1889, :2243, :2658; outcome_integrity.py:316; two_sided.py:359.

Не подтвердилось или не названо в SPEC:
- **б1. Круговой импорт у переноса 11.** Требование 4 (SPEC.md:61-66)
  требует, чтобы fsm брал деталь «импортом из `advance_gates.tests_writing`»,
  но не говорит, что импорт должен быть ленивым. При модульном импорте в
  fsm.py получается цикл. advance_gates/acceptance.py:17-18 импортирует
  `fsm` на уровне модуля, tests_writing.py:15 — `.acceptance`. Тогда
  `import orchestrator.advance_gates.acceptance` первым кончится цепочкой
  acceptance(частично) → fsm → tests_writing → `from .acceptance import
  blob_sha256` → ImportError. ТЗ такую оговорку сделал для acceptance.py, а
  для fsm.py нет. Нужен импорт внутри `_cmd_approve` — так fsm.py уже
  импортирует в :792, :1127, :1210 и других местах.
- **б2.** Точка подмены `_project_clones` не названа. doctor/orphans.py:38
  зовёт `_project_clones()` по локальному имени, а тесты doctor подменяют
  имена фасада: `mock.patch.object(doctor, …)`, как в
  tests/test_canary_doctor_owner.py:19 и tests/test_doctor_closed_ref_fix.py:169.
  Если планка подменит `doctor._project_clones`, а код позовёт локальное имя
  (или наоборот), подмена не сработает. Тогда тест AC-8 выполнит `git
  worktree prune` в настоящих клонах пульта (`workspace.repo(n)`).
- **б3.** Требование 6 не оговаривает, что ветка для
  `artel-outcome-*`/`artel-two-sided-*` в `_temp_owner_alive` должна стоять до
  общей проверки `owner_alive(path)` с маркером канарейки
  (doctor/orphans.py:98). Формулировка «возвращает только» это подразумевает,
  но AC-7 не ловит, если ветку поставить после :98 (см. в).
- **б4. AC-4 невыполним для `select`/`report_args`.** Этих полей нет в
  `PROFILE_FIELDS` (targets.py:45-61) — они только в `COMPONENT_FIELDS`
  (targets.py:94-95). `_check_profile` отказывает неизвестному подполю
  (targets.py:356-360). Поле `env` у `test_profile` допустимо только при
  `runner: pytest-own` (targets.py:370-377), а `report` — только `junit-xml`
  (targets.py:69). «Та же запись под `test_profile`» с запрещённым
  аргументом в `select`/`report_args` ОТКАЗ получит — по другой причине.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | флаги после подмножества или `report_args`; флаги у артели или у `test_profile`; правка `_pytest_command` |
| AC-2 | частично | условие только `reported(profile)` (флаги у `pytest-own`+`report`) — ловится. Условие только `from_components` не ловится: у артели и у `test_profile` без `report` `_report_argv` отказывает до сборки argv («нет {path}», acceptance.py:731-737), и проверка у них пустая |
| AC-3 | да | поле в ключе у всех профилей (ключ `test_profile` сменился); поле не добавлено (ключ компонента прежний) |
| AC-4 | нет в буквальном виде | формы ловятся; часть «та же запись под `test_profile` отказа не получает» невыполнима для `select`/`report_args` (б4). Варианты с пробелами вокруг имени не названы (е1) |
| AC-5 | да | литерал остался в fsm.py; деталь разошлась с константой |
| AC-6 | да | маркер после `worktree add`; маркер не у артели; содержимое не pid |
| AC-7 | частично | каталоги не включены в `_orphan_temp_dirs` — ловится. Если ветку гейта поставить ПОСЛЕ `owner_alive(path)` (doctor/orphans.py:98), каталог с живым `.artel-canary-owner` без маркера гейта уцелеет, а AC-7 этот случай не проверяет (б3) |
| AC-8 | да | удалён каталог живого владельца; prune не вызван; git вызван без удалений |
| AC-9 | да (регресс) | `_component_covered` зовётся вне границы |
| AC-10 | частично | прежнее широкое правило ловится. «Иной знак сразу за путём» неоднозначен: `_TOKEN_SPLIT_RE = [\s`,;()«»]+` (mandate.py:392) режет по запятой, точке с запятой и скобкам, так что «src/a.test.ts,» даёт токен-путь. Тест на запятую и код по ТЗ разойдутся. Не сказано, снимается ли выделение `*`/`_` (сейчас `strip("*_")`, mandate.py:509-510) |
| AC-11 | да | ключа нет в `REFUSAL_CLASSES` (индексация даёт KeyError), не тот класс |
| AC-12 | слабо | проверка на равенство не ловит главную мутацию требования 10: в outcome_integrity осталась своя копия литерала с тем же текстом. Нужна проверка текста модуля (как в AC-5) или `is` |

## Зоны
Зоны SPEC совпадают с зонами ТЗ и покрывают все требования: acceptance.py
(1, 2), targets.py (3), fsm.py (4), liveness.py, outcome_integrity.py,
two_sided.py (5), doctor/orphans.py (6), mandate.py (7, 8),
refusal_classes.py и outcome_integrity.py (9, 10), tests/.
docs/codebase-map.md и config.py — в `config.COMMON_ZONES` (config.py:814),
карту можно регенерировать без расширения зон. Защищённых путей
(`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) требования
не трогают. Песочница ролей не расширяется. Правка read-only путей не
нужна: константа в tests_writing.py:623 уже есть, auto.py остаётся
литералом по ТЗ, `_fix_orphan_temp_dirs` уже в фасаде
(doctor/__init__.py:153).

## Матрица неослабления
Раздела «Матрица неослабления» и раздела «Меняемое поведение» в SPEC нет.
Существующие тесты по требованию 11 не правятся. Ниже — свойства, которые
задача трогает; ни одно не ослабляется.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `_component_covered` (mandate.py:495) | признание «Чем покрыто после» компонента в границе — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py:785, :831 | да, сужается (идентификатор и `src/…test.ts` остаются покрытием) | существующие AC-17/AC-18 + новый тест AC-10 | ок |
| `_temp_owner_alive`/`_orphan_temp_dirs`/`_fix_orphan_temp_dirs` (doctor/orphans.py:82-128) | живые каталоги канарейки и базы не удаляются — tests/test_canary_doctor_owner.py:26, :46 | да | те же тесты + новые AC-7/AC-8 | ок |
| `_report_suite_result_key` (acceptance.py:3170) | переиспользование итога и «доказан» гейта исходов на мерже (outcome_integrity.py:399-412) | да; прежние ключи компонентов обесцениваются — прогон заново, не пропуск | новый тест AC-3 | ок |
| текст `MERGE_*_ACTION` (outcome_integrity.py:65-66) | класс отказа в `auto` — tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:493 | да | тот же тест + AC-11/AC-12 | ок |

## Пути обхода гейтов
- **е1. Пробел вокруг имени плагина.** pytest 9.1.1
  (`PytestPluginManager.consider_preparse`) делает `parg.strip()`, а
  `-p <имя>` снимает блок, поставленный `-p no:<имя>` раньше
  (`consider_pluginarg` → `unblock`). Элементы `-p`, `" rerunfailures"` и
  один элемент `"-p rerunfailures"` (с пробелом) снова загружают плагин, а
  буквальное правило требования 3 (SPEC.md:55-57) их не ловит. В `select` и
  `report_args`, которые в argv стоят ПОСЛЕ `-p no:…`, это рабочий обход:
  `--reruns` снова действует, отчёт junit повторов не видит. В `command` и
  `PYTEST_ADDOPTS` (они раньше блока) вред снимает поздний `no:`. Правило
  стоит сверять по имени после `strip()`.
- **е2. `env.PYTEST_PLUGINS`.** `-p no:flaky` блокирует имена `flaky` и
  `pytest_flaky`, но не модуль `flaky.flaky_pytest_plugin`. Значение
  `PYTEST_PLUGINS=flaky.flaky_pytest_plugin` в `env` компонента (pytest-own)
  его загрузит, а `targets.check` по требованию 3 смотрит только
  `PYTEST_ADDOPTS`. У `rerunfailures` этот путь закрыт: блокируется и
  `pytest_rerunfailures`. Это вне буквы ТЗ — вопрос Оператору, расширять ли
  проверку.
- **е3.** Другие плагины повторов (например, pytest-retry), а также
  `pytest_plugins` в conftest.py проекта ТЗ не покрывает — только к сведению,
  в смысл ADR-0026 п. 4 это входит.
- **е4.** AC-12, исполненный буквально (равенство), допускает оставить в
  outcome_integrity свои копии литералов — второй источник текста, ради
  устранения которого и задан перенос 23.

## Вердикт
concerns. SPEC верен по фактам и зонам. Отклонения ниже решаемы на гейте
уточнением формулировок, без нового разбора:

1. AC-4 (SPEC.md:116) невыполним в буквальном виде: у `test_profile` нет
   `select`/`report_args` (targets.py:45-61, :356-360), `env` — только при
   pytest-own (targets.py:370-377). Ограничить «ту же запись под
   `test_profile`» полями `command` и `env.PYTEST_ADDOPTS` при
   `runner: pytest-own`. (б4, а2)
2. Требование 3 (SPEC.md:52-57) пропускает `-p`, `" rerunfailures"` и
   `"-p rerunfailures"` — pytest делает strip имени. В `select`/`report_args`
   это обход запрета. (е1)
3. Требование 4 (SPEC.md:63-64) не оговаривает ленивый импорт.
   Модульный импорт tests_writing в fsm.py даёт ImportError по циклу
   advance_gates/acceptance.py:17-18 → fsm → tests_writing.py:15. (б1)
4. AC-8 (SPEC.md:124) не называет точку подмены `_project_clones`
   (локальное имя doctor/orphans.py:38 против фасада `doctor`). При
   расхождении тест выполнит `git worktree prune` в настоящих клонах. (б2)
5. AC-10 (SPEC.md:128): «иной знак сразу за путём» неоднозначен при
   разделителях `_TOKEN_SPLIT_RE` (mandate.py:392); не сказано про снятие
   выделения `*`/`_` (mandate.py:509-510).
6. AC-12 (SPEC.md:132) проверяет только равенство и не ловит оставленную
   копию литерала. (е4)
7. AC-7 (SPEC.md:122) не проверяет, что маркер канарейки не защищает
   каталог выписки (doctor/orphans.py:98). (б3)
8. На усмотрение Оператора: `env.PYTEST_PLUGINS` с
   `flaky.flaky_pytest_plugin` обходит `-p no:flaky` (е2); другие плагины
   повторов (е3) вне ТЗ.
