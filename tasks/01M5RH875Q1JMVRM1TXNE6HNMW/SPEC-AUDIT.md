---
task: 01M5RH875Q1JMVRM1TXNE6HNMW
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/components_outcome_sandbox.py, tests/fixtures.py, tests/merge_outcome_sandbox.py, tests/outcome_gate_sandbox.py, tests/sandbox.py, tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py, tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py, tests/test_invariants.py, tests/test_merge_outcome_module.py, tests/test_outcome_components_module.py, tests/test_outcome_gate_module.py; в) защищённые пути: tests/test_invariants.py; д) ТЗ ссылается на ADR: ADR-0020, ADR-0027."
spec_sha: 16260b89ede034a749ebf9a9a5de01d2c9e45a14
schema_version: 5
---

# SPEC-AUDIT: Сведение тестов, волна 2а-2б — песочницы гейта исходов по компонентам в `tests/components_outcome_sandbox.py`, тесты в `tests/test_outcome_components_module.py`, пути стенда в докстринге `outcome_prior`

Проверено на рабочем каталоге ad3608c6 (HEAD ветки задачи = origin/main из ТЗ);
sha SPEC.md каталога документов (`git hash-object`) = 16260b89…, совпадает с
миссией. ANSWER-n.md нет; раздела «Решения Оператора на гейте SPEC» в брифе нет.

## ТЗ и SPEC
ТЗ → SPEC (с учётом раздела ТЗ «Уточнения по независимой проверке 25.10»):
- ТЗ треб. 1 → SPEC 1–8: патчи, таблица «до», строка падения, перечень
  не-доказательств (включая уточнение 1 — `RealGitSandbox.git`), детерминизм
  (с уточнением 4 — SPEC 5), «итог неизвестен…», красный контроль (с
  уточнением 8: части при `--workers 4` до 15 патчей — SPEC 7), ожидание
  замка (с уточнением 7 — SPEC 8). Потерь нет.
- ТЗ треб. 2 → SPEC 9; треб. 3 → SPEC 10; треб. 4 → SPEC 11; треб. 5 → SPEC
  12–19 (сигнатуры и фикстуры дословно по уточнению 3, присваивания стенду по
  уточнению 5, докстринг по уточнению 9, ссылка заявки ac19 по уточнению 2);
  треб. 6 → SPEC 20–22; треб. 7 → SPEC 23 (с уточнением 6 о храповике); треб.
  8 → SPEC 25; «Ограничение зон по смыслу» → SPEC 24; «Не входит» и «Только
  чтение» → раздел SPEC «Не входит». Потерь нет.
- Расхождение основного текста ТЗ и уточнения (части по 5 / по 15 патчей;
  stdlib «тем же способом» / только `contextlib`, `io`) SPEC разрешил в
  пользу уточнений, как велит ТЗ, и назвал это в «Материалах». Верно.

SPEC → ТЗ: требований сверх ТЗ нет. Производные уточнения — SPEC 12 «без
тестовых классов, `unittest` и `subTest`» (следует из «стиль pytest» и факта
«`subTest` нет»), AC-6 «нет подкаталогов, кроме `acceptance_tests/`»
(следует из «файл первого уровня» треб. 2 ТЗ) — не новые требования.

## Факты против кода
Подтвердилось:
- Файл волны: 650 строк, 40 767 байт; 17 тестов (3+3+2+3+2+2+1+1), 17 заявок;
  константы `PASSED_ACTION`…`COUNTS` — `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:47–56`,
  `ContextRunnerProc` — :59, `ComponentsOutcomeSandbox` — :71,
  `FAIL_TO_PASS_ACTION`/`FOREIGN` — :554–555, `ForeignPlankSandbox` — :558,
  `Ac19ForeignPlankTest` — :579; `unittest`, `subTest`, «Предусловие» нет.
  Неточность без последствий: «тестовые классы … — :240–553» — последний
  тестовый класс кончается на :549, :552–553 — разделитель-комментарий.
- Утверждения подготовки: `writing_task` — `assertIsNone` :168,
  `component_task` — `assertEqual` :202; `mandate_answer` — `assertIn(exc.code, (None, 0), …)` :505;
  `review_section` (:390, локальный импорт :393) и `broken_consumer` (:508) — без утверждений.
