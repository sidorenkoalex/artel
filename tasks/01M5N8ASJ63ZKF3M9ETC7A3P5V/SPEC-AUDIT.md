---
task: 01M5N8ASJ63ZKF3M9ETC7A3P5V
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py, tests/test_acceptance_plank_exclude_lock.py, tests/test_acceptance_plank_layout_refusal.py, tests/test_task_component_places.py; в) пути-признаки (гейты): orchestrator/advance_gates/, orchestrator/advance_gates/outcome_integrity.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/two_sided.py; д) ТЗ ссылается на ADR: ADR-0027
spec_sha: 7607c201b2bee2bdc5a0086b454fa933cf8e6fae
schema_version: 5
---

# SPEC-AUDIT: CR-8, этап 1 — самодостаточная часть выкладки планки в `plank_layout`; публичные имена для закрытых имён `acceptance` (круг 2)

Проверка шла по рабочему каталогу, HEAD 2b187a3d. `git diff --stat 84c784aa HEAD -- orchestrator scripts tests` пуст, поэтому номера строк ТЗ и SPEC (база 84c784aa) совпадают с деревом. ANSWER-n нет. Есть одно решение Оператора на гейте SPEC (24.10.2026, круг 1): приняты все пять предложений аудита круга 1.

## ТЗ и SPEC
Соответствие ТЗ ↔ SPEC такое же, как в круге 1:
- ТЗ 1 → SPEC 1–2;
- ТЗ 2 → SPEC 3;
- ТЗ 3 → SPEC 4–5;
- ТЗ 4 → SPEC 6;
- ТЗ 5 → SPEC 7 и 8(д);
- ТЗ 6 → SPEC 8;
- ТЗ 7 → SPEC 9;
- ТЗ 8 → SPEC 10;
- ограничение зон → SPEC 11;
- «Не входит» и «Только чтение» → SPEC «Не входит».

Требований сверх ТЗ и решения Оператора в SPEC нет.

Решение Оператора на гейте №1 перенесено полностью:
- п.1 → SPEC.md:110–124 и :196–207. Формы: абсолютный импорт, включая `import orchestrator.acceptance`; относительный по пути файла; `doctor.acceptance`; оговорка про `advance_gates.acceptance`.
- п.2 → SPEC.md:133–136 и :214–216: второй сценарий, «импорт снова вне try».
- п.3 → SPEC.md:126–129 и :209–212: `profile is None`, `log=`, проверка, что без сбоя файл времени появляется.
- п.4 → SPEC.md:138–141 и :216–220: итог, строки `PASSED/FAILED <id>` без длительностей, нет трассировки.
- п.5 → SPEC.md:182–188: `__module__ == "orchestrator.acceptance"` у пяти имён.

Перечень 13 закрытых имён (SPEC.md:66) — это объединение списков ТЗ «Факты» без `_last_full_suite_metrics`.

## Факты против кода
Подтвердилось:
- Блок выкладки `orchestrator/acceptance.py:1200–1494` и состав самодостаточной части совпадают с кодом. Несамодостаточная часть и её зависимости тоже: `_own_target`, `_inside_real` :578, `_component_name` :428, `plank_present` :1181, `is_pytest_command` :709, `PLANK_HELPER_NAME` :2010.
- Закрытые имена `acceptance` в вызывающих модулях подтверждены:
  - `suite_run.py`: :109, :348, :417, :611, :632, :665–686;
  - `two_sided.py`: :289–307, :359;
  - `outcome_integrity.py`: :422, :714, :821;
  - `tests_writing.py`: :601;
  - `plank_run.py`: :227, :260;
  - `amend.py`: :765, :957;
  - `pull.py`: :667;
  - `doctor/machine_load.py`: :9 (`from orchestrator import doctor`, :3).
- Формы импорта из SPEC.md:113–121 сверены с `grep "import.*\bacceptance\b"` по `orchestrator/` и `scripts/`:
  - верхний пакет: `from . import (acceptance, …)` (`suite_run.py:53`, `plank_run.py:31`, `amend.py:36`, `pull.py:37`);
  - подпакеты: `from .. import acceptance` (`advance_gates/two_sided.py:38`, `outcome_integrity.py:58`, `tests_writing.py:10`, `doctor/__init__.py:96`);
  - через пакет: `doctor.acceptance` (`doctor/machine_load.py:9`).

  Перечень теперь покрывает все восемь вызывающих модулей.
