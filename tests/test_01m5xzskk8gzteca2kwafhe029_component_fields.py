"""Поля компонента `full_suite` и `ci_job` записи проекта: проверка при загрузке `targets.yaml` и доезд значений до профиля компонента.

Группа: долгоживущий
Красен до реализации: поля `full_suite`/`ci_job` загрузчику неизвестны — запись с ними отказывает «неизвестное поле», контрольная загрузка годной записи падает.

Стенд — временный `config.TARGETS` песочницы (`tmp_root`) с записью
внешнего проекта из одного компонента, дописанной к записи артели;
загрузка — публичный `targets.load()`, профиль — публичные
`project_profile.decide` и `project_profile.component_profiles`. Каждый
отказ проверяется в паре с контрольной загрузкой той же записи, где
нарушение снято: так отказ отличается от отказа по иной причине (текст
«неизвестное поле … (известны: …)» перечисляет все поля и назвал бы
любое из них).

Реестр хостингов — `forge.IMPLEMENTATIONS` (SPEC, требование 1 и AC-3):
подмена реестра — единственный способ получить реализацию без
`job_test_report` для любого значения `forge`, не сравнивая значение с
литералом.
"""
import random
from unittest import mock

import pytest

from orchestrator import config, forge, project_profile, targets
from tests.sandbox import make_project_repo

PROJECT = "uchfullsuite"
COMPONENT_NAMES = ("app", "core", "service", "web")

BASE_FIELDS = {
    "command": "[python3, -m, pytest]",
    "long_lived_dir": "tests",
    "long_lived_name": "test_<id>_<name>.py",
    "weakening_scope": "[tests/**]",
    "mutation_claim_scope": "[tests/test_*.py]",
}


class _WithReport:
    """Реализация хостинга, читающая отчёты тестов заданий."""

    CI_BY_PIPELINE = True

    @staticmethod
    def pipeline_status(target, sha):
        return forge.PipelineStatus(forge.UNKNOWN, "не нужен загрузке")

    @staticmethod
    def job_result(target, sha, job_name):
        return forge.JobResult(None, "не нужен загрузке")

    @staticmethod
    def job_test_report(target, sha, job_name):
        return forge.TestReport(None, "не нужен загрузке")


class _WithoutReport:
    """Реализация хостинга без `job_test_report`."""

    CI_BY_PIPELINE = True

    @staticmethod
    def pipeline_status(target, sha):
        return forge.PipelineStatus(forge.UNKNOWN, "не нужен загрузке")

    @staticmethod
    def job_result(target, sha, job_name):
        return forge.JobResult(None, "не нужен загрузке")


@pytest.fixture
def stand(tmp_root):
    """Песочница с зерном и именем компонента; запись ещё не написана."""
    seed = random.randrange(1 << 32)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    tmp_root.seed = seed
    tmp_root.component = rng.choice(COMPONENT_NAMES)
    tmp_root.job = f"{rng.choice(('full', 'suite', 'pytest'))}-{rng.randrange(1, 99)}"
    tmp_root.artel_text = config.TARGETS.read_text(encoding="utf-8")
    make_project_repo(PROJECT, origin=False)
    return tmp_root


def write_entry(stand, extra: dict, *, forge_value: str = "gitlab",
                drop=()) -> None:
    """Запись проекта из одного компонента: базовые поля, `report`, затем
    `extra`; `drop` — поля, которых в записи нет."""
    fields = dict(BASE_FIELDS, report="junit-xml")
    fields.update(extra)
    for name in drop:
        fields.pop(name, None)
    text = (f"  {PROJECT}:\n"
            f"    forge: {forge_value}\n"
            f"    url: https://localhost/artel-tests/{PROJECT}\n"
            "    base: main\n"
            f"    token_slot: {PROJECT}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n"
            "    components:\n"
            f"      {stand.component}:\n"
            + "".join(f"        {k}: {v}\n" for k, v in fields.items()))
    config.TARGETS.write_text(stand.artel_text.rstrip("\n") + "\n" + text,
                              encoding="utf-8")


def refusal(stand) -> str:
    """Текст отказа загрузки; запись загрузилась — провал с зерном."""
    try:
        targets.load()
    except targets.TargetsError as exc:
        return str(exc)
    pytest.fail(f"запись загрузилась, ожидался отказ; зерно: {stand.seed}")


def loads(stand) -> dict:
    """Записи после загрузки; отказ — провал с текстом и зерном."""
    try:
        return targets.load()
    except targets.TargetsError as exc:
        pytest.fail(f"годная запись не загрузилась: {exc}; зерно: {stand.seed}")


@pytest.mark.parametrize("mode", ["ci", "both"])
def test_ac1_ci_or_both_without_ci_job_refused(stand, mode):
    """Компонент `full_suite: ci`/`both` без `ci_job` не загружается, отказ называет `ci_job`.

    Контроль: та же запись с `ci_job` загружается — отказ дан именно за
    отсутствие имени задания.

    Ловит мутацию: обязательность `ci_job` проверяется только при `ci`
    (а `both` пропущен) или не проверяется вовсе — запись без `ci_job`
    загружается, и `refusal` не получает исключения.
    """
    write_entry(stand, {"full_suite": mode})
    text = refusal(stand)
    assert "ci_job" in text, f"{text}; зерно: {stand.seed}"

    write_entry(stand, {"full_suite": mode, "ci_job": stand.job})
    assert PROJECT in loads(stand)