- Перечень методов подготовки предков с утверждениями полон (сверено обходом
  AST): `OutcomeGateSandbox.in_dev_task`/`artel_in_dev_task`/`operator_mandate`
  (`tests/outcome_gate_sandbox.py:649,671,684,711,784`),
  `MergeOutcomeSandbox.direct_task`/`verifying_task`/`rewrite_passed`
  (`tests/merge_outcome_sandbox.py:180,203,205,277,280`), `RealGitSandbox.git`
  (`tests/sandbox.py:1959`). Ещё `refusal`/`no_gate_refusal`
  (`tests/outcome_gate_sandbox.py:824–837`) файл волны не зовёт.
- Зерно — `tests/outcome_gate_sandbox.py:258`. Предел — `targets.yaml:53`
  (`full_suite_timeout_sec: 1500`, `mutation_run.py:564` берёт
  `full_suite_limit`). `AGENT_TIMEOUT_SEC = 2700` — `orchestrator/config.py:132`.
  `--wait-lock` + `--wait` ≤ 9 — `orchestrator/mutation_run.py:752`;
  `--copy-table` пишет `mutation-run-<n>.tsv` в каталог документов —
  `orchestrator/mutation_run.py:142`, логи прогона — в каталоге логов пульта
  (:136), не в каталоге документов (AC-6 исполним).
- guard: `_HelperScope.function` — `scripts/guard.py:1902–1924`,
  `_helper_calls` — :1926–1948, сброс `msg` — :1628–1634; `_is_assertion`
  (:1565–1574) признаёт любой `<obj>.assert*`, поэтому `box.assertIn` в
  `mandate_answer`, вызванной голым именем, guard проследит. Правило стиля
  pytest (`scripts/guard.py:4594–4739`) вызов `box.assertIn` в помощнике не
  запрещает.
- `fsm_advance.py`: заявка ac19 ссылается на :609–613 (`tests/…_outcome_components.py:600`);
  `in_outcome_bounds(profile)` — `orchestrator/fsm_advance.py:617` внутри
  `tests_writing` (:510); граница чужого компонента —
  `orchestrator/advance_gates/tests_writing.py:1090`. Подтверждено (о смысле
  заявки — отклонение 3 ниже).
- `outcome_prior`: абзац «Стенд — …» — `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:6–8`,
  оба удалённых пути — там; 44 теста. Импортёров файла волны и упоминаний
  `ComponentsOutcomeSandbox`/`ForeignPlankSandbox`/`ContextRunnerProc` вне файла
  нет (`tests/`, `scripts/`, `orchestrator/`, `conftest.py`, `pyproject.toml`, `targets.yaml`).
- `_sandbox(cls)` — `tests/fixtures.py:42–54` (setUp + уборка `_cleanups`,
  без `tearDown`; у песочниц цепочки `tearDown` нет — перенос в фикстуру
  поведения уборки не меняет). Имена фикстур `tests/fixtures.py`: `tmp_dir`,
  `tmp_root`, `initialized_tmp_root`, `real_git`, `origin_real_git`,
  `light_transition` — с `box`/`foreign_box` не совпадают.
- Имена, нужные тестам: обход AST тел тестовых классов даёт ровно
  `PASSED_ACTION`, `OUTCOME_ACTION`, `BROKEN_ACTION`, `PREPARE_ACTION`,
  `SKIP_RECORD`, `OUT_OF_BOUNDS`, `NOT_RUN`, `COUNTS`, `FOREIGN`,
  `MATRIX_HEADERS`, `answer`, `mandate`, `outcome_integrity`,
  `project_profile`, `contextlib`, `io` — совпадает с перечнем SPEC 12 / AC-9.
  Локальных переменных, совпадающих с `box`, `foreign_box`, `mandate_answer`,
  `review_section`, `broken_consumer`, нет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | пропуск номера патча; патч, трогающий `tests/`; заявка без мутации/без фразы о случайности |
