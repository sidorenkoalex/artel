---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py, tests/test_acceptance_plank_exclude_lock.py, tests/test_acceptance_plank_layout_refusal.py, tests/test_task_component_places.py; в) пути-признаки (гейты): orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/two_sided.py; д) ТЗ ссылается на ADR: ADR-0027
spec_sha: 1431db7da244a74e75f37ace2294f91c9dfa6180
schema_version: 5
---

# SPEC-AUDIT: CR-8, этап 1 — самодостаточная часть выкладки планки в `plank_layout`; публичные имена для закрытых имён `acceptance`

Проверено на рабочем каталоге, HEAD 2b187a3d. `git diff --stat 84c784aa HEAD -- orchestrator scripts tests` пуст, поэтому номера строк ТЗ и SPEC (база 84c784aa) совпадают с деревом. ANSWER-n и решений Оператора на гейте SPEC нет.

## ТЗ и SPEC
Каждое требование ТЗ есть в SPEC:
- ТЗ 1 → SPEC 1–2;
- ТЗ 2 → SPEC 3;
- ТЗ 3 → SPEC 4–5;
- ТЗ 4 → SPEC 6;
- ТЗ 5 → SPEC 7 и 8(д);
- ТЗ 6 → SPEC 8;
- ТЗ 7 → SPEC 9;
- ТЗ 8 → SPEC 10;
- ограничение зон ТЗ → SPEC 11;
- «Не входит» и «Только чтение» ТЗ → SPEC «Не входит».

В обратную сторону: требований сверх ТЗ в SPEC нет. Перечень из 13 закрытых имён (SPEC.md:66) — это ровно объединение списков ТЗ «Факты» без `_last_full_suite_metrics`.

У ТЗ 8 потерялась формулировка «остаются зелёными»: SPEC.md:249 переносит полный зелёный набор в «Не входит». Это конвенция `skills/spec-authoring.md:20–25` («держит пульт»), поэтому не отклонение.

## Факты против кода
Подтвердилось:
- Блок выкладки — `orchestrator/acceptance.py:1200–1494`. Состав самодостаточной части совпадает с определениями: :1200–1205, :1210, :1215, :1238, :1242, :1253, :1284, :1295, :1333–1343, :1346, :1354, :1389, :1432, :1442.
- Несамодостаточная часть стоит там, где сказано, и зовёт то, что сказано: `_layout_ignore` :1224 → `_own_target`; `_layout_check` :1363 → `_inside_real` :578 и `_component_name` :428; `_plank_plan` :1401 → `plank_present` :1181, `is_pytest_command` :709 и ленивый `project_profile` :1408; `_component_layout` :1450 → `PLANK_HELPER_NAME` :2010; `_laid_plank` :1481.
- Места вызова: `_link_deps` → `_exclude_pattern` :605; `drop_from_code_copy` :2169–2176; `run_plank` :2227, :2240; `_component_target` :2287.
- Перенесённой части нужны `os` (`_inside`), `contextlib`, `shutil`, `fcntl`, `gitcmd.in_repo`, `Path`, `NamedTuple`, `Iterator`. `acceptance` после переноса по-прежнему сам использует `fcntl` (:510, :517), поэтому `mock.patch.object(acceptance.fcntl, "flock", …)` (`tests/test_acceptance_plank_layout_refusal.py:131`) продолжает подменять общий модуль. То же для `acceptance.shutil` (`tests/test_acceptance_pycache.py:155`).
- Закрытые имена `acceptance` в коде других модулей (`grep -rnoE "acceptance\._[a-zA-Z_]+" orchestrator scripts`):
  - `suite_run.py`: :109, :348, :417, :611, :632, :665, :666, :678, :684, :686;
  - `two_sided.py`: :289–307, :359;
  - `outcome_integrity.py`: :422, :714, :821;
  - `tests_writing.py`: :601;
  - `plank_run.py`: :227, :260;
  - `amend.py`: :765, :957;
  - `pull.py`: :667;
  - `doctor/machine_load.py`: :9.

  Прочие совпадения — только в комментариях и докстрингах: `two_sided.py:279` (`_pytest_command`), `plank_run.py:41` и `:110`, `outcome_integrity.py:12`, `fsm_autogate.py:48`, `models.py:1019`, `plank_helper.py:34`, `project_profile.py:424`. Перечень SPEC из 13 имён полный.
