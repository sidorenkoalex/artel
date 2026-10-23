---
task: 01M5KBGF184B07SVXMD4R1NXXC
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Отказ автогейта приёмки из-за окружения — отдельный класс «окружение» в журнале и в подсказке

## Фаза A — план
- Таблица покрытия полна (требования 1–6 → шаги 1, 2); шаг 2 добавлен под R1-F1 и проверяем (файл, 4 метода, названные мутации).
- «Влияние на систему» соответствует диффу итерации 2: новый файл `tests/test_fsm_autogate_env_refusal.py` и правка одного комментария в `orchestrator/fsm_autogate.py:50`; существующие тесты не тронуты.
- «Риски» обновлены: сверку текста таймаута теперь держит сторож в `tests/`.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Код без изменений с итерации 1 (проверен там); итерация 2 меняет только комментарий `fsm_autogate.py:50`. |
| 2 | OK | Без изменений; дополнительно закреплено `tests/test_fsm_autogate_env_refusal.py::test_environment_refusal_adds_record_and_hint`. |
| 3 | OK | Без изменений; закреплено `test_other_refusal_has_no_environment_record`, `test_other_producers_are_not_environment`. |
| 4 | OK | Без изменений. |
| 5 | OK | Новый тест детерминирован: подмены `gates.policy`, `_log_acceptance_checklist`, `_autogate_conditions`, `suspend_on_autogate_refusal` — из списка SPEC; БД — `SchemaConnTmpRootTest`. |
| 6 | OK | Существующие тесты не правились; новый файл тестов — вне запрета («существующие не правятся»). |

## Замечания

Нет. Сторож проверен временными мутациями (в памяти процесса), каждая красит заявленные методы — см. «Проверено исполнением». Повтора долгоживущего теста задачи нет: файлов `tests/test_01m5kbgf184b07svxmd4r1nxxc_*.py` не существует, планка целиком разовая.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm_autogate.py:51, :58-67, :481-487; tests/ | Новое свойство закрыто только разовой планкой; в `tests/` сторожа нет | Смена текста производителя в `acceptance.py` молча выключила бы класс при зелёном CI | **reviewer, итерация 2:** принято. `tests/test_fsm_autogate_env_refusal.py` сверяет классификатор с самими производителями (`_full_suite_timeout_note()`, `(1500, …)`, `_not_started_note`, `_db_in_tree_note`, `FULL_SUITE_NO_TESTS_NOTE`, `UNKNOWN_PREFIX`), вину `BLAME_PULT`, вторую запись/строку на таймауте и их отсутствие на красном наборе. Заявки «Ловит мутацию» у всех 4 методов называют наблюдаемое расхождение; проверены мутациями M1–M3 (ниже). |

## Вердикт
approved — R1-F1 закрыто, других замечаний нет.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_fsm_autogate*.py tests/test_canary_acceptance_reason.py` — 35 passed, 16 subtests passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5KBGF184B07SVXMD4R1NXXC` — 6 passed, код выхода pytest 0.
- Временные мутации без правки файлов (`mock.patch.object` в процессе, прогон `tests/test_fsm_autogate_env_refusal.py` через unittest):
  - M1 `_TIMEOUT_NOTE_START` без «tests/» (смена начала текста производителя) — 5 провалов: `test_environment_refusal_adds_record_and_hint` + 4 подтеста `test_environment_producers_get_their_kind`;
  - M2 классификатор возвращает вид на любой отказ — 7 провалов: `test_other_refusal_has_no_environment_record` + 6 подтестов `test_other_producers_are_not_environment` (включая `_db_in_tree_note` — «прогон не начат» без «машина занята»);
  - M3 классификатор всегда `None` (ветка не срабатывает) — 7 провалов: запись/строка и все подтесты видов;
  - базовый прогон — 0 провалов. Дерево чистое (`git status --short` пуст).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — пусто, карта свежа; изменение откатил `git checkout`.
- CI коммита 79ecd333 зелёный (16 проверок, из пакета).

## Предложения системе
- Временную мутацию правкой файла (`sed -i`, `python -c … write`) харнесс роли не пропускает без подтверждения; работает подмена в памяти (`mock.patch.object` + `unittest` из `python3 -c`) — стоит описать этот приём в skills/review-checklist.md («Сторож — проверен временной мутацией»).
