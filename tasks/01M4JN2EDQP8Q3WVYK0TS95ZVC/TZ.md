---
task: 01M4JN2EDQP8Q3WVYK0TS95ZVC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Сетевые адреса в tests/ — пульт ловит до CI

# ТЗ: Сетевые адреса в tests/ — пульт ловит до CI

Источник: строка бэклога «Сетевые адреса в tests/ — ловить пультом до CI»
(приоритет 1, решение Оператора 05.10); очередь критичных 10.10, пункт 7;
решение Оператора 10.10.2026 — заводить.

Случаи: 11.09 (01M1R5B33C), 02.10 (01M3Y75C9T, операторская правка
54e1cbc0), 05.10 (01M46D5ZZQ: три адреса в долгоживущем файле автора
тестов и один в файле разработчика — возврат, эскалация, amend-tests),
07.10 (01M4BEGQAV: https://example.test в долгоживущем тесте). Каждый раз
инвариант 35 краснел только в CI ветки, после шага разработчика.

Факты (main 1f3a0413, сверка 10.10):
- Правило живёт только в защищённом `tests/test_invariants.py::NoNetworkAddressesInTestsTest`
  (~1877): `_URL_RE = re.compile(r"https?://[^\s'\"]+")` (~1894),
  `_EXEMPT_HOSTS = ("localhost", "127.0.0.1")` (~1895), `_EXCEPTIONS`
  по паре (имя файла, хост) с обоснованиями (~1900–1919), `_host_of`,
  `_dns_addresses`; тест сканирует `tests/**/*.py` как текст и сообщает
  адреса без номеров строк. `tests/test_invariants.py` уже импортирует
  `scripts.guard` (~42).
- `scripts/guard.py::long_lived_sign_hits` (~2728) — признаки
  долгоживущих файлов (`SIGN_*` ~2533–2541, пояснения
  `_SIGN_EXPLANATIONS` ~2543), формат ошибки
  `«<файл>:<строка>: признак «…» — …»` в `long_lived_errors_from_files`
  (~2766); вызывающие — `orchestrator/advance_gates/tests_writing.py`
  (~275, ~391; отказ `LONG_LIVED_ACTION`), `orchestrator/amend.py` (~500).
  Адресов не проверяет.
- Рубеж in_dev → verifying (`orchestrator/fsm_advance.py::in_dev` ~586)
  ничего из `tests/test_invariants.py` не гоняет.

Требуется:
1. Правило адресов (шаблон, исключённые хосты, именованные исключения с
   обоснованиями) переезжает в `scripts/guard.py` одной функцией; инвариант
   35 в `tests/test_invariants.py` вызывает её, а не держит копию — один
   источник правила. Правка защищённого файла — приложением PLAN к
   `tests/test_invariants.py`, ожидания инварианта (что ловит, что
   пропускает) не меняются.
2. Выход из tests_writing: адрес http(s)://<DNS-имя> вне исключений в
   долгоживущем файле `tests/` — отказ перехода тем же путём, что прочие
   признаки (`long_lived_sign_hits`), с файлом и номером строки.
3. Рубеж in_dev → verifying: такой адрес в любом файле `tests/`, который
   ветка задачи добавила или изменила, — отказ перехода с файлом и
   строкой и возврат разработчику без похода в CI.
4. Нынешние исключения (`test_github_adapter.py`/github.com,
   `test_ci_status.py`/api.github.com, `test_sandbox.py`/example.invalid и
   127.0.0.1.evil.example) продолжают проходить; ослабления нет.
5. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- Долгоживущий файл с `https://example.test/x` — выход из tests_writing
  отказывает, называя файл и строку; с `http://127.0.0.1:8080` — проходит.
- Файл tests/, изменённый веткой, с адресом DNS-имени — рубеж
  in_dev → verifying отказывает; файл, ветку не затронутый, — не влияет.
- Именованные исключения проходят на обоих рубежах.
- Инвариант 35 после приложения даёт те же ответы на тех же случаях
  (тест сверки: функция guard и инвариант согласны).
- Мутация «функция guard не видит адрес» ловится тестом.

Зоны: scripts/guard.py, orchestrator/advance_gates/tests_writing.py,
orchestrator/fsm_advance.py, docs/codebase-map.md, tests/.
Приложением: tests/test_invariants.py.

Только чтение (не менять): orchestrator/amend.py, orchestrator/acceptance.py,
orchestrator/plank_run.py, orchestrator/liveness.py, orchestrator/pull.py,
orchestrator/fsm_postmerge.py, orchestrator/brief.py,
orchestrator/advance_gates/acceptance.py,
orchestrator/advance_gates/plan_appendix.py, orchestrator/config.py,
orchestrator/ci.py, orchestrator/appendix_tree.py,
.github/workflows/ci.yml, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, CLAUDE.md,
models.yaml, roles.yaml, targets.yaml, .artel/.

Не входит: строки правила «в тестовых данных адреса только 127.0.0.1 или
localhost» в skills/test-authoring.md и skills/coding-standards.md —
защищённые пути, их вносит Оператор отдельным коммитом документов;
планка acceptance_tests/ (вне tests/); адреса вне tests/.

Рамка: $30.

Набор моделей: по умолчанию.
