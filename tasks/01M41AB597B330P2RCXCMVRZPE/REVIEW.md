---
task: 01M41AB597B330P2RCXCMVRZPE
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Перефиксация не узаконивает сдвиг ссылки документов мимо пульта

## Фаза A — план
- Таблица покрытия полна (требования 1–10); добавлен шаг 6 (R1-F1), им
  покрыто требование 5. Шаги размером с MR.
- Требование 8 / AC-12: приложения к инварианту 25 нет, обоснование то же,
  что в итерации 1, — принимаю.
- «Влияние на систему» сходится с инкрементальным diff итерации 2:
  `fixation.py` (переименование `stop_on_moved_ref` → `stop_on_ref_drift`,
  новая ветка отказа, `unread_refusal`), 4 места вызова в `answer.py`/`amend.py`,
  отказ гейта перечня в `tests_writing.py`, новый файл
  `tests/test_docs_ref_deleted_refusal.py`. Существующие тесты в итерации 2 не
  тронуты: в diff `tests/` только новый файл, удалённых строк нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: узел зовут все места требования 1. |
| 2 | OK | Сдвиг — эскалация без паспорта и фиксации, именованный отказ, запись журнала. |
| 3 | OK | Сравнение по-прежнему только в `fixation.ref_drift`. |
| 4 | OK | AC-7/AC-10: законная цепочка зелёная. |
| 5 | OK | R1-F1 закрыт: `stop_on_ref_drift` (`fixation.py:236-241`) при `drift is not None and not drift.moved` пишет журнал и отказывает `unread_refusal` до коммита; гейт перечня (`tests_writing.py:338-346`) отказывает `GateRefusal`. Прочие места (`set_state` `store.py:644`, `snapshot.py:91`, `doctor/ignored_artifacts.py:50`, `checkpoint._docs_ref_drift:911`) уже не писали при любом `drift is not None`, это перепроверено чтением. `kill` с удалённой ссылкой: `set_state("killed")` без паспорта, `commit_closing` без коммита — в ссылку не пишет. |
| 6 | OK | `approve <sha>` → `legitimize` без изменений. |
| 7 | OK | AC-10 зелёный. |
| 8 | OK | Приложения нет, обоснование в PLAN. |
| 9 | OK | У всех 4 методов нового файла есть заявка «Ловит мутацию»; временной мутацией подтверждено, что тесты её ловят (см. ниже). Тесты долгоживущий файл не повторяют: сценарий удалённой ссылки там не покрыт. |
| 10 | OK | Без изменений с итерации 1. |

## Замечания

Новых замечаний нет. R1-F1 закрыт по всему классу: `answer`, `zones-extend`,
`amend-tests` в обоих режимах (через общий `stop_on_ref_drift`) и гейт перечня.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fixation.py:236; answer.py:176, :233; amend.py:525, :830; advance_gates/tests_writing.py:338 | Удалённая ролью ссылка при живой фиксации проходила как «голова не прочитана»; запись пульта создавала корневой коммит и перефиксировала его | Подмена была бы узаконена, `check_integrity` молчал бы | Принято: при непрочитанной голове — журнал и именованный отказ без коммита и без смены состояния. Гейт перечня отказывает. Сторож `tests/test_docs_ref_deleted_refusal.py` краснеет на мутации (4 failed) |

## Вердикт
approved. R1-F1 исправлен и проверен исполнением, новых blocker и major нет.

## Проверено исполнением
- `python3 -m pytest -q tests/test_docs_ref_deleted_refusal.py
  tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py tests/test_answer.py
  tests/test_amend.py tests/test_long_lived_transitions.py
  tests/test_fsm_advance_tests_writing_artifact_source.py`: 95 passed,
  15 subtests passed (1 мин 24 с).
- Временная мутация из заявок: в `stop_on_ref_drift` вернул `if not drift.moved: return`,
  в `tests_writing` заменил отказ при непрочитанной голове на `if False:`.
  Прогон `tests/test_docs_ref_deleted_refusal.py` дал 4 failed (все 4 метода).
  Код возвращён `git checkout -- orchestrator`, дерево чистое.
- Планка задачи: скопировал в рабочий каталог, прогнал
  `pytest tasks/01M41AB597B330P2RCXCMVRZPE/acceptance_tests` — 2 passed.
  Потом удалил только `tasks/01M41AB597B330P2RCXCMVRZPE/`.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки
  `built_at_sha` — 0 строк расхождения, карта свежая.
- grep `ref_drift|.moved` по `orchestrator/`: проверил, что `drift.moved`-only
  остались только там, где запись при непрочитанной голове и так не идёт
  (`store.set_state`: эскалация только при сдвиге, паспорт и фиксация — только при
  `drift is None`; `cleanup` kill: дальше `set_state` и `commit_closing`;
  `legitimize`).
- CI коммита 546016c1 зелёный (из пакета).

## Предложения системе
- В песочнице роли нет `rm` и `ls` (`command not found` в zsh шага). Уборку
  скопированной планки, которую предписывает миссия, приходится делать через
  `python3 -c "shutil.rmtree(...)"`. Стоит прямо написать это в миссии ревьювера
  рядом с командой копирования.
