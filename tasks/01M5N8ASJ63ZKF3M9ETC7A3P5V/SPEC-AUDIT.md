---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: spec_audit
author_role: spec_auditor
status: ready
verdict: pass
signals: "в) пути-признаки (тесты): tests/, tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py, tests/test_acceptance_plank_exclude_lock.py, tests/test_acceptance_plank_layout_refusal.py, tests/test_task_component_places.py; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/two_sided.py; д) ТЗ ссылается на ADR: ADR-0027."
spec_sha: aeb82033b9806883716a2ef2ba9308bac2422cbc
schema_version: 5
---

# SPEC-AUDIT: CR-8, этап 1 — самодостаточная часть выкладки планки в `plank_layout`; публичные имена для закрытых имён `acceptance`

Круг 3. Рабочий каталог на 2b187a3d; `git diff 84c784aa..HEAD -- orchestrator scripts tests` пуст, поэтому номера строк ТЗ и SPEC действуют.

## ТЗ и SPEC
- ТЗ п.1 → SPEC п.1–2. Список перенесённого, публичные имена и закрытые `_inside`, `_layout_parent`, `_LAYOUT_ID` совпадают дословно. Совпадает и запрет импорта `acceptance`.
- ТЗ п.2 → SPEC п.3 (реэкспорт тем же объектом; вызовы внутри `acceptance.py` идут через прежние имена).
- ТЗ п.3 → SPEC п.4–5. SPEC явно перечисляет 13 имён. ТЗ даёт их перечнем по модулям, и списки совпадают. Исключение `_last_full_suite_metrics` и повторный поиск подмен в четырёх формах сохранены.
- ТЗ п.4 → SPEC п.6. ТЗ п.5 → SPEC п.7 и 8(д). ТЗ п.6(а–д) → SPEC п.8(а–д). ТЗ п.7–8 → SPEC п.9–10. Ограничение зон по смыслу → SPEC п.11. «Не входит» перенесено полностью.
- Решения Оператора на гейте №1 (пять пунктов) отражены так:
  - формы импорта — SPEC 8(г) и AC-6;
  - второй сценарий и условие запуска потока — 8(д) и AC-7;
  - сравнение без длительностей — AC-7;
  - проверка `__module__` — AC-4.
- Решение №2 (снять атрибут пакета вместо `None`, проверить `ImportError` перед прогоном) отражено в 8(д) и AC-7 дословно.
- В SPEC нет требований, которых нет в ТЗ или в решениях. Расхождений не найдено.

## Факты против кода
- Блок выкладки — `orchestrator/acceptance.py:1200–1495`. Переносимая часть самодостаточна. Её внешние вызовы:
  - `gitcmd.in_repo` (:1256);
  - `fcntl.flock` (:1268, :1277);
  - `shutil.rmtree`/`copytree` (:1287, :1316, :1318, :1444);
  - `contextlib`, `os.path`.

  Она не зовёт ни `_own_target`, ни `_inside_real`, ни `_component_name`.
- Несамодостаточная часть устроена так, как пишет SPEC:
  - `_layout_ignore` → `_own_target` (:1231);
  - `_layout_check` → `_inside_real`, `_component_name`, `gitcmd` (:1374–1379);
  - `_plank_plan` → `plank_present`, `project_profile`, `is_pytest_command` (:1404–1419);
  - `_component_layout` → `PLANK_HELPER_NAME` (:1469).
