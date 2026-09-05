---
task: 01M1REVEZ1HESMJ7AFD5A9MEJ8
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: зависимости стека (P0) — файл закреплённых версий, venv пульта, установка в CI и у роли

## Подход

Продолжение шага, ушедшего в таймаут (ANSWER-1.md): код (16 файлов) уже
был в ветке, не хватало `PLAN.md` и уборки WIP-мусора. Этот шаг —
проверка унаследованного кода приёмочными тестами (уже залочены в
`tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/`), устранение
найденных огрехов и оформление плана.

Реализация (по факту в ветке, требование за требованием):

- `orchestrator/stack.py`: `THIRD_PARTY_EXCEPTIONS` несёт три записи
  (`pytest`, `pytest_timeout`, `xdist` — ИМПОРТИРУЕМЫЕ имена, не
  написание PyPI: дефис не бывает валидным идентификатором Python),
  каждая с причиной (требование 1, AC-2). `check_stack()` расширен
  двумя проверками: существование `.artel/venv` (`_venv_exists_check`,
  AC-8) и, если venv есть, сверка версий его пакетов (`pip freeze`
  внутри venv) с файлом закреплённых версий (`_venv_packages_check`,
  AC-7) — вторая не зовётся без первой, сверять нечего без venv.
  `_parse_pinned_versions`/`_normalize_package_name` — общий разбор
  формата `pip` для обеих сторон сверки (PEP 503: `_`/`-`/регистр
  взаимозаменяемы в написании имени пакета).
- `requirements.lock` (новый, корень репозитория): точные версии
  (`==`) `pytest`, `pytest-timeout`, `pytest-xdist` и их транзитивных
  зависимостей (`execnet`, `iniconfig`, `packaging`, `pluggy`,
  `pygments`) — резолвлено фактической установкой 05.09.2026, версии
  сверены с PyPI построчно на этом шаге (`pypi.org/pypi/<пакет>/json`,
  каждая запись существует как реальный релиз) — не написаны руками
  наугад (AC-1).
- `orchestrator/venv.py` (новый): `sync(target, lock_file)` — создаёт
  `target` командой `subprocess.run([sys.executable, "-m", "venv",
  str(target)])`, если это ещё не venv (маркер — отсутствие
  `pyvenv.cfg`), затем `pip install -r <lock_file>` внутрь него;
  идемпотентно — второй вызов на уже созданном venv не пересоздаёт его
  (AC-4/AC-5/AC-6). `cmd_venv_sync()` — тело команды CLI.
- `orchestrator/artel.py`: команда `venv-sync` в таблице команд `main()`
  и в usage/справке модуля (AC-4).
- `orchestrator/config.py`: `REQUIREMENTS_LOCK` (`ROOT /
  "requirements.lock"`) и `VENV_DIR` (`ROOT / ".artel" / "venv"`) —
  единственный источник путей для `venv.py`/`stack.py`/`runner.py`, не
  дублируются литералами.
- `orchestrator/runner.py`: `_venv_interpreter_bin()` — зовёт
  `stack.check_stack()` (та же проверка, что AC-7/AC-8, не отдельная
  копия логики) и поднимает `OSError`, называющий venv, если ЛЮБАЯ
  проверка с «venv» в имени вернула WARN; иначе отдаёт `<VENV_DIR>/bin`.
  `role_env()` зовёт её и ставит результат ПЕРВЫМ элементом PATH роли
  (AC-12). `OSError` из `role_env()` — уже документированный
  существующий контракт (`orchestrator/doctor.py::check_git_identity`,
  SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN): три места, вызывающие `role_env()`
  (`check_git_identity`, `isolation_smoke`, `_live_smoke_run` в
  `doctor.py`) уже ловят `OSError` и деградируют в `Check`/лог, не
  падают; настоящий отказ шага по этой причине — существующая ветка
  `run_agent_once` (`agent run SKIPPED`, `orchestrator/runner.py:656`) —
  ни то, ни другое этой задачей не изменено (AC-13 закрыт переиспользо-
  ванием контракта, не новым кодом отказа).
- `.github/workflows/ci.yml` — защищённый путь, НЕ тронут кодом этой
  ветки: диф приложен ниже, разделом «Приложение» (требование 3,
  AC-9/AC-10/AC-11).
- Тесты: `tests/test_stack.py` (записи исключений + venv-проверки
  `check_stack`), `tests/test_venv.py` (новый — `sync()`, реальный
  `python -m venv`/подменённый `pip install`, без сети),
  `tests/test_multitarget.py::RoleEnvVenvInterpreterTest` (PATH роли и
  отказ без согласованного venv), `tests/sandbox.py` (новый
  `_stub_check_stack`/патч в `TmpRootTest.setUp` — без него ЛЮБОЙ путь
  песочницы, доходящий до `role_env()`, отказывал бы `OSError`: временный
  `root` песочницы не несёт согласованного `.artel/venv`) и точечные
  правки в `tests/test_agent_prompt.py`, `tests/test_invariants.py`,
  `tests/test_review_freshness.py`, `tests/test_review_package.py` —
  тот же патч там, где эти файлы заводят СОБСТВЕННЫЙ класс песочницы
  вместо `TmpRootTest`.

