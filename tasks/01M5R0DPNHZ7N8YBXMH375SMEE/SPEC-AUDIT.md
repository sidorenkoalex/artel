---
task: 01M5R0DPNHZ7N8YBXMH375SMEE
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/fixtures.py, tests/merge_outcome_sandbox.py, tests/outcome_gate_sandbox.py, tests/sandbox.py, tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py, tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py, tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py, tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py, tests/test_invariants.py, tests/test_merge_outcome_module.py, tests/test_outcome_gate_module.py, tests/test_outcome_integrity_added_lines.py; в) защищённые пути: tests/test_invariants.py; г) budget_usd 60 ≥ 45; д) ТЗ ссылается на ADR: ADR-0020, ADR-0027
spec_sha: b44f219700a65f48b48c20e80527a60c951eff65
schema_version: 5
---

# SPEC-AUDIT: Сведение тестов, волна 2а-2а — песочница мержа в `tests/merge_outcome_sandbox.py`, тесты `merge_outcome_gate` в `tests/test_merge_outcome_module.py`, тесты `added_lines` в `tests/test_outcome_gate_module.py`

Проверено на рабочем каталоге `dad6165f` (`git hash-object SPEC.md` =
`b44f2197…` — совпадает с миссией). ANSWER-n нет, раздела «Решения
Оператора на гейте SPEC» в брифе нет.

## ТЗ и SPEC

Сверка в обе стороны — по требованиям ТЗ 1–9, ограничению зон, «Только
чтение», «Не входит» и 11 уточнениям 25.10.

- ТЗ 1 → SPEC 1–8: нумерация и группы М/Д, части ≤ 15 без смешения групп,
  `--wait 5` до итоговой строки, строка падения, перечень не-доказательств
  (включая предусловия :715, :718, :749, :786, :801 и уточнение 8 — их строки
  в старом и новом файле), детерминированность, исходы «итог неизвестен» и
  прочие, красный контроль, ожидание только `--wait-lock`. Уточнение 9
  (группа Д: `--workers 4` — ≤ 5, `-n auto` — ≤ 15) учтено в SPEC 7.
- ТЗ 2 → SPEC 9 дословно. ТЗ 3 + уточнение 4 → SPEC 10. ТЗ 4 → SPEC 11.
- ТЗ 5 + уточнения 1–3, 5 → SPEC 12–16, 19, 21. Расхождение ТЗ про
  `js_source` снято уточнением 2, SPEC это называет («Материалы»).
- ТЗ 6 + уточнения 6, 7, 10 → SPEC 17–18.
- ТЗ 7 + уточнение 1 → SPEC 20–22. Фраза ТЗ ««до» той же разбивкой» (при
  `--workers 4` группы Д) передана формой SPEC 20 «теми же диапазонами
  `--patches` и тем же `--workers`, что «до»» — по смыслу то же.
- ТЗ 8 → SPEC 23, ТЗ 9 → SPEC 25, ограничение зон → SPEC 24 и `zones`.
- Потеря при переносе уточнения 1: ТЗ (уточнение 1) задаёт общее правило
  «`assertX(a, b)` ↔ `assert a <op> b`» и даёт три примера в скобках; SPEC
  21 (SPEC.md, требование 21) оставил только три пары `assertEqual`/
  `assertIn`/`assertTrue` без общего правила. В старом файле есть и другие
  виды: `assertFalse` (3), `assertIsNone` (2, например
  `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:1121`),
  `assertIsNotNone` (4), `assertNotEqual` (4), `assertNotIn` (2). Для них
  соответствие задано только косвенно, через AC-12 «ни одно сравнение не
  ослаблено». Отклонение 3.
- Требований SPEC сверх ТЗ нет. Раздел «Оценка объёма и деление» — материал
  для Оператора, не требование.

## Факты против кода

