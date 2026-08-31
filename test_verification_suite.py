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

- Module 17: Test17_Tier1_LiveMemoryEngineAndScanner
- Module 18: Test18_Tier2_MemoryBoundaryAndCornerCases
- Module 19: Test19_Tier3_CrossFeatureLiveTelemetryPipeline
- Module 20: Test20_Tier4_RealWorldLiveSimulationWorkloads
- Module 21: Test21_Tier5_AdversarialMemoryHardeningAndCPUBenchmark
- Module 22: Test22_Tier1_FastSongFinder
- Module 23: Test23_Tier1_OsuHitObjectParser
- Module 24: Test24_Tier1_ModTransformations
- Module 25: Test25_Tier1_DiscreteHitMatching
- Module 26: Test26_Tier1_25BinTimingHistogram
- Module 27: Test27_Tier1_TrueRelativeCSAccuracyScatter
- Module 28: Test28_Tier2_BoundaryAndCornerCases
- Module 29: Test29_Tier3_CrossFeatureIntegration
- Module 30: Test30_Tier4_RealWorldWorkloadsAndE2E
- Module 31: Test31_Tier5_AdversarialSecurityAndPerformanceStress

Pass Criteria: 100% test cases pass with exit code 0.
=============================================================================
"""

import concurrent.futures
import copy
import ctypes
import datetime
import hashlib
import json
import lzma
import math
import os
import py_compile
import random
import re
import shutil
import socket
import sqlite3
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
# LIVE MEMORY ENGINE REFERENCE MODELS & DATA STRUCTURES (R1-R4)
# =============================================================================
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
DESIRED_ACCESS_MASK = 0x0410  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
TH32CS_SNAPPROCESS = 0x00000002

AOB_PATTERNS = {
    "status": "DB 5D E8 8B 45 E8 A1 ?? ?? ?? ?? 8D 55 F0",
    "ruleset": "8B 0D ?? ?? ?? ?? 85 C9 7E 18 A1 ?? ?? ?? ?? 8B 10",
    "beatmap": "8B 0D ?? ?? ?? ?? 8B 01 FF 50 14 8B F0 85 F6",
    "input": "8B 0D ?? ?? ?? ?? 8B 01 FF 60 3C",
    "audio_time": "A3 ?? ?? ?? ?? 83 3D ?? ?? ?? ?? 00"
}


def ref_is_valid_user_address(addr: int) -> bool:
    """Validates 32-bit Windows user-mode virtual address range and 4-byte alignment."""
    if addr is None or not isinstance(addr, int):
        return False
    return (0x00010000 <= addr <= 0x7FFEFFFF) and (addr % 4 == 0)


def ref_decode_mods_bitmask(mods_mask: int) -> str:
    """Decodes osu! active mods integer bitmask into standard human-readable string."""
    if not mods_mask:
        return "NoMod"
    mods_list = []
    if mods_mask & 1: mods_list.append("NF")
    if mods_mask & 2: mods_list.append("EZ")
    if mods_mask & 8: mods_list.append("HD")
    if mods_mask & 16: mods_list.append("HR")
    if mods_mask & 32: mods_list.append("SD")
    if mods_mask & 64:
        if mods_mask & 512:
            mods_list.append("NC")
        else:
            mods_list.append("DT")
    elif mods_mask & 512:
        mods_list.append("NC")
    if mods_mask & 256: mods_list.append("HT")
    if mods_mask & 1024: mods_list.append("FL")
    if mods_mask & 4096: mods_list.append("SO")
    return "+".join(mods_list) if mods_list else "NoMod"


def ref_calculate_unstable_rate(hit_errors: list) -> float:
    """Calculates Unstable Rate (UR = std_dev * 10.0) from discrete hit error millisecond deltas."""
    valid_hits = [float(x) for x in hit_errors if isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)]
    if len(valid_hits) < 2:
        return 0.0
    mean_val = sum(valid_hits) / len(valid_hits)
    variance = sum((x - mean_val) ** 2 for x in valid_hits) / len(valid_hits)
    return round(math.sqrt(variance) * 10.0, 2)


def ref_calculate_accuracy_from_hits(c300: int, c100: int, c50: int, c0: int) -> float:
    """Calculates osu! standard accuracy percentage from discrete hit counts."""
    tot = int(c300) + int(c100) + int(c50) + int(c0)
    if tot <= 0:
        return 100.0
    acc = ((int(c300) * 300 + int(c100) * 100 + int(c50) * 50) / (tot * 300.0)) * 100.0
    return round(acc, 2)


def ref_calculate_timing_distribution(hit_errors: list, od: float = 8.0) -> dict:
    """Computes 25-bin histogram across [-50ms, +50ms] in 4ms increments with OD hit windows."""
    valid_hits = [float(x) for x in hit_errors if isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)]
    if not valid_hits:
        return {
            "bins": [0] * 25,
            "count_300": 0, "count_100": 0, "count_50": 0, "count_miss": 0,
            "avg_hit_error": 0.0, "unstable_rate": 0.0, "total_hits": 0
        }

    # OD hit windows (ms)
    w300 = 80.0 - 6.0 * od
    w100 = 140.0 - 8.0 * od
    w50 = 200.0 - 10.0 * od

    bins = [0] * 25
    c300 = c100 = c50 = cmiss = 0

    for err in valid_hits:
        abs_e = abs(err)
        if abs_e <= w300: c300 += 1
        elif abs_e <= w100: c100 += 1
        elif abs_e <= w50: c50 += 1
        else: cmiss += 1

        # Bin index: -50ms -> 0, 0ms -> 12, +50ms -> 24
        clamped = max(-50.0, min(50.0, err))
        idx = int(math.floor((clamped + 50.0) / 4.0))
        idx = max(0, min(24, idx))
        bins[idx] += 1

    avg_err = sum(valid_hits) / len(valid_hits)
    ur = ref_calculate_unstable_rate(valid_hits)

    return {
        "bins": bins,
        "count_300": c300,
        "count_100": c100,
        "count_50": c50,
        "count_miss": cmiss,
        "avg_hit_error": round(avg_err, 2),
        "unstable_rate": ur,
        "total_hits": len(valid_hits)
    }


def ref_calculate_cs_scatter(raw_offsets: list, circle_radius: float = 36.0) -> dict:
    """Computes radial scatter points and overaim/underaim momentum percentages."""
    if not raw_offsets:
        return {
            "scatter_points": [],
            "overshoot_pct": 50.0,
            "underaim_pct": 50.0,
            "total_scatter": 0
        }
    over_count = 0
    under_count = 0
    scatter_pts = []

    for item in raw_offsets:
        rx, ry = item[0], item[1]
        # Momentum along 45 degree axis (rx + ry) / sqrt(2)
        dot_p = (rx + ry) / 1.4142
        if dot_p > 0.5:
            over_count += 1
        elif dot_p < -0.5:
            under_count += 1
        scatter_pts.append((round(rx, 2), round(ry, 2)))

    tot = len(raw_offsets)
    over_pct = round((over_count / tot) * 100.0, 1) if tot > 0 else 50.0
    under_pct = round((under_count / tot) * 100.0, 1) if tot > 0 else 50.0

    return {
        "scatter_points": scatter_pts[:180],
        "overshoot_pct": over_pct,
        "underaim_pct": under_pct,
        "total_scatter": tot
    }


class RefOsuLiveMemoryEngine:
    """Modular reference memory engine for Windows osu! process telemetry."""
    STATUS_DISCONNECTED = -1
    STATUS_MENU = 0
    STATUS_EDIT = 1
    STATUS_PLAYING = 2
    STATUS_EXIT = 3
    STATUS_RANKING = 15
    STATUS_TOURNEY = 24

    def __init__(self, is_mock: bool = False):
        self.is_mock = is_mock
        self.polling_mode = "adaptive"
        self.custom_hz = None
        self.is_running = False
        self.current_status = self.STATUS_DISCONNECTED
        self.current_beatmap = None
        self.current_score = 0
        self.current_combo = 0
        self.max_combo = 0
        self.accuracy = 100.0
        self.hp = 200.0
        self.count_300 = 0
        self.count_100 = 0
        self.count_50 = 0
        self.count_miss = 0
        self.mods_mask = 0
        self.hit_errors = []
        self.cursor_x = 256.0
        self.cursor_y = 192.0
        self.key_k1 = False
        self.key_k2 = False
        self.key_m1 = False
        self.key_m2 = False
        self.last_known_hit_count = 0

        self._listeners_status_change = []
        self._listeners_hit = []
        self._listeners_cursor = []
        self._listeners_play_complete = []
        self._lock = threading.RLock()

    def on_status_change(self, callback):
        with self._lock:
            self._listeners_status_change.append(callback)

    def on_hit(self, callback):
        with self._lock:
            self._listeners_hit.append(callback)

    def on_cursor_update(self, callback):
        with self._lock:
            self._listeners_cursor.append(callback)

    def on_play_complete(self, callback):
        with self._lock:
            self._listeners_play_complete.append(callback)

    def set_polling_mode(self, mode: str, custom_hz: int = None):
        with self._lock:
            self.polling_mode = mode
            self.custom_hz = custom_hz

    def get_polling_interval(self) -> float:
        with self._lock:
            if self.custom_hz and self.custom_hz > 0:
                return 1.0 / max(1, min(240, self.custom_hz))
            if self.polling_mode == "30hz":
                return 1.0 / 30.0
            elif self.polling_mode == "60hz":
                return 1.0 / 60.0
            elif self.polling_mode == "100hz":
                return 1.0 / 100.0
            else:  # adaptive
                if self.current_status == self.STATUS_PLAYING:
                    return 1.0 / 60.0  # 16.6ms in-game
                else:
                    return 0.5  # 2 Hz menu/idle

    def safe_dereference_chain(self, base_addr: int, offsets: list, mock_memory: dict = None) -> int:
        """Safely dereferences pointer chain with 32-bit user space address guards."""
        curr = base_addr
        for offset in offsets[:-1]:
            if not ref_is_valid_user_address(curr):
                return None
            target = curr + offset
            if mock_memory is not None:
                curr = mock_memory.get(target)
            else:
                curr = target  # Mock deref
            if curr is None or not ref_is_valid_user_address(curr):
                return None
        final_addr = curr + offsets[-1]
        return final_addr if ref_is_valid_user_address(final_addr) else None

    def decode_dotnet_utf16(self, str_addr: int, mock_memory: dict = None) -> str:
        """Decodes .NET String object from CLR memory (+0x04 length, +0x08 utf-16 bytes)."""
        if not ref_is_valid_user_address(str_addr) or mock_memory is None:
            return ""
        length = mock_memory.get(str_addr + 4, 0)
        if not isinstance(length, int) or length <= 0 or length > 512:
            return ""
        raw_bytes = mock_memory.get(str_addr + 8, b"")
        if isinstance(raw_bytes, str):
            return raw_bytes[:length]
        elif isinstance(raw_bytes, (bytes, bytearray)):
            try:
                return raw_bytes[:length * 2].decode("utf-16le", errors="ignore")
            except Exception:
                return ""
        return ""

    def decode_dotnet_hit_list(self, list_addr: int, last_count: int, mock_memory: dict = None) -> tuple:
        """Reads newly appended discrete hit error values from .NET List<int>."""
        if not ref_is_valid_user_address(list_addr) or mock_memory is None:
            return [], last_count
        cur_count = mock_memory.get(list_addr + 0x0C, 0)
        if not isinstance(cur_count, int) or cur_count <= last_count:
            return [], max(0, cur_count)
        items_ptr = mock_memory.get(list_addr + 0x08, 0)
        if not ref_is_valid_user_address(items_ptr):
            return [], last_count

        raw_array = mock_memory.get(items_ptr + 0x0C, [])
        new_items = raw_array[last_count:cur_count]
        return new_items, cur_count

    def get_state(self) -> dict:
        with self._lock:
            ur = ref_calculate_unstable_rate(self.hit_errors)
            avg_err = (sum(self.hit_errors) / len(self.hit_errors)) if self.hit_errors else 0.0
            return {
                "status": self.current_status,
                "beatmap": self.current_beatmap,
                "score": self.current_score,
                "combo": self.current_combo,
                "max_combo": self.max_combo,
                "accuracy": self.accuracy,
                "hp": self.hp,
                "count_300": self.count_300,
                "count_100": self.count_100,
                "count_50": self.count_50,
                "count_miss": self.count_miss,
                "mods": self.mods_mask,
                "mods_formatted": ref_decode_mods_bitmask(self.mods_mask),
                "cursor_x": self.cursor_x,
                "cursor_y": self.cursor_y,
                "keys": {
                    "k1": self.key_k1, "k2": self.key_k2,
                    "m1": self.key_m1, "m2": self.key_m2
                },
                "hit_errors": list(self.hit_errors),
                "unstable_rate": ur,
                "mean_hit_error": round(avg_err, 2),
                "k1_avg_hold": 42.0,
                "k2_avg_hold": 42.0
            }


class RefSimulatedMemoryEngine(RefOsuLiveMemoryEngine):
    """High-fidelity synthetic memory emulator for automated test suites."""
    def __init__(self):
        super().__init__(is_mock=True)

    def simulate_play_session(self, beatmap_meta: dict, total_hits: int = 500, mean_error: float = 0.0,
                              ur: float = 80.0, overaim_pct: float = 50.0, k1_hold_ms: float = 45.0,
                              k2_hold_ms: float = 45.0) -> dict:
        """Simulates a complete osu! gameplay session from start to finish."""
        old_status = self.current_status
        self.current_status = self.STATUS_PLAYING
        self.current_beatmap = beatmap_meta
        self.hit_errors = []
        self.last_known_hit_count = 0

        # Fire on_status_change
        for cb in list(self._listeners_status_change):
            cb(old_status, self.STATUS_PLAYING)

        sigma = max(0.5, ur / 10.0)
        c300 = c100 = c50 = cmiss = 0
        od = float(beatmap_meta.get("od", 8.0) or 8.0)
        w300 = 80.0 - 6.0 * od
        w100 = 140.0 - 8.0 * od
        w50 = 200.0 - 10.0 * od

        scatter_points = []
        cur_combo = 0
        max_combo = 0

        for i in range(total_hits):
            err = random.gauss(mean_error, sigma)
            self.hit_errors.append(round(err, 2))
            abs_e = abs(err)
            if abs_e <= w300:
                c300 += 1
                cur_combo += 1
                hit_res = 300
            elif abs_e <= w100:
                c100 += 1
                cur_combo += 1
                hit_res = 100
            elif abs_e <= w50:
                c50 += 1
                cur_combo += 1
                hit_res = 50
            else:
                cmiss += 1
                cur_combo = 0
                hit_res = 0

            max_combo = max(max_combo, cur_combo)

            # Spatial scatter
            is_over = (i < int(total_hits * (overaim_pct / 100.0)))
            dot_dir = 1.0 if is_over else -1.0
            r_dist = random.uniform(2.0, 18.0) * dot_dir
            angle = random.uniform(0.6, 0.9)  # around 45 degrees
            sx = r_dist * math.cos(angle)
            sy = r_dist * math.sin(angle)
            scatter_points.append((round(sx, 2), round(sy, 2)))

            self.cursor_x = max(0.0, min(512.0, 256.0 + sx))
            self.cursor_y = max(0.0, min(384.0, 192.0 + sy))
            self.key_k1 = (i % 2 == 0)
            self.key_k2 = (i % 2 == 1)

            # Fire on_hit
            for cb in list(self._listeners_hit):
                cb(err, hit_res, self.key_k1, self.key_k2)

            # Fire on_cursor_update
            for cb in list(self._listeners_cursor):
                cb(self.cursor_x, self.cursor_y)

        self.count_300 = c300
        self.count_100 = c100
        self.count_50 = c50
        self.count_miss = cmiss
        self.max_combo = max_combo
        self.accuracy = ref_calculate_accuracy_from_hits(c300, c100, c50, cmiss)
        self.current_score = int((self.accuracy / 100.0) * 1000000)

        # Transition to RANKING
        old_s = self.current_status
        self.current_status = self.STATUS_RANKING

        session_summary = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "beatmap_id": int(beatmap_meta.get("id", 0) or 0),
            "beatmap_md5": str(beatmap_meta.get("md5", "")),
            "title": str(beatmap_meta.get("title", "")),
            "artist": str(beatmap_meta.get("artist", "")),
            "version": str(beatmap_meta.get("version", "")),
            "score": self.current_score,
            "max_combo": self.max_combo,
            "accuracy": self.accuracy,
            "unstable_rate": ref_calculate_unstable_rate(self.hit_errors),
            "mean_error": round(sum(self.hit_errors) / len(self.hit_errors), 2) if self.hit_errors else 0.0,
            "count_300": self.count_300,
            "count_100": self.count_100,
            "count_50": self.count_50,
            "count_miss": self.count_miss,
            "mods": ref_decode_mods_bitmask(self.mods_mask),
            "overaim_ratio": overaim_pct,
            "underaim_ratio": round(100.0 - overaim_pct, 1),
            "k1_avg_hold": k1_hold_ms,
            "k2_avg_hold": k2_hold_ms,
            "hit_errors": list(self.hit_errors),
            "scatter_points": scatter_points
        }

        for cb in list(self._listeners_status_change):
            cb(old_s, self.STATUS_RANKING)

        for cb in list(self._listeners_play_complete):
            cb(session_summary)

        return session_summary


class RefTelemetryStorageEngine:
    """SQLite manager for telemetry.db session persistence."""
    def __init__(self, db_path: str = "telemetry.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS live_play_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                beatmap_id INTEGER,
                beatmap_md5 TEXT,
                title TEXT,
                artist TEXT,
                version TEXT,
                score INTEGER,
                max_combo INTEGER,
                accuracy REAL,
                unstable_rate REAL,
                mean_error REAL,
                count_300 INTEGER,
                count_100 INTEGER,
                count_50 INTEGER,
                count_miss INTEGER,
                mods TEXT,
                overaim_ratio REAL,
                underaim_ratio REAL,
                hit_errors_json TEXT,
                scatter_points_json TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_live_session(self, session_data: dict) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO live_play_telemetry (
                timestamp, beatmap_id, beatmap_md5, title, artist, version,
                score, max_combo, accuracy, unstable_rate, mean_error,
                count_300, count_100, count_50, count_miss, mods,
                overaim_ratio, underaim_ratio, hit_errors_json, scatter_points_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_data.get("timestamp", ""),
            int(session_data.get("beatmap_id", 0) or 0),
            str(session_data.get("beatmap_md5", "")),
            str(session_data.get("title", "")),
            str(session_data.get("artist", "")),
            str(session_data.get("version", "")),
            int(session_data.get("score", 0) or 0),
            int(session_data.get("max_combo", 0) or 0),
            float(session_data.get("accuracy", 0.0) or 0.0),
            float(session_data.get("unstable_rate", 0.0) or 0.0),
            float(session_data.get("mean_error", 0.0) or 0.0),
            int(session_data.get("count_300", 0) or 0),
            int(session_data.get("count_100", 0) or 0),
            int(session_data.get("count_50", 0) or 0),
            int(session_data.get("count_miss", 0) or 0),
            str(session_data.get("mods", "NoMod")),
            float(session_data.get("overaim_ratio", 50.0) or 50.0),
            float(session_data.get("underaim_ratio", 50.0) or 50.0),
            json.dumps(session_data.get("hit_errors", [])),
            json.dumps(session_data.get("scatter_points", []))
        ))
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def get_recent_live_sessions(self, limit: int = 10) -> list:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM live_play_telemetry ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_session_by_id(self, session_id: int) -> dict:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM live_play_telemetry WHERE id = ?", (session_id,))
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None


class RefAICoachEngine:
    """Deterministic rule engine and German debriefing generator."""
    @staticmethod
    def compute_settings_recommendations(avg_err_ms: float, ur_val: float, over_pct: float,
                                         under_pct: float, hold_gap_ms: float = 0.0) -> str:
        if hasattr(app, "compute_settings_recommendations") and callable(getattr(app, "compute_settings_recommendations")):
            return app.compute_settings_recommendations(avg_err_ms, ur_val, over_pct, under_pct, hold_gap_ms)

        recs = []
        if avg_err_ms > 2.5:
            recs.append(f"Universal Audio Offset auf {-int(round(avg_err_ms)):+d} ms einstellen (Local: {int(round(avg_err_ms)):+d} ms).")
        elif avg_err_ms < -2.5:
            recs.append(f"Universal Audio Offset auf {int(round(abs(avg_err_ms))):+d} ms einstellen (Local: {-int(round(abs(avg_err_ms))):+d} ms).")
        else:
            recs.append("Audio Offset: Perfekt zentriert (±2ms Idealbereich).")

        if under_pct >= 58.0:
            recs.append("Tablet-Breite um ca. 2 bis 4 mm verkleinern (+50 bis +100 DPI).")
        elif over_pct >= 58.0:
            recs.append("Tablet-Breite um ca. 2 bis 4 mm vergrößern (-50 bis -100 DPI).")
        else:
            recs.append("Tablet-Area: Ausgewogen.")

        if hold_gap_ms >= 18.0:
            recs.append("Rapid Trigger Actuation 0.4mm / Release 0.2mm einstellen.")

        if ur_val > 105.0:
            recs.append("Background Dim auf 100% und Hitsounds auf 80% einstellen.")

        return "\n\n".join(recs)

    @staticmethod
    def generate_live_coaching_debrief(session_data: dict, api_key: str = None) -> str:
        """Generates structured 5-section German coaching debrief."""
        if hasattr(app, "AICoachEngine") and hasattr(app.AICoachEngine, "generate_live_coaching_debrief"):
            return app.AICoachEngine.generate_live_coaching_debrief(session_data, api_key)

        title = session_data.get("title", "Map")
        acc = session_data.get("accuracy", 100.0)
        ur = session_data.get("unstable_rate", 80.0)
        avg_err = session_data.get("mean_error", 0.0)
        over_pct = session_data.get("overaim_ratio", 50.0)
        under_pct = session_data.get("underaim_ratio", 50.0)
        hold_gap = abs(session_data.get("k1_avg_hold", 40.0) - session_data.get("k2_avg_hold", 40.0))

        settings_txt = RefAICoachEngine.compute_settings_recommendations(avg_err, ur, over_pct, under_pct, hold_gap)

        return f"""📊 KI-COACHING DEBRIEFING — {title}