- Подмен тестами имён из списка требования 4 на базе ветки нет (проверено в круге 1, `tests/` с тех пор не менялись).
- `_durations_reader` — `acceptance.py:2855–2873`:
  - при `profile is not None` поток не запускается (:2859–2861);
  - импорт `from . import suite_durations` стоит вне `try` (:2862);
  - `Reader(...).start()` уже под `try/except Exception` (:2864–2868).

  Зовётся из `_run_full_suite_to_log` (:2892–2893), то есть только при прогоне с логом. Условие из SPEC.md:126–128 верно.
- `suite_durations` в `orchestrator/` и `scripts/` импортируется только лениво: `acceptance.py:2862` и `suite_run.py:698`.

Не подтвердилось — механизм сценария 2 (SPEC.md:133–136, :214–216). `from . import suite_durations` не обращается к `sys.modules`, если у пакета `orchestrator` уже есть атрибут `suite_durations`. Атрибут появляется при первом импорте подмодуля и остаётся после него. Пробой на Python 3.13.12 из рабочего каталога, `mock.patch.dict(sys.modules, …None)` + `from orchestrator import suite_durations`:
- модуль ещё не импортирован → `ImportError: import of orchestrator.suite_durations halted; None in sys.modules`;
- модуль уже импортирован → `import OK`.

В тесте AC-7 модуль заведомо импортирован до сценария 2 по трём причинам: базовый прогон «без сбоя» сам выполняет `acceptance.py:2862`; сценарий 1 импортирует `suite_durations` ради подмены `Reader.start`; в полном наборе его импортируют `tests/test_suite_durations.py` и `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py`. См. отклонение 1.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | публичное имя не объявлено (оставлен `_drop_layout` без `drop_layout`); появился публичный двойник `inside`/`layout_parent`/`LAYOUT_ID` |
| AC-2 | да | в `plank_layout.py` добавлен импорт `acceptance`, в том числе ленивый (ради `_own_target`/`_component_name`) |
| AC-3 | да | константа или функция в `acceptance.py` — копия, а не реэкспорт (`is` ложно); текст отказа изменён хоть на символ |
| AC-4 | да | несамодостаточная функция перенесена в `plank_layout`, в том числе с реэкспортом: `__module__` станет `orchestrator.plank_layout` |
| AC-5 | да | публичное имя не объявлено или указывает на обёртку; закрытое удалено; объявлено `last_full_suite_metrics` |
| AC-6 | да | любой из восьми вызывающих модулей оставлен на закрытом имени: формы теперь покрывают `from .. import acceptance` в `advance_gates/` и `doctor/`. Не ловит переход на `from .acceptance import _x` или `from orchestrator.acceptance import _x` в модуле верхнего пакета (см. «Пути обхода», п.1) |
| AC-7, сценарий 1 | да | убран `except` вокруг `Reader(...).start()` (`acceptance.py:2864–2868`); есть защита от холостого прогона (файл времени без сбоя появляется) |
| AC-7, сценарий 2 | по букве нет | мутацию «импорт снова вне `try`» тест по рецепту SPEC не проверяет: импорт не сбоит (раздел «Факты»), поток стартует, файл времени появляется, и тест красный уже на правильном коде. Если атрибут пакета подменить на `None`, а не удалить, сбой будет `AttributeError` на `suite_durations.Reader` внутри `try`, и мутация снова не ловится. Отклонение 1 |
| AC-8 | да, ревью | PLAN без результата поиска или без списка файлов — ревью PLAN |

## Зоны
- Зоны SPEC совпадают с ТЗ и покрывают всё, что требует правки: новый модуль, `acceptance.py`, восемь вызывающих модулей, карту, `tests/` (только новые файлы).
- `scripts/` правки не нужны: закрытых имён `acceptance` там нет.
- Защищённые пути внутри `tests/` — `tests/test_invariants.py` и `**/conftest.py`. SPEC исключает их правилом «только новые файлы» и разделом «Не входит».
- `orchestrator/suite_durations.py` — только чтение. Сценарий 2 его правки не требует.
- Песочница ролей не расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| перенос `_exclude_layout`/`_exclude_pattern` в `plank_layout` | шаблон в `info/exclude` под `flock`, без дублей — `tests/test_acceptance_plank_exclude_lock.py:36–76` | да (реэкспорт тем же объектом) | тот же тест без правки + AC-3 | остаётся |
| перенос `_plank_layout`, `_drop_layout`, констант отказа | отказ выкладки при сбое записи exclude — `tests/test_acceptance_plank_layout_refusal.py:48, 131` | да: `acceptance.fcntl` — тот же модуль, `acceptance.py:510` его использует | тот же тест + AC-3 | остаётся |
| перенос `_uses_plank_layout`, `_layout_parent`, `_drop_component_layout`, `LAYOUT_*` | `LAYOUT_OUTSIDE_NOTE` — `tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py:1239` | да | тот же тест + AC-3 | остаётся |
| публичные имена в `two_sided.py`, `outcome_integrity.py`, `tests_writing.py` (гейты) | двусторонний прогон, перепрогон красных, ключ итога — существующие тесты гейтов; файловый уровень по стеку — `tests/test_01m5edw6kd1escevrsv2wpnxap_file_level.py:410–417` | да (тот же объект) | существующие тесты + AC-5 + AC-6 | остаётся |
| импорт `suite_durations` внутрь `try` | «сбой потока прогон не меняет» — теста нет (ТЗ «Факты») | да, усиливается | AC-7, сценарий 1; сценарий 2 по рецепту SPEC — не покрыто | отклонение 1 |

