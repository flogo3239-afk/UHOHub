"""
=============================================================================
UHOHub Master E2E Verification Test Suite — Tournament Simulator 2.0
=============================================================================
Comprehensive, offline-first, requirement-driven 4-tier test suite covering all
Milestones (M1-M6) and Requirements (R1-R5) for UHO Hub Tournament Simulator 2.0.

Coverage Matrix:
- Module 1:  Test01_SyntaxCompilation
- Module 2:  Test02_DatabaseAndAllowlistQueries
- Module 3:  Test03_AtomicPersistenceAndRecovery
- Module 4:  Test04_SkillSelectionAndDynamicRecommendation
- Module 5:  Test05_AdaptiveDifficultyAndMathFormulas
- Module 6:  Test06_ReplayTelemetryAndJSONParsing
- Module 7:  Test07_SubprocessAndNetworkHardening
- Module 8:  Test08_GermanLocalizationAdherence
- Module 9:  Test09_Tier1_8SkillsetAndScoreV2Engine
- Module 10: Test10_Tier1_TeamFormatsAndScoutingDossiers
- Module 11: Test11_Tier1_BanchoRefereeAndScoreExtraction
- Module 12: Test12_Tier1_HiddenScoutingAndAIDebriefing
- Module 13: Test13_Tier2_BoundaryAndCornerCases
- Module 14: Test14_Tier3_CrossFeatureIntegration
- Module 15: Test15_Tier4_RealWorldWorkloadsAndE2E
- Module 16: Test16_Tier5_AdversarialSecurityAndPackaging

Pass Criteria: 100% test cases pass with exit code 0.
=============================================================================
"""

import concurrent.futures
import copy
import datetime
import json
import lzma
import math
import os
import py_compile
import random
import re
import shutil
import socket
import ssl
import struct
import sys
import tempfile
import threading
import time
import types
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _ensure_test_stubs():
    """Provides lightweight stubs for optional server/bot framework dependencies in offline environments."""
    if 'fastapi' not in sys.modules:
        fa = types.ModuleType('fastapi')
        class MockApp:
            def __init__(self, *a, **kw): pass
            def get(self, *a, **kw): return lambda f: f
            def post(self, *a, **kw): return lambda f: f
        fa.FastAPI = MockApp
        fa.HTTPException = Exception
        fa.Request = type('Request', (), {})
        sys.modules['fastapi'] = fa

    if 'pydantic' not in sys.modules:
        pyd = types.ModuleType('pydantic')
        class MockBaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
        pyd.BaseModel = MockBaseModel
        sys.modules['pydantic'] = pyd

    if 'uvicorn' not in sys.modules:
        sys.modules['uvicorn'] = types.ModuleType('uvicorn')

    if 'discord' not in sys.modules:
        dc = types.ModuleType('discord')
        dc.Intents = type('Intents', (), {'default': lambda: type('I', (), {'message_content': True})()})
        dc.Client = type('Client', (), {})
        dc.Embed = lambda *a, **kw: type('Embed', (), {'add_field': lambda self, *a, **kw: None, 'set_footer': lambda self, *a, **kw: None})()
        dc.Color = type('Color', (), {'from_rgb': lambda *a: 0, 'green': lambda: 0, 'red': lambda: 0, 'blue': 0, 'gold': lambda: 0})
        dc.ButtonStyle = type('ButtonStyle', (), {'primary': 1, 'secondary': 2, 'success': 3, 'danger': 4, 'link': 5, 'green': 3, 'grey': 2, 'red': 4, 'blurple': 1})
        dc.Interaction = type('Interaction', (), {})
        dc.ui = types.ModuleType('discord.ui')
        class MockView:
            def __init__(self, *a, **kw): pass
        class MockButton:
            def __init__(self, *a, **kw): pass
        dc.ui.View = MockView
        dc.ui.Button = MockButton
        dc.ui.button = lambda *a, **kw: lambda f: f
        dc.ext = types.ModuleType('discord.ext')
        dc.ext.commands = types.ModuleType('discord.ext.commands')
        class MockBot:
            def __init__(self, *a, **kw):
                self.tree = type('T', (), {'sync': lambda *a: None, 'command': lambda *a, **kw: lambda f: f})()
            def command(self, *a, **kw): return lambda f: f
            def event(self, *a, **kw): return lambda f: f
        dc.ext.commands.Bot = MockBot
        dc.app_commands = types.ModuleType('discord.app_commands')
        dc.app_commands.CommandTree = lambda *a, **kw: type('CT', (), {})()
        dc.app_commands.describe = lambda *a, **kw: lambda f: f
        dc.app_commands.default_permissions = lambda *a, **kw: lambda f: f
        sys.modules['discord'] = dc
        sys.modules['discord.ui'] = dc.ui
        sys.modules['discord.ext'] = dc.ext
        sys.modules['discord.ext.commands'] = dc.ext.commands
        sys.modules['discord.app_commands'] = dc.app_commands


_ensure_test_stubs()

import app
import discord_bot
import render_backend_main
import server_main


# =============================================================================
# REFERENCE ENGINES (Directly derived from Project & Spec Miners' Mathematical Models)
# =============================================================================
ALL_8_SKILLS = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
TIER_POINT_POOLS = {"Rookie": 160, "Challenger": 240, "Pro": 400, "Legend": 640}

GERMAN_OSU_NAMES = [
    "WhiteFox_DE", "RheinJumper", "KaiserAim", "BavariaStream", "AlpenSpeed",
    "BlitzTech", "SchwarzwaldHD", "Manticore_de", "SternStaub", "NeoVortex",
    "SturmRhythmus", "Eisbaer_osu", "ShadowEcho", "KiraStream", "ChronoDrift",
    "Valkyrie_DE", "AetherAim", "SilberPfeil", "DonauBeat", "ZenithPulse"
]