- Подмен тестами имён из этого перечня нет. Проверено разбором `ast` всех вызовов с первым аргументом `acceptance` или `<…>.acceptance` и строкой-именем вторым аргументом (patch.object, setattr), а также строковых целей `"orchestrator.acceptance.…"`. Подменяются только `PLANK_HELPER_NAME`, `_CACHE_RMTREE_PAUSE_SEC`, `_acceptance_suite_run`, `_machine_lock`, `_pytest_env`, `_run_full_suite_now`, `_run_pytest`, `_task_profile`, `_write_full_suite_log`, `plank_present` и публичные имена. Присваивание есть одно — `_last_full_suite_metrics` (`tests/test_suite_run.py:450`).
- Подмен перенесённых имён в тестах нет, поэтому внутренние вызовы `plank_layout` через свои глобалы поведение тестов не меняют.
- `_durations_reader` — `acceptance.py:2855`, импорт :2862 вне `try`, цикл `suite_durations` → `suite_run` → `acceptance` — подтверждено.
- `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py:410–417` ищет `orchestrator.acceptance` в стеке. После переноса `gitcmd.in_repo` зовётся из `plank_layout`, но в стеке по-прежнему стоит вызывающая функция `acceptance` (`_laid_plank`/`run_plank`). Адресный прогон SPEC 10 это закрывает.

Не подтвердилось или неточно:
- SPEC.md:115 и :182 перечисляют формы импорта `orchestrator.acceptance`: `from orchestrator import acceptance`, `from . import acceptance` верхнего пакета, `doctor.acceptance`. На деле три из восьми вызывающих модулей импортируют иначе — `from .. import acceptance`: `orchestrator/advance_gates/two_sided.py:38`, `orchestrator/advance_gates/outcome_integrity.py:58`, `orchestrator/advance_gates/tests_writing.py:10`. Так же `doctor/__init__.py:96` и `advance_gates/acceptance.py:17`. А формы `from orchestrator import acceptance` в `orchestrator/` и `scripts/` нет ни одной. См. отклонение 1.
- `_durations_reader` уже держит конструктор и `start()` под `try/except Exception` (`acceptance.py:2864–2868`); вне `try` стоит только импорт. Это задаёт ловимость AC-7, см. ниже.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | публичное имя не объявлено (например, оставлен `_drop_layout` без `drop_layout`); появился публичный двойник `inside`/`layout_parent`/`LAYOUT_ID` |
| AC-2 | да | в `plank_layout.py` добавлен импорт `acceptance`, в том числе ленивый (ради `_own_target`/`_component_name`) |
| AC-3 | да | константа или функция переопределена в `acceptance.py` копией, а не реэкспортом (`is` ложно); текст отказа изменён хоть на символ |
| AC-4 | да, слабо | несамодостаточная функция перенесена в `plank_layout` без имени в `acceptance`. Переноса с реэкспортом (`_plank_plan = plank_layout._plank_plan`) тест не ловит; запрет держит только требование 2 и ревью |
| AC-5 | да | публичное имя не объявлено или указывает на обёртку; закрытое имя удалено; объявлено `last_full_suite_metrics` |
| AC-6 | частично | формы SPEC.md:182 ловят «оставлен на закрытом имени» только в `suite_run`, `plank_run`, `amend`, `pull`, `doctor/machine_load`. Для `two_sided`, `outcome_integrity` и `tests_writing` (`from .. import acceptance`) тест, написанный по букве, мутацию не ловит — отклонение 1 |
| AC-7 | частично | ловит снятие `except` вокруг `Reader(...).start()`. Не ловит отмену самой правки требования 7 (импорт снова вне `try`): на main AC-7 уже зелёный. Тест не ловит ничего, если прогон идёт без `log=` или с профилем `pytest-own` — тогда поток не запускается (`acceptance.py:2859–2861`, :2892–2893). «Тот же лог» побайтно недостижим: итоговая строка pytest несёт время — отклонения 2–4 |
| AC-8 | да, ревью | PLAN без результата поиска или без списка файлов — ревью и аудит PLAN, не тест |