Подтверждено (HEAD `dad6165f`; `git diff 78a3013b dad6165f -- orchestrator/
<файлы волны> tests/outcome_gate_sandbox.py` пуст):
- `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`: 1144
  строки, 72 824 байта; 19 тестов, 19 строк «Ловит мутацию». Операторы
  верхнего уровня: докстринг 1–41, импорты 42–62, константы 64–98,
  `MergeOutcomeSandbox` 101–365, `TwoSidedSandbox` 955–980, `__main__`
  1143–1144. Байты песочницы (42–99, 101–365, 955–980) — 17 308, тестовых
  классов — 50 835 (с оценкой ТЗ сходится).
- Утверждения подготовки: `direct_task` :220, `verifying_task` :243/:245,
  `rewrite_passed` :317/:320; других методов с утверждениями у песочниц
  этого файла нет (28 методов `MergeOutcomeSandbox`, 2 — `TwoSidedSandbox`).
  `self.no_gate_refusal` зовётся один раз — :1078 (метод
  `OutcomeGateSandbox`, `tests/outcome_gate_sandbox.py:835`).
- `subTest` — 18 мест: 392, 470, 538, 587, 630, 772, 790, 823, 830, 912,
  918, 943, 1002, 1042, 1109, 1116, 1123, 1131. Вложенные `checkout_head`
  :526, `full` :532, `edit` :637. Строки уточнения 5 ТЗ (:527, :643, :645)
  — тело функции, а не `def`; SPEC 16 называет функции по имени, это
  расхождение снято.
- Случайная сторона: `self.rng.choice` — :1005 (`Ac11`), :1126 (`Ac14`).
- Именам из импортов тесты пользуются только такими: `py_source`,
  `acceptance`, `checkpoint`, `config`, `contextlib`, `hashlib`, `io`,
  `refusal_classes`, `store`, `two_sided`. Константам — только таким:
  `APPROVE_HINT`, `COUNTS_MARK`, `COVERED_BY`, `FLAKY_ON_BASE`,
  `FRESHNESS_DOCS`, `MANDATE_NONE`, `MERGE_OUTCOME_ACTION`, `NOT_RUN`,
  `OPERATOR_FIXES`, `PASSED_ACTION`, `PREPARE_ACTION`, `PROOF_LINE`,
  `PROVEN`, `PULLED`. `js_source` нужен только песочнице, что согласуется с
  SPEC 12. `GATE_ACTIONS` нужен телу `no_gate_refusal`
  (`tests/test_outcome_gate_module.py:827`) и есть только в
  `tests/outcome_gate_sandbox.py:36`. `unittest` не используется нигде,
  `hashlib` и `refusal_classes` — только тестами, не песочницей: в SPEC 10
  они названы «неиспользуемыми в нём» (в новом модуле песочницы), и это
  верно.
- `tests/test_outcome_integrity_added_lines.py`: 156 строк, 9 186 байт, 6
  тестов. Методы: `git` :21, `setUp` :28, `commit` :38, статический `files`
  :117. `subTest` :82 и :134, `assertRaises(outcome_integrity._Prepare)`
  :99, локальная `files` :151.
- `tests/test_outcome_gate_module.py`: 2412 строк, 135 395 байт, 53 теста;
  `outcome_integrity as gate` :63; `no_gate_refusal(box, rows: list, output:
  str, case: str = "") -> None` :826. Имён верхнего уровня `git`, `commit`,
  `files`, `added_repo`, `outcome_integrity` и шести имён тестов
  `added_lines` в модуле нет. Локальные `files` — только в методах
  `IdOutcomeGateSandbox` (:297–446).
- Фикстура `tmp_dir` (`tests/fixtures.py:57`) отдаёт `TmpDirTest` с `tdir`
  (`tests/sandbox.py:690–693`), то есть тело `setUp` с `box.tdir` работает.
  Фикстуры подключены плагином (`conftest.py:43`), импорт `tmp_dir` в
  модуль не нужен. `_sandbox(cls)` — `tests/fixtures.py:42`.
