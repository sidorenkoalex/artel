"""doctor: pre-flight, recovery-сверка, сироты, живой и офлайн-смоук CLI
(A3, tasks/T022/SPEC.md).

Один набор именованных чек-функций (`Check`), два потребителя:

- `runner.cmd_run` берёт `preflight_checks` — быстрые блокирующие проверки
  перед стартом шага (требование 2);
- команда `doctor` (`cmd_doctor`) прогоняет весь набор `all_checks`,
  включая дорогие (живой смоук CLI) и разовые (recovery-сверка, сироты).

Отсутствие токена роли, найденность CLI, свободное место на диске
и layout внешнего target'а — блокирующие (`status="fail"`) в preflight.
Git-идентичность тоже участвует в preflight (текст требования 2
перечисляет её среди «быстрых проверок») — предупреждением
(`"warn"`), не блоком: `runner.run_agent_once` уже проверяет её ещё раз
перед стартом процесса агента и журналит собственным предупреждением
(`agent env WARNING`) с существующим тестом на некритичность отказа
(`tests/test_multitarget.py`, `...identity_is_journalled_before_the_step`)
— превращать её в preflight в блок означало бы сломать тот тест без ADR
(принцип целостности). Двойная проверка (preflight + запуск агента) —
сознательно принятая избыточность ради видимости уже в preflight, а не
молчаливое исключение пункта требования. Она пропускается, если к этому
моменту preflight уже нашёл блокирующий провал (токен/CLI/диск) — шаг
всё равно не стартует, платить subprocess-вызовом `git config` за
дополнительную информацию не о чем не нужно (и, отдельно, ломает тесты,
проверяющие «при провале preflight не происходит вообще никаких
subprocess-вызовов», см. `preflight_checks`).

Версия CLI (требование 5) — часть per-step preflight (T037). Изначально
(T022) сюда не входила: живой прогон `claude --version` через
`subprocess.run` внутри `preflight_checks()` был реализован и прогнан
против полного набора тестов — 76 упавших тестов в 8+ файлах, все —
из-за того, что `subprocess.run` внутри порождает `Popen`, а десятки
существующих тестов подряд мокали `runner.subprocess.Popen` напрямую
(единый модульный объект `subprocess` на весь процесс — подмена ловила
любой Popen-вызов, включая посторонний). Оператор 25.08 сузил
требование 5 до одной проверки в `doctor` (SPEC.md tasks/T022 обновлён,
см. tasks/T022/PLAN.md «Риски»), а ревизию мокинга subprocess вынес
строкой беклога P3. T037 эту ревизию сделала: `runner.spawn_agent` —
отдельная от `subprocess.Popen` точка мокинга cli-вызова агента (по
образцу `gitcmd.git`/`keychain.token`), тесты переведены на её мокинг —
конфликт снят, сверка пина CLI вернулась в `preflight_checks()`.

Проверки, представляющие операционный инцидент, а не «шаг сейчас не
стартует» (recovery, сироты, давность бэкапа), заводят строку в
`alerts` (kind=incident) — так Оператор может её `alert-ack`. Точечные
блокировки шага (preflight fail) в alerts не дублируются: они уже видны
именованной причиной в журнале конкретной задачи.

Разрез на пакет (01M1TT9BPBRYMDXXEWVZSRG51V): разделы бывшего монолитного
`orchestrator/doctor.py` (1856 строк) разъехались по подмодулям этого
пакета — один раздел (граница комментария-разделителя) на файл, тело
функций не переписано, только перенесено. Этот файл (фасад) — ЕДИНСТВЕННОЕ
место, где коллаборанты (`alerts`, `artifact_branch`, `canary`, `ci`,
`coldstart`, `config`, `fixation`, `gitcmd`, `liveness`, `pool_seal`,
`projects`, `roles`, `runner`, `snapshot`, `spend`, `stack`, `store`,
`targets`, `workspace`, `zone_lock`, `subprocess`, `shutil`) импортируются напрямую — подмодули
их не импортируют (AC-9: сканирующий тест красит любой прямой
`import subprocess`/`import shutil`/`from orchestrator import gitcmd` в
подмодуле). Единый приём на весь пакет (AC-4): каждый подмодуль делает
`from orchestrator import doctor` у себя в шапке (это безопасно даже во
время инициализации самого пакета — Python регистрирует частично
собранный модуль в `sys.modules` до выполнения тела `__init__.py`, так
что подмодуль получает ссылку на объект, который к моменту первого
РЕАЛЬНОГО ВЫЗОВА любой функции уже полностью собран) и внутри тела
каждой функции читает коллаборанта через атрибут `doctor.<имя>` —
`doctor.config.ROOT`, `doctor.gitcmd.git(...)`, `doctor.subprocess.run(...)`
и т.д., а не через локально импортированное имя. Это же правило
применено и к ссылкам НА ДРУГИЕ разделы бывшего монолита (например,
`doctor.Check(...)`, `doctor._auto_ack_gone(...)`, `doctor.check_leases`
внутри `all_checks`) — единственный узел связывания подпакета сам с
собой снова этот фасад, а не граф прямых импортов между подмодулями.
Благодаря чтению в момент вызова `mock.patch.object(doctor, "gitcmd", ...)`
и аналогичные подмены продолжают работать как раньше — они переживают
разрез, потому что подмодуль всегда смотрит на ТЕКУЩИЙ атрибут фасада,
а не на объект, захваченный при загрузке.

Чисто вычислительные стандартные модули (`os`, `re`, `json`, `socket`,
`statistics`, `sys`, `tempfile`, `time`, `pathlib.Path`) в это правило не
попадают — их никто не подменяет в тестах, поэтому подмодули импортируют
их обычным образом, локально, где нужно.
"""
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path

