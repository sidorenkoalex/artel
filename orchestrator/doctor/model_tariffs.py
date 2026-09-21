"""Проверки действующего тарифа моделей (SPEC 01M300A14KRHCFB0DQXVCBJEKF,
требование 8): тариф свеж и тариф не старше смены модели у роли.

Обе отвечают на вопрос, которого пульт не задавал до инцидента
13.09-20.09: «по той ли цене мы сейчас считаем деньги». Первая ловит
протухший прейскурант (цена не пересматривалась кварталом), вторая —
смену модели у роли, прошедшую мимо тарифа (роль уже ходит на другой
модели, а цена осталась от прежней).

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from datetime import date

from orchestrator import doctor

FRESHNESS_CHECK = "model-tariff-age"
MODEL_CHANGE_CHECK = "model-tariff-vs-model-change"


def _tariff_age_days(calibrated_at: str):
    """Возраст даты тарифа в днях; `None` — дата не читается как дата.

    Отдельно от самой проверки, потому что «дата в будущем» — не ошибка
    формата: прейскурант, объявленный вперёд, имеет отрицательный
    возраст и потолок не превышает.
    """
    try:
        return (date.today() - date.fromisoformat(calibrated_at)).days
    except (TypeError, ValueError):
        return None


def _resolved_roles(catalog, local) -> dict:
    """{роль: разрешённая цепочка} — по одной записи на agent-роль.

    Слои читает и передаёт сюда вызывающий (`models.layers_or_none`),
    тем же приёмом, что `check_models_local`: обе проверки ниже
    спрашивают об одном и том же — действующая модель роли и дата её
    тарифа, — и разрешать цепочку каждой роли по второму разу внутри
    каждой из них значило бы читать оба файла слоёв на прогон `doctor`
    вчетверо против нужного.

    Роль с неразрешимой цепочкой сюда не попадает: её причину называет
    строка `models-local`, дублировать её второй красной строкой незачем.
    """
    resolved = {}
    for role in doctor.agent_roles():
        try:
            resolved[role] = doctor.models.resolve_role(role, catalog, local)
        except doctor.models.ModelsError:
            continue
    return resolved


def check_model_tariff_freshness() -> doctor.Check:
    """Дата действующего тарифа каждой модели, на которой идут роли, не
    старше `config.MODEL_TARIFF_MAX_AGE_DAYS` (требование 8а, AC-10).

    Не-ok — `warn`, не `fail`: протухшая цена не мешает шагу стартовать,
    она искажает учёт, и Оператор чинит её правкой прейскуранта
    (`doc-commit models.yaml`) или собственного тарифа локального слоя, а
    не немедленной остановкой конвейера. Строка называет и модель, и саму
    дату: «тариф протух» без этих двух вещей чинить не с чего.

    Ни одной разрешимой цепочки — `skip`: сверять нечего, и это не
    молчаливое «ок» (причину уже назвали `models-catalog`/`models-local`).
    """
    horizon = doctor.config.MODEL_TARIFF_MAX_AGE_DAYS
    catalog, local = doctor.models.layers_or_none()
    # Одна запись на МОДЕЛЬ: две роли одного яруса разрешают один тариф,
    # и сверять его дважды — две одинаковые строки в выводе.
    tariffs = {resolved.model: (resolved.calibrated_at,
                                resolved.tariff_source)
               for resolved in _resolved_roles(catalog, local).values()}
    if not tariffs:
        return doctor.Check(FRESHNESS_CHECK, "skip",
                            "действующий тариф не разрешён ни для одной "
                            "роли — свежесть сверять не с чем")
    stale, fresh = [], []
    for model_id in sorted(tariffs):
        calibrated_at, source_kind = tariffs[model_id]
        age = _tariff_age_days(calibrated_at)
        if age is None:
            stale.append(f"{model_id}: дата тарифа {calibrated_at!r} "
                         f"({source_kind}) не читается как дата")
        elif age > horizon:
            stale.append(f"{model_id}: тариф от {calibrated_at} "
                         f"({source_kind}) старше {horizon} дней — {age}")
        else:
            fresh.append(f"{model_id}: {calibrated_at}")
    if stale:
        return doctor.Check(FRESHNESS_CHECK, "warn",
                            f"давность тарифа: {'; '.join(stale)} — "
                            f"пересверь цену с фактом CLI и обнови "
                            f"прейскурант либо собственный тариф")
    return doctor.Check(FRESHNESS_CHECK, "ok",
                        f"тариф свеж (потолок {horizon} дней): "
                        f"{', '.join(fresh)}")


def _foreign_model_steps(conn, catalog, local) -> dict:
    """{(роль, модель): последний `ts`} по строкам журнала «agent cost
    KNOWN»: какая роль на какой модели ходила и когда в последний раз.

    Журнал читается один раз на всю проверку (`store.all_tasks` +
    `store.task_steps`, тем же приёмом, что `spend.known_cost_pairs`), а
    не по проходу на роль: ролей четыре, а строк журнала — тысячи.

    Строка, чьё поле `model=` не разрешается в модель каталога (метка
    «дефолт CLI», формат до 19.09, модель, которую из каталога убрали), в
    счёт не идёт — тот же тихий пропуск, что и в `spend.known_cost_pairs`
    (SPEC 01M300A14KRHCFB0DQXVCBJEKF, требование 3): иначе любой журнал
    старше 19.09 давал бы вечное предупреждение о «смене модели»,
    которой не было.
    """
    known: dict = {}
    latest: dict = {}
    for task in doctor.store.all_tasks(conn):
        for row in doctor.store.task_steps(conn, task["id"]):
            if row["action"] != doctor.spend.KNOWN_COST_JOURNAL_ACTION:
                continue
            model_id = doctor.spend.journal_model(row["detail"])
            if model_id is None or not row["ts"]:
                continue
            if model_id not in known:
                known[model_id] = doctor.spend.model_tariff(
                    model_id, catalog, local) is not None
            if not known[model_id]:
                continue
            key = (row["actor"], model_id)
            if row["ts"] > latest.get(key, ""):
                latest[key] = row["ts"]
    return latest


def check_model_tariff_vs_model_change(conn) -> doctor.Check:
    """Тариф не старше смены модели у роли (требование 8б, AC-11).

    Условие предупреждения: у роли есть строка «agent cost KNOWN» с
    ДРУГОЙ моделью, записанная ПОЗЖЕ даты действующего тарифа её
    сегодняшней модели. Это и есть отпечаток инцидента 13.09-20.09 в
    журнале: роль уже ходит на новой модели, а цена, по которой считают
    её шаги, датирована временем старой — учёт расходится с фактом CLI
    молча.

    Строка без опознаваемой модели (старый формат до 19.09, метка
    «дефолт CLI») в сверку не входит: отнести её к какой-либо модели
    нечем (тот же тихий пропуск, что и в `spend.known_cost_pairs`).
    """
    catalog, local = doctor.models.layers_or_none()
    roles = _resolved_roles(catalog, local)
    if not roles:
        return doctor.Check(MODEL_CHANGE_CHECK, "skip",
                            "действующий тариф не разрешён ни для одной "
                            "роли — сверять смену модели не с чем")
    latest = _foreign_model_steps(conn, catalog, local)
    findings = []
    for (actor, model_id), ts in sorted(latest.items()):
        resolved = roles.get(actor)
        # Строка роли, которой в карте ярусов больше нет (или цепочка
        # которой не разрешается), сверять не с чем — её причину уже
        # назвала строка `models-local`.
        if resolved is None or model_id == resolved.model:
            continue
        if ts[:len(resolved.calibrated_at)] <= resolved.calibrated_at:
            continue
        findings.append(
            f"{actor}: шаг на модели {model_id} от {ts} новее тарифа "
            f"модели {resolved.model} (с {resolved.calibrated_at})")
    if findings:
        return doctor.Check(MODEL_CHANGE_CHECK, "warn",
                            f"тариф старше смены модели у роли: "
                            f"{'; '.join(findings)} — пересверь тариф "
                            f"действующей модели")
    return doctor.Check(MODEL_CHANGE_CHECK, "ok",
                        "тариф не старше смены модели у роли: шагов на "
                        "чужой модели новее даты тарифа в журнале нет")
