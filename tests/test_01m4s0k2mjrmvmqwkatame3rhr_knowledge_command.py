"""Команда `knowledge <id> <запрос>`: белый список роли, выдача карточек,
граница недоверенных данных, отказ вида, неизменность состояния, журнал
обращений, его предел и очередь при БД без права записи.

Связка «команда — БД — git — диск»: песочница — настоящий git-репозиторий
пульта (`RealGitSandbox`) с системным файлом `knowledge/system.yaml` и
проектным файлом артели `knowledge/artel.yaml` в голове `main`, временный
`targets.yaml` с полем `knowledge` у артели и двух внешних проектов, файлы
карточек внешних проектов — на диске их области. Команда зовётся через
диспетчер `artel.main()` тем же argv, что из шага роли; окружение роли —
`ARTEL_ROLE`/`ARTEL_TASK`/`HOME` на время вызова. Ключи и тексты карточек,
запросы и роли порождаются при каждом запуске от зерна (печатается).

Группа: долгоживущий
Красен до реализации: модуля orchestrator.knowledge_cards и команды knowledge в диспетчере artel.py ещё нет — импорт модуля теста падает ImportError.
"""
import contextlib
import io
import json
import os
import random
import re
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, artel, brief, config, knowledge_cards,
                          roles, store, suite_lock, watch, workspace)
from tests.sandbox import RealGitSandbox, artel_target_entry

EXT = "extproj"
OTHER = "otherproj"
SYSTEM_REL = "knowledge/system.yaml"
ARTEL_REL = "knowledge/artel.yaml"
EXHAUSTED_PREFIX = "предел журнала обращений исчерпан"
REFUSAL_LINE = re.compile(r"карточки (\S+) не прочитаны: ([^\n]+)")
HEX64 = re.compile(r"[0-9a-f]{64}")

_EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    return exc.code if isinstance(exc.code, int) else 1


def card_block(key: str, where: list, token: str) -> str:
    """Карточка формы К-4а: все поля, текст полей несёт метку `token`."""
    return (f"  {key}:\n"
            f"    where: [{', '.join(where)}]\n"
            f"    rule: правило {token}\n"
            f"    why: причина {token}\n"
            f"    check: проверка {token}\n"
            f"    example: пример {token}\n"
            f"    incidents: [INC-{token}]\n")


def card_fields(token: str) -> list:
    return [f"правило {token}", f"причина {token}", f"проверка {token}",
            f"пример {token}", f"INC-{token}"]


def boundary_blocks(text: str) -> list:
    """Пары граничных маркеров `brief.wrap_boundary` в тексте: (id запуска,
    начало открывающего, конец закрывающего)."""
    probe = brief.wrap_boundary("RUNIDPROBE", "X").split("\n")
    open_re = re.compile(re.escape(probe[0]).replace("RUNIDPROBE", r"(\S+)"))
    blocks = []
    for found in open_re.finditer(text):
        rid = found.group(1)
        close = probe[-1].replace("RUNIDPROBE", rid)
        end = text.find(close, found.end())
        if end != -1:
            blocks.append((rid, found.start(), end + len(close)))
    return blocks


def inside(pos: int, blocks: list) -> bool:
    return any(start <= pos < end for _rid, start, end in blocks)


def occurrences(text: str, needle: str) -> list:
    return [m.start() for m in re.finditer(re.escape(needle), text)]


