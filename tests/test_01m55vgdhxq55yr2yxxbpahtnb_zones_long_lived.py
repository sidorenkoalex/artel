"""Гейт зон выхода из `in_dev` и собственные долгоживущие файлы задачи
внешнего проекта по профилю тестов.

Группа: долгоживущий
Красен до реализации: гейт зон у задачи внешнего проекта не признаёт зоной ничего сверх заявленных зон — свой долгоживущий файл `backend/tests/test_<id>_<имя>.py` отказывается как «вне заявленных zones» (AC-2), а текст отказа при непрочитанном профиле причину отказа профиля не называет (AC-5); методы AC-1, AC-3, AC-4, AC-6, AC-7, AC-8 держат сегодняшнее поведение и зелёные с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): корень — клон
артели с bare `origin`; внешний проект — свой клон с bare `origin`
(`tests.sandbox.make_project_repo`). `targets.yaml` песочницы пишется
сценарием: запись внешнего проекта — с профилем тестов
`long_lived_dir: backend/tests` либо без поля `test_profile`, запись артели —
с профилем (каталог долгоживущих файлов — по сценарию) либо со сломанным
профилем.

Каждый сценарий — своя задача в `in_dev` с зонами в БД, своя рабочая копия
(`workspace.ensure`), код задачи закоммичен в ветку задачи, PLAN.md `ready` и
SPEC.md — в ссылке документов автокоммитом шага
(`checkpoint.commit_step_artifacts`). Переход — `fsm.cmd_advance`;
наблюдаются новые записи журнала задачи и вывод команды (подсказку отказа
гейт печатает строкой «  дальше: …», в журнал она не пишется). Связка,
которую держит файл: «команда advance — гейт зон — профиль тестов проекта из
targets.yaml — дифф ветки задачи в git».

Провалидировано временным стабом реализации (удалён, не закоммичен): у
внешнего проекта пути вне зон, для которых `Profile.is_long_lived` профиля
из `project_profile.decide` истинно, признаются зоной, а причина
`Decision.refusal` дописывается в detail отказа — все методы зелёные.

Имена файлов, слова в именах и id задач — случайные при каждом запуске;
зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import (checkpoint, config, fsm, github_adapter, idgen,
                          repo_context, store, workspace)
from tests.sandbox import RealGitSandbox, make_project_repo

ARTEL = config.DEFAULT_TARGET
EXT = "vneshll"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

ZONES_ACTION = "переход отклонён: гейт зон"
EXT_LL_DIR = "backend/tests"
EXT_ZONE = "backend/src/"
NAME_TEMPLATE = "test_<id>_<name>.py"

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: {directory}
      long_lived_name: {name}
      weakening_scope: [{directory}/**/*.py]
      mutation_claim_scope: [{directory}/test_*.py]
"""

# Профиль без обязательного подполя `long_lived_name` — `targets.check`
# отвергает запись, профиль «не прочитан».
BROKEN_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: фикстура гейта зон

## Подход
Фикстура сценария.

## Шаги
1. Правка.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура гейта зон

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""

# Прежние тексты отказа гейта зон «вне зон» (до правки задачи): detail —
# формула с базой сравнения и её источником, hint — дословно.
DETAIL_RE = (r"дифф трогает файлы вне заявленных zones и COMMON_ZONES "
             r"\(база сравнения [0-9a-f]{{7,40}} от [^()]+\): {paths}")
HINT = ("сократи дифф до заявленных zones либо оформи раздел "
        "«## Расширение зон» в PLAN.md с обоснованием и мандатом "
        "Оператора («Расширение зон разрешено: <пути>» в ANSWER-n.md), и "
        "повтори artel.py advance {task}")


