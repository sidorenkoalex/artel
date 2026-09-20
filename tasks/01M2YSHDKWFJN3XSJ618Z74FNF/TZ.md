---
task: 01M2YSHDKWFJN3XSJ618Z74FNF
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Приложения PLAN к защищённым путям: гейт применимости на выходе in_dev и применение пультом на мерже

Источник: решение Оператора 19.09 («если изменение — команда, если
команды нет — её нужно сделать»), строка копилки П2 11.09 «Приложение-
дифф к PLAN для защищённого пути не проверяется на применимость» и
инцидент 20.09: после включения хуков защиты main (01M2XMCC83)
приложение к `skills/test-authoring.md` из PLAN задачи 01M2XJKKPH
применить некому — прямой коммит Оператора в main хук отказывает, а
команды для защищённых путей нет.

Факты:
- Защищённые пути (`config.PROTECTED_PATHS`: gates.yaml, roles.yaml,
  `.github/`, `templates/`, `skills/`, docs/invariants.md,
  tests/test_invariants.py, `docs/adr/`, CLAUDE.md, AGENTS.md,
  targets.yaml) роль менять не вправе: гейт зон на `in_dev -> review`
  (`orchestrator/advance_gates/zones.py`) и гейт защищённых путей на
  merge_gate (`orchestrator/fsm_merge_gate.py::_protected_path_diff_gate`)
  отказывают безусловно с подсказкой «предложи правку приложением к
  PLAN (unified-дифф)».
- Формат приложения сложился практикой: раздел PLAN.md с заголовком,
  начинающимся на «## Приложение», внутри блок(и) ```diff с unified
  diff (`diff --git a/<путь> b/<путь>`). Сегодня в `tasks/` восемь таких
  разделов. Никто их не разбирает: guard и автогейты приложения не
  читают, ревьювер применимость не проверяет (инцидент 11.09: хунк без
  диапазонов, `git apply --check` отвечает «patch with only garbage»).
- Применение — ручной коммит Оператора в main в цикле мержа (память
  сессии); после мержа 01M2XMCC83 этот путь закрыт хуками, обход —
  только маркером `ARTEL_PULT_GIT=1` по решению Оператора.
- Цикл approve на merge_gate (`fsm_merge_gate._cmd_approve_merge_gate`)
  делает плотницкий merge в scratch-дереве, накладывает снимок
  артефактов, карту и RETRO (`_publish_merge_artifacts`,
  `orchestrator/fsm_postmerge.py`) и пушит явный sha. Полный прогон
  тестов в произвольном дереве уже есть:
  `orchestrator/acceptance.py::run_full_suite(root)`.
- Разбор секций артефактов: `scripts/guard.py::section_body`.

Требуется:
1. Разбор приложений: функция (в `scripts/guard.py`, рядом с
   `section_body`) возвращает список приложений PLAN.md — по каждому
   блоку ```diff внутри разделов «## Приложение…»: пути из заголовков
   `diff --git`, текст диффа. Блок без корректного заголовка `diff
   --git` или с путём вне `config.PROTECTED_PATHS` — именованная
   ошибка («приложение PLAN: путь <путь> не защищённый — правь в ветке
   задачи» / «приложение PLAN: нет заголовка diff --git»).
2. Гейт применимости на `in_dev -> review` (пакет
   `orchestrator/advance_gates/`, точка подключения — список гейтов
   `in_dev` в `orchestrator/fsm_advance.py`): каждое приложение проходит
   `git apply --check` против дерева базы сравнения ветки
   (`gitcmd.diff_base`, тот же выбор базы, что у гейта зон); отказ —
   именованное действие «переход отклонён: приложение PLAN неприменимо»
   с путём и текстом git, класс «роль ещё не закончила» (шаг developer
   повторяется с историей отказов). PLAN без приложений гейт не трогает.
   Закрывает строку копилки 11.09.
3. Применение на мерже: в `fsm_merge_gate._cmd_approve_merge_gate`
   после плотницкого merge и ДО снимка артефактов приложения
   применяются в scratch-дереве (`git apply`) и коммитятся одним
   коммитом «<id>: приложения Оператора — <пути>» (маркер пульта уже
   стоит в `gitcmd`). Неприменимость на этом этапе (main сдвинулся) —
   не `sys.exit`: задача возвращается в `in_dev` с причиной «приложение
   PLAN неприменимо после подтяжки: <путь>» тем же путём, что возврат
   по конфликту (`_handle_merge_conflict`), scratch-дерево убирается.
4. Проверка после применения: если хоть одно приложение трогает
   `tests/` или `.github/`, перед push в scratch-дереве выполняется
   `acceptance.run_full_suite(scratch)`; красный прогон — именованный
   отказ мержа «приложения ломают тесты: <хвост>», задача остаётся на
   merge_gate, scratch убирается, приложения не публикуются. Для
   остальных защищённых путей (skills, templates, docs/adr,
   docs/invariants.md, конфигурация) прогон не требуется — их проверит
   CI main.
5. Журнал и RETRO: запись «приложения применены: <пути> (sha)» на
   мерже; в RETRO задачи — строка с перечнем применённых путей
   (`fsm_postmerge._generate_and_commit_retro` уже собирает RETRO по
   журналу — сверить, нужна ли правка; если нужна, она в зоне).
6. Тесты (tests/): разбор приложений (корректный блок, блок без
   заголовка, путь вне защищённых); гейт применимости отказывает
   именованно и роль получает историю отказа, применимый диф проходит;
   мерж применяет диф в scratch и main несёт коммит приложений;
   неприменимость на мерже возвращает в in_dev с причиной; приложение к
   `tests/` с красным прогоном не публикуется; PLAN без приложений —
   поведение мержа байт-в-байт прежнее. Существующие
   `tests/test_protected_paths_gate.py`, `tests/test_merge_gate_ci_wait.py`,
   `tests/test_fsm_merge_gate_done_snapshot.py`,
   `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py` остаются
   зелёными.

Зоны: scripts/guard.py, orchestrator/advance_gates/,
orchestrator/fsm_advance.py, orchestrator/fsm_merge_gate.py,
orchestrator/fsm_postmerge.py, tests/.

Только чтение (не менять): orchestrator/config.py (`PROTECTED_PATHS`),
orchestrator/acceptance.py (`run_full_suite` переиспользуется),
orchestrator/gitcmd.py (маркер и `diff_base` как есть),
orchestrator/advance_gates/zones.py (гейт зон не меняется),
docs/backlog.md (источник), skills/test-authoring.md (пример приложения,
защищённый путь), templates/PLAN.md (формат раздела не меняется;
если потребуется подсказка о формате — приложением), .github/, docs/adr/,
docs/invariants.md, skills/, templates/ (названы как примеры защищённых
путей — содержимое не меняется), tasks/ (артефакты задач — только
чтение разделов PLAN).

Не входит: отдельная команда применения приложений задач, уже
закрытых (сегодняшнее приложение 01M2XJKKPH применяет Оператор
однократно с маркером обхода); проверка приложений ревьювером
(гейт делает это до ревью); изменение списка защищённых путей;
приложения к не защищённым путям.

Рамка: $45.
