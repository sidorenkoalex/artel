---
task: 01M5RHGRH3YJV8VBFH3QCHD8X0
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py

Основание: мандат Оператора 23.10.2026 (дословно: «Волна сведения тестов по note; после бери все остальные модули в работу - даю мандат»); решение Оператора 24.10.2026 (дословно: «Бери») — до трёх волн одновременно, модуль merge; ADR-0027 п. 8; ADR-0020 п. 8, ветвь «удаление без замены долгоживущим тестом — решением Оператора» для шести долгоживущих файлов задач 01M44EP0D47F498TEE08MNGBYT и 01M45D29BQJE8FJYJA4JQWSYFZ (свойства переносятся в `tests/test_merge_after_module.py`); объём — требования ТЗ: перенос 33 тестов с дословными ожиданиями дописыванием в модуль, удаление шести файлов, удаление дублей только внутри того же прежнего файла; удаление утверждения без переноса, ослабление сравнения, `skip`/`xfail`, подъём пределов не разрешены. Мандат снимает находки обоих гейтов по этим шести путям. `tests/test_merge_after_module.py` мандатом не покрыт; находка по его 20 существующим тестам — `escalate`.

Независимая проверка: повтор `mutation-run` сессией при Операторе на зафиксированном наборе патчей и сверка утверждений и тел по синтаксическому дереву до approve на merge_gate — обязательны.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py | merge_after в ответе Оператора | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py | проверка guard поля merge_after | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py | merge_after в PLAN и отказ при подмене значения | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py | merge_after на гейте SPEC | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py | добавка зависимостей в status/show | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |
| tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py | объявление merge_after в new по «Порядок:» | остаётся | `tests/test_merge_after_module.py`; таблица мутаций «после» | перенос (ADR-0020 п. 8, решение Оператора) |

## Решения гейта SPEC (аудит concerns, без возврата аналитику)

1. Импорты `github_adapter`, `workspace` — отдельной новой строкой импорта в блоке импортов модуля; существующие строки :46–47 не меняются, дифф модуля — только добавления (докстринг и место вставки — как в 3м-2).
2. Мандат и матрица — этим ответом.
3. AC-2: у каждого патча в PLAN — отметка «может зациклить общий узел: да / нет» с одной фразой; по ней проверяется правило «по одному в части».
4. AC-5: от зерна зависит только вариант «включение завершённых», сохраняющий условие пустоты; снятие фильтра `s != "done"` (`orchestrator/merge_after.py:449`) убивается `status_show` :177 при любом зерне — эта мутация допустима.
5. «То же утверждение» — соответствие «до → после» (`assertX` ↔ `assert` с тем же смыслом, `self` ↔ имя фикстуры, литералы дословно), не нормальная форма guard.
