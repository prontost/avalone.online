"""Единый глоссарий Avalone.

Принцип: каждое слово, которое видит пользователь, имеет цифробуквенный ключ.
Все языки — переводы ключа; ни один язык не является «основой».
"""

GLOSSARY = {
    # Приложения
    "app_work":       {"ru": "Работа",     "en": "Work",      "ko": "업무"},
    "app_money":      {"ru": "Финансы",    "en": "Finance",   "ko": "재정"},
    "app_education":  {"ru": "Обучение",   "en": "Education", "ko": "교육"},
    "app_living":     {"ru": "Жильё",      "en": "Living",    "ko": "주거"},
    "app_travel":     {"ru": "Поездки",    "en": "Travel",    "ko": "여행"},
    "app_health":     {"ru": "Здоровье",   "en": "Health",    "ko": "건강"},

    # Описания приложений
    "app_work_desc":       {"ru": "Арбайт, смены, поездки, фриланс, карьера.", "en": "Part-time, shifts, rides, freelance, career.", "ko": "아륰바이트, 교대, 출퇴근, 프리랜스, 경력."},
    "app_money_desc":      {"ru": "Учёт, бюджет, аналитика, советы.", "en": "Tracking, budget, analytics, tips.", "ko": "가계부, 예산, 분석, 팁."},
    "app_education_desc":  {"ru": "Курсы, языки, переподготовка, адаптация.", "en": "Courses, languages, retraining, adaptation.", "ko": "강좌, 언어, 재교육, 적응."},
    "app_living_desc":     {"ru": "Аренда, соседи, бытовые вопросы.", "en": "Rent, neighbors, household issues.", "ko": "임대, 이웃, 가사 문제."},
    "app_travel_desc":     {"ru": "Трансферы, экскурсии, путешествия.", "en": "Transfers, excursions, travel.", "ko": "이동, 투어, 여행."},
    "app_health_desc":     {"ru": "Клиники, страховка, записи.", "en": "Clinics, insurance, appointments.", "ko": "병원, 보험, 예약."},

    # Статусы
    "status_active":  {"ru": "Работает",      "en": "Live",           "ko": "실행 중"},
    "status_planned": {"ru": "В планах",      "en": "Planned",        "ko": "계획 중"},
    "status_in_dev":  {"ru": "В разработке",  "en": "In development", "ko": "개발 중"},

    # Общее
    "brand":          {"ru": "Avalone",    "en": "Avalone",   "ko": "Avalone"},
    "brand_tagline":  {"ru": "Ваши инструменты в одном месте", "en": "Your tools in one place", "ko": "모든 도구가 한 곳에"},
    "portal_title":   {"ru": "Портал",     "en": "Portal",    "ko": "포털"},

    # Статус-карточка
    "status_title":   {"ru": "Работает",   "en": "Live",      "ko": "실행 중"},
    "status_text":    {
        "ru": "Работа и Финансы уже работают. Создавайте поездки, ведите учёт и управляйте бюджетом.",
        "en": "Work and Finance are live. Create rides, keep records and manage your budget.",
        "ko": "업무와 재정이 실행 중입니다. 출퇴근을 만들고, 기록을 관리하며 예산을 관리하세요."
    },
    "btn_open_money": {"ru": "Открыть Финансы", "en": "Open Finance", "ko": "재정 열기"},
    "btn_open_work":  {"ru": "Открыть Работу",  "en": "Open Work",    "ko": "업무 열기"},

    # Быстрые действия
    "quick_title":    {"ru": "Быстрые действия", "en": "Quick actions", "ko": "빠른 작업"},
    "quick_budget":   {"ru": "Бюджет",     "en": "Budget",    "ko": "예산"},
    "quick_work":     {"ru": "Работа",     "en": "Work",      "ko": "업무"},
    "quick_profile":  {"ru": "Профиль",    "en": "Profile",   "ko": "프로필"},
    "quick_community":{"ru": "Сообщества", "en": "Community", "ko": "커뮤니티"},

    # Раздел приложений
    "apps_title":     {"ru": "Приложения Avalone", "en": "Avalone apps", "ko": "Avalone 앱"},

    # Teaser
    "teaser_title":   {"ru": "Другие модули в планах", "en": "More modules planned", "ko": "추가 모듈 계획 중"},
    "teaser_text":    {
        "ru": "Оставьте способ связи, и мы сообщим, когда модуль будет доступен.",
        "en": "Leave your contact and we will notify you when the module is available.",
        "ko": "연락처를 남기시면 모듈을 사용할 수 있게 되면 알려드립니다."
    },
    "teaser_placeholder": {"ru": "Telegram / KakaoTalk / email", "en": "Telegram / KakaoTalk / email", "ko": "Telegram / KakaoTalk / email"},
    "teaser_btn":     {"ru": "Сообщить",   "en": "Notify me", "ko": "알림 받기"},

    # Подвал
    "footer":         {"ru": "© Avalone — ваши инструменты в одном месте", "en": "© Avalone — your tools in one place", "ko": "© Avalone — 모든 도구가 한 곳에"},

    # Нижняя навигация
    "nav_home":       {"ru": "Портал",     "en": "Portal",    "ko": "포털"},
    "nav_money":      {"ru": "Финансы",    "en": "Finance",   "ko": "재정"},
    "nav_chat":       {"ru": "Чат",        "en": "Chat",      "ko": "채팅"},
    "nav_profile":    {"ru": "Профиль",    "en": "Profile",   "ko": "프로필"},

    # Навигация внутри модулей
    "nav_trips":          {"ru": "Поездки",    "en": "Trips",       "ko": "출퇴근"},
    "nav_stats":          {"ru": "Статистика", "en": "Statistics",  "ko": "통계"},
    "nav_notifications":  {"ru": "Уведомления","en": "Notifications","ko": "알림"},
    "nav_settings":       {"ru": "Настройки",  "en": "Settings",    "ko": "설정"},
    "nav_balances":       {"ru": "Остатки",    "en": "Balances",    "ko": "잔액"},
    "nav_journal":        {"ru": "Журнал",     "en": "Journal",     "ko": "내역"},
    "nav_analytics":      {"ru": "Аналитика",  "en": "Analytics",   "ko": "분석"},

    # Прочее
    "coming_soon":    {"ru": "В планах: ", "en": "Planned: ", "ko": "계획 중: "},
    "search_placeholder": {"ru": "Поиск...", "en": "Search...", "ko": "검색..."},
}


def t(key: str, lang: str = "ru") -> str:
    """Перевод ключа на язык; если нет — возвращает ключ."""
    item = GLOSSARY.get(key, {})
    return item.get(lang) or item.get("ru") or item.get("en") or key


def i18n_js() -> dict:
    """Вернуть словарь для клиентского JS: {lang: {key: text}}."""
    langs = ("ru", "en", "ko")
    return {lang: {key: item.get(lang, "") for key, item in GLOSSARY.items()} for lang in langs}
