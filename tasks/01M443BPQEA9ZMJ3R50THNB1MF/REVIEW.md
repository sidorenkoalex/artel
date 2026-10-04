---
task: 01M443BPQEA9ZMJ3R50THNB1MF
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Указание Оператора роли в разработке и ревью; подтяжка main перед шагом разработчика

## Фаза A — план

- Таблица покрытия полна (требования 1–8 → шаги 1–7); шаги — единицы
  размера MR. Подход не конфликтует с архитектурой: указание идёт через
  общий `_commit_answer` (тот же коммит ANSWER и та же перефиксация, что у
  ответа и мандата), подтяжка — через тот же узел
  `fsm._pull_main_or_escalate`.
- Два решения сверх SPEC (`run_plank=False`, пропуск подтяжки при
  метке, которая ещё ждёт шага роли) одобрены Оператором в ANSWER-1 п.4 и
  описаны в «Подходе».
- Утверждение PLAN о мьютексе merge-окна подтверждено. Узел
  `_pull_main_or_escalate` вызывают из `fsm.py:985`,
  `fsm_advance.py:568`, `canary.py:1317` и `fsm_merge_gate.py:630`.
  Мьютекс берёт только `_approve_merge_gate` → `fsm_merge_gate`
  (`fsm.py:1019-1031`). Новая точка ведёт себя так же, как прежние
  точки вне merge_gate.