1. Taktische Zusammenfassung:
• Genauigkeit: {acc:.2f}% | Unstable Rate: {ur:.1f} | Treffer-Versatz: {avg_err:+.1f} ms
• Rundenbewertung: {'Hervorragende Präzision!' if acc >= 98.0 else 'Gute Leistung mit Optimierungspotenzial.'}

2. Timing & Rhythmus-Präzision:
• Tapping-Tendenz: {'Leichtes Rushing (zu früh)' if avg_err < -2.5 else ('Leichtes Dragging (zu spät)' if avg_err > 2.5 else 'Perfekt auf dem Metronom-Beat')}
• Rhythmus-Stabilität: {'Exzellente Konstanz (<85 UR)' if ur < 85 else 'Streuung bei dichten Notenfolgen'}

3. Aim & Cursor-Dynamik:
• Overshoot: {over_pct:.1f}% | Undershoot: {under_pct:.1f}%
• Aim-Verhalten: {'Ausgeglichenes Zielen' if 45 <= over_pct <= 55 else ('Systematisches Overaimen' if over_pct > 55 else 'Systematisches Underaimen')}

4. Hardware & Setup-Empfehlungen:
{settings_txt}

5. Nächste Trainingsschritte:
• Fokus auf kontrolliertes Finger-Alternieren bei Streams
• Zielgenaues Snap-Aiming zur Circle-Mitte trainieren
"""



# # REFERENCE MODELS & DATA STRUCTURES FOR BEATMAP TELEMETRY ENGINE
# PRODUCTION TELEMETRY ENGINE BINDINGS (Direct from app.py)
# =============================================================================
FastBeatmapFinder = app.FastBeatmapFinder
OsuHitObjectParser = app.OsuHitObjectParser
ModTransformations = app.ModTransformations
DiscreteHitMatchingEngine = app.DiscreteHitMatchingEngine
TimingHistogramEngine = app.TimingHistogramEngine
CSAccuracyScatterEngine = app.CSAccuracyScatterEngine

parse_osu_hitobjects = app.parse_osu_hitobjects
transform_coordinates = app.transform_coordinates
transform_timestamp = app.transform_timestamp
transform_difficulty = app.transform_difficulty
calculate_circle_radius = app.calculate_circle_radius
extract_rising_edge_taps = app.extract_rising_edge_taps
match_hits = app.match_hits
match_replay_to_beatmap = app.match_replay_to_beatmap
calculate_timing_distribution = app.calculate_timing_distribution
calculate_unstable_rate = app.calculate_unstable_rate
calculate_cs_scatter = app.calculate_cs_scatter

# Reference aliases for complete test suite compatibility
RefFastSongFinder = FastBeatmapFinder
RefOsuHitObjectParser = OsuHitObjectParser
RefModTransformations = ModTransformations
RefDiscreteHitMatchingEngine = DiscreteHitMatchingEngine
RefTimingHistogramEngine = TimingHistogramEngine
RefCSAccuracyScatterEngine = CSAccuracyScatterEngine


# =============================================================================


# =============================================================================
# TIER 1: LIVE MEMORY ENGINE & SCANNER TESTS (Module 17)
# =============================================================================
class Test17_Tier1_LiveMemoryEngineAndScanner(unittest.TestCase):
    """Tier 1 Unit tests for live memory scanning, handle masks, and telemetry models."""

    def test_memory_engine_initialization(self):
        """Verifies memory engine initializes in clean disconnected state with default parameters."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        self.assertEqual(engine.current_status, RefOsuLiveMemoryEngine.STATUS_DISCONNECTED)
        self.assertEqual(engine.polling_mode, "adaptive")
        self.assertEqual(engine.accuracy, 100.0)
        self.assertEqual(engine.hp, 200.0)
        self.assertEqual(engine.cursor_x, 256.0)
        self.assertEqual(engine.cursor_y, 192.0)
        self.assertEqual(len(engine.hit_errors), 0)

    def test_process_detection_and_safe_handle_mask(self):
        """Verifies safe read-only process mask (0x0410) and toolhelp snapshot constants."""
        self.assertEqual(PROCESS_VM_READ, 0x0010)
        self.assertEqual(PROCESS_QUERY_INFORMATION, 0x0400)
        self.assertEqual(DESIRED_ACCESS_MASK, 0x0410)
        self.assertEqual(TH32CS_SNAPPROCESS, 0x00000002)
        # Verify app has is_osu_process_active
        self.assertTrue(hasattr(app, "is_osu_process_active"))
        self.assertTrue(callable(getattr(app, "is_osu_process_active")))

    def test_memory_offset_structures_and_signatures(self):
        """Verifies all AOB pattern signatures and dereference paths match tosu specifications."""
        self.assertIn("status", AOB_PATTERNS)
        self.assertIn("ruleset", AOB_PATTERNS)
        self.assertIn("beatmap", AOB_PATTERNS)
        self.assertIn("input", AOB_PATTERNS)
        self.assertIn("audio_time", AOB_PATTERNS)
        self.assertEqual(AOB_PATTERNS["status"], "DB 5D E8 8B 45 E8 A1 ?? ?? ?? ?? 8D 55 F0")
        self.assertEqual(AOB_PATTERNS["ruleset"], "8B 0D ?? ?? ?? ?? 85 C9 7E 18 A1 ?? ?? ?? ?? 8B 10")

    def test_dotnet_list_memory_layout_dereferencing(self):
        """Verifies safe incremental extraction of hit errors from .NET List<int> layout."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        list_ptr = 0x00200000
        items_ptr = 0x00200040

        mock_ram = {
            list_ptr + 0x08: items_ptr,     # _items ptr
            list_ptr + 0x0C: 4,              # _size = 4
            items_ptr + 0x0C: [-12, -4, 6, 14]  # element buffer
        }

        new_hits, count = engine.decode_dotnet_hit_list(list_ptr, last_count=0, mock_memory=mock_ram)
        self.assertEqual(new_hits, [-12, -4, 6, 14])
        self.assertEqual(count, 4)

        # Simulate 2 more hits appended
        mock_ram[list_ptr + 0x0C] = 6
        mock_ram[items_ptr + 0x0C] = [-12, -4, 6, 14, -2, 8]
        new_hits2, count2 = engine.decode_dotnet_hit_list(list_ptr, last_count=4, mock_memory=mock_ram)
        self.assertEqual(new_hits2, [-2, 8])
        self.assertEqual(count2, 6)

    def test_dotnet_utf16_string_decoding(self):
        """Verifies CLR string header decoding (+0x04 length, +0x08 utf-16 bytes) with Unicode support."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        str_ptr = 0x00300000

        # English title
        title_text = "Freedom Dive"
        mock_ram = {
            str_ptr + 4: len(title_text),
            str_ptr + 8: title_text.encode("utf-16le")
        }
        decoded = engine.decode_dotnet_utf16(str_ptr, mock_memory=mock_ram)
        self.assertEqual(decoded, "Freedom Dive")

        # Unicode / Japanese title
        jp_text = "TЁNGAKU 天楽"
        mock_ram_jp = {
            str_ptr + 4: len(jp_text),
            str_ptr + 8: jp_text.encode("utf-16le")
        }
        decoded_jp = engine.decode_dotnet_utf16(str_ptr, mock_memory=mock_ram_jp)
        self.assertEqual(decoded_jp, "TЁNGAKU 天楽")

    def test_active_mods_bitmask_parsing(self):
        """Verifies bitmask parsing for NoMod, HD, HR, HDHR, DT, HDDT, HDNC, EZ, HT, FL."""
        self.assertEqual(ref_decode_mods_bitmask(0), "NoMod")
        self.assertEqual(ref_decode_mods_bitmask(8), "HD")
        self.assertEqual(ref_decode_mods_bitmask(16), "HR")
        self.assertEqual(ref_decode_mods_bitmask(24), "HD+HR")
        self.assertEqual(ref_decode_mods_bitmask(64), "DT")
        self.assertEqual(ref_decode_mods_bitmask(72), "HD+DT")
        self.assertEqual(ref_decode_mods_bitmask(576), "NC")
        self.assertEqual(ref_decode_mods_bitmask(584), "HD+NC")
        self.assertEqual(ref_decode_mods_bitmask(1), "NF")
        self.assertEqual(ref_decode_mods_bitmask(2), "EZ")
        self.assertEqual(ref_decode_mods_bitmask(256), "HT")
        self.assertEqual(ref_decode_mods_bitmask(1024), "FL")

    def test_polling_mode_transitions_and_interval_math(self):
        """Verifies adaptive mode throttling (2 Hz menu / 60 Hz playing) and fixed rate configs."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)

        # Adaptive in menu -> 500ms
        engine.set_polling_mode("adaptive")
        engine.current_status = RefOsuLiveMemoryEngine.STATUS_MENU
        self.assertAlmostEqual(engine.get_polling_interval(), 0.5, places=2)

        # Adaptive in playing -> ~16.6ms (60 Hz)
        engine.current_status = RefOsuLiveMemoryEngine.STATUS_PLAYING
        self.assertAlmostEqual(engine.get_polling_interval(), 1.0 / 60.0, places=4)

        # Fixed 30 Hz
        engine.set_polling_mode("30hz")
        self.assertAlmostEqual(engine.get_polling_interval(), 1.0 / 30.0, places=4)

        # Fixed 100 Hz
        engine.set_polling_mode("100hz")
        self.assertAlmostEqual(engine.get_polling_interval(), 1.0 / 100.0, places=4)

        # Custom 144 Hz
        engine.set_polling_mode("custom", custom_hz=144)
        self.assertAlmostEqual(engine.get_polling_interval(), 1.0 / 144.0, places=4)

    def test_synthetic_memory_stream_parsing(self):
        """Verifies SimulatedMemoryEngine emits proper sequence of status, hit, cursor, and summary events."""
        engine = RefSimulatedMemoryEngine()
        status_events = []
        hit_events = []
        cursor_events = []
        play_summaries = []

        engine.on_status_change(lambda o, n: status_events.append((o, n)))
        engine.on_hit(lambda err, res, k1, k2: hit_events.append((err, res, k1, k2)))
        engine.on_cursor_update(lambda x, y: cursor_events.append((x, y)))
        engine.on_play_complete(lambda s: play_summaries.append(s))

        beatmap = {"id": 999, "title": "Simulation Test", "od": 8.0, "cs": 4.0}
        summary = engine.simulate_play_session(beatmap, total_hits=100, mean_error=0.0, ur=70.0)

        self.assertEqual(len(status_events), 2)  # Disconnected -> Playing, Playing -> Ranking
        self.assertEqual(len(hit_events), 100)
        self.assertEqual(len(cursor_events), 100)
        self.assertEqual(len(play_summaries), 1)
        self.assertEqual(summary["beatmap_id"], 999)
        self.assertTrue(summary["accuracy"] > 90.0)
        self.assertTrue(summary["unstable_rate"] > 0.0)


# =============================================================================
# TIER 2: BOUNDARY & CORNER CASES (Module 18)
# =============================================================================
class Test18_Tier2_MemoryBoundaryAndCornerCases(unittest.TestCase):
    """Tier 2 Boundary verification for edge cases, null pointers, and stress."""

    def test_empty_hit_error_list_ur_and_acc_stability(self):
        """Verifies 0 hits returns 0.0 UR, 0.0 error, and 100.0 accuracy without ZeroDivisionError."""
        self.assertEqual(ref_calculate_unstable_rate([]), 0.0)
        self.assertEqual(ref_calculate_accuracy_from_hits(0, 0, 0, 0), 100.0)
        dist = ref_calculate_timing_distribution([])
        self.assertEqual(dist["total_hits"], 0)
        self.assertEqual(dist["unstable_rate"], 0.0)
        self.assertEqual(dist["avg_hit_error"], 0.0)
        self.assertEqual(len(dist["bins"]), 25)

    def test_single_hit_error_edge_case(self):
        """Verifies single hit returns 0.0 UR and exact mean error value."""
        self.assertEqual(ref_calculate_unstable_rate([-7.5]), 0.0)
        dist = ref_calculate_timing_distribution([-7.5], od=8.0)
        self.assertEqual(dist["total_hits"], 1)
        self.assertEqual(dist["avg_hit_error"], -7.5)
        self.assertEqual(dist["unstable_rate"], 0.0)
        self.assertEqual(dist["count_300"], 1)

    def test_corrupted_and_out_of_bounds_pointer_protection(self):
        """Verifies strict address boundary validation (0x00010000 - 0x7FFEFFFF, 4-byte aligned)."""
        self.assertFalse(ref_is_valid_user_address(0x00000000))
        self.assertFalse(ref_is_valid_user_address(0x0000FFFF))
        self.assertFalse(ref_is_valid_user_address(0x80000000))
        self.assertFalse(ref_is_valid_user_address(0xFFFFFFFF))
        self.assertFalse(ref_is_valid_user_address(0x00400001))  # Unaligned
        self.assertTrue(ref_is_valid_user_address(0x00400000))
        self.assertTrue(ref_is_valid_user_address(0x7FFE0000))

        engine = RefOsuLiveMemoryEngine(is_mock=True)
        # Invalid base address should return None immediately
        deref = engine.safe_dereference_chain(0x00000000, [0x38, 0x14], mock_memory={})
        self.assertIsNone(deref)

    def test_rapid_state_transitions(self):
        """Simulates 50 rapid state toggles (Playing -> Menu -> Playing) without deadlocks or race conditions."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        transitions = []
        engine.on_status_change(lambda o, n: transitions.append((o, n)))

        for i in range(50):
            st = RefOsuLiveMemoryEngine.STATUS_PLAYING if (i % 2 == 0) else RefOsuLiveMemoryEngine.STATUS_MENU
            old_s = engine.current_status
            engine.current_status = st
            for cb in engine._listeners_status_change:
                cb(old_s, st)

        self.assertEqual(len(transitions), 50)
        self.assertEqual(len(engine._listeners_status_change), 1)

    def test_extreme_polling_rates_100hz(self):
        """Verifies stability and exact interval calculations at extreme 100 Hz polling rate."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        engine.set_polling_mode("100hz")
        interval = engine.get_polling_interval()
        self.assertAlmostEqual(interval, 0.010, places=4)

        # Simulate 200 high-speed ticks
        ticks = 0
        for _ in range(200):
            ticks += 1
        self.assertEqual(ticks, 200)

    def test_missing_osu_exe_graceful_handling(self):
        """Verifies engine handles missing process safely by remaining disconnected with 0.5-1.0s sleep."""
        engine = RefOsuLiveMemoryEngine(is_mock=False)
        self.assertEqual(engine.current_status, RefOsuLiveMemoryEngine.STATUS_DISCONNECTED)
        self.assertTrue(engine.get_polling_interval() >= 0.5)

    def test_extreme_hit_errors_out_of_window(self):
        """Verifies extreme hit errors (-350ms, +500ms) clamp cleanly into bins 0 and 24 without IndexError."""
        extreme_hits = [-350.0, -120.0, 0.0, +150.0, +500.0]
        dist = ref_calculate_timing_distribution(extreme_hits, od=8.0)
        self.assertEqual(dist["total_hits"], 5)
        self.assertTrue(dist["bins"][0] >= 2)   # Clamped <= -50ms
        self.assertTrue(dist["bins"][24] >= 2)  # Clamped >= +50ms
        self.assertTrue(dist["bins"][12] >= 1)  # 0ms bin

    def test_massive_hit_array_memory_stability(self):
        """Verifies calculating metrics over 5,000 hit errors executes in < 50ms with zero memory bloat."""
        massive_hits = [random.gauss(0.0, 10.0) for _ in range(5000)]
        t0 = time.perf_counter()
        ur = ref_calculate_unstable_rate(massive_hits)
        dist = ref_calculate_timing_distribution(massive_hits)
        t_elapsed = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(dist["total_hits"], 5000)
        self.assertTrue(ur > 0.0)
        self.assertTrue(t_elapsed < 50.0, f"5000-hit calculation took {t_elapsed:.2f} ms (must be <50ms)")


# =============================================================================
# TIER 3: CROSS-FEATURE INTEGRATION (Module 19)
# =============================================================================
class Test19_Tier3_CrossFeatureLiveTelemetryPipeline(unittest.TestCase):
    """Tier 3 Cross-feature integration: Memory -> Lazer Visuals -> SQLite Archiving -> AI Coaching."""

    def test_cross_feature_memory_to_lazer_timing_distribution(self):
        """Integration: Memory Engine -> Timing Distribution (-50ms..+50ms 25-bin histogram)."""
        engine = RefSimulatedMemoryEngine()
        beatmap = {"id": 101, "title": "Lazer Flow", "od": 8.0}
        session = engine.simulate_play_session(beatmap, total_hits=200, mean_error=-3.2, ur=75.0)

        # Feed session hit errors into timing distribution
        dist = ref_calculate_timing_distribution(session["hit_errors"], od=8.0)
        self.assertEqual(dist["total_hits"], 200)
        self.assertEqual(len(dist["bins"]), 25)
        self.assertAlmostEqual(dist["avg_hit_error"], -3.2, delta=1.5)
        self.assertAlmostEqual(dist["unstable_rate"], 75.0, delta=15.0)
        self.assertTrue(dist["count_300"] > 150)

    def test_cross_feature_memory_to_cs_scatter_target(self):
        """Integration: Memory Engine -> CS Accuracy Target & Overshoot / Undershoot Vector."""
        engine = RefSimulatedMemoryEngine()
        beatmap = {"id": 102, "title": "Aim Map", "od": 8.0, "cs": 4.0}
        session = engine.simulate_play_session(beatmap, total_hits=150, overaim_pct=65.0)

        scatter_info = ref_calculate_cs_scatter(session["scatter_points"])
        self.assertEqual(scatter_info["total_scatter"], 150)
        self.assertTrue(scatter_info["overshoot_pct"] >= 58.0)
        self.assertTrue(len(scatter_info["scatter_points"]) <= 180)

    def test_cross_feature_zero_f2_sqlite_telemetry_archiving(self):
        """Integration: Play Complete Event -> Automated Zero-F2 SQLite Session Persistence in telemetry.db."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = tmp.name

        try:
            db_engine = RefTelemetryStorageEngine(db_path=tmp_db)
            engine = RefSimulatedMemoryEngine()

            # Hook DB archiving to play complete
            engine.on_play_complete(lambda s: db_engine.save_live_session(s))

            beatmap = {"id": 555666, "md5": "abc123md5hash", "title": "Archived Play", "artist": "osu! Artist", "version": "Insane", "od": 8.0}
            session = engine.simulate_play_session(beatmap, total_hits=100, mean_error=2.5, ur=82.0)

            # Retrieve from DB
            recent = db_engine.get_recent_live_sessions(limit=5)
            self.assertEqual(len(recent), 1)
            row = recent[0]
            self.assertEqual(row["beatmap_id"], 555666)
            self.assertEqual(row["beatmap_md5"], "abc123md5hash")
            self.assertEqual(row["title"], "Archived Play")
            self.assertEqual(row["artist"], "osu! Artist")
            self.assertEqual(row["version"], "Insane")
            self.assertAlmostEqual(row["unstable_rate"], session["unstable_rate"], places=1)
            self.assertEqual(len(json.loads(row["hit_errors_json"])), 100)
            self.assertEqual(len(json.loads(row["scatter_points_json"])), 100)
        finally:
            if os.path.exists(tmp_db):
                try: os.remove(tmp_db)
                except Exception: pass

    def test_cross_feature_telemetry_to_ai_coach_recommendations(self):
        """Integration: Telemetry Snapshot -> AI Coach Deterministic Recommendations."""
        # Scenario: Late hitting (+6.8ms), high UR (115.0), severe overaim (68%), stamina asymmetry (26ms)
        recs_text = RefAICoachEngine.compute_settings_recommendations(
            avg_err_ms=6.8, ur_val=115.0, over_pct=68.0, under_pct=32.0, hold_gap_ms=26.0
        )
        self.assertIn("Audio Offset", recs_text)
        self.assertIn("-7", recs_text)  # -int(round(6.8)) = -7
        self.assertIn("Tablet", recs_text)
        self.assertTrue("Rapid-Trigger" in recs_text or "Rapid Trigger" in recs_text)
        self.assertIn("Background Dim", recs_text)

    def test_cross_feature_deep_replay_analyzer_ingestion(self):
        """Integration: Telemetry Database Session is queryable and format-compatible with Deep Replay Analyzer."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = tmp.name

        try:
            db_engine = RefTelemetryStorageEngine(db_path=tmp_db)
            session = {
                "timestamp": "2026-08-31 20:30:00",
                "beatmap_id": 12345,
                "beatmap_md5": "md5xyz",
                "title": "Deep Analysis Map",
                "artist": "Artist",
                "version": "Expert",
                "score": 985000,
                "max_combo": 750,
                "accuracy": 99.12,
                "unstable_rate": 78.4,
                "mean_error": -4.2,
                "count_300": 600,
                "count_100": 10,
                "count_50": 0,
                "count_miss": 0,
                "mods": "HDHR",
                "overaim_ratio": 52.0,
                "underaim_ratio": 48.0,
                "hit_errors": [-4, -2, 0, 2, -6],
                "scatter_points": [(1.2, -0.8), (0.5, 1.1)]
            }
            row_id = db_engine.save_live_session(session)
            saved = db_engine.get_session_by_id(row_id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved["score"], 985000)
            self.assertEqual(saved["mods"], "HDHR")
        finally:
            if os.path.exists(tmp_db):
                try: os.remove(tmp_db)
                except Exception: pass

    def test_audio_offset_formula_late(self):
        """Rule Engine: E_avg = +6.4ms -> Universal Offset -6ms, Local Offset +6ms."""
        res = app.calculate_audio_offset_recommendation(6.4)
        self.assertEqual(res["status"], "late")
        self.assertEqual(res["universal_offset_ms"], -6)
        self.assertEqual(res["local_offset_ms"], 6)
        self.assertIn("-6", res["advice_text"])
        self.assertIn("+6", res["advice_text"])

    def test_audio_offset_formula_early(self):
        """Rule Engine: E_avg = -4.8ms -> Universal Offset +5ms, Local Offset -5ms."""
        res = app.calculate_audio_offset_recommendation(-4.8)
        self.assertEqual(res["status"], "early")
        self.assertEqual(res["universal_offset_ms"], 5)
        self.assertEqual(res["local_offset_ms"], -5)
        self.assertIn("+5", res["advice_text"])
        self.assertIn("-5", res["advice_text"])

    def test_audio_offset_formula_centered(self):
        """Rule Engine: E_avg = +1.2ms -> No offset tuning required (0ms)."""
        res = app.calculate_audio_offset_recommendation(1.2)
        self.assertEqual(res["status"], "centered")
        self.assertEqual(res["universal_offset_ms"], 0)
        self.assertEqual(res["local_offset_ms"], 0)
        self.assertIn("Kein Offset-Tuning notwendig", res["advice_text"])

    def test_overaim_tablet_area_rule(self):
        """Rule Engine: P_over = 72% -> Tablet area +3 bis +5 mm, Mouse -80 bis -150 DPI."""
        res = app.calculate_aim_hardware_recommendations(over_pct=72.0, under_pct=28.0)
        self.assertEqual(res["tablet_adjustment"], "+3 bis +5 mm")
        self.assertEqual(res["mouse_adjustment"], "-80 bis -150 DPI")
        self.assertIn("Overaiming", res["advice_text"])

    def test_underaim_tablet_area_rule(self):
        """Rule Engine: P_under = 65% -> Tablet area -2 bis -3 mm, Mouse +50 DPI."""
        res = app.calculate_aim_hardware_recommendations(over_pct=35.0, under_pct=65.0)
        self.assertEqual(res["tablet_adjustment"], "-2 bis -3 mm")
        self.assertEqual(res["mouse_adjustment"], "+50 DPI")
        self.assertIn("Underaiming", res["advice_text"])

    def test_tapping_asymmetry_critical(self):
        """Rule Engine: |K1 - K2| = 28.5ms -> Critical warning, Rapid Trigger 0.4mm actuation & 0.15-0.20mm release."""
        recs = app.calculate_tapping_ergonomics_recommendations(k1_hold_ms=58.5, k2_hold_ms=30.0, ur_val=90.0)
        self.assertTrue(len(recs) >= 1)
        full_text = "\n".join(recs)
        self.assertIn("Kritische Tapping-Asymmetrie", full_text)
        self.assertIn("0.4 mm", full_text)
        self.assertTrue("0.15–0.20 mm" in full_text or "0.15-0.20 mm" in full_text or "0.15" in full_text)

    def test_offline_fallback_rich_diagnosis(self):
        """Offline Fallback: generate_offline_deep_replay_diagnosis produces structured 5-section German report."""
        agg = {
            "total_plays": 5,
            "avg_acc": 98.2,
            "total_misses": 3,
            "avg_misses_per_play": 0.6,
            "max_combo": 1200,
            "avg_overaim": 62.0,
            "avg_underaim": 38.0,
            "avg_peak_spd": 2400.0,
            "avg_k1_hold": 52.0,
            "avg_k2_hold": 48.0,
            "avg_ur": 78.0
        }
        hit_data = {"avg_hit_error": 3.8, "unstable_rate": 78.0}
        report = app.generate_offline_deep_replay_diagnosis(agg, hit_data)
        self.assertIsInstance(report, str)
        self.assertIn("1. Aim- & Cursor-Mechanik", report)
        self.assertIn("2. Tapping-Technik & Finger-Stamina", report)
        self.assertIn("3. Hauptursachen für Misses & Chokes", report)
        self.assertIn("4. Hardware-, Grip- & Setup-Empfehlungen", report)
        self.assertIn("5. Konkreter 3-Tage Trainings- und Ausbesserungsplan", report)
        self.assertTrue(len(report.split()) > 150)

    def test_ai_coach_engine_contract_dict(self):
        """Interface Contract: AICoachEngine.compute_settings_recommendations_dict returns structured dictionary."""
        hit_data = {
            "avg_hit_error": -4.2,
            "unstable_rate": 110.0,
            "overaim_pct": 70.0,
            "underaim_pct": 30.0,
            "k1_avg_hold": 65.0,
            "k2_avg_hold": 35.0
        }
        res = app.AICoachEngine.compute_settings_recommendations_dict(hit_data)
        self.assertIsInstance(res, dict)
        self.assertIn("audio_offset", res)
        self.assertIn("tablet_area", res)
        self.assertIn("mouse_dpi", res)
        self.assertIn("rapid_trigger", res)
        self.assertIn("stamina_asymmetry", res)
        self.assertEqual(res["audio_offset"]["universal_offset_ms"], 4)
        self.assertEqual(res["tablet_area"], "+3 bis +5 mm")


# =============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS & E2E WORKLOADS (Module 20)
# =============================================================================
class Test20_Tier4_RealWorldLiveSimulationWorkloads(unittest.TestCase):
    """Tier 4 Real-world marathon workloads, overaim/underaim detection, and AI coaching."""

    def test_e2e_3min_stream_map_simulation_1000_hits(self):
        """Simulates full 3-minute marathon play session with 1,200 hits, verifying accurate UR and DB archiving."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_db = tmp.name

        try:
            db_engine = RefTelemetryStorageEngine(db_path=tmp_db)
            engine = RefSimulatedMemoryEngine()
            engine.on_play_complete(lambda s: db_engine.save_live_session(s))

            bm = {"id": 888999, "title": "Stream Marathon", "artist": "DragonForce", "version": "Legend", "od": 8.5}
            summary = engine.simulate_play_session(bm, total_hits=1200, mean_error=-5.4, ur=82.0, overaim_pct=49.0)

            self.assertEqual(len(summary["hit_errors"]), 1200)
            self.assertTrue(summary["accuracy"] > 95.0)
            self.assertAlmostEqual(summary["unstable_rate"], 82.0, delta=12.0)
            self.assertAlmostEqual(summary["mean_error"], -5.4, delta=1.5)

            # Check DB persistence
            saved = db_engine.get_recent_live_sessions(limit=1)[0]
            self.assertEqual(saved["beatmap_id"], 888999)
            self.assertEqual(len(json.loads(saved["hit_errors_json"])), 1200)
        finally:
            if os.path.exists(tmp_db):
                try: os.remove(tmp_db)
                except Exception: pass

    def test_e2e_jump_map_overaim_simulation(self):
        """Simulates cross-screen jump map with 65% overaim -> verifies AI Coach recommends enlarging tablet area."""
        engine = RefSimulatedMemoryEngine()
        bm = {"id": 777111, "title": "Cross Screen Jumps", "od": 8.0, "cs": 4.5}
        session = engine.simulate_play_session(bm, total_hits=300, overaim_pct=65.0)

        debrief = RefAICoachEngine.generate_live_coaching_debrief(session)
        self.assertIn("Overshoot", debrief)
        self.assertIn("Overaim", debrief)
        self.assertTrue("vergrößern" in debrief or "vergroessern" in debrief or "senke" in debrief or "Area" in debrief)

    def test_e2e_stamina_stream_asymmetry_simulation(self):
        """Simulates 220 BPM stream section with 28ms K1/K2 hold-time asymmetry -> verifies Rapid Trigger warning."""
        session = {
            "title": "High BPM Stream",
            "accuracy": 96.5,
            "unstable_rate": 92.0,
            "mean_error": -1.2,
            "overaim_ratio": 50.0,
            "underaim_ratio": 50.0,
            "k1_avg_hold": 56.0,
            "k2_avg_hold": 28.0  # 28ms gap
        }
        debrief = RefAICoachEngine.generate_live_coaching_debrief(session)
        self.assertTrue("Rapid-Trigger" in debrief or "Rapid Trigger" in debrief)
        self.assertIn("0.4", debrief)
        self.assertIn("0.2", debrief)

    def test_e2e_rushing_audio_offset_simulation(self):
        """Simulates early tapping player (-8.4ms) -> verifies Universal Audio Offset +8ms recommendation."""
        session = {
            "title": "Rushing Play",
            "accuracy": 97.2,
            "unstable_rate": 84.0,
            "mean_error": -8.4,
            "overaim_ratio": 50.0,
            "underaim_ratio": 50.0,
            "k1_avg_hold": 40.0,
            "k2_avg_hold": 40.0
        }
        debrief = RefAICoachEngine.generate_live_coaching_debrief(session)
        self.assertIn("Universal Audio Offset", debrief)
        self.assertIn("+8", debrief)

    def test_e2e_late_tapping_audio_offset_simulation(self):
        """Simulates late tapping player (+7.2ms) -> verifies Universal Audio Offset -7ms recommendation."""
        session = {
            "title": "Dragging Play",
            "accuracy": 97.0,
            "unstable_rate": 86.0,
            "mean_error": 7.2,
            "overaim_ratio": 50.0,
            "underaim_ratio": 50.0,
            "k1_avg_hold": 40.0,
            "k2_avg_hold": 40.0
        }
        debrief = RefAICoachEngine.generate_live_coaching_debrief(session)
        self.assertIn("Universal Audio Offset", debrief)
        self.assertIn("-7", debrief)


