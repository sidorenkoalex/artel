---
task: 01M2B6JNFD381MZT70CVB5NJQC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Гейт зон: собственный каталог задачи и уборка планки после подтяжки

Источник: копилка docs/backlog.md, строка П1 от 12.09 «Ложный отказ гейта
зон после чистой подтяжки main на in_dev -> review» (коммит b9d962e5).
Решение Оператора 12.09: первая задача волны 4.

Факты:
- Выход `in_dev` (orchestrator/fsm_advance.py, `in_dev`, строка ~1481):
  сначала `fsm._pull_main_or_escalate` (подтяжка main), затем
  `_zones_gate_refuses` (гейт зон), затем остальные гейты и
  `_acceptance_run_refuses` (прогон планки).
- Подтяжка (orchestrator/pull.py, `evaluate` ~355; `_materialize_and_run_plank`
  ~274–312) после успешного merge материализует планку в worktree задачи
  через `acceptance.materialize_from_branch(task_id, artifact_branch, wt_path)`
  (orchestrator/acceptance.py:164 — НА МЕСТЕ, каталог
  `tasks/<id>/acceptance_tests/` worktree, по замыслу регрессии №14) и гоняет
  её; после прогона файлы остаются в worktree неотслеживаемыми.
- Гейт зон (`_zones_gate`, ~839–947) с задачи 01M290PVYG (в main с 21:20Z
  11.09) добавляет к committed-диффу неотслеживаемые файлы worktree
  (`_untracked_worktree_paths`, ~815; `git status --porcelain=v1
  --untracked-files=all`) — и считает материализованную планку
  `tasks/<id>/acceptance_tests/*.py` диффом вне зон: отказ «дифф трогает
  файлы вне заявленных zones и COMMON_ZONES … tasks/<id>/acceptance_tests/…».
- 12.09: четыре ложных отказа на четырёх задачах волны 3 (01M2ARQD7C
  13:08Z и 14:28Z, 01M2ARQGY5 13:14Z, 01M2ARQRDV 13:20Z, 01M2ARQMTY 15:23Z),
  каждый — остановка `auto` стоп-краном T038 и ручной обход Оператора
  (rm -rf tasks/<id> в worktree + повторный auto). Отказ возникает ТОЛЬКО
  когда подтяжку делает сам `pull.evaluate` на этом выходе; если ветка уже
  свежа (подтяжку сделал шаг developer), `Fresh` — материализации до гейта
  нет, планка материализуется позже в `_acceptance_run_refuses`, и гейт её
  не видит (01M297HF 08:55Z, 01M2ARQGY5 15:41Z).
- `checkpoint._zone_paths` (orchestrator/checkpoint.py:849–867) считает
  `tasks/<id>/` зоной задачи; `_zones_gate` — нет. Несогласованность.
- Задача 01M2ARQMTY (смержена 12.09) снимает подтяжку по чисто документным
  сдвигам main, но любой код-мерж в main по-прежнему ведёт к подтяжке и
  ложному отказу для всех задач, стоящих в in_dev.

Требуется:
1. Довесок неотслеживаемых файлов в `_zones_gate` не считает путями вне
   зон файлы под `tasks/<task_id>/` — собственный каталог задачи, тем же
   правилом, что `checkpoint._zone_paths` (единый источник: вынести
   правило «каталог задачи — своя зона» в одно место, которым пользуются
   оба, без изменения поведения checkpoint). Неотслеживаемые файлы ВНЕ
   `tasks/<task_id>/` по-прежнему считаются (сегодняшний AC-6
   01M290PVYG сохраняется байт-в-байт).
2. `pull._materialize_and_run_plank` после прогона планки убирает
   материализованный каталог `tasks/<task_id>/acceptance_tests/` из
   worktree, если до материализации его там не было (не трогая файлы,
   которые лежали до неё) — worktree после подтяжки чист, как до неё.
   Источник истины планки — артефактная ветка, диск ей не нужен.
3. Журнал: пропуск неотслеживаемых путей под `tasks/<task_id>/` гейтом
   зон не журналируется отдельно (это штатное); уборка планки после
   подтяжки — без новой записи, если нечего убирать.
4. Тесты (tests/test_zones_gate.py либо соседний файл гейта, tests/
   test_pull.py): (а) worktree с неотслеживаемым
   `tasks/<id>/acceptance_tests/test_x.py` и диффом строго в зонах — гейт
   зон пропускает (мутация «планка считается вне зон» — красный);
   (б) неотслеживаемый файл вне `tasks/<id>/` (например
   `orchestrator/stray.py`) — прежний отказ; (в) после `Pulled` в стенде с
   bare origin (по образцу существующих тестов pull) каталог
   `tasks/<id>/acceptance_tests/` в worktree отсутствует, а прогон планки
   при этом состоялся; (г) существующие тесты гейта зон, checkpoint и pull
   — без ослабления.

Зоны: orchestrator/fsm_advance.py, orchestrator/pull.py,
orchestrator/checkpoint.py, tests/.

Приложением: orchestrator/acceptance.py (`materialize_from_branch`, в
зону не входит), docs/backlog.md (строка П1 12.09 «Ложный отказ гейта
зон…»), журналы задач 01M2ARQD7C/01M2ARQGY5/01M2ARQRDV/01M2ARQMTY 12.09.

Не входит: правка acceptance.py и самой материализации на месте;
изменение порядка гейтов на выходе in_dev; поведение checkpoint при
переносе артефактов.

Рамка: $30.
