---
task: 01M287TPG0HAVXS8CHBCY679WN
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: `answer` для задачи в `in_dev` (мандат на расширение зон), `zones-extend`, `amend-tests --from-branch`

## Подход

Три независимых расширения существующих команд, инфраструктура для
всех трёх уже в кодовой базе (`fsm_advance._ZONES_MANDATE_MARKER`,
`fsm_advance._split_zone_paths`, `fsm_advance._plan_zones_extension_paths`,
`fsm_advance._answer_zones_mandate` — маркер и гейт зон уже умеют читать
мандат из ЛЮБОГО ANSWER-n.md; не хватает только команд, которые его
пишут за пределами эскалации).

1. `orchestrator/answer.py::_cmd_answer` — гейт состояния расширяется:
   `escalated` — прежний путь без изменений; `in_dev`/`review` — путь
   принимается ТОЛЬКО если текст файла несёт строку маркера (проверка
   до отказа, не вместо него) — состояние не трогается, журнал получает
   отдельный текст записи с путями мандата. Любое другое состояние —
   прежний отказ, прежнее сообщение.
2. `orchestrator/answer.py::cmd_zones_extend` (новая функция, тот же
   модуль — переиспользует `_next_answer_number`/`_answer_document`,
   т.е. пишет тот же по форме ANSWER-документ, что и `answer`) — строит
   ANSWER-текст с обеими строками (маркер + «мандат Оператора: …»),
   коммитит его тем же плотницким приёмом, затем читает PLAN.md ГОЛОВЫ
   артефактной ветки (`gitcmd.show`, не worktree) и, если раздел
   «## Расширение зон» несёт РОВНО то же множество путей — сразу
   обновляет `tasks.zones_extension` (merge с уже имеющимся); иначе —
   БД не трогает, журналирует «раздел PLAN отсутствует — разработчик
   добавит на следующем шаге» (одна и та же запись для «раздела нет» и
   «пути не совпадают» — SPEC требование 2 не различает эти два случая
   исходом).
3. `orchestrator/amend.py` — новая ветка `_cmd_amend_tests_from_branch`:
   источник сравнения — не worktree, а git-дерево на двух ревизиях
   артефактной ветки (`tests_locked_sha` и её текущая голова), через
   `gitcmd.ls_tree_files`/`gitcmd.show` с ревизией вместо имени ветки
   (обе функции берут ЛЮБУЮ git-ревизию, не только имя ветки — тот же
   приём, каким `_zones_gate` уже сравнивает диффы). Расхождение есть —
   `tests_locked_sha` сдвигается на sha головы БЕЗ нового коммита (само
   содержимое уже на ветке — в этом смысл флага), журналируется список
   отличающихся файлов тем же действием `amend.AMEND_ACTION`. Расхождения
   нет — отказ с буквальным «нет расхождения» (SPEC AC-8 фиксирует эту
   формулировку явно, она НЕ совпадает с «нет изменений» пути без
   флага). Обязательный прогон pytest (как в пути без флага) сюда не
   переносится: контракт критериев (AC-7/AC-8/AC-9) не требует зелёного
   прогона для этого пути, а материализация содержимого ветки в
   worktree только ради прогона противоречила бы смыслу флага
   (сравнение независимо от worktree) — если Оператор увидит на
   практике необходимость прогона, это отдельный запрос, не входит в
   эти три критерия.
4. `orchestrator/artel.py` — таблица диспетчера: `zones-extend <id>
   <путь1>[, <путь2>]` → `answer.cmd_zones_extend`; `amend-tests`
   получает разбор `--from-branch` (`"--from-branch" in rest`),
   пробрасывается в `amend.cmd_amend_tests` именованным аргументом
   `from_branch` (дефолт `False` — путь без флага не меняется, AC-9).
5. `docs/operator-session.md`/`docs/operator-gates.md` — короткие
   правки текстом (эти файлы в зоне задачи, диффа-приложения не
   требуют): у существующего упоминания «answer только для escalated»
   и обходного трёхшагового мандата — пометка, что команды заведены
   этой задачей; в `operator-gates.md` — строка под «Гейт эскалации»
   про `zones-extend`/маркер/`--from-branch` как штатный путь вместо
   ручных операций.