from .. import (alerts, artifact_branch, canary, ci, coldstart, config,
                fixation, gitcmd, liveness, merge_lock, notes, pool_seal,
                projects, repo_context, roles, runner, snapshot, spend,
                stack, store, targets, workspace, zone_lock)

# status: "ok" | "warn" | "fail" | "skip" ("skip" — честный пропуск проверки,
# требование 9: сверка forge-политики без `gh`/сети — не провал и не ок).
Check = namedtuple("Check", "name status detail")

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
ISOLATION_MARKER = "АРТЕЛЬ-ИЗОЛЯЦИЯ-A3-МАРКЕР-НЕ-ДОЛЖЕН-ПРОСОЧИТЬСЯ"
ISOLATION_SMOKE_TARGET = "__doctor_isolation_smoke__"
LIVE_SMOKE_PROMPT = "Ответь одним словом: ок."
LIVE_SMOKE_TIMEOUT_SEC = 120
# Анти-race `check_leases` (SPEC 01M1G..., требование 5, AC-9): интервал
# между двумя снимками `liveness._pid_alive` одного и того же lease перед
# тем, как считать его мёртвым — тот же порядок величины, что уже
# использует `pause.TERMINATE_POLL_SEC` для опроса живости pid.
LEASE_DEAD_RECHECK_SEC = 0.05

from .preflight import (check_cli_found, cli_version, check_cli_version,
                        check_token, check_git_identity, check_disk_space,
                        _role_home_diff, check_role_home_reference,
                        check_target_layout, TARGET_WRAPPER_MARKERS,
                        check_target_wrapper, preflight_checks)
from .isolation import isolation_smoke
from .live_smoke import live_smoke, _live_smoke_run
from .recovery import recovery_check
from .auto_ack import (_BRANCH_ALERT_RE, _DIR_ALERT_RE, _WORKTREE_ALERT_RE,
                       _auto_ack_gone, _branch_alert_live, _dir_alert_live,
                       _worktree_alert_live)
from .orphans import _is_legit_task_worktree, _orphan_worktrees, check_orphans
from .canary_pool import (check_role_log_pool_leak, check_canary_pool_drift,
                          check_token_repo_scope, check_canary_trigger)
from .branch_freshness import check_branch_freshness
from .artifact_branches import (_artifact_branch_first_commit_parent,
                                check_artifact_branch_parent_ancestry,
                                _artifact_branch_candidates, _is_ancestor,
                                _sync_direction, check_artifact_branch_sync,
                                _ARTIFACT_BRANCH_CI_JSON_FIELDS,
                                _artifact_branch_ci_runs,
                                check_artifact_branch_ci)
from .lease_alerts import (_LEASE_ALERT_RE, _MERGE_LOCK_ALERT_RE,
                           _lease_alert_live, _merge_lock_alert_live)
from .leases import (_STEP_TERMINAL_ACTIONS, _ORPHAN_ACTION_MARKER,
                     _orphaned_start_step, _reconcile_orphaned_step,
                     _last_start_step, _lease_fail_detail, check_leases,
                     check_merge_lock, check_merge_queue)
from .hung_test_watchdog import (_HUNG_TEST_CMD_RE, _ETIME_RE,
                                 _etime_to_seconds, _running_processes,
                                 _process_cwd, _hung_test_run_task_id,
                                 _hung_test_run_task_lease_alive,
                                 _find_hung_test_runs, _HUNG_TEST_ALERT_RE,
                                 _hung_test_run_alert_live,
                                 check_hung_test_runs, _fix_hung_test_runs,
                                 _fix_dead_lease_groups, check_zone_waits)
from .misc_checks import (check_backup_age, check_pending_notes,
                          check_task_counters, check_pending_snapshots,
                          check_remote_empty, check_base_branch)
from .root_pin import (check_root_pin, fetch_origin_main_sha,
                       unpushed_commits, check_pin_unpushed)
from .orphan_branches import (ORPHAN_ARTIFACT_BRANCH_SOURCE,
                              _REMOTE_ARTIFACT_GLOB, _UNSET,
                              _remote_artifact_branch_names,
                              _orphan_artifact_branches,
                              sweep_orphan_artifact_branches,
                              _print_orphan_branch_candidates)
from .ignored_artifacts import _fix_ignored_artifact_files
from .map_growth import (MAP_SIZE_ACTION, MAP_GROWTH_SOURCE, _FAR_FUTURE_TS,
                         _all_map_size_steps, _map_growth_reference_point,
                         _map_growth_series, _map_growth_message,
                         _map_growth_check, check_map_growth)
from .cli import all_checks, LABELS, cmd_doctor, cmd_alert_ack