Требования 2 и 3 во второй половине («вызовы внутри `acceptance.py` идут через прежние имена») и требование 6 (argv, окружение, ключ кэша) своего AC не имеют. Объекты те же, поэтому наблюдаемо это только через подмену в тестах; держат существующие тесты адресного прогона SPEC 10. Отклонением не считаю.

## Зоны
- Зоны SPEC совпадают с ТЗ и покрывают всё, что требует правки: новый модуль, `acceptance.py`, восемь вызывающих модулей, карта, `tests/` (новые файлы).
- `scripts/` правки не нужны: закрытых имён `acceptance` там нет.
- Защищённые пути (`orchestrator/config.py:769–775`) внутри зоны `tests/` — `tests/test_invariants.py` и `**/conftest.py`. SPEC исключает их «Не входит» (SPEC.md:234–235) и правилом «только новые файлы».
- Песочница ролей не расширяется.
- Карта `docs/codebase-map.md` в зоне, регенерация — требование 9.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| перенос `_exclude_layout`/`_exclude_pattern` в `plank_layout` | шаблон в `info/exclude` под `flock`, без дублей — `tests/test_acceptance_plank_exclude_lock.py:36–76` через `acceptance._exclude_layout` | да (реэкспорт тем же объектом) | тот же тест без правки + AC-3 | остаётся |
| перенос `_plank_layout`, `_drop_layout`, констант отказа | отказ выкладки при сбое записи exclude — `tests/test_acceptance_plank_layout_refusal.py:48, 131` | да: `acceptance.fcntl` — тот же модуль, `acceptance.py:510` его использует | тот же тест + AC-3 (тексты побайтно) | остаётся |
| перенос `_uses_plank_layout`, `_layout_parent`, `_drop_component_layout`, `LAYOUT_*` | выкладка по `plank_layout`, текст `LAYOUT_OUTSIDE_NOTE` — `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py:1239` | да | тот же тест + AC-3 | остаётся |
| замена `acceptance._reported/_own/...` на публичные имена в `two_sided.py`, `outcome_integrity.py`, `tests_writing.py` (гейты) | двусторонний прогон, перепрогон красных, ключ итога — существующие тесты гейтов; файловый уровень по стеку — `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py:410–417` | да (тот же объект) | существующие тесты + AC-5; AC-6 по этим трём модулям — не покрыто при буквальном чтении SPEC.md:182 | отклонение 1 |
| импорт `suite_durations` внутрь `try` | «сбой потока прогон не меняет» — тест на запуск потока отсутствует (ТЗ «Факты») | да, усиливается | AC-7 (новый тест); ветка «сбой импорта» — не покрыто | отклонение 2 |

Существующие тесты, гейты и лимиты не ослабляются. Раздела «Меняемое поведение» в SPEC нет, и он не нужен: смены ожиданий существующих методов нет.

