"""Personalized financial-literacy tips based on current-period analytics.

Tips are intentionally sharp: each one highlights a specific pain and gives one
actionable step. Books are attached as "where to go deeper".
"""

from counta.core import catalog

# role order for priority when multiple tips match
_ROLE_PRIORITY = {
    "expense_gt_income": 0,
    "no_savings": 1,
    "housing_high": 2,
    "debt": 3,
    "wants_gt_needs": 4,
    "goal_low": 5,
    "subscriptions_high": 6,
    "eating_out_gt_food": 7,
    "shopping_high": 8,
    "fun_high": 9,
    "travel_high": 10,
    "family_high": 11,
    "transport_high": 12,
    "health_zero": 13,
    "no_education": 14,
    "gratitude": 15,
    "praise_green": 16,
}


def _localize(texts: dict, lang: str) -> str:
    return texts.get(lang, texts.get("ru", ""))


# Every tip: id, texts (ru/en/ko), condition(report), book.
# Conditions receive a normalized report dict:
#   total_income, total_expense, total_need, total_want, total_goal,
#   categories: {key: amount}, currency_groups: raw groups from /api/report.
TIP_CATALOG = [
    {
        "id": "expense_gt_income",
        "texts": {
            "ru": {"title": "Вы живёте за счёт будущего себя", "body": "Расходы превысили доходы. Найдите сегодня одну трату, которую можно отложить или сократить."},
            "en": {"title": "You're borrowing from your future self", "body": "Expenses exceeded income. Find one spend you can delay or cut today."},
            "ko": {"title": "미래의 자신에게 빌려 살고 있습니다", "body": "지출이 수입을 초과했습니다. 오늘 미루거나 줄일 수 있는 지출 하나를 찾으세요."},
        },
        "book": "Morgan Housel — The Psychology of Money",
        "condition": lambda r: r["total_expense"] > r["total_income"] and r["total_income"] > 0,
    },
    {
        "id": "no_savings",
        "texts": {
            "ru": {"title": "Вы платите всем, кроме себя", "body": "В этом периоде нет отложенного. Переведите 10% дохода в сбережения сразу при получении — до того, как деньги растворятся."},
            "en": {"title": "You're paying everyone except yourself", "body": "No savings this period. Move 10% of income to savings the moment you receive it."},
            "ko": {"title": "자신 외 모두에게 지불하고 있습니다", "body": "이 기간 저축이 없습니다. 돈이 사라지기 전에 수입의 10%를 저축으로 옮기세요."},
        },
        "book": "George Clason — The Richest Man in Babylon",
        "condition": lambda r: r["total_goal"] == 0 and r["total_income"] > 0,
    },
    {
        "id": "housing_high",
        "texts": {
            "ru": {"title": "Жильё съедает больше трети", "body": "Вы работаете больше месяца в году только на крышу над головой. Пересмотрите аренду, тарифы или страховки."},
            "en": {"title": "Housing eats more than a third", "body": "You work more than a month per year just for a roof. Review rent, utilities or insurance."},
            "ko": {"title": "주거비가 3분의 1 이상", "body": "지붕을 위해 1년 중 한 달 이상 일합니다. 임대료, 공과금, 보험을 재검토하세요."},
        },
        "book": "Thomas Stanley — The Millionaire Next Door",
        "condition": lambda r: r["categories"].get("cat_housing", 0) > r["total_income"] * 0.30 and r["total_income"] > 0,
    },
    {
        "id": "debt",
        "texts": {
            "ru": {"title": "Долг крадёт ваше будущее", "body": "Прошлое не должно управлять вашим завтра. Закройте самый маленький долг агрессивно — первая победа даст импульс."},
            "en": {"title": "Debt is stealing your future", "body": "Your past shouldn't run your tomorrow. Attack the smallest debt first for momentum."},
            "ko": {"title": "빚이 미래를 훔치고 있습니다", "body": "과거가 내일을 지배하지 않게 하세요. 가장 작은 빚부터 공격적으로 갚아 모멘텀을 만드세요."},
        },
        "book": "Dave Ramsey — The Total Money Makeover",
        "condition": lambda r: r["total_debt"] > 0,
    },
    {
        "id": "subscriptions_high",
        "texts": {
            "ru": {"title": "Подписки исчезают из головы, но не из выписки", "body": "Проведите аудит: отмените всё, что вы не использовали за последние 30 дней."},
            "en": {"title": "Subscriptions vanish from memory, not statements", "body": "Audit them: cancel anything you haven't used in the last 30 days."},
            "ko": {"title": "구독은 기억에서 사라지지만 명세서는 아닙니다", "body": "점검하세요: 최근 30일 동안 사용하지 않은 구독을 모두 해지하세요."},
        },
        "book": "Ramit Sethi — I Will Teach You to Be Rich",
        "condition": lambda r: r["categories"].get("cat_fun_subscriptions", 0) > r["total_expense"] * 0.10 and r["total_expense"] > 0,
    },
    {
        "id": "eating_out_gt_food",
        "texts": {
            "ru": {"title": "Вы кормите рестораны, а не себя", "body": "Траты на еду вне дома превысили продукты. Попробуйте неделю готовить дома — разница в бюджете и самочувствии ощутима."},
            "en": {"title": "You're feeding restaurants, not yourself", "body": "Eating out beat groceries. Try one week of home cooking and feel the budget difference."},
            "ko": {"title": "식당을 먹이고 있습니다", "body": "외식비가 식료품을 넘었습니다. 일주일간 집에서 요리해 예산 차이를 느껴 보세요."},
        },
        "book": "Vicki Robin — Your Money or Your Life",
        "condition": lambda r: r["categories"].get("cat_eating_out", 0) > r["categories"].get("cat_food", 0),
    },
    {
        "id": "shopping_high",
        "texts": {
            "ru": {"title": "Вещи обещают счастье, но крадут свободу", "body": "Перед покупкой спросите: 'Готов ли я отдать за это часы жизни, на которые заработал?' Если нет — отложите на 30 дней."},
            "en": {"title": "Stuff promises happiness but steals freedom", "body": "Before buying, ask: 'Am I willing to trade the life-hours I earned this for?' If not, wait 30 days."},
            "ko": {"title": "물건은 행복을 약속하지만 자유를 훔칩니다", "body": "구매 전 스스로에게 물으세요: '이것을 위해 번 시간을 희생할 의사가 있나요?' 아니라면 30일 미루세요."},
        },
        "book": "Vicki Robin — Your Money or Your Life",
        "condition": lambda r: r["categories"].get("cat_shopping_stuff", 0) > r["total_expense"] * 0.15 and r["total_expense"] > 0,
    },
    {
        "id": "no_education",
        "texts": {
            "ru": {"title": "Вы не вкладываете в главный актив — себя", "body": "90 дней без инвестиций в навыки. Купите книгу или курс — это единственная инвестиция с гарантированной доходностью."},
            "en": {"title": "You're not investing in your best asset — you", "body": "90 days without skill spending. Buy a book or course; it's the only guaranteed-return investment."},
            "ko": {"title": "최고의 자산인 자신에게 투자하지 않고 있습니다", "body": "90일 동안 기술 투자가 없습니다. 책이나 강의를 사세요. 유일한 보장 수익 투자입니다."},
        },
        "book": "Robert Kiyosaki — Rich Dad Poor Dad",
        "condition": lambda r: r["categories"].get("cat_education_growth", 0) == 0,
    },
    {
        "id": "fun_high",
        "texts": {
            "ru": {"title": "Развлечения стали главной статьёй", "body": "Бюджет не должен вращаться вокруг досуга. Бесплатный отдых — прогулки, библиотека, друзья — часто радует больше."},
            "en": {"title": "Entertainment became the main budget line", "body": "Budget shouldn't revolve around leisure. Free rest — walks, library, friends — often brings more joy."},
            "ko": {"title": "여가가 주요 예산 항목이 되었습니다", "body": "예산이 여가에 맞춰져서는 안 됩니다. 산책, 도서관, 친구들과의 물리적 휴식이 더 큰 기쁨을 줍니다."},
        },
        "book": "JL Collins — The Simple Path to Wealth",
        "condition": lambda r: r["categories"].get("cat_fun_subscriptions", 0) > r["total_expense"] * 0.15 and r["total_expense"] > 0,
    },
    {
        "id": "transport_high",
        "texts": {
            "ru": {"title": "Транспорт превратился в дыру", "body": "Сравните такси, общественный транспорт и личный авто. Часто самый удобный вариант — не самый дешёвый."},
            "en": {"title": "Transport became a leak", "body": "Compare taxi, public transit and owning a car. The most convenient option is often not the cheapest."},
            "ko": {"title": "교통비가 누수로 변했습니다", "body": "택시, 대중교통, 자차를 비교해 보세요. 가장 편한 선택이 가장 저렴한 것은 아닙니다."},
        },
        "book": "Scott Pape — The Barefoot Investor",
        "condition": lambda r: r["categories"].get("cat_transport", 0) > r["total_expense"] * 0.15 and r["total_expense"] > 0,
    },
    {
        "id": "health_zero",
        "texts": {
            "ru": {"title": "Экономия на здоровье — самая дорогая экономия", "body": "В этом месяце нет трат на здоровье. Профилактика сегодня стоит копеек по сравнению с лечением завтра."},
            "en": {"title": "Saving on health is the most expensive saving", "body": "No health spending this month. Prevention today costs pennies compared to treatment tomorrow."},
            "ko": {"title": "건강에 아끼는 것이 가장 비싼 절약입니다", "body": "이번 달 건강 지출이 없습니다. 예방은 내일 치료비와 비교하면 푼돈입니다."},
        },
        "book": "Morgan Housel — The Psychology of Money",
        "condition": lambda r: r["categories"].get("cat_health_wellness", 0) == 0 and r["total_expense"] > 0,
    },
    {
        "id": "income_up_savings_flat",
        "texts": {
            "ru": {"title": "Доход вырос, а сбережения — нет", "body": "Эффект образа жизни: расходы подстроились под доход. Прибавку надо автоматически перенаправлять в цели."},
            "en": {"title": "Income rose but savings didn't", "body": "Lifestyle creep: spending adjusted to income. Auto-redirect raises to goals before you notice them."},
            "ko": {"title": "수입은 늘었지만 저축은 아닙니다", "body": "라이프스타일 크립: 지출이 수입에 맞춰졌습니다. 알아차리기 전에 인상분을 목표로 자동 이체하세요."},
        },
        "book": "JL Collins — The Simple Path to Wealth",
        "condition": lambda r: False,  # requires trend data; disabled until trend analytics built
    },
    {
        "id": "net_positive_streak",
        "texts": {
            "ru": {"title": "Вы стабильно в плюсе", "body": "Отличная работа. Следующий шаг — экстренный фонд на 3–6 месяцев расходов. Спокойствие дороже доходности."},
            "en": {"title": "You're consistently in the green", "body": "Great job. Next step: an emergency fund covering 3–6 months of expenses. Peace beats returns."},
            "ko": {"title": "꾸준히 흑자입니다", "body": "잘하고 있습니다. 다음 단계: 3~6개월 지출을 커버하는 비상자금입니다. 안정이 수익보다 소중합니다."},
        },
        "book": "JL Collins — The Simple Path to Wealth",
        "condition": lambda r: r["total_income"] > r["total_expense"] and r["total_goal"] > 0,
    },
    {
        "id": "travel_high",
        "texts": {
            "ru": {"title": "Путешествия съедают будущее", "body": "Путешествия важны, но не за счёт подушки безопасности. Откладывайте на поездку заранее, а не на кредитке."},
            "en": {"title": "Travel is eating your future", "body": "Travel matters, but not at the cost of your safety net. Save for trips in advance, not on credit."},
            "ko": {"title": "여행이 미래를 먹고 있습니다", "body": "여행은 중요하지만 안전망을 희생해서는 안 됩니다. 신용카드가 아닌 미리 저축하세요."},
        },
        "book": "Bill Perkins — Die with Zero",
        "condition": lambda r: r["categories"].get("cat_travel", 0) > r["total_income"] * 0.20 and r["total_income"] > 0,
    },
    {
        "id": "family_high",
        "texts": {
            "ru": {"title": "Семья не должна съедать всё", "body": "Дети — не инвестиция, но и их потребности не могут поглощать бюджет. Введите лимит на импульсные семейные покупки."},
            "en": {"title": "Family shouldn't devour everything", "body": "Kids aren't an investment, but their needs can't swallow the budget. Cap impulse family spending."},
            "ko": {"title": "가족이 모든 것을 삼켜서는 안 됩니다", "body": "아이들은 투자가 아니지만 그들의 필요가 예산을 삼켜서는 안 됩니다. 충동적 가족 지출에 한도를 정하세요."},
        },
        "book": "Ron Lieber — The Opposite of Spoiled",
        "condition": lambda r: r["categories"].get("cat_family_kids", 0) > r["total_expense"] * 0.25 and r["total_expense"] > 0,
    },
    {
        "id": "wants_gt_needs",
        "texts": {
            "ru": {"title": "Хочу обогнали нужды", "body": "Лайфстайл в обычный месяц не должен превышать базовые траты. Пересмотрите хотя бы одну категорию 'хочу'."},
            "en": {"title": "Wants overtook needs", "body": "In a normal month, lifestyle shouldn't exceed basics. Review at least one 'want' category."},
            "ko": {"title": "원하는 것이 필요를 앞섰습니다", "body": "평범한 달에 라이프스타일이 기본 지출을 초과해서는 안 됩니다. '원하는 것' 카테고리 하나를 검토하세요."},
        },
        "book": "Vicki Robin — Your Money or Your Life",
        "condition": lambda r: r["total_want"] > r["total_need"] and r["total_need"] > 0,
    },
    {
        "id": "goal_low",
        "texts": {
            "ru": {"title": "Вы работаете на сегодня, но не на завтра", "body": "На финансовые цели уходит меньше 10% дохода. Даже 5% в месяц создадут подушку через год. Начните с малого."},
            "en": {"title": "You're working for today, not tomorrow", "body": "Less than 10% of income goes to goals. Even 5% monthly builds a cushion in a year. Start small."},
            "ko": {"title": "오늘을 위해 일하지 내일은 아닙니다", "body": "수입의 10% 미만이 목표에 사용됩니다. 매달 5%만으로도 1년이면 쿠션이 생깁니다. 작게 시작하세요."},
        },
        "book": "George Clason — The Richest Man in Babylon",
        "condition": lambda r: r["total_goal"] < r["total_income"] * 0.10 and r["total_income"] > 0,
    },
    {
        "id": "mindful_checkout",
        "texts": {
            "ru": {"title": "Стоя на кассе, задумайтесь", "body": "Точно ли этот товар стоит часов жизни, которые вы отдали, чтобы его заработать?"},
            "en": {"title": "At the checkout, pause", "body": "Is this item really worth the life-hours you traded to earn it?"},
            "ko": {"title": "계산대에서 잠시 멈추세요", "body": "이 물건이 정말 이를 위해 번 시간만큼 가치가 있나요?"},
        },
        "book": "Vicki Robin — Your Money or Your Life",
        "condition": lambda r: False,  # fallback only
    },
    {
        "id": "first_week",
        "texts": {
            "ru": {"title": "Идеальная категория — враг записи", "body": "Не гонитесь за идеалом. Лучше неточная запись, чем отсутствие записи. Внесите хотя бы одну трату сегодня."},
            "en": {"title": "Perfect categorization is the enemy of tracking", "body": "Don't chase perfection. A rough entry is better than no entry. Log at least one expense today."},
            "ko": {"title": "완벽한 분류는 기록의 적입니다", "body": "완벽을 추구하지 마세요. 부정확한 기록이 없는 것보다 낫습니다. 오늘 지출 하나라도 기록하세요."},
        },
        "book": "James Clear — Atomic Habits",
        "condition": lambda r: False,  # requires user age; shown manually for new users
    },
    {
        "id": "irregular_entries",
        "texts": {
            "ru": {"title": "Финансовая амнезия начинается с пропущенной траты", "body": "Записывайте расходы сразу — это 10 секунд сейчас и часы экономии потом."},
            "en": {"title": "Financial amnesia starts with one missed expense", "body": "Log expenses immediately — 10 seconds now saves hours later."},
            "ko": {"title": "금융 망각은 하나의 누락된 지출에서 시작됩니다", "body": "지출을 즉시 기록하세요. 지금 10초가 나중에 시간을 절약합니다."},
        },
        "book": "James Clear — Atomic Habits",
        "condition": lambda r: False,  # requires last-entry age; disabled for now
    },
    {
        "id": "gratitude",
        "texts": {
            "ru": {"title": "Благодарность снижает импульс к покупкам", "body": "Прежде чем купить ещё одну вещь, назовите три, за которые вы уже благодарны. Желание часто уходит."},
            "en": {"title": "Gratitude reduces the urge to buy", "body": "Before buying another thing, name three you're grateful for. The urge often fades."},
            "ko": {"title": "감사는 구매 충동을 줄입니다", "body": "또 다른 것을 사기 전에 감사한 세 가지를 말해 보세요. 충동이 사라지는 경우가 많습니다."},
        },
        "book": "Rhonda Byrne — The Secret",
        "condition": lambda r: r["total_want"] > r["total_need"] * 0.5 and r["total_need"] > 0,
    },
    {
        "id": "praise_green",
        "texts": {
            "ru": {"title": "Вы на правильном пути", "body": "Доход превышает расходы и вы откладываете. Продолжайте, и через год удивитесь, как далеко продвинулись."},
            "en": {"title": "You're on the right track", "body": "Income exceeds spending and you're saving. Keep going; in a year you'll be amazed how far you've come."},
            "ko": {"title": "올바른 방향으로 가고 있습니다", "body": "수입이 지출을 초과하고 저축하고 있습니다. 계속하세요. 1년 후 얼마나 멀리 왔는지 놀랄 것입니다."},
        },
        "book": "Morgan Housel — The Psychology of Money",
        "condition": lambda r: r["total_income"] > r["total_expense"] and r["total_want"] <= r["total_need"],
    },
]


