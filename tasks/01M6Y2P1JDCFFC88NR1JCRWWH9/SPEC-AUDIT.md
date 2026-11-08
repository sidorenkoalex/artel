---
task: 01M6Y2P1JDCFFC88NR1JCRWWH9
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/a_sandbox.py, tests/b_sandbox.py, tests/fixtures.py, tests/outcome_gate_sandbox.py, tests/report_outcome_sandbox.py, tests/sandbox.py, tests/test_01m6xhjh6ej8d0br5prngzay8c_size_gate_paths.py, tests/test_01m6xhjh6ej8d0br5prngzay8c_size_rules.py; в) SPEC требует приложения PLAN; д) ТЗ ссылается на ADR: ADR-0032"
spec_sha: 2fef468d8bd6fba6c77150840789f7e765e2436d
schema_version: 5
---

# SPEC-AUDIT: Правила guard для общего состояния: фикстуры уровня модуля только через shared_readonly, build — помощник гейта неослабления (ADR-0032, этап 5, часть б)

## ТЗ и SPEC
- ТЗ пп. 1–7 → SPEC требования 1–7, все критерии ТЗ → AC-1…AC-7, матрица ТЗ
  перенесена целиком, с добавленной строкой «правила размера на файлах
  планки» (решение №1.6). Безопасность тестов и заметки разработчику
  перенесены дословно (SPEC.md:173-183).
- Решения Оператора первого круга №1.1–№1.6 и второго №2.1–№2.4 внесены:
  №2.1 — SPEC.md:39-52 и AC-1 (псевдоним `pt.fixture`, присваивание
  `pytest.fixture(scope=…)(f)`, `scope=None`); №2.2 — SPEC.md:98-114
  (`tests/*_sandbox.py`, `sandbox_sources`, `config.ROOT`, `{}` без
  исключения) и случаи AC-4; №2.3 — псевдонимы класса и `shared_readonly`,
  `_sandbox`, повторное создание (SPEC.md:62-66, :88-93, «Не входит»
  SPEC.md:231-236) и случаи AC-2/AC-4; №2.4 — регулярное выражение
  `^(tasks/[^/]+/)?acceptance_tests/` (SPEC.md:130-143), адрес
  `records.trace` `:2163-2177` и случай AC-6 «сегмент в середине пути».
- Противоречий между решениями не нашёл: №2.2 и №2.3 уточняют №1.3, №2.4 —
  №1.6, как они сами и заявляют.
- Требований сверх ТЗ и решений нет.

## Факты против кода
Подтвердилось:
- `scripts/guard.py:1985` `_fixture_decorator` — только `decorator_list`;
  `:2036` `_fixture_table`; `:2091` `_FixtureScope`, `records.trace` —
  `:2163-2177` (фикстура, запрошенная фикстурой, одним уровнем);
  `:2228` `_fixture_helper_calls`; `:2349` `_changed_fixture_names`;
  `:2873` `assertion_changes`; `:4399-4407` `long_lived_errors_from_files`
  с `sandbox_sources`; `:4618` `_style_violations`; `:4725`
  `pytest_style_errors_from_files`; `:4916-4930` `is_long_lived_test_path`
  с `<dir>/` из нуля или больше сегментов.
- `tests/sandbox.py:711` `TmpDirTest`, `:1609` `TmpRootTest`, `:1925`
  `RealGitSandbox(TmpRootTest)`, `:2534` `construct`, `:2539`
  `sb = self.sandbox_cls()` вне `try` (try с `:2541`), `:2568`
  `shared_readonly`. `tests/report_outcome_sandbox.py:335`
  `ReportSandbox(RealGitSandbox)`, `tests/outcome_gate_sandbox.py:251`
  `OutcomeGateSandbox(GitignoreCommittedRealGitSandbox)`; есть и цепочки
  глубже (`tests/merge_outcome_sandbox.py:61`,
  `tests/components_outcome_sandbox.py:43`, `tests/prior_outcome_sandbox.py:69`)
  — определение требования 3 их покрывает транзитивностью.
- `orchestrator/test_lint.py:292` `SANDBOX_SOURCE_PATH =
  tests/([^/]*_)?sandbox\.py` (захватывает и `tests/test_sandbox.py`, но его
  классы — `unittest.TestCase` без `TmpDirTest`/`TmpRootTest`, вреда нет).
