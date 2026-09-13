"""Семейство гейтов вокруг вердикта ревьювера — `_review_escalation_sha_gate`,
`_mutation_claim_gate`, `_review_rework_gate` и их помощники дат/sha (SPEC
01M2CYQR0357VAQFZ5VACJD9TD, требование 1) — перенесено дословно из
`orchestrator/fsm_advance.py`."""
from datetime import datetime, timezone

from scripts import guard

from .. import auto, budget, config, gitcmd, store, yamlmini
from ._base import GateRefusal, _run_gates


def _code_sha_at_review_escalation(conn, task_id: str) -> str | None:
    """sha кода, зафиксированный `budget.enforce_budget` в момент
    ПОСЛЕДНЕЙ эскалации ПО БЮДЖЕТУ из `review` (SPEC
    01M1VBEDGMEXHVGWAH42FTDZ4X, требование 3, `budget.
    REVIEW_ESCALATION_CODE_SHA_ACTION`) — `None`, если такой записи нет
    вовсе, либо она относится к ПРЕДЫДУЩЕМУ циклу ревью (запись СТАРШЕ
    последнего `"agent run finished"` роли `reviewer` — новый прогон
    reviewer уже перекрыл её собой, сверять с ней текущий вердикт нельзя,
    тот же приём отсечки, что и у `auto._role_step_since_state_entry`)."""
    rows = store.task_steps(conn, task_id)
    last_reviewer_run = None
    last_escalation_sha = None
    for i, row in enumerate(rows):
        if row["actor"] == "reviewer" and row["action"] == "agent run finished":
            last_reviewer_run = i
        if row["action"] == budget.REVIEW_ESCALATION_CODE_SHA_ACTION:
            last_escalation_sha = (i, row["detail"])
    if last_escalation_sha is None:
        return None
    idx, sha = last_escalation_sha
    if last_reviewer_run is not None and last_reviewer_run >= idx:
        return None
    return sha or None


def _review_escalation_sha_gate(conn, task_id: str, t) -> GateRefusal | None:
    """Требование 3 (SPEC 01M1VBEDGMEXHVGWAH42FTDZ4X): budget-эскалация,
    поймавшая уже вынесенный approved-вердикт reviewer (эскалация ИЗ
    `review`), не должна пропускать переход в `acceptance` по устаревшему
    вердикту, если код кодовой ветки СМЕНИЛСЯ, пока задача стояла
    `escalated` — нужен новый прогон reviewer.

    Отметки эскалации нет вовсе (обычный approved без эскалации по
    бюджету, либо она относится к предыдущему циклу ревью,
    `_code_sha_at_review_escalation`), текущий `gitcmd.branch_head_sha`
    не ответил, либо совпадает с зафиксированным — гейт пропускает
    (fail-open, тот же принцип, что и у `_review_rework_gate` рядом:
    неотвеченный git не значит «код сменился», значит «сверить нечем»)."""
    escalation_sha = _code_sha_at_review_escalation(conn, task_id)
    if escalation_sha is None:
        return None
    current_sha = gitcmd.branch_head_sha(t["branch"])
    if not current_sha or current_sha == escalation_sha:
        return None
    detail = (f"код кодовой ветки сменился, пока задача стояла escalated "
             f"по бюджету: на момент вердикта reviewer было "
             f"{escalation_sha}, сейчас {current_sha} — вердикт относится "
             f"к уже неактуальному коду")
    hint = f"новый прогон reviewer, затем artel.py advance {task_id}"
    return GateRefusal("переход отклонён: код сменился после вердикта",
                       detail, hint)


# Именованная причина отказа (требование 4) — общий текст с
# `orchestrator/auto.py::REWORK_REFUSAL_ACTION` (второй, независимый
# рубеж того же класса регрессии).
_REWORK_REFUSAL_ACTION = "переход отклонён: замечания ревью не отработаны"