| AC-2 | да | часть > 15 патчей; вывод части пересказан, а не перенесён; мутация вне таблиц |
| AC-3 | да | мутация без строки «файл:строка» падения |
| AC-4 | да | засчитано убийство setup-ошибкой, `Timeout` или утверждением `writing_task`/`component_task`/`RealGitSandbox.git` |
| AC-5 | да | мутация «не убита» в одной таблице и «убита» в другой/повторе |
| AC-6 | да | посторонний файл в diff ветки; `test_*`/`mutation-*` или подкаталог в каталоге документов |
| AC-7 | да | правка метода песочницы при переносе; «чистка» неиспользуемого импорта; изменение `tests/merge_outcome_sandbox.py` |
| AC-8 | да | правка кода/текста `outcome_prior` сверх двух путей; иная разбивка строк |
| AC-9 | да | `PREPARE_ACTION` из `tests.merge_outcome_sandbox`; лишний импорт (`json`, `random`) |
| AC-10 | да | строка «Группа: долгоживущий» осталась; старый путь стенда |
| AC-11 | частично | утверждение в фикстуре — да; но буквально «не зовут методов с утверждениями» невыполнимо (отклонение 1) |
| AC-12 | да | тело помощника изменено; `box.assertIn` заменён на `assert`; `no_marker` присвоен не тем порядком |
| AC-13 | да | `assertEqual` → `assert a in b`; константа заменена литералом; сообщение потеряно |
| AC-14 | да | функция без «Ловит мутацию:»; удалён тест без условий (а)/(б) |
| AC-15 | да | иные диапазоны/`--workers`; изменённое дерево `orchestrator/`; другой sha патча |
| AC-16 | да | мутация «после» убита другим утверждением/другой функцией |
| AC-17 | да | нет числа тестов/строк/времени |
| AC-18 | да | `skip`/`xfail`; изменён `tests/fixtures.py` или `orchestrator/`; карта не по генератору |

Пробел: ни один AC не проверяет неассертивную часть тел перенесённых тестов
и запрет фиксировать зерно (SPEC 5, 17) — отклонение 2.

## Зоны
Зоны `tests/, docs/codebase-map.md` покрывают всё: два новых модуля, правку
докстринга `outcome_prior`, удаление файла волны, карту. Патчи и таблицы —
в каталоге документов задачи, не в зонах кода. Код `orchestrator/` не
меняется (мутации — во временной копии `mutation-run`). Защищённые пути
(`orchestrator/config.py:769–775`): `tests/test_invariants.py`,
`**/conftest.py`, `pyproject.toml`, `targets.yaml` требованиями не
затрагиваются, SPEC 24 и AC-18 явно их исключают; приложения PLAN не нужны.
Песочница ролей не расширяется: мандат только на удаление одного пути
(SPEC 23).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| удаление `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py` (класс `Ac16DiffComponentsTest`, :240–312) | гейт исходов берёт компоненты по диффу с потребителями; отказ «подготовка» при сбое `diff` | остаётся | функции `test_ac23_…`, `test_ac16_…` (×2) нового модуля; доказательство — AC-15/AC-16 | ок |
| то же, `Ac17PerComponentTest` (:317–383) | префикс компонента в отказе; строка «вне границы»; запись пропуска и строки ревью при всех вне границы | остаётся | `test_ac17_…` (×3) нового модуля; AC-16 | ок |
| то же, `Ac18ReviewLinesTest` (:388–428) | `review_lines` и пакет ревьювера по записям всех компонентов | остаётся | `test_ac18_…` (×2) + `review_section`; AC-12, AC-16 | ок |
| то же, `Ac22FrontendTaskTest` (:433–479) | выход `tests_writing`, гейт `in_dev`, гейт мержа задачи на `frontend` по профилю компонента | остаётся | `test_ac22_…` (×3); AC-16 | ок |
| то же, `Ac13Ac14GateMandateTest` (:484–549) | мандат по пути и по идентификатору на компонент-потребитель принят `answer` и снимает находку; утверждение исхода `mandate_answer` :505 | остаётся | `test_ac13_…`, `test_ac14_…` + `mandate_answer(box, …)` с `box.assertIn` (AC-12); AC-16 | ок |
| то же, `Ac19`/`Ac25`/`Ac27` (:579–650) | отказ FAIL_TO_PASS по файлу планки чужого компонента в границе, текст отказа, отсутствие проверки вне границы | остаётся | `test_ac19_…` (×2), `test_ac25_…`, `test_ac27_…` на `foreign_box`; AC-16 | ок |
| прослеживание guard утверждений подготовки (`writing_task` :168, `component_task` :202) при вызове `self.` | счёт храповика `test_integrity.ratchet_finding` (`orchestrator/advance_gates/test_integrity.py:1222`) | убывает (методы зовутся через `box.`) | не покрыто прослеживанием; убыль на удаляемый путь, покрыта мандатом на него (SPEC 23, уточнение 6 ТЗ); сами утверждения в песочницах остаются (AC-7) | ок при условии мандата на один путь |
| перенос песочниц в `tests/components_outcome_sandbox.py` | поведение стенда (раннеры, учебный проект) | остаётся | `ast.dump` операторов равен (AC-7) | ок |
| докстринг `outcome_prior` :6–8 | свойств не держит | — | `ast.dump` модуля без докстринга равен (AC-8) | ок |

