"""Уборка сирот не трогает каталог origin канарейки, ещё не получивший маркер владельца.

Группа: долгоживущий
Красен до реализации: `canary` заводит `artel-canary-origin-*` через `tempfile.mkdtemp` и пишет в него маркер владельца только после `git clone --bare`, а ссылку клона на него — ещё позже; уборка `doctor --fix` на любом вызове git в этом окне видит каталог без маркера и без ссылки и удаляет его.

Связка, которую держит тест: настоящий `canary.cmd_canary` (как в
`tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`: ведение клона —
поддельный процесс с готовым итогом, `catalog.cmd_init` подменён) — и
настоящая уборка сирот `doctor.cmd_doctor(fix=True)` (проверки `all_checks`
пусты, остаются только починки). Временный каталог процесса —
`tempfile.tempdir`/`TMPDIR` — подменён каталогом внутри корня песочницы:
уборка идёт только во временном корне этого теста, не в системном.

Уборка «другого процесса» разыгрывается в окне между созданием каталога
origin и записью маркера: перед каждым вызовом git, который канарейка
делает, пока во временном корне есть каталог `artel-canary-origin-*`,
вызов git задерживается и выполняется уборка — ровно то, что видит
параллельный процесс xdist, если его уборка совпала с этим вызовом git.
Владелец каталога — этот процесс, он жив; защищает каталог только то, что
канарейка успела записать к этому моменту. Контроль того, что уборка
вообще работает, — каталог origin мёртвого владельца (маркер с pid
несуществующего процесса, имя от зерна) — его первая же уборка удаляет.
"""

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from orchestrator import canary, catalog, config, doctor, liveness
from tests.sandbox import ALL_CONFIG_ATTRS, RealGitSandbox, capture

ORIGIN_PREFIX = "artel-canary-origin-"
DEAD_PID = "99999999"
MAX_SWEEPS = 12