- Раздел «Влияние на систему» и шаг 6 заявляют правку
  `docs/operator-session.md`, но в ветке её нет (см. R1-F1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `answer.py::_instruction_text`/`_commit_instruction`; действие `ANSWER создан: указание Оператора`, деталь — путь ANSWER; файл с маркером мандата идёт прежним путём (`_has_mandate_lines`) |
| 2 | OK | `raw.strip()` → отказ «пустой файл указания» до коммита |
| 3 | OK | `runner.in_role_environment()` проверяется до `_read_answer_file` |
| 4 | OK | `brief._developer_answer_names`: последний ANSWER плюс каждый, чья запись приёма от operator новее старта прошлого шага developer; пакет ревью уже несёт все ANSWER |
| 5 | OK | Указание обходит `lease.run_locked`; AC-8 зелёный |
| 6 | OK | `runner._pull_before_developer_step` вызывается после `_refuse_before_start` и до `_build_prompt`; исходы fresh, pulled, escalated и refused обработаны |
| 7 | OK | WIP-чекпоинт, `--no-ff` и авторазрешение карты — внутри общего узла; мьютекс — как на прежних точках вне merge_gate |
| 8 | Не реализовано | Карта регенерирована, но абзац `docs/operator-session.md` в ветку не закоммичен — R1-F1 |

## Замечания

- major — docs/operator-session.md:183 (ветка задачи, диапазон
  `a6d1656d..55b0fd55`) — абзац требования 8 лежит в рабочей копии
  незакоммиченным (`git status --short` → ` M docs/operator-session.md`;
  `git log a6d1656d..HEAD -- docs/operator-session.md` пуст). Автокоммит
  пульта (`checkpoint.commit_success_checkpoint` →
  `_commit_worktree_change`) снимает со стейджа пути вне зон SPEC
  (`zones: orchestrator/, tests/, docs/codebase-map.md`), и мандат
  «Расширение зон разрешено» из ANSWER-1 этот фильтр не учитывает. Оба
  коммита пульта (ef8567a6, 55b0fd55) файл не несут. Последствия:
  (1) после мержа требования 8 в main нет — документация оператора
  потеряна, хотя PLAN заявляет её сделанной (шаги 6 и 7, «Расширение
  зон»); (2) грязная рабочая копия вне зон ломает новую точку подтяжки:
  при первом же отставании ветки от `origin/main` чекпоинт подтяжки
  (`refuse_on_stray=True`) найдёт посторонний путь, и исход `refused`
  вызовет `sys.exit` в `_pull_before_developer_step`
  (`runner.py:537-539`) — шаг developer не начнётся. Тот же отказ
  ждёт и подтяжку на выходе из `in_dev`. Предложение: разработчику
  закоммитить `docs/operator-session.md` в ветку задачи самому
  (`git add docs/operator-session.md && git commit -m
  "01M443BPQEA9ZMJ3R50THNB1MF: docs/operator-session.md — указание
  Оператора и подтяжка перед шагом"`) и проверить, что `git status`
  после шага чист.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | docs/operator-session.md:183 | Абзац требования 8 не закоммичен в ветку: автокоммит пульта отфильтровал путь вне зон SPEC, мандат расширения зон фильтр не учитывает | Требование 8 не попадёт в main; посторонний грязный путь заставит подтяжку перед шагом отказать (`refused` → `sys.exit`), как только ветка отстанет | Закоммитить `docs/operator-session.md` в ветку задачи явно, убедиться, что рабочая копия чиста |

## Вердикт

changes_requested — исправить R1-F1: закоммитить абзац
`docs/operator-session.md` в ветку задачи. В остальном код и тесты
соответствуют SPEC и ANSWER-1.

Проверено по пути:
- Изменённые утверждения тестов сверены с base по diff. В методе
  `test_ac5_…keeps_old_refusal` прежний отказ заменён приёмом указания.
  В `test_developer_step_has_no_package` к прежнему точному списку
  вызовов дописаны три вызова fetch, случайная часть имени приватной
  ссылки нормализована, остальные вызовы не тронуты. Оба изменения
  покрыты мандатом ANSWER-1 (п.1, п.2, строка «Ослабление тестов
  разрешено»). Сужения данных под неизменными утверждениями не нашёл.
- `_read_checked_answer_file` проверяет только строки мандатов
  (`answer.py:101-117`). Указание без таких строк по построению этот
  рубеж не обходит.
- Граница брифа: действие `state -> in_dev` совпадает с форматом журнала
  (`budget.STATE_ENTRY_ACTION_PREFIX`). У ответа в `escalated` деталь —
  путь ANSWER, поэтому `_ANSWER_REL_RE` его подбирает.
- Заявки «Ловит мутацию» в `tests/test_runner_pre_step_pull.py` и в
  переписанных методах называют наблюдаемое расхождение. Долгоживущих
  файлов задачи новые тесты не повторяют: они кроют пропуск по метке,
  `run_plank` и границу до первого шага — этого долгоживущие файлы не
  касаются.

## Проверено исполнением

- `git status --short` → ` M docs/operator-session.md`;
  `git log --oneline a6d1656d..HEAD -- docs/operator-session.md` → пусто;
  `git show --stat HEAD ef8567a6` → файла нет ни в одном коммите пульта
  (основание R1-F1).
- `git rev-list --count HEAD..origin/main` → 0 (сейчас ветка не
  отстаёт, поэтому R1-F1(2) пока не сработал).
- `python3 -m pytest -q tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py tests/test_runner_pre_step_pull.py tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py "tests/test_review_package.py::CmdRunReviewPackageTest" tests/test_answer.py tests/test_brief.py`
  → 77 passed, 8 subtests passed (93 с).
- `grep` вызовов `_pull_main_or_escalate(` и чтение `fsm.py:1019-1031` —
  подтверждено утверждение PLAN о мьютексе merge-окна.
- Временную мутацию `_developer_answer_boundary` (граница по первому
  старту шага) не прогнал: команда правки файла требовала подтверждения.
  Чувствительность этого теста подтверждает только PLAN («6 мутаций»).

## Предложения системе

- `checkpoint._commit_worktree_change` (автокоммит шага developer)
  фильтрует пути по зонам SPEC и не учитывает мандат «Расширение зон
  разрешено» из ANSWER, хотя гейт зон его учитывает. Путь, законно
  расширенный Оператором, молча остаётся незакоммиченным, а роль
  уверена, что пульт его закоммитит (conventions-core: «код … коммитит
  пульт»). Стоит либо учесть мандат в фильтре, либо писать в журнал
  запись «путь вне зон не закоммичен: …», видимую роли и ревью.