class KnowledgeSandbox(RealGitSandbox):
    """Пульт песочницы с карточками обоих видов и задачами трёх проектов."""

    def setUp(self):
        super().setUp()
        self.use_role_map()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.home = self.root / ".artel" / "operator-home"
        self.home.mkdir(parents=True, exist_ok=True)
        self.write_targets()

    # ---------------------------------------------------------- окружение
    def word(self, n: int = 6) -> str:
        return "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(n))

    def write_targets(self, artel_field: str | None = ARTEL_REL,
                      fields: dict | None = None) -> None:
        if fields is None:
            fields = {EXT: f".artel/projects/{EXT}/knowledge/cards.yaml",
                      OTHER: f".artel/projects/{OTHER}/knowledge/cards.yaml"}
        entry = artel_target_entry()
        if artel_field is not None:
            entry = entry.replace("    merge_gate: operator\n",
                                  f"    merge_gate: operator\n"
                                  f"    knowledge: {artel_field}\n", 1)
        text = "targets:\n" + entry
        for name in (EXT, OTHER):
            ext = _EXTERNAL_ENTRY.format(name=name, base=config.MAIN_BRANCH)
            if fields.get(name) is not None:
                ext += f"    knowledge: {fields[name]}\n"
            text += ext
        config.TARGETS.parent.mkdir(parents=True, exist_ok=True)
        config.TARGETS.write_text(text, encoding="utf-8")

    def commit_main(self, files: dict) -> None:
        """Файлы головы `main` пульта: текст — записать, `None` — удалить."""
        for rel, text in files.items():
            path = self.root / rel
            if text is None:
                if path.exists() or path.is_symlink():
                    path.unlink()
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "карточки")

    def project_file(self, name: str) -> Path:
        return config.PROJECTS / name / "knowledge" / "cards.yaml"

    def write_project_cards(self, name: str, text: str) -> Path:
        path = self.project_file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def cards_text(self, cards: list) -> str:
        """`cards` — (ключ, where, метка); порядок в файле перемешан."""
        cards = list(cards)
        self.rng.shuffle(cards)
        return "cards:\n" + "".join(card_block(*c) for c in cards)

    def add_task(self, task_id: str, target: str | None,
                 worktree: dict | None = None) -> None:
        conn = store.db()
        store.insert_task(conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-zadacha",
                          target or config.DEFAULT_TARGET, 25.0)
        if target is None:
            conn.execute("UPDATE tasks SET target=NULL WHERE id=?", (task_id,))
            conn.commit()
        if worktree is not None:
            wt = workspace.path(task_id, target or config.DEFAULT_TARGET)
            wt.mkdir(parents=True, exist_ok=True)
            for rel, text in worktree.items():
                path = wt / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    def run_knowledge(self, *argv: str, role: str | None = None,
                      task: str | None = None,
                      home_role: bool = False) -> tuple:
        """(код возврата, stdout, stderr) вызова `artel.py knowledge …`."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(self.home)}):
            os.environ.pop(config.ARTEL_ROLE_ENV, None)
            os.environ.pop(config.ARTEL_TASK_ENV, None)
            if role is not None:
                os.environ[config.ARTEL_ROLE_ENV] = role
            if task is not None:
                os.environ[config.ARTEL_TASK_ENV] = task
            if home_role:
                os.environ["HOME"] = str(config.ROLE_HOME)
            with mock.patch.object(sys, "argv",
                                   ["artel.py", "knowledge", *argv]), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                try:
                    artel.main()
                    code = 0
                except SystemExit as exc:
                    code = exit_code(exc)
                    if isinstance(exc.code, str):
                        err.write(exc.code + "\n")
        return code, out.getvalue(), err.getvalue()

    def access_rows(self, task_id: str) -> list:
        return [r for r in store.task_steps(store.db(), task_id)
                if r["action"] == knowledge_cards.ACCESS_ACTION]

    def plain_access(self, task_id: str) -> list:
        return [r for r in self.access_rows(task_id)
                if not (r["detail"] or "").startswith(EXHAUSTED_PREFIX)]

    def exhausted(self, task_id: str) -> list:
        return [r for r in self.access_rows(task_id)
                if (r["detail"] or "").startswith(EXHAUSTED_PREFIX)]

    def role_names(self) -> list:
        return sorted(roles.load())

    # ------------------------------------------------- стандартный набор
    def seed_standard(self) -> dict:
        """Две системные и три проектные карточки проекта EXT под запрос
        `pkg/mod.py`, по одной лишней карточке каждого вида; задача EXT с
        рабочей копией, где из трёх символов проектных карточек нет одного.
        Возвращает метки и ожидаемые числа."""
        t = {k: self.word() for k in ("s1", "s2", "s3", "p1", "p2", "p3",
                                      "p4")}
        sys_cards = [(f"{t['s1']}-s", ["pkg/mod.py::alpha_fn"], t["s1"]),
                     (f"{t['s2']}-s", ["pkg/*.py"], t["s2"]),
                     (f"{t['s3']}-s", ["elsewhere/x.py::zeta"], t["s3"])]
        prj_cards = [(f"{t['p1']}-p", ["pkg/mod.py::beta_fn"], t["p1"]),
                     (f"{t['p2']}-p", ["pkg/mod.py::gamma_fn"], t["p2"]),
                     (f"{t['p3']}-p", ["pkg/mod.py"], t["p3"]),
                     (f"{t['p4']}-p", ["other/y.md"], t["p4"])]
        system_text = self.cards_text(sys_cards)
        project_text = self.cards_text(prj_cards)
        self.commit_main({SYSTEM_REL: system_text,
                          "pkg/mod.py": "def alpha_fn():\n    pass\n"})
        self.write_project_cards(EXT, project_text)
        self.add_task("T101", EXT, worktree={
            "pkg/mod.py": "def beta_fn():\n    pass\n"})
        return {"tokens": t, "system_text": system_text,
                "project_text": project_text, "n_system": 2, "n_project": 3,
                "n_stale": 1}


class RoleWhitelistTest(KnowledgeSandbox):
    """AC-1: белый список роли и сверка `<id>` с `ARTEL_TASK`."""

    def test_ac1_role_with_matching_task_passes_whitelist(self):
        """Шаг роли (случайная роль карты, `ARTEL_TASK` = id задачи) зовёт
        `knowledge <id> pkg/mod.py`.

        Наблюдение: отказа «команда недоступна процессу роли» нет, код
        возврата 0, карточки выданы.

        Ловит мутацию: `knowledge` не внесена в `_ROLE_ALLOWED_COMMANDS` —
        диспетчер отказывает роли текстом «команда недоступна процессу
        роли» с ненулевым кодом, карточек в выводе нет.
        """
        data = self.seed_standard()
        role = self.rng.choice(self.role_names())
        code, out, err = self.run_knowledge("T101", "pkg/mod.py", role=role,
                                            task="T101")
        self.assertNotIn("недоступна процессу роли", out + err,
                         f"зерно: {self.seed}")
        self.assertEqual(code, 0, f"зерно: {self.seed}\n{out}\n{err}")
        self.assertIn(f"правило {data['tokens']['p1']}", out,
                      f"зерно: {self.seed}")

    def test_ac1_mismatched_id_home_only_role_and_unknown_task_refused(self):
        """Четыре вызова, каждый обязан отказать без записи журнала: роль с
        `ARTEL_TASK` другой существующей задачи; роль, распознанная только
        по дому роли без `ARTEL_TASK`, и с пустым `ARTEL_TASK`; вызов вне
        окружения роли с id несуществующей задачи.

        Наблюдение: код возврата ненулевой, карточек в выводе нет, записей
        действия `ACCESS_ACTION` ни у одной задачи нет.

        Ловит мутацию: сверка `<id>` с `ARTEL_TASK` пропускает пустой
        `ARTEL_TASK` (роль по дому без id задачи) — команда выдаёт карточки
        с кодом 0 и пишет запись обращения.
        """
        data = self.seed_standard()
        self.add_task("T102", EXT)
        role = self.rng.choice(self.role_names())
        cases = (
            ("чужой ARTEL_TASK", ("T101", "pkg/mod.py"),
             {"role": role, "task": "T102"}),
            ("дом роли без ARTEL_TASK", ("T101", "pkg/mod.py"),
             {"home_role": True}),
            ("дом роли с пустым ARTEL_TASK", ("T101", "pkg/mod.py"),
             {"home_role": True, "task": ""}),
            ("неизвестная задача", ("T999", "pkg/mod.py"), {}),
        )
        for label, argv, env in cases:
            with self.subTest(label):
                code, out, err = self.run_knowledge(*argv, **env)
                self.assertNotEqual(code, 0,
                                    f"зерно: {self.seed}; {label}\n{out}")
                self.assertNotIn(f"правило {data['tokens']['p1']}", out,
                                 f"зерно: {self.seed}; {label}")
                for task_id in ("T101", "T102"):
                    self.assertEqual(self.access_rows(task_id), [],
                                     f"зерно: {self.seed}; {label}")


class OutputTest(KnowledgeSandbox):
    """AC-2: состав, порядок и предел выдачи; проект задачи."""

    def test_ac2_cards_whole_ordered_and_capped(self):
        """Совпавших карточек на 2–5 больше `KNOWLEDGE_CARD_OUTPUT_MAX`
        (половина предела — системные, остальные — проектные); ключи
        случайны, в файлах карточки перемешаны.

        Наблюдение: выведены ровно первые `OUTPUT_MAX` карточек порядка
        «системные, затем проектные, внутри вида — по ключу», каждая
        целиком (ключ и все поля); остальные — только ключами в строке
        «ещё N по запросу (уточни путь)».

        Ловит мутацию: сортировка по ключу без учёта вида (системные и
        проектные вперемешку) — позиции правил в выводе нарушают ожидаемый
        порядок, а в «ещё N» попадают не те ключи.
        """
        cap = config.KNOWLEDGE_CARD_OUTPUT_MAX
        n_sys = max(1, cap // 2)
        n_prj = cap - n_sys + self.rng.randint(2, 5)
        sys_cards, prj_cards = [], []
        for i in range(n_sys):
            token = f"{self.word()}{i}"
            sys_cards.append((f"{self.word()}-{i}s",
                              ["qdir/*.py", f"other/{token}.md"], token))
        for i in range(n_prj):
            token = f"{self.word()}{i}"
            prj_cards.append((f"{self.word()}-{i}p",
                              ["qdir/*.py", f"other/{token}.md"], token))
        self.commit_main({SYSTEM_REL: self.cards_text(sys_cards)})
        self.write_project_cards(EXT, self.cards_text(prj_cards))
        self.add_task("T101", EXT, worktree={})

        code, out, err = self.run_knowledge("T101", "qdir/target.py")

        ordered = (sorted(sys_cards, key=lambda c: c[0])
                   + sorted(prj_cards, key=lambda c: c[0]))
        shown, hidden = ordered[:cap], ordered[cap:]
        self.assertEqual(code, 0, f"зерно: {self.seed}\n{out}\n{err}")
        positions = []
        for key, where, token in shown:
            self.assertIn(key, out, f"зерно: {self.seed}")
            for value in card_fields(token) + where:
                self.assertIn(value, out, f"зерно: {self.seed}; {key}")
            positions.append(out.index(f"правило {token}"))
        self.assertEqual(positions, sorted(positions),
                         f"зерно: {self.seed}: порядок выдачи\n{out}")
        rest_lines = [line for line in out.splitlines()
                      if f"ещё {len(hidden)} по запросу (уточни путь)" in line]
        self.assertTrue(rest_lines, f"зерно: {self.seed}: нет строки «ещё "
                                    f"{len(hidden)}»\n{out}")
        for key, _where, token in hidden:
            self.assertNotIn(f"правило {token}", out, f"зерно: {self.seed}")
            self.assertTrue(any(key in line for line in rest_lines),
                            f"зерно: {self.seed}: ключ {key} не в строке "
                            f"«ещё N»\n{out}")

    def test_ac2_project_cards_only_of_task_project(self):
        """Проектные карточки трёх проектов (EXT, OTHER — на диске их
        областей, артель — `knowledge/artel.yaml` в `main`) и системная
        карточка — все под один запрос; задачи EXT, OTHER и задача с
        `target` NULL.

        Наблюдение: каждой задаче выданы системная карточка и проектные
        карточки только её проекта; задаче с `target` NULL — проектные
        карточки `config.DEFAULT_TARGET`.

        Ловит мутацию: проект задачи с `target` NULL берётся как пустой (а
        не `config.DEFAULT_TARGET`) — задаче NULL не выдана проектная
        карточка артели; либо проектный файл читается без учёта проекта
        задачи — задаче EXT выдана карточка OTHER.
        """
        tok = {k: self.word() for k in ("sys", EXT, OTHER, "artel")}
        where = ["shared/x.py"]
        self.commit_main({
            SYSTEM_REL: self.cards_text([(f"{tok['sys']}-s", where,
                                          tok["sys"])]),
            ARTEL_REL: self.cards_text([(f"{tok['artel']}-a", where,
                                         tok["artel"])])})
        for name in (EXT, OTHER):
            self.write_project_cards(
                name, self.cards_text([(f"{tok[name]}-p", where, tok[name])]))
        self.add_task("T101", EXT)
        self.add_task("T102", OTHER)
        self.add_task("T103", None)
        expected = {"T101": EXT, "T102": OTHER, "T103": "artel"}
        for task_id, own in expected.items():
            with self.subTest(task_id):
                code, out, err = self.run_knowledge(task_id, "shared/x.py")
                self.assertEqual(code, 0, f"зерно: {self.seed}\n{out}\n{err}")
                self.assertIn(f"правило {tok['sys']}", out,
                              f"зерно: {self.seed}")
                for name in (EXT, OTHER, "artel"):
                    if name == own:
                        self.assertIn(f"правило {tok[name]}", out,
                                      f"зерно: {self.seed}; {task_id}")
                    else:
                        self.assertNotIn(f"правило {tok[name]}", out,
                                         f"зерно: {self.seed}; {task_id}")


class BoundaryTest(KnowledgeSandbox):
    """AC-3: граница недоверенных данных вокруг проектного вида."""

    def test_ac3_project_cards_and_their_marks_inside_boundary(self):
        """Системная карточка и проектная карточка с символом, которого нет
        в рабочей копии задачи EXT; команда зовётся дважды.

        Наблюдение: перед первым граничным маркером стоит
        `brief.BOUNDARY_INSTRUCTION`; текст проектной карточки и каждое
        упоминание её пропавшего символа (в том числе пометка «возможно
        устарела») — внутри пары маркеров; текст системной карточки — вне
        маркеров; id маркеров двух вызовов различны.

        Ловит мутацию: пометка «возможно устарела» проектной карточки
        печатается после закрывающего маркера (вне блока) — упоминание
        пропавшего символа найдено вне границы.
        """
        st, pt = self.word(), self.word()
        ghost = f"ghost_{self.word()}"
        self.commit_main({SYSTEM_REL: self.cards_text(
            [(f"{st}-s", ["src/a.py"], st)])})
        self.write_project_cards(EXT, self.cards_text(
            [(f"{pt}-p", [f"src/a.py::{ghost}"], pt)]))
        self.add_task("T101", EXT, worktree={"src/a.py": "X = 1\n"})

        code, out, err = self.run_knowledge("T101", "src/a.py")
        _code2, out2, _err2 = self.run_knowledge("T101", "src/a.py")

        blocks = boundary_blocks(out)
        self.assertTrue(blocks, f"зерно: {self.seed}: нет пары маркеров\n{out}")
        self.assertIn(brief.BOUNDARY_INSTRUCTION.strip(), out,
                      f"зерно: {self.seed}")
        self.assertLess(out.index(brief.BOUNDARY_INSTRUCTION.strip()),
                        blocks[0][1], f"зерно: {self.seed}")
        for value in card_fields(pt):
            for pos in occurrences(out, value):
                self.assertTrue(inside(pos, blocks),
                                f"зерно: {self.seed}: {value} вне границы\n{out}")
        self.assertIn("возможно устарела", out, f"зерно: {self.seed}\n{out}")
        for pos in occurrences(out, ghost):
            self.assertTrue(inside(pos, blocks),
                            f"зерно: {self.seed}: {ghost} вне границы\n{out}")
        for pos in occurrences(out, f"правило {st}"):
            self.assertFalse(inside(pos, blocks),
                             f"зерно: {self.seed}: системная карточка внутри "
                             f"границы\n{out}")
        self.assertIn(f"правило {st}", out, f"зерно: {self.seed}")
        ids1 = {rid for rid, _s, _e in blocks}
        ids2 = {rid for rid, _s, _e in boundary_blocks(out2)}
        self.assertTrue(ids2, f"зерно: {self.seed}")
        self.assertFalse(ids1 & ids2, f"зерно: {self.seed}: id границы "
                                      f"повторился между вызовами")

    def test_ac3_refusal_details_system_truncated_project_wrapped(self):
        """Файл вида с ключом карточки из 300 заглавных букв (отказ формы).
        Отказ системного вида — при исправном проектном, и наоборот.

        Наблюдение: в выводе нет 201 подряд символа ключа системного файла
        (подробность усечена до 200); при отказе проектного вида вывод
        несёт пару граничных маркеров, и каждое упоминание ключа проектного
        файла — внутри неё.

        Ловит мутацию: подробность отказа системного вида печатается
        целиком, без усечения — в выводе 300 подряд символов ключа.
        """
        good_s, good_p = self.word(), self.word()
        bad_sys = "cards:\n" + card_block("Q" * 300, ["a/b.py"], "x")
        bad_prj = "cards:\n" + card_block("P" * 300, ["a/b.py"], "y")
        self.add_task("T101", EXT, worktree={})
        with self.subTest("системный вид"):
            self.commit_main({SYSTEM_REL: bad_sys})
            self.write_project_cards(EXT, self.cards_text(
                [(f"{good_p}-p", ["a/b.py"], good_p)]))
            _code, out, err = self.run_knowledge("T101", "a/b.py")
            self.assertRegex(out + err, REFUSAL_LINE, f"зерно: {self.seed}")
            self.assertNotIn("Q" * 201, out + err, f"зерно: {self.seed}")
        with self.subTest("проектный вид"):
            self.commit_main({SYSTEM_REL: self.cards_text(
                [(f"{good_s}-s", ["a/b.py"], good_s)])})
            self.write_project_cards(EXT, bad_prj)
            _code, out, err = self.run_knowledge("T101", "a/b.py")
            combined = out + err
            blocks = boundary_blocks(combined)
            self.assertTrue(blocks, f"зерно: {self.seed}: подробность отказа "
                                    f"проектного вида без границы\n{combined}")
            for pos in occurrences(combined, "P" * 20):
                self.assertTrue(inside(pos, blocks), f"зерно: {self.seed}")


class KindRefusalTest(KnowledgeSandbox):
    """AC-4: отказ одного вида, «не заведён» и «нет поля»."""

    def test_ac4_refused_kind_reported_other_kind_given_nonzero_exit(self):
        """Отказ чтения системного вида (файл в `main` не разбирается) при
        исправном проектном и отказ проектного (файл на диске не
        разбирается) при исправном системном.

        Наблюдение: строка «карточки <вид> не прочитаны: <код причины>» с
        кодом из `knowledge_cards.REFUSAL_CODES`, карточки другого вида
        выданы, код возврата ненулевой.

        Ловит мутацию: отказ вида печатается строкой, но код возврата
        остаётся 0 — `assertNotEqual(code, 0)` падает.
        """
        st, pt = self.word(), self.word()
        broken = "cards:\n  a: [unclosed\n"
        good_sys = self.cards_text([(f"{st}-s", ["a/b.py"], st)])
        good_prj = self.cards_text([(f"{pt}-p", ["a/b.py"], pt)])
        self.add_task("T101", EXT, worktree={})
        for label, sys_text, prj_text, other in (
                ("системный", broken, good_prj, pt),
                ("проектный", good_sys, broken, st)):
            with self.subTest(label):
                self.commit_main({SYSTEM_REL: sys_text})
                self.write_project_cards(EXT, prj_text)
                code, out, err = self.run_knowledge("T101", "a/b.py")
                found = REFUSAL_LINE.search(out + err)
                self.assertIsNotNone(found, f"зерно: {self.seed}\n{out}{err}")
                self.assertTrue(
                    any(found.group(2).strip().startswith(c)
                        for c in knowledge_cards.REFUSAL_CODES),
                    f"зерно: {self.seed}: код вне перечня: {found.group(0)}")
                self.assertIn(f"правило {other}", out, f"зерно: {self.seed}")
                self.assertNotEqual(code, 0, f"зерно: {self.seed}; {label}")

    def test_ac4_not_set_up_and_no_field_are_lines_with_zero_exit(self):
        """Три случая без отказа: у проекта нет поля `knowledge`; поле есть,
        файла нет; системного файла нет в `main`.

        Наблюдение: код возврата 0, карточки исправного вида выданы, строка
        «не заведён»/«нет поля» есть, строки «не прочитаны» нет.

        Ловит мутацию: «файл не заведён» трактуется как отказ вида — код
        возврата ненулевой и печатается «карточки … не прочитаны».
        """
        st, pt = self.word(), self.word()
        good_sys = self.cards_text([(f"{st}-s", ["a/b.py"], st)])
        good_prj = self.cards_text([(f"{pt}-p", ["a/b.py"], pt)])
        self.add_task("T101", EXT, worktree={})
        cases = (("нет поля", good_sys, None, False, st),
                 ("файла нет", good_sys, None, True, st),
                 ("системного нет", None, good_prj, True, pt))
        for label, sys_text, prj_text, with_field, shown in cases:
            with self.subTest(label):
                self.commit_main({SYSTEM_REL: sys_text})
                path = self.project_file(EXT)
                if prj_text is None:
                    if path.exists():
                        path.unlink()
                else:
                    self.write_project_cards(EXT, prj_text)
                self.write_targets(fields={} if not with_field else None)
                code, out, err = self.run_knowledge("T101", "a/b.py")
                self.assertEqual(code, 0, f"зерно: {self.seed}; {label}\n"
                                          f"{out}{err}")
                self.assertIn(f"правило {shown}", out, f"зерно: {self.seed}")
                self.assertNotRegex(out + err, REFUSAL_LINE,
                                    f"зерно: {self.seed}; {label}")
                self.assertRegex(out, r"не заведён|нет поля",
                                 f"зерно: {self.seed}; {label}\n{out}")


class ReadOnlyTest(KnowledgeSandbox):
    """AC-5: команда не меняет состояние; чтение БД — `mode=ro`."""

    def snapshot(self, task_ids: tuple) -> dict:
        conn = store.db()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'steps'")]
        rows = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")]
                for t in tables}
        files = {}
        roots = [workspace.path(t, EXT) for t in task_ids]
        roots.append(self.project_file(EXT).parent)
        for base in roots:
            if base.exists():
                for path in sorted(base.rglob("*")):
                    if path.is_file():
                        files[str(path)] = path.read_bytes()
        return {"db": rows, "files": files,
                "refs": self.git("for-each-ref",
                                 "--format=%(refname) %(objectname)"),
                "head": self.git("rev-parse", "HEAD"),
                "status": self.git("status", "--porcelain")}

    def test_ac5_call_changes_no_state(self):
        """Задача с lease и рабочей копией; шаг роли зовёт команду несколько
        раз разными запросами.

        Наблюдение: строки всех таблиц БД, кроме журнала (`tasks`,
        `leases`, …), ссылки и HEAD git, `git status`, файлы рабочей копии
        и файл проектных карточек — те же, что до вызовов.

        Ловит мутацию: команда берёт lease задачи (или пишет строку задачи)
        на время чтения — таблица `leases`/`tasks` после вызова отличается
        от снимка.
        """
        self.seed_standard()
        conn = store.db()
        store.insert_lease(conn, "T101", "sess-fixture", 4242, "host",
                           store.now())
        before = self.snapshot(("T101",))
        role = self.rng.choice(self.role_names())
        for query in ("pkg/mod.py", "pkg/mod.py::beta_fn", "::alpha_fn"):
            self.run_knowledge("T101", query, role=role, task="T101")
        self.assertEqual(self.snapshot(("T101",)), before,
                         f"зерно: {self.seed}")

    def test_ac5_reads_db_with_read_only_connection(self):
        """Соединение записи `store.db()` отказывает `sqlite3.OperationalError`
        (БД закрыта на запись, как у шага на Codex).

        Наблюдение: задача найдена и карточки выданы (чтение не зависит от
        `store.db()`), среди соединений `sqlite3.connect` есть открытое
        `mode=ro`.

        Ловит мутацию: строка задачи читается через `store.db()` — команда
        падает `sqlite3.OperationalError` до выдачи карточек.
        """
        data = self.seed_standard()
        with mock.patch.object(store, "db",
                               side_effect=sqlite3.OperationalError("ro")), \
                mock.patch.object(sqlite3, "connect",
                                  wraps=sqlite3.connect) as connect:
            code, out, err = self.run_knowledge("T101", "pkg/mod.py")
        self.assertEqual(code, 0, f"зерно: {self.seed}\n{out}\n{err}")
        self.assertIn(f"правило {data['tokens']['p1']}", out,
                      f"зерно: {self.seed}")
        ro = [c for c in connect.call_args_list
              if "mode=ro" in str(c.args[0] if c.args else
                                  c.kwargs.get("database", ""))]
        self.assertTrue(ro, f"зерно: {self.seed}: нет соединения mode=ro: "
                            f"{connect.call_args_list}")


class AccessJournalTest(KnowledgeSandbox):
    """AC-6, AC-7: запись обращения и её поля."""

    def test_ac6_one_record_per_query_with_fields(self):
        """Стандартный набор: под запрос `pkg/mod.py` 2 системные и 3
        проектные карточки, одна помечена «возможно устарела». Два
        обращения разных ролей разными запросами.

        Наблюдение: каждое даёт ровно одну запись `ACCESS_ACTION` с автором
        `JOURNAL_ACTOR` (не ролью); `detail` двух записей начинаются общим
        префиксом без запроса; первая несёт роль, запрос в `json.dumps`,
        числа 2, 3 и 1 и `sha256` обоих файлов карточек.

        Ловит мутацию: автором записи берётся `ARTEL_ROLE` — `actor` записи
        равен роли, а не `JOURNAL_ACTOR`.
        """
        data = self.seed_standard()
        names = self.role_names()
        role1, role2 = self.rng.sample(names, 2)
        self.run_knowledge("T101", "pkg/mod.py", role=role1, task="T101")
        rows = self.access_rows("T101")
        self.assertEqual(len(rows), 1, f"зерно: {self.seed}")
        self.run_knowledge("T101", "pkg/mod.py::beta_fn", role=role2,
                           task="T101")
        rows = self.access_rows("T101")
        self.assertEqual(len(rows), 2, f"зерно: {self.seed}")
        for row in rows:
            self.assertEqual(row["actor"], knowledge_cards.JOURNAL_ACTOR)
            self.assertNotIn(row["actor"], names)
        first, second = rows[0]["detail"], rows[1]["detail"]
        prefix = os.path.commonprefix([first, second])
        self.assertGreaterEqual(len(prefix.strip()), 3,
                                f"зерно: {self.seed}: нет общего префикса")
        self.assertNotIn("pkg/mod.py", prefix, f"зерно: {self.seed}")
        query_json = json.dumps("pkg/mod.py", ensure_ascii=False)
        self.assertIn(role1, first, f"зерно: {self.seed}")
        self.assertIn(query_json, first, f"зерно: {self.seed}")
        for text in (data["system_text"], data["project_text"]):
            self.assertIn(brief.component_hash(text), first,
                          f"зерно: {self.seed}")
        rest = HEX64.sub(" ", first).replace(query_json, " ")
        rest = rest.replace(role1, " ")
        for number in (data["n_system"], data["n_project"], data["n_stale"]):
            self.assertRegex(rest, rf"(?<!\d){number}(?!\d)",
                             f"зерно: {self.seed}: нет числа {number}: {first}")

    def test_ac6_refusal_code_in_detail_and_rejected_query_not_written(self):
        """Проектный файл не разбирается — обращение пишет код отказа вида;
        запросы, отвергнутые формой (абсолютный путь, `..`, два `::`,
        длиннее `KNOWLEDGE_CARD_QUERY_MAX_CHARS`), записей не дают.

        Наблюдение: `detail` записи обращения несёт код причины из
        `REFUSAL_CODES`, напечатанный в строке отказа; число записей после
        отвергнутых запросов не растёт.

        Ловит мутацию: запись журнала пишется до проверки формы запроса —
        отвергнутый запрос оставляет запись обращения.
        """
        self.seed_standard()
        self.write_project_cards(EXT, "cards:\n  a: [unclosed\n")
        _code, out, err = self.run_knowledge("T101", "pkg/mod.py")
        found = REFUSAL_LINE.search(out + err)
        self.assertIsNotNone(found, f"зерно: {self.seed}")
        code_text = next(c for c in knowledge_cards.REFUSAL_CODES
                         if found.group(2).strip().startswith(c))
        rows = self.access_rows("T101")
        self.assertEqual(len(rows), 1, f"зерно: {self.seed}")
        self.assertIn(code_text, rows[0]["detail"], f"зерно: {self.seed}")
        too_long = "a/" + "b" * config.KNOWLEDGE_CARD_QUERY_MAX_CHARS
        for query in ("/abs/x.py", "a/../x.py", "a.py::b::c", too_long):
            with self.subTest(query=query[:30]):
                self.run_knowledge("T101", query)
                self.assertEqual(len(self.access_rows("T101")), 1,
                                 f"зерно: {self.seed}")

    def test_ac7_role_labels_in_detail(self):
        """Три обращения: роль из карты, роль вне карты `roles.yaml`
        песочницы, вызов вне окружения роли.

        Наблюдение: в `detail` — имя роли из карты; «роль не определена»
        (и нет присланного имени) для роли вне карты; «оператор» вне
        окружения роли.

        Ловит мутацию: роль вне перечня `roles.yaml` записывается как есть
        — в `detail` присланное имя, «роль не определена» нет.
        """
        self.seed_standard()
        known = self.rng.choice(self.role_names())
        stranger = f"zz{self.word()}-role"
        self.run_knowledge("T101", "pkg/mod.py", role=known, task="T101")
        self.run_knowledge("T101", "pkg/mod.py", role=stranger, task="T101")
        self.run_knowledge("T101", "pkg/mod.py")
        rows = self.access_rows("T101")
        self.assertEqual(len(rows), 3, f"зерно: {self.seed}")
        self.assertIn(known, rows[0]["detail"], f"зерно: {self.seed}")
        self.assertIn("роль не определена", rows[1]["detail"])
        self.assertNotIn(stranger, rows[1]["detail"], f"зерно: {self.seed}")
        self.assertIn("оператор", rows[2]["detail"], f"зерно: {self.seed}")

    def test_ac7_control_chars_cleaned_and_quote_kept_in_json(self):
        """Запросы с управляющими/форматирующими символами (ESC, U+202E,
        U+200B) и с двойной кавычкой в имени файла.

        Наблюдение: ни одна запись журнала не несёт сырого управляющего
        символа; принятый запрос записан
        `json.dumps(watch.safe_text(запрос), ensure_ascii=False)`, и
        разбор этой подстроки `json.loads` отдаёт очищенный запрос (кавычка
        не обрывает поле).

        Ловит мутацию: запрос пишется в `detail` без `watch.safe_text` —
        символ U+202E попадает в журнал сырым.
        """
        self.seed_standard()
        queries = [f"pkg/m{ch}od.py" for ch in ("\x1b", "‮", "​")]
        quoted = f'pkg/"{self.word()}".py'
        for query in queries + [quoted]:
            self.run_knowledge("T101", query)
        rows = self.access_rows("T101")
        for row in rows:
            for ch in ("\x1b", "‮", "​"):
                self.assertNotIn(ch, row["detail"], f"зерно: {self.seed}")
        for query in queries + [quoted]:
            encoded = json.dumps(watch.safe_text(query), ensure_ascii=False)
            hits = [r for r in rows if encoded in r["detail"]]
            if query == quoted:
                self.assertEqual(len(hits), 1, f"зерно: {self.seed}: "
                                               f"{encoded} не найден")
            for row in hits:
                start = row["detail"].index(encoded)
                decoded, _end = json.JSONDecoder().raw_decode(
                    row["detail"], start)
                self.assertEqual(decoded, watch.safe_text(query))


class CommandLimitTest(KnowledgeSandbox):
    """AC-9 на пути команды."""

    def test_ac9_limit_reached_then_single_exhausted_record(self):
        """В журнале задачи `KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK - 1` записей
        обращения и 2–4 записи `HINT_REFUSAL_ACTION` того же автора;
        команда зовётся четыре раза.

        Наблюдение: первый вызов дописывает обращение до предела (записи
        отказа подсказки предел не съели); второй пишет одну запись того же
        действия и автора с `detail` «предел журнала обращений исчерпан…»;
        третий и четвёртый не пишут ничего; карточки выдаются каждый раз.

        Ловит мутацию: признак «уже писалась» не проверяется — каждый вызов
        сверх предела пишет новую запись «предел исчерпан», их больше одной.
        """
        data = self.seed_standard()
        limit = config.KNOWLEDGE_CARD_JOURNAL_MAX_PER_TASK
        conn = store.db()
        for i in range(limit - 1):
            store.journal(conn, "T101", knowledge_cards.JOURNAL_ACTOR,
                          knowledge_cards.ACCESS_ACTION, f"посев {i}")
        for i in range(self.rng.randint(2, 4)):
            store.journal(conn, "T101", knowledge_cards.JOURNAL_ACTOR,
                          knowledge_cards.HINT_REFUSAL_ACTION, f"посев {i}")
        role = self.rng.choice(self.role_names())
        for call in range(4):
            code, out, err = self.run_knowledge("T101", "pkg/mod.py",
                                                role=role, task="T101")
            self.assertIn(f"правило {data['tokens']['p1']}", out,
                          f"зерно: {self.seed}; вызов {call}")
            self.assertEqual(len(self.plain_access("T101")), limit,
                             f"зерно: {self.seed}; вызов {call}")
            self.assertEqual(len(self.exhausted("T101")), 0 if call == 0 else 1,
                             f"зерно: {self.seed}; вызов {call}")
        last = self.exhausted("T101")[0]
        self.assertEqual(last["actor"], knowledge_cards.JOURNAL_ACTOR)


class DeferredJournalTest(KnowledgeSandbox):
    """AC-10: БД без права записи — очередь и досыл."""

    def test_ac10_unwritable_db_defers_and_delivery_writes_once(self):
        """`store.db()` отказывает `sqlite3.OperationalError` и `OSError`
        (по вызову на класс); затем досыл `suite_lock.deliver_journal`
        дважды. Рядом в очереди — прежнее действие
        `acceptance.SUITE_NEAR_LIMIT_ACTION`.

        Наблюдение: карточки выданы; после досыла записей обращения ровно
        две (по одной на вызов) с автором `JOURNAL_ACTOR`, повторный досыл
        их не дублирует; запись прежнего действия — с автором
        `suite_lock.DEFERRED_ACTOR`.

        Ловит мутацию: `ACCESS_ACTION` не внесено в `suite_lock.deferrable`
        — файл очереди не пишется (или досыл его выбрасывает), записей
        обращения после досыла нет.
        """
        data = self.seed_standard()
        for exc in (sqlite3.OperationalError("ro"), OSError("ro")):
            with self.subTest(type(exc).__name__), \
                    mock.patch.object(store, "db", side_effect=exc):
                code, out, err = self.run_knowledge("T101", "pkg/mod.py")
                self.assertIn(f"правило {data['tokens']['p1']}", out,
                              f"зерно: {self.seed}\n{err}")
        self.assertEqual(self.access_rows("T101"), [])
        suite_lock.defer_journal({
            "task_id": "T101", "action": acceptance.SUITE_NEAR_LIMIT_ACTION,
            "detail": "нагрузка", "session_id": None, "at": store.now()})
        suite_lock.deliver_journal()
        suite_lock.deliver_journal()
        rows = self.access_rows("T101")
        self.assertEqual(len(rows), 2, f"зерно: {self.seed}")
        for row in rows:
            self.assertEqual(row["actor"], knowledge_cards.JOURNAL_ACTOR)
        near = [r for r in store.task_steps(store.db(), "T101")
                if r["action"] == acceptance.SUITE_NEAR_LIMIT_ACTION]
        self.assertEqual([r["actor"] for r in near],
                         [suite_lock.DEFERRED_ACTOR])

    def test_ac10_queue_unavailable_one_stderr_line_cards_given(self):
        """`store.db()` отказывает, и очередь `suite_lock.defer_journal`
        отказывает `OSError` (каталог закрыт песочницей).

        Наблюдение: карточки выданы, исключение наружу не вышло, в stderr
        ровно одна непустая строка.

        Ловит мутацию: сбой очереди не перехвачен — команда падает `OSError`
        (тест видит исключение вместо вывода карточек).
        """
        data = self.seed_standard()
        with mock.patch.object(store, "db",
                               side_effect=sqlite3.OperationalError("ro")), \
                mock.patch.object(suite_lock, "defer_journal",
                                  side_effect=OSError("закрыт")):
            code, out, err = self.run_knowledge("T101", "pkg/mod.py")
        self.assertIn(f"правило {data['tokens']['p1']}", out,
                      f"зерно: {self.seed}")
        lines = [line for line in err.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"зерно: {self.seed}: stderr {err!r}")


if __name__ == "__main__":
    unittest.main()