Существующие тесты, гейты и лимиты не ослабляются. Раздела «Меняемое поведение» нет, и он не нужен: ожидания существующих методов не меняются.

## Пути обхода гейтов
1. Разработчик может формально выполнить AC-6, переписав вызов на `from .acceptance import _reported` или `from orchestrator.acceptance import _reported` в модуле верхнего пакета. Это прямой импорт имени, и формы SPEC.md:113–121 его не распознают. В `two_sided`/`outcome_integrity`/`tests_writing` такая же форма `from .acceptance import …` относится к `advance_gates.acceptance` и законно пропускается. Сегодня в коде есть только `from .acceptance import is_pytest_command` (публичное имя, `project_profile.py:461`, :651), и ограничение зон SPEC 11 («только замена на публичное») такую перепись запрещает. Замечание, не отклонение: закрыть его можно, разрешая `from <…> import <имя>` по тому же правилу пути файла.
2. Константа исключений AC-6 расширяется «по требованию 5» без автоматической проверки, что подмена существует; держит только ревью PLAN (замечание круга 1, без изменений). Подмен на базе нет.
3. `getattr(acceptance, "_reported")` разбор по атрибутам не видит. В коде такой формы нет; замечание.
4. Сценарий 2 AC-7: если исполнитель напишет его по букве, тест окажется красным на правильном коде. Если «починит» подменой атрибута на `None`, тест позеленеет, но заявленную мутацию ловить не будет. Это отклонение 1.

## Вердикт
**concerns.** Все пять решений Оператора круга 1 в SPEC перенесены, факты о коде подтверждены. Осталось одно отклонение, Оператор может снять его уточнением на гейте:

1. **Рецепт сценария 2 AC-7 не вызывает сбоя импорта** — SPEC.md:133–136, :214–216 против `orchestrator/acceptance.py:2862`. `sys.modules["orchestrator.suite_durations"] = None` ломает `from . import suite_durations` только тогда, когда у пакета `orchestrator` нет атрибута `suite_durations`. В тесте AC-7 атрибут к сценарию 2 уже есть: его оставляют базовый прогон (SPEC.md:128–129) и импорт ради подмены `Reader.start` в сценарии 1. Проверено пробой: «warm → import OK», «cold → ImportError». Поэтому по букве поток стартует, файл времени появляется, и утверждение «файла времени нет» красное на правильном коде.

   Предложение: на время прогона одновременно `sys.modules["orchestrator.suite_durations"] = None` и **удалить** атрибут `suite_durations` у пакета `orchestrator` (`monkeypatch.delattr(orchestrator, "suite_durations", raising=False)` или `mock.patch.dict(orchestrator.__dict__)` с удалением ключа), с восстановлением после. Подмена атрибута значением `None` не годится: сбой уйдёт в `AttributeError` внутри `try`, и мутация «импорт снова вне try» ловиться не будет. В качестве защиты от холостого сценария тест может сначала убедиться, что `from orchestrator import suite_durations` в этих условиях бросает `ImportError`.

Замечания без отклонения — «Пути обхода», п.1–3.

Эскалация не нужна: отклонение снимается уточнением формулировки и не требует выбора между существенно разными реализациями.

## Предложения системе
- `skills/spec-audit.md`: подмену `sys.modules[...] = None` в рецептах тестов стоит сверять пробой. Для подмодуля, уже импортированного в процесс, она не действует на `from <пакет> import <подмодуль>`, пока атрибут пакета на месте.