- Импортёры: `outcome_prior:59` и `outcome_components:44` импортируют только
  `MergeOutcomeSandbox`, докстринги :7. `pytest --collect-only` двух
  импортёров и модуля исходов собирает 114 тестов (61 + 53). Других
  ссылок на оба удаляемых пути (`git grep`) нет, кроме
  `docs/codebase-map.md`.
- guard: `_HelperScope.function` — `scripts/guard.py:1902–1923`,
  `_helper_calls` — :1926–1948, отбрасывание `msg` — :1628–1640.
  Сравнение утверждений идёт парой (ключ, текст) без происхождения
  (:2301), поэтому смена модуля песочницы у импортёров находки по
  происхождению не даёт.
- `targets.yaml:53` — `full_suite_timeout_sec: 1500`;
  `orchestrator/config.py:132` — `AGENT_TIMEOUT_SEC = 2700`;
  `REVIEW_SNAPSHOT_DIFF_MAX_BYTES = 262_144` (`config.py:578`). У
  `mutation-run` есть `--copy-table` (`mutation-run-<n>.tsv`,
  `orchestrator/mutation_run.py:142`), `--wait-lock`, `--workers`; исходы
  `orchestrator/mutation_run.py:72–76`.
- Неточность факта (отклонение 4): SPEC 12 требует перенести в докстринг
  нового модуля «описание стенда из прежнего докстринга». Прежний докстринг
  называет стенд
  `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`
  (`tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:7`). Этот
  файл удалён волной 2а-1б (`tests/test_outcome_gate_module.py:31–37`),
  стенд живёт в `tests/outcome_gate_sandbox.py`. SPEC не оговаривает, что
  адрес надо исправить, и при дословном переносе в новый модуль попадёт
  мёртвая ссылка.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | пропущенный номер патча; патч группы Д раньше М; патч, трогающий `tests/`; заявка без мутации в PLAN |
| AC-2 | да | часть > 15 (> 7 / > 5 при `--workers 4`) или смешение групп; вывод таблицы пересказан, а не перенесён дословно; мутация, которой нет в таблице |
| AC-3 | да | у мутации нет строки падения «до» или «после» |
| AC-4 | да | мутация засчитана убитой по ошибке сбора, по `Timeout` или только по `direct_task`/предусловию :715… |
| AC-5 | частично | расхождение исхода, видимое в таблицах, ловит. Убийство, зависящее от случайной стороны `Ac11`/`Ac14` или от чисел `Ac8`, при совпавших жребиях в двух прогонах не ловит (отклонение 2) |
| AC-6 | да | в диффе ветки лишний файл; подкаталог или `test_*`/`mutation-*` в каталоге документов |
| AC-7 | да | изменённый оператор песочницы (`ast.dump` ≠), «почищенный» `import unittest`, правка `tests/outcome_gate_sandbox.py` |
| AC-8 | да | правка докстринга или разбивки импорта у импортёра; сбор ≠ 61 |
| AC-9 | да | `js_source` или `FLAKY_ON_BASE` из `tests.outcome_gate_sandbox`; остался класс или `subTest` |
| AC-10 | да | фикстура зовёт `direct_task`; имя фикстуры `tmp_dir`/`real_git` |
| AC-11 | да | `no_gate_refusal` без `case` или с иным телом (`ast.dump` ≠) |
| AC-12 | частично | заменённая литералом константа и сообщение не вторым операндом — ловит. Для видов вне трёх пар SPEC 21 (`assertIsNone(x)` → `assert not x`) опирается только на общее «не ослаблено» (отклонение 3) |
| AC-13 | да | цикл `subTest`, распиленный на несколько функций; утверждение подслучая без ярлыка и зерна; невынесенная локальная `files` |
| AC-14 | да | `outcome_integrity` заменён на `gate`; повторный `import os`; `super().setUp()` в фикстуре; изменённый тест волны 2а-1а |
| AC-15 | да | функция без «Ловит мутацию»; удалённый тест без записи о дубле |
| AC-16 | да | иной `--patches`/`--workers` «после»; нет пустого `git status -- orchestrator/`; sha патча ≠ |
| AC-17 | да | мутацию «после» убил другой тест или утверждение; нет соответствия строк |
| AC-18 | да | нет чисел или времени |
| AC-19 | да | старый файл остался; `skip`/`xfail`; правка `tests/sandbox.py`; ручная правка карты |