## Пути обхода гейтов
1. Тест AC-6 по формам SPEC.md:182 строится буквально и не видит `from .. import acceptance`. Тогда разработчик может оставить `two_sided`/`outcome_integrity`/`tests_writing` на закрытых именах при зелёном тесте. Это ровно три модуля-гейта из сигнала «пути-признаки (гейты)». Отклонение 1.
2. Тест AC-7 запускается без `log=` или с профилем `pytest-own`. Поток не создаётся, подмена `Reader.start` не срабатывает, тест зелёный при любой мутации. SPEC.md:185 не называет условие запуска потока (раннер пульта, `profile is None`, прогон в файл лога). Отклонение 3.
3. Константа исключений AC-6 расширяется именами «по требованию 5» (SPEC.md:91–92) без проверки, что подмена существует. На базе ветки подмен нет (раздел «Факты против кода»), но SPEC не фиксирует, что исключение — ровно `{"_last_full_suite_metrics"}`, если поиск ничего не нашёл. Держит только ревью PLAN. Замечание к отклонению 1, отдельным отклонением не считаю.
4. Обращение `getattr(acceptance, "_reported")` разбор `ast` по атрибутам не видит. В коде сегодня такой формы нет; замечание, не отклонение.

## Вердикт
**concerns.** SPEC верно переносит ТЗ, факты о коде подтверждены, перечень 13 имён полный, подмен этих имён тестами нет. Отклонения решаемы Оператором на гейте:

1. **Формы импорта в AC-6 и 8(г) неполны** — SPEC.md:110–116, :177–184. Вызывающие модули `orchestrator/advance_gates/two_sided.py:38`, `orchestrator/advance_gates/outcome_integrity.py:58` и `orchestrator/advance_gates/tests_writing.py:10` берут `orchestrator.acceptance` формой `from .. import acceptance`, которой в перечне нет. Тест по букве пропускает мутацию «вызывающий модуль оставлен на закрытом имени» в трёх гейтах из восьми модулей. Перечень наследован из ТЗ (требование 6(г)), так что править его — Оператору. Предложение: форма «относительный импорт, разрешающийся в `orchestrator.acceptance` (`from . import acceptance` в `orchestrator/*.py`, `from .. import acceptance` в подпакетах), плюс `doctor.acceptance`». Различать `from .acceptance import …` и `acceptance_gates` в `advance_gates` по-прежнему как другой модуль.
2. **AC-7 не ловит отмену самой правки требования 7** — SPEC.md:185–189 против `acceptance.py:2862–2868`. `try` вокруг `Reader(...).start()` уже есть, поэтому тест со сбоем `Reader.start` зелёный и на main. Перенос импорта внутрь `try` тестом не закреплён. Мутация «импорт снова вне `try`» не ловится; ловить её мог бы сбой импорта, например `sys.modules["orchestrator.suite_durations"] = None` на время прогона. Строка «Ловит мутацию» наследована из ТЗ 5.
3. **AC-7 не называет условие, при котором поток запускается** — SPEC.md:185. Поток идёт только у раннера пульта (`profile is None`) с прогоном в файл лога (`acceptance.py:2859–2861`, :2892–2893, `run_full_suite(..., log=...)`). Без этого условия тест может пройти вхолостую.
4. **«Тот же лог» в AC-7 побайтно недостижим** — SPEC.md:187. Итоговая строка pytest несёт длительность (`in 0.0Xs`), и два прогона дают разный лог. Нужно уточнить сравнение: итог и строки результатов тестов без времени, отсутствие строк трассировки исключения.
5. **(мелкое) AC-4 не ловит перенос несамодостаточной функции в `plank_layout` с реэкспортом** — SPEC.md:164–167. Запрет держат только требования 2/11 и ревью; можно усилить сверкой `acceptance._plank_plan.__module__ == "orchestrator.acceptance"` для пяти имён.

Эскалация не нужна: каждое отклонение решается уточнением формулировки на гейте без выбора между существенно разными реализациями.

## Предложения системе
- `skills/spec-audit.md` / ТЗ Оператора: перечни «форм импорта модуля» в тестах-сторожах стоит сверять с `grep -rn "import.*\bacceptance\b"` по подпакетам — `from .. import X` легко пропустить, когда список пишется по модулям верхнего уровня.