@pytest.mark.parametrize("full_suite", ["local", None])
def test_ac2_ci_job_with_local_refused(stand, full_suite):
    """`ci_job` при `full_suite: local` и при отсутствии `full_suite` — отказ загрузки, называющий `ci_job`.

    Контроль: та же запись без `ci_job` загружается.

    Ловит мутацию: запрет `ci_job` проверяется только при явном
    `full_suite: local`, а умолчание (поля нет) пропущено — запись с
    `ci_job` без `full_suite` загружается молча.
    """
    extra = {"ci_job": stand.job}
    if full_suite is not None:
        extra["full_suite"] = full_suite
    write_entry(stand, extra)
    text = refusal(stand)
    assert "ci_job" in text, f"{text}; зерно: {stand.seed}"

    write_entry(stand, {} if full_suite is None else {"full_suite": full_suite})
    assert PROJECT in loads(stand)


@pytest.mark.parametrize("mode", ["ci", "both"])
def test_ac3_forge_without_job_test_report_refused(stand, mode):
    """`full_suite: ci`/`both` у записи, чья реализация хостинга в реестре `forge` без `job_test_report`, — отказ, называющий `full_suite`.

    Для каждого значения `forge` из `targets.FORGES` реестр
    `forge.IMPLEMENTATIONS` подменён: реализация без `job_test_report` —
    отказ, с ним — запись загружается.

    Ловит мутацию: проверка сравнивает значение `forge` с литералом
    (`== "gitlab"`) вместо чтения реестра — у `github` с подменённой
    реализацией, читающей отчёты, запись не загрузится, а у `gitlab` без
    `job_test_report` — загрузится.
    """
    extra = {"full_suite": mode, "ci_job": stand.job}
    for value in targets.FORGES:
        write_entry(stand, extra, forge_value=value)
        with mock.patch.dict(forge.IMPLEMENTATIONS, {value: _WithoutReport}):
            text = refusal(stand)
        assert "full_suite" in text, f"{value}: {text}; зерно: {stand.seed}"
        with mock.patch.dict(forge.IMPLEMENTATIONS, {value: _WithReport}):
            assert PROJECT in loads(stand), value


@pytest.mark.parametrize("mode", ["ci", "both"])
def test_ac4_ci_or_both_without_report_refused(stand, mode):
    """`full_suite: ci`/`both` с `ci_job`, но без `report` — отказ загрузки, называющий `report`.

    Контроль: та же запись с `report` загружается.

    Ловит мутацию: требование `report` проверяется только при `ci`
    (`both` пропущен) — запись `both` без `report` загружается, и граница
    гейта исходов (`in_outcome_bounds`) остаётся без отчёта.
    """
    write_entry(stand, {"full_suite": mode, "ci_job": stand.job},
                drop=("report",))
    text = refusal(stand)
    assert "report" in text, f"{text}; зерно: {stand.seed}"

    write_entry(stand, {"full_suite": mode, "ci_job": stand.job})
    assert PROJECT in loads(stand)


def test_ac5_profile_carries_full_suite_and_ci_job(stand):
    """Годный компонент `ci` загружается, его профиль несёт `full_suite` и `ci_job`; компонент без полей — `full_suite` = `local`.

    Профиль читается двумя публичными входами: `project_profile.decide`
    (запись из одного компонента) и `project_profile.component_profiles`.

    Ловит мутацию: поля проверяются загрузчиком, но не переносятся в
    профиль одного из входов (`decide` или `component_profiles`) — он несёт
    умолчание `local` при `full_suite: ci` (или пустой `ci_job`), и
    приёмка молча гоняет полный набор локально.
    """
    write_entry(stand, {"full_suite": "ci", "ci_job": stand.job})
    assert PROJECT in loads(stand)
    decided = project_profile.decide(PROJECT).profile
    listed = project_profile.component_profiles(PROJECT)
    for where, profile in (("decide", decided), ("component_profiles",
                                                  listed[0])):
        assert profile is not None, where
        assert profile.full_suite == "ci", f"{where}; зерно: {stand.seed}"
        assert profile.ci_job == stand.job, f"{where}; зерно: {stand.seed}"

    write_entry(stand, {})
    assert PROJECT in loads(stand)
    decided = project_profile.decide(PROJECT).profile
    listed = project_profile.component_profiles(PROJECT)
    for where, profile in (("decide", decided), ("component_profiles",
                                                  listed[0])):
        assert profile is not None, where
        assert profile.full_suite == "local", f"{where}; зерно: {stand.seed}"


@pytest.mark.parametrize("value", ["remote", "Local", "CI", "both-ci"])
def test_ac14_full_suite_out_of_range_refused(stand, value):
    """`full_suite` со значением вне `local | ci | both` — отказ загрузки, называющий `full_suite`.

    Контроль: та же запись с `full_suite: local` загружается — значение
    из перечня поле принимает.

    Ловит мутацию: проверка значения сравнивает без учёта регистра или
    по вхождению подстроки (`"ci" in value`) — `CI`/`both-ci` загружаются
    и затем ведут себя как неизвестный режим.
    """
    write_entry(stand, {"full_suite": value})
    text = refusal(stand)
    assert "full_suite" in text, f"{text}; зерно: {stand.seed}"

    write_entry(stand, {"full_suite": "local"})
    assert PROJECT in loads(stand)