Уборка этого шага (по итогам прогона приёмочных тестов, все 15 зелёные
без правок кода):
- Удалены `ci-diff.patch`/`scratch_check.py` — рабочий WIP-мусор
  прерванного таймаутом шага (диф `ci.yml` перенесён сюда, в раздел
  «Приложение»; `scratch_check.py` — отладочный скрипт, не часть
  реализации).
- Уточнены две устаревшие фразы в докстрингах (`orchestrator/stack.py`
  — «список исключений… пуст», `tests/test_invariants.py` — «пуст на
  сегодня»): обе написаны до расширения списка исключений этой же
  задачей и больше не соответствуют содержимому `THIRD_PARTY_EXCEPTIONS`
  тут же рядом в коде.
- `docs/stack.md` несёт ту же устаревшую фразу («список пуст на
  сегодня») — сознательно НЕ тронут: `docs/` нет в зонах SPEC
  (`requirements.lock, orchestrator/stack.py, orchestrator/venv.py,
  orchestrator/runner.py, tests/, PLAN.md`), правка вне зоны — риск
  зонового гейта на пустом месте; отмечено в «Риски» ниже для
  Оператора.

Все 15 методов приёмочных тестов (`tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/
acceptance_tests/`) — зелёные на унаследованном коде без единой правки
`orchestrator/*.py`/`requirements.lock`. Версии в `requirements.lock`
дополнительно сверены с PyPI на этом шаге поштучно (`pytest==9.1.1`,
`pytest-timeout==2.4.0`, `pytest-xdist==3.8.0`, `execnet==2.1.2`,
`iniconfig==2.3.0`, `packaging==26.3`, `pluggy==1.6.0`,
`pygments==2.21.0`) — каждая существует как реальный релиз пакета.

## Шаги

1. `orchestrator/stack.py` + `requirements.lock`: список исключений
   манифеста, venv-проверки `check_stack()` (требование 1, требование 2
   — сверка).
2. `orchestrator/venv.py` + `orchestrator/config.py` (`REQUIREMENTS_LOCK`,
   `VENV_DIR`) + `orchestrator/artel.py` (`venv-sync`): создание
   `.artel/venv` (требование 2 — создание).
3. `orchestrator/runner.py` (`_venv_interpreter_bin`, `role_env`):
   интерпретатор роли из venv, отказ без согласованного venv
   (требование 4).
4. Диф-приложение `.github/workflows/ci.yml` (раздел «Приложение»):
   установка зависимостей из файла закреплённых версий (требование 3).
5. Тесты (`tests/test_stack.py`, `tests/test_venv.py`,
   `tests/test_multitarget.py`, `tests/sandbox.py` и точечные правки
   зависимых песочниц) + приёмочные тесты задачи (требование 6).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 4 |
| 4 | 3 |
| 5 | 1, 2, 3 (граница объёма — раннер pytest не добавлен нигде) |
| 6 | 5 |

## Влияние на систему

- `check_stack()` — расширение аддитивное: три новые проверки
  (`venv-`), существующие (`python`/`git`/`gh`/`claude`) не изменены;
  `THIRD_PARTY_EXCEPTIONS` расширен с пустого до трёх записей — сканер
  «только стандартная библиотека» (`tests/test_invariants.py::
  StdlibOnlyImportsInvariantTest`, S1) по-прежнему падает на импорте
  вне списка (проверено приёмочным AC-3 и юнитом на синтетическом
  дереве) — инвариант не ослаблен, расширен ровно на три поименованных
  разрешения с причиной каждое.
- `role_env()` теперь может отказать `OSError` по НОВОЙ причине
  (venv не готов) — это не новый класс отказа: `OSError` из `role_env()`
  уже был документированным контрактом (`doctor.py::check_git_identity`)
  ДО этой задачи по другой причине (курируемый слой не создался); три
  существующих вызывающих места `role_env()` в `doctor.py` уже ловят
  `OSError` общим образом и не упадут на новой причине — подтверждено
  прогоном `tests.test_doctor` (124/124 зелёных, без правок с его
  стороны). Настоящий отказ шага (`agent run SKIPPED`) — существующая
  ветка `runner.run_agent_once`, тоже не тронута.
- Операционный риск после мержа (тот же, что называет само SPEC для
  гипотетической части D монолитного или раздельного мержа): с момента
  мержа ЛЮБОЙ шаг роли требует существующего и согласованного
  `.artel/venv` — если Оператор не прогонит `venv-sync` сразу после
  мержа, все последующие шаги ролей получат `agent run SKIPPED` до
  первого успешного `venv-sync`. Не новый риск от решения делить/не
  делить задачу — свойство самого требования 4 SPEC; явно
  отмечено в «Риски» ниже как операционное действие Оператора сразу
  после мержа.