def _normalize_report(report_groups: list[dict], total_debt: float = 0.0) -> dict:
    """Aggregate multi-currency report groups into a single analysis dict."""
    total_income = sum(g.get("income", 0) for g in report_groups)
    total_expense = sum(g.get("expense", 0) for g in report_groups)
    categories: dict[str, float] = {}
    labels: dict[str, str] = {}
    for g in report_groups:
        for e in g.get("top_expenses", []):
            key = e.get("key", "")
            if key:
                categories[key] = categories.get(key, 0.0) + e.get("amount", 0)
                labels[key] = e.get("label", key)
        for i in g.get("incomes", []):
            key = i.get("key", "")
            if key:
                categories[key] = categories.get(key, 0.0) + i.get("amount", 0)
                labels[key] = i.get("label", key)

    # role totals from canonical categories
    total_need = total_want = total_goal = 0.0
    for key, amount in categories.items():
        # strip tenant-specific prefix if any; canon keys start with cat_
        base_key = key
        if not base_key.startswith("cat_"):
            continue
        # find canonical account name by key
        name = None
        for n, meta in catalog.CANON.items():
            if catalog.canon_key(n) == base_key:
                name = n
                break
        if not name:
            continue
        role = catalog.role(name)
        if role == "need":
            total_need += amount
        elif role == "want":
            total_want += amount
        elif role == "goal":
            total_goal += amount

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "total_need": total_need,
        "total_want": total_want,
        "total_goal": total_goal,
        "total_debt": total_debt,
        "categories": categories,
        "category_labels": labels,
        "currency_groups": report_groups,
    }