# Префикс сообщения автослияния «подтяжка main» на КОДОВОЙ ветке задачи
# (`fsm._pull_main_or_escalate`/`fsm._auto_resolve_map_conflict`:
# `f"{task_id}: подтяжка {source_branch}"`) — единственный вид коммита на
# кодовой ветке, не являющийся работой developer'а (SPEC «Контекст»:
# именно подтяжка была ЕДИНСТВЕННЫМ, что двигало кодовую ветку между
# итерациями в реальном инциденте регрессии №12/№13) — гейт ниже обязан
# его игнорировать, иначе рутинная подтяжка main маскировала бы
# неотработанные замечания под настоящий шаг developer.
_PULL_MAIN_COMMIT_INFIX = ": подтяжка "


def _commit_iso_date(ref: str, *path: str):
    """Дата последнего коммита `ref` (committer, `%cI`), затрагивающего
    `path` (без него — голова `ref`) — `datetime` с часовым поясом; `None`
    — git не ответил, коммитов нет, либо строка не разбирается как ISO8601
    (лёгкие песочницы без настоящего git — `fake_git`/заглушки, тот же
    вырожденный случай деградации, что и у `fsm._pull_main_or_escalate`)."""
    args = ["log", "-1", "--format=%cI", ref]
    if path:
        args += ["--", *path]
    res = gitcmd.git(*args)
    if res is None or res.returncode != 0:
        return None
    line = res.stdout.strip()
    if not line:
        return None
    try:
        return datetime.fromisoformat(line)
    except ValueError:
        return None


def _latest_developer_commit_iso_date(branch: str, task_id: str):
    """Дата последнего коммита КОДОВОЙ ветки `branch`, который НЕ является
    автослиянием «подтяжка main» (`_PULL_MAIN_COMMIT_INFIX`) — иначе гейт
    принял бы рутинную подтяжку main за настоящий шаг developer (см.
    докстринг `_PULL_MAIN_COMMIT_INFIX`). `None` — git не ответил, либо на
    ветке нет ни одного коммита, кроме подтяжек."""
    res = gitcmd.git("log", "--format=%cI\x1f%s", branch)
    if res is None or res.returncode != 0:
        return None
    prefix = f"{task_id}{_PULL_MAIN_COMMIT_INFIX}"
    for line in res.stdout.splitlines():
        ts, sep, subject = line.partition("\x1f")
        if not sep or subject.startswith(prefix):
            continue
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            continue
    return None


# Префикс сообщения автокоммита артефактов шага ИМЕННО `reviewer` (сужение
# `_STEP_ARTIFACTS_COMMIT_PREFIX` до конкретной роли, checkpoint.py::
# _commit_external_step_artifacts::own_commit_marker) — единственный
# текстовый признак, которым коммит REVIEW.md, несущий вердикт ревьювера,
# отличим от более позднего автокоммита артефактов шага DEVELOPER,
# тронувшего тот же файл (правка леджера замечаний, T100) — регрессия №15,
# «Контекст» SPEC 01M1SCQ6WZHMQVK1AHP9F392JZ.
_REVIEWER_STEP_AUTOCOMMIT_PREFIX = "{task_id}: артефакты шага reviewer (автокоммит оркестратора"