- `tests/fixtures.py:42` `_sandbox(cls)`; фикстуры `:57-93` — ровно шесть
  названных в требовании 3.
- Классы `tests/sandbox.py` вне определения: `TmpPlanPathTest`
  (`:738`, временный каталог без подмен `config`), `StubTest` (`:2150`),
  `FakeProc`/`SpyRun`/`PollGate` — исключены решением №1.3/№2.2,
  подмен `config` не делают; отклонением не считаю.
- Опыт: pytest 9.1.1, `inspect.signature(pytest.fixture)` — `scope`
  только ключевой (`fixture_function=None, *, scope=…`): позиционной формы
  обхода требования 1 нет.
- `_pytest_aliases` (`test_lint.pytest_aliases`) с `_pytest_name`
  (`guard.py:1971-1982`) развёртывают и `import pytest as pt`, и
  `from pytest import fixture` — опора требования 1 на псевдонимы есть.

Не подтвердилось / не сказано:
- **Ф1. Реальный путь проверки стиля не получает `sandbox_sources`.**
  `pytest_style_errors_from_files` вызывается в коде пульта только из
  `long_lived_errors_from_files` (`scripts/guard.py:4462-4463`, без
  `sandbox_sources`). Вызывающие передают дерево кодовой ветки только в
  `long_lived_errors_from_files`: `orchestrator/advance_gates/tests_writing.py:519-526`
  (рабочая копия), `:651-662` (`sandbox_sources_at(code_branch)`),
  `orchestrator/preflight.py:261-300`, `orchestrator/amend.py:1125-1136`,
  `:1390-1409`. Требование 3 (SPEC.md:108-114) требует «перечень по
  исходникам модулей песочниц из того же дерева, что проверяемые файлы»,
  но называет лишь новый параметр `pytest_style_errors_from_files` с
  `None` → `config.ROOT`; проброс из `long_lived_errors_from_files` не
  назван. Буквальная реализация оставит `guard.py:4462` без аргумента, и
  перечень на всех трёх местах требования 6 будет из `config.ROOT` —
  корня пульта (`orchestrator/config.py:11`), а не дерева кодовой ветки:
  класс песочницы, добавленный в ветке задачи в `tests/<имя>_sandbox.py`,
  не распознается. Ни один AC этого не ловит (AC-4 зовёт
  `pytest_style_errors_from_files` напрямую). Побочный эффект проброса:
  `tests_writing.py:651-652` передаёт `{}` при выключенном `size_marks`,
  и тогда классовая часть требования 3 молча выключится (у артели
  `size_marks: required`, `targets.yaml:56` — сейчас не проявляется).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `scope=` в декораторе не проверяется; не литерал пропущен; псевдоним `pt.fixture` не развёрнут; присваивание `pytest.fixture(scope=…)(f)` пропущено; ложный отказ на `scope="function"`/`None`. До кода — красный по отсутствию отказа, без побочных процессов (строки в памяти) |
| AC-2 | да | присваивание не распознано через `import tests.sandbox as m`/`from tests import sandbox`/псевдоним; `assert` в `build` или его помощнике не отклоняется; лямбда как `build` принята; иная форма вызова не отклонена. Красный до кода по отсутствию отказов |
| AC-3 | да | `build` не попадает в `_fixture_table`; помощник `build` не прослеживается; прослеживается функция, которую `build` не вызывает. До кода — красный (гейт не называет изменение) |
| AC-4 | да | `tmp_root` через параметр/`usefixtures`/обёртку/транзитивную обёртку пропущен; `RealGitSandbox()`/`R()`/`_sandbox(...)` пропущены; подкласс из `tests/*_sandbox.py`/цепочки не распознан; `FakeProc` ложно отклонён; второе присваивание принято; `lint_base` освобождает добавленное присваивание; `{}` бросает. **Не ловит** «`long_lived_errors_from_files` не передаёт `sandbox_sources`» (Ф1) |
| AC-5 | да | конструктор вне `try`; уборка `_run_cleanups(None)` без проверки `sb is not None` (подменит исключение, `failure` не выставится). Подпроцесс pytest — с пределом времени и своей группой процессов по разделу безопасности; до кода — красный (`AttributeError` у второго/третьего теста), рекурсии и меняющих команд нет |
| AC-6 | да | фильтр метки отсутствует; фильтр только `acceptance_tests/` без `tasks/<id>/`; фильтр «содержит `acceptance_tests`» снимает размер с `tests/acceptance_tests/…`; `long_lived_plank_errors` сломан. Красный до кода по лишней строке |
| AC-7 | да | сводка мутаций AC-1…AC-6 |