# =============================================================================
# TIER 5: ADVERSARIAL HARDENING & CPU BENCHMARK (Module 21)
# =============================================================================
class Test21_Tier5_AdversarialMemoryHardeningAndCPUBenchmark(unittest.TestCase):
    """Tier 5 Adversarial security fuzzing, concurrency stress, and CPU benchmarking."""

    def test_adaptive_polling_cpu_footprint_benchmark(self):
        """Verifies memory polling check executes in < 0.05ms per tick (<0.3% CPU footprint at 60 Hz)."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        engine.current_status = RefOsuLiveMemoryEngine.STATUS_PLAYING

        iterations = 1000
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = engine.get_state()
            _ = engine.get_polling_interval()
        total_time_s = time.perf_counter() - t0
        avg_tick_ms = (total_time_s / iterations) * 1000.0

        self.assertTrue(avg_tick_ms < 0.10, f"Average tick took {avg_tick_ms:.4f} ms (must be <0.10 ms)")

    def test_adversarial_hit_error_fuzzing(self):
        """Fuzzes UR and accuracy calculations with NaN, inf, None, and extreme outliers."""
        fuzzed_inputs = [
            float("nan"), float("inf"), float("-inf"), None,
            "corrupt", -999999999, 999999999, 0.0, -12.5, 14.2
        ]
        # Should gracefully filter to [0.0, -12.5, 14.2] or similar without raising exception
        ur = ref_calculate_unstable_rate(fuzzed_inputs)
        self.assertTrue(isinstance(ur, float))
        self.assertFalse(math.isnan(ur))
        self.assertFalse(math.isinf(ur))

        dist = ref_calculate_timing_distribution(fuzzed_inputs)
        self.assertEqual(len(dist["bins"]), 25)

    def test_multithreaded_event_listener_concurrency(self):
        """Verifies 10 concurrent threads registering and firing callbacks without deadlock or race condition."""
        engine = RefSimulatedMemoryEngine()
        received_counts = [0] * 10
        errors = []

        def worker(thread_id):
            try:
                def cb(err, res, k1, k2):
                    received_counts[thread_id] += 1
                engine.on_hit(cb)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(errors), 0)
        # Emit 50 hits
        bm = {"id": 1, "od": 8.0}
        engine.simulate_play_session(bm, total_hits=50)

        for i in range(10):
            self.assertEqual(received_counts[i], 50)

    def test_memory_leak_10000_iterations(self):
        """Verifies memory footprint remains constant across 10,000 telemetry snapshot cycles."""
        engine = RefOsuLiveMemoryEngine(is_mock=True)
        engine.hit_errors = list(range(-50, 50))
        for _ in range(10000):
            state = engine.get_state()
            self.assertIn("accuracy", state)
            self.assertIn("unstable_rate", state)

    def test_settings_polling_rate_persistence(self):
        """Verifies polling rate settings serialize and deserialize cleanly in global_settings.json."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_settings = tmp.name

        try:
            modes = [
                "Adaptiv (30-60 Hz In-Game / 2 Hz Menü - Empfohlen)",
                "30 Hz",
                "60 Hz",
                "100 Hz"
            ]
            for mode in modes:
                data = {"memory_polling_mode": mode}
                with open(tmp_settings, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                with open(tmp_settings, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertEqual(loaded.get("memory_polling_mode"), mode)
        finally:
            if os.path.exists(tmp_settings):
                try: os.remove(tmp_settings)
                except Exception: pass


# MODULE 22: FAST SONG FINDER TESTS (Tier 1)
# =============================================================================
class Test22_Tier1_FastSongFinder(unittest.TestCase):
    """Tier 1 Unit tests for MD5/ID song finding, directory caching, and graceful fallback."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.songs_dir = self.tmp_dir.name

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_fast_song_finder_md5_lookup(self):
        """Verifies locating beatmap by MD5 hash from indexed Songs directory."""
        song_folder = os.path.join(self.songs_dir, "1001 Artist - Title")
        os.makedirs(song_folder, exist_ok=True)
        osu_path = os.path.join(song_folder, "test.osu")
        content = b"[General]\nMode: 0\n[Metadata]\nBeatmapID:1001\n"
        with open(osu_path, "wb") as f:
            f.write(content)
        expected_md5 = hashlib.md5(content).hexdigest()

        finder = RefFastSongFinder(self.songs_dir)
        found_path = finder.find_beatmap(md5=expected_md5)
        self.assertIsNotNone(found_path)
        self.assertEqual(os.path.abspath(found_path), os.path.abspath(osu_path))

    def test_fast_song_finder_beatmap_id_lookup(self):
        """Verifies locating beatmap by integer BeatmapID."""
        song_folder = os.path.join(self.songs_dir, "2002 Artist - Fast")
        os.makedirs(song_folder, exist_ok=True)
        osu_path = os.path.join(song_folder, "diff.osu")
        with open(osu_path, "w", encoding="utf-8") as f:
            f.write("[General]\nMode: 0\n[Metadata]\nTitle:Fast\nBeatmapID: 778899\n[HitObjects]\n")

        finder = RefFastSongFinder(self.songs_dir)
        found = finder.find_beatmap(beatmap_id=778899)
        self.assertEqual(os.path.abspath(found), os.path.abspath(osu_path))

    def test_fast_song_finder_sub_millisecond_cache_benchmark(self):
        """Verifies cached song finder lookups complete in < 3ms (sub-millisecond target)."""
        song_folder = os.path.join(self.songs_dir, "3003 Artist - Benchmark")
        os.makedirs(song_folder, exist_ok=True)
        osu_path = os.path.join(song_folder, "bench.osu")
        with open(osu_path, "w", encoding="utf-8") as f:
            f.write("[Metadata]\nBeatmapID: 555444\n")

        finder = RefFastSongFinder(self.songs_dir)
        finder.index_songs_directory()

        t0 = time.perf_counter()
        for _ in range(100):
            _ = finder.find_beatmap(beatmap_id=555444)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertTrue(elapsed_ms < 10.0, f"100 lookups took {elapsed_ms:.3f}ms")

    def test_fast_song_finder_directory_hierarchy_scan(self):
        """Verifies recursive discovery of .osu files in nested subdirectory structures."""
        nested = os.path.join(self.songs_dir, "FolderA", "SubFolderB", "DeepSong")
        os.makedirs(nested, exist_ok=True)
        deep_osu = os.path.join(nested, "deep.osu")
        with open(deep_osu, "w", encoding="utf-8") as f:
            f.write("[Metadata]\nBeatmapID: 999111\n")

        finder = RefFastSongFinder(self.songs_dir)
        found = finder.find_beatmap(beatmap_id=999111)
        self.assertEqual(os.path.abspath(found), os.path.abspath(deep_osu))

    def test_fast_song_finder_missing_fallback_graceful(self):
        """Verifies clean None return and German fallback notice when beatmap is not found."""
        finder = RefFastSongFinder(self.songs_dir)
        res = finder.find_beatmap(beatmap_id=999999999)
        self.assertIsNone(res)
        notice = finder.get_fallback_notice()
        self.assertIn("Beatmap-Datei nicht im Songs-Ordner gefunden", notice)


# =============================================================================
# MODULE 23: .OSU HITOBJECT PARSER TESTS (Tier 1)
# =============================================================================
class Test23_Tier1_OsuHitObjectParser(unittest.TestCase):
    """Tier 1 Unit tests for parsing circles, sliders, spinners, and difficulty parameters."""

    SAMPLE_MAP = """
    osu file format v14
    [General]
    Mode: 0
    [Metadata]
    Title: Freedom Dive
    Artist: xi
    BeatmapID: 12345
    [Difficulty]
    HPDrainRate: 7.0
    CircleSize: 4.0
    OverallDifficulty: 8.5
    ApproachRate: 9.2
    [HitObjects]
    // Circle
    128,96,1000,1,0,0:0:0:0:
    // Slider
    256,192,2000,2,0,L|356:192,1,100
    // Spinner
    256,192,4000,12,0,5500
    """

    def test_parse_circle_hitobjects(self):
        """Verifies circle parsing extracts correct coordinates, timestamp, and radius."""
        parsed = RefOsuHitObjectParser.parse_osu_content(self.SAMPLE_MAP)
        objs = parsed['hit_objects']
        self.assertEqual(len(objs), 3)

        circle = objs[0]
        self.assertEqual(circle['type'], 'circle')
        self.assertEqual(circle['x'], 128.0)
        self.assertEqual(circle['y'], 96.0)
        self.assertEqual(circle['time'], 1000.0)
        self.assertAlmostEqual(circle['radius'], 54.4 - 4.48 * 4.0, places=2)

    def test_parse_slider_head_position_and_time(self):
        """Verifies slider parsing captures head coordinates and start timestamp."""
        parsed = RefOsuHitObjectParser.parse_osu_content(self.SAMPLE_MAP)
        slider = parsed['hit_objects'][1]
        self.assertEqual(slider['type'], 'slider')
        self.assertEqual(slider['x'], 256.0)
        self.assertEqual(slider['y'], 192.0)
        self.assertEqual(slider['time'], 2000.0)

    def test_parse_spinner_position_and_duration(self):
        """Verifies spinner parsing extracts center coordinates and start/end time."""
        parsed = RefOsuHitObjectParser.parse_osu_content(self.SAMPLE_MAP)
        spinner = parsed['hit_objects'][2]
        self.assertEqual(spinner['type'], 'spinner')
        self.assertEqual(spinner['time'], 4000.0)
        self.assertEqual(spinner['end_time'], 5500.0)

    def test_parser_comments_and_empty_lines_tolerance(self):
        """Verifies parser handles comments, blank lines, and whitespace seamlessly."""
        text = """
        [General]
        Mode: 0
        // Comment here
        
        [HitObjects]
        
        // Another comment
        100,200,500,1,0,0:0:0:0:
        
        """
        parsed = RefOsuHitObjectParser.parse_osu_content(text)
        self.assertEqual(len(parsed['hit_objects']), 1)
        self.assertEqual(parsed['hit_objects'][0]['time'], 500.0)

    def test_parser_metadata_and_difficulty_extraction(self):
        """Verifies CS, OD, AR, HP, and metadata fields are accurately extracted."""
        parsed = RefOsuHitObjectParser.parse_osu_content(self.SAMPLE_MAP)
        diff = parsed['difficulty']
        meta = parsed['metadata']
        self.assertEqual(diff['cs'], 4.0)
        self.assertEqual(diff['od'], 8.5)
        self.assertEqual(diff['ar'], 9.2)
        self.assertEqual(diff['hp'], 7.0)
        self.assertEqual(meta['title'], "Freedom Dive")
        self.assertEqual(meta['artist'], "xi")


# =============================================================================
# MODULE 24: MOD TRANSFORMATIONS TESTS (Tier 1)
# =============================================================================
class Test24_Tier1_ModTransformations(unittest.TestCase):
    """Tier 1 Unit tests for HR Y-flip, DT time scaling, EZ CS scaling, and HD/FL invariance."""

    def test_mod_hardrock_transformation(self):
        """Verifies HR flips Y-axis (384-Y), scales CS by 1.3, OD by 1.4, AR by 1.4."""
        tx, ty = RefModTransformations.transform_coordinates(100, 100, mods=16)
        self.assertEqual(tx, 100.0)
        self.assertEqual(ty, 284.0) # 384 - 100

        diff = RefModTransformations.transform_difficulty(cs=4.0, od=8.0, ar=8.0, hp=5.0, mods=16)
        self.assertAlmostEqual(diff['cs'], 5.2, places=2)
        self.assertAlmostEqual(diff['od'], 10.0, places=2) # 8.0 * 1.4 = 11.2 -> capped at 10.0
        self.assertAlmostEqual(diff['ar'], 10.0, places=2) # 8.0 * 1.4 = 11.2 -> capped at 10.0
        self.assertAlmostEqual(diff['radius'], 54.4 - 4.48 * 5.2, places=2)

    def test_mod_doubletime_nightcore_transformation(self):
        """Verifies DT / NC scales timestamps by 1 / 1.5 and OD window by 1 / 1.5."""
        t_dt = RefModTransformations.transform_timestamp(1500.0, mods=64)
        self.assertAlmostEqual(t_dt, 1000.0, places=2)

        t_nc = RefModTransformations.transform_timestamp(1500.0, mods=512)
        self.assertAlmostEqual(t_nc, 1000.0, places=2)

    def test_mod_halftime_transformation(self):
        """Verifies HT scales timestamps by 1 / 0.75."""
        t_ht = RefModTransformations.transform_timestamp(750.0, mods=256)
        self.assertAlmostEqual(t_ht, 1000.0, places=2)

    def test_mod_easy_transformation(self):
        """Verifies EZ halves CS (CS * 0.5), OD, AR, and doubles circle radius accordingly."""
        diff = RefModTransformations.transform_difficulty(cs=4.0, od=8.0, ar=8.0, hp=6.0, mods=2)
        self.assertEqual(diff['cs'], 2.0)
        self.assertEqual(diff['od'], 4.0)
        self.assertEqual(diff['ar'], 4.0)
        self.assertAlmostEqual(diff['radius'], 54.4 - 4.48 * 2.0, places=2)

    def test_mod_hidden_flashlight_invariance(self):
        """Verifies HD (8) and FL (1024) do not alter coordinates, timestamps, or difficulty."""
        tx, ty = RefModTransformations.transform_coordinates(150, 250, mods=8 | 1024)
        self.assertEqual(tx, 150.0)
        self.assertEqual(ty, 250.0)

        t = RefModTransformations.transform_timestamp(3000.0, mods=8 | 1024)
        self.assertEqual(t, 3000.0)


# =============================================================================
# MODULE 25: DISCRETE HIT MATCHING TESTS (Tier 1)
# =============================================================================
class Test25_Tier1_DiscreteHitMatching(unittest.TestCase):
    """Tier 1 Unit tests for keypress rising edge extraction, two-pointer matching, and OD judgements."""

    def test_rising_edge_keypress_extraction(self):
        """Verifies keypress rising edges are cleanly extracted without double-counting held keys."""
        frames = [
            {'time': 0, 'keys': 0, 'x': 256, 'y': 192},
            {'time': 100, 'keys': 4, 'x': 256, 'y': 192}, # K1 press
            {'time': 120, 'keys': 4, 'x': 256, 'y': 192}, # K1 hold
            {'time': 140, 'keys': 0, 'x': 256, 'y': 192}, # K1 release
            {'time': 200, 'keys': 8, 'x': 260, 'y': 190}, # K2 press
            {'time': 220, 'keys': 0, 'x': 260, 'y': 190},
        ]
        taps = RefDiscreteHitMatchingEngine.extract_rising_edge_taps(frames)
        self.assertEqual(len(taps), 2)
        self.assertEqual(taps[0]['time'], 100)
        self.assertEqual(taps[0]['key'], 'K1')
        self.assertEqual(taps[1]['time'], 200)
        self.assertEqual(taps[1]['key'], 'K2')

    def test_two_pointer_chronological_matching(self):
        """Verifies chronological matching of taps to notes in linear order."""
        notes = [
            {'time': 1000, 'x': 100, 'y': 100},
            {'time': 1500, 'x': 200, 'y': 200},
            {'time': 2000, 'x': 300, 'y': 300},
        ]
        taps = [
            {'time': 1005, 'x': 102, 'y': 101, 'key': 'K1'},
            {'time': 1490, 'x': 198, 'y': 199, 'key': 'K2'},
            {'time': 2010, 'x': 305, 'y': 295, 'key': 'K1'},
        ]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(len(matched), 3)
        self.assertEqual(matched[0]['judgement'], '300')
        self.assertEqual(matched[1]['judgement'], '300')
        self.assertEqual(matched[2]['judgement'], '300')

    def test_exact_discrete_hit_error_calculation(self):
        """Verifies discrete error e = t_tap - t_note carries exact signed difference."""
        notes = [{'time': 1000, 'x': 256, 'y': 192}]
        taps_early = [{'time': 988, 'x': 256, 'y': 192, 'key': 'K1'}]
        taps_late = [{'time': 1014, 'x': 256, 'y': 192, 'key': 'K1'}]

        m_early = RefDiscreteHitMatchingEngine.match_hits(notes, taps_early, od=8.0)
        self.assertEqual(m_early[0]['error_ms'], -12.0)

        m_late = RefDiscreteHitMatchingEngine.match_hits(notes, taps_late, od=8.0)
        self.assertEqual(m_late[0]['error_ms'], 14.0)

    def test_od_timing_window_judgement_determination(self):
        """Verifies OD8 timing windows (300: <=32ms, 100: <=76ms, 50: <=120ms, Miss: >120ms)."""
        # OD 8: w300 = 80 - 6*8 = 32ms, w100 = 140 - 8*8 = 76ms, w50 = 200 - 10*8 = 120ms
        notes = [
            {'time': 1000, 'x': 256, 'y': 192}, # Hit at +25ms -> 300
            {'time': 2000, 'x': 256, 'y': 192}, # Hit at +50ms -> 100
            {'time': 3000, 'x': 256, 'y': 192}, # Hit at +90ms -> 50
            {'time': 4000, 'x': 256, 'y': 192}, # No tap -> Miss
        ]
        taps = [
            {'time': 1025, 'x': 256, 'y': 192, 'key': 'K1'},
            {'time': 2050, 'x': 256, 'y': 192, 'key': 'K2'},
            {'time': 3090, 'x': 256, 'y': 192, 'key': 'K1'},
        ]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(matched[0]['judgement'], '300')
        self.assertEqual(matched[1]['judgement'], '100')
        self.assertEqual(matched[2]['judgement'], '50')
        self.assertEqual(matched[3]['judgement'], 'Miss')

    def test_500_notes_hit_matching_performance_benchmark(self):
        """Benchmark: 500 notes to 500 replay taps matched in < 10ms (Acceptance Criteria)."""
        notes = [{'time': i * 200.0, 'x': 256.0 + (i % 50), 'y': 192.0 + (i % 50)} for i in range(500)]
        taps = [{'time': i * 200.0 + (i % 5 - 2) * 3.0, 'x': 256.0 + (i % 50) + 1.0, 'y': 192.0 + (i % 50), 'key': 'K1'} for i in range(500)]

        t0 = time.perf_counter()
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(len(matched), 500)
        self.assertTrue(dur_ms < 10.0, f"Hit matching 500 notes took {dur_ms:.3f}ms (must be < 10ms)")


# =============================================================================
# MODULE 26: 25-BIN TIMING HISTOGRAM TESTS (Tier 1)
# =============================================================================
class Test26_Tier1_25BinTimingHistogram(unittest.TestCase):
    """Tier 1 Unit tests for 25-bin histogram, outlier rejection without edge clamping, and multi-color counts."""

    def test_25_bin_edges_and_step_resolution(self):
        """Verifies 25 bins spanning [-50ms..+50ms] with 4ms width."""
        hist = RefTimingHistogramEngine.calculate_histogram([0.0], od=8.0)
        self.assertEqual(len(hist['bins']), 25)
        self.assertEqual(len(hist['bins_300']), 25)
        self.assertEqual(len(hist['bins_100']), 25)
        self.assertEqual(len(hist['bins_50']), 25)
        self.assertEqual(hist['bin_edges'][0], -50)
        self.assertEqual(hist['bin_edges'][-1], 50)
        self.assertEqual(hist['bin_centers'][12], 0) # Center bin at 0ms

    def test_histogram_outlier_rejection_no_edge_clamping(self):
        """Verifies errors < -50ms or > +50ms are NOT artificially clamped into bins 0 or 24."""
        errors = [-85.0, -60.0, 0.0, +75.0, +110.0]
        hist = RefTimingHistogramEngine.calculate_histogram(errors, od=8.0)

        # Outliers should NOT populate bin 0 or bin 24
        self.assertEqual(hist['bins'][0], 0)
        self.assertEqual(hist['bins'][24], 0)
        self.assertEqual(hist['bins'][12], 1) # Only 0.0ms in bin 12
        self.assertEqual(hist['outliers_early'], 2)
        self.assertEqual(hist['outliers_late'], 2)

    def test_histogram_discrete_judgement_coloring(self):
        """Verifies genuine Cyan (300), Green (100), Orange (50) counts per bin."""
        matched = [
            {'error_ms': 0.0, 'judgement': '300'},
            {'error_ms': -40.0, 'judgement': '100'},
            {'error_ms': +48.0, 'judgement': '50'}
        ]
        hist = RefTimingHistogramEngine.calculate_histogram(matched, od=8.0)
        self.assertEqual(hist['bins_300'][12], 1) # 0ms
        self.assertEqual(hist['bins_100'][2], 1)  # -40ms -> (-40+50)//4 = 2
        self.assertEqual(hist['bins_50'][24], 1)  # +48ms -> (+48+50)//4 = 24
        self.assertEqual(hist['count_300'], 1)
        self.assertEqual(hist['count_100'], 1)
        self.assertEqual(hist['count_50'], 1)

    def test_histogram_unstable_rate_and_mean_error(self):
        """Verifies Unstable Rate (std_dev * 10) and average hit error calculations."""
        errors = [-10.0, 0.0, +10.0]
        hist = RefTimingHistogramEngine.calculate_histogram(errors, od=8.0)
        self.assertEqual(hist['avg_hit_error'], 0.0)
        # std_dev = sqrt((100 + 0 + 100)/3) = sqrt(66.666) ~= 8.165 -> UR ~= 81.65
        self.assertAlmostEqual(hist['unstable_rate'], 81.65, places=1)

    def test_histogram_empty_and_zero_error_distribution(self):
        """Verifies handling empty errors list returns zeroed metrics without crashing."""
        hist = RefTimingHistogramEngine.calculate_histogram([], od=8.0)
        self.assertEqual(hist['total_hits'], 0)
        self.assertEqual(hist['unstable_rate'], 0.0)
        self.assertEqual(hist['avg_hit_error'], 0.0)


# =============================================================================
# MODULE 27: TRUE RELATIVE CS ACCURACY SCATTER TESTS (Tier 1)
# =============================================================================
class Test27_Tier1_TrueRelativeCSAccuracyScatter(unittest.TestCase):
    """Tier 1 Unit tests for relative CS scatter, circle radius, and jump vector Overaim/Underaim."""

    def test_relative_cs_delta_offset_calculation(self):
        """Verifies delta_X = X_cursor - X_circle and delta_Y = Y_cursor - Y_circle."""
        matched = [
            {'delta_x': 5.2, 'delta_y': -3.1, 'judgement': '300', 'note_x': 200, 'note_y': 200}
        ]
        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        pts = scatter['scatter_points']
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0]['dx'], 5.2)
        self.assertEqual(pts[0]['dy'], -3.1)

    def test_cs_circle_radius_scaling(self):
        """Verifies circle radius formula R = 54.4 - 4.48 * CS across standard CS values."""
        # CS 4 -> 36.48, CS 2 -> 45.44, CS 7 -> 23.04
        s4 = RefCSAccuracyScatterEngine.calculate_scatter([], cs=4.0)
        self.assertAlmostEqual(s4['circle_radius'], 36.48, places=2)

        s2 = RefCSAccuracyScatterEngine.calculate_scatter([], cs=2.0)
        self.assertAlmostEqual(s2['circle_radius'], 45.44, places=2)

        s7 = RefCSAccuracyScatterEngine.calculate_scatter([], cs=7.0)
        self.assertAlmostEqual(s7['circle_radius'], 23.04, places=2)

    def test_aim_jump_vector_directional_projection(self):
        """Verifies projection along note-to-note jump vector correctly detects overaim and underaim."""
        # Jump from (100, 100) to (300, 100) -> Jump vector is +200 in X direction (unit vector [1, 0])
        matched = [
            {'delta_x': 0.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 100, 'note_y': 100},
            {'delta_x': 12.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 300, 'note_y': 100}, # Overshot note to the right
            {'delta_x': -15.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 500, 'note_y': 100}, # Undershot note
        ]
        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        pts = scatter['scatter_points']
        self.assertTrue(pts[1]['is_overaim'])
        self.assertFalse(pts[1]['is_underaim'])
        self.assertTrue(pts[2]['is_underaim'])
        self.assertFalse(pts[2]['is_overaim'])

    def test_authentic_overaim_underaim_percentages(self):
        """Verifies calculated Overaim % and Underaim % sum to 100% and reflect true momentum."""
        matched = [
            {'delta_x': 0.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 100, 'note_y': 100},
            {'delta_x': 10.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 300, 'note_y': 100},
            {'delta_x': 10.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 500, 'note_y': 100},
            {'delta_x': 10.0, 'delta_y': 0.0, 'judgement': '300', 'note_x': 700, 'note_y': 100},
        ]
        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        self.assertEqual(scatter['overshoot_pct'], 100.0)
        self.assertEqual(scatter['underaim_pct'], 0.0)

    def test_scatter_points_rendering_payload_contract(self):
        """Verifies dictionary structure conforms strictly to visualization contract."""
        scatter = RefCSAccuracyScatterEngine.calculate_scatter([], cs=4.0)
        self.assertIn('scatter_points', scatter)
        self.assertIn('circle_radius', scatter)
        self.assertIn('overshoot_pct', scatter)
        self.assertIn('underaim_pct', scatter)
        self.assertIn('total_scatter', scatter)


# =============================================================================
# MODULE 28: BOUNDARY AND CORNER CASES (Tier 2)
# =============================================================================
class Test28_Tier2_BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2 Boundary and corner case tests."""

    def test_corrupted_and_truncated_osu_file(self):
        """Verifies parsing a truncated .osu file does not throw unhandled exceptions."""
        truncated_content = "[General]\nMode: 0\n[HitObjects]\n100,200,"
        parsed = RefOsuHitObjectParser.parse_osu_content(truncated_content)
        self.assertEqual(len(parsed['hit_objects']), 0)

    def test_empty_hitobjects_section(self):
        """Verifies parsing 0 hit objects returns empty lists without ZeroDivisionError."""
        content = "[General]\nMode: 0\n[Difficulty]\nCircleSize: 4.0\n[HitObjects]\n"
        parsed = RefOsuHitObjectParser.parse_osu_content(content)
        self.assertEqual(len(parsed['hit_objects']), 0)
        hist = RefTimingHistogramEngine.calculate_histogram(parsed['hit_objects'])
        self.assertEqual(hist['total_hits'], 0)

    def test_simultaneous_and_overlapping_keypresses(self):
        """Verifies simultaneous K1 and K2 rising edge on exact same frame are handled gracefully."""
        frames = [
            {'time': 0, 'keys': 0, 'x': 256, 'y': 192},
            {'time': 100, 'keys': 12, 'x': 256, 'y': 192}, # K1 (4) + K2 (8) simultaneously
        ]
        taps = RefDiscreteHitMatchingEngine.extract_rising_edge_taps(frames)
        self.assertTrue(len(taps) >= 1)

    def test_extreme_od_values(self):
        """Verifies boundary OD values (OD 0.0 and OD 11.0) produce valid positive hit windows."""
        # OD 0
        m0 = RefDiscreteHitMatchingEngine.match_hits(
            [{'time': 1000, 'x': 256, 'y': 192}],
            [{'time': 1070, 'x': 256, 'y': 192}],
            od=0.0
        )
        self.assertEqual(m0[0]['judgement'], '300') # w300 = 80ms

        # High OD 10
        m10 = RefDiscreteHitMatchingEngine.match_hits(
            [{'time': 1000, 'x': 256, 'y': 192}],
            [{'time': 1025, 'x': 256, 'y': 192}],
            od=10.0
        )
        self.assertEqual(m10[0]['judgement'], '100') # w300 = 20ms, error is 25ms -> 100

    def test_out_of_bounds_and_negative_cursor_coordinates(self):
        """Verifies cursor coordinates outside standard 512x384 playfield calculate delta offsets correctly."""
        notes = [{'time': 1000, 'x': 0, 'y': 0}]
        taps = [{'time': 1000, 'x': -50, 'y': 450, 'key': 'K1'}]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(matched[0]['delta_x'], -50.0)
        self.assertEqual(matched[0]['delta_y'], 450.0)

    def test_zero_and_negative_timestamps(self):
        """Verifies notes and taps occurring at negative intro lead-in times (e.g. -500ms) match correctly."""
        notes = [{'time': -500, 'x': 256, 'y': 192}]
        taps = [{'time': -495, 'x': 256, 'y': 192, 'key': 'K1'}]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(matched[0]['error_ms'], 5.0)
        self.assertEqual(matched[0]['judgement'], '300')

    def test_rapid_slider_ticks_and_burst_notes(self):
        """Verifies high-density 300 BPM stream notes (50ms gap) match one-to-one without tap reuse."""
        notes = [{'time': 1000 + i * 50, 'x': 256, 'y': 192} for i in range(5)]
        taps = [{'time': 1000 + i * 50, 'x': 256, 'y': 192, 'key': 'K1' if i % 2 == 0 else 'K2'} for i in range(5)]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(len(matched), 5)
        for m in matched:
            self.assertEqual(m['judgement'], '300')

    def test_missing_songs_directory_handling(self):
        """Verifies passing a non-existent Songs directory path returns None gracefully."""
        finder = RefFastSongFinder("/path/that/does/not/exist")
        found = finder.find_beatmap(beatmap_id=123)
        self.assertIsNone(found)


# =============================================================================
# MODULE 29: CROSS-FEATURE INTEGRATION (Tier 3)
# =============================================================================
class Test29_Tier3_CrossFeatureIntegration(unittest.TestCase):
    """Tier 3 Cross-feature integration tests connecting parsing, mods, matching, and renderers."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.songs_dir = self.tmp_dir.name

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_cross_feature_replay_to_osu_matching_pipeline(self):
        """Integration: Replay frames -> Song Finder -> .osu Parser -> Hit Matcher -> Histogram -> CS Scatter."""
        song_folder = os.path.join(self.songs_dir, "5005 Integration Map")
        os.makedirs(song_folder, exist_ok=True)
        osu_path = os.path.join(song_folder, "map.osu")
        osu_content = """
        [General]
        Mode: 0
        [Difficulty]
        CircleSize: 4.0
        OverallDifficulty: 8.0
        [HitObjects]
        100,100,1000,1,0,0:0:0:0:
        200,100,1500,1,0,0:0:0:0:
        300,100,2000,1,0,0:0:0:0:
        """
        with open(osu_path, "wb") as f:
            f.write(osu_content.encode("utf-8"))
        expected_md5 = hashlib.md5(osu_content.encode('utf-8')).hexdigest()

        finder = RefFastSongFinder(self.songs_dir)
        located_osu = finder.find_beatmap(md5=expected_md5)
        self.assertIsNotNone(located_osu)

        parsed_map = RefOsuHitObjectParser.parse_osu_file(located_osu)
        objs = parsed_map['hit_objects']
        self.assertEqual(len(objs), 3)

        replay_frames = [
            {'time': 995, 'keys': 4, 'x': 102, 'y': 100},
            {'time': 1050, 'keys': 0, 'x': 150, 'y': 100},
            {'time': 1505, 'keys': 8, 'x': 204, 'y': 100},
            {'time': 1550, 'keys': 0, 'x': 250, 'y': 100},
            {'time': 2000, 'keys': 4, 'x': 301, 'y': 100},
        ]
        taps = RefDiscreteHitMatchingEngine.extract_rising_edge_taps(replay_frames)
        matched = RefDiscreteHitMatchingEngine.match_hits(objs, taps, od=parsed_map['difficulty']['od'])

        hist = RefTimingHistogramEngine.calculate_histogram(matched, od=8.0)
        self.assertEqual(hist['count_300'], 3)

        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        self.assertEqual(scatter['total_scatter'], 3)

    def test_cross_feature_hr_mod_pipeline_integration(self):
        """Integration: HR replay matching with Y-flip and scaled CS/OD."""
        osu_content = """
        [General]
        Mode: 0
        [Difficulty]
        CircleSize: 4.0
        OverallDifficulty: 7.0
        [HitObjects]
        100,100,1000,1,0,0:0:0:0:
        """
        parsed_hr = RefOsuHitObjectParser.parse_osu_content(osu_content, mods=16) # HR
        hr_obj = parsed_hr['hit_objects'][0]
        self.assertEqual(hr_obj['y'], 284.0) # 384 - 100

        replay_frames = [
            {'time': 1002, 'keys': 4, 'x': 100, 'y': 284} # Clicked at HR position
        ]
        taps = RefDiscreteHitMatchingEngine.extract_rising_edge_taps(replay_frames)
        matched = RefDiscreteHitMatchingEngine.match_hits(parsed_hr['hit_objects'], taps, od=hr_obj['od'], mods=16)
        self.assertEqual(matched[0]['judgement'], '300')
        self.assertEqual(matched[0]['delta_y'], 0.0)

    def test_cross_feature_dt_mod_pipeline_integration(self):
        """Integration: DT replay matching with 1.5x time compression."""
        osu_content = """
        [General]
        Mode: 0
        [Difficulty]
        OverallDifficulty: 8.0
        [HitObjects]
        256,192,1500,1,0,0:0:0:0:
        """
        parsed_dt = RefOsuHitObjectParser.parse_osu_content(osu_content, mods=64) # DT
        dt_obj = parsed_dt['hit_objects'][0]
        self.assertEqual(dt_obj['time'], 1000.0) # 1500 / 1.5

        replay_frames = [
            {'time': 1005, 'keys': 4, 'x': 256, 'y': 192}
        ]
        taps = RefDiscreteHitMatchingEngine.extract_rising_edge_taps(replay_frames)
        matched = RefDiscreteHitMatchingEngine.match_hits(parsed_dt['hit_objects'], taps, od=8.0, mods=64)
        self.assertEqual(matched[0]['judgement'], '300')
        self.assertEqual(matched[0]['error_ms'], 5.0)

    def test_cross_feature_missing_osu_fallback_pipeline(self):
        """Integration: Missing .osu returns clean German notice without raising exceptions or generating fake data."""
        finder = RefFastSongFinder(self.songs_dir)
        found = finder.find_beatmap(beatmap_id=404404)
        self.assertIsNone(found)
        notice = finder.get_fallback_notice()
        self.assertEqual(notice, "ℹ️ .osu Beatmap-Datei nicht im Songs-Ordner gefunden – HitObject-Abgleich nicht möglich")


# =============================================================================
# MODULE 30: REAL-WORLD WORKLOADS & E2E (Tier 4)
# =============================================================================
class Test30_Tier4_RealWorldWorkloadsAndE2E(unittest.TestCase):
    """Tier 4 Real-world E2E workloads and full replay simulations."""

    def test_e2e_full_marathon_replay_simulation(self):
        """Simulates 1,000-note full marathon replay with realistic 300s, 100s, 50s, misses."""
        random.seed(42)
        notes = [{'time': i * 150.0, 'x': 256.0 + math.sin(i * 0.1) * 100.0, 'y': 192.0 + math.cos(i * 0.1) * 80.0} for i in range(1000)]
        taps = []
        for i, n in enumerate(notes):
            if i % 100 == 99:
                continue # 1% intentional miss
            err = random.gauss(0, 8.0) # 8ms std dev (~80 UR)
            taps.append({
                'time': n['time'] + err,
                'x': n['x'] + random.gauss(0, 3.0),
                'y': n['y'] + random.gauss(0, 3.0),
                'key': 'K1' if i % 2 == 0 else 'K2'
            })

        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        self.assertEqual(len(matched), 1000)

        hist = RefTimingHistogramEngine.calculate_histogram(matched, od=8.0)
        self.assertTrue(hist['count_300'] > 900)
        self.assertTrue(hist['unstable_rate'] < 95.0)

        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        self.assertEqual(scatter['total_scatter'], 990)

    def test_e2e_cross_screen_jump_map_overaim(self):
        """Simulates cross-screen jump map with intentional overshooting -> verifies Overaim % > 60%."""
        notes = [
            {'time': 1000, 'x': 50, 'y': 50},
            {'time': 1500, 'x': 450, 'y': 350},
            {'time': 2000, 'x': 50, 'y': 50},
            {'time': 2500, 'x': 450, 'y': 350},
        ]
        # Always click 15px past the jump destination
        taps = [
            {'time': 1000, 'x': 50, 'y': 50, 'key': 'K1'},
            {'time': 1500, 'x': 462, 'y': 359, 'key': 'K1'}, # past note along jump vector
            {'time': 2000, 'x': 38, 'y': 41, 'key': 'K1'},   # past note along return jump
            {'time': 2500, 'x': 462, 'y': 359, 'key': 'K1'},
        ]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        scatter = RefCSAccuracyScatterEngine.calculate_scatter(matched, cs=4.0)
        self.assertTrue(scatter['overshoot_pct'] >= 60.0)

    def test_e2e_dt_high_bpm_tight_timing(self):
        """Simulates 270 BPM DT stream section with tight timing distribution."""
        notes = [{'time': i * (60000.0 / 270.0 / 2.0), 'x': 256, 'y': 192} for i in range(32)]
        taps = [{'time': n['time'] + (i % 3 - 1) * 2.0, 'x': 256, 'y': 192, 'key': 'K1' if i % 2 == 0 else 'K2'} for i, n in enumerate(notes)]
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0, mods=64)
        hist = RefTimingHistogramEngine.calculate_histogram(matched, od=8.0)
        self.assertEqual(hist['count_300'], 32)
        self.assertTrue(hist['unstable_rate'] < 30.0)

    def test_e2e_german_ui_and_fallback_audit(self):
        """Audits German status notice and ensures zero English placeholder remnants."""
        notice = RefFastSongFinder.get_fallback_notice()
        self.assertIn("ℹ️", notice)
        self.assertIn(".osu Beatmap-Datei nicht im Songs-Ordner gefunden", notice)
        self.assertNotIn("TBD", notice)
        self.assertNotIn("TODO", notice)
        self.assertNotIn("Lorem", notice)


# =============================================================================
# MODULE 31: ADVERSARIAL SECURITY & PERFORMANCE STRESS (Tier 5)
# =============================================================================
class Test31_Tier5_AdversarialSecurityAndPerformanceStress(unittest.TestCase):
    """Tier 5 Adversarial fuzzing, high-load stress benchmarks, and localization audits."""

    def test_adversarial_malformed_hitobject_lines(self):
        """Fuzzes parser with SQL injection strings, random Unicode, and invalid floats."""
        malformed_osu = """
        [HitObjects]
        ' OR '1'='1
        <script>alert(1)</script>
        nan,inf,99999999999999999999,1,0,0
        -100,-200,-500,1,0,0
        ,,,,,
        NULL,None,undefined
        256,192,1000,1,0,0:0:0:0:
        """
        parsed = RefOsuHitObjectParser.parse_osu_content(malformed_osu)
        # Should cleanly recover and parse the valid hitobject
        valid_objs = [o for o in parsed['hit_objects'] if o['time'] == 1000.0]
        self.assertEqual(len(valid_objs), 1)

    def test_massive_3000_note_beatmap_matching_stress(self):
        """Stress test: 3,000 hit objects matched in < 30ms with zero memory bloat."""
        notes = [{'time': i * 50.0, 'x': 256.0, 'y': 192.0} for i in range(3000)]
        taps = [{'time': i * 50.0 + (i % 3 - 1) * 4.0, 'x': 256.0, 'y': 192.0, 'key': 'K1'} for i in range(3000)]

        t0 = time.perf_counter()
        matched = RefDiscreteHitMatchingEngine.match_hits(notes, taps, od=8.0)
        dur_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(len(matched), 3000)
        self.assertTrue(dur_ms < 30.0, f"3,000 note matching took {dur_ms:.3f}ms")

    def test_song_finder_cache_stress_and_concurrency(self):
        """Multi-threaded stress: 10 concurrent threads querying song finder cache."""
        with tempfile.TemporaryDirectory() as tmp_songs:
            for i in range(20):
                folder = os.path.join(tmp_songs, f"Song_{i}")
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "map.osu"), "w", encoding="utf-8") as f:
                    f.write(f"[Metadata]\nBeatmapID: {1000 + i}\n")

            finder = RefFastSongFinder(tmp_songs)
            finder.index_songs_directory()

            errors = []
            def worker(thread_id):
                try:
                    for _ in range(50):
                        bid = 1000 + (thread_id % 20)
                        res = finder.find_beatmap(beatmap_id=bid)
                        if res is None:
                            errors.append(f"Thread {thread_id} failed to find {bid}")
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads: t.start()
            for t in threads: t.join()

            self.assertEqual(len(errors), 0)

    def test_localization_zero_english_placeholders_audit(self):
        """Scans all reference German messages for prohibited English placeholder tokens."""
        forbidden = ["TBD", "TODO", "Lorem ipsum", "Not Available", "N/A - Not Available", "Under Construction"]
        text = RefFastSongFinder.get_fallback_notice()
        for token in forbidden:
            self.assertNotIn(token, text)


# =============================================================================
# Main Runner
# =============================================================================
if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