Раздела «Меняемое поведение» в SPEC нет — и не нужен: ожидания тестов не
меняются.

## Пути обхода гейтов
- Неассертивная часть тел тестов не сверяется ни одним AC: в функцию можно
  добавить `box.rng.seed(0)` / `box.rng = type(box.rng)(0)` (импорт `random`
  не нужен, AC-9 не сработает), сменить входной литерал (`"SEED = 7\n"`),
  аргумент `training(backend_report=False)` или добавить лишний вызов
  метода песочницы. AC-12 сверяет по AST только три помощника и порядок трёх
  присваиваний, AC-13 — только ожидания и вид утверждений. AC-16 ловит такую
  правку лишь если она снимает убийство конкретной мутации; фиксация зерна
  при этом может сделать «детерминированными» исходы, которые зависят от
  случайности, — в обход SPEC 5. См. отклонение 2.
- Мутации пишет сам исполнитель; дубли (SPEC 18) удаляются по таблице «до»
  из его же мутаций. Условие (б) (все литералы и виды утверждений удаляемого
  теста есть в сохраняемом) и независимая проверка (SPEC 25) закрывают это
  достаточно; отклонением не считаю.
- Процессные требования без AC (SPEC 8 — только `--wait-lock`, без циклов;
  SPEC 9 — `git status` к концу каждого шага; SPEC 22 — адресный прогон
  только нового модуля) проверяются журналом шагов и PLAN, не тестом. Это
  ограничение формы, не обход; на усмотрение Оператора.

## Вердикт
concerns — SPEC полно и верно переносит ТЗ с уточнениями, факты о коде
подтвердились; отклонения решаемы Оператором на гейте:

1. AC-11 (SPEC 14) буквально невыполним: «фикстуры … не зовут методов с
   утверждениями», а предписанная `yield from _sandbox(…)` через
   `tests/fixtures.py:44` (`obj.setUp()`) →
   `GitignoreCommittedRealGitSandbox.setUp` (`tests/sandbox.py:2054`, зовёт
   `self.git`) → `RealGitSandbox.git` (`tests/sandbox.py:1959`,
   `assertEqual` кода возврата). Нужно уточнение «непосредственно (помощником
   первого уровня, как проверяет guard `scripts/guard.py:4616–4642`)», иначе
   критерий читается двумя способами.
2. Нет критерия на неассертивную часть тел перенесённых тестов и на SPEC 5
   «зерно не фиксируется, выбор `broken`/`other` не меняется» (SPEC.md,
   AC-12/AC-13): правки вроде `box.rng.seed(0)` или смены входного литерала
   ни одним AC не ловятся (см. «Пути обхода»). Предложение: AC «тело каждой
   тестовой функции по AST равно телу исходного метода после замен
   требования 17 (`self`→имя фикстуры, `assertX`→`assert`, сообщение —
   вторым операндом, `self.<помощник>`→функция модуля)», со сверкой в PLAN —
   как уже требуется для трёх помощников (SPEC 15).
3. SPEC 19 (текст из уточнения 2 ТЗ) и «Контекст» SPEC связывают заявку
   `test_ac19_task_out_of_bounds_still_refused` с условием
   `in_outcome_bounds(profile)` у `orchestrator/fsm_advance.py:617` — это
   условие гейта честного FAIL_TO_PASS, которое уже есть в коде. Отказ,
   который проверяет тест, даёт `_tests_writing_foreign_plank_gate`,
   добавленный без условия (`orchestrator/fsm_advance.py:599`, тело
   `orchestrator/advance_gates/tests_writing.py:1060–1098`). Мутация заявки —
   поставить этот гейт под `if in_outcome_bounds(profile)`. Патч,
   «реализующий» ссылку буквально (правка условия на :617), тест не убьёт и
   уведёт исполнителя в переписывание заявки. Текст задан Оператором, поэтому
   это не fail. Стоит, чтобы PLAN назвал функцию мутации
   (`fsm_advance.tests_writing`, добавление `_tests_writing_foreign_plank_gate`).
4. Мелкое: «тестовые классы … — :240–553» — последний класс кончается на
   :549 (`tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py:549`).