def select_tip(report_groups: list[dict], lang: str = "ru",
               total_debt: float = 0.0) -> dict:
    """Pick the highest-priority matching tip for the current period."""
    r = _normalize_report(report_groups, total_debt=total_debt)
    matches = []
    for tip in TIP_CATALOG:
        try:
            if tip["condition"](r):
                priority = _ROLE_PRIORITY.get(tip["id"], 100)
                matches.append((priority, tip))
        except Exception:
            continue
    if not matches:
        # fallback: mindful checkout
        mindful = next(t for t in TIP_CATALOG if t["id"] == "mindful_checkout")
        matches.append((1000, mindful))
    matches.sort(key=lambda x: x[0])
    tip = matches[0][1]
    texts = _localize(tip["texts"], lang)
    return {
        "id": tip["id"],
        "title": texts.get("title", ""),
        "body": texts.get("body", ""),
        "book": tip["book"],
    }


def all_tips(lang: str = "ru") -> list[dict]:
    """Library of all tips (for the 'Tips' screen)."""
    out = []
    for tip in TIP_CATALOG:
        texts = _localize(tip["texts"], lang)
        out.append({
            "id": tip["id"],
            "title": texts.get("title", ""),
            "body": texts.get("body", ""),
            "book": tip["book"],
        })
    return out
