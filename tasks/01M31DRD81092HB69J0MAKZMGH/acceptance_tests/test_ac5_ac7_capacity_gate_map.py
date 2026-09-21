"""Приёмочные тесты AC-5..AC-7: гейт ёмкости
`orchestrator/advance_gates/capacity.py` исключает из меры
`docs/codebase-map.md` тем же приёмом pathspec `:!`, каким уже исключает
`tasks/<id>/`, и называет объём исключённой карты отдельной цифрой в
тексте отказа (SPEC, требование 5).

Песочница — `tests.sandbox.TmpRootTest` плюс поддельный `gitcmd.git`,
который РАЗБИРАЕТ pathspec вызова и отдаёт diff ровно тех файлов, что
под него попали: тест не привязан к порядку и форме аргументов, только к
наблюдаемому свойству «карта в мере не участвует». Тот же приём патча
`mock.patch.object(gitcmd, "git", ...)`, что у существующего прецедента
`tests/test_capacity_gate.py`.

Размеры фикстуры считаются динамически от
`config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES` — поворот этой крутилки
Оператором планку не ломает (порог задачей не меняется, SPEC,
требование 5, последнее предложение).

Красен до реализации: гейт сегодня меряет diff кода вместе с
docs/codebase-map.md и не называет её объём в отказе — карта попадает в
первую цифру, и второй цифры для неё в тексте нет.
"""
import subprocess
import unittest
from unittest import mock

from orchestrator import config, fsm_advance, gitcmd, store
from tests.sandbox import TmpRootTest

MAP_REL = "docs/codebase-map.md"

TASK_ID = "T001"
BRANCH = "task/t001-map"

# Окно после имени пути, в котором ищется относящаяся к нему цифра: текст
# отказа гейта — одна строка вида «... (исключённые ...: N байт)».
FIGURE_WINDOW = 80


def diff_chunk(path: str, size: int) -> str:
    """Кусок diff ровно `size` байт (ASCII) без ведущих и завершающих
    пробельных символов — `review.git_diff_part` отдаёт `stdout.strip()`,
    и байты меряются уже после него."""
    head = f"diff --git a/{path} b/{path}\n"
    return head + "+" + "x" * max(1, size - len(head) - 1)


def matches(path: str, spec: str) -> bool:
    if spec == ".":
        return True
    if spec.endswith("/"):
        return path.startswith(spec)
    return path == spec or path.startswith(spec + "/")