6. Итерация 2 (REVIEW.md итерации 1, замечание R1-F1 — blocker):
   `_cmd_answer` (ветка `in_dev`/`review`) и `_cmd_zones_extend`
   принимали мандат «от Оператора» без проверки, что вызов пришёл не
   из окружения самой роли, ведущей этот же активный шаг — developer
   на своём `in_dev`/reviewer на своём `review` физически имели
   безусловный `Bash(python3:*)` (`runner.role_cmd`) и могли выполнить
   `python3 orchestrator/artel.py zones-extend <свой же id> <путь>`
   (или `answer` файлом, который сами же и написали) и сами себе
   выдать мандат. Закрыто тем же рубежом, что уже защищает расшифровку
   пула канарейки (`canary._authorized_pool_payload`, `canary.py:317`)
   — `runner.in_role_environment()` в начале обеих точек, отказ ДО
   чтения файла/коммита. Симметричная запись в `permissions.deny`
   курируемого слоя роли (`docs/reference/role-home/claude/
   settings.json`) вне зон этой задачи — приложена к этому PLAN
   unified-диффом (см. «Приложение» ниже), применяет Оператор.

## Шаги

1. `orchestrator/answer.py`: гейт состояния `_cmd_answer` (маркер +
   in_dev/review), новая `cmd_zones_extend`/`_cmd_zones_extend`.
2. `orchestrator/amend.py`: `_cmd_amend_tests_from_branch` + сниппет
   чтения дерева по ревизии; `cmd_amend_tests` получает `from_branch`.
3. `orchestrator/artel.py`: регистрация `zones-extend`, разбор
   `--from-branch` у `amend-tests`.
4. `docs/operator-session.md`, `docs/operator-gates.md`: текстовые
   правки.
5. Юнит-тесты новых веток (`tests/test_answer.py` дополнить классом
   мандата, `tests/test_amend.py` — классом `--from-branch`; новый
   `tests/test_zones_extend.py` для CLI-команды) + прогон трёх
   заблокированных `acceptance_tests/` этой задачи и затронутых модулей.
6. Итерация 2 (R1-F1): `runner.in_role_environment()` в `_cmd_answer`/
   `_cmd_zones_extend` (`orchestrator/answer.py`) + регресс-тесты
   `tests/test_answer.py::RoleEnvironmentRefusalTest`; unified-дифф
   `docs/reference/role-home/claude/settings.json` — приложением к
   этому PLAN, не коммитом (путь вне зон задачи).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 3 |
| 3 | 2, 3 |
| 4 | 5 |
| 5 | 4 |

## Влияние на систему

- Гейт зон (`fsm_advance._zones_gate`) не меняется — он уже умеет читать
  мандат из ЛЮБОГО ANSWER-n.md и уже умеет сверять раздел PLAN с
  `zones_extension`; эта задача только добавляет команды, которые пишут
  то, что гейт уже читает. Риск регресса гейта — нулевой (код гейта не
  тронут), но юнит-тесты `tests/test_zones_gate.py` прогоняются как
  контроль.
- `answer` для `escalated` — путь не тронут (гейт состояния получает
  ветвление ДО отказа, тело коммита то же самое, тот же
  `_answer_document`), `tests/test_answer.py`/`tests/test_answer_gate.py`/
  `tests/test_answer_branch_reads.py` — регресс-контроль без правки
  ассертов.
- `amend-tests` без `--from-branch` — путь не тронут (новая ветка кода
  изолирована флагом), `tests/test_amend.py` — регресс-контроль.
- Новый путь `amend-tests --from-branch` сознательно НЕ прогоняет
  pytest перед сдвигом лока (см. «Подход», п.3) — единственное
  отклонение от «тем же способом, что обычный amend-tests» в
  формулировке SPEC; критерии AC-7/AC-8/AC-9 этого не требуют
  буквально. Если это разночтение неверно — эскалация ниже.
- `zones-extend` пишет в БД (`tasks.zones_extension`) без прохождения
  через гейт — тот же приём, что уже применяет `_zones_gate` сам с
  собой (запись `zones_extension` при совпадении путей PLAN); не новый
  канал записи, тот же самый.