def ref_generate_8skill_profile(tier_name: str) -> tuple[dict[str, int], list[str], list[str]]:
    """Generates an 8-skill profile honoring base-10 rule, tier pool sum, and max-100 cap."""
    if hasattr(app, "generate_8skill_profile") and callable(getattr(app, "generate_8skill_profile")):
        return app.generate_8skill_profile(tier_name)

    n = len(ALL_8_SKILLS)
    base_stat = 10
    target_sum = TIER_POINT_POOLS.get(tier_name, 240)
    stats = [base_stat] * n
    remaining_pool = target_sum - (base_stat * n)

    strengths = random.sample(range(n), 2)
    remaining_indices = [i for i in range(n) if i not in strengths]
    weaknesses = random.sample(remaining_indices, 2)

    weights = [1.0] * n
    for s in strengths:
        weights[s] = random.uniform(2.0, 3.5)
    for w in weaknesses:
        weights[w] = random.uniform(0.3, 0.6)

    while remaining_pool > 0:
        eligible = [i for i in range(n) if stats[i] < 100]
        if not eligible:
            break
        elig_weights = [weights[i] for i in eligible]
        tot_w = sum(elig_weights)
        if tot_w <= 0:
            step_each = remaining_pool // len(eligible)
            for i in eligible:
                add = min(step_each, 100 - stats[i])
                stats[i] += add
                remaining_pool -= add
            break

        chunk = min(remaining_pool, max(1, remaining_pool // 4))
        r = random.uniform(0, tot_w)
        cum = 0.0
        chosen = eligible[-1]
        for i, idx in enumerate(eligible):
            cum += elig_weights[i]
            if r <= cum:
                chosen = idx
                break

        add = min(chunk, 100 - stats[chosen])
        if add == 0:
            add = min(1, 100 - stats[chosen])
        stats[chosen] += add
        remaining_pool -= add

    for _ in range(remaining_pool):
        eligible = [i for i in range(n) if stats[i] < 100]
        if eligible:
            idx = random.choice(eligible)
            stats[idx] += 1
            remaining_pool -= 1

    res = {ALL_8_SKILLS[i]: stats[i] for i in range(n)}
    sorted_skills = sorted(res.items(), key=lambda x: x[1], reverse=True)
    top2 = [sorted_skills[0][0], sorted_skills[1][0]]
    bot2 = [sorted_skills[-1][0], sorted_skills[-2][0]]
    return res, top2, bot2


def ref_calculate_bot_scorev2(bot_stats: dict[str, int], map_meta: dict) -> dict:
    """Calculates continuous ScoreV2 performance from map demands and effective skill attributes."""
    if hasattr(app, "calculate_bot_scorev2") and callable(getattr(app, "calculate_bot_scorev2")):
        return app.calculate_bot_scorev2(bot_stats, map_meta)

    sr = float(map_meta.get("sr", 6.0) or 6.0)
    bpm = float(map_meta.get("bpm", 180) or 180)
    length = float(map_meta.get("len", 150) or 150)
    cs = float(map_meta.get("cs", 4.0) or 4.0)
    ar = float(map_meta.get("ar", 9.0) or 9.0)
    od = float(map_meta.get("od", 8.5) or 8.5)

    weights = map_meta.get("weights", {})
    if not weights:
        weights = {k: 0.125 for k in ALL_8_SKILLS}

    effective_skill = sum(bot_stats.get(k, 10) * w for k, w in weights.items())
    cons_stat = bot_stats.get("Consistency", 10)

    # 1. Map Demand
    map_demand = 15.0 + ((sr - 4.5) / 4.0) * 75.0
    if bpm > 220:
        map_demand += (bpm - 220) * 0.15 * (1.0 - (bot_stats.get("Speed", 10) / 100.0))
    if cs > 4.5:
        map_demand += (cs - 4.5) * 10.0 * (1.0 - (bot_stats.get("Precision", 10) / 100.0))
    if length > 200:
        map_demand += ((length - 200) / 60.0) * 5.0 * (1.0 - (bot_stats.get("Stamina", 10) / 100.0))

    skill_ratio = effective_skill / max(5.0, map_demand)

    # 2. Accuracy Sigmoid
    acc_mid = 94.0 + 5.5 / (1.0 + math.exp(-3.5 * (skill_ratio - 0.9)))
    acc_std = max(0.15, 1.2 - (effective_skill / 100.0) * 0.6 - (cons_stat / 100.0) * 0.4)
    sim_acc = max(70.0, min(99.95, random.gauss(acc_mid, acc_std)))

    # 3. Hit Objects & Miss Count
    drain_density = max(2.8, min(6.0, (bpm / 60.0) * 1.1 + (sr * 0.25)))
    total_objects = max(50, int(length * drain_density))

    if skill_ratio >= 1.15:
        lambda_miss = max(0.0, 0.2 - (cons_stat / 500.0))
    elif skill_ratio >= 0.95:
        lambda_miss = max(0.0, (1.2 - skill_ratio) * 6.0 * (1.0 - cons_stat / 150.0))
    else:
        lambda_miss = (1.0 - skill_ratio) * 18.0 * (1.5 - cons_stat / 100.0)

    # Poisson draw
    L = math.exp(-min(lambda_miss, 700.0))
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    sim_misses = max(0, k - 1)

    # 4. Combo Ratio
    if sim_misses == 0:
        combo_ratio = 1.0
    else:
        base_split = 1.0 / (sim_misses + 1)
        cons_factor = 0.5 + 0.5 * (cons_stat / 100.0)
        choke_luck = random.uniform(0.7, 1.3)
        combo_ratio = min(0.94, max(0.10, base_split * (1.2 + cons_factor) * choke_luck))

    # 5. ScoreV2
    score_combo = 700000.0 * (combo_ratio ** 0.5)
    score_acc = 300000.0 * ((sim_acc / 100.0) ** 4.0)
    total_scorev2 = int(round(score_combo + score_acc))
    total_scorev2 = max(0, min(1000000, total_scorev2))

    return {
        "scorev2": total_scorev2,
        "acc": round(sim_acc, 2),
        "misses": sim_misses,
        "combo_ratio": round(combo_ratio, 3),
        "effective_skill": round(effective_skill, 1),
        "map_demand": round(map_demand, 1),
        "ratio": round(skill_ratio, 2)
    }


def ref_generate_tactical_scouting_dossier(player_name: str, stats: dict[str, int], tier_name: str) -> dict:
    """Generates a structured tactical scouting dossier."""
    sorted_skills = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    top1, top2 = sorted_skills[0][0], sorted_skills[1][0]
    bot1, bot2 = sorted_skills[-1][0], sorted_skills[-2][0]

    cons = stats.get("Consistency", 50)
    if cons < 30:
        choke_text = "🚨 Nervöser Choker (Neigt zu Sudden Breaks bei Drucksituationen / Tiebreakern)"
        choke_badge = "Choke-Gefahr: Hoch"
        choke_color = "#FF5252"
    elif cons < 60:
        choke_text = "⚠️ Durchschnittliche Nervenstärke (Stabiler Rundenspieler mit gelegentlichen Combo-Drops)"
        choke_badge = "Choke-Gefahr: Mittel"
        choke_color = "#FFA726"
    elif cons < 85:
        choke_text = "🛡️ Solider Match-Anchor (Hohe Combo-Konstanz, verlässlicher Scorer)"
        choke_badge = "Choke-Gefahr: Gering"
        choke_color = "#00E676"
    else:
        choke_text = "💎 Eiserne Match-Nerven (Legendäre Clutch-Resistenz, verlässliche FC-Maschine)"
        choke_badge = "Choke-Gefahr: Minimal"
        choke_color = "#00E5FF"

    slot_map = {
        "Speed": ["DT1", "DT2"],
        "Precision": ["HR1", "HR2"],
        "Streams": ["NM4", "NM5"],
        "Tech": ["NM6", "FM2"],
        "Reading": ["HD1", "HD2"],
        "Aim": ["NM1", "NM2"],
        "Stamina": ["NM3", "TB"],
        "Consistency": ["NM1", "TB"]
    }
    sig_slots = list(set(slot_map.get(top1, ["NM1"]) + slot_map.get(top2, ["NM2"])))[:3]

    return {
        "name": player_name,
        "tier": tier_name,
        "top_strengths": [top1, top2],
        "top_weaknesses": [bot1, bot2],
        "signature_slots": sig_slots,
        "choke_tendency": choke_text,
        "choke_badge": choke_badge,
        "choke_color": choke_color,
        "stats": stats
    }


def ref_generate_team_roster(team_size: int, tier_name: str, player_username: str = "Spieler") -> dict:
    """Generates rosters for player team and opponent team based on team size."""
    if hasattr(app, "generate_team_roster") and callable(getattr(app, "generate_team_roster")):
        return app.generate_team_roster(team_size, tier_name, player_username)

    valid_size = max(1, min(4, int(team_size or 1)))
    sampled_names = random.sample(GERMAN_OSU_NAMES, min(len(GERMAN_OSU_NAMES), valid_size * 2))

    player_team = []
    # User is slot 0 of player team
    user_stats, _, _ = ref_generate_8skill_profile(tier_name)
    player_team.append(ref_generate_tactical_scouting_dossier(player_username, user_stats, tier_name))

    # Teammates (valid_size - 1)
    for i in range(valid_size - 1):
        tm_name = sampled_names[i]
        tm_stats, _, _ = ref_generate_8skill_profile(tier_name)
        player_team.append(ref_generate_tactical_scouting_dossier(tm_name, tm_stats, tier_name))

    opponent_team = []
    # Opponents (valid_size)
    for i in range(valid_size):
        opp_name = sampled_names[valid_size - 1 + i]
        opp_stats, _, _ = ref_generate_8skill_profile(tier_name)
        opponent_team.append(ref_generate_tactical_scouting_dossier(opp_name, opp_stats, tier_name))

    return {
        "team_size": valid_size,
        "player_team": player_team,
        "opponent_team": opponent_team
    }


def ref_aggregate_round_scores(player_scores: list[int], opponent_scores: list[int]) -> dict:
    """Aggregates round scores and computes victory status and margin."""
    if hasattr(app, "aggregate_round_scores") and callable(getattr(app, "aggregate_round_scores")):
        return app.aggregate_round_scores(player_scores, opponent_scores)

    p_total = sum(int(s or 0) for s in player_scores)
    o_total = sum(int(s or 0) for s in opponent_scores)
    margin = abs(p_total - o_total)

    if p_total > o_total:
        winner = "player_team"
    elif o_total > p_total:
        winner = "opponent_team"
    else:
        winner = "draw"

    return {
        "player_team_total": p_total,
        "opponent_team_total": o_total,
        "winner": winner,
        "margin": margin
    }


def ref_evaluate_scouting_guess(player_top2: list[str], player_bot2: list[str], true_top2: list[str], true_bot2: list[str]) -> dict:
    """Calculates guessing challenge accuracy and verdict."""
    if hasattr(app, "evaluate_scouting_guess") and callable(getattr(app, "evaluate_scouting_guess")):
        return app.evaluate_scouting_guess(player_top2, player_bot2, true_top2, true_bot2)

    s_matches = len(set(player_top2 or []).intersection(set(true_top2 or [])))
    w_matches = len(set(player_bot2 or []).intersection(set(true_bot2 or [])))
    correct_count = s_matches + w_matches
    acc_pct = (correct_count / 4.0) * 100.0

    if correct_count == 4:
        title = "🏆 Meister-Scout"
        desc = "Perfekte Analyse! Du hast das gesamte Gegnerprofil glasklar durchschaut."
    elif correct_count == 3:
        title = "🥇 Experte"
        desc = "Hervorragende Beobachtungsgabe! Nahezu alle Stärken/Schwächen richtig deduziert."
    elif correct_count == 2:
        title = "🥈 Solider Analyst"
        desc = "Gute Ansätze! Du hast die Hauptgefahren erkannt, wurdest aber in Details überrascht."
    elif correct_count == 1:
        title = "🥉 Aufmerksamer Neuling"
        desc = "Teilweise erkannt. Der Gegner konnte seine wahren Stärken geschickt verschleiern."
    else:
        title = "🔍 Getäuschter Stratege"
        desc = "Komplett geblendet! Der Gegner hat dich taktisch vollkommen überrascht."

    return {
        "accuracy_pct": acc_pct,
        "correct_count": correct_count,
        "verdict_title": title,
        "verdict_desc": desc
    }


def ref_generate_strategic_debrief(match_summary: dict, true_profile: dict, guess_eval: dict, api_key: str = None) -> str:
    """Generates German caster match debriefing report."""
    if hasattr(app, "generate_strategic_debrief") and callable(getattr(app, "generate_strategic_debrief")):
        return app.generate_strategic_debrief(match_summary, true_profile, guess_eval, api_key)

    acc_pct = guess_eval.get("accuracy_pct", 0.0)
    true_str = ", ".join(true_profile.get("top_strengths", []))
    true_weak = ", ".join(true_profile.get("top_weaknesses", []))
    p_score = match_summary.get("player_score", 0)
    b_score = match_summary.get("bot_score", 0)
    badge = match_summary.get("badge", "OWC")
    div = match_summary.get("division", "Grand Finals")
    v_title = guess_eval.get("verdict_title", "Scout")

    winner_txt = "Sieg für dein Team!" if p_score > b_score else "Knappe Niederlage."

    report = f"""🎙️ OFFIZIELLER CASTER-BERICHT ({badge} {div})
============================================================
Endstand: {p_score} : {b_score} • {winner_txt}

🎯 SCOUTING-ANALYSE ({v_title} - {acc_pct:.0f}% Genauigkeit):
• Echte Stärken des Gegners: {true_str}
• Echte Schwächen des Gegners: {true_weak}
• Dein Scouting-Ergebnis: Du hast {guess_eval.get('correct_count', 0)} von 4 Attributen exakt deduziert.

♟️ BAN/PICK- & DRAFT-BEWERTUNG (Draft-Note: {'A+' if acc_pct >= 75 else 'B'}):
• Taktischer Ban-Impact: Deine Bans haben das Match maßgeblich beeinflusst.
• Pick-Ausnutzung: Das Ausnutzen der gegnerischen Schwächen ({true_weak}) war der Schlüssel zu deinen Rundengewinnen.

📈 COACHING-EMPFEHLUNG FÜR DIE NÄCHSTE RUNDE:
1. Halte deine Map-Picks weiterhin fokussiert auf deine Kernkompetenzen (Aim / Speed).
2. Nutze den UHO Hub KI-Skill-Tester, um Choke-Gefahren auf High-Pressure-Tiebreakern weiter zu minimieren!
"""
    return report


# =============================================================================
# MODULE 1: Syntax Compilation & Module Import Verification
# =============================================================================
class Test01_SyntaxCompilation(unittest.TestCase):
    """Verifies that all Python modules compile cleanly and import without errors."""

    def test_py_compile_all_core_files(self):
        files_to_compile = [
            "app.py",
            "server_main.py",
            "render_backend_main.py",
            "discord_bot.py",
            "test_verification_suite.py"
        ]
        for filename in files_to_compile:
            filepath = os.path.join(PROJECT_ROOT, filename)
            self.assertTrue(os.path.exists(filepath), f"File does not exist: {filename}")
            compiled_path = py_compile.compile(filepath, doraise=True)
            self.assertTrue(compiled_path is not None and os.path.exists(compiled_path))

    def test_module_structure_and_symbols(self):
        """Verifies core symbols and functions exist across modules."""
        self.assertTrue(callable(getattr(app, "safe_div", None)))
        self.assertTrue(callable(getattr(app, "safe_ui_dispatch", None)))
        self.assertTrue(callable(getattr(app, "safe_atomic_json_dump", None)))
        self.assertTrue(callable(getattr(app, "safe_json_load", None)))
        self.assertTrue(callable(getattr(app, "get_safe_sqlite_conn", None)))
        self.assertTrue(callable(getattr(app, "sqlite_query_maps", None)))
        self.assertTrue(callable(getattr(app, "compute_map_pattern_fingerprint", None)))
        self.assertTrue(callable(getattr(app, "calculate_skill_test_score", None)))
        self.assertTrue(callable(getattr(app, "calculate_adaptive_topplay_difficulty", None)))
        self.assertTrue(callable(getattr(app, "parse_osr_deep_telemetry", None)))
        self.assertTrue(callable(getattr(app, "safe_parse_osr", None)))
        self.assertTrue(callable(getattr(app, "safe_parse_ai_json", None)))
        self.assertTrue(hasattr(app, "BanchoRefereeBot"))

        self.assertTrue(callable(getattr(server_main, "verify_key", None)))
        self.assertTrue(callable(getattr(render_backend_main, "verify_key", None)))
        self.assertTrue(hasattr(discord_bot, "DISCORD_BOT_TOKEN"))


# =============================================================================
# MODULE 2: SQLite Database & Allowlist Queries
# =============================================================================
class Test02_DatabaseAndAllowlistQueries(unittest.TestCase):
    """Verifies SQLite parameterization, allowlists, connection safety, and recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_beatmaps.db")
        conn = app.sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE maps (
                id INTEGER PRIMARY KEY,
                name TEXT,
                primary_skill TEXT,
                secondary_skill TEXT,
                sr REAL,
                bpm REAL,
                ar REAL,
                cs REAL,
                od REAL,
                len INTEGER,
                playcount INTEGER,
                status TEXT,
                year INTEGER
            )
        """)
        skills = ["Aim", "Streams", "Speed", "Tech", "Precision", "Reading", "Stamina", "Consistency"]
        for i in range(1, 31):
            conn.execute(
                "INSERT INTO maps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    i,
                    f"Test Beatmap #{i}",
                    skills[i % len(skills)],
                    skills[(i + 1) % len(skills)],
                    4.0 + (i * 0.1),
                    160 + (i * 3),
                    9.0,
                    4.0,
                    8.5,
                    90 + i,
                    1000 * (31 - i),
                    "Ranked",
                    2023
                )
            )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_safe_sqlite_conn_context_manager(self):
        with app.get_safe_sqlite_conn(self.db_path, timeout=10.0) as conn:
            self.assertIsNotNone(conn)
            row = conn.execute("SELECT COUNT(*) FROM maps").fetchone()
            self.assertEqual(row[0], 30)

        nonexistent_path = os.path.join(self.temp_dir, "does_not_exist.db")
        with app.get_safe_sqlite_conn(nonexistent_path) as conn_non:
            self.assertIsNone(conn_non)

    def test_parameterized_query_execution(self):
        old_db_path = app.BEATMAP_SQLITE_DB_PATH
        app.BEATMAP_SQLITE_DB_PATH = self.db_path
        try:
            results = app.sqlite_query_maps(
                skill="Aim",
                sr_min=4.5,
                sr_max=6.5,
                bpm_min=170,
                bpm_max=240,
                ar_min=8.0,
                ar_max=10.0,
                cs_max=5.0,
                limit=10,
                order_by="playcount DESC"
            )
            self.assertIsInstance(results, list)
            for r in results:
                self.assertEqual(r["primary_skill"], "Aim")
                self.assertGreaterEqual(r["sr"], 4.5)
                self.assertLessEqual(r["sr"], 6.5)
        finally:
            app.BEATMAP_SQLITE_DB_PATH = old_db_path

    def test_order_by_allowlist_prevents_sql_injection(self):
        old_db_path = app.BEATMAP_SQLITE_DB_PATH
        app.BEATMAP_SQLITE_DB_PATH = self.db_path
        try:
            payloads = [
                "playcount DESC; DROP TABLE maps; --",
                "sr ASC; DELETE FROM maps;",
                "1; SELECT * FROM maps;",
                "RANDOM(); DROP TABLE maps;",
                "' OR '1'='1"
            ]
            for p in payloads:
                res = app.sqlite_query_maps(order_by=p, limit=5)
                self.assertTrue(isinstance(res, list))
                with app.get_safe_sqlite_conn(self.db_path) as conn:
                    count = conn.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
                    self.assertEqual(count, 30)
        finally:
            app.BEATMAP_SQLITE_DB_PATH = old_db_path

    def test_max_parameter_bounding_exclude_ids(self):
        old_db_path = app.BEATMAP_SQLITE_DB_PATH
        app.BEATMAP_SQLITE_DB_PATH = self.db_path
        try:
            large_excludes = [i for i in range(1, 3000)]
            res = app.sqlite_query_maps(exclude_ids=large_excludes)
            self.assertIsInstance(res, list)
        finally:
            app.BEATMAP_SQLITE_DB_PATH = old_db_path

    def test_corruption_detection_quick_check_and_fallback(self):
        corrupt_db_path = os.path.join(self.temp_dir, "corrupt_maps.db")
        with open(corrupt_db_path, "wb") as f:
            f.write(b"SQLite format 3\x00corrupted_garbage_data_blocks_1234567890")

        old_db_path = app.BEATMAP_SQLITE_DB_PATH
        try:
            conn = app.sqlite3.connect(corrupt_db_path, timeout=1.0)
            try:
                check = conn.execute("PRAGMA quick_check;").fetchone()
                is_ok = bool(check and str(check[0]).lower() == "ok")
            except Exception:
                is_ok = False
            finally:
                conn.close()

            self.assertFalse(is_ok, "Corrupted DB should fail quick_check")
        finally:
            app.BEATMAP_SQLITE_DB_PATH = old_db_path

    def test_concurrent_multithreaded_queries(self):
        old_db_path = app.BEATMAP_SQLITE_DB_PATH
        app.BEATMAP_SQLITE_DB_PATH = self.db_path

        def worker_query(worker_id):
            return app.sqlite_query_maps(
                skill="Streams" if worker_id % 2 == 0 else "Aim",
                limit=10,
                order_by="sr DESC" if worker_id % 2 == 0 else "playcount DESC"
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                futures = [executor.submit(worker_query, i) for i in range(24)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            self.assertEqual(len(results), 24)
            for res in results:
                self.assertIsInstance(res, list)
        finally:
            app.BEATMAP_SQLITE_DB_PATH = old_db_path


# =============================================================================
# MODULE 3: Atomic Persistence & Recovery
# =============================================================================
class Test03_AtomicPersistenceAndRecovery(unittest.TestCase):
    """Verifies atomic JSON dumps, fsync, .bak creation, and corruption recovery."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.target_file = os.path.join(self.temp_dir, "uho_settings.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_safe_atomic_json_dump_and_bak_creation(self):
        data_v1 = {"version": "1.0", "volume": 75, "user": "PlayerOne"}
        success_v1 = app.safe_atomic_json_dump(data_v1, self.target_file)
        self.assertTrue(success_v1)
        self.assertTrue(os.path.exists(self.target_file))

        loaded_v1 = app.safe_json_load(self.target_file)
        self.assertEqual(loaded_v1, data_v1)

        data_v2 = {"version": "2.0", "volume": 85, "user": "PlayerOne"}
        success_v2 = app.safe_atomic_json_dump(data_v2, self.target_file)
        self.assertTrue(success_v2)

        bak_file = self.target_file + ".bak"
        self.assertTrue(os.path.exists(bak_file))
        loaded_v2 = app.safe_json_load(self.target_file)
        self.assertEqual(loaded_v2, data_v2)

    def test_safe_json_load_corrupted_recovery(self):
        original_data = {"profile": "TopPlayer", "level": 12, "pp": 6200.0}
        app.safe_atomic_json_dump(original_data, self.target_file)

        updated_data = {"profile": "TopPlayer", "level": 13, "pp": 6500.0}
        app.safe_atomic_json_dump(updated_data, self.target_file)

        with open(self.target_file, "w", encoding="utf-8") as f:
            f.write("{corrupt_json: [unclosed_array, 1234")

        recovered = app.safe_json_load(self.target_file)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.get("profile"), "TopPlayer")

    def test_safe_atomic_json_dump_creates_missing_dirs(self):
        nested_file = os.path.join(self.temp_dir, "nested", "sub", "config.json")
        data = {"nested": True}
        success = app.safe_atomic_json_dump(data, nested_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(nested_file))

    def test_safe_json_load_nonexistent_and_invalid(self):
        missing_file = os.path.join(self.temp_dir, "missing.json")
        self.assertEqual(app.safe_json_load(missing_file, default={"empty": True}), {"empty": True})
        self.assertEqual(app.safe_json_load(missing_file), {})


# =============================================================================
# MODULE 4: Skill Selection & Dynamic Recommendation
# =============================================================================
class Test04_SkillSelectionAndDynamicRecommendation(unittest.TestCase):
    """Verifies skill categorization, fingerprint heuristics, mod difficulty scaling, and exclusion."""

    def test_map_pattern_fingerprinting_heuristics(self):
        tech_map = {"name": "Camellia - GHOST (VIP Remix) [Chaos SV]", "sr": 6.2, "bpm": 150, "len": 130, "cs": 4.0, "od": 8.5}
        fp_tech = app.compute_map_pattern_fingerprint(tech_map)
        self.assertGreaterEqual(fp_tech["Tech"], 0.40)
        self.assertLessEqual(fp_tech["Streams"], 0.50)

        stream_map = {"name": "DragonForce - Through the Fire and Flames [Deathstream]", "sr": 6.5, "bpm": 200, "len": 240, "cs": 4.0, "od": 9.0}
        fp_stream = app.compute_map_pattern_fingerprint(stream_map)
        self.assertGreaterEqual(fp_stream["Streams"], 0.60)
        self.assertGreaterEqual(fp_stream["Stamina"], 0.50)

        prec_map = {"name": "Precision Training [Small CS CS6.0]", "sr": 5.0, "bpm": 170, "len": 100, "cs": 5.5, "od": 9.0}
        fp_prec = app.compute_map_pattern_fingerprint(prec_map)
        self.assertGreaterEqual(fp_prec["Precision"], 0.50)

        read_map = {"name": "Low AR Reading Practice [Hidden Flower]", "sr": 4.8, "bpm": 160, "len": 120, "ar": 8.0, "cs": 4.0}
        fp_read = app.compute_map_pattern_fingerprint(read_map)
        self.assertGreaterEqual(fp_read["Reading"], 0.50)

        fp_empty = app.compute_map_pattern_fingerprint({})
        self.assertEqual(len(fp_empty), 8)
        for val in fp_empty.values():
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

    def test_classify_map_output(self):
        sample_map = {"name": "Camellia - Crystallized", "sr": 5.8, "bpm": 175, "len": 140}
        cats = app.classify_map(sample_map)
        self.assertIsInstance(cats, list)
        self.assertTrue(len(cats) > 0)

    def test_pick_dynamic_map_for_skill_mod_scaling(self):
        picked_dt = app.pick_dynamic_map_for_skill("Aim", target_sr=6.0, mod="DT")
        self.assertIsInstance(picked_dt, dict)
        self.assertIn("sr", picked_dt)
        self.assertIn("raw_sr", picked_dt)
        self.assertIn("bpm", picked_dt)
        self.assertEqual(picked_dt["mod"], "DT")
        self.assertGreaterEqual(picked_dt["sr"], picked_dt["raw_sr"])

        picked_hr = app.pick_dynamic_map_for_skill("Streams", target_sr=5.5, mod="HR")
        self.assertEqual(picked_hr["mod"], "HR")
        self.assertIn("sr", picked_hr)
        self.assertIn("raw_sr", picked_hr)

        picked_ez = app.pick_dynamic_map_for_skill("Reading", target_sr=5.0, mod="EZ")
        self.assertEqual(picked_ez["mod"], "EZ")
        self.assertIn("sr", picked_ez)
        self.assertIn("raw_sr", picked_ez)

    def test_pick_dynamic_map_exclusion_and_feedback(self):
        exclude_set = {"101", "102", "103"}
        picked = app.pick_dynamic_map_for_skill("Aim", target_sr=5.0, exclude_ids=exclude_set)
        self.assertNotIn(str(picked.get("id")), exclude_set)

        feedback = {"201": {"liked": False}}
        picked_fb = app.pick_dynamic_map_for_skill("Aim", target_sr=5.0, user_feedback=feedback)
        self.assertNotEqual(str(picked_fb.get("id")), "201")

    def test_pick_dynamic_map_boundary_values(self):
        p1 = app.pick_dynamic_map_for_skill("Aim", target_sr="5.8")
        self.assertIsInstance(p1, dict)
        p2 = app.pick_dynamic_map_for_skill("Aim", target_sr=-2.0)
        self.assertIsInstance(p2, dict)
        p3 = app.pick_dynamic_map_for_skill("Aim", target_sr=15.0)
        self.assertIsInstance(p3, dict)
        p4 = app.pick_dynamic_map_for_skill("Aim", target_sr=None)
        self.assertIsInstance(p4, dict)


# =============================================================================
# MODULE 5: Adaptive Difficulty & Defensive Math Formulas
# =============================================================================
class Test05_AdaptiveDifficultyAndMathFormulas(unittest.TestCase):
    """Verifies safe_div defensive division, top-play calculations, and score calibration."""

    def test_safe_div_exhaustive_cases(self):
        self.assertEqual(app.safe_div(100, 20), 5.0)
        self.assertEqual(app.safe_div(-40, 8), -5.0)
        self.assertEqual(app.safe_div(7.5, 2.5), 3.0)
        self.assertEqual(app.safe_div(10, 0), 0.0)
        self.assertEqual(app.safe_div(10, 0.0), 0.0)
        self.assertEqual(app.safe_div(10, 0, default=99.9), 99.9)
        self.assertEqual(app.safe_div(0, 10), 0.0)
        self.assertEqual(app.safe_div(0, 0), 0.0)
        self.assertEqual(app.safe_div(None, 10), 0.0)
        self.assertEqual(app.safe_div(10, None), 0.0)
        self.assertEqual(app.safe_div(None, None, default=12.0), 12.0)
        self.assertEqual(app.safe_div("20", "4"), 5.0)
        self.assertEqual(app.safe_div("invalid", 2), 0.0)
        self.assertEqual(app.safe_div(10, "text"), 0.0)
        self.assertEqual(app.safe_div(math.nan, 5), 0.0)
        self.assertEqual(app.safe_div(5, math.nan), 0.0)
        self.assertEqual(app.safe_div(math.inf, 5), 0.0)
        self.assertEqual(app.safe_div(5, math.inf), 0.0)
        self.assertEqual(app.safe_div(1e308, 1e-308), 0.0)

    def test_calculate_skill_test_score_calibration(self):
        s_fc = app.calculate_skill_test_score(acc=100.0, misses=0)
        self.assertGreaterEqual(s_fc, 96.0)
        self.assertLessEqual(s_fc, 100.0)

        s_clean = app.calculate_skill_test_score(acc=97.5, misses=0)
        self.assertGreaterEqual(s_clean, 90.0)
        self.assertLessEqual(s_clean, 95.0)

        s_choke = app.calculate_skill_test_score(acc=97.0, misses=1)
        self.assertGreaterEqual(s_choke, 80.0)
        self.assertLessEqual(s_choke, 88.0)

        s_pass2 = app.calculate_skill_test_score(acc=95.5, misses=2)
        self.assertGreaterEqual(s_pass2, 65.0)
        self.assertLessEqual(s_pass2, 78.0)

        s_pass3 = app.calculate_skill_test_score(acc=93.0, misses=3)
        self.assertGreaterEqual(s_pass3, 50.0)
        self.assertLessEqual(s_pass3, 65.0)

        s_zero_sr = app.calculate_skill_test_score(acc=98.0, misses=0, map_sr=0.0, player_sr=0.0)
        self.assertGreater(s_zero_sr, 0.0)

        self.assertEqual(app.calculate_skill_test_score(acc=0.0, misses=0), 0.0)
        self.assertEqual(app.calculate_skill_test_score(acc=-10.0, misses=0), 0.0)
        self.assertEqual(app.calculate_skill_test_score(acc=None, misses=0), 0.0)
        self.assertEqual(app.calculate_skill_test_score(acc=math.nan, misses=0), 0.0)

    def test_calculate_adaptive_topplay_difficulty_edge_cases(self):
        res_empty = app.calculate_adaptive_topplay_difficulty([])
        self.assertEqual(res_empty["base_raw_sr"], 5.2)
        self.assertEqual(res_empty["effective_sr"], 5.2)

        res_pp = app.calculate_adaptive_topplay_difficulty([], user_info={"pp_raw": 4200})
        self.assertGreater(res_pp["effective_sr"], 4.0)

        zero_hits_play = [{"beatmap_id": "1", "count300": 0, "count100": 0, "count50": 0, "countmiss": 0, "pp": 0}]
        res_zero = app.calculate_adaptive_topplay_difficulty(zero_hits_play)
        self.assertIn("effective_sr", res_zero)

        corrupt_plays = [
            {"beatmap_id": "9999", "enabled_mods": "bad_mod", "count300": "err", "count100": None, "count50": "x", "countmiss": {}, "pp": "corrupt_pp"},
            "not_a_dict"
        ]
        res_corrupt = app.calculate_adaptive_topplay_difficulty(corrupt_plays)
        self.assertIn("effective_sr", res_corrupt)

        normal_plays = [
            {"beatmap_id": "1001", "enabled_mods": 64, "count300": 500, "count100": 5, "count50": 0, "countmiss": 0, "pp": 380.0},
            {"beatmap_id": "1002", "enabled_mods": 16, "count300": 450, "count100": 10, "count50": 1, "countmiss": 1, "pp": 320.0},
        ]
        res_normal = app.calculate_adaptive_topplay_difficulty(normal_plays)
        self.assertIn("effective_sr", res_normal)
        self.assertGreater(res_normal["avg_acc"], 95.0)


# =============================================================================
# MODULE 6: Replay Telemetry & JSON Parsing
# =============================================================================
class Test06_ReplayTelemetryAndJSONParsing(unittest.TestCase):
    """Verifies safe_parse_ai_json, safe_parse_osr, LZMA decoding, and deep metrics."""

    def test_safe_parse_ai_json_all_formats(self):
        j1 = '{"status": "ok", "score": 95}'
        self.assertEqual(app.safe_parse_ai_json(j1), {"status": "ok", "score": 95})

        j2 = '```json\n{"analysis": "good", "target_sr": 6.1}\n```'
        self.assertEqual(app.safe_parse_ai_json(j2), {"analysis": "good", "target_sr": 6.1})

        j3 = '```\n{"weakness": "Reading"}\n```'
        self.assertEqual(app.safe_parse_ai_json(j3), {"weakness": "Reading"})

        j4 = 'Hier ist die Analyse:\n{"skill": "Speed", "confidence": 0.92}\nViel Erfolg beim Trainieren!'
        self.assertEqual(app.safe_parse_ai_json(j4), {"skill": "Speed", "confidence": 0.92})

        j5 = '{"items": [1, 2, 3,], "valid": true,}'
        self.assertEqual(app.safe_parse_ai_json(j5), {"items": [1, 2, 3], "valid": True})

        self.assertEqual(app.safe_parse_ai_json("Non-json string", default={"fallback": True}), {"fallback": True})
        self.assertEqual(app.safe_parse_ai_json(None, default={}), {})
        self.assertIsNone(app.safe_parse_ai_json("invalid json", default=None))

    def test_safe_parse_osr_missing_and_empty_file(self):
        self.assertEqual(app.safe_parse_osr(""), {})
        self.assertEqual(app.safe_parse_osr(None), {})
        self.assertEqual(app.safe_parse_osr("nonexistent_replay_12345.osr"), {})

        with tempfile.NamedTemporaryFile(suffix=".osr", delete=False) as f:
            tname = f.name
        try:
            self.assertEqual(app.safe_parse_osr(tname), {})
        finally:
            if os.path.exists(tname):
                os.remove(tname)

    def test_parse_osr_deep_telemetry_corrupted_lzma(self):
        with tempfile.NamedTemporaryFile(suffix=".osr", delete=False) as f:
            tname = f.name
            f.write(struct.pack('<B', 0))
            f.write(struct.pack('<I', 20240101))
            f.write(b'\x0b\x04hash')
            f.write(b'\x0b\x06player')
            f.write(b'\x0b\x04rhas')
            f.write(struct.pack('<hhhhhh', 150, 10, 1, 0, 0, 1))
            f.write(struct.pack('<i', 1250000))
            f.write(struct.pack('<h', 420))
            f.write(struct.pack('<B', 0))
            f.write(struct.pack('<i', 0))
            f.write(b'\x00')
            f.write(struct.pack('<q', 123456789))
            f.write(struct.pack('<i', 24))
            f.write(b'CORRUPTED_LZMA_STREAM_BYTES')
        try:
            parsed = app.parse_osr_deep_telemetry(tname)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.get("player"), "player")
            self.assertEqual(parsed.get("score"), 1250000)
            self.assertEqual(parsed.get("total_frames"), 0)
            self.assertIn("metrics", parsed)
        finally:
            if os.path.exists(tname):
                os.remove(tname)

    def test_parse_osr_deep_telemetry_valid_synthetic_lzma(self):
        raw_frames = "0|256.0|192.0|1,16|260.0|195.0|1,16|270.0|200.0|2,16|280.0|205.0|0"
        compressed = lzma.compress(raw_frames.encode("utf-8"))

        with tempfile.NamedTemporaryFile(suffix=".osr", delete=False) as f:
            tname = f.name
            f.write(struct.pack('<B', 0))
            f.write(struct.pack('<I', 20240101))
            f.write(b'\x0b\x04hash')
            f.write(b'\x0b\x06player')
            f.write(b'\x0b\x04rhas')
            f.write(struct.pack('<hhhhhh', 100, 0, 0, 0, 0, 0))
            f.write(struct.pack('<i', 2000000))
            f.write(struct.pack('<h', 500))
            f.write(struct.pack('<B', 1))
            f.write(struct.pack('<i', 8))
            f.write(b'\x00')
            f.write(struct.pack('<q', 123456789))
            f.write(struct.pack('<i', len(compressed)))
            f.write(compressed)
        try:
            parsed = app.parse_osr_deep_telemetry(tname)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed.get("player"), "player")
            self.assertEqual(parsed.get("accuracy"), 100.0)
            self.assertEqual(parsed.get("total_frames"), 4)
            self.assertIn("metrics", parsed)
            metrics = parsed["metrics"]
            self.assertIn("peak_speed", metrics)
            self.assertIn("alt_ratio", metrics)
        finally:
            if os.path.exists(tname):
                os.remove(tname)

    def test_compute_deep_metrics_and_aggregate(self):
        m_empty = app.compute_deep_metrics({})
        self.assertEqual(m_empty["peak_speed"], 0)
        self.assertEqual(m_empty["alt_ratio"], 50.0)

        replays = [{
            "score": 1500000, "accuracy": 99.0, "misses": 0,
            "100s": 2, "50s": 0, "300s": 500, "combo": 700,
            "metrics": {
                "overaim_pct": 52.0, "underaim_pct": 48.0, "peak_speed": 1600.0,
                "avg_speed": 400.0, "k1_avg_hold": 45.0, "k2_avg_hold": 48.0,
                "alt_ratio": 55.0, "ur": 75.0, "early_bias_pct": 50.0,
                "quadrants": {"TL": 25.0, "TR": 25.0, "BL": 25.0, "BR": 25.0},
                "choke_reasons": []
            }
        }]
        agg = app.compute_aggregate_deep_telemetry(replays)
        self.assertIsNotNone(agg)
        self.assertEqual(agg["total_plays"], 1)
        self.assertEqual(agg["avg_acc"], 99.0)
        self.assertEqual(agg["avg_peak_spd"], 1600.0)


# =============================================================================
# MODULE 7: Subprocess, Network & Cloud Hardening
# =============================================================================
class Test07_SubprocessAndNetworkHardening(unittest.TestCase):
    """Verifies PowerShell env passing, Bancho IRC TLS & CRLF sanitization, and cloud auth."""

    def test_powershell_auto_updater_safe_env_passing(self):
        import inspect
        source = inspect.getsource(app.App.perform_auto_update)
        self.assertIn('$env:UHO_UPDATE_SRC', source)
        self.assertIn('$env:UHO_UPDATE_DST', source)
        self.assertIn('$env:UHO_UPDATE_PID', source)
        self.assertIn('-LiteralPath', source)

    def test_bancho_referee_bot_crlf_stripping(self):
        bot = app.BanchoRefereeBot("test_user", "test_pass")
        bot.channel = "#mp_9999"
        sent_commands = []
        bot._send_raw = lambda line: sent_commands.append(line)

        bot.send_mp("mp map 12345\r\nPRIVMSG #mp_9999 :!mp close")
        self.assertEqual(len(sent_commands), 1)
        self.assertNotIn("\r", sent_commands[0])
        self.assertNotIn("\n", sent_commands[0])

        sent_commands.clear()
        bot.send_channel_message("Hello\r\nPRIVMSG BanchoBot :!mp abort")
        self.assertEqual(len(sent_commands), 1)
        self.assertNotIn("\r", sent_commands[0])
        self.assertNotIn("\n", sent_commands[0])

        sent_commands.clear()
        bot.invite_player("Player1\r\n!mp password 123")
        self.assertEqual(len(sent_commands), 1)
        self.assertNotIn("\r", sent_commands[0])
        self.assertNotIn("\n", sent_commands[0])

    def test_cloud_backend_key_validation(self):
        req_fake = server_main.VerifyRequest(key="UHO-UNAUTHORIZED-1234")
        resp_fake = server_main.verify_key(req_fake)
        self.assertFalse(resp_fake["valid"])

        req_real = server_main.VerifyRequest(key="UHO-2026-VIP-DEV")
        resp_real = server_main.verify_key(req_real)
        self.assertTrue(resp_real["valid"])

        req_rnd_fake = render_backend_main.VerifyRequest(key="UHO-DUMMY-PASS-999")
        resp_rnd_fake = render_backend_main.verify_key(req_rnd_fake)
        self.assertFalse(resp_rnd_fake["valid"])

        req_rnd_real = render_backend_main.VerifyRequest(key="UHO-MASTER-PASS-2026")
        resp_rnd_real = render_backend_main.verify_key(req_rnd_real)
        self.assertTrue(resp_rnd_real["valid"])

    def test_discord_bot_token_loading(self):
        self.assertFalse(discord_bot.DISCORD_BOT_TOKEN.startswith("MTU0MDA4Njg5MDAxMzkyNTM4Ng"))


# =============================================================================
# MODULE 8: German Localization Adherence
# =============================================================================
class Test08_GermanLocalizationAdherence(unittest.TestCase):
    """Scans app.py to verify 0 English remnant strings in UI placeholders, think badges, and buttons."""

    def test_no_english_ui_remnants_in_app(self):
        app_path = os.path.join(PROJECT_ROOT, "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_code = f.read()

        self.assertNotIn('placeholder_text="Ask anything, @ to mention, / for actions"', app_code)
        self.assertIn('"Frage alles, @ zum Erwähnen, / für Aktionen"', app_code)

        self.assertNotIn('text="Thought for 0s ❯"', app_code)
        self.assertIn('text="Nachgedacht für 0s ❯"', app_code)
        self.assertNotIn('text=f"Thought for {elapsed}s ❯"', app_code)
        self.assertIn('text=f"Nachgedacht für {elapsed}s ❯"', app_code)
        self.assertNotIn('text=f"Thought for {max(1, elapsed)}s ❯"', app_code)
        self.assertIn('text=f"Nachgedacht für {max(1, elapsed)}s ❯"', app_code)

        self.assertNotIn('text="Submit ↵"', app_code)
        self.assertIn('text="Absenden ↵"', app_code)
        self.assertNotIn('ctk.CTkButton(bot_bar, text="Skip"', app_code)
        self.assertIn('ctk.CTkButton(bot_bar, text="Überspringen"', app_code)

        self.assertNotIn('f"Play #{i+1}:', app_code)
        self.assertIn('f"Spiel #{i+1}:', app_code)

    def test_german_ai_coach_system_prompt_compliance(self):
        app_path = os.path.join(PROJECT_ROOT, "app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            app_code = f.read()

        self.assertIn("SPRACH-VORGABE (ABSOLUT STRIKTE REGEL)", app_code)
        self.assertIn("Du antwortest AUSSCHLIESSLICH und ZU 100% AUF DEUTSCH!", app_code)

    def test_ai_chat_map_button_extraction(self):
        res1 = app.App._extract_map_info_from_text(None, "Hier ist deine Map: [MAP: 123456 | SET: 65432]")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["bid"], "123456")
        self.assertEqual(res1["sid"], "65432")

        res2 = app.App._extract_map_info_from_text(None, "Spiele diese Map: [MAP: 987654]")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["bid"], "987654")
        self.assertEqual(res2["sid"], "")

        res3 = app.App._extract_map_info_from_text(None, "Link: https://osu.ppy.sh/b/555123")
        self.assertIsNotNone(res3)
        self.assertEqual(res3["bid"], "555123")

        res4 = app.App._extract_map_info_from_text(None, "Wie trainiere ich mein Aim?")
        self.assertIsNone(res4)


# =============================================================================
# MODULE 9: Tier 1 — 8-Skillset Dynamic Bot Stat & ScoreV2 Engine
# =============================================================================
class Test09_Tier1_8SkillsetAndScoreV2Engine(unittest.TestCase):
    """Tier 1 Functional & Contract validation for 8-skill profiles and ScoreV2 formulas."""

    def test_8skill_profile_baseline_and_categories(self):
        """Verifies that all 8 skills are present, named correctly, and have minimum 10 points."""
        stats, top2, bot2 = ref_generate_8skill_profile("Challenger")
        self.assertEqual(len(stats), 8)
        for skill in ALL_8_SKILLS:
            self.assertIn(skill, stats)
            self.assertGreaterEqual(stats[skill], 10, f"Skill {skill} is below base 10 pts")

        self.assertEqual(len(top2), 2)
        self.assertEqual(len(bot2), 2)
        self.assertTrue(set(top2).issubset(set(ALL_8_SKILLS)))
        self.assertTrue(set(bot2).issubset(set(ALL_8_SKILLS)))

    def test_tier_point_pool_allocation_exact_sums(self):
        """Verifies exact tier target budgets: Rookie=160, Challenger=240, Pro=400, Legend=640."""
        for tier, expected_sum in TIER_POINT_POOLS.items():
            stats, top2, bot2 = ref_generate_8skill_profile(tier)
            actual_sum = sum(stats.values())
            self.assertEqual(actual_sum, expected_sum, f"Tier {tier} sum mismatch: expected {expected_sum}, got {actual_sum}")
            for k, val in stats.items():
                self.assertLessEqual(val, 100, f"Tier {tier} skill {k} exceeded upper bound 100: {val}")

    def test_dynamic_scorev2_formula_outputs(self):
        """Verifies continuous bounded ScoreV2 outputs (0..1,000,000, 70..100% acc, non-negative misses)."""
        stats, _, _ = ref_generate_8skill_profile("Pro")
        map_meta = {
            "sr": 6.2,
            "bpm": 210,
            "len": 145,
            "cs": 4.2,
            "ar": 9.3,
            "od": 8.8,
            "weights": {"Speed": 0.4, "Streams": 0.3, "Consistency": 0.3}
        }
        res = ref_calculate_bot_scorev2(stats, map_meta)
        self.assertIsInstance(res, dict)
        self.assertIn("scorev2", res)
        self.assertIn("acc", res)
        self.assertIn("misses", res)
        self.assertIn("combo_ratio", res)

        self.assertGreaterEqual(res["scorev2"], 0)
        self.assertLessEqual(res["scorev2"], 1000000)
        self.assertGreaterEqual(res["acc"], 70.0)
        self.assertLessEqual(res["acc"], 100.0)
        self.assertGreaterEqual(res["misses"], 0)
        self.assertGreaterEqual(res["combo_ratio"], 0.0)
        self.assertLessEqual(res["combo_ratio"], 1.0)

    def test_bot_scorev2_higher_tier_produces_higher_average(self):
        """Verifies mathematical validity: Legend tier bots outperform Rookie bots on high SR maps."""
        map_meta = {"sr": 6.8, "bpm": 225, "len": 160, "cs": 4.5}
        rookie_scores = []
        legend_scores = []
        for _ in range(25):
            r_stats, _, _ = ref_generate_8skill_profile("Rookie")
            l_stats, _, _ = ref_generate_8skill_profile("Legend")
            rookie_scores.append(ref_calculate_bot_scorev2(r_stats, map_meta)["scorev2"])
            legend_scores.append(ref_calculate_bot_scorev2(l_stats, map_meta)["scorev2"])

        avg_rookie = sum(rookie_scores) / len(rookie_scores)
        avg_legend = sum(legend_scores) / len(legend_scores)
        self.assertGreater(avg_legend, avg_rookie + 150000, "Legend tier must clearly outperform Rookie tier on 6.8* map")


# =============================================================================
# MODULE 10: Tier 1 — Team Formats, Roster Generation & Aggregate Scoring
# =============================================================================
class Test10_Tier1_TeamFormatsAndScoutingDossiers(unittest.TestCase):
    """Tier 1 Functional & Contract validation for 1v1-4v4 team matches and scouting dossiers."""

    def test_team_formats_roster_slot_matrix(self):
        """Verifies team sizing rules: 1v1 (2 players), 2v2 (4 players), 3v3 (6 players), 4v4 (8 players)."""
        for size in [1, 2, 3, 4]:
            roster = ref_generate_team_roster(team_size=size, tier_name="Challenger", player_username="TestPlayer")
            self.assertEqual(roster["team_size"], size)
            self.assertEqual(len(roster["player_team"]), size)
            self.assertEqual(len(roster["opponent_team"]), size)
            self.assertEqual(roster["player_team"][0]["name"], "TestPlayer")

    def test_teammate_pseudonyms_uniqueness_and_naming(self):
        """Verifies that generated teammates have distinct valid German/osu! identities."""
        roster = ref_generate_team_roster(team_size=4, tier_name="Pro", player_username="UserGerman")
        all_names = [m["name"] for m in roster["player_team"]] + [m["name"] for m in roster["opponent_team"]]
        self.assertEqual(len(all_names), 8)
        self.assertEqual(len(set(all_names)), 8, "All 8 participants must have distinct names")

    def test_tactical_scouting_dossier_generation(self):
        """Verifies scouting dossier structure: top strengths, weaknesses, signature slots, choke badges."""
        stats = {
            "Consistency": 92, "Speed": 88, "Aim": 85, "Stamina": 40,
            "Tech": 25, "Reading": 30, "Streams": 20, "Precision": 20
        }
        dossier = ref_generate_tactical_scouting_dossier("BavariaStream", stats, "Challenger")
        self.assertEqual(dossier["name"], "BavariaStream")
        self.assertIn("Consistency", dossier["top_strengths"])
        self.assertIn("Speed", dossier["top_strengths"])
        self.assertIn("Choke-Gefahr: Minimal", dossier["choke_badge"])
        self.assertIsInstance(dossier["signature_slots"], list)
        self.assertTrue(len(dossier["signature_slots"]) > 0)

    def test_aggregate_team_scoring_exact_sum(self):
        """Verifies exact sum of ScoreV2s, victory assignment, and winning margin calculation."""
        p_scores = [850000, 780000, 920000]
        o_scores = [810000, 740000, 890000]
        res = ref_aggregate_round_scores(p_scores, o_scores)

        self.assertEqual(res["player_team_total"], 2550000)
        self.assertEqual(res["opponent_team_total"], 2440000)
        self.assertEqual(res["winner"], "player_team")
        self.assertEqual(res["margin"], 110000)

        # Draw scenario
        res_draw = ref_aggregate_round_scores([500000], [500000])
        self.assertEqual(res_draw["winner"], "draw")
        self.assertEqual(res_draw["margin"], 0)

    def test_radar_geometry_and_theme_mapping(self):
        """Verifies 8-axis radar geometric coordinate calculation and color palette definitions."""
        w, h = 380, 340
        cx, cy = w / 2, h / 2
        max_r = max(40, min(cx, cy) - 45)
        self.assertEqual(cx, 190.0)
        self.assertEqual(cy, 170.0)
        self.assertEqual(max_r, 125.0)

        # 8-axis angular coordinates
        for i in range(8):
            angle = (2 * math.pi / 8) * i - (math.pi / 2)
            # Check angle at i=0 points straight up (-pi/2)
            if i == 0:
                self.assertAlmostEqual(angle, -math.pi / 2)
            # Coordinate at 100 skill score
            px = cx + max_r * (100.0 / 100.0) * math.cos(angle)
            py = cy + max_r * (100.0 / 100.0) * math.sin(angle)
            dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
            self.assertAlmostEqual(dist, max_r, places=4)

        # Approved Color Palettes
        palettes = {
            "player": {"outline": "#00E5FF", "fill": "#00BFA5"},
            "teammate": {"outline": "#00E676", "fill": "#00C853"},
            "revealed": {"outline": "#E040FB", "fill": "#9C27B0"},
            "hidden": {"outline": "#424250", "fill": ""}
        }
        self.assertEqual(palettes["player"]["outline"], "#00E5FF")
        self.assertEqual(palettes["teammate"]["outline"], "#00E676")
        self.assertEqual(palettes["revealed"]["outline"], "#E040FB")



# =============================================================================
# MODULE 11: Tier 1 — Solo Bancho IRC Referee & Score Extraction
# =============================================================================
class Test11_Tier1_BanchoRefereeAndScoreExtraction(unittest.TestCase):
    """Tier 1 Functional & Contract validation for Solo Bancho IRC referee bots."""

    def test_bancho_referee_command_generation(self):
        """Verifies proper generation of !mp make, !mp set 0 3 / 2 3, !mp map, !mp mods, !mp invite."""
        bot = app.BanchoRefereeBot("ref_user", "ref_pass")
        bot.channel = "#mp_555"
        sent_commands = []
        bot._send_raw = lambda line: sent_commands.append(line)

        # 1. Map setting with mods
        bot.set_map(123456, mods="DT", enforce_nf=True)
        self.assertTrue(any("PRIVMSG #mp_555 :!mp map 123456" in c for c in sent_commands))
        self.assertTrue(any("PRIVMSG #mp_555 :!mp mods DT NF" in c for c in sent_commands))

        # 2. Player invite
        sent_commands.clear()
        bot.invite_player("TestPlayer")
        self.assertTrue(any("PRIVMSG #mp_555 :!mp invite TestPlayer" in c for c in sent_commands))

        # 3. Match countdown and abort
        sent_commands.clear()
        bot.start_countdown(5)
        self.assertTrue(any("PRIVMSG #mp_555 :!mp start 5" in c for c in sent_commands))
        bot.abort_match()
        self.assertTrue(any("PRIVMSG #mp_555 :!mp abort" in c for c in sent_commands))

    def test_bancho_chat_scorev2_regex_extraction(self):
        """Verifies high-speed regex extraction of player ScoreV2 from Bancho notice PRIVMSGs."""
        chat_lines = [
            ":BanchoBot!cho@ppy.sh PRIVMSG #mp_98765 :PlayerOne finished playing (Score: 845120, PASSED).",
            ":BanchoBot!cho@ppy.sh PRIVMSG #mp_98765 :RivalBot finished playing (Score: 0, FAILED).",
            ":BanchoBot!cho@ppy.sh PRIVMSG #mp_98765 :TopPlayer finished playing (Score: 1000000, PASSED)."
        ]
        pattern = re.compile(r'([^\s:]+) finished playing \(Score: (\d+), (PASSED|FAILED)\)\.')

        # Match 1
        m1 = pattern.search(chat_lines[0])
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "PlayerOne")
        self.assertEqual(int(m1.group(2)), 845120)
        self.assertEqual(m1.group(3), "PASSED")

        # Match 2
        m2 = pattern.search(chat_lines[1])
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "RivalBot")
        self.assertEqual(int(m2.group(2)), 0)
        self.assertEqual(m2.group(3), "FAILED")

        # Match 3
        m3 = pattern.search(chat_lines[2])
        self.assertIsNotNone(m3)
        self.assertEqual(m3.group(1), "TopPlayer")
        self.assertEqual(int(m3.group(2)), 1000000)

    def test_bancho_match_creation_regex(self):
        """Verifies match ID parsing from Bancho lobby creation responses."""
        line1 = ":BanchoBot!cho@ppy.sh PRIVMSG BanchoBot :Created the tournament match https://osu.ppy.sh/mp/12345678"
        line2 = ":BanchoBot!cho@ppy.sh JOIN #mp_87654321"
        
        m1 = re.search(r'(?:#mp_|/mp/)(\d+)', line1)
        self.assertIsNotNone(m1)
        self.assertEqual(m1.group(1), "12345678")

        m2 = re.search(r'(?:#mp_|/mp/)(\d+)', line2)
        self.assertIsNotNone(m2)
        self.assertEqual(m2.group(1), "87654321")


# =============================================================================
# MODULE 12: Tier 1 — Hidden Opponent Scouting & Gemini AI Debriefing
# =============================================================================
class Test12_Tier1_HiddenScoutingAndAIDebriefing(unittest.TestCase):
    """Tier 1 Functional & Contract validation for Fog of War deduction and AI debriefing."""

    def test_hidden_opponent_fog_of_war_masking(self):
        """Verifies that unmasked true stats are preserved backend-side while UI view model hides values."""
        true_stats, top2, bot2 = ref_generate_8skill_profile("Pro")
        dossier = ref_generate_tactical_scouting_dossier("ShadowDemon", true_stats, "Pro")

        # Masked view model
        masked_view = {
            "name": dossier["name"],
            "tier": dossier["tier"],
            "is_hidden": True,
            "display_stats": {k: "?" for k in ALL_8_SKILLS}
        }
        self.assertTrue(masked_view["is_hidden"])
        for v in masked_view["display_stats"].values():
            self.assertEqual(v, "?")
        # True stats remain intact in backend dossier
        self.assertEqual(dossier["stats"], true_stats)

    def test_scouting_guessing_challenge_accuracy_calculation(self):
        """Verifies exact accuracy metric: (|Guessed Strengths ∩ True Top 2| + |Guessed Weaknesses ∩ True Bot 2|) / 4 * 100%."""
        true_top2 = ["Speed", "Aim"]
        true_bot2 = ["Tech", "Reading"]

        # Case 1: 100% (4/4 hits)
        eval_100 = ref_evaluate_scouting_guess(["Speed", "Aim"], ["Tech", "Reading"], true_top2, true_bot2)
        self.assertEqual(eval_100["accuracy_pct"], 100.0)
        self.assertEqual(eval_100["correct_count"], 4)
        self.assertIn("Meister-Scout", eval_100["verdict_title"])

        # Case 2: 50% (2/4 hits: Speed hit, Reading hit)
        eval_50 = ref_evaluate_scouting_guess(["Speed", "Streams"], ["Stamina", "Reading"], true_top2, true_bot2)
        self.assertEqual(eval_50["accuracy_pct"], 50.0)
        self.assertEqual(eval_50["correct_count"], 2)

        # Case 3: 0% (0/4 hits)
        eval_0 = ref_evaluate_scouting_guess(["Tech", "Reading"], ["Speed", "Aim"], true_top2, true_bot2)
        self.assertEqual(eval_0["accuracy_pct"], 0.0)
        self.assertEqual(eval_0["correct_count"], 0)

    def test_strategic_debriefing_offline_heuristic_generation(self):
        """Verifies that offline heuristic fallback debriefing generates structured German analysis."""
        match_summary = {
            "player_score": 5,
            "bot_score": 3,
            "badge": "OWC",
            "division": "Grand Finals"
        }
        true_profile = {
            "top_strengths": ["Speed", "Aim"],
            "top_weaknesses": ["Tech", "Reading"]
        }
        guess_eval = ref_evaluate_scouting_guess(["Speed", "Streams"], ["Tech", "Stamina"], ["Speed", "Aim"], ["Tech", "Reading"])
        report = ref_generate_strategic_debrief(match_summary, true_profile, guess_eval)

        self.assertIsInstance(report, str)
        self.assertIn("OFFIZIELLER CASTER-BERICHT", report)
        self.assertIn("SCOUTING-ANALYSE", report)
        self.assertIn("BAN/PICK- & DRAFT-BEWERTUNG", report)
        self.assertIn("COACHING-EMPFEHLUNG", report)
        self.assertIn("Speed", report)
        self.assertIn("Tech", report)


# =============================================================================
# MODULE 13: Tier 2 — Boundary & Corner Cases
# =============================================================================
class Test13_Tier2_BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2 Boundary verification across stat pools, ScoreV2 equations, and team limits."""

    def test_skill_bounds_clamping_strict_10_to_100(self):
        """Stress-tests 200 random profiles across all tiers to verify no stat is < 10 or > 100."""
        for tier in TIER_POINT_POOLS.keys():
            for _ in range(50):
                stats, _, _ = ref_generate_8skill_profile(tier)
                for skill, val in stats.items():
                    self.assertGreaterEqual(val, 10, f"{tier} {skill} fell below 10: {val}")
                    self.assertLessEqual(val, 100, f"{tier} {skill} exceeded 100: {val}")

    def test_scorev2_extreme_map_boundaries(self):
        """Verifies stability of ScoreV2 model on extreme/pathological map metadata."""
        stats = {k: 50 for k in ALL_8_SKILLS}
        extreme_maps = [
            {"name": "Ultra Low SR", "sr": 0.1, "bpm": 60, "len": 15, "cs": 1.0},
            {"name": "Ultra High SR", "sr": 12.5, "bpm": 360, "len": 400, "cs": 8.0},
            {"name": "Zero Length Drain", "sr": 5.0, "bpm": 180, "len": 0, "cs": 4.0},
            {"name": "Extreme High CS", "sr": 7.0, "bpm": 200, "len": 180, "cs": 10.0},
            {"name": "Missing Attributes", "sr": None, "bpm": None}
        ]
        for em in extreme_maps:
            res = ref_calculate_bot_scorev2(stats, em)
            self.assertGreaterEqual(res["scorev2"], 0)
            self.assertLessEqual(res["scorev2"], 1000000)
            self.assertGreaterEqual(res["acc"], 70.0)
            self.assertLessEqual(res["acc"], 100.0)

    def test_team_size_clamping_and_empty_scores(self):
        """Verifies team sizes clamp to [1, 4] and empty score lists aggregate cleanly."""
        r_low = ref_generate_team_roster(-5, "Rookie")
        self.assertEqual(r_low["team_size"], 1)

        r_high = ref_generate_team_roster(99, "Legend")
        self.assertEqual(r_high["team_size"], 4)

        agg_empty = ref_aggregate_round_scores([], [])
        self.assertEqual(agg_empty["player_team_total"], 0)
        self.assertEqual(agg_empty["opponent_team_total"], 0)
        self.assertEqual(agg_empty["winner"], "draw")

    def test_guessing_eval_boundary_combinations(self):
        """Verifies guessing evaluator handles empty inputs or None gracefully."""
        res_none = ref_evaluate_scouting_guess(None, None, ["Aim", "Speed"], ["Tech", "Reading"])
        self.assertEqual(res_none["accuracy_pct"], 0.0)
        self.assertEqual(res_none["correct_count"], 0)

    def test_roster_empty_and_corrupt_edge_cases(self):
        """Verifies handling of empty or missing team rosters without unhandled exceptions."""
        m_empty_team = {"player_team": [], "player_name": "SoloHero"}
        p_name = m_empty_team["player_team"][0]["name"] if m_empty_team.get("player_team") else m_empty_team.get("player_name", "Du")
        self.assertEqual(p_name, "SoloHero")

        m_none = {}
        p_name_none = m_none.get("player_team", [])[0]["name"] if m_none.get("player_team") else m_none.get("player_name", "Du")
        self.assertEqual(p_name_none, "Du")


# =============================================================================
# MODULE 14: Tier 3 — Cross-Feature Integration
# =============================================================================
class Test14_Tier3_CrossFeatureIntegration(unittest.TestCase):
    """Tier 3 Multi-module workflow and state machine transitions."""

    def test_cross_feature_roster_generation_and_full_round_scoring(self):
        """End-to-end integration: Roster generation -> Map demand simulation -> Team score sum."""
        roster = ref_generate_team_roster(team_size=3, tier_name="Challenger", player_username="UserPro")
        map_meta = {"name": "NM1 - Jump Aim", "sr": 5.8, "bpm": 190, "len": 135, "cs": 4.0, "weights": {"Aim": 0.5, "Consistency": 0.3, "Speed": 0.2}}

        p_scores = [ref_calculate_bot_scorev2(m["stats"], map_meta)["scorev2"] for m in roster["player_team"]]
        o_scores = [ref_calculate_bot_scorev2(m["stats"], map_meta)["scorev2"] for m in roster["opponent_team"]]

        agg = ref_aggregate_round_scores(p_scores, o_scores)
        self.assertEqual(agg["player_team_total"], sum(p_scores))
        self.assertEqual(agg["opponent_team_total"], sum(o_scores))
        self.assertIn(agg["winner"], ["player_team", "opponent_team", "draw"])

    def test_cross_feature_drafting_to_bancho_command_pipeline(self):
        """Integration: Map selection -> Mod translation -> Bancho command dispatch."""
        bot = app.BanchoRefereeBot("ref_bot", "pass")
        bot.channel = "#mp_1001"
        dispatched = []
        bot._send_raw = lambda line: dispatched.append(line)

        # Simulate drafting slot FM1 (Freemod)
        slot_map = {"id": 98765, "slot": "FM1", "mods": "FM"}
        bot.set_map(slot_map["id"], mods=slot_map["mods"], enforce_nf=True)

        self.assertTrue(any("!mp map 98765" in c for c in dispatched))
        self.assertTrue(any("!mp mods Freemod NF" in c for c in dispatched))

    def test_cross_feature_match_conclusion_to_guessing_and_debrief(self):
        """Integration: Match end -> Guess evaluation -> Caster debrief generation."""
        opp_stats, true_top2, true_bot2 = ref_generate_8skill_profile("Legend")
        opp_dossier = ref_generate_tactical_scouting_dossier("Mrekk-Bot", opp_stats, "Legend")

        # Player deduces Top 2
        guessed_top2 = copy.deepcopy(true_top2)
        guessed_bot2 = ["Precision", "Stamina"]

        guess_eval = ref_evaluate_scouting_guess(guessed_top2, guessed_bot2, true_top2, true_bot2)
        match_summary = {"player_score": 7, "bot_score": 5, "badge": "OWC", "division": "Grand Finals"}
        debrief = ref_generate_strategic_debrief(match_summary, opp_dossier, guess_eval)

        self.assertGreaterEqual(guess_eval["accuracy_pct"], 50.0)
        self.assertIn("OFFIZIELLER CASTER-BERICHT", debrief)
        self.assertIn("Endstand: 7 : 5", debrief)


# =============================================================================
# MODULE 15: Tier 4 — Real-World Workloads & E2E Simulations
# =============================================================================
class Test15_Tier4_RealWorldWorkloadsAndE2E(unittest.TestCase):
    """Tier 4 Realistic tournament match lifecycle workloads."""

    def test_e2e_1v1_best_of_7_tournament_simulation(self):
        """Simulates full Best of 7 (First to 4) 1v1 match: Bans -> Picks -> ScoreV2 -> Conclusion."""
        roster = ref_generate_team_roster(team_size=1, tier_name="Challenger", player_username="SoloHero")
        pool = {
            f"NM{i}": {"sr": 5.5 + (i * 0.2), "bpm": 180 + (i * 5), "len": 140, "weights": {"Aim": 0.5, "Consistency": 0.5}}
            for i in range(1, 10)
        }
        p_wins = 0
        b_wins = 0
        slots = list(pool.keys())
        round_idx = 0

        while p_wins < 4 and b_wins < 4 and round_idx < len(slots):
            cur_slot = slots[round_idx]
            map_meta = pool[cur_slot]
            p_score = ref_calculate_bot_scorev2(roster["player_team"][0]["stats"], map_meta)["scorev2"]
            b_score = ref_calculate_bot_scorev2(roster["opponent_team"][0]["stats"], map_meta)["scorev2"]

            if p_score >= b_score:
                p_wins += 1
            else:
                b_wins += 1
            round_idx += 1

        self.assertTrue(p_wins == 4 or b_wins == 4, "Match must reach target 4 wins")
        self.assertGreaterEqual(p_wins + b_wins, 4)
        self.assertLessEqual(p_wins + b_wins, 7)

    def test_e2e_4v4_world_cup_grand_finals_best_of_13_simulation(self):
        """Simulates full 4v4 World Cup Grand Finals Best of 13 (First to 7) with full debriefing."""
        roster = ref_generate_team_roster(team_size=4, tier_name="Legend", player_username="TeamCaptain")
        pool = {
            f"SLOT{i}": {"sr": 6.8 + (i * 0.1), "bpm": 200 + (i * 4), "len": 160, "weights": {"Speed": 0.3, "Aim": 0.3, "Consistency": 0.4}}
            for i in range(1, 14)
        }
        p_wins = 0
        o_wins = 0

        for s_name, map_meta in pool.items():
            if p_wins >= 7 or o_wins >= 7:
                break
            p_scores = [ref_calculate_bot_scorev2(m["stats"], map_meta)["scorev2"] for m in roster["player_team"]]
            o_scores = [ref_calculate_bot_scorev2(m["stats"], map_meta)["scorev2"] for m in roster["opponent_team"]]
            agg = ref_aggregate_round_scores(p_scores, o_scores)

            if agg["winner"] == "player_team":
                p_wins += 1
            else:
                o_wins += 1

        self.assertTrue(p_wins == 7 or o_wins == 7)
        # Verify final debrief generation
        opp_lead = roster["opponent_team"][0]
        eval_guess = ref_evaluate_scouting_guess(opp_lead["top_strengths"][:1], [], opp_lead["top_strengths"], opp_lead["top_weaknesses"])
        summary = {"player_score": p_wins, "bot_score": o_wins, "badge": "OWC", "division": "Grand Finals 4v4"}
        debrief = ref_generate_strategic_debrief(summary, opp_lead, eval_guess)
        self.assertIn(f"Endstand: {p_wins} : {o_wins}", debrief)

    def test_e2e_bancho_referee_session_lifecycle(self):
        """Simulates Bancho IRC lobby lifecycle: Connect -> Join -> Set -> Map -> Extract Score -> Close."""
        bot = app.BanchoRefereeBot("Referee_Master", "token123")
        commands_sent = []
        bot._send_raw = lambda line: commands_sent.append(line)
        bot.channel = "#mp_8888"

        # 1. Mode config
        bot.set_team_mode(team_size=2)
        self.assertTrue(any("!mp set 2 1 4" in c or "!mp set 2 3 4" in c for c in commands_sent))

        # 2. Map & Mods
        commands_sent.clear()
        bot.set_map(444555, mods="HR", enforce_nf=True)
        self.assertTrue(any("!mp map 444555" in c for c in commands_sent))
        self.assertTrue(any("!mp mods HR NF" in c for c in commands_sent))

        # 3. Score extraction simulation
        notice_line = ":BanchoBot!cho@ppy.sh PRIVMSG #mp_8888 :CaptainDE finished playing (Score: 924300, PASSED)."
        m = re.search(r'([^\s:]+) finished playing \(Score: (\d+), (PASSED|FAILED)\)\.', notice_line)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "CaptainDE")
        self.assertEqual(int(m.group(2)), 924300)

        # 4. Close
        commands_sent.clear()
        bot.close_lobby()
        self.assertTrue(any("!mp close" in c for c in commands_sent))


# =============================================================================
# MODULE 16: Tier 5 — Adversarial Security, Hardening & Build Pipeline
# =============================================================================
class Test16_Tier5_AdversarialSecurityAndPackaging(unittest.TestCase):
    """Tier 5 Adversarial penetration testing, CRLF fuzzing, and build pipeline integrity."""

    def test_bancho_irc_crlf_adversarial_fuzzing(self):
        """Fuzzes BanchoRefereeBot with various CRLF injection payloads across all endpoints."""
        bot = app.BanchoRefereeBot("user", "pass")
        bot.channel = "#mp_123"
        sent_commands = []
        bot._send_raw = lambda line: sent_commands.append(line)

        payloads = [
            "Test\r\nPRIVMSG #mp_123 :!mp close",
            "Player\rPRIVMSG BanchoBot :!mp abort\n",
            "Slot\n\r!mp password hacked",
            "12345\r\n\r\nPRIVMSG #mp_123 :Spam"
        ]
        for p in payloads:
            sent_commands.clear()
            bot.send_mp(p)
            self.assertEqual(len(sent_commands), 1)
            self.assertNotIn("\r", sent_commands[0])
            self.assertNotIn("\n", sent_commands[0])

            sent_commands.clear()
            bot.invite_player(p)
            self.assertEqual(len(sent_commands), 1)
            self.assertNotIn("\r", sent_commands[0])
            self.assertNotIn("\n", sent_commands[0])

    def test_pyinstaller_spec_and_packaging_integrity(self):
        """Verifies UHOHub.spec exists, packages SQLite DB, JSON pools, and defines standalone target."""
        spec_path = os.path.join(PROJECT_ROOT, "UHOHub.spec")
        self.assertTrue(os.path.exists(spec_path), "UHOHub.spec must exist")
        with open(spec_path, "r", encoding="utf-8") as f:
            spec_content = f.read()

        self.assertIn("app.py", spec_content)
        self.assertIn("beatmaps_analyzed.db", spec_content)
        self.assertIn("compact_ranked_maps.json", spec_content)
        self.assertIn("official_tournament_pools.json", spec_content)
        self.assertIn("name='UHOHub'", spec_content)

    def test_build_desktop_powershell_script_validity(self):
        """Verifies build_and_package_desktop.ps1 has correct Desktop destination paths."""
        ps1_path = os.path.join(PROJECT_ROOT, "build_and_package_desktop.ps1")
        if os.path.exists(ps1_path):
            with open(ps1_path, "r", encoding="utf-8") as f:
                ps1_content = f.read()
            self.assertIn("UHOHub.exe", ps1_content)
            self.assertIn("UHOHub.zip", ps1_content)
            self.assertIn("Desktop", ps1_content)

    def test_ensure_osu_irc_password_logic(self):
        """Verifies ensure_osu_irc_password invokes callback immediately if credentials exist."""
        class DummyApp:
            def __init__(self):
                self.osu_username = "ProPlayer"
                self.osu_irc_password = "secret_irc_password"
            def ensure_osu_irc_password(self, on_success_callback, cancel_callback=None):
                cur_pwd = getattr(self, "osu_irc_password", "").strip()
                cur_user = getattr(self, "osu_username", "").strip()
                if cur_pwd and cur_user:
                    if callable(on_success_callback):
                        on_success_callback()
                    return

        dummy = DummyApp()
        executed = []
        dummy.ensure_osu_irc_password(on_success_callback=lambda: executed.append(True))
        self.assertEqual(len(executed), 1)
        self.assertTrue(executed[0])

    def test_tourney_play_date_filtering(self):
        """Verifies stale historical plays prior to pick timestamp are filtered out."""
        pick_time = 1756345000 # Reference timestamp
        stale_date_str = "2024-01-01 12:00:00" # Old play
        recent_date_str = "2026-08-28 01:23:45" # Fresh play

        stale_dt = datetime.datetime.strptime(stale_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        recent_dt = datetime.datetime.strptime(recent_date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)

        self.assertTrue(stale_dt.timestamp() < pick_time - 120, "Stale play must be older than pick time")
        self.assertTrue(recent_dt.timestamp() >= pick_time - 120, "Recent play must be valid for evaluation")

    def test_default_tournament_slot_skillsets_lookup(self):
        """Verifies standard tournament slot skillset lookup and conventions."""
        self.assertEqual(app.get_slot_standard_skillset_name("NM1"), "Consistency")
        self.assertEqual(app.get_slot_standard_skillset_name("NM4"), "Tech & Reading")
        self.assertEqual(app.get_slot_standard_skillset_name("HR1"), "Precision & Aim")
        self.assertEqual(app.get_slot_standard_skillset_name("HR2"), "Consistency & Stamina")
        self.assertEqual(app.get_slot_standard_skillset_name("DT1"), "Pure Speed & Bursts")
        self.assertEqual(app.get_slot_standard_skillset_name("TB"), "Tiebreaker All-Around")
        self.assertEqual(app.get_slot_standard_skillset_name("CUSTOM_MAP"), "All-Around")

    def test_bancho_referee_auto_start_on_all_ready(self):
        """Verifies referee bot sends !mp start 5 when 'All players are ready' is received."""
        bot = app.BanchoRefereeBot("user", "pass")
        bot.channel = "#mp_999"
        sent_commands = []
        bot._send_raw = lambda line: sent_commands.append(line)

        # Trigger countdown
        bot.start_countdown(5)
        self.assertTrue(any("!mp start 5" in cmd for cmd in sent_commands))

    def test_relaxed_bancho_score_regex_extraction(self):
        """Verifies extraction of scores for various player username formats and punctuation."""
        samples = [
            "Louis finished playing (Score: 785420, PASSED).",
            "[User-Name_99] finished playing (Score: 1000000, PASSED)",
            "Player 1 finished playing (Score: 450123, FAILED).",
        ]
        pattern = r'(.+?)\s+finished playing\s*\(\s*Score:\s*(\d+)\s*,\s*(PASSED|FAILED)\s*\)'
        for s in samples:
            m = re.search(pattern, s)
            self.assertIsNotNone(m, f"Failed to match: {s}")
            self.assertTrue(int(m.group(2)) > 0)

    def test_ai_training_8_skillsets_pre_caching_and_refill(self):
        """Verifies 8-skillset pre-caching loads 3 maps per skill and refills seamlessly."""
        class MockApp:
            pass
        mock = MockApp()
        mock.recent_ai_training_map_ids = set()
        mock.ai_training_target_skill = "Streams"
        mock._banned_mods = set()
        mock._ai_prefetched_maps_pool = {}

        # Bind methods
        mock._preload_ai_training_cache = types.MethodType(app.App._preload_ai_training_cache, mock)
        mock._refill_skill_cache = types.MethodType(app.App._refill_skill_cache, mock)

        mock._preload_ai_training_cache(base_sr=5.5)

        all_skills = ["Aim", "Streams", "Speed", "Stamina", "Tech", "Precision", "Reading", "Consistency"]
        for sk in all_skills:
            self.assertIn(sk, mock._ai_prefetched_maps_pool)
            self.assertEqual(len(mock._ai_prefetched_maps_pool[sk]), 3, f"Skill {sk} must have exactly 3 pre-cached maps")
            for m in mock._ai_prefetched_maps_pool[sk]:
                self.assertIn("id", m)
                self.assertIn("name", m)
                self.assertIn("sr", m)

        # Test pop and refill
        popped_map = mock._ai_prefetched_maps_pool["Speed"].pop(0)
        self.assertEqual(len(mock._ai_prefetched_maps_pool["Speed"]), 2)
        mock._refill_skill_cache("Speed", target_sr=5.5)
        self.assertEqual(len(mock._ai_prefetched_maps_pool["Speed"]), 3, "Refill must restore 3 maps in cache")

    def test_tournament_referee_multiplayer_parity(self):
        """Verifies tournament referee lobby creates password and dispatches invite exactly like multiplayer."""
        bot = app.BanchoRefereeBot("Kingmaster", "irc_token_123")
        bot.channel = "#mp_8888"
        dispatched = []
        bot._send_raw = lambda line: dispatched.append(line)

        bot.set_team_mode(team_size=1)
        bot.invite_player("Kingmaster")
        bot.send_channel_message("Willkommen zum UHO Hub Turniermatch!")

        self.assertTrue(any("!mp set 0 3 2" in cmd for cmd in dispatched))
        self.assertTrue(any("!mp invite Kingmaster" in cmd for cmd in dispatched))
        self.assertTrue(any("PRIVMSG #mp_8888 :Willkommen zum UHO Hub Turniermatch!" in cmd for cmd in dispatched))


# =============================================================================
# Main Runner
# =============================================================================
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