def _reviewer_verdict_baseline(conn, task_id: str, branch: str):
    """(момент вердикта ревьювера текущей итерации, источник) — опорное
    время рубежа `_review_rework_gate_refuses` (регрессия №15, требование
    1, AC-1): САМЫЙ СВЕЖИЙ коммит `REVIEW.md`, чьё сообщение — автокоммит
    артефактов шага именно `reviewer` (`_REVIEWER_STEP_AUTOCOMMIT_PREFIX`),
    а не любой более поздний коммит того же файла. Автокоммит шага
    developer (правка леджера замечаний, T100) несёт в сообщении другую
    роль и этим фильтром не проходит, даже будучи самым свежим коммитом
    REVIEW.md — этим закрывается AC-2.

    Такого коммита нет вовсе (REVIEW.md правился в обход checkpoint.py —
    вручную Оператором, либо лёгкая песочница без настоящего git) —
    fallback на последнюю по времени запись журнала `agent run finished`
    роли `reviewer` (вторая часть требования 1): её момент — тот же
    реальный вердикт, просто без git-подписи.

    `(None, None)` — ни коммита, ни записи журнала: гейту сверять не с
    чем, та же деградация, что у `_commit_iso_date`."""
    path = f"tasks/{task_id}/REVIEW.md"
    prefix = _REVIEWER_STEP_AUTOCOMMIT_PREFIX.format(task_id=task_id)
    res = gitcmd.git("log", "--format=%cI\x1f%s", branch, "--", path)
    if res is not None and res.returncode == 0:
        for line in res.stdout.splitlines():
            ts, sep, subject = line.partition("\x1f")
            if not sep or not subject.startswith(prefix):
                continue
            try:
                return datetime.fromisoformat(ts), "автокоммит шага reviewer"
            except ValueError:
                continue
    for row in reversed(store.task_steps(conn, task_id)):
        if row["actor"] == "reviewer" and row["action"] == "agent run finished":
            try:
                ts = datetime.strptime(row["ts"], "%Y-%m-%d %H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                continue
            return ts, "запись журнала agent run finished роли reviewer"
    return None, None


def _mutation_claim_gate(conn, task_id: str, t, branch: str) -> GateRefusal | None:
    """Заявка «Ловит мутацию: …» для новых/изменённых тестов `tests/` на
    `in_dev -> verifying` (SPEC 01M29A0F88P9GKSXFW90F99H2N, требования
    1-4): шесть задач 11.09 получили от ревьювера один и тот же major на
    ЭТО правило (`skills/test-authoring.md`) без единой правки кода —
    круг ревью и CI стоил дороже самой проверки. Рубеж по образцу
    `_zones_gate` выше — та же база сравнения, то же чтение содержимого
    файлов через git, тот же приём отказа на сбое git (fail-closed,
    ADR-0002), не пропуск перехода молча.

    Внешний (не self) target и канареечная задача — гейт не проверяется,
    тем же условием, что `_origin_push_gate` (требование 3/AC-8): дифф в
    `config.ROOT` не видит код внешнего target, а канареечный `verifying`
    не ждёт CI и не читает origin — сверка тестов ветки здесь так же не
    имеет смысла.
    """
    if t["is_canary"] or t["target"] != config.DEFAULT_TARGET:
        return None
    base = gitcmd.diff_base(branch)
    if base is None:
        detail = (f"гейт заявки мутации: git не ответил на определение базы "
                 f"сравнения (merge-base с origin/{config.MAIN_BRANCH} либо "
                 f"локальным {config.MAIN_BRANCH}) для ветки {branch} — "
                 f"сверка заявки мутации невозможна")
        hint = (f"разберись, почему git не отвечает на merge-base "
               f"для {branch}, и повтори artel.py advance {task_id}")
        return GateRefusal("переход отклонён: гейт заявки мутации", detail, hint)
    files = gitcmd.diff_names(base, branch)
    if files is None:
        detail = (f"гейт заявки мутации: git не ответил на список файлов "
                 f"диффа (база {base}...{branch}) — сверка заявки мутации "
                 f"невозможна")
        hint = (f"разберись, почему git не отвечает на diff "
               f"{base}...{branch}, и повтори artel.py advance {task_id}")
        return GateRefusal("переход отклонён: гейт заявки мутации", detail, hint)

    # Только tests/test_*.py на верхнем уровне каталога (AC-5) — тот же
    # шаблон путей, что и остальные проверки заявок в acceptance_tests/
    # (guard.scan_redness_markers).
    test_files = [f for f in files
                 if f.startswith("tests/test_") and f.endswith(".py")
                 and f.count("/") == 1]

    per_file: list[str] = []
    for path in test_files:
        head_source, head_reason = gitcmd.show(branch, path)
        if head_source is None:
            # `gitcmd.show` возвращает `None` и на легитимное отсутствие
            # пути в HEAD (файл удалён — требование 2), и на сбой самого
            # git на существующем пути (R1-F2, REVIEW.md итерация 1/3):
            # различать эти два случая по ТЕКСТУ причины `gitcmd.show`
            # недостаточно — есть третий класс сбоя (повреждённый объект,
            # недоступный blob, гонка со сборкой мусора), не совпадающий
            # ни с «git не ответил», ни с `UnicodeDecodeError`, который
            # молча трактовался бы как удаление. Источник истины —
            # `gitcmd.ls_tree_files(branch, "tests")`: путь есть в дереве
            # HEAD — это сбой чтения независимо от текста причины; путь
            # реально отсутствует — легитимное удаление (требование 2).
            tree = gitcmd.ls_tree_files(branch, "tests")
            if tree is not None:
                is_failure = path in tree
            else:
                # git не ответил и на эту проверку — permissive-фоллбэк на
                # прежнее поведение (два уже известных класса причины);
                # это уже двойной сбой git на одном пути, дальше сужать
                # незачем — есть отдельный fail-closed рубеж выше на сбой
                # `diff_base`/`diff_names` для случая полной неотвечаемости.
                is_failure = (head_reason == "git не ответил"
                             or head_reason.startswith("не прочитан:"))
            if is_failure:
                detail = (f"гейт заявки мутации: git не ответил на чтение "
                         f"{path} из {branch} ({head_reason}) — сверка "
                         f"заявки мутации для этого файла невозможна")
                hint = (f"разберись, почему git не отвечает на show "
                       f"{branch}:{path}, и повтори artel.py advance "
                       f"{task_id}")
                return GateRefusal("переход отклонён: гейт заявки мутации",
                                  detail, hint)
            # Файл легитимно удалён в HEAD — заявку мутации сравнивать не
            # с чем, пропускаем (требование 2).
            continue
        base_source, _ = gitcmd.show(base, path)
        missing = guard.test_functions_without_mutation_claim(
            base_source, head_source)
        if missing:
            per_file.append(f"{path}: {', '.join(missing)}")
    if not per_file:
        return None
    detail = (f"{'; '.join(per_file)} — каждый новый или изменённый тест в "
             f"tests/ несёт в докстринге строку «Ловит мутацию: <что "
             f"сломали — и тест покраснеет>» (skills/test-authoring.md)")
    hint = f"допиши заявку и повтори artel.py advance {task_id}"
    return GateRefusal("переход отклонён: гейт заявки мутации", detail, hint)


def _review_rework_gate(conn, task_id: str, t, branch: str) -> GateRefusal | None:
    """Гейт `in_dev -> review` (SPEC «регрессия №13» 01M1RHFRQ2C0P4A57XJJ1WZV8N,
    требование 3, AC-3/AC-4/AC-6/AC-7; SPEC «регрессия №15»
    01M1SCQ6WZHMQVK1AHP9F392JZ, требования 1-4): REVIEW.md текущей
    итерации ещё `changes_requested`, а после момента вердикта ревьювера
    (`_reviewer_verdict_baseline`, не любого более позднего коммита
    REVIEW.md) не было ни коммита developer в кодовой ветке, ни записи
    журнала `agent run finished` роли developer после входа в `in_dev`
    этого визита — переделка не отработана.

    Второе (журнальное) условие OR — ОБЩАЯ с `auto.py` функция
    `auto._role_step_since_state_entry` (регрессия №15, требование 2,
    AC-3/AC-4): не независимая копия критерия «был ли шаг developer после
    входа в состояние» — та же деградация на легитимный первый вход
    (ANSWER-3), что уже применяет журнальный гейт `auto.py`.

    `_role_step_since_state_entry` возвращает `(True, None)` и на
    легитимный первый вход, И на «записи `state -> in_dev` нет вовсе» —
    для `auto.py` оба вырожденных случая означают одно и то же: сверять
    нечем, не блокировать. Для ЭТОГО рубежа второй случай (`detail is
    None`) — не сигнал «шаг developer состоялся», а отсутствие
    журнальной информации вовсе, при уже посчитанном git-условии
    (`code_ts`/`review_ts` выше) — переиспользование функции целиком, но
    без слепого доверия её вырожденному «да» там, где есть более
    надёжный git-сигнал (планка регрессии №13 заводит задачу прямо в
    `in_dev` без единой записи журнала — ANSWER-3 повторной приёмки).

    Помимо журнального условия, рубеж по-прежнему независим от `auto.py`
    (по образцу `_capacity_gate_refuses` выше): держит и ручной `advance`
    Оператора, минуя цикл `auto`.

    Сверка git-условия — по ВРЕМЕНИ коммитов (`%cI`), не по sha и не по
    тексту: REVIEW.md живёт в АРТЕФАКТНОЙ ветке пульта, код — в ОТДЕЛЬНОЙ
    кодовой ветке (`artifact_source.resolve`, `foreign` всегда `True`),
    общего родителя у них нет — единственный осмысленный признак «после»
    здесь время, не sha.

    Внешний (не self) target — гейт не проверяется: тот же довод, что
    `_capacity_gate_refuses`/`_zones_gate_refuses` выше — `git log`/`show`
    в `config.ROOT` не видит код внешнего target.

    Git не ответил, дата не разобрана, REVIEW.md вовсе не существует, или
    на кодовой ветке нет ни одного коммита developer (легковесные
    песочницы без настоящего git — `fake_git`/`disk_backed_show`, первый
    вход задачи в `in_dev` до первого ревью) — гейт НЕ отказывает по
    git-условию (та же деградация, что у `fsm._pull_main_or_escalate`:
    «git не ответил -> "fresh"» — не найденный сигнал не значит «код не
    менялся», значит «сверить нечем»); журнальное условие OR при этом
    всё равно проверяется отдельно.

    `_reviewer_verdict_baseline` не нашла ни автокоммита шага reviewer,
    ни записи журнала (ANSWER-3, повторный отказ приёмки регрессии №13
    итерации 2: планка `01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests`
    коммитит REVIEW.md вне `checkpoint.py`, без журнальной записи роли
    reviewer вовсе) — опорное время не остаётся пустым (что открывало бы
    рубеж нараспашку, fail open): fallback на дату последнего коммита
    REVIEW.md (`_commit_iso_date`), тем же способом, каким рубеж сверял
    ДО этой задачи. Опора `_reviewer_verdict_baseline`, если она нашлась,
    по-прежнему приоритетна — этот fallback работает только на её
    `(None, None)`.
    """
    if store.task_target(conn, task_id) != config.DEFAULT_TARGET:
        return None
    review_text, _ = gitcmd.show(branch, f"tasks/{task_id}/REVIEW.md")
    if review_text is None:
        return None
    meta = yamlmini.frontmatter(review_text) or {}
    if meta.get("status") != "changes_requested":
        return None
    review_ts, baseline_source = _reviewer_verdict_baseline(conn, task_id, branch)
    if review_ts is None:
        review_ts = _commit_iso_date(branch, f"tasks/{task_id}/REVIEW.md")
        baseline_source = "последний коммит REVIEW.md"
    if review_ts is None:
        return None
    code_ts = _latest_developer_commit_iso_date(t["branch"], task_id)
    if code_ts is not None and code_ts > review_ts:
        return None
    ran, _detail = auto._role_step_since_state_entry(conn, task_id, "in_dev",
                                                      "developer")
    if ran and _detail is not None:
        return None
    code_ts_text = code_ts.isoformat() if code_ts is not None else "нет коммитов"
    detail = (f"замечания ревью не отработаны: нет шага developer после "
              f"итерации {meta.get('iteration', '—')} (опорное время "
              f"{review_ts.isoformat()} — {baseline_source}; последний "
              f"коммит developer {code_ts_text})")
    hint = (f"почини код (не спорь с ревью втихую) и повтори "
           f"artel.py advance {task_id}")
    return GateRefusal(_REWORK_REFUSAL_ACTION, detail, hint)


def _review_rework_gate_refuses(conn, task_id: str, t, branch: str) -> bool:
    """Сохранённая публичная обёртка (тесты
    `tests/test_fsm_review_rework_gate.py` зовут её напрямую и читают
    журнал/stdout) — тот же единственный гейт `_review_rework_gate`,
    применённый через каркас `_run_gates`."""
    return _run_gates(conn, task_id,
                      [lambda: _review_rework_gate(conn, task_id, t, branch)])
