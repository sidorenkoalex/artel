---
task: 01M4JN2EDQP8Q3WVYK0TS95ZVC
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: scripts/guard.py, orchestrator/advance_gates/tests_writing.py, orchestrator/fsm_advance.py, docs/codebase-map.md, tests/
budget_usd: 30
---

# SPEC: Сетевые адреса в tests/ — пульт ловит до CI

## Контекст
Инвариант 35 (адресов `http(s)://<DNS-имя>` в `tests/**/*.py` нет, кроме
`localhost`/`127.0.0.1` и именованных исключений) живёт только в защищённом
`tests/test_invariants.py::NoNetworkAddressesInTestsTest` (~1877:
`_URL_RE` ~1894, `_EXEMPT_HOSTS` ~1895, `_EXCEPTIONS` ~1900–1919, `_host_of`,
`_dns_addresses`) и краснеет только в CI ветки, уже после шага разработчика.
Так было 11.09 (01M1R5B33C), 02.10 (01M3Y75C9T), 05.10 (01M46D5ZZQ — возврат,
эскалация, amend-tests) и 07.10 (01M4BEGQAV). Ни выход из `tests_writing`
(`scripts/guard.py::long_lived_sign_hits` ~2728 через
`orchestrator/advance_gates/tests_writing.py` ~275/~391), ни рубеж
`in_dev -> verifying` (`orchestrator/fsm_advance.py::in_dev` ~586) адресов не
проверяют. Задача — один источник правила в `scripts/guard.py` и отказ на
обоих рубежах пульта до похода в CI.

## Требования
1. Правило адресов — шаблон адреса, исключённые хосты (`localhost`,
   `127.0.0.1`, сравнение хоста точное, не префиксом), именованные
   исключения по паре (имя файла, хост) с обоснованиями — живёт в
   `scripts/guard.py` одной функцией. Инвариант 35 в
   `tests/test_invariants.py` вызывает эту функцию и не держит копию
   правила. Правка `tests/test_invariants.py` — приложением PLAN (защищённый
   путь); ожидания инварианта (что ловит, что пропускает) не меняются.
2. Выход из `tests_writing`: адрес `http(s)://<DNS-имя>` вне исключённых
   хостов и именованных исключений в долгоживущем файле `tests/` — отказ
   перехода тем же путём, что прочие признаки `long_lived_sign_hits`
   (отказ `LONG_LIVED_ACTION`), с указанием файла и номера строки.
3. Рубеж `in_dev -> verifying`: такой адрес в любом файле `tests/`, который
   ветка задачи добавила или изменила, — отказ перехода с указанием файла и
   номера строки; задача возвращается разработчику без похода в CI. Файлы
   `tests/`, которые ветка не затронула, на исход рубежа не влияют.
4. Нынешние именованные исключения (`test_github_adapter.py`/`github.com`,
   `test_ci_status.py`/`api.github.com`, `test_sandbox.py`/`example.invalid`,
   `test_sandbox.py`/`127.0.0.1.evil.example`) продолжают проходить на обоих
   рубежах и в инварианте 35; ослабления правила нет (набор ловимых адресов
   не сужается).

## Критерии приёмки

AC-1. Долгоживущий файл планки с адресом `https://example.test/x` — выход из
`tests_writing` отказывает (тем же отказом, что прочие признаки долгоживущих
файлов), в тексте отказа названы файл и номер строки с адресом.

AC-2. Тот же долгоживущий файл, где вместо DNS-имени адрес
`http://127.0.0.1:8080` (или `localhost`), — выход из `tests_writing` по
этому признаку не отказывает.

AC-3. Файл `tests/`, добавленный или изменённый веткой задачи, с адресом
`http(s)://<DNS-имя>` вне исключений — рубеж `in_dev -> verifying`
отказывает, называя файл и номер строки; задача остаётся у разработчика.

AC-4. Файл `tests/` с таким адресом, который ветка задачи не добавляла и
не меняла, — на исход рубежа `in_dev -> verifying` не влияет.

