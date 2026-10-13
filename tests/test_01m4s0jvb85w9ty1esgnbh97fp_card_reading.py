"""Чтение карточек знаний по видам: `orchestrator.knowledge_cards.read_cards`.

Держит связку «`targets.yaml` — git главной копии пульта — диск области
проектов — исход чтения вида»: песочница `tests.sandbox.RealGitSandbox`
(корень пульта — настоящий git-репозиторий с веткой `config.MAIN_BRANCH`,
область проектов и `targets.yaml` — во временном каталоге). Системный
файл `config.KNOWLEDGE_CARD_SYSTEM_REL` и проектный файл артели
коммитятся в репозиторий песочницы, проектный файл внешнего проекта
кладётся на диск области проектов. Настоящие `targets.yaml` и
`knowledge/` пульта не трогаются. Ключи карточек, имена проектов и
файлов — случайные при каждом запуске; зерно печатается и входит в текст
провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/knowledge_cards.py (и `read_cards`) ещё нет — импорт падает, все тесты файла красны.
"""
import builtins
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, repo_context
try:
    from orchestrator import knowledge_cards as kc
except ImportError as exc:  # до реализации модуля нет: сбор проходит, тесты красны
    kc = None
    KC_IMPORT_ERROR = exc


def setUpModule() -> None:
    if kc is None:
        raise KC_IMPORT_ERROR
from tests.sandbox import RealGitSandbox, artel_target_entry

# Боевая область проектов этого процесса — до любых подмен песочницы.
LOADED_PROJECTS = config.PROJECTS

LATIN = "abcdefghijklmnopqrstuvwxyz"
SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")

_OPENED: list = []
_RECORDING: list = []


def _audit(event, args):
    if _RECORDING and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        _OPENED.append(os.fsdecode(args[0]))


sys.addaudithook(_audit)


EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class CardsSandbox(RealGitSandbox):
    """Корень пульта — git с веткой main; `targets.yaml` — артель и два
    внешних проекта `self.p` (с полем `knowledge`) и `self.q` (без поля)."""

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()
        self.p, self.q = self.name(), self.name()
        self.p_rel = f".artel/projects/{self.p}/knowledge/{self.name()}.yaml"
        self.write_targets({self.p: self.p_rel, self.q: None})

    # --- случайные входы ---

    def name(self) -> str:
        while True:
            value = "".join(self.rng.choice(LATIN)
                            for _ in range(self.rng.randrange(4, 10)))
            if value not in self.used and value != config.DEFAULT_TARGET:
                self.used.add(value)
                return value

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def cards_text(self, count: int | None = None) -> tuple:
        """(текст файла карточек, ключи) — 2–3 верные карточки."""
        keys = [self.name() for _ in range(count or self.rng.randrange(2, 4))]
        lines = ["cards:"]
        for key in keys:
            lines += [f"  {key}:", f"    where: [{self.name()}/{self.name()}.py]",
                      f"    rule: правило {self.name()}",
                      f"    why: причина {self.name()}"]
        return "\n".join(lines) + "\n", keys

    # --- окружение ---

    def write_targets(self, external: dict, artel_knowledge: str | None = None):
        artel = artel_target_entry()
        if artel_knowledge is not None:
            artel = artel.replace(
                "    merge_gate: operator\n",
                f"    merge_gate: operator\n    knowledge: {artel_knowledge}\n", 1)
        text = "targets:\n" + artel
        for name, rel in external.items():
            text += EXTERNAL_ENTRY.format(name=name, base=config.MAIN_BRANCH)
            if rel is not None:
                text += f"    knowledge: {rel}\n"
        config.TARGETS.parent.mkdir(parents=True, exist_ok=True)
        config.TARGETS.write_text(text, encoding="utf-8")

    def commit(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", rel)
        self.git("commit", "-q", "-m", f"карточки {rel}")

    def put(self, rel: str, data) -> Path:
        """Файл на диске по пути `rel` от корня пульта (без коммита)."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def project_file(self, project: str, rel: str) -> Path:
        """Путь проектного файла внешнего проекта в области проектов."""
        return config.PROJECTS / project / "knowledge" / Path(rel).name

    # --- чтение ---

    def read(self, project: str) -> tuple:
        result = kc.read_cards(project)
        self.assertIsInstance(result, tuple, self.msg(repr(result)))
        self.assertEqual(len(result), 2, self.msg(repr(result)))
        system, own = result
        self.assertEqual(system.kind, kc.SYSTEM, self.msg(repr(system)))
        self.assertEqual(own.kind, kc.PROJECT, self.msg(repr(own)))
        self.assert_coherent(system)
        self.assert_coherent(own)
        return system, own

    def assert_coherent(self, kr) -> None:
        """Исход вида — ровно один из трёх, поля согласованы с исходом."""
        self.assertIn(kr.outcome, (kc.CARDS, kc.NOT_SET_UP, kc.REFUSED),
                      self.msg(repr(kr)))
        self.assertIsInstance(kr.cards, tuple, self.msg(repr(kr)))
        if kr.outcome == kc.CARDS:
            self.assertIsNone(kr.refusal, self.msg(repr(kr)))
            self.assertRegex(kr.sha256 or "", SHA256, self.msg(repr(kr)))
            for card in kr.cards:
                self.assertEqual(card.kind, kr.kind, self.msg(repr(card)))
        else:
            self.assertEqual(kr.cards, (), self.msg(repr(kr)))
            self.assertIsNone(kr.sha256, self.msg(repr(kr)))
        if kr.outcome == kc.REFUSED:
            self.assertIsInstance(kr.refusal, kc.Refusal, self.msg(repr(kr)))
            self.assertIn(kr.refusal.code, kc.REFUSAL_CODES, self.msg(repr(kr)))
            self.assertIsInstance(kr.refusal.detail, str, self.msg(repr(kr)))
            self.assertTrue(kr.refusal.detail.strip(), self.msg(repr(kr)))
        else:
            self.assertIsNone(kr.refusal, self.msg(repr(kr)))

    def assert_cards(self, kr, keys, text) -> None:
        self.assertEqual(kr.outcome, kc.CARDS, self.msg(repr(kr)))
        self.assertEqual(sorted(c.key for c in kr.cards), sorted(keys),
                         self.msg(repr(kr)))
        self.assertEqual(kr.sha256, brief.component_hash(text), self.msg(repr(kr)))

    def assert_no_project_cards(self, kr) -> None:
        self.assertEqual(kr.cards, (), self.msg(repr(kr)))
        self.assertNotEqual(kr.outcome, kc.REFUSED, self.msg(repr(kr)))

    def assert_refused(self, kr, code) -> None:
        self.assertEqual(kr.outcome, kc.REFUSED, self.msg(repr(kr)))
        self.assertEqual(kr.refusal.code, code, self.msg(repr(kr)))


class KindsTest(CardsSandbox):

    def test_ac7_project_cards_come_from_named_file_with_sha(self):
        """Проектные карточки — из файла, названного полем `knowledge`, вместе
        с `sha256` его текста; системные — из `knowledge/system.yaml` main.

        Сценарий: в каталоге знаний проекта `p` два файла — названный полем
        и соседний-приманка с другими карточками; `read_cards(p)` отдаёт
        системный вид с карточками и хэшем системного текста, проектный —
        с карточками именно названного файла и `brief.component_hash` его
        текста; вид каждой карточки совпадает с видом исхода.

        Ловит мутацию: проектный файл берётся первым по имени в каталоге
        знаний (или фиксированным `<проект>.yaml`) вместо значения поля —
        отданы карточки приманки; либо `sha256` считается от пути/байтов
        другого файла — хэш не совпал.
        """
        system_text, system_keys = self.cards_text()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, system_text)
        own_text, own_keys = self.cards_text()
        decoy_text, _ = self.cards_text()
        self.put(self.p_rel, own_text)
        decoy = Path(self.p_rel).with_name("a" + Path(self.p_rel).name)
        self.put(str(decoy), decoy_text)

        system, own = self.read(self.p)

        self.assert_cards(system, system_keys, system_text)
        self.assert_cards(own, own_keys, own_text)

    def test_ac7_project_cards_only_for_own_project(self):
        """Системные карточки отдаются задачам любого проекта, проектные —
        только своему: у `q` без поля и у артели без поля проектных нет, у
        `q` со своим полем — только его карточки.

        Ловит мутацию: проектный вид собирается из всех записей
        `targets.yaml` с полем `knowledge` (или из записи первого проекта) —
        карточки `p` отданы задаче `q`/артели.
        """
        system_text, system_keys = self.cards_text()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, system_text)
        own_text, _ = self.cards_text()
        self.put(self.p_rel, own_text)

        for project in (self.q, config.DEFAULT_TARGET):
            with self.subTest(project=project):
                system, own = self.read(project)
                self.assert_cards(system, system_keys, system_text)
                self.assert_no_project_cards(own)

        q_rel = f".artel/projects/{self.q}/knowledge/{self.name()}.yaml"
        q_text, q_keys = self.cards_text()
        self.put(q_rel, q_text)
        self.write_targets({self.p: self.p_rel, self.q: q_rel})
        system, own = self.read(self.q)
        self.assert_cards(system, system_keys, system_text)
        self.assert_cards(own, q_keys, q_text)

    def test_ac7_missing_or_broken_targets_gives_no_project_cards(self):
        """Нет `targets.yaml`, он не разобран или запись негодна
        (`targets.TargetsError`) — проектных карточек ноль, исключение
        наружу не выходит, системные отдаются.

        Ловит мутацию: `targets.target` зовётся без перехвата
        `TargetsError` — `read_cards` падает исключением на сломанном
        файле.
        """
        system_text, system_keys = self.cards_text()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, system_text)
        self.put(self.p_rel, self.cards_text()[0])
        broken = (
            None,
            "targets:\n  x: [\n",
            "targets:\n" + EXTERNAL_ENTRY.format(
                name=self.p, base=config.MAIN_BRANCH).replace(
                    "    forge: github\n", "")
            + f"    knowledge: {self.p_rel}\n",
            "nothing: here\n",
        )
        for text in broken:
            with self.subTest(text=text):
                if text is None:
                    config.TARGETS.unlink(missing_ok=True)
                else:
                    config.TARGETS.write_text(text, encoding="utf-8")
                try:
                    system, own = self.read(self.p)
                except Exception as exc:  # noqa: BLE001 — предмет теста
                    self.fail(self.msg(f"исключение наружу: {exc!r}"))
                self.assert_cards(system, system_keys, system_text)
                self.assert_no_project_cards(own)


class MainBranchReadTest(CardsSandbox):

    def setUp(self):
        super().setUp()
        self.write_targets({self.p: self.p_rel, self.q: None},
                           artel_knowledge="knowledge/artel.yaml")

    def test_ac8_system_and_artel_files_read_from_main_not_disk(self):
        """Системный файл и проектный файл артели (`knowledge/artel.yaml`)
        читаются с головы `main`: незакоммиченная правка на диске в выдачу
        не попадает, `sha256` — текста из `main`.

        Ловит мутацию: файл в `knowledge/` читается с диска `config.ROOT`
        (как прочие файлы) — отданы карточки незакоммиченной правки.
        """
        system_text, system_keys = self.cards_text()
        artel_text, artel_keys = self.cards_text()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, system_text)
        self.commit("knowledge/artel.yaml", artel_text)
        self.put(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.put("knowledge/artel.yaml", self.cards_text()[0])

        system, own = self.read(config.DEFAULT_TARGET)

        self.assert_cards(system, system_keys, system_text)
        self.assert_cards(own, artel_keys, artel_text)

    def test_ac8_file_absent_in_main_is_not_set_up(self):
        """Файла нет в `main` (есть только неотслеживаемым на диске) —
        «не заведён», не отказ, у системного и у проектного файла артели.

        Ловит мутацию: пустой вывод `ls-tree` трактуется как отказ git (или
        отсутствие различается по `gitcmd.show`, который отвечает
        `(None, причина)` и на отказ) — исход «отказ» вместо «не заведён»;
        либо при отсутствии в `main` файл берётся с диска.
        """
        self.put(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.put("knowledge/artel.yaml", self.cards_text()[0])

        system, own = self.read(config.DEFAULT_TARGET)

        self.assertEqual(system.outcome, kc.NOT_SET_UP, self.msg(repr(system)))
        self.assertEqual(own.outcome, kc.NOT_SET_UP, self.msg(repr(own)))

    def test_ac8_missing_main_branch_is_git_no_answer(self):
        """Репозиторий есть, ветки `config.MAIN_BRANCH` нет — отказ «git не
        ответил» у системного и у проектного файла артели.

        Ловит мутацию: ненулевой код `ls-tree` (неизвестная ревизия)
        трактуется как «файла нет» — исход «не заведён» вместо отказа.
        """
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.commit("knowledge/artel.yaml", self.cards_text()[0])
        self.git("branch", "-m", config.MAIN_BRANCH, f"x-{self.name()}")

        system, own = self.read(config.DEFAULT_TARGET)

        self.assert_refused(system, kc.GIT_NO_ANSWER)
        self.assert_refused(own, kc.GIT_NO_ANSWER)

    def test_ac8_ls_tree_nonzero_or_none_is_git_no_answer(self):
        """Ненулевой код или `None` от `gitcmd.in_repo` на `ls-tree` — отказ
        «git не ответил».

        Сценарий: `gitcmd.in_repo` подменён ответом с кодом 128 и затем
        `None`; системный файл в `main` есть.

        Ловит мутацию: ответ `None` не проверяется (`res.returncode` на
        `None` роняет `AttributeError`) либо ненулевой код читается как
        пустой вывод — «не заведён».
        """
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.commit("knowledge/artel.yaml", self.cards_text()[0])
        for answer in (subprocess.CompletedProcess([], 128, "", "fatal"),
                       None):
            with self.subTest(answer=answer), \
                    mock.patch("orchestrator.gitcmd.in_repo",
                               return_value=answer):
                system, own = self.read(config.DEFAULT_TARGET)
                self.assert_refused(system, kc.GIT_NO_ANSWER)
                self.assert_refused(own, kc.GIT_NO_ANSWER)

    def test_ac8_no_git_in_root_is_not_set_up(self):
        """Нет `.git` в `config.ROOT` ни каталогом, ни файлом — «не
        заведён», не отказ; файлы `knowledge/` на диске не читаются.

        Ловит мутацию: проверка `.git` снята — `ls-tree` вне репозитория
        отвечает ненулевым кодом и вид получает отказ «git не ответил»;
        либо при отсутствии `.git` файл берётся с диска.
        """
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.commit("knowledge/artel.yaml", self.cards_text()[0])
        (self.root / ".git").rename(self.root / f"git-{self.name()}")

        system, own = self.read(config.DEFAULT_TARGET)

        self.assertEqual(system.outcome, kc.NOT_SET_UP, self.msg(repr(system)))
        self.assertEqual(own.outcome, kc.NOT_SET_UP, self.msg(repr(own)))

    def test_ac8_worktree_root_with_git_file_reads_main(self):
        """Корень, где `.git` — файл (рабочая копия `git worktree`),
        читается с головы `main` репозитория, а не помечается «не заведён».

        Сценарий: рабочая копия на отделённом HEAD; `config.ROOT` — она; на
        её диске файлы `knowledge/` изменены — выдача из `main`.

        Ловит мутацию: признак репозитория — `(ROOT / ".git").is_dir()` —
        рабочая копия worktree принята за «нет git», карточек нет.
        """
        system_text, system_keys = self.cards_text()
        artel_text, artel_keys = self.cards_text()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, system_text)
        self.commit("knowledge/artel.yaml", artel_text)
        holder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        worktree = (holder / "wt").resolve()
        self.git("worktree", "add", "-q", "--detach", str(worktree))
        self.assertTrue((worktree / ".git").is_file())
        (worktree / config.KNOWLEDGE_CARD_SYSTEM_REL).write_text(
            self.cards_text()[0], encoding="utf-8")
        (worktree / "knowledge" / "artel.yaml").write_text(
            self.cards_text()[0], encoding="utf-8")

        with mock.patch.object(config, "ROOT", worktree):
            system, own = self.read(config.DEFAULT_TARGET)

        self.assert_cards(system, system_keys, system_text)
        self.assert_cards(own, artel_keys, artel_text)


class ProjectDiskReadTest(CardsSandbox):

    def setUp(self):
        super().setUp()
        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL, self.cards_text()[0])
        self.kdir = config.PROJECTS / self.p / "knowledge"
        self.target = self.project_file(self.p, self.p_rel)

    def reset_kdir(self) -> None:
        if self.kdir.is_symlink() or self.kdir.is_file():
            self.kdir.unlink()
        elif self.kdir.exists():
            shutil.rmtree(self.kdir)
        self.kdir.mkdir(parents=True)

    def test_ac9_no_area_is_not_set_up_and_live_area_untouched(self):
        """`repo_context.projects_root()` — `NO_AREA` (корень пульта
        подменён, область проектов боевая): проектный вид «не заведён», ни
        одного обращения к файлам боевой области.

        Сценарий: тот же путь поля лежит верным файлом от корня
        песочницы; область проектов возвращена на боевую, во время
        `read_cards` записываются `stat`/`lstat`/`open`.

        Ловит мутацию: путь проектного файла строится от `config.ROOT` или
        `config.PROJECTS` в обход `projects_root()` — отданы карточки
        файла песочницы либо зафиксировано обращение к боевой области.
        """
        self.put(self.p_rel, self.cards_text()[0])
        touched = []

        def spy(real):
            def wrapper(path, *args, **kwargs):
                touched.append(os.fsdecode(path) if isinstance(
                    path, (str, bytes, os.PathLike)) else repr(path))
                return real(path, *args, **kwargs)
            return wrapper

        with mock.patch.object(config, "PROJECTS", LOADED_PROJECTS):
            self.assertEqual(repo_context.projects_root(), repo_context.NO_AREA)
            _OPENED.clear()
            with mock.patch.object(os, "stat", spy(os.stat)), \
                    mock.patch.object(os, "lstat", spy(os.lstat)), \
                    mock.patch.object(builtins, "open", spy(builtins.open)):
                _RECORDING.append(True)
                try:
                    _system, own = self.read(self.p)
                finally:
                    _RECORDING.pop()

        self.assertEqual(own.outcome, kc.NOT_SET_UP, self.msg(repr(own)))
        live = str(LOADED_PROJECTS)
        hits = [p for p in touched + _OPENED if p.startswith(live)]
        self.assertEqual(hits, [], self.msg("обращения к боевой области"))

    def test_ac9_missing_file_is_not_set_up(self):
        """Нет файла (каталог знаний есть или его нет) — «не заведён».

        Ловит мутацию: отсутствующий файл читается и `FileNotFoundError`
        уходит в отказ «файл не прочитан».
        """
        for make_dir in (False, True):
            with self.subTest(make_dir=make_dir):
                if make_dir:
                    self.kdir.mkdir(parents=True, exist_ok=True)
                _system, own = self.read(self.p)
                self.assertEqual(own.outcome, kc.NOT_SET_UP, self.msg(repr(own)))

    def test_ac9_links_special_escaping_unreadable_non_utf8_refused(self):
        """Ссылка (на файл в клоне `repo/`, в каталоге другого проекта, в
        том же каталоге), специальный файл (FIFO), путь, вышедший по
        `resolve()` из каталога знаний (каталог — ссылка в другой проект и
        во внешний каталог), нечитаемый файл и файл не в UTF-8 — отказ «файл
        не прочитан».

        Ловит мутацию: проверка ссылки делается после `resolve()` (ссылка
        принята за обычный файл), каталог знаний не сверяется с
        `resolve()`, `UnicodeDecodeError` уходит наружу исключением —
        отданы чужие карточки или тест падает исключением.
        """
        good_text, _ = self.cards_text()
        clone_file = self.put(f".artel/projects/{self.p}/repo/{self.name()}.yaml",
                              good_text)
        other_dir = config.PROJECTS / self.q / "knowledge"
        other_file = self.put(f".artel/projects/{self.q}/knowledge/"
                              f"{self.target.name}", good_text)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / self.target.name).write_text(good_text, encoding="utf-8")

        def link_to(dest):
            def make():
                self.target.symlink_to(dest)
            return make

        def sibling_link():
            sibling = self.kdir / f"s{self.target.name}"
            sibling.write_text(good_text, encoding="utf-8")
            self.target.symlink_to(sibling)

        def kdir_link(dest):
            def make():
                self.kdir.rmdir()
                self.kdir.symlink_to(dest, target_is_directory=True)
            return make

        def fifo():
            os.mkfifo(self.target)

        def unreadable():
            self.target.write_text(good_text, encoding="utf-8")
            self.target.chmod(0)
            self.addCleanup(lambda: self.target.exists()
                            and self.target.chmod(0o644))
            readable = True
            try:
                with open(self.target, encoding="utf-8"):
                    pass
            except OSError:
                readable = False
            if readable:
                self.skipTest("права файла не ограничивают чтение (root)")

        def non_utf8():
            self.target.write_bytes(good_text.encode("utf-8") + b"\xff\xfe\x80")

        cases = (("ссылка в клон repo/", link_to(clone_file)),
                 ("ссылка в другой проект", link_to(other_file)),
                 ("ссылка в том же каталоге", sibling_link),
                 ("FIFO", fifo),
                 ("каталог знаний — ссылка в другой проект", kdir_link(other_dir)),
                 ("каталог знаний — ссылка наружу", kdir_link(outside)),
                 ("не UTF-8", non_utf8),
                 ("нечитаемый", unreadable))
        for label, make in cases:
            with self.subTest(case=label):
                self.reset_kdir()
                make()
                _system, own = self.read(self.p)
                self.assert_refused(own, kc.FILE_UNREADABLE)


class OutcomeCoherenceTest(CardsSandbox):

    def test_ac10_each_kind_outcome_is_one_of_three_with_listed_code(self):
        """Исход чтения вида — ровно один из трёх; отказ несёт код из
        `REFUSAL_CODES` и подробность отдельным полем — и у отказов чтения
        (git, файл), и у отказов формы, пришедших через чтение.

        Сценарий: подряд — карточки; «не заведён»; системный файл в `main`
        не разобран `yamlmini`; проектный файл с повтором ключа; проектный
        файл не в UTF-8; ветки `main` нет.

        Ловит мутацию: отказ формы при чтении отдаётся исходом `CARDS` с
        пустым кортежем либо кодом вне перечня (текст `yamlmini` в поле
        кода) — тест красен на согласованности исхода.
        """
        seen = []
        text, keys = self.cards_text()
        self.put(self.p_rel, text)
        _system, own = self.read(self.p)
        self.assert_cards(own, keys, text)
        seen.append(own.outcome)

        system, _own = self.read(self.q)
        self.assertEqual(system.outcome, kc.NOT_SET_UP, self.msg(repr(system)))
        seen.append(system.outcome)

        self.commit(config.KNOWLEDGE_CARD_SYSTEM_REL,
                    "cards:\n  a:\n    where: [\"a.py\"]\n    rule: r\n    why: w\n")
        system, _own = self.read(self.q)
        self.assert_refused(system, kc.FILE_UNPARSED)
        seen.append(system.outcome)

        key = self.name()
        self.put(self.p_rel, f"cards:\n  {key}:\n    where: [a.py]\n    rule: r\n"
                             f"    why: w\n  {key}:\n    where: [b.py]\n"
                             f"    rule: r\n    why: w\n")
        _system, own = self.read(self.p)
        self.assert_refused(own, kc.DUPLICATE)

        self.put(self.p_rel, b"cards:\n\xff\n")
        _system, own = self.read(self.p)
        self.assert_refused(own, kc.FILE_UNREADABLE)

        self.git("branch", "-m", config.MAIN_BRANCH, f"x-{self.name()}")
        system, _own = self.read(self.q)
        self.assert_refused(system, kc.GIT_NO_ANSWER)
        seen.append(system.outcome)

        self.assertEqual(set(seen), {kc.CARDS, kc.NOT_SET_UP, kc.REFUSED})


if __name__ == "__main__":
    unittest.main()
