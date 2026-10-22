"""Слой базы данных (SQLite через aiosqlite). Одно соединение + WAL."""
from __future__ import annotations

import time
from typing import Any, Iterable, Optional

import aiosqlite

from config import DB_PATH, START_BALANCE

_conn: Optional[aiosqlite.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    nick        TEXT,
    balance     INTEGER NOT NULL DEFAULT 0,
    bank        INTEGER NOT NULL DEFAULT 0,
    bank_ts     INTEGER NOT NULL DEFAULT 0,
    xp          INTEGER NOT NULL DEFAULT 0,
    rep         INTEGER NOT NULL DEFAULT 0,
    messages    INTEGER NOT NULL DEFAULT 0,
    married_to  INTEGER,
    married_at  INTEGER,
    banned      INTEGER NOT NULL DEFAULT 0,
    verified    INTEGER NOT NULL DEFAULT 0,
    grams       INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_stats (
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    messages  INTEGER NOT NULL DEFAULT 0,
    xp        INTEGER NOT NULL DEFAULT 0,
    last_seen INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);

-- Последнее известное состояние членства. Перед массовым созывом бот всё
-- равно перепроверяет пользователя через Telegram API.
CREATE TABLE IF NOT EXISTS chat_members (
    chat_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    status    TEXT NOT NULL DEFAULT 'member',
    is_member INTEGER NOT NULL DEFAULT 1,
    updated_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_members_active
    ON chat_members(chat_id, is_member, updated_at);

CREATE TABLE IF NOT EXISTS chats (
    chat_id   INTEGER PRIMARY KEY,
    title     TEXT,
    added_at  INTEGER NOT NULL DEFAULT 0,
    silent    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cooldowns (
    user_id INTEGER NOT NULL,
    key     TEXT    NOT NULL,
    ts      INTEGER NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS warns (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    reason  TEXT,
    ts      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS marry_requests (
    from_id INTEGER NOT NULL,
    to_id   INTEGER NOT NULL,
    ts      INTEGER NOT NULL,
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action  TEXT,
    amount  INTEGER,
    meta    TEXT,
    ts      INTEGER
);

CREATE TABLE IF NOT EXISTS ranks (
    chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0, granted_by INTEGER, ts INTEGER,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS chat_nicks (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    nick    TEXT NOT NULL,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS staff (
    chat_id  INTEGER NOT NULL,
    username TEXT    NOT NULL,
    name     TEXT,
    rank     INTEGER NOT NULL DEFAULT 1,
    user_id  INTEGER DEFAULT 0,
    left_chat INTEGER NOT NULL DEFAULT 0,
    pos      INTEGER NOT NULL DEFAULT 0,
    ts       INTEGER,
    PRIMARY KEY (chat_id, username));

CREATE TABLE IF NOT EXISTS rank_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
    rank INTEGER, by_id INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS bans (
    chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reason TEXT,
    by_id INTEGER, until INTEGER DEFAULT 0, ts INTEGER,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS mutes (
    chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reason TEXT,
    by_id INTEGER, until INTEGER DEFAULT 0, ts INTEGER,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT,
    PRIMARY KEY (chat_id, key));

CREATE TABLE IF NOT EXISTS cmd_access (
    chat_id INTEGER NOT NULL, cmd TEXT NOT NULL, rank INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (chat_id, cmd));

CREATE TABLE IF NOT EXISTS cmd_personal (
    chat_id INTEGER NOT NULL, cmd TEXT NOT NULL, user_id INTEGER NOT NULL,
    mode TEXT NOT NULL DEFAULT 'allow',   -- allow | deny
    by_id INTEGER, ts INTEGER, PRIMARY KEY (chat_id, cmd, user_id));

CREATE TABLE IF NOT EXISTS punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,                   -- mute | ban | warn | kick
    reason TEXT, rule TEXT, seconds INTEGER DEFAULT 0,
    by_id INTEGER, ts INTEGER, active INTEGER NOT NULL DEFAULT 1,
    lifted_by INTEGER, lifted_ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_pun_chat ON punishments(chat_id, user_id);

CREATE TABLE IF NOT EXISTS daily_stats (
    day TEXT NOT NULL, chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, chat_id, user_id));
CREATE INDEX IF NOT EXISTS idx_daily ON daily_stats(day, chat_id);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, item TEXT,
    stars INTEGER, amount INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS mod_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL, punish_id INTEGER,
    target_id INTEGER, target_name TEXT,
    by_id INTEGER, by_name TEXT,
    kind TEXT, reason TEXT, seconds INTEGER DEFAULT 0,
    context TEXT,              -- переписка вокруг нарушения
    source TEXT,               -- 'админ' | 'автомодерация'
    reviewed INTEGER NOT NULL DEFAULT 0,
    ai_verdict TEXT,           -- ok | soft | harsh | wrong
    ai_score INTEGER DEFAULT 0,
    ai_reason TEXT,
    ai_advice TEXT,
    ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_modlog_chat ON mod_log(chat_id, ts);

CREATE TABLE IF NOT EXISTS word_filters (
    chat_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    action TEXT DEFAULT 'warn',
    PRIMARY KEY (chat_id, word));

CREATE TABLE IF NOT EXISTS lift_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL, log_id INTEGER, punish_id INTEGER,
    target_id INTEGER, target_name TEXT,
    kind TEXT, reason TEXT,            -- за что было наказание
    by_id INTEGER, by_name TEXT,       -- кто выдал
    lifted_by INTEGER, lifted_name TEXT,   -- кто снял
    ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_liftlog ON lift_log(chat_id, ts);

CREATE TABLE IF NOT EXISTS msg_buffer (
    chat_id INTEGER NOT NULL, msg_id INTEGER NOT NULL,
    user_id INTEGER, user_name TEXT, text TEXT, ts INTEGER,
    PRIMARY KEY (chat_id, msg_id));
CREATE INDEX IF NOT EXISTS idx_buf ON msg_buffer(chat_id, ts);

CREATE TABLE IF NOT EXISTS chat_schedule (
    chat_id INTEGER PRIMARY KEY,
    open_at TEXT, close_at TEXT,          -- 'HH:MM' или NULL
    tz_offset INTEGER NOT NULL DEFAULT 3, -- часовой пояс (МСК по умолчанию)
    enabled INTEGER NOT NULL DEFAULT 0,
    last_open TEXT, last_close TEXT);

CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, cmd TEXT,
    rank INTEGER, enabled INTEGER, by_id INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, pattern TEXT,
    answer TEXT, action TEXT, by_id INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
    name TEXT, text TEXT, ts INTEGER);

CREATE TABLE IF NOT EXISTS bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    link TEXT, ts INTEGER);

CREATE TABLE IF NOT EXISTS timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
    text TEXT, fire_at INTEGER, done INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS clans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, owner_id INTEGER,
    balance INTEGER DEFAULT 0, descr TEXT, ts INTEGER);

CREATE TABLE IF NOT EXISTS clan_members (
    clan_id INTEGER NOT NULL, user_id INTEGER NOT NULL PRIMARY KEY, ts INTEGER);

CREATE TABLE IF NOT EXISTS relations (
    user_id INTEGER NOT NULL, target_id INTEGER NOT NULL, kind TEXT NOT NULL,
    ts INTEGER, count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, target_id, kind));

CREATE TABLE IF NOT EXISTS awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
    title TEXT, by_id INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY, about TEXT, city TEXT, age TEXT,
    birthday TEXT, hobby TEXT, contact TEXT,
    real_name TEXT, country TEXT, tz TEXT, family TEXT, nick2 TEXT,
    gender TEXT,               -- пол, если человек его указал
    custom TEXT,               -- описание, вписанное админом вручную
    custom_by INTEGER, custom_ts INTEGER,
    filled INTEGER NOT NULL DEFAULT 0, filled_ts INTEGER);

CREATE TABLE IF NOT EXISTS chat_profiles (
    chat_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    about       TEXT,
    city        TEXT,
    age         TEXT,
    birthday    TEXT,
    hobby       TEXT,
    contact     TEXT,
    real_name   TEXT,
    country     TEXT,
    tz          TEXT,
    family      TEXT,
    nick2       TEXT,
    gender      TEXT,
    custom      TEXT,
    custom_by   INTEGER,
    custom_ts   INTEGER,
    filled      INTEGER NOT NULL DEFAULT 0,
    filled_ts   INTEGER,
    PRIMARY KEY (chat_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_profiles ON chat_profiles(chat_id, user_id);

CREATE TABLE IF NOT EXISTS first_seen (
    chat_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    ts INTEGER NOT NULL, PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS vip (
    user_id INTEGER PRIMARY KEY, until INTEGER, level INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS vip_settings (
    user_id INTEGER PRIMARY KEY,
    color_theme TEXT NOT NULL DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS ai_pass (
    user_id INTEGER PRIMARY KEY, until INTEGER
);

CREATE TABLE IF NOT EXISTS yookassa_payments (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    amount_rub REAL NOT NULL,
    status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);


CREATE TABLE IF NOT EXISTS user_businesses (
    user_id INTEGER NOT NULL,
    biz_key TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    last_collect INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, biz_key)
);

CREATE TABLE IF NOT EXISTS game_stats (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0,
    games_played INTEGER NOT NULL DEFAULT 0,
    games_won INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    offended_by INTEGER DEFAULT NULL,
    soothe_points INTEGER NOT NULL DEFAULT 0,
    soothe_last_ts INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user1_id, user2_id)
);
CREATE INDEX IF NOT EXISTS idx_rel_u1 ON relationships(user1_id);
CREATE INDEX IF NOT EXISTS idx_rel_u2 ON relationships(user2_id);

CREATE TABLE IF NOT EXISTS relationship_cooldowns (
    rel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action_key TEXT NOT NULL,
    last_ts INTEGER NOT NULL,
    PRIMARY KEY (rel_id, user_id, action_key)
);

CREATE TABLE IF NOT EXISTS relationship_property (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_id INTEGER NOT NULL,
    item_key TEXT NOT NULL,
    item_name TEXT NOT NULL,
    price INTEGER NOT NULL DEFAULT 0,
    bought_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS relationship_children (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    born_at INTEGER NOT NULL,
    care_last_ts INTEGER NOT NULL DEFAULT 0,
    satiety INTEGER NOT NULL DEFAULT 80,
    happiness INTEGER NOT NULL DEFAULT 80,
    health INTEGER NOT NULL DEFAULT 100,
    growth_stage INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    toys_count INTEGER NOT NULL DEFAULT 0,
    clothes_count INTEGER NOT NULL DEFAULT 0,
    food_count INTEGER NOT NULL DEFAULT 0,
    last_fed_ts INTEGER NOT NULL DEFAULT 0,
    last_play_ts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS relationship_bank (
    rel_id INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS wedding_gifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rel_id INTEGER NOT NULL,
    giver_id INTEGER NOT NULL,
    giver_name TEXT NOT NULL,
    amount INTEGER NOT NULL DEFAULT 1000,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(user1_id, user2_id)
);
CREATE INDEX IF NOT EXISTS idx_friends_u1 ON friends(user1_id);
CREATE INDEX IF NOT EXISTS idx_friends_u2 ON friends(user2_id);

CREATE TABLE IF NOT EXISTS relationship_rings (
    rel_id INTEGER PRIMARY KEY,
    ring_key TEXT NOT NULL,
    giver_id INTEGER NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    car_key TEXT NOT NULL,
    bought_at INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chat_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    quote_text TEXT NOT NULL,
    author_name TEXT NOT NULL,
    adder_name TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_quotes_chat ON chat_quotes(chat_id);

CREATE TABLE IF NOT EXISTS chat_pair_of_day (
    chat_id INTEGER NOT NULL,
    date_str TEXT NOT NULL,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    user1_name TEXT NOT NULL,
    user2_name TEXT NOT NULL,
    compatibility INTEGER NOT NULL,
    story TEXT NOT NULL,
    PRIMARY KEY(chat_id, date_str)
);

CREATE TABLE IF NOT EXISTS spam_base (
    user_id INTEGER PRIMARY KEY, reason TEXT, by_id INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, user_id INTEGER,
    target_id INTEGER, text TEXT, status TEXT DEFAULT 'open', ts INTEGER);

CREATE TABLE IF NOT EXISTS giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, prize TEXT,
    owner_id INTEGER, until INTEGER, done INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS giveaway_members (
    gid INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (gid, user_id));

CREATE TABLE IF NOT EXISTS market (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT,
    amount INTEGER, price INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS net_chats (
    net_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, num INTEGER,
    PRIMARY KEY (net_id, chat_id));

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, cmd TEXT,
    target_id INTEGER, by_id INTEGER, need INTEGER, ts INTEGER);

CREATE TABLE IF NOT EXISTS vote_marks (
    vote_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY (vote_id, user_id));

-- Две связанные группы клана. Роли: admin и clan.
CREATE TABLE IF NOT EXISTS clan_groups (
    role TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL UNIQUE,
    title TEXT,
    updated_by INTEGER,
    ts INTEGER);

-- Защита от повторной обработки двух Telegram-событий одного сквозного бана.
CREATE TABLE IF NOT EXISTS clan_crossban_lock (
    user_id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL);

-- Отложенный мут/бан по @username. Нужен, потому что Bot API не умеет
-- мгновенно преобразовывать неизвестный username обычного пользователя в ID.
CREATE TABLE IF NOT EXISTS pending_punishments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT,
    seconds INTEGER NOT NULL DEFAULT 0,
    by_id INTEGER NOT NULL DEFAULT 0,
    ts INTEGER NOT NULL,
    UNIQUE(chat_id, username, kind));

CREATE TABLE IF NOT EXISTS user_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    extra TEXT,
    ts INTEGER NOT NULL,
    UNIQUE(user_id, item_id));

CREATE TABLE IF NOT EXISTS chat_boss (
    chat_id INTEGER PRIMARY KEY,
    boss_name TEXT NOT NULL,
    boss_icon TEXT NOT NULL,
    boss_level INTEGER NOT NULL DEFAULT 1,
    max_hp INTEGER NOT NULL,
    current_hp INTEGER NOT NULL,
    reward_pool INTEGER NOT NULL,
    reward_xp INTEGER NOT NULL,
    spawn_time INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    last_msg_id INTEGER DEFAULT 0);

CREATE TABLE IF NOT EXISTS boss_damage (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    damage INTEGER NOT NULL DEFAULT 0,
    attacks_count INTEGER NOT NULL DEFAULT 0,
    last_attack_ts INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS boss_daily_count (
    chat_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, day));

CREATE TABLE IF NOT EXISTS boss_knockouts (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    knocked_out_ts INTEGER NOT NULL,
    PRIMARY KEY (chat_id, user_id));

CREATE TABLE IF NOT EXISTS rep_daily_count (
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day));

CREATE TABLE IF NOT EXISTS chat_quiz (
    chat_id INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    options TEXT,
    reward_coins INTEGER NOT NULL DEFAULT 200,
    reward_xp INTEGER NOT NULL DEFAULT 30,
    created_at INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1);

CREATE TABLE IF NOT EXISTS duels_stats (
    user_id INTEGER PRIMARY KEY,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS clan_upgrades (
    clan_id INTEGER PRIMARY KEY,
    armory_lvl INTEGER NOT NULL DEFAULT 0,
    treasury_lvl INTEGER NOT NULL DEFAULT 0,
    outpost_lvl INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS clan_wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan1_id INTEGER NOT NULL,
    clan2_id INTEGER NOT NULL,
    clan1_score INTEGER NOT NULL DEFAULT 0,
    clan2_score INTEGER NOT NULL DEFAULT 0,
    prize_pool INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active');

CREATE TABLE IF NOT EXISTS user_fish_catch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    fish_type TEXT NOT NULL,
    fish_name TEXT NOT NULL,
    fish_price INTEGER NOT NULL,
    caught_at INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INTEGER NOT NULL,
    ach_id TEXT NOT NULL,
    unlocked_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, ach_id));

CREATE TABLE IF NOT EXISTS user_daily_quests (
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    quest_id TEXT NOT NULL,
    quest_title TEXT NOT NULL,
    target_count INTEGER NOT NULL DEFAULT 1,
    current_count INTEGER NOT NULL DEFAULT 0,
    reward_coins INTEGER NOT NULL DEFAULT 500,
    reward_xp INTEGER NOT NULL DEFAULT 100,
    completed INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, quest_id)
);

CREATE TABLE IF NOT EXISTS user_pets (
    user_id INTEGER PRIMARY KEY,
    pet_type TEXT NOT NULL,
    pet_name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    hunger INTEGER NOT NULL DEFAULT 100,
    last_feed INTEGER NOT NULL DEFAULT 0,
    expedition_until INTEGER NOT NULL DEFAULT 0,
    expedition_type TEXT NOT NULL DEFAULT '',
    expedition_reward TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS market_lots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL,
    seller_name TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    price INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_seller ON market_lots(seller_id);

CREATE TABLE IF NOT EXISTS user_dungeon_progress (
    user_id INTEGER PRIMARY KEY,
    floor INTEGER NOT NULL DEFAULT 1,
    room INTEGER NOT NULL DEFAULT 1,
    hp INTEGER NOT NULL DEFAULT 100,
    max_hp INTEGER NOT NULL DEFAULT 100,
    gold_found INTEGER NOT NULL DEFAULT 0,
    xp_found INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 0,
    state_data TEXT,
    last_action_ts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_jackpot (
    chat_id INTEGER PRIMARY KEY,
    pool INTEGER NOT NULL DEFAULT 5000,
    last_winner_id INTEGER,
    last_winner_name TEXT,
    last_winner_amount INTEGER,
    last_win_ts INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS casino_big_wins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    game_name TEXT NOT NULL,
    bet INTEGER NOT NULL,
    win_amount INTEGER NOT NULL,
    ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_casino_wins_ts ON casino_big_wins(ts, win_amount);

CREATE TABLE IF NOT EXISTS user_titles (
    user_id INTEGER NOT NULL,
    title_id TEXT NOT NULL,
    unlocked_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, title_id)
);

CREATE TABLE IF NOT EXISTS party_words_game (
    chat_id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    hint TEXT NOT NULL,
    reward_coins INTEGER NOT NULL DEFAULT 200,
    reward_xp INTEGER NOT NULL DEFAULT 25,
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    rating INTEGER NOT NULL DEFAULT 5,
    text TEXT NOT NULL,
    item_purchased TEXT,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    upvotes INTEGER NOT NULL DEFAULT 0,
    downvotes INTEGER NOT NULL DEFAULT 0,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS suggestion_votes (
    suggestion_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    vote INTEGER NOT NULL,
    PRIMARY KEY (suggestion_id, user_id)
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL,
    answered_by INTEGER,
    answered_name TEXT,
    answer_text TEXT,
    answered_at INTEGER,
    ai_answered INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_log_user ON log(user_id);
CREATE INDEX IF NOT EXISTS idx_stats_chat ON chat_stats(chat_id);
CREATE INDEX IF NOT EXISTS idx_support_status ON support_tickets(status, created_at);

CREATE TABLE IF NOT EXISTS bot_staff (
    user_id     INTEGER PRIMARY KEY,
    rank        INTEGER NOT NULL DEFAULT 1,
    granted_by  INTEGER,
    title       TEXT,
    ts          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blacklisted_chats (
    chat_id     INTEGER PRIMARY KEY,
    reason      TEXT,
    banned_by   INTEGER,
    ts          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS disabled_chats (
    chat_id     INTEGER PRIMARY KEY,
    disabled_by INTEGER,
    ts          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS announcements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    msg_id      INTEGER NOT NULL DEFAULT 0,
    creator_id  INTEGER NOT NULL,
    title       TEXT NOT NULL,
    text        TEXT NOT NULL,
    event_type  TEXT NOT NULL DEFAULT 'general',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS announcement_votes (
    ann_id      INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    user_name   TEXT NOT NULL,
    vote        TEXT NOT NULL,
    updated_at  INTEGER NOT NULL,
    PRIMARY KEY (ann_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_ann_chat ON announcements(chat_id, created_at);

CREATE TABLE IF NOT EXISTS chat_antiraid (
    chat_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    threshold INTEGER NOT NULL DEFAULT 5,
    media_block_seconds INTEGER NOT NULL DEFAULT 0,
    anti_links INTEGER NOT NULL DEFAULT 0,
    slowmode_auto INTEGER NOT NULL DEFAULT 0,
    shield_until INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    by_id INTEGER NOT NULL DEFAULT 0,
    ts INTEGER NOT NULL,
    UNIQUE(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS deleted_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    text TEXT NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_vacations (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    until_ts INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS staff_norms (
    chat_id INTEGER PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    quota INTEGER NOT NULL DEFAULT 5
);

CREATE TABLE IF NOT EXISTS user_jobs (
    user_id INTEGER PRIMARY KEY,
    job_key TEXT NOT NULL,
    last_worked INTEGER NOT NULL DEFAULT 0,
    total_earned INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_deposits (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL DEFAULT 0,
    last_interest INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS chat_crypto (
    rate REAL NOT NULL DEFAULT 100.0,
    last_update INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_crypto (
    user_id INTEGER PRIMARY KEY,
    amount REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS chat_lottery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    tickets INTEGER NOT NULL DEFAULT 1,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS business_upgrades (
    user_id INTEGER NOT NULL,
    biz_key TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(user_id, biz_key)
);

CREATE TABLE IF NOT EXISTS business_partners (
    chat_id INTEGER NOT NULL,
    biz_key TEXT NOT NULL,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    PRIMARY KEY(chat_id, biz_key, user1_id)
);

CREATE TABLE IF NOT EXISTS user_bios (
    user_id INTEGER PRIMARY KEY,
    bio TEXT NOT NULL,
    updated_ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_wall (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_name TEXT NOT NULL,
    text TEXT NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mentorships (
    teacher_id INTEGER NOT NULL,
    student_id INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_compliments (
    user_id INTEGER PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    last_given INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_birthdays (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    PRIMARY KEY(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS promocodes (
    code TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    reward INTEGER NOT NULL,
    uses_left INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS promocode_activations (
    code TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    PRIMARY KEY(code, user_id)
);

CREATE TABLE IF NOT EXISTS clan_districts (
    district_id TEXT PRIMARY KEY,
    clan_id INTEGER NOT NULL,
    captured_ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS clan_alliances (
    clan1_id INTEGER NOT NULL,
    clan2_id INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    PRIMARY KEY(clan1_id, clan2_id)
);

CREATE TABLE IF NOT EXISTS staff_spy (
    chat_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    by_id INTEGER NOT NULL,
    ts INTEGER NOT NULL,
    PRIMARY KEY(chat_id, target_id)
);

CREATE TABLE IF NOT EXISTS veteran_bonus_claims (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    last_claimed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(chat_id, user_id)
);

CREATE TABLE IF NOT EXISTS bot_daily_activity (
    date    TEXT NOT NULL,
    metric  TEXT NOT NULL,
    val     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date, metric)
);

CREATE TABLE IF NOT EXISTS daily_user_activity (
    date    TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (date, user_id)
);

CREATE TABLE IF NOT EXISTS daily_quests (
    user_id    INTEGER NOT NULL,
    quest_id   TEXT NOT NULL,
    date       TEXT NOT NULL,
    title      TEXT NOT NULL,
    reward_coins INTEGER NOT NULL,
    reward_xp  INTEGER NOT NULL,
    progress   INTEGER NOT NULL DEFAULT 0,
    target     INTEGER NOT NULL DEFAULT 1,
    claimed    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, quest_id, date)
);

CREATE TABLE IF NOT EXISTS daily_roulette_spins (
    user_id   INTEGER PRIMARY KEY,
    last_spin INTEGER NOT NULL DEFAULT 0
);
"""


class DictRow(dict):
    """Строка БД: поддерживает доступ по ключу, индексу и метод .get()."""
    def __init__(self, cursor, values):
        fields = [col[0] for col in cursor.description]
        super().__init__(zip(fields, values))
        self._values = values

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return super().__getitem__(item)

    def get(self, key, default=None):
        val = super().get(key, default)
        return default if val is None else val


async def init() -> None:
    global _conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = DictRow
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    await _conn.executescript(SCHEMA)
    await _migrate()
    # Миграция: объединяем любые старые балансы из grams и coins в единый balance
    try:
        await _conn.execute("UPDATE users SET balance = balance + grams WHERE grams > 0")
        await _conn.execute("UPDATE users SET grams = 0 WHERE grams > 0")
    except Exception:
        pass
    try:
        await _conn.execute("UPDATE users SET balance = balance + coins WHERE coins > 0")
        await _conn.execute("UPDATE users SET coins = 0 WHERE coins > 0")
    except Exception:
        pass
    try:
        from config import MAIN_CHAT
        await _conn.execute(
            "INSERT OR IGNORE INTO chat_profiles "
            "(chat_id, user_id, about, city, age, birthday, hobby, contact, real_name, "
            " country, tz, family, nick2, gender, custom, custom_by, custom_ts, filled, filled_ts) "
            f"SELECT {MAIN_CHAT}, user_id, about, city, age, birthday, hobby, contact, real_name, "
            "       country, tz, family, nick2, gender, custom, custom_by, custom_ts, filled, filled_ts "
            "FROM profiles"
        )
    except Exception:
        pass
    await _conn.commit()




async def _migrate() -> None:
    """Добавляет недостающие колонки в уже существующих базах."""
    wanted = {
        "staff": [("pos", "INTEGER NOT NULL DEFAULT 0"),
                  ("left_chat", "INTEGER NOT NULL DEFAULT 0")],
        "cmd_personal": [("mode", "TEXT NOT NULL DEFAULT 'allow'")],
        "mod_log": [("ai_verdict", "TEXT"), ("ai_score", "INTEGER DEFAULT 0"),
                    ("ai_reason", "TEXT"), ("ai_advice", "TEXT")],
        "users": [("verified", "INTEGER NOT NULL DEFAULT 0"),
                  ("grams", "INTEGER NOT NULL DEFAULT 0"),
                  ("coins", "INTEGER NOT NULL DEFAULT 0")],
        "relations": [("count", "INTEGER NOT NULL DEFAULT 1")],
        "profiles": [("gender", "TEXT"), ("custom", "TEXT"), ("custom_by", "INTEGER"),
                     ("custom_ts", "INTEGER"),
                     ("real_name", "TEXT"), ("country", "TEXT"), ("tz", "TEXT"),
                     ("family", "TEXT"), ("nick2", "TEXT"),
                     ("filled", "INTEGER NOT NULL DEFAULT 0"), ("filled_ts", "INTEGER")],
        "relationship_children": [
            ("satiety", "INTEGER NOT NULL DEFAULT 80"),
            ("happiness", "INTEGER NOT NULL DEFAULT 80"),
            ("health", "INTEGER NOT NULL DEFAULT 100"),
            ("growth_stage", "INTEGER NOT NULL DEFAULT 1"),
            ("xp", "INTEGER NOT NULL DEFAULT 0"),
            ("toys_count", "INTEGER NOT NULL DEFAULT 0"),
            ("clothes_count", "INTEGER NOT NULL DEFAULT 0"),
            ("food_count", "INTEGER NOT NULL DEFAULT 0"),
            ("last_fed_ts", "INTEGER NOT NULL DEFAULT 0"),
            ("last_play_ts", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "bot_staff": [
            ("warns", "INTEGER NOT NULL DEFAULT 0"),
            ("muted_until", "INTEGER NOT NULL DEFAULT 0"),
        ],
    }
    for table, cols in wanted.items():
        try:
            async with _conn.execute(f"PRAGMA table_info({table})") as cur:
                have = {r[1] for r in await cur.fetchall()}
        except Exception:
            continue
        for name, ddl in cols:
            if name not in have:
                try:
                    await _conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                except Exception:
                    pass

    # Автоматическая инициализация официальных групп проекта Moxxi:
    default_links = {
        "global_community_chat": "https://t.me/moxxi_chat",
        "global_reviews_chat": "https://t.me/moxxi_reviews",
        "global_ideas_chat": "https://t.me/moxxi_ideas",
        "global_support_chat": "https://t.me/moxxi_support",
        "global_commands_chat": "https://t.me/moxxi_chat",
    }
    for k, v in default_links.items():
        try:
            row = await fetchone("SELECT value FROM settings WHERE chat_id=0 AND key=?", (k,))
            if not row or not row["value"] or row["value"] in ("Не привязана", ""):
                await execute(
                    "INSERT INTO settings (chat_id, key, value) VALUES (0, ?, ?) "
                    "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value",
                    (k, v)
                )
        except Exception:
            pass

    # Автоматическое подтверждение статуса владельцев бота (Fanat & Simba) в таблице bot_staff:
    for owner_id in (8036974481, 8412527198):
        try:
            await execute(
                "INSERT INTO bot_staff (user_id, rank, title, granted_by, ts, warns) "
                "VALUES (?, 4, 'Владелец', 0, ?, 0) "
                "ON CONFLICT(user_id) DO UPDATE SET rank=4, title='Владелец'",
                (owner_id, int(time.time()))
            )
        except Exception:
            pass



# ═══════════════════════════════════════════════════════════════
# СТАФФ БОТА, РАНГИ, ЧС ГРУПП, УПРАВЛЕНИЕ И ГЛОБАЛЬНЫЕ НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

BOT_STAFF_TITLES = {
    1: "Хелпер",
    2: "Модератор",
    3: "Администратор",
    4: "Владелец"
}

async def get_staff_warns(user_id: int) -> int:
    row = await fetchone("SELECT warns FROM bot_staff WHERE user_id=?", (user_id,))
    return int(row["warns"]) if row and row["warns"] is not None else 0

async def add_staff_warn(user_id: int) -> int:
    await execute("UPDATE bot_staff SET warns = COALESCE(warns, 0) + 1 WHERE user_id=?", (user_id,))
    return await get_staff_warns(user_id)

async def remove_staff_warn(user_id: int) -> int:
    await execute("UPDATE bot_staff SET warns = MAX(0, COALESCE(warns, 0) - 1) WHERE user_id=?", (user_id,))
    return await get_staff_warns(user_id)

async def reset_staff_warns(user_id: int) -> None:
    await execute("UPDATE bot_staff SET warns = 0 WHERE user_id=?", (user_id,))

async def get_bot_staff_rank(user_id: int) -> int:
    """Возвращает ранг стаффа бота: 4 = Владелец, 3 = Админ, 2 = Модер, 1 = Хелпер, 0 = Обычный игрок."""
    import config
    if config.is_bot_owner(user_id):
        return 4
    row = await fetchone("SELECT rank FROM bot_staff WHERE user_id=?", (user_id,))
    if row:
        return int(row["rank"])
    return 0

async def set_bot_staff_rank(user_id: int, rank: int, title: str = "", granted_by: int = 0) -> None:
    now = int(time.time())
    if not title:
        title = BOT_STAFF_TITLES.get(rank, "Сотрудник")
    await execute(
        "INSERT INTO bot_staff (user_id, rank, title, granted_by, ts) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET rank=excluded.rank, title=excluded.title, granted_by=excluded.granted_by, ts=excluded.ts",
        (user_id, rank, title, granted_by, now)
    )

async def remove_bot_staff(user_id: int) -> bool:
    await execute("DELETE FROM bot_staff WHERE user_id=?", (user_id,))
    return True

async def get_all_bot_staff() -> list[dict]:
    rows = await fetchall(
        "SELECT s.user_id, s.rank, s.title, s.granted_by, s.ts, COALESCE(s.warns, 0) as warns, "
        "COALESCE(s.muted_until, 0) as muted_until, u.first_name, u.username, u.nick "
        "FROM bot_staff s LEFT JOIN users u ON s.user_id = u.user_id "
        "ORDER BY s.rank DESC, s.ts ASC"
    )
    return [dict(r) for r in rows]

async def staff_mute(user_id: int, duration_sec: int = 3600) -> int:
    until = int(time.time()) + duration_sec
    await execute("UPDATE bot_staff SET muted_until=? WHERE user_id=?", (until, user_id))
    return until

async def staff_unmute(user_id: int) -> bool:
    await execute("UPDATE bot_staff SET muted_until=0 WHERE user_id=?", (user_id,))
    return True

async def is_staff_muted(user_id: int) -> tuple[bool, int]:
    row = await fetchone("SELECT muted_until FROM bot_staff WHERE user_id=?", (user_id,))
    if not row or not row["muted_until"]:
        return False, 0
    now = int(time.time())
    if row["muted_until"] > now:
        return True, int(row["muted_until"] - now)
    return False, 0


# ═══════════════════════════════════════════════════════════════
# ДНЕВНАЯ СТАТИСТИКА И АКТИВНОСТЬ БОТА (VISITS, STARTS, GROUPS)
# ═══════════════════════════════════════════════════════════════

async def track_daily_activity(user_id: int, action: str = "msg", is_group: bool = False, is_start: bool = False) -> None:
    """Фиксирует дневную активность пользователей и запусков бота."""
    if not user_id:
        return
    today = time.strftime("%Y-%m-%d")
    try:
        # Уникальный посетитель сегодня
        is_new_today = False
        try:
            await execute("INSERT INTO daily_user_activity (date, user_id) VALUES (?, ?)", (today, user_id))
            is_new_today = True
        except Exception:
            pass

        if is_new_today:
            await execute(
                "INSERT INTO bot_daily_activity (date, metric, val) VALUES (?, 'unique_users', 1) "
                "ON CONFLICT(date, metric) DO UPDATE SET val = val + 1",
                (today,)
            )

        if is_start:
            await execute(
                "INSERT INTO bot_daily_activity (date, metric, val) VALUES (?, 'bot_starts', 1) "
                "ON CONFLICT(date, metric) DO UPDATE SET val = val + 1",
                (today,)
            )

        if action == "cmd":
            await execute(
                "INSERT INTO bot_daily_activity (date, metric, val) VALUES (?, 'commands_count', 1) "
                "ON CONFLICT(date, metric) DO UPDATE SET val = val + 1",
                (today,)
            )

        await execute(
            "INSERT INTO bot_daily_activity (date, metric, val) VALUES (?, 'messages_count', 1) "
            "ON CONFLICT(date, metric) DO UPDATE SET val = val + 1",
            (today,)
        )
    except Exception:
        pass


async def track_daily_group_add(chat_id: int) -> None:
    """Фиксирует добавление бота в новую группу за сегодня."""
    today = time.strftime("%Y-%m-%d")
    try:
        await execute(
            "INSERT INTO bot_daily_activity (date, metric, val) VALUES (?, 'group_adds', 1) "
            "ON CONFLICT(date, metric) DO UPDATE SET val = val + 1",
            (today,)
        )
    except Exception:
        pass


async def get_daily_activity(target_date: str = None) -> dict:
    """Возвращает сводку активности бота за сегодня или указанную дату."""
    if not target_date:
        target_date = time.strftime("%Y-%m-%d")

    rows = await fetchall("SELECT metric, val FROM bot_daily_activity WHERE date=?", (target_date,))
    stats_map = {r["metric"]: r["val"] for r in rows}

    row_total_u = await fetchone("SELECT COUNT(*) as c FROM users")
    row_total_c = await fetchone("SELECT COUNT(*) as c FROM chats WHERE chat_id < 0")

    return {
        "date": target_date,
        "unique_users": stats_map.get("unique_users", 0),
        "bot_starts": stats_map.get("bot_starts", 0),
        "group_adds": stats_map.get("group_adds", 0),
        "commands_count": stats_map.get("commands_count", 0),
        "messages_count": stats_map.get("messages_count", 0),
        "total_users": row_total_u["c"] if row_total_u else 0,
        "total_chats": row_total_c["c"] if row_total_c else 0,
    }


# ═══════════════════════════════════════════════════════════════
# ИГРОВЫЕ КВЕСТЫ И РУЛЕТКА УДАЧИ ДЛЯ ИГРОКОВ
# ═══════════════════════════════════════════════════════════════

DAILY_QUEST_TEMPLATES = [
    {
        "id": "chat_msgs",
        "title": "💬 Общительный игрок: написать 25 сообщений",
        "target": 25,
        "coins": 10000,
        "xp": 50,
    },
    {
        "id": "play_duels",
        "title": "⚔️ Дуэлянт: сыграть 3 дуэли с игроками",
        "target": 3,
        "coins": 15000,
        "xp": 80,
    },
    {
        "id": "catch_fish",
        "title": "🎣 Заядлый рыбак: поймать 3 рыбы",
        "target": 3,
        "coins": 12000,
        "xp": 60,
    },
]

async def get_or_create_daily_quests(user_id: int) -> list[dict]:
    today = time.strftime("%Y-%m-%d")
    existing = await fetchall(
        "SELECT * FROM daily_quests WHERE user_id=? AND date=?",
        (user_id, today)
    )
    if not existing:
        for tpl in DAILY_QUEST_TEMPLATES:
            await execute(
                "INSERT INTO daily_quests (user_id, quest_id, date, title, reward_coins, reward_xp, progress, target, claimed) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0)",
                (user_id, tpl["id"], today, tpl["title"], tpl["coins"], tpl["xp"], tpl["target"])
            )
        existing = await fetchall(
            "SELECT * FROM daily_quests WHERE user_id=? AND date=?",
            (user_id, today)
        )
    return [dict(r) for r in existing]

async def update_quest_progress(user_id: int, quest_id: str, inc: int = 1) -> None:
    today = time.strftime("%Y-%m-%d")
    try:
        await execute(
            "UPDATE daily_quests SET progress = MIN(target, progress + ?) "
            "WHERE user_id=? AND quest_id=? AND date=? AND claimed=0",
            (inc, user_id, quest_id, today)
        )
    except Exception:
        pass

async def claim_daily_quest(user_id: int, quest_id: str) -> dict | None:
    today = time.strftime("%Y-%m-%d")
    row = await fetchone(
        "SELECT * FROM daily_quests WHERE user_id=? AND quest_id=? AND date=?",
        (user_id, quest_id, today)
    )
    if not row or row["claimed"] or row["progress"] < row["target"]:
        return None
    await execute(
        "UPDATE daily_quests SET claimed=1 WHERE user_id=? AND quest_id=? AND date=?",
        (user_id, quest_id, today)
    )
    coins = row["reward_coins"]
    xp = row["reward_xp"]
    await add_balance(user_id, coins, "quest_reward", quest_id)
    await add_xp(user_id, xp)
    return {"coins": coins, "xp": xp, "title": row["title"]}

async def check_roulette_cooldown(user_id: int) -> int:
    """Возвращает оставшееся время кулдауна на прокрут рулетки в секундах (0 = доступно)."""
    lvl, _, active = await get_vip_info(user_id)
    cd_total = 21600 if (active and lvl >= 2) else (43200 if (active and lvl >= 1) else 86400)
    row = await fetchone("SELECT last_spin FROM daily_roulette_spins WHERE user_id=?", (user_id,))
    if not row:
        return 0
    now = int(time.time())
    passed = now - row["last_spin"]
    return max(0, cd_total - passed)

async def record_roulette_spin(user_id: int) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO daily_roulette_spins (user_id, last_spin) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET last_spin=excluded.last_spin",
        (user_id, now)
    )

async def blacklist_chat(chat_id: int, reason: str = "", banned_by: int = 0) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO blacklisted_chats (chat_id, reason, banned_by, ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET reason=excluded.reason, banned_by=excluded.banned_by, ts=excluded.ts",
        (chat_id, reason, banned_by, now)
    )

async def unblacklist_chat(chat_id: int) -> bool:
    await execute("DELETE FROM blacklisted_chats WHERE chat_id=?", (chat_id,))
    return True

async def is_chat_blacklisted(chat_id: int) -> tuple[bool, str]:
    row = await fetchone("SELECT reason FROM blacklisted_chats WHERE chat_id=?", (chat_id,))
    if row:
        return True, row["reason"] or "Нарушение правил сообщества (интим/18+, спам, коммерция)"
    return False, ""

async def get_blacklisted_chats() -> list[dict]:
    rows = await fetchall("SELECT * FROM blacklisted_chats ORDER BY ts DESC")
    return [dict(r) for r in rows]

async def set_chat_disabled(chat_id: int, disabled: bool, by_id: int = 0) -> None:
    if disabled:
        now = int(time.time())
        await execute(
            "INSERT INTO disabled_chats (chat_id, disabled_by, ts) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET disabled_by=excluded.disabled_by, ts=excluded.ts",
            (chat_id, by_id, now)
        )
    else:
        await execute("DELETE FROM disabled_chats WHERE chat_id=?", (chat_id,))

async def is_chat_disabled(chat_id: int) -> bool:
    row = await fetchone("SELECT 1 FROM disabled_chats WHERE chat_id=?", (chat_id,))
    return bool(row)

async def set_global_setting(key: str, value: str) -> None:
    await execute(
        "INSERT INTO settings (chat_id, key, value) VALUES (0, ?, ?) "
        "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value",
        (key, str(value))
    )

async def get_global_setting(key: str, default: str = "") -> str:
    row = await fetchone("SELECT value FROM settings WHERE chat_id=0 AND key=?", (key,))
    return str(row["value"]) if (row and row["value"] is not None) else default

async def get_global_bot_stats() -> dict:
    row_users = await fetchone("SELECT COUNT(*) as c, COALESCE(SUM(balance), 0) as s FROM users")
    row_chats = await fetchone("SELECT COUNT(*) as c FROM chats")
    row_tickets = await fetchone("SELECT COUNT(*) as c FROM support_tickets WHERE status='open'")
    row_reviews = await fetchone("SELECT COUNT(*) as c FROM reviews")
    row_sug = await fetchone("SELECT COUNT(*) as c FROM suggestions WHERE status='pending'")
    row_bl = await fetchone("SELECT COUNT(*) as c FROM blacklisted_chats")
    return {
        "users_count": int(row_users["c"]) if row_users else 0,
        "total_coins": int(row_users["s"]) if row_users else 0,
        "chats_count": int(row_chats["c"]) if row_chats else 0,
        "open_tickets": int(row_tickets["c"]) if row_tickets else 0,
        "reviews_count": int(row_reviews["c"]) if row_reviews else 0,
        "pending_ideas": int(row_sug["c"]) if row_sug else 0,
        "blacklisted_chats": int(row_bl["c"]) if row_bl else 0,
    }


# ══════════════════ АНОНСЫ И ПЕРЕКЛИЧКИ С ИИ ══════════════════

async def create_announcement(chat_id: int, creator_id: int, title: str, text: str, event_type: str = "general") -> int:
    now = int(time.time())
    cur = await execute(
        "INSERT INTO announcements (chat_id, creator_id, title, text, event_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, creator_id, title, text, event_type, now)
    )
    return int(cur.lastrowid or 0)


async def set_announcement_msg_id(ann_id: int, msg_id: int) -> None:
    await execute("UPDATE announcements SET msg_id = ? WHERE id = ?", (msg_id, ann_id))


async def record_announcement_vote(ann_id: int, user_id: int, user_name: str, vote: str) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO announcement_votes (ann_id, user_id, user_name, vote, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(ann_id, user_id) DO UPDATE SET vote = excluded.vote, user_name = excluded.user_name, updated_at = excluded.updated_at",
        (ann_id, user_id, user_name, vote, now)
    )


async def get_announcement_vote_counts(ann_id: int) -> dict[str, int]:
    rows = await fetchall("SELECT vote, COUNT(*) as cnt FROM announcement_votes WHERE ann_id = ? GROUP BY vote", (ann_id,))
    counts = {"yes": 0, "no": 0, "late": 0}
    for r in rows:
        v = r["vote"]
        if v in counts:
            counts[v] = int(r["cnt"])
    return counts


async def get_announcement_votes_detailed(ann_id: int) -> dict[str, list[str]]:
    rows = await fetchall("SELECT user_id, user_name, vote FROM announcement_votes WHERE ann_id = ? ORDER BY updated_at ASC", (ann_id,))
    res = {"yes": [], "no": [], "late": []}
    for r in rows:
        v = r["vote"]
        if v in res:
            res[v].append(r["user_name"] or str(r["user_id"]))
    return res


async def get_announcement(ann_id: int) -> dict | None:
    return await fetchone("SELECT * FROM announcements WHERE id = ?", (ann_id,))


# --- Цитатник чата ---------------------------------------------------
async def add_chat_quote(chat_id: int, user_id: int, quote_text: str, author_name: str, adder_name: str) -> int:
    now = int(time.time())
    cur = await execute(
        "INSERT INTO chat_quotes (chat_id, user_id, quote_text, author_name, adder_name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, user_id, quote_text, author_name, adder_name, now)
    )
    return int(cur.lastrowid or 0)


async def get_random_chat_quote(chat_id: int) -> dict | None:
    return await fetchone(
        "SELECT quote_text, author_name, adder_name, created_at FROM chat_quotes WHERE chat_id=? ORDER BY RANDOM() LIMIT 1",
        (chat_id,)
    )


async def get_chat_quotes_count(chat_id: int) -> int:
    row = await fetchone("SELECT COUNT(*) as cnt FROM chat_quotes WHERE chat_id=?", (chat_id,))
    return int(row["cnt"]) if row else 0


# --- Пара Дня (Шипперинг) -------------------------------------------
async def get_pair_of_day(chat_id: int, date_str: str) -> dict | None:
    return await fetchone(
        "SELECT user1_id, user2_id, user1_name, user2_name, compatibility, story FROM chat_pair_of_day "
        "WHERE chat_id=? AND date_str=?",
        (chat_id, date_str)
    )


async def set_pair_of_day(chat_id: int, date_str: str, u1_id: int, u2_id: int,
                          u1_name: str, u2_name: str, compat: int, story: str) -> None:
    await execute(
        "INSERT OR REPLACE INTO chat_pair_of_day "
        "(chat_id, date_str, user1_id, user2_id, user1_name, user2_name, compatibility, story) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, date_str, u1_id, u2_id, u1_name, u2_name, compat, story)
    )


# --- Фильтр запрещённых слов ----------------------------------------
async def add_filtered_word(chat_id: int, word: str, action: str = "warn") -> None:
    await execute(
        "INSERT INTO word_filters (chat_id, word, action) VALUES (?,?,?) "
        "ON CONFLICT(chat_id, word) DO UPDATE SET action=excluded.action",
        (chat_id, word.lower().strip(), action)
    )


async def remove_filtered_word(chat_id: int, word: str) -> None:
    await execute(
        "DELETE FROM word_filters WHERE chat_id=? AND lower(word)=lower(?)",
        (chat_id, word.strip())
    )


async def get_filtered_words(chat_id: int) -> list[dict]:
    return await fetchall("SELECT word, action FROM word_filters WHERE chat_id=?", (chat_id,))


async def clear_filtered_words(chat_id: int) -> None:
    await execute("DELETE FROM word_filters WHERE chat_id=?", (chat_id,))


async def close() -> None:
    if _conn:
        await _conn.close()


def conn() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("DB не инициализирована: вызовите db.init()")
    return _conn


async def execute(sql: str, params: Iterable[Any] = ()) -> aiosqlite.Cursor:
    cur = await conn().execute(sql, tuple(params))
    await conn().commit()
    return cur


async def fetchone(sql: str, params: Iterable[Any] = ()) -> Optional[aiosqlite.Row]:
    async with conn().execute(sql, tuple(params)) as cur:
        return await cur.fetchone()


async def fetchall(sql: str, params: Iterable[Any] = ()) -> list[aiosqlite.Row]:
    async with conn().execute(sql, tuple(params)) as cur:
        return list(await cur.fetchall())


# --- Пользователи ---------------------------------------------------------
async def get_user(user_id: int) -> aiosqlite.Row:
    row = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    if row is None:
        await execute(
            "INSERT OR IGNORE INTO users (user_id, balance, created_at) VALUES (?,?,?)",
            (user_id, START_BALANCE, int(time.time())),
        )
        row = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    return row  # type: ignore[return-value]


async def touch_user(user_id: int, username: str | None, first_name: str | None) -> None:
    await get_user(user_id)
    await execute(
        "UPDATE users SET username=?, first_name=? WHERE user_id=?",
        (username, first_name, user_id),
    )
    # состав мог быть импортирован по @нику без id — связываем при первом сообщении
    if username:
        rows = await fetchall(
            "SELECT chat_id, rank FROM staff WHERE lower(username)=lower(?) "
            "AND (user_id IS NULL OR user_id=0)", (username,))
        for r in rows:
            await execute(
                "UPDATE staff SET user_id=? WHERE chat_id=? AND lower(username)=lower(?)",
                (user_id, r["chat_id"], username))
            await execute(
                "INSERT INTO ranks (chat_id,user_id,rank,granted_by,ts) VALUES (?,?,?,0,?) "
                "ON CONFLICT(chat_id,user_id) DO NOTHING",
                (r["chat_id"], user_id, r["rank"], int(__import__("time").time())))


async def get_balance(user_id: int) -> int:
    row = await fetchone("SELECT balance FROM users WHERE user_id=?", (user_id,))
    if not row:
        u = await get_user(user_id)
        return int(u["balance"]) if u else 0
    return int(row["balance"])


async def add_balance(user_id: int, amount: int, action: str = "", meta: str = "") -> int:
    await get_user(user_id)
    # Защита от NaN / бесконечности / переполнений
    try:
        amt = int(amount)
    except Exception:
        amt = 0
    # Максимальная разумная граница баланса для защиты от переполнений (100 млрд)
    await execute("UPDATE users SET balance = MIN(100000000000, MAX(0, balance + ?)) WHERE user_id=?", (amt, user_id))
    if action:
        await execute(
            "INSERT INTO log (user_id, action, amount, meta, ts) VALUES (?,?,?,?,?)",
            (user_id, action, amt, meta, int(time.time())),
        )
    row = await fetchone("SELECT balance FROM users WHERE user_id=?", (user_id,))
    return row["balance"] if row else 0


async def set_balance(user_id: int, amount: int) -> int:
    await get_user(user_id)
    val = max(0, int(amount))
    await execute("UPDATE users SET balance=? WHERE user_id=?", (val, user_id))
    return val


REFERENCE_TOP = [
    {"patterns": ["гоуст", "ghost", "богатый"], "target_name": "Гоуст 🇬🇧 🇧🇾 🤙", "balance": 194915},
    {"patterns": ["malaya", "малая", "əmalaya", "dmalaya"], "target_name": "𝓓𝓜𝓪𝓵𝓪𝔂𝓪🍼", "balance": 168869},
    {"patterns": ["дима", "dima"], "target_name": "Дима", "balance": 135199},
    {"user_id": 8297844640, "patterns": ["kaktys6390", "кактус"], "target_name": "Kaktys6390", "balance": 131455},
    {"patterns": ["простоник", "просто ник", "просто_ник"], "target_name": "ПростоНик", "balance": 113997},
    {"patterns": ["авокадик", "авокадо", "avocado"], "target_name": "🥑АВОКАДИК🥑", "balance": 101915},
    {"patterns": ["forever_young", "foreveryoung", "forever young"], "target_name": "forever_young🔞 🥷", "balance": 41443},
    {"patterns": ["тамик", "tamik"], "target_name": "Тамик00", "balance": 22130},
    {"user_id": 6592023977, "patterns": ["lizaveta", "лизавета", "лиза", "l_i_zavetka"], "target_name": "༒Lizaveta༒", "balance": 15451},
    {"patterns": ["саша", "sasha"], "target_name": "Саша", "balance": 12418},
]


async def restore_top_balances() -> list[dict]:
    """Восстанавливает эталонный топ игроков и сбрасывает все накрученные триллионы."""
    raw_users = await fetchall("SELECT user_id, username, first_name, balance FROM users")
    all_users = [dict(r) for r in raw_users]
    matched_uids = set()
    restored = []

    for item in REFERENCE_TOP:
        target_uid = item.get("user_id")
        matched_user = None

        if target_uid:
            matched_user = next((u for u in all_users if u["user_id"] == target_uid), None)

        if not matched_user:
            for u in all_users:
                if u["user_id"] in matched_uids:
                    continue
                uname = (u.get("username") or "").lower()
                fname = (u.get("first_name") or "").lower()
                for pat in item["patterns"]:
                    if pat in uname or pat in fname:
                        matched_user = u
                        break
                if matched_user:
                    break

        if matched_user:
            uid = matched_user["user_id"]
            matched_uids.add(uid)
            bal = item["balance"]
            await execute("UPDATE users SET balance=? WHERE user_id=?", (bal, uid))
            restored.append({
                "user_id": uid,
                "first_name": matched_user.get("first_name") or item["target_name"],
                "balance": bal
            })

    # Очищаем баганные отрицательные балансы если были
    await execute("UPDATE users SET balance=0 WHERE balance < 0")

    # Очищаем баганные записи лога
    await execute("DELETE FROM log WHERE action IN ('rob_fail', 'rob_win', 'robbed_by', 'rob_comp') AND ABS(amount) > 5000000")

    return restored


async def reset_all_businesses_and_levels() -> dict:
    """Полностью удаляет все купленные предприятия (фермы, заводы, дома, ТЦ, шахты и т.д.),
    сбрасывает игровой XP/уровни и восстанавливает балансы игроков до состояния до ошибки.
    """
    biz_row = await fetchone("SELECT COUNT(*) c FROM user_businesses")
    biz_count = int(biz_row["c"] or 0) if biz_row else 0
    await execute("DELETE FROM user_businesses")

    stats_row = await fetchone("SELECT COUNT(*) c FROM game_stats")
    stats_count = int(stats_row["c"] or 0) if stats_row else 0
    await execute("DELETE FROM game_stats")

    # Очищаем логи покупок и невалидных операций
    await execute("DELETE FROM log WHERE action IN ('biz_buy', 'biz_sell', 'biz_income', 'rob_fail', 'rob_win', 'robbed_by', 'rob_comp')")

    # Восстанавливаем эталонные балансы игроков
    restored = await restore_top_balances()

    return {
        "businesses_deleted": biz_count,
        "stats_reset": stats_count,
        "top_restored": len(restored)
    }


# --- Алиасы для полной совместимости со всеми модулями ---
async def get_grams(user_id: int) -> int:
    return await get_balance(user_id)



async def add_grams(user_id: int, amount: int, action: str = "", meta: str = "") -> int:
    return await add_balance(user_id, amount, action, meta)


async def set_grams(user_id: int, amount: int) -> int:
    return await set_balance(user_id, amount)


async def get_coins(user_id: int) -> int:
    return await get_balance(user_id)


async def add_coins(user_id: int, amount: int, action: str = "", meta: str = "") -> int:
    return await add_balance(user_id, amount, action, meta)


async def set_coins(user_id: int, amount: int) -> int:
    return await set_balance(user_id, amount)


async def get_comets(user_id: int) -> int:
    return await get_balance(user_id)


async def add_comets(user_id: int, amount: int, action: str = "", meta: str = "") -> int:
    return await add_balance(user_id, amount, action, meta)


async def set_comets(user_id: int, amount: int) -> int:
    return await set_balance(user_id, amount)


async def add_xp(user_id: int, amount: int) -> None:
    await execute("UPDATE users SET xp = xp + ?, messages = messages + 1 WHERE user_id=?",
                  (amount, user_id))


# --- Кулдауны -------------------------------------------------------------
async def cooldown_left(user_id: int, key: str, period: int) -> int:
    row = await fetchone("SELECT ts FROM cooldowns WHERE user_id=? AND key=?", (user_id, key))
    if not row:
        return 0
    left = int(row["ts"]) + period - int(time.time())
    return max(0, left)


async def set_cooldown(user_id: int, key: str) -> None:
    await execute(
        "INSERT INTO cooldowns (user_id, key, ts) VALUES (?,?,?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET ts=excluded.ts",
        (user_id, key, int(time.time())),
    )


# --- Чаты и статистика ----------------------------------------------------
async def register_chat(chat_id: int, title: str | None) -> None:
    await execute(
        "INSERT INTO chats (chat_id, title, added_at) VALUES (?,?,?) "
        "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
        (chat_id, title, int(time.time())),
    )


async def bump_chat_stat(chat_id: int, user_id: int, xp: int) -> None:
    await execute(
        "INSERT INTO chat_stats (chat_id, user_id, messages, xp, last_seen) VALUES (?,?,1,?,?) "
        "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
        "messages = messages + 1, xp = xp + excluded.xp, last_seen = excluded.last_seen",
        (chat_id, user_id, xp, int(time.time())),
    )

# --- Настройки чата -------------------------------------------------------
async def get_setting(chat_id: int, key: str, default: str = "") -> str:
    row = await fetchone("SELECT value FROM settings WHERE chat_id=? AND key=?", (chat_id, key))
    return row["value"] if row else default


async def set_setting(chat_id: int, key: str, value: str) -> None:
    await execute(
        "INSERT INTO settings (chat_id, key, value) VALUES (?,?,?) "
        "ON CONFLICT(chat_id, key) DO UPDATE SET value=excluded.value",
        (chat_id, key, value))


# --- VIP & VIP+ -----------------------------------------------------------
async def get_vip_info(user_id: int) -> tuple[int, int, bool]:
    """Возвращает (level, until, is_active). Level: 1 = VIP, 2 = VIP+."""
    row = await fetchone("SELECT until, level FROM vip WHERE user_id=?", (user_id,))
    if not row:
        return 0, 0, False
    lvl = row["level"] or 1
    until = row["until"] or 0
    active = until > time.time()
    return lvl if active else 0, until, active


async def set_vip(user_id: int, until: int, level: int = 1) -> None:
    await execute(
        "INSERT INTO vip (user_id, until, level) VALUES (?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET until=excluded.until, level=excluded.level",
        (user_id, until, level))


async def remove_vip(user_id: int) -> None:
    await execute("DELETE FROM vip WHERE user_id=?", (user_id,))


async def get_vip_theme(user_id: int) -> str:
    row = await fetchone("SELECT color_theme FROM vip_settings WHERE user_id=?", (user_id,))
    return row["color_theme"] if row else "default"


async def set_vip_theme(user_id: int, theme: str) -> None:
    await execute(
        "INSERT INTO vip_settings (user_id, color_theme) VALUES (?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET color_theme=excluded.color_theme",
        (user_id, theme))


# --- AI Pass (ИИ-Подписка) ------------------------------------------------
async def get_ai_pass_info(user_id: int) -> tuple[int, bool]:
    """Возвращает (until, is_active). В VIP+ (level 2) ИИ-подписка включена автоматически."""
    lvl, v_until, v_act = await get_vip_info(user_id)
    if v_act and lvl >= 2:
        return v_until, True

    row = await fetchone("SELECT until FROM ai_pass WHERE user_id=?", (user_id,))
    if not row:
        return 0, False
    until = int(row["until"] or 0)
    active = until > time.time()
    return until, active


async def set_ai_pass(user_id: int, until: int) -> None:
    await execute(
        "INSERT INTO ai_pass (user_id, until) VALUES (?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET until=excluded.until",
        (user_id, until))



# --- Отношения (ОТН) -------------------------------------------------------
REL_LEVELS = {
    1: 0,
    2: 50,
    3: 150,
    4: 350,
    5: 700,
    6: 1500,
    7: 3000,
    8: 6000,
}


def calc_rel_level(xp: int) -> int:
    lvl = 1
    for l, req in sorted(REL_LEVELS.items()):
        if xp >= req:
            lvl = l
    return lvl


async def get_user_relationships(user_id: int) -> list[dict]:
    """Возвращает все отношения пользователя (отсортированные по ID)."""
    return await fetchall(
        "SELECT * FROM relationships WHERE user1_id=? OR user2_id=? ORDER BY id ASC",
        (user_id, user_id))


async def get_active_rel_idx(user_id: int) -> int:
    """Возвращает номер активной пары пользователя (1-based, 1 = основа)."""
    val = await get_setting(user_id, "active_rel_idx", "1")
    try:
        return max(1, int(val))
    except Exception:
        return 1


async def set_active_rel_idx(user_id: int, idx: int) -> None:
    """Устанавливает номер активной пары."""
    await set_setting(user_id, "active_rel_idx", str(max(1, idx)))


async def get_relationship(user_id: int, target_idx: int | None = None) -> dict | None:
    """Возвращает активную пару или пару под номером target_idx (1-based, 1 = основа)."""
    rels = await get_user_relationships(user_id)
    if not rels:
        return None
    if target_idx is not None and target_idx > 0:
        if target_idx <= len(rels):
            return rels[target_idx - 1]
        return rels[0]
    cur_idx = await get_active_rel_idx(user_id)
    if 1 <= cur_idx <= len(rels):
        return rels[cur_idx - 1]
    return rels[0]


async def are_in_relationship(u1: int, u2: int) -> bool:
    """Проверяет, есть ли уже союз между двумя конкретными людьми."""
    row = await fetchone(
        "SELECT 1 FROM relationships WHERE (user1_id=? AND user2_id=?) OR (user1_id=? AND user2_id=?)",
        (u1, u2, u2, u1))
    return bool(row)


async def get_rel_by_id(rel_id: int) -> dict | None:
    return await fetchone("SELECT * FROM relationships WHERE id=?", (rel_id,))


async def create_relationship(u1: int, u2: int) -> int:
    ts = int(time.time())
    await execute(
        "INSERT INTO relationships (user1_id, user2_id, created_at, xp, level) "
        "VALUES (?,?,?,0,1)", (u1, u2, ts))
    await execute("UPDATE users SET married_to=?, married_at=? WHERE user_id=?", (u2, ts, u1))
    await execute("UPDATE users SET married_to=?, married_at=? WHERE user_id=?", (u1, ts, u2))
    row = await fetchone("SELECT last_insert_rowid() id")
    return int(row["id"]) if row else 0


async def delete_relationship(rel_id: int) -> None:
    rel = await get_rel_by_id(rel_id)
    if rel:
        u1, u2 = rel["user1_id"], rel["user2_id"]
        for uid in (u1, u2):
            other_rels = await get_user_relationships(uid)
            rem_rels = [r for r in other_rels if r["id"] != rel_id]
            if rem_rels:
                next_rel = rem_rels[0]
                pid = next_rel["user2_id"] if next_rel["user1_id"] == uid else next_rel["user1_id"]
                await execute("UPDATE users SET married_to=?, married_at=? WHERE user_id=?",
                              (pid, next_rel["created_at"], uid))
            else:
                await execute("UPDATE users SET married_to=NULL, married_at=NULL WHERE user_id=?", (uid,))
    await execute("DELETE FROM relationships WHERE id=?", (rel_id,))
    await execute("DELETE FROM relationship_cooldowns WHERE rel_id=?", (rel_id,))
    await execute("DELETE FROM relationship_property WHERE rel_id=?", (rel_id,))
    await execute("DELETE FROM relationship_children WHERE rel_id=?", (rel_id,))



async def add_rel_xp(rel_id: int, amount: int) -> tuple[int, int, bool]:
    """Добавляет XP и возвращает (new_xp, new_level, is_level_up)."""
    rel = await get_rel_by_id(rel_id)
    if not rel:
        return 0, 1, False
    old_lvl = rel["level"]
    new_xp = rel["xp"] + amount
    new_lvl = calc_rel_level(new_xp)
    await execute("UPDATE relationships SET xp=?, level=? WHERE id=?",
                  (new_xp, new_lvl, rel_id))
    return new_xp, new_lvl, (new_lvl > old_lvl)


async def set_rel_offended(rel_id: int, offended_by: int | None) -> None:
    await execute(
        "UPDATE relationships SET offended_by=?, soothe_points=0, soothe_last_ts=0 WHERE id=?",
        (offended_by, rel_id))


async def soothe_rel(rel_id: int, points: int) -> tuple[int, bool]:
    """Добавляет очки задабривания. Возвращает (всего_очков, снята_ли_обида)."""
    rel = await get_rel_by_id(rel_id)
    if not rel:
        return 0, False
    total = rel["soothe_points"] + points
    now = int(time.time())
    if total >= 100:
        await execute(
            "UPDATE relationships SET offended_by=NULL, soothe_points=0, soothe_last_ts=? WHERE id=?",
            (now, rel_id))
        return total, True
    await execute(
        "UPDATE relationships SET soothe_points=?, soothe_last_ts=? WHERE id=?",
        (total, now, rel_id))
    return total, False


async def get_rel_cooldown_left(rel_id: int, user_id: int, action_key: str, period: int) -> int:
    row = await fetchone(
        "SELECT last_ts FROM relationship_cooldowns WHERE rel_id=? AND user_id=? AND action_key=?",
        (rel_id, user_id, action_key))
    if not row:
        return 0
    left = int(row["last_ts"]) + period - int(time.time())
    return max(0, left)


async def set_rel_cooldown(rel_id: int, user_id: int, action_key: str) -> None:
    await execute(
        "INSERT INTO relationship_cooldowns (rel_id, user_id, action_key, last_ts) VALUES (?,?,?,?) "
        "ON CONFLICT(rel_id, user_id, action_key) DO UPDATE SET last_ts=excluded.last_ts",
        (rel_id, user_id, action_key, int(time.time())))


async def get_rel_properties(rel_id: int) -> list[dict]:
    return await fetchall("SELECT * FROM relationship_property WHERE rel_id=? ORDER BY price ASC", (rel_id,))


async def add_rel_property(rel_id: int, item_key: str, item_name: str, price: int) -> None:
    await execute(
        "INSERT INTO relationship_property (rel_id, item_key, item_name, price, bought_at) "
        "VALUES (?,?,?,?,?)", (rel_id, item_key, item_name, price, int(time.time())))


async def get_rel_children(rel_id: int) -> list[dict]:
    return await fetchall("SELECT * FROM relationship_children WHERE rel_id=? ORDER BY id ASC", (rel_id,))


async def add_rel_child(rel_id: int, name: str, gender: str) -> None:
    await execute(
        "INSERT INTO relationship_children (rel_id, name, gender, born_at, care_last_ts) "
        "VALUES (?,?,?,?,?)", (rel_id, name, gender, int(time.time()), int(time.time())))


async def get_child_by_id(child_id: int) -> Optional[dict]:
    return await fetchone("SELECT * FROM relationship_children WHERE id=?", (child_id,))


async def update_child_stats(child_id: int, satiety: int, happiness: int, health: int,
                             growth_stage: int, xp: int, toys_count: int,
                             clothes_count: int, food_count: int) -> None:
    await execute(
        "UPDATE relationship_children SET satiety=?, happiness=?, health=?, "
        "growth_stage=?, xp=?, toys_count=?, clothes_count=?, food_count=?, care_last_ts=? "
        "WHERE id=?",
        (satiety, happiness, health, growth_stage, xp, toys_count, clothes_count, food_count,
         int(time.time()), child_id)
    )


async def get_all_relationships() -> list[dict]:
    return await fetchall("SELECT * FROM relationships ORDER BY level DESC, xp DESC, id ASC")


# --- Семейный банк и подарки молодожёнам ---
async def get_rel_bank(rel_id: int) -> int:
    b, _ = await get_rel_bank_with_interest(rel_id)
    return b


async def get_rel_bank_with_interest(rel_id: int) -> tuple[int, int]:
    """Возвращает (текущий_баланс, начисленный_доход). Каждые 24ч капает +1% дохода!"""
    row = await fetchone("SELECT balance, updated_at FROM relationship_bank WHERE rel_id=?", (rel_id,))
    if not row:
        return 0, 0
    bal = int(row["balance"] or 0)
    updated_at = int(row["updated_at"] or int(time.time()))
    now = int(time.time())
    interest = 0
    if bal > 0 and (now - updated_at) >= 86400:
        days = min(30, (now - updated_at) // 86400)
        interest = int(bal * 0.01 * days)
        if interest > 0:
            bal += interest
            await execute("UPDATE relationship_bank SET balance=?, updated_at=? WHERE rel_id=?", (bal, now, rel_id))
    return bal, interest


async def add_rel_bank(rel_id: int, amount: int) -> int:
    now = int(time.time())
    await execute(
        "INSERT INTO relationship_bank (rel_id, balance, updated_at) VALUES (?, MAX(0, ?), ?) "
        "ON CONFLICT(rel_id) DO UPDATE SET balance = MAX(0, balance + ?), updated_at = ?",
        (rel_id, amount, now, amount, now)
    )
    return await get_rel_bank(rel_id)


async def add_wedding_gift(rel_id: int, giver_id: int, giver_name: str, amount: int = 1000) -> tuple[int, int]:
    now = int(time.time())
    await execute(
        "INSERT INTO wedding_gifts (rel_id, giver_id, giver_name, amount, ts) VALUES (?, ?, ?, ?, ?)",
        (rel_id, giver_id, giver_name, amount, now)
    )
    # Пополняем семейный банк пары на сумму подарка
    await add_rel_bank(rel_id, amount)
    return await get_wedding_gifts_stats(rel_id)


async def get_wedding_gifts_stats(rel_id: int) -> tuple[int, int]:
    row = await fetchone("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as cnt FROM wedding_gifts WHERE rel_id=?", (rel_id,))
    if not row:
        return 0, 0
    return int(row["total"] or 0), int(row["cnt"] or 0)


# --- Турниры казино и крупные заносы ---
async def record_big_win(user_id: int, user_name: str, chat_id: int, game_name: str, bet: int, win_amount: int) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO casino_big_wins (user_id, user_name, chat_id, game_name, bet, win_amount, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, user_name, chat_id, game_name, bet, win_amount, now)
    )


async def get_weekly_big_wins(limit: int = 10) -> list[dict]:
    week_ago = int(time.time()) - (7 * 86400)
    rows = await fetchall(
        "SELECT user_id, user_name, game_name, bet, MAX(win_amount) as max_win, ts "
        "FROM casino_big_wins WHERE ts >= ? "
        "GROUP BY user_id ORDER BY max_win DESC LIMIT ?",
        (week_ago, limit)
    )
    return [dict(r) for r in rows]


# ================== ДРУЗЬЯ (ДРУЖЕСКИЕ ОТНОШЕНИЯ) ==================

async def add_friend(u1: int, u2: int) -> bool:
    """Добавляет двух пользователей в друзья."""
    u_min, u_max = min(u1, u2), max(u1, u2)
    now = int(time.time())
    res = await execute(
        "INSERT OR IGNORE INTO friends (user1_id, user2_id, created_at) VALUES (?, ?, ?)",
        (u_min, u_max, now))
    return bool(res)


async def remove_friend(u1: int, u2: int) -> bool:
    """Удаляет дружбу между двумя пользователями."""
    u_min, u_max = min(u1, u2), max(u1, u2)
    res = await execute(
        "DELETE FROM friends WHERE user1_id=? AND user2_id=?", (u_min, u_max))
    return bool(res)


async def are_friends(u1: int, u2: int) -> bool:
    """Проверяет, дружат ли пользователи."""
    u_min, u_max = min(u1, u2), max(u1, u2)
    row = await fetchone(
        "SELECT 1 FROM friends WHERE user1_id=? AND user2_id=?", (u_min, u_max))
    return bool(row)


async def get_friends(uid: int) -> list[dict]:
    """Возвращает список друзей пользователя."""
    return await fetchall(
        "SELECT CASE WHEN user1_id=? THEN user2_id ELSE user1_id END AS friend_id, created_at "
        "FROM friends WHERE user1_id=? OR user2_id=? ORDER BY created_at DESC",
        (uid, uid, uid))


async def count_friends(uid: int) -> int:
    """Возвращает количество друзей."""
    row = await fetchone(
        "SELECT COUNT(*) c FROM friends WHERE user1_id=? OR user2_id=?", (uid, uid))
    return int(row["c"]) if row else 0


# --- Обручальные кольца пары ---
async def get_rel_ring(rel_id: int) -> dict | None:
    row = await fetchone("SELECT ring_key, giver_id, ts FROM relationship_rings WHERE rel_id=?", (rel_id,))
    return dict(row) if row else None


async def set_rel_ring(rel_id: int, ring_key: str, giver_id: int) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO relationship_rings (rel_id, ring_key, giver_id, ts) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(rel_id) DO UPDATE SET ring_key=excluded.ring_key, giver_id=excluded.giver_id, ts=excluded.ts",
        (rel_id, ring_key, giver_id, now)
    )


# --- Гараж и Автомобили ---
async def get_user_cars(user_id: int) -> list[dict]:
    rows = await fetchall("SELECT id, car_key, bought_at, is_active FROM user_cars WHERE user_id=? ORDER BY id ASC", (user_id,))
    return [dict(r) for r in rows]


async def get_user_active_car(user_id: int) -> dict | None:
    row = await fetchone("SELECT id, car_key, bought_at FROM user_cars WHERE user_id=? AND is_active=1 ORDER BY id DESC LIMIT 1", (user_id,))
    return dict(row) if row else None


async def add_user_car(user_id: int, car_key: str) -> int:
    now = int(time.time())
    await execute("UPDATE user_cars SET is_active=0 WHERE user_id=?", (user_id,))
    cur = await execute("INSERT INTO user_cars (user_id, car_key, bought_at, is_active) VALUES (?, ?, ?, 1)", (user_id, car_key, now))
    return int(cur.lastrowid or 0)


async def set_active_car(user_id: int, car_id: int) -> bool:
    row = await fetchone("SELECT 1 FROM user_cars WHERE id=? AND user_id=?", (car_id, user_id))
    if not row:
        return False
    await execute("UPDATE user_cars SET is_active=0 WHERE user_id=?", (user_id,))
    await execute("UPDATE user_cars SET is_active=1 WHERE id=? AND user_id=?", (car_id, user_id))
    return True


async def remove_user_car(user_id: int, car_id: int) -> bool:
    row = await fetchone("SELECT is_active FROM user_cars WHERE id=? AND user_id=?", (car_id, user_id))
    if not row:
        return False
    await execute("DELETE FROM user_cars WHERE id=? AND user_id=?", (car_id, user_id))
    if row["is_active"]:
        rem = await fetchone("SELECT id FROM user_cars WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
        if rem:
            await execute("UPDATE user_cars SET is_active=1 WHERE id=?", (rem["id"],))
    return True


# --- Кометы (валюта comets / comets engine) -----------------------------
async def get_comets(user_id: int) -> int:
    return await get_grams(user_id)


async def add_comets(user_id: int, amount: int, action: str = "", meta: str = "") -> int:
    return await add_grams(user_id, amount, action, meta)


async def set_comets(user_id: int, amount: int) -> int:
    return await set_grams(user_id, amount)


# --- Игровой уровень и XP (1-100 LVL) -----------------------------------
import bisect

_BASE_LVLS = [
    (1, 0), (2, 10), (3, 25), (4, 50), (5, 90), (6, 150), (7, 230), (8, 330),
    (9, 450), (10, 600), (11, 800), (12, 1050), (13, 1350), (14, 1700),
    (15, 2100), (16, 2600), (17, 3200), (18, 3900), (19, 4700), (20, 5600),
]
GAME_LVL_THRESHOLDS = list(_BASE_LVLS)
_cur_xp = 5600
for _l in range(21, 10001):
    _step = int(900 + (_l - 20) * 120)
    _cur_xp += _step
    GAME_LVL_THRESHOLDS.append((_l, _cur_xp))

_THRESHOLDS_XP = [t[1] for t in GAME_LVL_THRESHOLDS]


def _calc_game_lvl(xp: int) -> tuple[int, int, int]:
    """Возвращает (level, next_xp_req, cur_level_base_xp) масштабируемый до 10 000 LVL."""
    if xp <= 0:
        return 1, GAME_LVL_THRESHOLDS[1][1], 0
    idx = bisect.bisect_right(_THRESHOLDS_XP, xp)
    if idx >= len(GAME_LVL_THRESHOLDS):
        max_t = GAME_LVL_THRESHOLDS[-1]
        return 10000, max_t[1] + 10000 * 500, max_t[1]
    cur_lvl = GAME_LVL_THRESHOLDS[idx - 1][0]
    cur_base = GAME_LVL_THRESHOLDS[idx - 1][1]
    next_req = GAME_LVL_THRESHOLDS[idx][1]
    return min(10000, cur_lvl), next_req, cur_base


async def get_game_profile(user_id: int) -> dict:
    await get_user(user_id)
    row = await fetchone("SELECT xp, games_played, games_won FROM game_stats WHERE user_id=?", (user_id,))
    if not row:
        return {"xp": 0, "level": 1, "next_xp": 10, "cur_base": 0, "games_played": 0, "games_won": 0, "progress_pct": 0}
    xp = int(row["xp"] or 0)
    lvl, next_xp, cur_base = _calc_game_lvl(xp)
    played = int(row["games_played"] or 0)
    won = int(row["games_won"] or 0)
    denom = max(1, next_xp - cur_base)
    progress_pct = min(100, max(0, int(((xp - cur_base) / denom) * 100)))
    return {
        "xp": xp,
        "level": lvl,
        "next_xp": next_xp,
        "cur_base": cur_base,
        "games_played": played,
        "games_won": won,
        "progress_pct": progress_pct
    }


async def add_game_xp(user_id: int, xp_amount: int = 1, is_win: bool = False) -> tuple[int, bool]:
    """Начисляет игровой опыт и возвращает (новый_уровень, повысился_ли_уровень)."""
    await get_user(user_id)
    win_add = 1 if is_win else 0
    row = await fetchone("SELECT xp FROM game_stats WHERE user_id=?", (user_id,))
    old_xp = int(row["xp"] or 0) if row else 0
    old_lvl, _, _ = _calc_game_lvl(old_xp)
    
    new_xp = old_xp + xp_amount
    new_lvl, _, _ = _calc_game_lvl(new_xp)
    
    await execute(
        "INSERT INTO game_stats (user_id, xp, games_played, games_won) VALUES (?, ?, 1, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET xp=xp+?, games_played=games_played+1, games_won=games_won+?",
        (user_id, new_xp, win_add, xp_amount, win_add)
    )
    return new_lvl, (new_lvl > old_lvl)


# --- Предприятия и имущество за Кометы ---------------------------------
async def get_user_businesses(user_id: int) -> dict[str, dict]:
    """Возвращает {biz_key: {'count': count, 'last_collect': last_collect}}."""
    rows = await fetchall("SELECT biz_key, count, last_collect FROM user_businesses WHERE user_id=? AND count > 0", (user_id,))
    res = {}
    for r in rows:
        res[r["biz_key"]] = {"count": int(r["count"]), "last_collect": int(r["last_collect"] or 0)}
    return res


async def change_user_business(user_id: int, biz_key: str, count_delta: int) -> int:
    now = int(time.time())
    row = await fetchone("SELECT count, last_collect FROM user_businesses WHERE user_id=? AND biz_key=?", (user_id, biz_key))
    if not row:
        new_cnt = max(0, count_delta)
        if new_cnt > 0:
            await execute("INSERT INTO user_businesses (user_id, biz_key, count, last_collect) VALUES (?, ?, ?, ?)",
                          (user_id, biz_key, new_cnt, now))
        return new_cnt


    else:
        new_cnt = max(0, int(row["count"]) + count_delta)
        if new_cnt == 0:
            await execute("DELETE FROM user_businesses WHERE user_id=? AND biz_key=?", (user_id, biz_key))
        else:
            await execute("UPDATE user_businesses SET count=? WHERE user_id=? AND biz_key=?", (new_cnt, user_id, biz_key))
        return new_cnt


async def update_business_collect_time(user_id: int, biz_keys: Iterable[str]) -> None:
    now = int(time.time())
    keys = list(biz_keys)
    if not keys:
        return
    placeholders = ", ".join("?" for _ in keys)
    await execute(
        f"UPDATE user_businesses SET last_collect=? WHERE user_id=? AND biz_key IN ({placeholders})",
        (now, user_id, *keys)
    )




# --- Улучшение предприятий (до 10 000 LVL) --------------------------------
async def get_business_level(user_id: int, biz_key: str) -> int:
    """Возвращает уровень предприятия игрока (по умолчанию 1)."""
    row = await fetchone("SELECT level FROM business_upgrades WHERE user_id=? AND biz_key=?", (user_id, biz_key))
    return int(row["level"]) if row else 1


async def get_user_business_levels(user_id: int) -> dict[str, int]:
    """Возвращает словарь {biz_key: level} для всех улучшений игрока."""
    rows = await fetchall("SELECT biz_key, level FROM business_upgrades WHERE user_id=?", (user_id,))
    return {r["biz_key"]: int(r["level"]) for r in rows}


async def upgrade_business_level(user_id: int, biz_key: str, levels: int = 1) -> tuple[bool, int, str]:
    """Улучшает предприятие на указанное количество уровней (до 10 000 LVL).
    Каждый уровень даёт +5% к доходу предприятия.
    Возвращает (успех, новый_уровень, сообщение).
    """
    levels = max(1, min(10000, levels))
    cur_lvl = await get_business_level(user_id, biz_key)
    if cur_lvl >= 10000:
        return False, cur_lvl, "Предприятие уже достигло максимального 10 000 уровня!"

    new_lvl = min(10000, cur_lvl + levels)
    actual_levels = new_lvl - cur_lvl

    from h_grams import BUSINESS_TYPES
    info = BUSINESS_TYPES.get(biz_key)
    base_price = info["base_price"] if info else 10000
    base_cost = max(500, int(base_price * 0.15))

    total_cost = 0
    for i in range(actual_levels):
        lvl_i = cur_lvl + i
        total_cost += int(base_cost * (1 + 0.04 * (lvl_i - 1)))

    bal = await get_balance(user_id)
    if bal < total_cost:
        return False, cur_lvl, f"Недостаточно ирисок. Требуется: <b>{total_cost:,}</b>, ваш баланс: <b>{bal:,}</b>."

    await add_coins(user_id, -total_cost, "upgrade_biz", f"{biz_key}:{new_lvl}")
    await execute(
        "INSERT INTO business_upgrades (user_id, biz_key, level) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, biz_key) DO UPDATE SET level=?",
        (user_id, biz_key, new_lvl, new_lvl)
    )
    bonus_pct = (new_lvl - 1) * 5
    return True, new_lvl, f"✅ Предприятие успешно прокачано на +{actual_levels} ур.!\nТекущий уровень: <b>{new_lvl:,} LVL</b>\nБонус к прибыли: <b>+{bonus_pct}%</b>"


# --- Питомцы (RPG Pets) ------------------------------------------------
async def get_user_pet(user_id: int) -> dict | None:
    return await fetchone("SELECT * FROM user_pets WHERE user_id=?", (user_id,))


async def create_user_pet(user_id: int, pet_type: str, pet_name: str) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO user_pets (user_id, pet_type, pet_name, level, xp, hunger, last_feed) "
        "VALUES (?, ?, ?, 1, 0, 100, ?) ON CONFLICT(user_id) DO UPDATE SET "
        "pet_type=excluded.pet_type, pet_name=excluded.pet_name, level=1, xp=0, hunger=100, last_feed=excluded.last_feed",
        (user_id, pet_type, pet_name, now)
    )


async def update_user_pet(user_id: int, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields.keys())
    vals = list(fields.values()) + [user_id]
    await execute(f"UPDATE user_pets SET {sets} WHERE user_id=?", vals)


# --- P2P Рынок и Аукцион -----------------------------------------------
async def create_market_lot(seller_id: int, seller_name: str, item_id: str, item_name: str, count: int, price: int) -> int:
    now = int(time.time())
    cursor = await execute(
        "INSERT INTO market_lots (seller_id, seller_name, item_id, item_name, count, price, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (seller_id, seller_name, item_id, item_name, count, price, now)
    )
    return cursor.lastrowid if cursor else 0


async def get_market_lots(limit: int = 15, offset: int = 0) -> list[dict]:
    return await fetchall("SELECT * FROM market_lots ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))


async def count_market_lots() -> int:
    row = await fetchone("SELECT COUNT(*) c FROM market_lots")
    return int(row["c"]) if row else 0


async def get_market_lot_by_id(lot_id: int) -> dict | None:
    return await fetchone("SELECT * FROM market_lots WHERE id=?", (lot_id,))


async def delete_market_lot(lot_id: int) -> None:
    await execute("DELETE FROM market_lots WHERE id=?", (lot_id,))


async def get_user_market_lots(user_id: int) -> list[dict]:
    return await fetchall("SELECT * FROM market_lots WHERE seller_id=? ORDER BY id DESC", (user_id,))


# --- Подземелья (Dungeon) -----------------------------------------------
async def get_dungeon_progress(user_id: int) -> dict | None:
    return await fetchone("SELECT * FROM user_dungeon_progress WHERE user_id=?", (user_id,))


async def save_dungeon_progress(user_id: int, floor: int, room: int, hp: int, max_hp: int, gold_found: int, xp_found: int, active: int, state_data: str) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO user_dungeon_progress (user_id, floor, room, hp, max_hp, gold_found, xp_found, active, state_data, last_action_ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
        "floor=excluded.floor, room=excluded.room, hp=excluded.hp, max_hp=excluded.max_hp, "
        "gold_found=excluded.gold_found, xp_found=excluded.xp_found, active=excluded.active, "
        "state_data=excluded.state_data, last_action_ts=excluded.last_action_ts",
        (user_id, floor, room, hp, max_hp, gold_found, xp_found, active, state_data, now)
    )


# --- Джекпот Чата ------------------------------------------------------
async def get_chat_jackpot(chat_id: int) -> dict:
    row = await fetchone("SELECT * FROM chat_jackpot WHERE chat_id=?", (chat_id,))
    if not row:
        await execute("INSERT OR IGNORE INTO chat_jackpot (chat_id, pool) VALUES (?, 5000)", (chat_id,))
        row = await fetchone("SELECT * FROM chat_jackpot WHERE chat_id=?", (chat_id,))
    return row or {"chat_id": chat_id, "pool": 5000, "last_winner_id": None, "last_winner_name": None, "last_winner_amount": 0}


async def add_to_chat_jackpot(chat_id: int, amount: int) -> int:
    await execute(
        "INSERT INTO chat_jackpot (chat_id, pool) VALUES (?, 5000 + ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET pool = pool + excluded.pool",
        (chat_id, amount)
    )
    row = await fetchone("SELECT pool FROM chat_jackpot WHERE chat_id=?", (chat_id,))
    return int(row["pool"]) if row else 5000


async def claim_chat_jackpot(chat_id: int, winner_id: int, winner_name: str) -> int:
    row = await get_chat_jackpot(chat_id)
    cur_pool = int(row.get("pool", 5000))
    now = int(time.time())
    await execute(
        "UPDATE chat_jackpot SET pool=5000, last_winner_id=?, last_winner_name=?, last_winner_amount=?, last_win_ts=? WHERE chat_id=?",
        (winner_id, winner_name, cur_pool, now, chat_id)
    )
    return cur_pool


# --- Титулы и Значки Профиля -------------------------------------------
async def get_user_titles(user_id: int) -> list[str]:
    rows = await fetchall("SELECT title_id FROM user_titles WHERE user_id=?", (user_id,))
    return [r["title_id"] for r in rows]


async def unlock_user_title(user_id: int, title_id: str) -> None:
    now = int(time.time())
    await execute("INSERT OR IGNORE INTO user_titles (user_id, title_id, unlocked_at) VALUES (?, ?, ?)",
                  (user_id, title_id, now))


async def get_active_title(user_id: int) -> str | None:
    return await get_setting(user_id, "active_title", "")


async def set_active_title(user_id: int, title_id: str) -> None:
    await set_setting(user_id, "active_title", title_id)


# --- Чат-игра «Угадай слово» -------------------------------------------
async def get_active_word_game(chat_id: int) -> dict | None:
    return await fetchone("SELECT * FROM party_words_game WHERE chat_id=? AND active=1", (chat_id,))


async def set_word_game(chat_id: int, word: str, hint: str, reward_coins: int = 250, reward_xp: int = 30) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO party_words_game (chat_id, word, hint, reward_coins, reward_xp, active, created_at) "
        "VALUES (?, ?, ?, ?, ?, 1, ?) ON CONFLICT(chat_id) DO UPDATE SET "
        "word=excluded.word, hint=excluded.hint, reward_coins=excluded.reward_coins, reward_xp=excluded.reward_xp, active=1, created_at=excluded.created_at",
        (chat_id, word, hint, reward_coins, reward_xp, now)
    )


async def finish_word_game(chat_id: int) -> None:
    await execute("UPDATE party_words_game SET active=0 WHERE chat_id=?", (chat_id,))


# --- Отзывы о боте и покупках ---------------------------------------------
async def add_review(user_id: int, user_name: str, rating: int, text: str, item_purchased: str = "") -> int:
    now = int(time.time())
    rating = max(1, min(5, rating))
    async with conn().execute(
        "INSERT INTO reviews (user_id, user_name, rating, text, item_purchased, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, user_name, rating, text, item_purchased, now)
    ) as cur:
        await conn().commit()
        return int(cur.lastrowid)


async def get_reviews(limit: int = 10) -> list[dict]:
    rows = await fetchall("SELECT * FROM reviews ORDER BY ts DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


async def get_review_stats() -> dict:
    row = await fetchone("SELECT COUNT(*) cnt, AVG(rating) avg_r FROM reviews")
    cnt = int(row["cnt"] or 0) if row else 0
    avg_r = float(row["avg_r"] or 5.0) if row and row["avg_r"] else 5.0
    return {"total": cnt, "avg_rating": round(avg_r, 1)}


# --- Идеи и предложения ----------------------------------------------------
async def add_suggestion(user_id: int, user_name: str, text: str) -> int:
    now = int(time.time())
    async with conn().execute(
        "INSERT INTO suggestions (user_id, user_name, text, status, upvotes, downvotes, ts) VALUES (?, ?, ?, 'pending', 0, 0, ?)",
        (user_id, user_name, text, now)
    ) as cur:
        await conn().commit()
        return int(cur.lastrowid)


async def get_suggestion(sug_id: int) -> dict | None:
    row = await fetchone("SELECT * FROM suggestions WHERE id=?", (sug_id,))
    return dict(row) if row else None


async def vote_suggestion(sug_id: int, user_id: int, vote: int) -> tuple[int, int, str]:
    """vote: 1 (up) or -1 (down). Returns (upvotes, downvotes, message)."""
    cur_vote = await fetchone("SELECT vote FROM suggestion_votes WHERE suggestion_id=? AND user_id=?", (sug_id, user_id))
    if cur_vote:
        if cur_vote["vote"] == vote:
            return 0, 0, "already_voted"
        await execute("UPDATE suggestion_votes SET vote=? WHERE suggestion_id=? AND user_id=?", (vote, sug_id, user_id))
    else:
        await execute("INSERT INTO suggestion_votes (suggestion_id, user_id, vote) VALUES (?, ?, ?)", (sug_id, user_id, vote))

    up_row = await fetchone("SELECT COUNT(*) c FROM suggestion_votes WHERE suggestion_id=? AND vote=1", (sug_id,))
    down_row = await fetchone("SELECT COUNT(*) c FROM suggestion_votes WHERE suggestion_id=? AND vote=-1", (sug_id,))
    up = int(up_row["c"] or 0) if up_row else 0
    down = int(down_row["c"] or 0) if down_row else 0
    await execute("UPDATE suggestions SET upvotes=?, downvotes=? WHERE id=?", (up, down, sug_id))
    return up, down, "voted"


async def update_suggestion_status(sug_id: int, status: str) -> bool:
    await execute("UPDATE suggestions SET status=? WHERE id=?", (status, sug_id))
    return True


async def get_suggestions(limit: int = 10, status: str | None = None) -> list[dict]:
    if status:
        rows = await fetchall("SELECT * FROM suggestions WHERE status=? ORDER BY (upvotes - downvotes) DESC, ts DESC LIMIT ?", (status, limit))
    else:
        rows = await fetchall("SELECT * FROM suggestions ORDER BY (upvotes - downvotes) DESC, ts DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


# --- Служба техподдержки и тикетов -----------------------------------------
async def create_support_ticket(user_id: int, user_name: str, text: str) -> int:
    now = int(time.time())
    async with conn().execute(
        "INSERT INTO support_tickets (user_id, user_name, text, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (user_id, user_name, text, now)
    ) as cur:
        await conn().commit()
        return int(cur.lastrowid)


async def get_support_ticket(ticket_id: int) -> dict | None:
    row = await fetchone("SELECT * FROM support_tickets WHERE id=?", (ticket_id,))
    return dict(row) if row else None


async def get_open_tickets(limit: int = 15) -> list[dict]:
    rows = await fetchall(
        "SELECT * FROM support_tickets WHERE status IN ('open', 'pending', 'auto_rejected') "
        "ORDER BY created_at ASC LIMIT ?",
        (limit,)
    )
    return [dict(r) for r in rows]


async def get_unanswered_tickets_older_than(seconds: int = 6 * 3600) -> list[dict]:
    threshold = int(time.time()) - seconds
    rows = await fetchall(
        "SELECT * FROM support_tickets WHERE status='open' AND created_at <= ? AND answered_by IS NULL",
        (threshold,)
    )
    return [dict(r) for r in rows]


async def answer_support_ticket(ticket_id: int, answer_text: str, answered_by: int = 0, answered_name: str = "", is_ai: bool = False) -> bool:
    now = int(time.time())
    ai_flag = 1 if is_ai else 0
    await execute(
        "UPDATE support_tickets SET status='closed', answer_text=?, answered_by=?, answered_name=?, answered_at=?, ai_answered=? WHERE id=?",
        (answer_text, answered_by, answered_name, now, ai_flag, ticket_id)
    )
    return True


async def close_support_ticket(ticket_id: int, closed_by: int = 0, closed_name: str = "Администрация") -> bool:
    now = int(time.time())
    await execute(
        "UPDATE support_tickets SET status='closed', answered_by=?, answered_name=?, answered_at=? WHERE id=?",
        (closed_by, closed_name, now, ticket_id)
    )
    return True


# ══════════════════ АНОНСЫ И ПЕРЕКЛИЧКИ С ИИ ══════════════════

async def create_announcement(chat_id: int, creator_id: int, title: str, text: str, event_type: str = "general") -> int:
    now = int(time.time())
    cur = await execute(
        "INSERT INTO announcements (chat_id, creator_id, title, text, event_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, creator_id, title, text, event_type, now)
    )
    return int(cur.lastrowid or 0)


async def set_announcement_msg_id(ann_id: int, msg_id: int) -> None:
    await execute("UPDATE announcements SET msg_id = ? WHERE id = ?", (msg_id, ann_id))


async def record_announcement_vote(ann_id: int, user_id: int, user_name: str, vote: str) -> None:
    now = int(time.time())
    await execute(
        "INSERT INTO announcement_votes (ann_id, user_id, user_name, vote, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(ann_id, user_id) DO UPDATE SET vote = excluded.vote, user_name = excluded.user_name, updated_at = excluded.updated_at",
        (ann_id, user_id, user_name, vote, now)
    )


async def get_announcement_vote_counts(ann_id: int) -> dict[str, int]:
    rows = await fetchall("SELECT vote, COUNT(*) as cnt FROM announcement_votes WHERE ann_id = ? GROUP BY vote", (ann_id,))
    counts = {"yes": 0, "no": 0, "late": 0}
    for r in rows:
        v = r["vote"]
        if v in counts:
            counts[v] = int(r["cnt"])
    return counts


async def get_announcement_votes_detailed(ann_id: int) -> dict[str, list[str]]:
    rows = await fetchall("SELECT user_id, user_name, vote FROM announcement_votes WHERE ann_id = ? ORDER BY updated_at ASC", (ann_id,))
    res = {"yes": [], "no": [], "late": []}
    for r in rows:
        v = r["vote"]
        if v in res:
            res[v].append(r["user_name"] or str(r["user_id"]))
    return res


async def get_announcement(ann_id: int) -> dict | None:
    return await fetchone("SELECT * FROM announcements WHERE id = ?", (ann_id,))


# --- Цитатник чата ---------------------------------------------------
async def add_chat_quote(chat_id: int, user_id: int, quote_text: str, author_name: str, adder_name: str) -> int:
    now = int(time.time())
    cur = await execute(
        "INSERT INTO chat_quotes (chat_id, user_id, quote_text, author_name, adder_name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, user_id, quote_text, author_name, adder_name, now)
    )
    return int(cur.lastrowid or 0)


async def get_random_chat_quote(chat_id: int) -> dict | None:
    return await fetchone(
        "SELECT quote_text, author_name, adder_name, created_at FROM chat_quotes WHERE chat_id=? ORDER BY RANDOM() LIMIT 1",
        (chat_id,)
    )


async def get_chat_quotes_count(chat_id: int) -> int:
    row = await fetchone("SELECT COUNT(*) as cnt FROM chat_quotes WHERE chat_id=?", (chat_id,))
    return int(row["cnt"]) if row else 0


# --- Пара Дня (Шипперинг) -------------------------------------------
async def get_pair_of_day(chat_id: int, date_str: str) -> dict | None:
    return await fetchone(
        "SELECT user1_id, user2_id, user1_name, user2_name, compatibility, story FROM chat_pair_of_day "
        "WHERE chat_id=? AND date_str=?",
        (chat_id, date_str)
    )


async def set_pair_of_day(chat_id: int, date_str: str, u1_id: int, u2_id: int,
                          u1_name: str, u2_name: str, compat: int, story: str) -> None:
    await execute(
        "INSERT OR REPLACE INTO chat_pair_of_day "
        "(chat_id, date_str, user1_id, user2_id, user1_name, user2_name, compatibility, story) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (chat_id, date_str, u1_id, u2_id, u1_name, u2_name, compat, story)
    )


# --- Фильтр запрещённых слов ----------------------------------------
async def add_filtered_word(chat_id: int, word: str, action: str = "warn") -> None:
    await execute(
        "INSERT INTO word_filters (chat_id, word, action) VALUES (?,?,?) "
        "ON CONFLICT(chat_id, word) DO UPDATE SET action=excluded.action",
        (chat_id, word.lower().strip(), action)
    )


async def remove_filtered_word(chat_id: int, word: str) -> None:
    await execute(
        "DELETE FROM word_filters WHERE chat_id=? AND lower(word)=lower(?)",
        (chat_id, word.strip())
    )


async def get_filtered_words(chat_id: int) -> list[dict]:
    return await fetchall("SELECT word, action FROM word_filters WHERE chat_id=?", (chat_id,))


async def clear_filtered_words(chat_id: int) -> None:
    await execute("DELETE FROM word_filters WHERE chat_id=?", (chat_id,))


async def close() -> None:
    global _conn
    if _conn:
        try:
            await _conn.close()
        except Exception:
            pass
        _conn = None