## Зоны

- `zones: tests/, docs/codebase-map.md` покрывают всё, что требования
  заставляют менять: два новых модуля, дописку в модуль исходов, два
  импортёра, удаление двух файлов и карту.
- Патчи мутаций и таблицы пишутся в каталог документов задачи, а не в
  кодовые зоны. Это задано SPEC 9 и AC-6.
- Из `config.PROTECTED_PATHS` под зону попадает `tests/test_invariants.py`,
  но SPEC 24 и AC-19 запрещают его менять. Остальные защищённые пути
  (`conftest.py`, `pyproject.toml`, `targets.yaml`, `docs/adr/`, `skills/`)
  в задаче только читаются. Приложения PLAN не нужны.
- Инварианты дерева `tests/` на новый модуль не реагируют. Сканы
  `tests/test_invariants.py:1947` (сетевые адреса) и :2225 (часы и живые
  файлы — в файлах волны нет `time.`, `sleep`, `__file__`) не дают находок,
  :2818 (`PATCHED_ATTRS`) — тоже: в файлах волны этого атрибута нет.
  Расширения песочницы ролей нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| Удаление `merge_outcome_gate` (19 тестов, AC-1..AC-14 SPEC 01M5DDTVZEA40ZB9BHEH4YDEE7) | Утверждения тестовых классов `…merge_outcome_gate.py:370–1140` | остаётся | Функции `tests/test_merge_outcome_module.py`; доказательство — таблицы «до/после» и соответствие строк (SPEC 2, 20, 21; AC-2, AC-16, AC-17) | ок при мандате по пути (SPEC 23) |
| Удаление `added_lines` (6 тестов) | Разбор `_added_lines` и `_code_exception_findings` (`…added_lines.py:43–156`) | остаётся | Раздел `added_lines` в `tests/test_outcome_gate_module.py` (SPEC 17–18; AC-14, AC-17) | ок при мандате по пути |
| Утверждения подготовки `direct_task`/`verifying_task`/`rewrite_passed` под прослеживанием гейта неослабления | Сейчас guard видит их у каждого теста через `self.<метод>` по цепочке класса (`scripts/guard.py:1939–1942`), поэтому ослабление метода в песочнице даёт находку по вызывающим (`orchestrator/advance_gates/test_integrity.py:953–983`) | остаётся, не покрыто гейтом | Вызов `box.direct_task(…)` guard не прослеживает (:1943–1944 — только голое имя или функция `tests/sandbox.py`), а `tests/merge_outcome_sandbox.py` — не `test_*`. Ослабление этих утверждений в будущей задаче гейт не увидит. Требования-замены в SPEC нет | ок при условии — вопрос Оператору (отклонение 1) |
| Утверждающий исход `no_gate_refusal` | Метод `OutcomeGateSandbox` (`tests/outcome_gate_sandbox.py:835`), прослеживается через `self.` | остаётся | Функция модуля, зовётся голым именем, guard прослеживает (:1907–1912); AC-11 | ок |
| `subTest` → цикл/прямой код | Каждый подслучай отчитывается отдельно, зерно в `subTest` | остаётся (данные цикла гейту не видны — как и до) | AC-13: ярлык и зерно в сообщении | ок |
| Источник импорта у `outcome_prior`/`outcome_components` | Цепочка `PriorSandbox`/`ComponentsOutcomeSandbox` → `MergeOutcomeSandbox` | остаётся | `ast.dump` песочницы (AC-7), сбор 61 (AC-8), CI ветки | ок |
| Детерминированность доказательства | — (новое требование волны) | остаётся | SPEC 5. Проверяется только совпадением наблюдённых исходов (AC-5) | ок при условии (отклонение 2) |