class ZonesLongLivedSandbox(RealGitSandbox):
    """Клон артели и клон внешнего проекта; задачи в `in_dev`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        # Draft MR — обращение к форджу, которого у песочницы нет.
        for patcher in (mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                        mock.patch.object(github_adapter, "ensure_draft_mr",
                                          lambda conn, task_id, t: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.add_synced_origin()
        self.ext_clone = make_project_repo(EXT)
        self.conn = store.db()

    # ---------------------------------------------------------------- входы

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def own_long_lived(self, task_id: str, directory: str,
                       suffix: str = ".py") -> str:
        """Путь файла по шаблону `test_<id>_<имя>.py` в `directory` с id
        задачи `task_id` (суффикс — по сценарию)."""
        return f"{directory}/test_{task_id.lower()}_{self.word()}{suffix}"

    # -------------------------------------------------------- targets.yaml

    def write_targets(self, *, ext_profile: bool = True,
                      artel_profile: str | None = None) -> None:
        """`targets.yaml` песочницы: артель — с `artel_profile` (по
        умолчанию профиль с каталогом `tests`), внешний проект — с профилем
        `long_lived_dir: backend/tests` либо без поля `test_profile`."""
        if artel_profile is None:
            artel_profile = PROFILE.format(directory="tests", name=NAME_TEMPLATE)
        text = "targets:\n" + TARGET_ENTRY.format(
            name=ARTEL, url="http://localhost/artel", base=config.MAIN_BRANCH,
            no_paths=", ".join(config.PROTECTED_PATHS))
        text += artel_profile
        text += TARGET_ENTRY.format(
            name=EXT, url=f"file:///nonexistent/{EXT}",
            base=config.MAIN_BRANCH, no_paths=f"zn{self.word()}/")
        if ext_profile:
            text += PROFILE.format(directory=EXT_LL_DIR, name=NAME_TEMPLATE)
        config.TARGETS.write_text(text, encoding="utf-8")

    # ------------------------------------------------------- задача и ветка

    def new_task(self, target: str, zones: list[str]) -> str:
        """Задача `target` в `in_dev` с зонами `zones`, рабочей копией,
        PLAN.md и SPEC.md в ссылке документов; кода ещё нет."""
        task_id = idgen.new_task_id()
        branch = f"task/{task_id.lower()}-zones"
        store.insert_task(self.conn, task_id, f"Фикстура {self.word()}",
                          "in_dev", branch, target, config.DEFAULT_BUDGET_USD)
        store.update_task(self.conn, task_id, zones=", ".join(zones))
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.explain(f"рабочая копия не заведена: {error}"))
        docs = config.PROJECTS / target / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "PLAN.md").write_text(PLAN_TEXT.format(task=task_id),
                                      encoding="utf-8")
        (docs / "SPEC.md").write_text(SPEC_TEXT.format(task=task_id),
                                      encoding="utf-8")
        checkpoint.commit_step_artifacts(self.conn, task_id, "developer")
        return task_id

    def commit_code(self, task_id: str, paths: list[str]) -> None:
        """Файлы `paths` закоммичены в ветку задачи её рабочей копии."""
        wt = workspace.path(task_id)
        for rel in paths:
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"V = '{self.word()}'\n", encoding="utf-8")
        self.git("-C", str(wt), "add", "-A")
        self.git("-C", str(wt), "commit", "-q", "-m", f"{task_id}: код задачи")

    def common_zone_path(self) -> str:
        """Путь под случайной записью `config.COMMON_ZONES`, не защищённый
        у артели."""
        while True:
            entry = self.rng.choice(config.COMMON_ZONES)
            rel = (f"{entry}test_{self.word()}.py" if entry.endswith("/")
                   else entry)
            if not config.is_protected_path(rel):
                return rel

    def ext_code(self) -> str:
        return f"{EXT_ZONE}{self.word()}.py"

    # ------------------------------------------------------------- переход

    def advance(self, task_id: str) -> tuple[list[dict], str]:
        """(новые записи журнала задачи, вывод `advance`)."""
        rows = store.task_steps(self.conn, task_id)
        before = rows[-1]["id"] if rows else 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_advance(task_id)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        new_rows = [dict(r) for r in store.task_steps(self.conn, task_id)
                    if r["id"] > before]
        return new_rows, buf.getvalue()

    @staticmethod
    def zone_refusals(rows: list[dict]) -> list[dict]:
        """Записи отказа гейта зон — любой его формулировки."""
        return [r for r in rows if r["action"].startswith(ZONES_ACTION)]

    @staticmethod
    def hints(out: str) -> list[str]:
        return [line[len("  дальше: "):] for line in out.splitlines()
                if line.startswith("  дальше: ")]

    @staticmethod
    def text_of(rows: list[dict], out: str) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in rows) + "\n--- вывод:\n" + out

    def scenario(self, target: str, zones: list[str], paths: list[str],
                 task_id: str | None = None) -> tuple[str, list[dict], str]:
        task_id = task_id or self.new_task(target, zones)
        self.commit_code(task_id, paths)
        rows, out = self.advance(task_id)
        return task_id, rows, out

    def assert_no_zone_refusal(self, rows, out, label: str) -> None:
        self.assertEqual(self.zone_refusals(rows), [], self.explain(
            f"{label}: гейт зон отказал: {self.text_of(rows, out)}"))

    def assert_out_of_zone_refusal(self, task_id: str, rows, out, rel: str,
                                   label: str) -> dict:
        """Ровно прежний отказ «вне зон», называющий `rel`; запись журнала."""
        note = self.explain(f"{label} ({rel}): {self.text_of(rows, out)}")
        refusals = self.zone_refusals(rows)
        self.assertEqual(len(refusals), 1, note)
        self.assertEqual(refusals[0]["action"], ZONES_ACTION, note)
        self.assertIn(rel, refusals[0]["detail"], note)
        return refusals[0]

    def assert_prior_texts(self, task_id: str, refusal: dict, out: str,
                           rel: str, label: str) -> None:
        """detail и hint отказа — прежние тексты байт-в-байт по формуле."""
        note = self.explain(f"{label} ({rel}): {refusal['detail']}\n{out}")
        self.assertRegex(refusal["detail"],
                         "^" + DETAIL_RE.format(paths=re.escape(rel)) + "$", note)
        self.assertIn(HINT.format(task=task_id), self.hints(out), note)


class ArtelUnchangedTest(ZonesLongLivedSandbox):

    def test_ac1_artel_zones_gate_texts_unchanged(self):
        """Задача артели: общие зоны пропускаются, путь вне зон и общих зон отказывается прежним текстом.

        Сценарий: профиль артели в `targets.yaml` объявляет каталог
        долгоживущих файлов `zl<слово>` (вне `config.COMMON_ZONES`). Задачи
        артели с зоной `pk<слово>/`: (а) файл под случайной записью
        `config.COMMON_ZONES` и (б) свой долгоживущий файл
        `tests/test_<id>_<имя>.py` — отказа гейта зон нет; (в) посторонний
        файл `zs<слово>/<имя>.py` и (г) файл по шаблону профиля артели с id
        задачи в каталоге `zl<слово>` — ровно одна запись «переход отклонён:
        гейт зон», detail — прежняя формула с базой сравнения и единственным
        путём, подсказка — прежний текст дословно.

        Ловит мутацию: расширение зоны по профилю применено и к артели —
        файл (г) проходит гейт без отказа; к detail или hint отказа
        приписан новый текст (о профиле, о долгоживущих файлах) — сверка с
        прежней формулой падает; общие зоны у артели заменены зоной
        профиля — файл (а) вне `tests/` отказывает.
        """
        ll_dir = f"zl{self.word()}"
        self.write_targets(artel_profile=PROFILE.format(directory=ll_dir,
                                                        name=NAME_TEMPLATE))
        for _ in range(2):
            zone = f"pk{self.word()}/"
            code = f"{zone}{self.word()}.py"
            common = self.common_zone_path()
            with self.subTest(case="общая зона", path=common):
                _, rows, out = self.scenario(ARTEL, [zone], [code, common])
                self.assert_no_zone_refusal(rows, out, "общая зона")

            task = self.new_task(ARTEL, [zone])
            own = self.own_long_lived(task, "tests")
            with self.subTest(case="свой файл tests/", path=own):
                _, rows, out = self.scenario(ARTEL, [zone], [code, own], task)
                self.assert_no_zone_refusal(rows, out, "свой файл tests/")

            stray = f"zs{self.word()}/{self.word()}.py"
            with self.subTest(case="вне зон", path=stray):
                task, rows, out = self.scenario(ARTEL, [zone], [code, stray])
                refusal = self.assert_out_of_zone_refusal(task, rows, out, stray,
                                                          "вне зон")
                self.assert_prior_texts(task, refusal, out, stray, "вне зон")

            task = self.new_task(ARTEL, [zone])
            by_profile = self.own_long_lived(task, ll_dir)
            with self.subTest(case="файл по профилю артели", path=by_profile):
                _, rows, out = self.scenario(ARTEL, [zone], [code, by_profile], task)
                refusal = self.assert_out_of_zone_refusal(
                    task, rows, out, by_profile, "файл по профилю артели")
                self.assert_prior_texts(task, refusal, out, by_profile,
                                        "файл по профилю артели")

    def test_ac8_artel_unread_profile_texts_unchanged(self):
        """Профиль артели не прочитан: исход и тексты гейта зон прежние, причина отказа профиля в них не попадает.

        Сценарий: запись артели в `targets.yaml` несёт `test_profile` без
        подполя `long_lived_name` — определение профиля отказывает. Задачи
        артели с зоной `pk<слово>/`: файл под `config.COMMON_ZONES` и свой
        `tests/test_<id>_<имя>.py` — отказа гейта зон нет; посторонний
        файл `zs<слово>/<имя>.py` — ровно одна запись «переход отклонён:
        гейт зон» с прежней формулой detail и прежней подсказкой дословно;
        ни detail, ни подсказка не упоминают `test_profile` и «не прочитан».

        Ловит мутацию: причина отказа профиля добавлена в текст отказа гейта
        зон для любого проекта, а не только внешнего — detail или
        подсказка у артели несут «профиль тестов проекта … не прочитан»;
        отказ профиля у артели превращён в отказ гейта зон — файл под
        общей зоной отказывает.
        """
        self.write_targets(artel_profile=BROKEN_PROFILE)
        for _ in range(2):
            zone = f"pk{self.word()}/"
            code = f"{zone}{self.word()}.py"
            common = f"tests/test_{self.word()}.py"
            with self.subTest(case="общая зона", path=common):
                _, rows, out = self.scenario(ARTEL, [zone], [code, common])
                self.assert_no_zone_refusal(rows, out, "общая зона")

            task = self.new_task(ARTEL, [zone])
            own = self.own_long_lived(task, "tests")
            with self.subTest(case="свой файл tests/", path=own):
                _, rows, out = self.scenario(ARTEL, [zone], [code, own], task)
                self.assert_no_zone_refusal(rows, out, "свой файл tests/")

            stray = f"zs{self.word()}/{self.word()}.py"
            with self.subTest(case="вне зон", path=stray):
                task, rows, out = self.scenario(ARTEL, [zone], [code, stray])
                refusal = self.assert_out_of_zone_refusal(task, rows, out, stray,
                                                          "вне зон")
                self.assert_prior_texts(task, refusal, out, stray, "вне зон")
                texts = [refusal["detail"]] + self.hints(out)
                for marker in ("test_profile", "не прочитан"):
                    self.assertFalse(
                        any(marker in t for t in texts),
                        self.explain(f"«{marker}» в тексте гейта зон: {texts}"))


class ExternalProfileTest(ZonesLongLivedSandbox):

    def setUp(self):
        super().setUp()
        self.write_targets(ext_profile=True)

    def test_ac2_own_long_lived_file_is_in_zone(self):
        """Свой долгоживущий файл задачи внешнего проекта по профилю проходит гейт зон.

        Сценарий: внешний проект с профилем `long_lived_dir: backend/tests`,
        задачи с зонами `backend/src/` (без `backend/tests/`). Дифф —
        файл `backend/src/<слово>.py` и `backend/tests/test_<id>_<имя>.py`
        (id этой задачи в нижнем регистре, имя случайное), трижды с разными
        именами: ни одной записи отказа «переход отклонён: гейт зон».

        Ловит мутацию: расширение зоны по профилю не сделано или включено
        только для артели — свой файл отказывается как «вне заявленных
        zones»; профиль взят не того проекта (артели, каталог `tests`) —
        файл в `backend/tests` по-прежнему вне зон; id в шаблон
        подставлен в верхнем регистре — путь с id в нижнем регистре не
        признан своим.
        """
        for _ in range(3):
            task = self.new_task(EXT, [EXT_ZONE])
            own = self.own_long_lived(task, EXT_LL_DIR)
            with self.subTest(path=own):
                _, rows, out = self.scenario(EXT, [EXT_ZONE],
                                             [self.ext_code(), own], task)
                self.assert_no_zone_refusal(rows, out, "свой долгоживущий файл")

    def test_ac3_other_file_of_long_lived_dir_refused(self):
        """Файл каталога долгоживущих тестов без id задачи отказывается гейтом зон.

        Сценарий: тот же проект и зоны `backend/src/`; дифф — файл кода и
        `backend/tests/test_<слово>.py` (без id задачи), дважды: отказ
        «переход отклонён: гейт зон», detail называет этот файл.

        Ловит мутацию: зона расширена всем каталогом `long_lived_dir`
        (префикс `backend/tests/`) вместо шаблона с id задачи — файл без id
        проходит без отказа.
        """
        for _ in range(2):
            other = f"{EXT_LL_DIR}/test_{self.word()}.py"
            with self.subTest(path=other):
                task, rows, out = self.scenario(EXT, [EXT_ZONE],
                                                [self.ext_code(), other])
                self.assert_out_of_zone_refusal(task, rows, out, other,
                                                "файл без id задачи")

    def test_ac4_long_lived_file_of_other_task_refused(self):
        """Долгоживущий файл с id другой задачи отказывается гейтом зон.

        Сценарий: тот же проект и зоны `backend/src/`; дифф — файл кода и
        `backend/tests/test_<чужой id>_<имя>.py` (чужой id — свежий id из
        `idgen`), дважды: отказ «переход отклонён: гейт зон», detail
        называет этот файл.

        Ловит мутацию: шаблон сверяется без id задачи (любой
        `test_<что угодно>_<имя>.py`) либо по общей части id (первые знаки
        ULID — метка времени, у соседних задач совпадает) — чужой файл
        проходит без отказа.
        """
        for _ in range(2):
            task = self.new_task(EXT, [EXT_ZONE])
            foreign = self.own_long_lived(idgen.new_task_id(), EXT_LL_DIR)
            with self.subTest(path=foreign):
                _, rows, out = self.scenario(EXT, [EXT_ZONE],
                                             [self.ext_code(), foreign], task)
                self.assert_out_of_zone_refusal(task, rows, out, foreign,
                                                "файл чужой задачи")

    def test_ac7_prefix_without_template_match_refused(self):
        """Путь с префиксом своего файла, но не по шаблону имени, отказывается гейтом зон.

        Сценарий: тот же проект и зоны `backend/src/`; дифф — файл кода и
        `backend/tests/test_<id>_<имя>.json` (id этой задачи), дважды:
        отказ «переход отклонён: гейт зон», detail называет этот путь.

        Ловит мутацию: признание по префиксу `long_lived_prefix` (startswith)
        вместо полного совпадения `is_long_lived` — файл `.json` с префиксом
        своего файла проходит без отказа.
        """
        for _ in range(2):
            task = self.new_task(EXT, [EXT_ZONE])
            near = self.own_long_lived(task, EXT_LL_DIR, suffix=".json")
            with self.subTest(path=near):
                _, rows, out = self.scenario(EXT, [EXT_ZONE],
                                             [self.ext_code(), near], task)
                self.assert_out_of_zone_refusal(task, rows, out, near,
                                                "не по шаблону имени")


class ExternalProfileRefusalTest(ZonesLongLivedSandbox):

    def test_ac5_unread_profile_named_in_zones_refusal(self):
        """Профиль внешнего проекта не прочитан: зона не расширена, текст отказа называет причину отказа профиля.

        Сценарий: запись внешнего проекта в `targets.yaml` несёт профиль
        `long_lived_dir: backend/tests`, но ответ о профиле
        (`repo_context.profile_of`, источник `project_profile.decide`)
        подменён исходом «не прочитан» со случайной причиной; контекст
        проекта разрешён. Задача с зонами `backend/src/`, дифф — файл кода и
        свой `backend/tests/test_<id>_<имя>.py`: отказ «переход отклонён:
        гейт зон», detail называет этот файл, а detail или подсказка
        отказа содержат случайную причину отказа профиля. Дважды.

        Ловит мутацию: при отказе профиля гейт зон молча не расширяет зону
        и отдаёт прежний текст — причины отказа профиля в нём нет; при
        отказе профиля зона расширяется по каталогу и шаблону из записи
        `targets.yaml` в обход `decide` — свой файл проходит без отказа.
        """
        self.write_targets(ext_profile=True)
        real = repo_context.profile_of
        for _ in range(2):
            reason = f"zr{self.word()} подполе сломано {self.word()}"

            def unread(name, reason=reason):
                if name == EXT:
                    return repo_context.ProfileAnswer(
                        repo_context.PROFILE_UNREAD, reason=reason)
                return real(name)

            task = self.new_task(EXT, [EXT_ZONE])
            own = self.own_long_lived(task, EXT_LL_DIR)
            with self.subTest(path=own), \
                    mock.patch.object(repo_context, "profile_of", unread):
                _, rows, out = self.scenario(EXT, [EXT_ZONE],
                                             [self.ext_code(), own], task)
                refusal = self.assert_out_of_zone_refusal(
                    task, rows, out, own, "профиль не прочитан")
                texts = [refusal["detail"]] + self.hints(out)
                self.assertTrue(any(reason in t for t in texts), self.explain(
                    f"причина «{reason}» не названа: {texts}"))


class ExternalWithoutProfileTest(ZonesLongLivedSandbox):

    def test_ac6_no_profile_no_default_fallback(self):
        """Внешний проект без test_profile: файл по каталогу и шаблону по умолчанию отказывается гейтом зон.

        Сценарий: запись внешнего проекта без поля `test_profile`, задачи с
        зонами `backend/src/`; дифф — файл кода и `tests/test_<id>_<имя>.py`
        (id этой задачи), дважды: отказ «переход отклонён: гейт зон»,
        detail называет `tests/test_<id>_<имя>.py`.

        Ловит мутацию: у проекта без профиля (`Decision.skip`) гейт зон
        берёт каталог и шаблон по умолчанию (`tests`, артельный шаблон) —
        файл проходит без отказа.
        """
        self.write_targets(ext_profile=False)
        for _ in range(2):
            task = self.new_task(EXT, [EXT_ZONE])
            own = self.own_long_lived(task, "tests")
            with self.subTest(path=own):
                _, rows, out = self.scenario(EXT, [EXT_ZONE],
                                             [self.ext_code(), own], task)
                self.assert_out_of_zone_refusal(task, rows, out, own,
                                                "без профиля")


if __name__ == "__main__":
    unittest.main()
