---
task: 01M5KBGF184B07SVXMD4R1NXXC
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Отказ автогейта приёмки из-за окружения — отдельный класс «окружение» в журнале и в подсказке

## Фаза A — план
- Таблица покрытия полна (требования 1–6 → шаг 1); один шаг размера MR оправдан: дифф 35 строк в одном модуле.
- Подход не конфликтует с архитектурой: ветка добавлена после прежних записи/строки, до `suspend_on_autogate_refusal`.
- PLAN «Риски» сам называет дефект, который ниже стал замечанием R1-F1: «ловит AC-6 планки (разовый), долгоживущего сторожа нет» — риск записан, но не закрыт.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm_autogate.py:45-67`: снятие `AUTOGATE_REFUSAL_PREFIX`, схлопывание пробелов, начала сверены с `acceptance._full_suite_timeout_note` (acceptance.py: `"прогон полного набора tests/ превысил "`) и `f"{FULL_SUITE_NOT_STARTED}: машина занята"` (`_not_started_note`). `_db_in_tree_note` («прогон не начат: полный набор…») и отказ `checks_local … не определены` в класс не попадают. Реальные пути причин проверены: `_autogate_conditions` даёт `f"автогейт: {tree.mark(run.detail)}"`, `tree.mark` добавляет пометку суффиксом, повторно взятый итог таймаута (`full_suite`, ветка `saved`) начинается с того же `_full_suite_timeout_note()`, `checks_local` на незелёном итоге дописывает текст через `\n` в хвост — начало не страдает. |
| 2 | OK | `fsm_autogate.py:481-487`: прежние запись и строка не тронуты, затем вторая запись (actor `fsm`, деталь `класс: окружение (<вид>) — …; повторить проверку: artel.py approve <id>`) и строка `[<id>] класс отказа: …`; затем прежний `suspend_on_autogate_refusal`. Тексты совпадают с SPEC побайтно. |
| 3 | OK | при `kind is None` поток прежний. |
| 4 | OK | переходов, повторов, approve не добавлено; `models` не тронут. |
| 5 | OK | планка детерминирована (подмены из списка SPEC), 6 passed. |
| 6 | OK | дифф — только константы, функция, ветка отказа (+ служебный `_TIMEOUT_NOTE_START`, разрешённый требованием 1 «со сверкой»); существующие тесты не тронуты. |

## Замечания

- major — `orchestrator/fsm_autogate.py:51` (`_TIMEOUT_NOTE_START`), `:58-67` (`autogate_refusal_class`), `:481-487` (ветка отказа); `tests/` — новых тестов нет — Свойство «отказ класса окружение получает вторую запись и строку, и классификатор согласован с текстами производителей `acceptance.py`» после мержа остаётся без сторожа. Вся планка задачи помечена `Группа: разовый` (`acceptance_tests/test_env_refusal_record.py:4`, `test_refusal_class_producers.py:3`, `test_refusal_preserved.py:3`), а по ADR-0018 п.3 планку смерженной задачи не гоняет ни CI, ни автогейт. Предпосылка SPEC «Не входит» («свойства держат долгоживущие приёмочные тесты автора тестов») не сбылась: долгоживущих тестов нет. Проверено grep'ом: `autogate_refusal_class`/`AUTOGATE_ENV_REFUSAL_ACTION`/`ENV_REFUSAL_CLASS` в `tests/` не упоминаются ни разу. Сценарий поломки: правка текста `_full_suite_timeout_note` (например, «прогон полного набора tests/ превысил предел …» или смена слова) — литерал `_TIMEOUT_NOTE_START` молча перестаёт совпадать, таймауты (5 из 7 отказов окружения по находке CR-2026-10-22-17) снова пишутся без класса, весь набор `tests/` зелёный; PLAN «Риски» сам это признаёт. — Предложение: добавить в `tests/` тест (новый файл, существующие не правятся — требование 6 соблюдено; зона `tests/` в SPEC объявлена; «не заказывается» в SPEC — не запрет, а следствие несбывшейся предпосылки) минимум с двумя свойствами: (а) сверка с производителями как в AC-6 — `autogate_refusal_class` для `acceptance._full_suite_timeout_note()`, `_full_suite_timeout_note((N, "…"))`, `_not_started_note(<держатель>)` → вид, для `_db_in_tree_note(…)`/`FULL_SUITE_NO_TESTS_NOTE`/`UNKNOWN_PREFIX…` → `None`; (б) запись `AUTOGATE_ENV_REFUSAL_ACTION` и строка подсказки на отказе окружения и их отсутствие на отказе вне класса (AC-1/AC-3 в сжатом виде). Каждый метод — с заявкой «Ловит мутацию: …». Закрытые имена `acceptance` в `tests/` — обычная практика, ограничения планки на них здесь не действуют. Альтернатива по PLAN «Предложения системе» (константа-начало в `acceptance.py`) вне зоны SPEC — не предлагаю.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_autogate.py:51, :58-67, :481-487; tests/ | Новое свойство (класс «окружение», сверка начала текста таймаута с `acceptance._full_suite_timeout_note`) закрыто только разовой планкой; в `tests/` сторожа нет | Смена текста производителя в `acceptance.py` молча выключит класс для таймаутов при зелёном CI | Добавить тест(ы) в `tests/`: сверка классификатора с производителями (AC-6) и вторая запись/строка на отказе окружения vs её отсутствие вне класса, с заявками «Ловит мутацию» |

## Вердикт
changes_requested — закрыть R1-F1 (долгоживущий сторож в `tests/`). Код по существу SPEC выполнен верно; других замечаний нет.

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5KBGF184B07SVXMD4R1NXXC` — 6 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_fsm_autogate*.py tests/test_canary_acceptance_reason.py tests/test_approve_acceptance_full_suite.py` — 43 passed, 6 subtests passed.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расходится только `built_at_sha` (не дефект); изменение откатил `git checkout -- docs/codebase-map.md`, дерево чистое.
- `grep -rln "autogate_refusal_class\|AUTOGATE_ENV_REFUSAL_ACTION\|отказ окружения\|ENV_REFUSAL_CLASS" tests/ orchestrator/` — в `tests/` только постороннее совпадение `tests/test_01m484rnv3qbdy3b0m16j916zp_wave_breaker_projects.py:56` (другой контекст), сторожа нет → R1-F1.
- `grep -n "Группа" acceptance_tests/*.py` — все три файла планки «разовый».
- Чтение `orchestrator/acceptance.py:2320-2400, 2477-2495, 3375-3440, 3487-3525`, `orchestrator/appendix_tree.py:105-117`, `orchestrator/fsm_autogate.py:330-440` — сверка реальных текстов причин, приходящих в классификатор (итог в таблице, требование 1).

## Предложения системе
- Класс «SPEC отказывается от тестов в `tests/`, ссылаясь на долгоживущую планку, а автор тестов помечает всю планку разовой» — предпосылка SPEC не сверяется ни на гейте планки, ни при входе в разработку; стоит, чтобы гейт фиксации планки сверял «Не входит: тест в tests/» с наличием хотя бы одного `Группа: долгоживущий` (skills/test-authoring.md / гейт планки).