- Откат — вся правка в трёх модулях и двух командах без изменения схемы
  БД и без изменения существующих путей выполнения; откат — ревёрт
  коммита.
- Итерация 2 (R1-F1): рубеж `runner.in_role_environment()` в `answer`/
  `zones-extend` не меняет happy-path Оператора (его сессия не несёт
  `HOME`/`CLAUDE_CONFIG_DIR` роли — обе переменные ставит только
  `runner.role_env` процессу шага) и не меняет ветку `escalated` (там
  рубежа нет — на этом состоянии процесс роли уже завершён, действующего
  вызывающего из-под роли физически нет). Регресс подтверждён
  `AnswerCommandRefusalsTest`/`AnswerMandateMarkerOutsideInDevOrReviewStillRefusesTest`/
  `ZonesExtendCommandTest`/тремя приёмочными тестами AC-1/AC-4 —
  зелёные без правки ассертов.

## Риски

- Круговой импорт `answer.py` → `fsm_advance.py`: проверено по карте
  импортов (`fsm_advance` не импортирует `answer` ни прямо, ни
  транзитивно) — риска нет, но это единственное место кодовой базы,
  где `answer.py` обзаводится зависимостью на `fsm_advance.py` (раньше
  было наоборот только текстом комментария, не импортом).
- Итерация 2: та же проверка для новой зависимости `answer.py` →
  `runner.py` — `runner.py` не импортирует `answer.py` ни прямо, ни
  транзитивно (проверено `python3 -c "import orchestrator.answer"` —
  чистый импорт, без цикла); карта кодовой базы перегенерирована тем
  же коммитом (`python3 scripts/codebase_map.py`).

## Приложение: unified-дифф docs/reference/role-home/claude/settings.json (R1-F1)

Путь вне зон этой задачи (курируемый слой роли — не `orchestrator/`/
`docs/operator-*.md`/`tests/`) — применяет Оператор. Проверено `git
apply --check` на чистом дереве перед сдачей (журнал шага: `APPLIES
CLEANLY`). Второй, независимый от кода рубеж (симметрично
`permissions.deny` записям `init`/`doctor --restore` в этом же файле):
роль не сможет даже попытаться вызвать `answer`/`zones-extend` из-под
Bash своего шага — код (`runner.in_role_environment()`, см. «Подход»,
п.6) отказывает и без этой записи, здесь — защита в глубину, не замена.

```diff
diff --git a/docs/reference/role-home/claude/settings.json b/docs/reference/role-home/claude/settings.json
index 60d03f78..8737366d 100644
--- a/docs/reference/role-home/claude/settings.json
+++ b/docs/reference/role-home/claude/settings.json
@@ -8,6 +8,8 @@
       "Bash(git remote add:*)",
       "Bash(python3 orchestrator/artel.py init:*)",
       "Bash(python3 orchestrator/artel.py doctor --restore:*)",
+      "Bash(python3 orchestrator/artel.py answer:*)",
+      "Bash(python3 orchestrator/artel.py zones-extend:*)",
       "Bash(openssl enc -d:*)",
       "Bash(security find-generic-password:*)"
     ]
```

## Предложения системе

- SPEC этой задачи описывает `amend-tests --from-branch` фразой «тем же
  способом, что и обычный amend-tests», подразумевая, видимо, только
  формат записи лока/журнала — но формулировка читается неоднозначно
  (обязателен ли зелёный прогон). Критерии приёмки (AC-7/AC-8/AC-9) не
  требуют прогона буквально, поэтому реализация его не делает; будущим
  SPEC на похожие команды стоит явно писать «включая обязательный
  прогон» или «без прогона», а не полагаться на «тем же способом».
- До этой задачи `runner.in_role_environment()` защищал только
  расшифровку пула канарейки (единственный пример в кодовой базе) —
  класс шире:
  любая новая Оператор-only команда, доступная из активного состояния
  роли (`in_dev`/`review`/…), нуждается в том же рубеже. Ревьювер этой
  задачи (REVIEW итерации 1) уже предложил вынести это в
  `skills/review-checklist.md` — присоединяюсь: без явного пункта
  чек-листа класс находится вручную по кодовой базе, не по инструкции.