## Зоны
- Требования 1–5 меняют `scripts/guard.py` и `tests/sandbox.py` (входит и
  в `tests/`), новые тесты — `tests/`, карта — `docs/codebase-map.md`;
  зоны SPEC это покрывают.
- Вызывающие в `orchestrator/` (tests_writing, preflight, amend) не
  требуют правки: проброс Ф1 закрывается внутри `scripts/guard.py`.
- Защищённые пути `skills/test-authoring.md`, `skills/review-checklist.md`
  — только приложениями PLAN (требование 7); песочница ролей не
  расширяется.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `_style_violations` (новые отказы) | стиль pytest, `scripts/guard.py:4618`; `tests/test_guard_pytest_fixtures.py:89` | да, отказы только добавляются; в образцах существующих тестов нет `scope=` и `shared_readonly(` вне `tests/test_01m6xhm9qhegdq6fra5y8g12aq_shared_readonly.py` (он правилами не проверяется) | AC-1, AC-2, AC-4 | в силе |
| `_fixture_table` / прослеживание | гейт неослабления, `scripts/guard.py:2036`, `:2163-2177` | да, плюс `build` | AC-3 | в силе |
| `pytest_style_errors_from_files` (параметр `sandbox_sources`) | — | да | AC-4; проброс на реальном пути — **не покрыт** (Ф1) | вопрос Оператору |
| `_SharedModuleState.construct` | `tests/sandbox.py:2534-2557`; тесты части а `tests/test_01m6xhm9qhegdq6fra5y8g12aq_shared_readonly.py:232-481` | да, исход успешного построения не меняется | AC-5 | в силе |
| `long_lived_errors_from_files` размер | `scripts/guard.py:4483-4487`; `tests/test_01m6xhjh6ej8d0br5prngzay8c_size_*.py` | снимается только с меток `^(tasks/[^/]+/)?acceptance_tests/`; существующие тесты размера таких меток с группой «долгоживущий» не дают | AC-6 | в силе |
| Освобождение `lint_base` | `scripts/guard.py:4744-4757` | да, с оговоркой требования 3 | AC-4 | в силе |

## Пути обхода гейтов
- Ф1: исполнитель добавляет параметр и проходит AC-4, не пробросив его
  на `guard.py:4462` — правило классов песочниц работает по дереву пульта,
  а не ветки задачи; песочница, добавленная задачей в
  `tests/<имя>_sandbox.py`, проходит мимо требования 3.
- Динамические формы (`getattr`, присваивание класса другому имени,
  `pytest.fixture(**kw)`) — принятый пробел «Не входит» (SPEC.md:231-236);
  `**kw` формально относится к требованию 1, а оговорка названа для
  требований 2–3, но под «не литерал» её можно отнести — замечание
  справочное, не отклонение.
- Иных путей буквального выполнения в обход смысла не нашёл.

## Вердикт
concerns — одно отклонение, решаемое Оператором на гейте:

1. **Ф1** — `scripts/guard.py:4462-4463` (единственный вызов
   `pytest_style_errors_from_files` на пути `tests_writing`/`preflight`/
   `amend-tests`) без `sandbox_sources`; SPEC.md:108-114 не требует
   проброса из `long_lived_errors_from_files`, при `None` перечень берётся
   из `config.ROOT` (`orchestrator/config.py:11`), а не из дерева кодовой
   ветки, которое вызывающие уже передают
   (`orchestrator/advance_gates/tests_writing.py:651-662`,
   `orchestrator/preflight.py:261-300`, `orchestrator/amend.py:1125-1136`).
   AC-4 (SPEC.md:165) проброс не ловит. Предлагаемое решение: требование 3
   дополнить «`long_lived_errors_from_files` передаёт свой
   `sandbox_sources` в `pytest_style_errors_from_files` (при `None` —
   модули `config.ROOT`, как сейчас для размера)» и случаем AC-4/AC-7
   через `long_lived_errors_from_files(..., sandbox_sources={…})` с
   классом из `tests/<имя>_sandbox.py`; заодно решить, что делать при
   `sandbox_sources={}` от `tests_writing.py:651-652` у проекта без
   `size_marks` (сейчас у артели не проявляется, `targets.yaml:56`).