class OriginSweepTest(RealGitSandbox):
    """Канарейка в песочнице и уборка сирот на каждом её вызове git."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.temp_root = self.root / ".artel" / "origin-sweep-tmp"
        self.temp_root.mkdir(parents=True)
        for patcher in (mock.patch.object(tempfile, "tempdir", str(self.temp_root)),
                        mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root)})):
            patcher.start()
            self.addCleanup(patcher.stop)
        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# ведение заменено тестом\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture drive")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.home = self.root / ".artel" / "origin-sweep-home"
        pool = self.home / config.CANARY_POOL_DIRNAME
        pool.mkdir(parents=True)
        (pool / "fixture.md").write_text("# учебная задача\n", encoding="utf-8")
        self.sweeping = False
        self.sweeps = []
        self.control = None
        self.outer_paths = {attr: getattr(config, attr) for attr in ALL_CONFIG_ATTRS}

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def dead_origin(self) -> Path:
        """Каталог origin мёртвого владельца — сирота по построению."""
        name = "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(8))
        path = self.temp_root / f"{ORIGIN_PREFIX}dead{name}"
        path.mkdir()
        (path / liveness.CANARY_OWNER_MARKER).write_text(
            DEAD_PID, encoding="utf-8")
        return path

    def origins(self) -> list:
        """Каталоги origin канарейки во временном корне (верхний уровень и
        уровнем ниже), кроме контрольного."""
        found = [p for pattern in (f"{ORIGIN_PREFIX}*", f"*/{ORIGIN_PREFIX}*")
                 for p in self.temp_root.glob(pattern) if p.is_dir()]
        return sorted(p for p in found if p != self.control)

    def sweep(self, argv: list) -> None:
        """Уборка сирот перед вызовом git канарейки, пока origin существует."""
        present = self.origins()
        if not present or len(self.sweeps) >= MAX_SWEEPS:
            return
        if self.control is None:
            self.control = self.dead_origin()
        self.sweeping = True
        try:
            # Уборка — чужой процесс со своими путями пульта: внутри клона
            # канарейка переключает пути `config` на клон, уборка их не видит.
            with mock.patch.multiple(config, **self.outer_paths), \
                 mock.patch.object(doctor, "all_checks", return_value=[]):
                out = capture(lambda: doctor.cmd_doctor(fix=True))
        finally:
            self.sweeping = False
        self.sweeps.append({"git": " ".join(map(str, argv[:4])),
                            "present": [str(p) for p in present],
                            "gone": [str(p) for p in present if not p.exists()],
                            "control_gone": not self.control.exists(),
                            "doctor": out[-1500:]})

    def run_canary(self) -> str:
        real_popen = subprocess.Popen

        def launch(argv, *args, **kwargs):
            argv_list = [argv] if isinstance(argv, (str, bytes)) else list(argv)
            if argv_list[:3] == [sys.executable, "-m", canary.CANARY_DRIVE_MODULE]:
                result = Path(argv_list[argv_list.index("--result") + 1])
                result.write_text(json.dumps({
                    "task_id": "01FIXTURE", "head": self.sha,
                    "outcome": "killed", "escalated": False,
                    "metrics": {"steps": 1, "cost_usd": 0.0,
                                "review_iterations": 0, "escalations": [],
                                "dev_retries": 0, "outcome": "killed",
                                "kill_note": "штатно",
                                "test_author_visited": False,
                                "ceiling_exhausted": False,
                                "ceiling_raise": None},
                    "steps": [],
                }), encoding="utf-8")
                return real_popen([sys.executable, "-c", "pass"], *args, **kwargs)
            if (not self.sweeping and argv_list
                    and Path(str(argv_list[0])).name == "git"):
                self.sweep(argv_list)
            return real_popen(argv, *args, **kwargs)

        buf = []
        with mock.patch.object(Path, "home", return_value=self.home), \
             mock.patch.object(catalog, "cmd_init"), \
             mock.patch.object(subprocess, "Popen", launch):
            try:
                buf.append(capture(lambda: canary.cmd_canary(
                    k=1, sha=self.sha, templates=["fixture"])))
            except SystemExit as exc:
                buf.append(f"SystemExit: {exc.code}")
            except RuntimeError as exc:
                buf.append(f"RuntimeError: {exc}")
        for leftover in self.temp_root.iterdir():
            shutil.rmtree(leftover, ignore_errors=True)
        return "".join(buf)

    def test_ac7_sweep_keeps_origin_created_before_owner_marker(self):
        """Уборка на каждом вызове git канарейки не удаляет её каталог origin.

        Сценарий: `canary.cmd_canary` в песочнице; перед каждым вызовом git
        канарейки, пока во временном корне есть `artel-canary-origin-*`,
        идёт `doctor --fix` (только починки) — в том числе в окне между
        созданием каталога и записью маркера владельца. После каждой
        уборки все каталоги origin, бывшие до неё, на месте; контрольный
        origin мёртвого владельца первой же уборкой удалён (уборка
        действует); прогон канарейки не отказывает «origin-заглушка не
        создана».

        Ловит мутацию: маркер владельца пишется в origin только после
        `git clone --bare` (прежний порядок) — уборка на `git clone` клона
        удаляет пустой origin без маркера, сообщение называет вызов git и
        каталог; защита origin держится лишь на ссылке remote клона,
        которая появляется после `git remote set-url`, — то же на любом
        более раннем вызове git; уборка переведена на проверку маркера
        без pid (любой маркер — «жив») — контрольный мёртвый origin не
        удалён.
        """
        out = self.run_canary()
        self.assertTrue(self.sweeps, self.note(
            f"канарейка не завела каталог {ORIGIN_PREFIX}* во временном "
            f"каталоге процесса ни к одному вызову git:\n{out[-3000:]}"))
        self.assertTrue(self.sweeps[0]["control_gone"], self.note(
            f"уборка не удалила origin мёртвого владельца — уборка не "
            f"действует:\n{self.sweeps[0]['doctor']}"))
        lost = [f"перед «{s['git']}» удалено: {s['gone']}"
                for s in self.sweeps if s["gone"]]
        self.assertEqual(lost, [], self.note(
            "уборка удалила каталог origin живой канарейки:\n"
            + "\n".join(lost)))
        self.assertNotIn("origin-заглушка не создана", out, self.note(out[-3000:]))