class FakeGit:
    """Поддельный `gitcmd.git`: знает дерево `files` (путь -> кусок diff)
    и честно применяет к нему pathspec вызова `git diff <range> -- ...`,
    включая исключения `:!`.

    `fail_on_map=True` — git не отвечает ИМЕННО на отдельную меру карты:
    вызов, чей pathspec адресно называет `docs/codebase-map.md` (а не
    забирает её заодно с остальным деревом через `.`). Мера кода, где
    карта приходит исключением `:!`, этим сбоем не затрагивается —
    сценарий AC-7 про вторую цифру, а не про первую.
    """

    def __init__(self, files: dict, fail_on_map: bool = False):
        self.files = files
        self.fail_on_map = fail_on_map

    def __call__(self, *args):
        argv = list(args)
        if argv[:2] == ["rev-parse", "--verify"]:
            # Ref origin/main не заведён — база берётся от локального main.
            return subprocess.CompletedProcess(argv, 1, "", "")
        if argv[0] == "merge-base":
            return subprocess.CompletedProcess(argv, 0, "basesha0\n", "")
        if argv[0] == "diff":
            return self._diff(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    def _diff(self, argv):
        specs = argv[argv.index("--") + 1:] if "--" in argv else []
        excludes = [s[2:] for s in specs if s.startswith(":!")]
        includes = [s for s in specs if not s.startswith(":!")] or ["."]
        addressed = "." not in includes and any(matches(MAP_REL, s)
                                                for s in includes)
        if self.fail_on_map and addressed:
            return subprocess.CompletedProcess(
                argv, 128, "", "fatal: bad object basesha0")
        selected = [p for p in sorted(self.files)
                    if any(matches(p, s) for s in includes)
                    and not any(matches(p, s) for s in excludes)]
        return subprocess.CompletedProcess(
            argv, 0, "\n".join(self.files[p] for p in selected), "")


class CapacityGateMapTest(TmpRootTest):
    """Мера гейта ёмкости с `docs/codebase-map.md` в диффе и без неё."""

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.t = {"title": "Карта в мере гейта ёмкости", "branch": BRANCH}
        self.ceiling = config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES

    def gate(self, files: dict, fail_on_map: bool = False) -> tuple:
        """(отказал ли гейт, склеенный текст журнала отказа)."""
        with mock.patch.object(gitcmd, "git", FakeGit(files, fail_on_map)):
            refused = fsm_advance._capacity_gate_refuses(
                self.conn, TASK_ID, self.t, "in_dev")
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id", (TASK_ID,))]
        return refused, "\n".join(d for d in details if d)

    @staticmethod
    def figure_after(text: str, marker: str) -> str:
        at = text.find(marker)
        return "" if at < 0 else text[at + len(marker):at + len(marker) + FIGURE_WINDOW]

    def test_ac5_map_is_excluded_from_the_measured_diff(self):
        """Diff ветки: код на 1000 байт НИЖЕ потолка плюс карта на 5000
        байт — вместе потолок превышен, код без карты укладывается.

        Гейт обязан пропустить переход: с потолком сравнивается объём diff
        БЕЗ `docs/codebase-map.md`.

        Ловит мутацию: карта исключена только из второй меры (цифры в
        тексте отказа), а pathspec первой меры остался прежним `. :!tasks/
        <id>/` — код укладывается в потолок, а гейт продолжает отказывать.
        """
        files = {
            "orchestrator/models.py": diff_chunk("orchestrator/models.py",
                                                 self.ceiling - 1000),
            MAP_REL: diff_chunk(MAP_REL, 5000),
            f"tasks/{TASK_ID}/PLAN.md": diff_chunk(f"tasks/{TASK_ID}/PLAN.md", 300),
        }

        refused, detail = self.gate(files)

        self.assertFalse(
            refused,
            f"код без карты ({self.ceiling - 1000} байт) укладывается в потолок "
            f"{self.ceiling} — переход обязан пройти:\n{detail}")

    def test_ac6_refusal_names_the_map_volume_as_a_separate_figure(self):
        """Diff ветки: код САМ ПО СЕБЕ выше потолка, плюс карта 5000 байт и
        артефакты задачи 300 байт.

        Отказ обязан назвать объём исключённой карты отдельной цифрой в
        байтах — рядом с цифрой исключённых `tasks/<id>/`, не вместо неё и
        не в сумме с ней.

        Ловит мутацию: цифру карты не вынесли отдельно, а сложили с
        цифрой артефактов задачи в одно число «исключено N байт».
        """
        map_bytes, artifacts_bytes = 5000, 300
        files = {
            "orchestrator/models.py": diff_chunk("orchestrator/models.py",
                                                 self.ceiling + 2000),
            MAP_REL: diff_chunk(MAP_REL, map_bytes),
            f"tasks/{TASK_ID}/PLAN.md": diff_chunk(f"tasks/{TASK_ID}/PLAN.md",
                                                   artifacts_bytes),
        }

        refused, detail = self.gate(files)

        self.assertTrue(refused, f"код выше потолка — отказ:\n{detail}")
        self.assertIn(MAP_REL, detail,
                      f"отказ обязан назвать исключённую карту:\n{detail}")
        map_figure = self.figure_after(detail, MAP_REL)
        self.assertIn(str(map_bytes), map_figure,
                      f"объём карты обязан быть назван цифрой:\n{detail}")
        self.assertIn("байт", map_figure, f"цифра карты — в байтах:\n{detail}")
        artifacts_figure = self.figure_after(detail, f"tasks/{TASK_ID}/")
        self.assertIn(str(artifacts_bytes), artifacts_figure,
                      f"цифра артефактов задачи обязана остаться рядом "
                      f"отдельным числом:\n{detail}")

    def test_ac7_absent_map_keeps_the_verdict_and_unknown_on_git_failure(self):
        """Три вырожденных случая второй меры.

        Карты в диффе нет — цифра карты «0 байт (изменений нет)», а
        решение гейта совпадает с решением до этой задачи: код выше
        потолка отклоняется, код ниже потолка проходит. git не ответил на
        меру карты — цифра «неизвестен», отказ по превышению потолка
        кодом остаётся в силе.

        Ловит мутацию: пустой diff карты измерен как байты
        строки-плейсхолдера `review.EMPTY_DIFF_TEXT` вместо нуля, а сбой
        git на второй мере обработан как отказ всей меры (или как
        пропуск перехода) вместо пометки «неизвестен».
        """
        artifacts = {f"tasks/{TASK_ID}/PLAN.md":
                     diff_chunk(f"tasks/{TASK_ID}/PLAN.md", 300)}
        over = dict(artifacts, **{"orchestrator/models.py": diff_chunk(
            "orchestrator/models.py", self.ceiling + 2000)})

        refused_no_map, detail_no_map = self.gate(over)
        self.assertTrue(
            refused_no_map,
            f"карты нет — решение прежнее, код выше потолка отклоняется:"
            f"\n{detail_no_map}")
        self.assertIn(MAP_REL, detail_no_map,
                      f"цифра карты называется и когда карты нет:\n{detail_no_map}")
        self.assertIn("0 байт", self.figure_after(detail_no_map, MAP_REL),
                      f"карты в диффе нет — цифра карты 0 байт:\n{detail_no_map}")

        self.setUp()
        under = dict(artifacts, **{"orchestrator/models.py": diff_chunk(
            "orchestrator/models.py", self.ceiling - 1000)})
        refused_under, detail_under = self.gate(under)
        self.assertFalse(
            refused_under,
            f"карты нет, код ниже потолка — решение прежнее, переход "
            f"проходит:\n{detail_under}")

        self.setUp()
        with_map = dict(over, **{MAP_REL: diff_chunk(MAP_REL, 5000)})
        refused_failed, detail_failed = self.gate(with_map, fail_on_map=True)
        self.assertTrue(
            refused_failed,
            f"сбой git на мере карты отказ по коду не отменяет:\n{detail_failed}")
        self.assertIn(
            "неизвестен", self.figure_after(detail_failed, MAP_REL),
            f"git не ответил на меру карты — цифра «неизвестен», а не "
            f"вымышленное число:\n{detail_failed}")


if __name__ == "__main__":
    unittest.main()