## Пути обхода гейтов

1. **Слепое пятно на утверждениях подготовки** (матрица, строка 3). SPEC 14
   прямо велит звать методы подготовки с утверждениями через стенд. Буквально
   исполненный SPEC переводит утверждения `direct_task`, `verifying_task`,
   `rewrite_passed` из прослеживаемых guard в непрослеживаемые. Следующая
   задача может ослабить их в `tests/merge_outcome_sandbox.py` без
   находки гейта неослабления: правка нетестового модуля, вызывающие
   `box.<метод>` не прослеживаются (`scripts/guard.py:1939–1944`;
   `orchestrator/advance_gates/test_integrity.py:955–983`). Решение взято из
   ТЗ (п. 5) и прецедента 2а-1б. Но правило 3 матрицы
   (`docs/operator-gates.md:71–74`) требует перечня замен, а SPEC его не
   даёт.
2. **Убийство по жребию.** У мутации, которую убивает только `Ac11`
   (`…merge_outcome_gate.py:1005`) или подслучай (в) `Ac14` (:1126) при
   одной стороне, исходы «до» и «после» совпадут с вероятностью ½: она будет
   засчитана убитой (или неубитой) без нарушения AC-5. SPEC 5 запрещает
   такое на словах, но ни один AC не требует обоснования в PLAN, почему
   убийство не зависит от `self.rng`.
3. **Ослабление вида утверждения вне трёх пар SPEC 21.** Пример:
   `assertIsNone(box.section(text))` (:1121) переписан в `assert not
   box.section(text)`. Пустая строка тогда пройдёт. Требование «тем же
   утверждением» формально соблюдено по соответствию строк, а запрет держит
   только общая формулировка AC-12.

## Вердикт

`concerns`: SPEC верно отражает ТЗ и уточнения 25.10, факты о коде
подтверждены, зоны достаточны. Найдены отклонения, решить которые может
Оператор на гейте:

1. Утверждения подготовки `direct_task`/`verifying_task`/`rewrite_passed`
   (`tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:220`,
   :243, :245, :317, :320) выпадают из прослеживания гейта неослабления.
   Причина: вызов через стенд (SPEC.md, требование 14) не прослеживается
   (`scripts/guard.py:1939–1944`), а песочница переезжает в нетестовый
   модуль. Строка матрицы — «остаётся, не покрыто», и требования-замены нет
   (`docs/operator-gates.md:71–74`). Варианты: принять осознанно, как в
   2а-1б, с записью в матрицу ANSWER; либо потребовать замену — например,
   функцию модуля с утверждениями подготовки, которую тесты зовут голым
   именем.
2. Детерминированность убийства (SPEC.md, требование 5) не проверяема
   AC-5 для мутаций, которые убивают только `Ac11`/`Ac14` со случайной
   стороной (:1005, :1126) или `Ac8` со случайными числами (:860–862).
   Можно дописать в AC-5 обязательное обоснование в PLAN независимости
   убийства от стороны и чисел (например, мутация ломает обе стороны
   симметрично).
3. SPEC 21 потерял общее правило уточнения 1 ТЗ «`assertX(a, b)` ↔ `assert
   a <op> b`»: перечислены только `assertEqual`/`assertIn`/`assertTrue`, а в
   файле есть `assertFalse`, `assertIsNone` (:1121), `assertIsNotNone`,
   `assertNotEqual`, `assertNotIn`. Неослабление их перевода держит только
   общая формулировка AC-12.
4. SPEC 12 (докстринг: «описание стенда из прежнего докстринга») не
   оговаривает исправление устаревшего адреса стенда
   `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`
   (`…merge_outcome_gate.py:7`; файл удалён волной 2а-1б, стенд — в
   `tests/outcome_gate_sandbox.py`). Это мелочь документации.

Без ответа Оператора вердикт вынести можно: эскалации нет.