- `tests/sandbox.py::TmpRootTest` и её потребители (`test_invariants`,
  `test_multitarget`, `test_multitarget_invariants`, `test_canary`,
  `test_doctor` и др.) продолжают проходить с общим патчем
  `stack.check_stack` — подтверждено прогоном затронутых модулей
  (`tests.test_stack`, `tests.test_venv`, `tests.test_invariants`,
  `tests.test_multitarget`, `tests.test_multitarget_invariants`,
  `tests.test_doctor`, `tests.test_agent_prompt`,
  `tests.test_review_freshness`, `tests.test_review_package`,
  `tests.test_sandbox` — 176+124+45+14 тестов зелёные, полный
  перечень команд см. «Риски»/журнал шага).
- Диф-приложение `.github/workflows/ci.yml` не убирает и не меняет ни
  одного существующего шага джоба `python` — добавляет один шаг
  (`pip install -r requirements.lock`) сразу после `setup-python`, до
  прогона тестов; версия пакетов нигде не продублирована литералом
  (единственный источник — `requirements.lock`).
- Откат: любая из четырёх правок (`stack.py`, `venv.py`, `runner.py`,
  диф `ci.yml`) откатывается независимо реверсом соответствующего
  коммита/диффа — `role_env()` без `_venv_interpreter_bin` возвращается
  к прежнему PATH, `check_stack()` без venv-проверок — к прежним
  четырём проверкам, `requirements.lock`/`venv.py` без риска для
  остального кода (новые файлы, на них никто, кроме `stack.py`/
  `runner.py`, не ссылается).

## Риски

- Операционный риск мержа (см. «Влияние на систему»): Оператору нужно
  прогнать `python3 orchestrator/artel.py venv-sync` сразу после мержа
  этой задачи — до первого успешного прогона все шаги ролей будут
  `agent run SKIPPED`.
- `docs/stack.md` несёт устаревшую фразу «список пуст на сегодня»
  (строка 22) — вне зон SPEC этой задачи, не тронут; Оператору стоит
  поправить её отдельно либо явным расширением зон.
- `_venv_packages_check()` зовёт `<venv>/bin/python -m pip freeze`
  живым подпроцессом (таймаут 30 c) при каждом вызове `check_stack()`
  внутри `role_env()` — то есть дважды за шаг роли (`doctor.
  check_git_identity` в preflight и сам `run_agent_once`), пока venv
  существует; на практике venv пульта после `venv-sync` содержит 8
  пакетов — `pip freeze` возвращает быстро (проверено локально при
  прогоне `tests/test_venv.py`, создающего реальный venv), но при
  будущем расширении `requirements.lock` десятками пакетов стоит
  держать это в уме.
- Версии `requirements.lock` (пункт «Подход») сверены с PyPI
  однократно на этом шаге (сеть была доступна исполнителю), но сама
  установка `pip install -r requirements.lock` целиком (венв +
  разрешение зависимостей pip) на реальной сети этим шагом не
  прогонялась — `git apply --check`/юнит-тесты подтверждают контракт
  кода, не факт «пакеты действительно совместимы друг с другом при
  разрешении pip»; первый реальный `venv-sync` Оператора после мержа —
  первая живая проверка этого файла целиком.

## Предложения системе

- Класс «WIP-мусор прерванного таймаутом шага остаётся в ветке до
  следующего developer» (`ci-diff.patch`, `scratch_check.py` в этой
  задаче) — coding-standards.md не называет явно шаг «убрать
  отладочные файлы перед `status: ready`» после восстановления из
  WIP-чекпоинта; стоило бы явно упомянуть рядом с существующим
  правилом про `git status` в конце шага.

## Приложение: диф `.github/workflows/ci.yml`

`git apply --check` на чистом `main` (`72a755a3`) — пройден.

```diff
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index ef5a705b..cd4110ae 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -158,6 +158,8 @@ jobs:
       - uses: actions/setup-python@v5
         with:
           python-version: ${{ steps.stack-python.outputs.version }}
+      - name: зависимости из файла закреплённых версий (01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 3)
+        run: python3 -m pip install -r requirements.lock
       - run: python3 -m py_compile orchestrator/artel.py scripts/guard.py
       - name: снимок ссылок репозитория до прогона тестов (SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 1)
         run: git for-each-ref --format='%(refname) %(objectname)' refs/heads/ refs/artifacts/ > /tmp/refs-before.txt
```

## Расширение зон

Пути: orchestrator/artel.py

Обоснование (Оператор, 05.09): требование 2 SPEC вводит команду пульта
`venv-sync`; подключение подкоманды в диспетчере `orchestrator/artel.py`
(таблица команд и строка usage) — единственный способ сделать команду
доступной, зона SPEC его не назвала. Правка — одна строка таблицы и
одна строка usage. Мандат — ANSWER-2.md.

