---
task: 01M3SF7DPFGEZ7VYEGGXGTX49E
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Main не краснеет незаметно: guard после снимка, CI main после мержа и в pin-update

# ТЗ: Main не краснеет незаметно — guard после снимка, CI main после мержа, в pin-update и doctor

Источник: решение Оператора 30.09.2026; строки копилки 30.09 (П1) о мерже
01M3RWA2786HCAC8PT3XSBKQT4, сделавшем main красным, и о `pin-update` на
коммит с красным CI main.

Факты (пин 34b298c7, main f6e111f2):
- CI проверяет артефакты задач `scripts/guard.py`: на ветке задачи — в
  режиме `--artifact-branch` (нарушения содержания черновика — только
  предупреждение), на main — `guard.py --all` (любой `.md` в `tasks/`
  обязан иметь frontmatter).
- Гейт мержа (`orchestrator/fsm_merge_gate.py`) после merge накладывает
  снимок артефактной ветки (`_overlay_artifact_snapshot`, коммит «снимок
  артефактной ветки поверх merge») и отправляет main в origin, не
  прогоняя `guard.py --all` по получившемуся дереву. 30.09 так в main
  попал `tasks/01M3RWA2786HCAC8PT3XSBKQT4/acceptance_tests/README.md` без
  frontmatter; main был красным с 45a26011 до f6e111f2 (три часа).
- `pin-update` (`orchestrator/pin.py::cmd_pin_update`) требует зелёную
  канарейку на целевом коммите, но не сверяет CI этого коммита в origin.
  30.09 пин дважды сдвинут на коммит с красным CI main. Правило «pin-update
  только по зелёному CI origin/main» есть в `docs/operator-session.md`,
  программной сверки нет. `doctor` цвет CI головы main не показывает.
- Статус CI коммита умеет читать `orchestrator/ci.py` (`check_runs`,
  `failed_check_names`, `status_kind`).

Требуется:
1. Гейт мержа: после наложения снимка и до push в origin прогоняется
   `guard.py --all` по дереву результата. Нарушения — именованный отказ
   мержа до push (задача остаётся на `merge_gate`, main в origin не
   меняется, локальный результат мержа снимается тем же путём, что прочие
   отказы гейта мержа); текст называет файлы и нарушения. Предупреждения
   guard мерж не останавливают.
2. `pin-update <sha>`: кроме зелёной канарейки требуется зелёный CI
   этого коммита в origin (все проверки завершены и успешны). CI красный —
   именованный отказ с названиями упавших проверок; CI ещё идёт или `gh`
   не ответил — именованный отказ «CI не подтверждён» (не молчаливый
   пропуск). Аварийный откат `pin --to` (ADR-0013) эту сверку не получает.
3. `doctor`: строка о CI головы origin/main — `ok` при зелёном, `fail`
   при красном с коммитом и именами упавших проверок, `warn` при идущем
   прогоне или недоступном `gh`.
4. После мержа — CI main. `approve` на `merge_gate` после push мержа ждёт
   CI нового коммита головы main (тем же ожиданием, что `verifying`, с
   пределом времени — именованная константа) и пишет итог в журнал задачи
   и в вывод: зелёный / красный с именами упавших проверок / не дождался.
   Пока CI головы origin/main красный, следующий `approve` на `merge_gate`
   любой задачи отказывает именованно («main красный с <коммит> — сначала
   починить main»). Исключение — задача, названная Оператором как
   исправление main: флаг `approve <id> <sha> --fixes-main "<основание>"`
   пишет основание в журнал и снимает только эту сверку.
5. Тесты в `tests/`: мерж, чей снимок нарушает guard `--all`, отказывает
   до push («Ловит мутацию: мерж без guard после снимка»); мерж с чистым
   снимком проходит как прежде; `pin-update` отказывает на красном и на
   неподтверждённом CI и проходит на зелёном; `pin --to` не сверяет CI;
   три исхода строки `doctor`; ожидание CI main после мержа (зелёный,
   красный, не дождался) и отказ следующего мержа при красном main,
   `--fixes-main` снимает отказ с записью основания. Существующие тесты гейта мержа, `pin` и
   `doctor` не удаляются и не ослабляются.

Зоны: orchestrator/fsm_merge_gate.py, orchestrator/pin.py, orchestrator/ci.py, orchestrator/doctor/, orchestrator/fsm.py (разбор аргументов approve), orchestrator/artel.py (диспетчер), tests/.

Только чтение (не менять): scripts/guard.py, orchestrator/canary.py,
orchestrator/canary_drive.py, orchestrator/store.py,
orchestrator/fsm_advance.py, orchestrator/config.py, .github/, skills/,
templates/, docs/adr/, docs/invariants.md, tests/test_invariants.py,
docs/backlog.md, docs/operator-session.md, tasks/.

Не входит: смена режимов guard на ветке задачи; README в
`acceptance_tests/` (скил test_author — отдельная задача); задача без
коммитов кода в `verifying`.

Рамка: $40.