- `_PlankPlan` и `_Laid` — `NamedTuple` без методов (:1389, :1432). У перенесённого кода нет методов, которые зовут git вне стека `acceptance`. Поэтому проверка «git из модуля раннера» по стеку (`tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py:75–78`, :410–417) не сломается: перенесённое вызывается только из функций `acceptance`.
- 13 закрытых имён, которые берут другие модули, подтверждены поиском. Примеры: `suite_run.py:109, 348, 417, 611, 632, 665–666, 686`; `two_sided.py:289–307, 359`; `outcome_integrity.py:422, 714, 821`; `tests_writing.py:601`; `plank_run.py:227, 260`; `amend.py:765, 957`; `pull.py:667`; `doctor/machine_load.py:9`. `_last_full_suite_metrics` — `suite_run.py:678, 684`.
- В `tests/` подмен этих 13 имён нет (поиск по `patch…"<имя>"`, присваиванию `acceptance.<имя> =` и строке `orchestrator.acceptance.<имя>`).
- `_durations_reader` — `acceptance.py:2855–2872`. Импорт на :2862 стоит вне `try`, ветка `profile is not None` на :2859. `suite_durations` импортируется ещё только в `suite_run.py:698` (команда `suite-run`, не путь `run_full_suite`). Значит, в сценарии 2 AC-7 на правильном коде прогон ничто другое не уронит.
- Тесты существующих файлов обращаются к перенесённой части только через `acceptance.PLANK_LAYOUT_EXCLUDE`, `acceptance._exclude_layout`, `acceptance.PLANK_LAYOUT_DIR`, `acceptance.LAYOUT_OUTSIDE_NOTE`. Это `tests/test_acceptance_plank_exclude_lock.py:36,50,55,76`, `…layout_refusal.py:48`, `…component_plank_layout.py:1239`. Подмен функций перенесённой части нет. Значит, внутренние вызовы внутри `plank_layout` в обход реэкспорта ничью подмену не обойдут.
- Полные имена файлов из SPEC п.10: `tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py`, `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py`.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | имя не перенесено или осталось только с подчёркиванием; появился публичный двойник `_inside`/`_layout_parent`/`_LAYOUT_ID` |
| AC-2 | да (`ast`, включая ленивые импорты) | `plank_layout` берёт `_own_target` или иное имя из `acceptance` импортом |
| AC-3 | да | копия функции или константы в `acceptance` вместо реэкспорта; изменён текст отказа |
| AC-4 | да (`__module__`) | несамодостаточная функция перенесена в `plank_layout` и реэкспортирована |
| AC-5 | да | публичное имя не объявлено или указывает на обёртку; заведено `last_full_suite_metrics` |
| AC-6 | да (`ast` по формам решения №1) | вызывающий модуль оставлен на закрытом имени, включая `doctor.acceptance._process_snapshot` |
| AC-7 | да, два сценария с защитой от холостого прогона | сценарий 1: убран `except` вокруг `Reader(...).start()`; сценарий 2: импорт снова вне `try` |
| AC-8 | да (чтение PLAN на ревью) | PLAN без результата поиска подмен или без списка адресных прогонов |

## Зоны
- Зоны SPEC совпадают с зонами ТЗ и покрывают все правки:
  - новый модуль;
  - `acceptance.py`;
  - 8 вызывающих модулей;
  - карту;
  - новые файлы в `tests/`.
- Защищённых путей задача не трогает. `tests/test_invariants.py` указан только для чтения. Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Перенос выкладки в `plank_layout` | тексты отказов и шаблон исключения — `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py:1239`; замок `info/exclude` — `tests/test_acceptance_plank_exclude_lock.py:36–76`; отказ записи — `tests/test_acceptance_plank_layout_refusal.py:48, 131` | да: реэкспорт тем же объектом, тесты не правятся | те же тесты (SPEC п.10) + новые AC-1–AC-4 | остаётся |
| Вызывающие модули на публичных именах | поведение гейтов `two_sided`, `outcome_integrity`, `tests_writing`, `suite-run` — существующие тесты этих модулей | да: тот же объект | существующие тесты + AC-5, AC-6 | остаётся |
| `_durations_reader`: импорт внутри `try` | «сбой потока прогон не меняет» — было не покрыто | усиливается | AC-7 (новый файл) | усиление |

Раздела «Меняемое поведение» в SPEC нет, и он не нужен: смены ожиданий существующих тестов задача не вносит.

## Пути обхода гейтов
- `from orchestrator.acceptance import _x` / `from .acceptance import _x` в модуле верхнего пакета не входят в формы AC-6. Сейчас такой формы нет; единственный случай — `project_profile.py:461, 651` с публичным `is_pytest_command`. Перечень форм установил Оператор решением №1. Замену `acceptance._x` на такой импорт запрещает и SPEC п.11 («только замена на публичное»), так что ловит её ревью. Это не отклонение.
- Перечислить исключения требования 5 «по находке» и так обойти AC-5/AC-6 нельзя: SPEC требует приложить результат поиска к PLAN (AC-8), а подмен 13 имён на базе нет (поиск выше).

## Вердикт
pass. Отклонений нет. Решения Оператора кругов 1 и 2 перенесены в SPEC полностью (SPEC п.8(г), 8(д), AC-4, AC-6, AC-7). Факты SPEC сверены с кодом (`acceptance.py:1200–1495`, :2855–2872; вызывающие модули — раздел «Факты против кода»). Каждый AC ловит правдоподобную мутацию.