AC-5. Именованные исключения (каждая из четырёх пар требования 4) проходят
и на выходе из `tests_writing`, и на рубеже `in_dev -> verifying`.

AC-6. Инвариант 35 после наложения приложения даёт те же ответы на тех же
случаях: тест сверки подтверждает, что функция `scripts/guard.py` и
инвариант согласны (тот же адрес пойман/пропущен обоими, включая точное
сравнение хоста — `127.0.0.1.evil.example` вне пары исключения пойман).

AC-7. Мутация «функция guard не видит адрес» (функция возвращает пусто на
тексте с DNS-адресом) ловится тестом.

## Оценка объёма и деление
Сигнал: зона задевает механизм, на который опирается запись
`docs/invariants.md` (инвариант 35 — `NoNetworkAddressesInTestsTest`).
Прочие сигналы не срабатывают: файлов зоны вне общих зон — 3
(`scripts/guard.py`, `orchestrator/advance_gates/tests_writing.py`,
`orchestrator/fsm_advance.py`; `tests/test_invariants.py` — приложением),
критериев 7, бюджет $30 (рамка ТЗ).

Обоснование монолита (материал для решения Оператора): перенос правила в
`scripts/guard.py` (требование 1) — механика, на которую опираются оба
рубежа (требования 2, 3). Отдельно его можно было бы смержить, но объём
задачи мал (три файла кода и одно приложение), а рубежи без перенесённой
функции не имеют смысла; деление удвоило бы проход гейтов при рамке $30.
Инвариант 35 не ослабляется — меняется лишь место хранения правила при тех
же ожиданиях (требование 1, AC-6).

## Не входит
- Строки правила «в тестовых данных адреса только 127.0.0.1 или localhost»
  в `skills/test-authoring.md` и `skills/coding-standards.md` — защищённые
  пути, их вносит Оператор отдельным коммитом документов.
- Планка `acceptance_tests/` (вне `tests/`) как объект проверки адресов.
- Адреса вне `tests/`.
- Правка файлов только для чтения из ТЗ: `orchestrator/amend.py`,
  `orchestrator/acceptance.py`, `orchestrator/plank_run.py`,
  `orchestrator/liveness.py`, `orchestrator/pull.py`,
  `orchestrator/fsm_postmerge.py`, `orchestrator/brief.py`,
  `orchestrator/advance_gates/acceptance.py`,
  `orchestrator/advance_gates/plan_appendix.py`, `orchestrator/config.py`,
  `orchestrator/ci.py`, `orchestrator/appendix_tree.py`,
  `.github/workflows/ci.yml`, `docs/invariants.md`, `docs/adr/`,
  `docs/roadmap.md`, `docs/backlog.md`, `docs/operator-session.md`,
  `templates/`, `CLAUDE.md`, `models.yaml`, `roles.yaml`, `targets.yaml`,
  `.artel/`.
- Смена ожиданий существующих тестовых методов `tests/`: ТЗ её не
  заказывает, раздела «Меняемое поведение» нет; понадобится — только через
  этот раздел SPEC (инвариант 38), то есть вопросом Оператору.
- Полный зелёный набор `tests/` и зелёный CI ветки — их держит пульт.

## Материалы
- ТЗ: `tasks/01M4JN2EDQP8Q3WVYK0TS95ZVC/TZ.md` (сверка фактов — main 1f3a0413).
- `orchestrator/amend.py` (~500) тоже зовёт `long_lived_errors_from_files`:
  если признак адреса войдёт в `long_lived_sign_hits` (путь требования 2),
  `amend-tests` по тому же узлу начнёт отказывать долгоживущему файлу с
  DNS-адресом — прямое следствие «тем же путём», сам `amend.py` не
  меняется.
- Именованные исключения ключуются по имени файла `tests/`; на выходе из
  `tests_writing` долгоживущий файл ещё лежит в планке под своим именем —
  соответствие метки файла ключу исключения решает разработчик на PLAN.
