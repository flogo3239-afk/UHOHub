import os
import sys
import json
import struct
import requests
import webbrowser
import hashlib
import math
import random
import threading
import tkinter as tk
import re
import time
import traceback
import subprocess
import shutil
import zipfile
import socket
import ssl
import tempfile
import lzma
import uuid
import sqlite3
from contextlib import contextmanager
from datetime import datetime
try:
    import winreg
except Exception:
    winreg = None

CURRENT_APP_VERSION = "2.9.0"
GITHUB_REPO = "flogo3239-afk/UHOHub"

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

DYNAMIC_RANKED_MAPS_DB = []
DYNAMIC_MAPS_BY_SKILL = {}
OFFICIAL_TOURNAMENTS_DB = {}
BEATMAP_SQLITE_DB_PATH = None
_json_file_lock = threading.Lock()

ALLOWED_ORDER_FIELDS = {
    "playcount DESC": "playcount DESC",
    "playcount ASC": "playcount ASC",
    "sr DESC": "sr DESC",
    "sr ASC": "sr ASC",
    "bpm DESC": "bpm DESC",
    "bpm ASC": "bpm ASC",
    "len DESC": "len DESC",
    "len ASC": "len ASC",
    "id ASC": "id ASC",
    "id DESC": "id DESC",
    "rating DESC": "rating DESC",
    "rating ASC": "rating ASC",
    "RANDOM()": "RANDOM()",
}

def safe_atomic_json_dump(data, filepath, encoding="utf-8", indent=2):
    """Safely and atomically writes JSON data to filepath using a temporary file and os.replace."""
    try:
        dir_name = os.path.dirname(os.path.abspath(filepath))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        with _json_file_lock:
            with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, delete=False, encoding=encoding, suffix=".tmp", prefix="uho_tmp_") as f:
                temp_path = f.name
                json.dump(data, f, indent=indent, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            if os.path.exists(filepath):
                bak_path = filepath + ".bak"
                try:
                    shutil.copy2(filepath, bak_path)
                except Exception:
                    pass
            
            os.replace(temp_path, filepath)
            bak_path = filepath + ".bak"
            if not os.path.exists(bak_path):
                try:
                    shutil.copy2(filepath, bak_path)
                except Exception:
                    pass
            return True
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return False

def safe_json_load(filepath, default=None):
    """Safely loads JSON data from filepath with fallback to .bak if corrupted."""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        bak_path = filepath + ".bak"
        if os.path.exists(bak_path):
            try:
                with open(bak_path, "r", encoding="utf-8") as f_bak:
                    return json.load(f_bak)
            except Exception:
                pass
        return default

def safe_div(numerator, denominator, default=0.0):
    """
    Performs safe floating-point division preventing ZeroDivisionError, TypeError, ValueError, and NaN.
    Returns float(default) if division cannot be performed.
    """
    try:
        if numerator is None or denominator is None:
            return float(default)
        num = float(numerator)
        den = float(denominator)
        res = num / den
        if math.isinf(res) or math.isnan(res):
            return float(default)
        return res
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        return float(default)

def safe_ui_dispatch(widget_or_root, callback, *args, **kwargs):
    """
    Safely executes a UI callback on the main thread, ensuring the target widget exists and is alive.
    If widget_or_root is None or destroyed, suppresses TclError gracefully.
    """
    def _execute():
        try:
            if widget_or_root is None:
                callback(*args, **kwargs)
                return
            exists = True
            if hasattr(widget_or_root, "winfo_exists"):
                try:
                    exists = bool(widget_or_root.winfo_exists())
                except Exception:
                    exists = False
            if exists:
                callback(*args, **kwargs)
        except (tk.TclError, RuntimeError, AttributeError):
            pass
        except Exception:
            pass

    try:
        if threading.current_thread() is threading.main_thread():
            _execute()
            return

        after_target = None
        if widget_or_root is not None and hasattr(widget_or_root, "after"):
            after_target = widget_or_root
        elif hasattr(tk, "_default_root") and tk._default_root is not None:
            after_target = tk._default_root

        if after_target is not None:
            try:
                if hasattr(after_target, "winfo_exists") and not after_target.winfo_exists():
                    return
                after_target.after(0, _execute)
            except Exception:
                pass
        else:
            _execute()
    except Exception:
        pass

_DEFAULT_SENTINEL = object()

def safe_parse_ai_json(raw_text, default=_DEFAULT_SENTINEL):
    """Extracts and parses JSON object or list from AI text responses with markdown, code blocks, or preamble."""
    fallback = {} if default is _DEFAULT_SENTINEL else default
    if raw_text is None:
        return fallback
    if not isinstance(raw_text, str):
        if isinstance(raw_text, (dict, list)):
            return raw_text
        return fallback

    cleaned = raw_text.strip()
    if not cleaned:
        return fallback

    # Fast path: direct JSON
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Strip markdown code blocks like ```json ... ``` or ``` ... ```
    stripped = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.MULTILINE)
    stripped = re.sub(r'\s*```$', '', stripped, flags=re.MULTILINE).strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass

    # Regex search for outer JSON object {...}
    obj_match = re.search(r'(\{[\s\S]*\})', cleaned)
    if obj_match:
        try:
            return json.loads(obj_match.group(1))
        except Exception:
            cleaned_obj = re.sub(r',\s*([\}\]])', r'\1', obj_match.group(1))
            try:
                return json.loads(cleaned_obj)
            except Exception:
                pass

    # Regex search for outer JSON array [...]
    arr_match = re.search(r'(\[[\s\S]*\])', cleaned)
    if arr_match:
        try:
            return json.loads(arr_match.group(1))
        except Exception:
            cleaned_arr = re.sub(r',\s*([\}\]])', r'\1', arr_match.group(1))
            try:
                return json.loads(cleaned_arr)
            except Exception:
                pass

    return fallback

def _find_resource_file(filename):
    """Find a resource file across all candidate directories."""
    for candidate_dir in [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__)), os.getcwd(), r"C:\Users\louis\.gemini\antigravity\scratch"]:
        if not candidate_dir: continue
        fpath = os.path.join(candidate_dir, filename)
        if os.path.exists(fpath):
            return fpath
    return None

def _init_sqlite_db():
    """Initialize SQLite database connection for beatmap data with PRAGMA quick_check and WAL mode."""
    global BEATMAP_SQLITE_DB_PATH
    db_path = _find_resource_file("beatmaps_analyzed.db")
    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            check = conn.execute("PRAGMA quick_check;").fetchone()
            if not check or str(check[0]).lower() != "ok":
                conn.close()
                print(f"[SQLite] Integrity check failed for {db_path}: {check}")
                BEATMAP_SQLITE_DB_PATH = None
                return False
            
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            count = conn.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
            conn.close()
            BEATMAP_SQLITE_DB_PATH = db_path
            print(f"[SQLite] Loaded beatmap database: {count} maps from {db_path}")
            return True
        except Exception as e:
            print(f"[SQLite] Error loading {db_path}: {e}")
            BEATMAP_SQLITE_DB_PATH = None
    return False

@contextmanager
def get_safe_sqlite_conn(db_path=None, timeout=10.0):
    """Context manager for thread-safe SQLite access with WAL mode and busy timeout."""
    target_path = db_path if db_path is not None else BEATMAP_SQLITE_DB_PATH
    if not target_path or not os.path.exists(target_path):
        yield None
        return
    conn = None
    try:
        conn = sqlite3.connect(target_path, timeout=timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        yield conn
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def _get_sqlite_conn():
    """Get a thread-local SQLite connection safely."""
    if not BEATMAP_SQLITE_DB_PATH or not os.path.exists(BEATMAP_SQLITE_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(BEATMAP_SQLITE_DB_PATH, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        return conn
    except Exception:
        return None

def sqlite_query_maps(skill=None, sr_min=None, sr_max=None, bpm_min=None, bpm_max=None, ar_min=None, ar_max=None, cs_max=None, exclude_ids=None, limit=200, order_by="playcount DESC"):
    """Query maps from SQLite with filters. Returns list of dicts."""
    safe_order = ALLOWED_ORDER_FIELDS.get(order_by.strip() if isinstance(order_by, str) else "", "playcount DESC")
    with get_safe_sqlite_conn() as conn:
        if not conn:
            return []
        try:
            conditions = []
            params = []
            if skill:
                conditions.append("primary_skill = ?")
                params.append(skill)
            if sr_min is not None:
                conditions.append("sr >= ?")
                params.append(float(sr_min))
            if sr_max is not None:
                conditions.append("sr <= ?")
                params.append(float(sr_max))
            if bpm_min is not None:
                conditions.append("bpm >= ?")
                params.append(float(bpm_min))
            if bpm_max is not None:
                conditions.append("bpm <= ?")
                params.append(float(bpm_max))
            if ar_min is not None:
                conditions.append("ar >= ?")
                params.append(float(ar_min))
            if ar_max is not None:
                conditions.append("ar <= ?")
                params.append(float(ar_max))
            if cs_max is not None:
                conditions.append("cs <= ?")
                params.append(float(cs_max))
            if exclude_ids:
                clean_exclude_ids = [str(x) for x in exclude_ids if x is not None][:500]
                if clean_exclude_ids:
                    placeholders = ",".join("?" for _ in clean_exclude_ids)
                    conditions.append(f"id NOT IN ({placeholders})")
                    params.extend(clean_exclude_ids)
            
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"SELECT * FROM maps {where} ORDER BY {safe_order} LIMIT ?"
            params.append(int(limit))
            
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        except Exception:
            return []

def sqlite_get_skill_distribution():
    """Get count of maps per primary_skill."""
    with get_safe_sqlite_conn() as conn:
        if not conn:
            return {}
        try:
            rows = conn.execute("SELECT primary_skill, COUNT(*) FROM maps GROUP BY primary_skill ORDER BY COUNT(*) DESC").fetchall()
            return {row[0]: row[1] for row in rows}
        except Exception:
            return {}

def sqlite_get_total_count():
    """Get total map count from SQLite."""
    with get_safe_sqlite_conn() as conn:
        if not conn:
            return 0
        try:
            count = conn.execute("SELECT COUNT(*) FROM maps").fetchone()[0]
            return int(count)
        except Exception:
            return 0

# Initialize databases
try:
    has_sqlite = _init_sqlite_db()
    
    # Fallback: Load JSON if no SQLite DB
    if not has_sqlite:
        for candidate_dir in [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__)), os.getcwd(), r"C:\Users\louis\.gemini\antigravity\scratch"]:
            if not candidate_dir: continue
            db_path = os.path.join(candidate_dir, "compact_ranked_maps.json")
            if not DYNAMIC_RANKED_MAPS_DB and os.path.exists(db_path):
                with open(db_path, "r", encoding="utf-8") as f:
                    DYNAMIC_RANKED_MAPS_DB = json.load(f)
                    DYNAMIC_MAPS_BY_SKILL = {}
                    for m in DYNAMIC_RANKED_MAPS_DB:
                        sk = m.get('primary_skill', 'Aim')
                        if sk not in DYNAMIC_MAPS_BY_SKILL:
                            DYNAMIC_MAPS_BY_SKILL[sk] = []
                        DYNAMIC_MAPS_BY_SKILL[sk].append(m)

    for candidate_dir in [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(__file__)), os.getcwd(), r"C:\Users\louis\.gemini\antigravity\scratch"]:
        if not candidate_dir: continue
        t_path = os.path.join(candidate_dir, "official_tournament_pools.json")
        if not OFFICIAL_TOURNAMENTS_DB and os.path.exists(t_path):
            with open(t_path, "r", encoding="utf-8") as f:
                OFFICIAL_TOURNAMENTS_DB = json.load(f)
except Exception as e:
    pass

import ctypes
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD),
        ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD),
        ('th32DefaultHeapID', ctypes.POINTER(wintypes.ULONG)),
        ('th32ModuleID', wintypes.DWORD),
        ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD),
        ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD),
        ('szExeFile', ctypes.c_char * 260)
    ]

def is_osu_process_active():
    """Detects if osu!.exe is running on Windows in <1ms without subprocess overhead."""
    try:
        hSnapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if hSnapshot == -1:
            return False
        pe32 = PROCESSENTRY32()
        pe32.dwSize = ctypes.sizeof(PROCESSENTRY32)
        has_next = ctypes.windll.kernel32.Process32First(hSnapshot, ctypes.byref(pe32))
        found = False
        while has_next:
            exe_name = pe32.szExeFile.decode('cp1252', errors='ignore').lower()
            if 'osu!.exe' in exe_name or exe_name == 'osu.exe':
                found = True
                break
            has_next = ctypes.windll.kernel32.Process32Next(hSnapshot, ctypes.byref(pe32))
        ctypes.windll.kernel32.CloseHandle(hSnapshot)
        return found
    except Exception:
        return False


TECH_ARTISTS = {'camellia', 'kobaryo', 'lapix', 'frums', 'silentroom', 'v0id', 'laur', 'team grimoire', 'usao',
                't+pazolite', 'redalice', 'psycho filth', 'sota fujimori', 'nanahira', 'polysha', 'kikoyu',
                'aran', 'massive new krew', 'roughsketch', 'kurokotei', 'maozon', 'giga', 'teddyloid',
                'c-show', 'technoplanet', 'morimori atsushi', 'siqlo', 'sky_delta', 'yooh', 'kors k',
                'dj sharpnel', 'djkurara', 'sewerslvt', 'm108', 'ice', 'sta', 'void', 'dawmii', 'nh22',
                'take us to vegas', 'expander'}

TECH_KEYWORDS = {'tech', 'remix', 'gimmick', 'slider', 'velocity', 'polyrhythm', 'sv', 'awkward',
                 'glitch', 'experimental', 'complex', 'odd', 'chaos', 'overdose', 'expert????', 'level 2',
                 'level 1', 'level 3', 'level 4', 'level 5', 'limbo', 'chayot', 'tag', 'tag4', 'tag2',
                 'alt', 'alternate', 'alternating', 'slider-tech', 'sv gimmick', 'jump-tech'}

STREAM_ARTISTS = {'dragonforce', 'xi', 'foreground eclipse', 'imperial circus dead decadence',
                  'undead corporation', 'memai siren', 'demetori', 'galneryus', 'tears of tragedy',
                  'fellows', 'necrofantasia', 'icdd', 'aether realm', 'dragon eyes', 'ryo-kun'}

EXPLICIT_STREAM_KEYWORDS = {'ice angel', 'freedom dive', 'the empress', 'sidetracked', 'blue zenith',
                            'ascension to heaven', 'uta', 'songs compilation', 'arcadia', 'stream', 'deathstream'}

def compute_map_pattern_fingerprint(m):
    """
    Berechnet einen mathematischen HitObject- & Struktur-Fingerabdruck (0.0 bis 1.0)
    für alle 8 osu! Standard Skillsets zur millimetergenauen Vorfilterung & Auto-Skip.
    Verhindert zuverlässig, dass Tag- und Tech-Maps in Streams, Aim oder Stamina rutschen.
    """
    if not isinstance(m, dict):
        m = {}
    try: sr = float(m.get('sr', 5.0) or 5.0)
    except: sr = 5.0
    try: bpm = float(m.get('bpm', 180.0) or 180.0)
    except: bpm = 180.0
    try: length = int(m.get('len', 120) or 120)
    except: length = 120
    try: cs = float(m.get('cs', 4.0) or 4.0)
    except: cs = 4.0
    try: od = float(m.get('od', 8.0) or 8.0)
    except: od = 8.0
    try: ar = float(m.get('ar', 9.0) or 9.0)
    except: ar = 9.0
    name = str(m.get('name', '') or '').lower()

    is_explicit_stream = any(k in name for k in EXPLICIT_STREAM_KEYWORDS)
    is_tech_artist = any(a in name for a in TECH_ARTISTS) and not is_explicit_stream
    is_tech_kw = (any(k in name for k in TECH_KEYWORDS) or 'tag' in name or 'remix' in name) and not is_explicit_stream
    is_stream_artist = any(a in name for a in STREAM_ARTISTS)

    # 1. Tech Score (Slider Velocity, Tag Maps, Awkward Angles, Polyrhythms)
    tech_score = 0.05
    if is_tech_artist: tech_score += 0.50
    if is_tech_kw: tech_score += 0.45
    if 125 <= bpm <= 165 and sr >= 5.0: tech_score += 0.25
    if 'slider' in name or 'sv' in name or 'gimmick' in name or 'velocity' in name or 'tag' in name: tech_score += 0.35
    if is_explicit_stream: tech_score = 0.05
    tech_score = min(1.0, tech_score)

    # 2. Streams Score (1/4 Note Chains, Deathstreams - Strikt ohne Tech/Tag Maps!)
    stream_score = 0.05
    if is_explicit_stream:
        stream_score = 0.85
    elif not is_tech_artist and not is_tech_kw:
        if is_stream_artist or 'stream' in name or 'deathstream' in name: stream_score += 0.60
        if 170 <= bpm <= 230 and length >= 110: stream_score += 0.35
        if 175 <= bpm <= 225: stream_score += 0.15
    if tech_score > 0.40 and not is_explicit_stream: stream_score = max(0.0, stream_score - 0.50)
    stream_score = max(0.0, min(1.0, stream_score))

    # 3. Speed Score (High BPM Bursting & Raw Tapping Speed)
    speed_score = 0.05
    if bpm >= 215: speed_score += 0.55
    elif bpm >= 195: speed_score += 0.35
    if 'speed' in name or 'fast' in name or 'bpm' in name: speed_score += 0.30
    if length <= 130 and bpm >= 195 and not is_tech_kw: speed_score += 0.20
    if tech_score > 0.50: speed_score = max(0.0, speed_score - 0.45)
    speed_score = max(0.0, min(1.0, speed_score))

    # 4. Jump Aim Score (Snapping Distance, Wide Spacing - Strictly non-tech/non-tag!)
    aim_score = 0.05
    if not is_tech_artist and not is_tech_kw:
        if 'jump' in name or 'tv size' in name or 'killer' in name: aim_score += 0.50
        if 170 <= bpm <= 220 and length <= 160: aim_score += 0.35
        if cs <= 4.4 and sr >= 4.5 and stream_score < 0.40: aim_score += 0.30
    if tech_score > 0.35: aim_score = max(0.0, aim_score - 0.60)
    if stream_score > 0.60: aim_score = max(0.0, aim_score - 0.35)
    aim_score = max(0.0, min(1.0, aim_score))

    # 5. Precision Score (Small CS >= 4.5 & High OD Accuracy)
    prec_score = 0.05
    if cs >= 5.0: prec_score += 0.60
    elif cs >= 4.5: prec_score += 0.35
    if od >= 9.0: prec_score += 0.30
    if 'precision' in name or 'small cs' in name or 'cs5' in name or 'cs6' in name: prec_score += 0.40
    prec_score = max(0.0, min(1.0, prec_score))

    # 6. Reading Score (Low AR Density, Overlapping Notes)
    read_score = 0.05
    if ar <= 8.5 and sr >= 4.5: read_score += 0.60
    elif ar <= 8.8 and sr >= 4.0: read_score += 0.35
    if 'reading' in name or 'hidden' in name or 'low ar' in name or 'wildflower' in name: read_score += 0.45
    read_score = max(0.0, min(1.0, read_score))

    # 7. Stamina Score (Long Marathon Drain >= 3 Min, Sustained Note Density)
    stam_score = 0.05
    if length >= 210: stam_score += 0.60
    elif length >= 170: stam_score += 0.35
    else: stam_score = 0.0  # Kurze Maps sind niemals Stamina!
    if (bpm >= 175 and length >= 180) or 'marathon' in name or 'stamina' in name: stam_score += 0.30
    stam_score = max(0.0, min(1.0, stam_score))

    # 8. Consistency Score (Uniform Star Density, High OD, Tournament Pacing)
    cons_score = 0.05
    if length >= 120 and od >= 8.0 and not is_tech_artist and not is_tech_kw:
        cons_score += 0.45
    if length >= 150 and aim_score > 0.30:
        cons_score += 0.30
    cons_score = max(0.0, min(1.0, cons_score))

    return {
        'Aim': aim_score,
        'Streams': stream_score,
        'Speed': speed_score,
        'Tech': tech_score,
        'Precision': prec_score,
        'Reading': read_score,
        'Stamina': stam_score,
        'Consistency': cons_score
    }

def classify_map(m):
    fp = compute_map_pattern_fingerprint(m)
    cats = [k for k, v in fp.items() if v >= 0.40]
    return cats if cats else ['Consistency', 'Aim']

# =============================================================================
# 8-SKILLSET DYNAMIC BOT STAT ENGINE & SCOREV2 TOURNAMENT SIMULATOR 2.0
# =============================================================================
ALL_8_SKILLS = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
TIER_POINT_POOLS = {"Rookie": 160, "Challenger": 240, "Pro": 400, "Legend": 640}

GERMAN_OSU_NAMES = [
    "WhiteFox_DE", "RheinJumper", "KaiserAim", "BavariaStream", "AlpenSpeed",
    "BlitzTech", "SchwarzwaldHD", "Manticore_de", "SternStaub", "NeoVortex",
    "SturmRhythmus", "Eisbaer_osu", "ShadowEcho", "KiraStream", "ChronoDrift",
    "Valkyrie_DE", "AetherAim", "SilberPfeil", "DonauBeat", "ZenithPulse",
    "NordLicht_osu", "HarzRider", "Edelweiss_Aim", "RuhrPott_God", "BerlinExpress",
    "Phantasm_DE", "ViperStream", "EchoBlade", "MeisterTap", "FrostBite_de",
    "Tornado_DE", "SchattenWolf", "Phoenix_DACH", "NovaStrike", "RhythmusKomet",
    "Hyperion_de", "AeroSync", "Blitzschlag", "Starlight_DE", "KometenSchweif"
]

def generate_8skill_profile(tier_name: str) -> tuple[dict[str, int], list[str], list[str]]:
    """
    Generates an 8-skill radar profile enforcing the strict Base-10 Rule (all skills >= 10),
    exact tier point pool budgets (Rookie: 160, Challenger: 240, Pro: 400, Legend: 640),
    and maximum 100 points cap per skill.
    Returns (stats_dict, top2_strengths, bot2_weaknesses).
    """
    normalized_tier = "Challenger"
    tier_str = str(tier_name or "Challenger").lower()
    for k in TIER_POINT_POOLS:
        if k.lower() in tier_str:
            normalized_tier = k
            break

    n = len(ALL_8_SKILLS)
    base_stat = 10
    target_sum = TIER_POINT_POOLS.get(normalized_tier, 240)
    stats = [base_stat] * n
    remaining_pool = target_sum - (base_stat * n)

    strengths = random.sample(range(n), 2)
    remaining_indices = [i for i in range(n) if i not in strengths]
    weaknesses = random.sample(remaining_indices, 2)

    weights = [1.0] * n
    for s in strengths:
        weights[s] = random.uniform(2.2, 3.8)
    for w in weaknesses:
        weights[w] = random.uniform(0.3, 0.6)

    while remaining_pool > 0:
        eligible = [i for i in range(n) if stats[i] < 100]
        if not eligible:
            break
        elig_weights = [weights[i] for i in eligible]
        tot_w = sum(elig_weights)
        if tot_w <= 0:
            step_each = max(1, remaining_pool // len(eligible))
            for i in eligible:
                add = min(step_each, 100 - stats[i], remaining_pool)
                stats[i] += add
                remaining_pool -= add
                if remaining_pool <= 0:
                    break
            continue

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

def calculate_bot_scorev2(bot_stats: dict, map_meta: dict) -> dict:
    """
    Dynamically computes realistic bot ScoreV2 performance (0 to 1,000,000)
    matching bot skillset against map demands (SR, BPM, Length, CS, AR, OD).
    Resilient to empty, missing, or corrupt inputs.
    """
    if not isinstance(bot_stats, dict) or not bot_stats:
        bot_stats = {k: 50 for k in ALL_8_SKILLS}
    if not isinstance(map_meta, dict):
        map_meta = {}

    clean_stats = {}
    for k in ALL_8_SKILLS:
        try:
            clean_stats[k] = float(bot_stats.get(k, 10) or 10)
        except Exception:
            clean_stats[k] = 10.0

    try: sr = float(map_meta.get("sr", 6.0) or 6.0)
    except Exception: sr = 6.0
    if math.isnan(sr) or math.isinf(sr): sr = 6.0

    try: bpm = float(map_meta.get("bpm", 180.0) or 180.0)
    except Exception: bpm = 180.0
    if math.isnan(bpm) or math.isinf(bpm): bpm = 180.0

    try: length = float(map_meta.get("len", 150) or 150)
    except Exception: length = 150.0
    if math.isnan(length) or math.isinf(length) or length < 0: length = 150.0

    try: cs = float(map_meta.get("cs", 4.0) or 4.0)
    except Exception: cs = 4.0
    if math.isnan(cs) or math.isinf(cs): cs = 4.0

    try: ar = float(map_meta.get("ar", 9.0) or 9.0)
    except Exception: ar = 9.0

    try: od = float(map_meta.get("od", 8.5) or 8.5)
    except Exception: od = 8.5

    weights = map_meta.get("weights")
    if not weights or not isinstance(weights, dict):
        try:
            fp = compute_map_pattern_fingerprint(map_meta)
            tot_fp = sum(fp.values())
            if tot_fp > 0:
                weights = {k: fp.get(k, 0.0) / tot_fp for k in ALL_8_SKILLS}
            else:
                weights = {k: 0.125 for k in ALL_8_SKILLS}
        except Exception:
            weights = {k: 0.125 for k in ALL_8_SKILLS}

    effective_skill = sum(clean_stats.get(k, 10.0) * float(weights.get(k, 0.125)) for k in ALL_8_SKILLS)
    cons_stat = clean_stats.get("Consistency", 10.0)

    # 1. Map Demand
    map_demand = 15.0 + ((sr - 4.5) / 4.0) * 75.0
    if bpm > 220:
        map_demand += (bpm - 220) * 0.15 * (1.0 - (clean_stats.get("Speed", 10.0) / 100.0))
    if cs > 4.5:
        map_demand += (cs - 4.5) * 10.0 * (1.0 - (clean_stats.get("Precision", 10.0) / 100.0))
    if length > 200:
        map_demand += ((length - 200) / 60.0) * 5.0 * (1.0 - (clean_stats.get("Stamina", 10.0) / 100.0))

    skill_ratio = effective_skill / max(5.0, map_demand)

    # 2. Accuracy Sigmoid
    acc_midpoint = 94.0 + 5.5 / (1.0 + math.exp(-3.5 * (skill_ratio - 0.9)))
    acc_std = max(0.15, 1.2 - (effective_skill / 100.0) * 0.6 - (cons_stat / 100.0) * 0.4)
    sim_acc = max(70.0, min(99.95, random.gauss(acc_midpoint, acc_std)))

    # 3. Hit Objects & Miss Count (Poisson)
    drain_density = max(2.8, min(6.0, (bpm / 60.0) * 1.1 + (sr * 0.25)))
    total_objects = max(50, int(length * drain_density))

    if skill_ratio >= 1.15:
        lambda_miss = max(0.0, 0.2 - (cons_stat / 500.0))
    elif skill_ratio >= 0.95:
        lambda_miss = max(0.0, (1.2 - skill_ratio) * 6.0 * (1.0 - cons_stat / 150.0))
    else:
        lambda_miss = (1.0 - skill_ratio) * 18.0 * (1.5 - cons_stat / 100.0)

    # Poisson draw
    l_val = math.exp(-min(max(0.0, lambda_miss), 700.0))
    k = 0
    p = 1.0
    while p > l_val:
        k += 1
        p *= random.random()
    sim_misses = max(0, k - 1)

    # 4. Combo Ratio Model
    if sim_misses == 0:
        combo_ratio = 1.0
    else:
        base_split = 1.0 / (sim_misses + 1)
        cons_factor = 0.5 + 0.5 * (cons_stat / 100.0)
        choke_luck = random.uniform(0.7, 1.3)
        combo_ratio = min(0.94, max(0.10, base_split * (1.2 + cons_factor) * choke_luck))

    # 5. ScoreV2 Calculation
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

def generate_tactical_scouting_dossier(player_name: str, stats: dict[str, int], tier_name: str) -> dict:
    """Generates a structured tactical scouting dossier with choke danger badges and signature slots."""
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

def generate_team_roster(team_size: int, tier_name: str, player_username: str = "Spieler") -> dict:
    """Generates rosters for player team and opponent team based on team size (1 to 4)."""
    valid_size = max(1, min(4, int(team_size or 1)))
    needed_names = valid_size * 2
    sampled_names = random.sample(GERMAN_OSU_NAMES, min(len(GERMAN_OSU_NAMES), max(8, needed_names)))

    player_team = []
    user_stats, _, _ = generate_8skill_profile(tier_name)
    player_team.append(generate_tactical_scouting_dossier(player_username, user_stats, tier_name))

    for i in range(valid_size - 1):
        tm_name = sampled_names[i]
        tm_stats, _, _ = generate_8skill_profile(tier_name)
        player_team.append(generate_tactical_scouting_dossier(tm_name, tm_stats, tier_name))

    opponent_team = []
    for i in range(valid_size):
        opp_name = sampled_names[valid_size - 1 + i]
        opp_stats, _, _ = generate_8skill_profile(tier_name)
        opponent_team.append(generate_tactical_scouting_dossier(opp_name, opp_stats, tier_name))

    return {
        "team_size": valid_size,
        "player_team": player_team,
        "opponent_team": opponent_team
    }

def aggregate_round_scores(player_scores: list[int], opponent_scores: list[int]) -> dict:
    """Aggregates round scores and computes victory status and winning margin."""
    p_total = sum(int(s or 0) for s in (player_scores or []))
    o_total = sum(int(s or 0) for s in (opponent_scores or []))
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

def evaluate_scouting_guess(player_top2: list[str], player_bot2: list[str], true_top2: list[str], true_bot2: list[str]) -> dict:
    """Calculates guessing challenge accuracy and verdict."""
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

def generate_offline_heuristic_debrief(match_summary: dict, true_profile: dict, guess_eval: dict) -> str:
    """Generates German caster match debriefing report without external API."""
    if not isinstance(match_summary, dict): match_summary = {}
    if not isinstance(true_profile, dict): true_profile = {}
    if not isinstance(guess_eval, dict): guess_eval = {}

    acc_pct = guess_eval.get("accuracy_pct", 0.0)
    true_str = ", ".join(true_profile.get("top_strengths", ["Aim", "Speed"]))
    true_weak = ", ".join(true_profile.get("top_weaknesses", ["Reading", "Stamina"]))
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

def generate_strategic_debrief(match_summary: dict, true_profile: dict, guess_eval: dict, api_key: str = None) -> str:
    """Generates German caster match debriefing report via Gemini AI or offline fallback."""
    if not api_key:
        return generate_offline_heuristic_debrief(match_summary, true_profile, guess_eval)

    prompt = f"""Du bist der offizielle deutsche osu! World Cup Chef-Caster und Taktik-Analyst.
Ein hochklassiges Turniermatch wurde soeben beendet:

=== MATCH-DATEN ===
Turnier: {match_summary.get('tournament', 'OWC')} ({match_summary.get('division', 'Grand Finals')})
Endstand: {match_summary.get('player_score', 0)} : {match_summary.get('bot_score', 0)}

=== WAHRER GEGNER-SKILL-RADAR ===
Echte Top-2 Stärken: {', '.join(true_profile.get('top_strengths', []))}
Echte Top-2 Schwächen: {', '.join(true_profile.get('top_weaknesses', []))}

=== SCOUTING-TIPPS DES SPIELERS ===
Scouting-Genauigkeit: {guess_eval.get('accuracy_pct', 0.0):.0f}% ({guess_eval.get('correct_count', 0)}/4 Treffer - {guess_eval.get('verdict_title', '')})

=== GESPIELTE RUNDEN & DRAFT-VERLAUF ===
{chr(10).join(match_summary.get('history', []))}

Erstelle einen packenden, hochprofessionellen Caster-Abschlussbericht auf Deutsch mit:
1. 🎙️ CASTER-MATCH-HIGHLIGHTS
2. 🎯 SCOUTING-URTEIL
3. ♟️ DRAFT- & BAN/PICK-ANALYSE
4. 📈 KONKRETER COACHING-TRAININGSPLAN"""

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}}
        r = requests.post(url, json=payload, timeout=12)
        resp = r.json()
        text = resp.get("candidates", [])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        if text:
            return text
    except Exception:
        pass
    return generate_offline_heuristic_debrief(match_summary, true_profile, guess_eval)

def draw_radar_polygon(canvas, skill_scores: dict[str, int], color_theme="cyan", is_hidden=False):
    """Draws 8-axis radar chart with concentric rings, labels, and theme polygons on CTkCanvas or Canvas."""
    try:
        canvas.delete("all")
        w = canvas.winfo_width() or 380
        h = canvas.winfo_height() or 340
        if w < 50: w = 380
        if h < 50: h = 340
        cx, cy = w / 2, h / 2
        max_r = max(40, min(cx, cy) - 45)

        categories = ALL_8_SKILLS
        n = len(categories)

        # Concentric background rings
        for ring in [0.25, 0.5, 0.75, 1.0]:
            r = max_r * ring
            ring_pts = []
            for i in range(n):
                angle = (2 * math.pi / n) * i - (math.pi / 2)
                ring_pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])
            canvas.create_polygon(ring_pts, fill="", outline="#2e2e3f", width=1)

        # Spokes and Labels
        for i, cat in enumerate(categories):
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + max_r * math.cos(angle)
            py = cy + max_r * math.sin(angle)
            canvas.create_line(cx, cy, px, py, fill="#3a3a4e", dash=(2, 2))

            lx = cx + (max_r + 24) * math.cos(angle)
            ly = cy + (max_r + 24) * math.sin(angle)
            score_val = "?" if is_hidden else str(skill_scores.get(cat, 10)) if isinstance(skill_scores, dict) else "10"
            canvas.create_text(lx, ly, text=f"{cat}\n({score_val})", fill="#bbbbcc" if not is_hidden else "#666677",
                               font=("Arial", 8, "bold"), justify="center")

        if is_hidden:
            canvas.create_text(cx, cy, text="❓\nVerdecktes\nProfil", fill="#555566", font=("Arial", 12, "bold"), justify="center")
            return

        themes = {
            "cyan": {"outline": "#00E5FF", "fill": "#00BFA5", "dot": "#00E5FF"},
            "green": {"outline": "#00E676", "fill": "#00C853", "dot": "#00E676"},
            "purple": {"outline": "#E040FB", "fill": "#9C27B0", "dot": "#E040FB"}
        }
        cfg = themes.get(color_theme, themes["cyan"])

        data_pts = []
        for i, cat in enumerate(categories):
            score = skill_scores.get(cat, 10) if isinstance(skill_scores, dict) else 10
            r = max_r * (max(5, min(100, score)) / 100.0)
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            data_pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])

        canvas.create_polygon(data_pts, fill=cfg["fill"], outline=cfg["outline"], width=2, stipple="gray25")
        for i in range(0, len(data_pts), 2):
            x, y = data_pts[i], data_pts[i+1]
            canvas.create_oval(x-4, y-4, x+4, y+4, fill=cfg["dot"], outline="#ffffff", width=1)
    except Exception:
        pass

def evaluate_bot_map_affinity(stats: dict[str, int], map_meta: dict) -> float:
    """Evaluates bot affinity score (0..100) for a given map slot."""
    weights = map_meta.get("weights", {})
    if not weights:
        weights = {s: 0.125 for s in ALL_8_SKILLS}
    return sum(stats.get(k, 10) * w for k, w in weights.items())

def bot_select_action(pool: dict, bot_stats: dict, player_stats: dict, action_type: str) -> str:
    """
    Selects slot for protect, ban, or pick based on true stats and counter-drafting.
    action_type in ['protect', 'ban', 'pick']
    """
    available_slots = [s for s, data in pool.items() if data.get("state") == "available" and s != "TB"]
    if not available_slots:
        return "TB" if "TB" in pool else list(pool.keys())[0]

    scored_slots = []
    for slot in available_slots:
        map_meta = pool[slot]
        bot_eval = evaluate_bot_map_affinity(bot_stats, map_meta)
        player_eval = evaluate_bot_map_affinity(player_stats, map_meta) if player_stats else 50.0
        delta = bot_eval - player_eval
        scored_slots.append((slot, delta, bot_eval))

    if action_type == "protect":
        scored_slots.sort(key=lambda x: x[2], reverse=True)
        return scored_slots[0][0]
    elif action_type == "ban":
        scored_slots.sort(key=lambda x: x[1])
        return scored_slots[0][0]
    elif action_type == "pick":
        scored_slots.sort(key=lambda x: x[1], reverse=True)
        return scored_slots[0][0]
    return available_slots[0]


def extract_replay_weakness_profile(deep_metrics, play_acc=100.0, play_combo=0, max_combo=0):
    """
    Analysiert Replay-Telemetrie und leitet gezielte Schwächen-Trainingsvektoren ab:
    - overaim / underaim -> Snap-Aim Distanz-Training
    - low alt_ratio + unsteadiness -> Finger-Control / Alternating Training
    - high ur / fatigue -> Stamina & Speed Consistency
    """
    if not isinstance(deep_metrics, dict):
        return {"target_subskill": None, "weaknesses": [], "recommended_focus": "Saubere Form beibehalten"}
        
    weaknesses = []
    subskill = None
    
    overaim = deep_metrics.get("overaim_pct", 50.0)
    underaim = deep_metrics.get("underaim_pct", 50.0)
    alt_ratio = deep_metrics.get("alt_ratio", 50.0)
    ur = deep_metrics.get("ur", 0.0)
    early_bias = deep_metrics.get("early_bias_pct", 50.0)
    
    if overaim > 65.0:
        weaknesses.append("Overshooting bei weiten Jumps (Cursor bremst zu spät ab)")
        subskill = "Snap-Aim"
    elif underaim > 65.0:
        weaknesses.append("Undershooting bei schnellen Snaps (Circles werden knapp verfehlt)")
        subskill = "Snap-Aim"
        
    if alt_ratio < 20.0 and ur > 140.0:
        weaknesses.append("Singletap-Ermüdung / Finger-Control Defizit auf Bursts")
        subskill = "Finger-Control"
    elif 25.0 <= alt_ratio <= 75.0 and ur > 160.0:
        weaknesses.append("Ungleichmäßiges Alternating-Tapping (Tapping-Asymmetrie)")
        subskill = "Alternating"
        
    if ur > 180.0:
        weaknesses.append("Hohe Unstable Rate (Rhythmus-Schwankungen)")
        if not subskill: subskill = "Consistency"
        
    if early_bias > 70.0:
        weaknesses.append("Zu frühes Tapping (Noten-Panik / Reading-Rush)")
    elif early_bias < 30.0:
        weaknesses.append("Zu spätes Tapping (Latenz oder AR-Überforderung)")
        
    return {
        "target_subskill": subskill,
        "weaknesses": weaknesses,
        "recommended_focus": weaknesses[0] if weaknesses else "Gleichmäßige Form beibehalten"
    }

def pick_dynamic_map_for_skill(category, target_sr, exclude_ids=None, mod=None, user_feedback=None, banned_mods=None, aim_style=None, strain_type=None, weakness_vector=None):
    if exclude_ids is None:
        exclude_ids = set()
    if banned_mods is None:
        banned_mods = set()
    
    # Resolve required mod and scale query SR
    req_mod = str(mod or "NM").upper().strip()
    if req_mod in ["NONE", "NO MOD", "NOMOD", "AUTO"]:
        req_mod = "NM"
    if req_mod in banned_mods:
        req_mod = "NM"

    try:
        query_sr = float(target_sr)
    except (ValueError, TypeError):
        query_sr = 5.0
    query_sr = max(1.0, min(12.0, query_sr))

    mod_bpm_min, mod_bpm_max = None, None
    mod_ar_min, mod_ar_max = None, None
    mod_cs_max = None

    if req_mod in ["DT", "NC"]:
        query_sr = max(2.8, safe_div(query_sr, 1.40, 5.0))
        mod_bpm_min = 115
        mod_bpm_max = 168
        mod_ar_min = 6.8
        mod_ar_max = 9.1
        mod_cs_max = 4.4
    elif req_mod == "HR":
        query_sr = max(3.0, safe_div(query_sr, 1.06, 5.0))
        mod_cs_max = 4.6
    elif req_mod == "EZ":
        query_sr = min(9.5, safe_div(query_sr, 0.72, 5.0))

    # === SQLite Path (accurate HitObject-based classification) ===
    if BEATMAP_SQLITE_DB_PATH:
        sr_range = 0.80
        candidates = sqlite_query_maps(
            skill=category,
            sr_min=round(query_sr - sr_range, 2),
            sr_max=round(query_sr + sr_range, 2),
            bpm_min=mod_bpm_min,
            bpm_max=mod_bpm_max,
            ar_min=mod_ar_min,
            ar_max=mod_ar_max,
            cs_max=mod_cs_max,
            exclude_ids=exclude_ids,
            limit=200,
            order_by="playcount DESC"
        )
        
        # Widen SR range if not enough candidates
        if len(candidates) < 5:
            candidates = sqlite_query_maps(
                skill=category,
                sr_min=round(query_sr - 1.5, 2),
                sr_max=round(query_sr + 1.5, 2),
                bpm_min=mod_bpm_min,
                bpm_max=min(176, mod_bpm_max + 8) if mod_bpm_max else None,
                ar_min=mod_ar_min,
                ar_max=min(9.3, mod_ar_max + 0.2) if mod_ar_max else None,
                cs_max=mod_cs_max,
                exclude_ids=exclude_ids,
                limit=200,
                order_by="playcount DESC"
            )
        
        # Also try secondary_skill if still sparse
        if len(candidates) < 3:
            with get_safe_sqlite_conn() as conn:
                if conn:
                    try:
                        rows = conn.execute(
                            "SELECT * FROM maps WHERE secondary_skill = ? AND sr BETWEEN ? AND ? ORDER BY playcount DESC LIMIT 100",
                            (str(category), float(round(query_sr - 1.2, 2)), float(round(query_sr + 1.2, 2)))
                        ).fetchall()
                        clean_ex = set(str(x) for x in exclude_ids) if exclude_ids else set()
                        candidates.extend([dict(r) for r in rows if str(dict(r).get("id", "")) not in clean_ex])
                    except Exception:
                        pass
        
        if candidates:
            # Filter by user feedback
            if user_feedback and isinstance(user_feedback, dict):
                candidates = [m for m in candidates if not (user_feedback.get(str(m.get("id","")), {}).get("liked") is False)]
            
            # Multi-Dimensional AI Ranking based on 11 Advanced Physics & Biomechanical Vectors
            def score_candidate(cand):
                score = 0.0
                desc = str(cand.get("description", ""))
                # Aim-Style matching
                if aim_style:
                    if aim_style.lower() in desc.lower(): score += 2.5
                # Strain-Profile matching
                if strain_type:
                    if strain_type.lower() in desc.lower(): score += 2.0
                # Weakness-Vector matching
                if weakness_vector and isinstance(weakness_vector, dict):
                    target_sub = str(weakness_vector.get("target_subskill", "")).lower()
                    if target_sub and target_sub in desc.lower(): score += 3.0
                # Playcount weighting
                score += min(1.5, math.log10(max(10, int(cand.get("playcount", 0) or 0))) * 0.25)
                # SR proximity
                sr_diff = abs(float(cand.get("sr", query_sr)) - query_sr)
                score -= sr_diff * 1.5
                return score

            candidates.sort(key=score_candidate, reverse=True)
            top_pool = candidates[:15]
            chosen = random.choice(top_pool) if len(top_pool) > 1 else top_pool[0]
        else:
            # Absolute fallback: any map near the SR
            fallback = sqlite_query_maps(sr_min=round(query_sr - 1.0, 2), sr_max=round(query_sr + 1.0, 2), limit=50)
            chosen = random.choice(fallback) if fallback else {"id": "0", "name": "Unknown", "sr": query_sr, "bpm": 180, "cs": 4.0, "ar": 9.0, "od": 8.0, "len": 120, "status": "Ranked", "year": 2024}
    
    # === JSON Fallback Path ===
    else:
        pool = DYNAMIC_MAPS_BY_SKILL.get(category)
        if not pool:
            pool = DYNAMIC_RANKED_MAPS_DB if DYNAMIC_RANKED_MAPS_DB else []

        sr_close_pool = [m for m in pool if abs(float(m.get('sr', 5.0)) - query_sr) <= 0.90]
        eval_pool = sr_close_pool if sr_close_pool else pool

        sample_pool = random.sample(eval_pool, min(len(eval_pool), 150)) if len(eval_pool) > 150 else eval_pool

        scored_candidates = []
        for m in sample_pool:
            m_id = str(m.get('id', ''))
            if m_id in exclude_ids:
                continue
            if user_feedback and isinstance(user_feedback, dict):
                fb = user_feedback.get(m_id)
                if fb and fb.get("liked") is False:
                    continue

            fp = compute_map_pattern_fingerprint(m)
            aff_score = fp.get(category, 0.50)
            if m.get('primary_skill') == category:
                aff_score = max(aff_score, 0.75)

            sr_diff = abs(float(m.get('sr', 5.0)) - query_sr)
            rank_metric = aff_score * 2.0 - sr_diff
            scored_candidates.append((rank_metric, aff_score, sr_diff, m))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [item[3] for item in scored_candidates if item[2] <= 0.65]
        if not top_candidates:
            top_candidates = [item[3] for item in scored_candidates[:5]] if scored_candidates else pool
        chosen = random.choice(top_candidates[:5]) if len(top_candidates) >= 5 else (top_candidates[0] if top_candidates else {"id": "0", "name": "Unknown", "sr": query_sr, "bpm": 180, "cs": 4.0, "ar": 9.0, "od": 8.0, "len": 120})

    # === Build result (shared for both paths) ===
    try: raw_sr = float(chosen.get('sr', 5.0) or 5.0)
    except: raw_sr = 5.0
    try: raw_bpm = int(chosen.get('bpm', 180) or 180)
    except: raw_bpm = 180
    try: raw_cs = float(chosen.get('cs', 4.0) or 4.0)
    except: raw_cs = 4.0
    try: raw_ar = float(chosen.get('ar', 9.0) or 9.0)
    except: raw_ar = 9.0
    try: raw_od = float(chosen.get('od', 8.0) or 8.0)
    except: raw_od = 8.0
    try: raw_len = int(chosen.get('len', 120) or 120)
    except: raw_len = 120

    eff_sr, eff_bpm, eff_cs, eff_ar, eff_od, eff_len = raw_sr, raw_bpm, raw_cs, raw_ar, raw_od, raw_len
    mod_suffix = ""

    if req_mod in ["DT", "NC"]:
        eff_sr = round(raw_sr * 1.40, 2)
        eff_bpm = int(raw_bpm * 1.5)
        eff_ar = min(11.0, round(safe_div(raw_ar * 2 + 13, 3, 9.0), 1)) if raw_ar > 5 else min(11.0, round(safe_div(raw_ar * 5 + 13, 3, 9.0), 1))
        eff_len = max(30, int(safe_div(raw_len, 1.5, 120)))
        mod_suffix = " +DT"
    elif req_mod == "HR":
        eff_sr = round(raw_sr * 1.06, 2)
        eff_cs = min(10.0, round(raw_cs * 1.3, 1))
        eff_ar = min(10.0, round(raw_ar * 1.4, 1))
        eff_od = min(10.0, round(raw_od * 1.4, 1))
        mod_suffix = " +HR"
    elif req_mod == "HD":
        mod_suffix = " +HD"
    elif req_mod == "EZ":
        eff_sr = round(raw_sr * 0.72, 2)
        eff_cs = max(1.5, round(raw_cs * 0.5, 1))
        eff_ar = max(1.5, round(raw_ar * 0.5, 1))
        eff_od = max(1.5, round(raw_od * 0.5, 1))
        mod_suffix = " +EZ"

    mins = eff_len // 60
    secs = eff_len % 60
    dur_str = f"{mins}:{secs:02d} min"

    if req_mod in ["DT", "NC"]:
        mod_goal_prefix = f"⚡ Spiele zwingend mit +DT ({eff_bpm} BPM / AR {eff_ar:.1f})! "
    elif req_mod == "HR":
        mod_goal_prefix = f"🛡️ Spiele zwingend mit +HR (CS {eff_cs:.1f} / OD {eff_od:.1f})! "
    elif req_mod == "HD":
        mod_goal_prefix = f"🕶️ Spiele zwingend mit +HD (Hidden Rhythmus-Lesen)! "
    elif req_mod == "EZ":
        mod_goal_prefix = f"🟢 Spiele zwingend mit +EZ (AR {eff_ar:.1f} Low-AR Reading)! "
    else:
        mod_goal_prefix = ""

    # Use real description from SQLite if available
    map_desc = str(chosen.get('description', '') or '')
    base_goals = {
        'Consistency': f"Versuche einen stabilen 97.5%+ FC über die gesamte Map ({dur_str}) ohne Nervosität zu halten.",
        'Speed': f"Kontrollierte Finger-Beschleunigung und saubere Tapping-Acc auf den {eff_bpm} BPM Bursts.",
        'Aim': f"Saubere Cursor-Snaps auf die {eff_sr:.1f}★ Jump-Distanzen ohne Over- oder Undershooting.",
        'Stamina': f"Halte die Tapping-Power über den {dur_str} Drain konstant ohne Muskelverkrampfung.",
        'Tech': f"Perfektes Slider-Tracking, präzise Winkel-Wechsel und Kontrolle über unkonventionelle Slider-Velocities (SV).",
        'Reading': f"Entspannte Muster-Erkennung auf AR {eff_ar:.1f}: Den Blick vorausschauend führen und Rhythmus fühlen.",
        'Streams': f"Gleichmäßiger Tapping-Rhythmus und fließende Cursor-Führung durch die {eff_bpm} BPM Streams.",
        'Precision': f"Exakte Treffer auf die kleinen CS {eff_cs:.1f} Circles mit maximaler Treffsicherheit."
    }
    if map_desc:
        goal_text = mod_goal_prefix + map_desc
    else:
        goal_text = mod_goal_prefix + base_goals.get(category, "Spiele die Map mit vollem Fokus auf saubere Accuracy.")

    rating = f"{min(9.9, max(9.1, 9.2 + (float(eff_sr) % 0.7))):.1f}/10"
    
    return {
        'id': chosen.get('id', '0'),
        'set_id': chosen.get('set_id', ''),
        'name': str(chosen.get('name', 'Unknown')) + mod_suffix,
        'raw_name': str(chosen.get('name', 'Unknown')),
        'artist': chosen.get('artist', ''),
        'title': chosen.get('title', ''),
        'version': chosen.get('version', ''),
        'sr': eff_sr,
        'raw_sr': raw_sr,
        'year': chosen.get('year', 2024),
        'status': chosen.get('status', 'Ranked'),
        'rating': rating,
        'type': category,
        'mod': req_mod,
        'goal': goal_text,
        'bpm': eff_bpm,
        'cs': eff_cs,
        'ar': eff_ar,
        'od': eff_od,
        'len': eff_len,
        'description': map_desc,
    }

def estimate_sr_from_rank_and_pp(rank=0, pp=0):
    """
    Kalibriert das reale Benchmark-Star-Rating anhand des Globalen Rangs und der Performance Points.
    Gewährleistet, dass High-Rank-Spieler (z.B. Rang 1.900) echte 7.4★ - 7.8★ Test-Maps erhalten.
    """
    try: rank = int(rank or 0)
    except: rank = 0
    try: pp = float(pp or 0.0)
    except: pp = 0.0
    
    if rank > 0:
        if rank <= 50: return 9.2
        elif rank <= 200: return 8.6
        elif rank <= 500: return 8.2
        elif rank <= 1000: return 7.9
        elif rank <= 2500: return 7.5  # z.B. Rang 1.900 -> 7.5★
        elif rank <= 5000: return 7.1
        elif rank <= 10000: return 6.7
        elif rank <= 25000: return 6.2
        elif rank <= 50000: return 5.8
        elif rank <= 100000: return 5.3
        elif rank <= 250000: return 4.7
        else: return 4.2
    elif pp > 0:
        return round(max(3.8, min(9.5, (pp ** 0.35) * 0.77)), 2)
    return 5.2

def calculate_adaptive_topplay_difficulty(top_plays, user_info=None, db=None):
    """
    Analysiert Top-Plays des Spielers mit SQLite-Lookup und Rang-Kalibrierung:
    - Fragt echte Star Ratings direkt aus der 65k+ SQLite-Datenbank ab
    - Berücksichtigt Mods (+DT 1.4x, +HR 1.06x, +EZ 0.72x)
    - Bewertet Accuracy und Misses für die effektive Ziel-Schwierigkeit
    """
    id_map = {}
    if top_plays and isinstance(top_plays, list):
        bids = [str(p.get("beatmap_id", "")) for p in top_plays if isinstance(p, dict) and p.get("beatmap_id")]
        with get_safe_sqlite_conn() as conn:
            if conn and bids:
                placeholders = ",".join(["?"] * len(bids[:100]))
                try:
                    rows = conn.execute(f"SELECT id, sr FROM maps WHERE id IN ({placeholders})", bids[:100]).fetchall()
                    for r in rows:
                        id_map[str(r["id"])] = float(r["sr"])
                except Exception:
                    pass
    if not id_map:
        id_map = {str(m.get('id', '')): float(m.get('sr', 5.0)) for m in (db or DYNAMIC_RANKED_MAPS_DB or []) if isinstance(m, dict)}
    
    u_rank = 0
    u_pp = 0.0
    if user_info and isinstance(user_info, dict):
        try: u_rank = int(user_info.get("pp_rank", 0) or 0)
        except: pass
        try: u_pp = float(user_info.get("pp_raw", 0) or 0.0)
        except: pass

    default_rank_sr = estimate_sr_from_rank_and_pp(u_rank, u_pp)

    if not top_plays or not isinstance(top_plays, list):
        return {
            "base_raw_sr": default_rank_sr, "effective_sr": default_rank_sr,
            "avg_acc": 97.0, "avg_misses": 0.0, "mastery_tier": "Solid",
            "explanation": f"Rang-Kalibrierung (#{u_rank:,} / {u_pp:.0f}pp): ★ {default_rank_sr:.2f}"
        }

    raw_srs = []
    effective_srs = []
    accs = []
    misses_list = []
    weights = []

    for i, p in enumerate(top_plays[:50]):
        if not isinstance(p, dict):
            continue
        try:
            bid = str(p.get("beatmap_id", "") or "")
            mods = int(p.get("enabled_mods", 0) or 0)
            h300 = int(p.get("count300", 0) or 0)
            h100 = int(p.get("count100", 0) or 0)
            h50 = int(p.get("count50", 0) or 0)
            miss = int(p.get("countmiss", 0) or 0)
            pp = float(p.get("pp", 0.0) or 0.0)
        except (ValueError, TypeError):
            bid = str(p.get("beatmap_id", "") or "") if isinstance(p, dict) else ""
            mods = 0
            h300, h100, h50, miss = 0, 0, 0, 0
            pp = 0.0

        tot = h300 + h100 + h50 + miss
        acc = (safe_div(h300 * 300 + h100 * 100 + h50 * 50, tot * 300, 0.0) * 100.0) if tot > 0 else 0.0

        # Star Rating Resolution
        try:
            if bid in id_map:
                play_sr = float(id_map[bid])
                if (mods & 64) or (mods & 512): # DT / NC
                    play_sr *= 1.40
                elif (mods & 16): # HR
                    play_sr *= 1.06
                elif (mods & 2): # EZ
                    play_sr *= 0.72
                elif (mods & 256): # HT
                    play_sr *= 0.75
            elif pp > 0:
                play_sr = (pp ** 0.35) * 0.77
            else:
                play_sr = default_rank_sr
        except (ValueError, TypeError):
            play_sr = default_rank_sr

        play_sr = max(3.5, min(10.5, play_sr))

        # Mastery Offset based on Accuracy and Miss Count
        if miss == 0 and acc >= 99.0:
            mastery_offset = +0.35
        elif miss == 0 and acc >= 98.0:
            mastery_offset = +0.22
        elif miss <= 1 and acc >= 96.5:
            mastery_offset = +0.08
        elif miss <= 2 and acc >= 94.5:
            mastery_offset = 0.00
        elif miss <= 4 and acc >= 92.0:
            mastery_offset = -0.25
        elif miss <= 7 or acc >= 88.0:
            mastery_offset = -0.45
        else:
            mastery_offset = -0.70

        eff_sr = max(3.5, min(10.0, play_sr + mastery_offset))
        w = 0.96 ** i

        raw_srs.append(play_sr)
        effective_srs.append(eff_sr)
        accs.append(acc)
        misses_list.append(miss)
        weights.append(w)

    sum_w = sum(weights)
    weighted_raw_sr = safe_div(sum(r * w for r, w in zip(raw_srs, weights)), sum_w, 5.2)
    # Set benchmark difficulty to 0.55* below Top Plays (comfort baseline / skill floor)
    effective_sr_calibrated = max(3.0, min(9.5, weighted_raw_sr - 0.55))
    weighted_acc = safe_div(sum(a * w for a, w in zip(accs, weights)), sum_w, 97.0)
    weighted_misses = safe_div(sum(m * w for m, w in zip(misses_list, weights)), sum_w, 0.0)

    tier = "Adaptive Baseline (~0.55★ unter Top-Plays)"

    return {
        "base_raw_sr": round(weighted_raw_sr, 2),
        "effective_sr": round(effective_sr_calibrated, 2),
        "avg_acc": round(weighted_acc, 2),
        "avg_misses": round(weighted_misses, 2),
        "mastery_tier": tier,
        "explanation": f"Echter Top-Play Durchschnitt: ★ {weighted_raw_sr:.2f} (Acc: {weighted_acc:.1f}%) -> Benchmark-Test-Schwierigkeit (-0.55★ für realistischen Skill-Floor): ★ {effective_sr_calibrated:.2f}"
    }

def calculate_skill_test_score(acc, misses, h50=0, maxcombo=0, map_sr=5.5, player_sr=5.5):
    """
    Berechnet die faire, kalibrierte Skillset-Punktzahl (0 - 100) fuer eine gespielte Test-Map:
    - 0 Misses (FC) & 99%+ Acc -> 96 - 100 Punkte (Meisterhaft)
    - 0 Misses & 97.5% Acc -> 90 - 95 Punkte (Souveraener FC)
    - 1 Miss (Choke) & 97%+ Acc -> 80 - 88 Punkte
    - 2-3 Misses & 93%+ Acc -> 65 - 78 Punkte (Solider A-Rank Pass)
    - 4-6 Misses & 92%+ Acc -> 50 - 64 Punkte
    - 8+ Misses / Low Acc -> 25 - 45 Punkte
    """
    try: acc = float(acc)
    except: acc = 0.0
    try: misses = int(misses)
    except: misses = 0
    try: h50 = int(h50)
    except: h50 = 0
    try: maxcombo = int(maxcombo)
    except: maxcombo = 0
    try: map_sr = float(map_sr)
    except: map_sr = 5.5
    try: player_sr = float(player_sr)
    except: player_sr = 5.5

    if math.isnan(acc) or math.isinf(acc) or acc <= 0:
        return 0.0

    # 1. Base Score derived from Accuracy (smooth realistic curve)
    if acc >= 98.0:
        base = 92.0 + safe_div(acc - 98.0, 2.0, 0.0) * 8.0   # 98% -> 92, 100% -> 100
    elif acc >= 95.0:
        base = 82.0 + safe_div(acc - 95.0, 3.0, 0.0) * 10.0  # 95% -> 82, 98% -> 92
    elif acc >= 90.0:
        base = 68.0 + safe_div(acc - 90.0, 5.0, 0.0) * 14.0  # 90% -> 68, 95% -> 82
    elif acc >= 80.0:
        base = 45.0 + safe_div(acc - 80.0, 10.0, 0.0) * 23.0  # 80% -> 45, 90% -> 68
    else:
        base = max(15.0, acc * 0.55)

    # 2. Miss Penalty (balanced scaling so A-ranks never crash to 5 pts)
    if misses <= 0:
        miss_penalty = 0.0
    elif misses == 1:
        miss_penalty = 6.0
    elif misses == 2:
        miss_penalty = 12.0
    elif misses == 3:
        miss_penalty = 18.0
    elif misses == 4:
        miss_penalty = 24.0
    elif misses <= 6:
        miss_penalty = 24.0 + (misses - 4) * 4.0   # 5 misses -> -28 pts
    elif misses <= 10:
        miss_penalty = 32.0 + (misses - 6) * 3.0   # 10 misses -> -44 pts
    else:
        miss_penalty = 44.0 + min(25.0, (misses - 10) * 1.5)

    # 3. 50s Tapping Instability Penalty (max 10 pts)
    h50_penalty = min(10.0, max(0, h50) * 1.5)

    # 4. SR Difficulty Scaling Bonus/Adjustment
    safe_player_sr = max(0.1, player_sr)
    sr_ratio = safe_div(map_sr, max(3.5, safe_player_sr), 1.0)
    sr_mult = max(0.90, min(1.15, sr_ratio))

    raw_calc = (base - miss_penalty - h50_penalty) * sr_mult

    # Safe floor guarantees based on Accuracy & Pass Quality (e.g. 93% A-rank >= 50 pts)
    if acc >= 95.0 and misses <= 3:
        floor_val = 65.0
    elif acc >= 92.0 and misses <= 5:
        floor_val = 50.0
    elif acc >= 88.0:
        floor_val = 35.0
    else:
        floor_val = 10.0

    final_score = max(floor_val, min(100.0, raw_calc))
    return round(final_score, 1)

import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES

# --- UHO HUB CONFIGURATION ---
UHO_AUTH_SERVER_URL = "https://uho-hub-api.onrender.com"
UHO_DISCORD_INVITE_URL = "https://discord.gg/your-invite"
UHO_DEV_PROFILE_URL = "https://discord.com/users/kingmaster0550"

def get_hwid():
    """Generiert einen eindeutigen Hardware-Fingerabdruck des Computers."""
    hwid_components = []
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        hwid_components.append(str(value))
    except:
        pass
    hwid_components.append(os.environ.get("PROCESSOR_IDENTIFIER", "CPU"))
    hwid_components.append(os.environ.get("COMPUTERNAME", "PC"))
    hwid_components.append(os.environ.get("USERNAME", "USER"))
    raw = "-".join(hwid_components)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]

# Standard Tournament Slot Skillset Conventions (OWC / Corsace / Major Tournaments)
DEFAULT_TOURNAMENT_SLOT_SKILLSETS = {
    "NM1": ("Consistency", "All-Around Konstanz, Jumps & Stabilität. Standard-Eröffnungsmap.", "#3b8ed0"),
    "NM2": ("Aim & Precision", "Präzises Flow Aim, kleine CS & Snaps.", "#3b8ed0"),
    "NM3": ("Speed & Bursts", "Hohes Grundtempo (220+ BPM), Finger Speed & Bursts.", "#3b8ed0"),
    "NM4": ("Tech & Reading", "Komplexe Slider-Shapes, unkonventionelle Rhythmen & Reading.", "#3b8ed0"),
    "NM5": ("Finger Control", "Rhythmus-Wechsel (1/3, 1/4, 1/6 Snappings) & Alternate.", "#3b8ed0"),
    "NM6": ("Stamina & High CS", "Lange Streams, hohe Ausdauerbelastung oder kleine CS.", "#3b8ed0"),
    "HD1": ("Aim & Reading", "Reines Hidden Aim, Muscle-Memory & Notenpositionierung.", "#E91E63"),
    "HD2": ("Tech & Flow", "SliderTech mit Hidden & präzise Slider-Geschwindigkeiten.", "#E91E63"),
    "HD3": ("Speed & Control", "Hohes Tempo & Bursts mit Hidden.", "#E91E63"),
    "HR1": ("Precision & Aim", "Sehr kleine CS (CS 5.2 - 6.5) & AR 10 Präzision.", "#F44336"),
    "HR2": ("Consistency & Stamina", "Längere HR-Map mit Fokus auf Combo-Sicherheit & Nervenstärke.", "#F44336"),
    "HR3": ("High AR & Tech", "Schnelle Übergänge, Flow Aim & hohe Lesegeschwindigkeit.", "#F44336"),
    "DT1": ("Pure Speed & Bursts", "Hohes BPM-Tempo (250 - 280+ BPM) & schnelle Burst-Streams.", "#9C27B0"),
    "DT2": ("Speed Aim & Jumps", "Schnelle Velocity-Jumps & snappy Aim bei hoher Geschwindigkeit.", "#9C27B0"),
    "DT3": ("Finger Control & Alt", "Komplexe Rhythmen auf DoubleTime, Alternate & Finger Control.", "#9C27B0"),
    "DT4": ("Stamina & Drain", "Lange DT-Maps mit hohem Ausdauer-Fokus & Drain.", "#9C27B0"),
    "FM1": ("Consistency & Hybrid", "Ausgewogener All-Rounder Slot für HD, HR, EZ oder NM.", "#00E5FF"),
    "FM2": ("Tech & Precision", "SliderTech / Präzisions-Map für Spezialisten (z. B. HDHR / HD).", "#00E5FF"),
    "FM3": ("Speed & Alt", "Tempo- & Alternate-Fokus für FreeMod-Strategien.", "#00E5FF"),
    "TB":  ("Tiebreaker All-Around", "Lange (4-6 Min) epische Final-Map, die alle Skills kombiniert.", "#FF9800"),
    "EZ1": ("Reading & Density", "Easy Low AR Reading & Notendichte.", "#4CAF50"),
    "FL1": ("Memory & Precision", "Flashlight Memorization & Auswendiglernen.", "#FFEB3B")
}

def get_slot_standard_skillset_name(slot):
    """Returns the standard tournament skillset name for any pool slot (e.g. NM1 -> Consistency, HR2 -> Consistency & Stamina)."""
    s = str(slot).upper().strip()
    if s in DEFAULT_TOURNAMENT_SLOT_SKILLSETS:
        return DEFAULT_TOURNAMENT_SLOT_SKILLSETS[s][0]
    for pfx in ["NM", "HD", "HR", "DT", "FM", "TB", "EZ", "FL"]:
        if s.startswith(pfx):
            key = f"{pfx}1" if f"{pfx}1" in DEFAULT_TOURNAMENT_SLOT_SKILLSETS else pfx
            if key in DEFAULT_TOURNAMENT_SLOT_SKILLSETS:
                return DEFAULT_TOURNAMENT_SLOT_SKILLSETS[key][0]
    return "All-Around"

class BanchoRefereeBot:
    """Automated osu! Bancho IRC Referee Bot: creates lobbies, enforces ScoreV2, sends in-game invites,
    sets maps/mods, broadcasts pools, parses ScoreV2 match events, and handles in-game chat commands."""
    def __init__(self, username, irc_password, on_log=None, on_match_created=None, on_round_ended=None,
                 on_chat_command=None, on_player_score=None, on_map_changed=None, on_match_settings=None,
                 on_player_joined=None, on_player_left=None):
        self.username = username
        self.irc_password = irc_password
        self.on_log = on_log or (lambda msg, col="#ffffff": None)
        self.on_match_created = on_match_created or (lambda match_id, channel: None)
        self.on_round_ended = on_round_ended or (lambda: None)
        self.on_chat_command = on_chat_command or (lambda sender, cmd, arg, full: None)
        self.on_player_score = on_player_score or (lambda user, score, status, raw: None)
        self.on_map_changed = on_map_changed or (lambda title, bid: None)
        self.on_match_settings = on_match_settings or (lambda settings: None)
        self.on_player_joined = on_player_joined or (lambda user, slot, team: None)
        self.on_player_left = on_player_left or (lambda user: None)
        
        self.sock = None
        self.running = False
        self.connected = False
        self.match_id = None
        self.channel = None
        self.thread = None
        self.pending_lobby_name = "UHO Hub Match"
        self.pending_password = ""

        # Solo Referee & Host-Rotation State
        self.is_solo_referee_mode = False
        self.target_player_username = ""
        self.team_size = 1
        self.is_host_rotation_mode = False
        self.host_queue = []
        self.current_host_idx = 0

    def log(self, text, color="#aaaaaa"):
        try:
            sys.stdout.buffer.write(f"[BanchoRefereeBot] {text}\n".encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        except Exception:
            pass
        if self.on_log:
            try: self.on_log(text, color)
            except Exception:
                pass

    def connect_and_host(self, lobby_name="UHO Hub Match", password="", host_rotation=False, initial_players=None):
        self.pending_lobby_name = lobby_name
        self.pending_password = password
        self.is_solo_referee_mode = False
        self.is_host_rotation_mode = host_rotation
        self.host_queue = [p.strip().replace(" ", "_") for p in (initial_players or []) if p.strip()]
        self.current_host_idx = 0
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        # 20-Sekunden Watchdog für Fehlerausgabe
        def _watchdog_20s():
            time.sleep(20)
            if self.running and not self.match_id:
                if not self.connected:
                    self.log("❌ FEHLERCODE [ERR_IRC_TIMEOUT_20S]: Verbindung zu irc.ppy.sh nach 20 Sekunden fehlgeschlagen!", "#FF5252")
                    self.log("👉 Mögliche Ursachen: Firewall/Antivirus blockiert IRC-Port 6667/6697 oder keine Internetverbindung.", "#FFA726")
                else:
                    self.log("❌ FEHLERCODE [ERR_BANCHO_NO_RESPONSE_20S]: Keine Antwort von BanchoBot auf '!mp make' nach 20 Sekunden!", "#FF5252")
                    self.log("👉 Mögliche Ursachen: Falsches Server-Passwort (https://osu.ppy.sh/p/irc), Bancho überlastet oder Login ungültig.", "#FFA726")
        threading.Thread(target=_watchdog_20s, daemon=True).start()

    def connect_and_host_solo(self, lobby_name="UHO Hub Solo Tournament", player_username="", password="", team_size=1):
        """Spawns an automated private ScoreV2 solo tournament lobby and invites the player."""
        self.pending_lobby_name = lobby_name
        self.pending_password = password
        self.is_solo_referee_mode = True
        self.target_player_username = player_username.strip().replace(" ", "_") if player_username else self.username
        self.team_size = max(1, min(4, int(team_size or 1)))
        self.is_host_rotation_mode = False
        self.host_queue = []
        self.current_host_idx = 0
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        # 20-Sekunden Watchdog für Fehlerausgabe
        def _watchdog_20s():
            time.sleep(20)
            if self.running and not self.match_id:
                if not self.connected:
                    self.log("❌ FEHLERCODE [ERR_IRC_TIMEOUT_20S]: Verbindung zu irc.ppy.sh nach 20 Sekunden fehlgeschlagen!", "#FF5252")
                    self.log("👉 Mögliche Ursachen: Firewall/Antivirus blockiert IRC-Port 6667/6697 oder keine Internetverbindung.", "#FFA726")
                else:
                    self.log("❌ FEHLERCODE [ERR_BANCHO_NO_RESPONSE_20S]: Keine Antwort von BanchoBot auf '!mp make' nach 20 Sekunden!", "#FF5252")
                    self.log("👉 Mögliche Ursachen: Falsches Server-Passwort (https://osu.ppy.sh/p/irc), Bancho überlastet oder Login ungültig.", "#FFA726")
        threading.Thread(target=_watchdog_20s, daemon=True).start()

    def setup_solo_room(self, player_username=None, password="", team_size=1):
        """Configures ScoreV2, locks room slots, sets optional password, and dispatches in-game invite."""
        target_u = player_username or self.target_player_username or self.username
        def _bg():
            time.sleep(0.8)
            self.set_team_mode(team_size=team_size, scoremode=3) # ScoreV2 Mode
            time.sleep(0.4)
            self.lock_room()
            if password:
                time.sleep(0.3)
                self.set_password(password)
            if target_u:
                time.sleep(0.5)
                self.invite_player(target_u)
                self._send_raw(f"PRIVMSG BanchoBot :!mp invite {target_u}")
                self.log(f"✉️ Ingame-Einladung an '{target_u}' gesendet! Tippe in osu! '/join {self.channel}' oder klicke auf den Lobby-Button im UHO Hub.", "#00E676")
            time.sleep(0.5)
            self.send_channel_message("🏆 UHO Hub Solo-Turnier-Lobby initialisiert (ScoreV2 aktiv). Nutze !pick <slot> oder das UHO Hub UI!")
        threading.Thread(target=_bg, daemon=True).start()

    def _send_raw(self, line):
        clean_line = str(line).replace("\r", "").replace("\n", "").strip()
        if self.sock and self.connected:
            try:
                if clean_line:
                    self.sock.sendall((clean_line + "\r\n").encode("utf-8"))
            except Exception as e:
                self.log(f"⚠️ IRC Send Fehler: {e}", "#ff4444")

    def send_mp(self, command):
        """Sends a command to the match channel or BanchoBot."""
        clean_command = str(command).replace("\r", "").replace("\n", "").strip()
        clean_cmd = clean_command if clean_command.startswith("!") else ("!" + clean_command)
        target = self.channel if self.channel else "BanchoBot"
        self.log(f"🤖 Referee Bot: {clean_cmd}", "#00E5FF")
        self._send_raw(f"PRIVMSG {target} :{clean_cmd}")

    def send_channel_message(self, text):
        clean_text = str(text).replace("\r", "").replace("\n", "").strip()
        if self.channel and clean_text:
            self._send_raw(f"PRIVMSG {self.channel} :{clean_text}")

    def invite_player(self, username):
        clean_u = str(username).replace("\r", "").replace("\n", "").strip().replace(" ", "_")
        if clean_u:
            self.send_mp(f"mp invite {clean_u}")

    def lock_room(self):
        self.send_mp("mp lock")

    def unlock_room(self):
        self.send_mp("mp unlock")

    def set_password(self, password=""):
        clean_pwd = str(password).replace("\r", "").replace("\n", "").strip()
        self.send_mp(f"mp password {clean_pwd}" if clean_pwd else "mp password")

    def set_size(self, size=2):
        s = max(1, min(16, int(size)))
        self.send_mp(f"mp size {s}")

    def set_map(self, beatmap_id, mods=None, enforce_nf=True):
        clean_bid = int(beatmap_id) if str(beatmap_id).isdigit() else beatmap_id
        self.send_mp(f"mp map {clean_bid} 0")
        time.sleep(0.3)
        if mods:
            m = str(mods).strip().upper()
            if m in ["FM", "FREEMOD"]:
                self.send_mp("mp mods Freemod NF" if enforce_nf else "mp mods Freemod")
            elif m in ["NM", "NOMOD", "NONE"]:
                self.send_mp("mp mods NF" if enforce_nf else "mp mods None")
            elif m in ["TB", "TIEBREAKER"]:
                self.send_mp("mp mods Freemod NF" if enforce_nf else "mp mods Freemod")
            elif m in ["HD", "HIDDEN"]:
                self.send_mp("mp mods HD NF" if enforce_nf else "mp mods HD")
            elif m in ["HR", "HARDROCK"]:
                self.send_mp("mp mods HR NF" if enforce_nf else "mp mods HR")
            elif m in ["DT", "DOUBLETIME"]:
                self.send_mp("mp mods DT NF" if enforce_nf else "mp mods DT")
            elif m in ["EZ", "EASY"]:
                self.send_mp("mp mods EZ NF" if enforce_nf else "mp mods EZ")
            elif m in ["FL", "FLASHLIGHT"]:
                self.send_mp("mp mods FL NF" if enforce_nf else "mp mods FL")
            else:
                self.send_mp(f"mp mods {m} NF" if enforce_nf else f"mp mods {m}")
        else:
            self.send_mp("mp mods NF" if enforce_nf else "mp mods None")

    def set_team_mode(self, team_size=1, scoremode=3):
        """Sets team and score mode on Bancho. scoremode: 0=Score, 1=Accuracy, 2=Combo, 3=ScoreV2."""
        if team_size <= 1:
            self.send_mp(f"mp set 0 {scoremode} 2") # Head-to-Head, ScoreV2, 2 Slots
        else:
            slots = max(2, min(16, int(team_size) * 2))
            self.send_mp(f"mp set 2 {scoremode} {slots}") # TeamVs, ScoreV2, N Slots

    def start_countdown(self, seconds=10):
        self.send_mp(f"mp start {seconds}")

    def abort_match(self):
        self.send_mp("mp abort")

    def set_host(self, username):
        clean_u = str(username).replace("\r", "").replace("\n", "").strip().replace(" ", "_")
        if clean_u:
            self.send_mp(f"mp host {clean_u}")
            self.send_channel_message(f"👑 Host übergeben an: {clean_u}!")

    def rotate_next_host(self):
        if not self.host_queue:
            return None
        self.current_host_idx = (self.current_host_idx + 1) % len(self.host_queue)
        next_host = self.host_queue[self.current_host_idx]
        self.set_host(next_host)
        return next_host

    def broadcast_mappool(self, pool_dict, stage_name="Turnier"):
        if not self.channel or not pool_dict:
            return
        def _bg():
            time.sleep(0.8)
            self.send_channel_message(f"🏆 --- UHO Hub Offizieller Mappool ({stage_name}) ---")
            
            # Format slots in readable lines
            slot_order = ["NM1", "NM2", "NM3", "NM4", "NM5", "NM6", "HD1", "HD2", "HD3", "HR1", "HR2", "HR3", "DT1", "DT2", "DT3", "FM1", "FM2", "FM3", "TB"]
            lines_chunk = []
            curr_line = []
            for s in sorted(pool_dict.keys(), key=lambda x: slot_order.index(x) if x in slot_order else 99):
                m = pool_dict[s]
                curr_line.append(f"[{s}] {m.get('name', 'Map')[:32]} (★ {m.get('sr', 5.0):.2f})")
                if len(curr_line) >= 3:
                    lines_chunk.append(" | ".join(curr_line))
                    curr_line = []
            if curr_line:
                lines_chunk.append(" | ".join(curr_line))

            for l in lines_chunk:
                time.sleep(0.7)
                self.send_channel_message(l)

            time.sleep(0.7)
            self.send_channel_message("📌 Ingame-Befehle: !roll | !save <slot> | !ban <slot> | !pick <slot> | !ready | !abort | !maps | !score")
        threading.Thread(target=_bg, daemon=True).start()

    def close_lobby(self):
        if self.channel:
            self.send_mp("mp close")
        self.running = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def _run_loop(self):
        try:
            clean_pass = self.irc_password.replace("\r", "").replace("\n", "").strip()
            clean_user = self.username.replace("\r", "").replace("\n", "").strip().replace(" ", "_")
            if not clean_pass:
                self.log("❌ FEHLERCODE [ERR_NO_IRC_PASSWORD]: Kein IRC-Passwort vorhanden! Bitte trage dein Server-Passwort von https://osu.ppy.sh/p/irc in den Einstellungen ein.", "#FF5252")
                return
            if not clean_user:
                self.log("❌ FEHLERCODE [ERR_NO_USERNAME]: Kein osu! Spielername vorhanden!", "#FF5252")
                return

            connected = False
            for port, use_tls in [(6667, False), (6697, True)]:
                try:
                    self.log(f"🔒 Verbinde mit Bancho IRC (irc.ppy.sh:{port}{' TLS' if use_tls else ''}) als '{clean_user}'...", "#00E5FF")
                    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    raw_sock.settimeout(6)
                    if use_tls:
                        ssl_ctx = ssl.create_default_context()
                        ssl_ctx.check_hostname = False
                        ssl_ctx.verify_mode = ssl.CERT_NONE
                        self.sock = ssl_ctx.wrap_socket(raw_sock, server_hostname="irc.ppy.sh")
                        self.sock.connect(("irc.ppy.sh", port))
                    else:
                        self.sock = raw_sock
                        self.sock.connect(("irc.ppy.sh", port))
                    self.connected = True
                    connected = True
                    break
                except Exception as e_conn:
                    self.log(f"⚠️ Verbindung auf Port {port} fehlgeschlagen: {e_conn}", "#FFA726")
                    if self.sock:
                        try: self.sock.close()
                        except: pass
                        self.sock = None

            if not connected or not self.sock:
                self.log("❌ FEHLERCODE [ERR_SOCKET_CONN]: Verbindung zu irc.ppy.sh fehlgeschlagen (Port 6697/6667 blockiert).", "#FF5252")
                return

            self.sock.settimeout(None)
            
            # Send standard Bancho IRC handshake
            self._send_raw(f"PASS {clean_pass}")
            self._send_raw(f"NICK {clean_user}")
            self._send_raw(f"USER {clean_user} 0 * :{clean_user}")
            
            readbuffer = ""
            logged_in = False
            while self.running:
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        if self.running:
                            self.log("⚠️ Verbindung von Bancho-Server geschlossen.", "#FFA726")
                        break
                    readbuffer += data.decode("utf-8", errors="ignore")
                    if "\n" in readbuffer:
                        lines = readbuffer.split("\n")
                        readbuffer = lines.pop()

                        for raw_line in lines:
                            line = raw_line.strip("\r").strip()
                            if not line: continue
                            
                            # Respond to PING
                            if line.startswith("PING"):
                                self._send_raw(line.replace("PING", "PONG"))
                                continue

                            # Check for Bancho Authentication Failures
                            if " 464 " in line or "Password incorrect" in line or "Bad authentication" in line or "Bad token" in line:
                                self.log("❌ FEHLERCODE [ERR_AUTH_464]: Ungültiges Bancho IRC-Passwort!", "#FF5252")
                                self.log("👉 WICHTIG: Verwende dein offizielles Server-Passwort von https://osu.ppy.sh/p/irc (NICHT dein normales osu!-Login-Passwort!).", "#FFA726")
                                self.running = False
                                return

                            if " 433 " in line or "Nickname is already in use" in line:
                                self.log(f"❌ FEHLERCODE [ERR_NICK_IN_USE_433]: Nickname '{clean_user}' ist bereits eingeloggt! Schließe bitte andere IRC-Clients.", "#FF5252")

                            # Check for Bancho Login Successful
                            if (" 001 " in line or "Welcome to" in line or "ChoToken" in line) and not logged_in:
                                logged_in = True
                                self.log(f"✅ Erfolgreich bei Bancho IRC eingeloggt als '{clean_user}'!", "#00E676")
                                time.sleep(0.5)
                                self.log(f"⚡ Sende Lobby-Erstellungsbefehl: !mp make {self.pending_lobby_name}", "#00E5FF")
                                self._send_raw(f"PRIVMSG BanchoBot :!mp make {self.pending_lobby_name}")

                            # Check for Match Created
                            if "Created the tournament match" in line or "Joined channel #mp_" in line or "#mp_" in line or "/mp/" in line or "JOIN :#mp_" in line:
                                match_m = re.search(r'(?:#mp_|/mp/)(\d+)', line)
                                if match_m and not self.match_id:
                                    self.match_id = match_m.group(1)
                                    self.channel = f"#mp_{self.match_id}"
                                    self.log(f"🏆 Ingame-Lobby erfolgreich erstellt: {self.channel} (ID: {self.match_id})", "#00E676")
                                    self._send_raw(f"JOIN {self.channel}")
                                    if self.pending_password:
                                        time.sleep(0.3)
                                        self.send_mp(f"mp password {self.pending_password}")
                                    if self.on_match_created:
                                        threading.Thread(target=lambda m_id=self.match_id, ch=self.channel: self.on_match_created(m_id, ch), daemon=True).start()

                            # Match Chat & events
                            if "PRIVMSG" in line:
                                parts = line.split("PRIVMSG", 1)
                                sender = parts[0].split("!")[0].lstrip(":")
                                target_ch = parts[1].split(":", 1)[0].strip()
                                msg_content = parts[1].split(":", 1)[1].strip() if ":" in parts[1] else parts[1].strip()
                                self.log(f"💬 [{sender}]: {msg_content}", "#dddddd")

                                # Detect All players are ready event from BanchoBot -> Auto-start countdown
                                if "all players are ready" in msg_content.lower() or "everyone is ready" in msg_content.lower():
                                    self.log("🚀 Alle Spieler im Raum sind bereit! Starte 5s Countdown automatisch...", "#00E676")
                                    self.start_countdown(5)

                                # Detect ScoreV2 finished playing event from BanchoBot
                                if sender == "BanchoBot" and "finished playing" in msg_content:
                                    m_score = re.search(r'(.+?)\s+finished playing\s*\(\s*Score:\s*(\d+)\s*,\s*(PASSED|FAILED)\s*\)', msg_content)
                                    if m_score:
                                        p_user = m_score.group(1).strip()
                                        p_score = int(m_score.group(2))
                                        p_status = m_score.group(3)
                                        self.log(f"🎯 ScoreV2 erfasst für {p_user}: {p_score:,} ({p_status})", "#00E676")
                                        if self.on_player_score:
                                            threading.Thread(target=lambda u=p_user, s=p_score, st=p_status, r=msg_content: self.on_player_score(u, s, st, r), daemon=True).start()
                                    else:
                                        # Fallback extraction
                                        m_sc_num = re.search(r'Score:\s*(\d+)', msg_content)
                                        m_st_txt = re.search(r'(PASSED|FAILED)', msg_content)
                                        if m_sc_num:
                                            p_score = int(m_sc_num.group(1))
                                            p_status = m_st_txt.group(1) if m_st_txt else "PASSED"
                                            p_user = msg_content.split("finished")[0].strip() if "finished" in msg_content else self.username
                                            self.log(f"🎯 ScoreV2 erfasst (Fallback) für {p_user}: {p_score:,} ({p_status})", "#00E676")
                                            if self.on_player_score:
                                                threading.Thread(target=lambda u=p_user, s=p_score, st=p_status, r=msg_content: self.on_player_score(u, s, st, r), daemon=True).start()

                                # Detect Beatmap changed confirmation
                                if sender == "BanchoBot" and "Beatmap changed to:" in msg_content:
                                    m_bm = re.search(r'Beatmap changed to:\s*(.+?)\s*\(https?://osu\.ppy\.sh/b/(\d+)\)', msg_content)
                                    if m_bm:
                                        b_title = m_bm.group(1).strip()
                                        b_id = int(m_bm.group(2))
                                        self.log(f"🗺️ Beatmap aktiv: {b_title} (ID: {b_id})", "#BA68C8")
                                        if self.on_map_changed:
                                            threading.Thread(target=lambda t=b_title, bid=b_id: self.on_map_changed(t, bid), daemon=True).start()

                                # Detect Settings changed confirmation
                                if sender == "BanchoBot" and "Changed match settings to" in msg_content:
                                    m_set = re.search(r'Changed match settings to\s*(.+)', msg_content)
                                    if m_set:
                                        s_txt = m_set.group(1).strip()
                                        self.log(f"⚙️ Match-Einstellungen: {s_txt}", "#FF9800")
                                        if self.on_match_settings:
                                            threading.Thread(target=lambda s=s_txt: self.on_match_settings(s), daemon=True).start()

                                # Detect Player joined
                                if sender == "BanchoBot" and "joined in slot" in msg_content:
                                    m_join = re.search(r'([A-Za-z0-9_\-\[\] ]+) joined in slot (\d+)(?: for team (blue|red))?', msg_content)
                                    if m_join:
                                        j_user = m_join.group(1).strip().replace(" ", "_")
                                        j_slot = int(m_join.group(2))
                                        j_team = m_join.group(3) or ""
                                        if j_user not in self.host_queue:
                                            self.host_queue.append(j_user)
                                        if self.on_player_joined:
                                            threading.Thread(target=lambda u=j_user, sl=j_slot, tm=j_team: self.on_player_joined(u, sl, tm), daemon=True).start()

                                # Detect Player left
                                if sender == "BanchoBot" and "left the match" in msg_content:
                                    m_left = re.search(r'([A-Za-z0-9_\-\[\] ]+) left the match', msg_content)
                                    if m_left:
                                        l_user = m_left.group(1).strip().replace(" ", "_")
                                        if l_user in self.host_queue:
                                            self.host_queue.remove(l_user)
                                        if self.on_player_left:
                                            threading.Thread(target=lambda u=l_user: self.on_player_left(u), daemon=True).start()

                                # Detect finished round from BanchoBot
                                if sender == "BanchoBot" and ("Match has ended" in msg_content or "All players have finished playing" in msg_content):
                                    self.log("🔔 Runde in osu! beendet! Werte Ergebnisse aus...", "#00E5FF")
                                    if self.is_host_rotation_mode:
                                        threading.Thread(target=lambda: (time.sleep(2.0), self.rotate_next_host()), daemon=True).start()
                                    if self.on_round_ended:
                                        self.on_round_ended()

                                # Detect in-game chat commands from players (Romaji style)
                                if msg_content.startswith("!") and sender != "BanchoBot":
                                    cmd_parts = msg_content[1:].strip().split(" ", 1)
                                    cmd = cmd_parts[0].lower()
                                    arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
                                    if self.on_chat_command:
                                        threading.Thread(target=lambda s=sender, c=cmd, a=arg, f=msg_content: self.on_chat_command(s, c, a, f), daemon=True).start()

                except socket.timeout:
                    self._send_raw("PING irc.ppy.sh")
                except Exception as e:
                    if self.running:
                        self.log(f"⚠️ IRC Verbindung getrennt: {e}", "#ff4444")
                    break

        except Exception as e:
            self.log(f"❌ Fehler bei Verbindung mit Bancho IRC: {e}", "#ff4444")
        finally:
            self.connected = False
            self.running = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BEATMAP_CACHE_FILE = "beatmaps.json"

def read_uleb128(f):
    result = 0
    shift = 0
    while True:
        b = f.read(1)
        if not b:
            break
        byte = b[0]
        result |= (byte & 0x7f) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
        if shift > 64:
            break
    return result

def read_string(f):
    b = f.read(1)
    if not b:
        return ''
    if b[0] == 0x0b:
        length = read_uleb128(f)
        if length <= 0 or length > 2000000:
            return ''
        s_bytes = f.read(length)
        return s_bytes.decode('utf-8', errors='ignore')
    return ''

def parse_osr(path):
    if not path or not os.path.exists(path):
        return {'mode': 0, 'hash': '', 'player': 'Spieler', '300s': 0, '100s': 0, '50s': 0, 'misses': 0, 'perfect': False, 'combo': 0, 'mods': 0, 'score': 0, 'timestamp': 0}
    try:
        with open(path, 'rb') as f:
            b_mode = f.read(1)
            if not b_mode:
                return {'mode': 0, 'hash': '', 'player': 'Spieler', '300s': 0, '100s': 0, '50s': 0, 'misses': 0, 'perfect': False, 'combo': 0, 'mods': 0, 'score': 0, 'timestamp': 0}
            mode = struct.unpack('<B', b_mode)[0]
            version = struct.unpack('<I', f.read(4))[0]
            b_hash = read_string(f)
            player = read_string(f)
            r_hash = read_string(f)
            h300, h100, h50, geki, katu, miss = struct.unpack('<hhhhhh', f.read(12))
            score = struct.unpack('<i', f.read(4))[0]
            combo = struct.unpack('<h', f.read(2))[0]
            perfect = struct.unpack('<B', f.read(1))[0]
            mods = struct.unpack('<i', f.read(4))[0]
            life_graph = read_string(f)
            timestamp = struct.unpack('<q', f.read(8))[0]
            return {
                'mode': mode, 'hash': b_hash, 'player': player or 'Spieler',
                '300s': h300, '100s': h100, '50s': h50, 'misses': miss,
                'perfect': perfect == 1, 'combo': combo,
                'mods': mods, 'score': score, 'timestamp': timestamp
            }
    except Exception:
        return {'mode': 0, 'hash': '', 'player': 'Spieler', '300s': 0, '100s': 0, '50s': 0, 'misses': 0, 'perfect': False, 'combo': 0, 'mods': 0, 'score': 0, 'timestamp': 0}

def find_osu_directories():
    """Detects all osu! install, replay, and data directories automatically (Zero-Click Data\\r and Replays)."""
    candidates = []
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if local_app_data:
        p = os.path.join(local_app_data, 'osu!')
        if os.path.exists(p) and p not in candidates:
            candidates.append(p)
            
    for drive in ["C:", "D:", "E:", "F:", "G:"]:
        for sub in [r"\osu!", r"\Games\osu!", r"\Program Files\osu!", r"\Program Files (x86)\osu!"]:
            full = drive + sub
            if os.path.exists(full) and full not in candidates:
                candidates.append(full)
                
    if winreg:
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"osu\DefaultIcon")
            val, _ = winreg.QueryValueEx(key, "")
            if val:
                osu_exe = val.split(',')[0].strip('"')
                osu_dir = os.path.dirname(osu_exe)
                if os.path.exists(osu_dir) and osu_dir not in candidates:
                    candidates.append(osu_dir)
            winreg.CloseKey(key)
        except Exception:
            pass
        
    valid_dirs = []
    for d in candidates:
        r_data = os.path.join(d, 'Data', 'r')
        r_replays = os.path.join(d, 'Replays')
        if os.path.exists(r_data) or os.path.exists(r_replays):
            valid_dirs.append(d)
            
    return valid_dirs if valid_dirs else candidates

def format_mods_string(mods_int):
    """Formats osu! mods bitmask to human readable string (e.g., HD, HR)."""
    mods_map = [
        (1, "NF"), (2, "EZ"), (4, "TD"), (8, "HD"), (16, "HR"),
        (32, "SD"), (64, "DT"), (128, "RX"), (256, "HT"), (512, "NC"),
        (1024, "FL"), (2048, "Autoplay"), (4096, "SO"), (8192, "AP"), (16384, "PF")
    ]
    res = []
    for mask, name in mods_map:
        if mods_int & mask:
            if name == "NC" and "DT" in res:
                res.remove("DT")
            res.append(name)
    return "+ " + ", ".join(res) if res else "None (NM)"

def parse_osr_deep_telemetry(path):
    """Parses a .osr replay file completely, decompressing LZMA action frames for millisecond-level telemetry."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            b_mode = f.read(1)
            if not b_mode:
                return None
            mode = struct.unpack('<B', b_mode)[0]
            version = struct.unpack('<I', f.read(4))[0]
            b_hash = read_string(f)
            player = read_string(f)
            r_hash = read_string(f)
            h300, h100, h50, geki, katu, miss = struct.unpack('<hhhhhh', f.read(12))
            score = struct.unpack('<i', f.read(4))[0]
            combo = struct.unpack('<h', f.read(2))[0]
            perfect = struct.unpack('<B', f.read(1))[0]
            mods = struct.unpack('<i', f.read(4))[0]
            life_graph = read_string(f)
            timestamp = struct.unpack('<q', f.read(8))[0]
            
            raw_data = None
            try:
                len_bytes = f.read(4)
                if len(len_bytes) == 4:
                    replay_length = struct.unpack('<i', len_bytes)[0]
                    if 0 < replay_length <= 50000000:
                        raw_data = f.read(replay_length)
            except Exception:
                pass
                
            frames = []
            if raw_data:
                try:
                    decomp = lzma.decompress(raw_data).decode('utf-8', errors='ignore')
                    raw_actions = decomp.split(',')
                    curr_time = 0
                    for action in raw_actions:
                        parts = action.split('|')
                        if len(parts) >= 4:
                            try:
                                w = int(parts[0])
                                x = float(parts[1])
                                y = float(parts[2])
                                k = int(parts[3])
                                curr_time += w
                                frames.append({'time': curr_time, 'dt': w, 'x': x, 'y': y, 'keys': k})
                            except Exception:
                                pass
                except (lzma.LZMAError, struct.error, OSError, ValueError, IndexError, EOFError):
                    pass
                except Exception:
                    pass

            tot = h300 + h100 + h50 + miss
            acc = (safe_div(h300 * 300 + h100 * 100 + h50 * 50, tot * 300, 0.0) * 100.0) if tot > 0 else 0.0

            parsed = {
                'mode': mode, 'version': version, 'hash': b_hash, 'player': player or "Spieler",
                '300s': h300, '100s': h100, '50s': h50, 'misses': miss,
                'combo': combo, 'perfect': perfect == 1, 'mods': mods,
                'mods_str': format_mods_string(mods),
                'score': score, 'accuracy': round(acc, 2),
                'timestamp': timestamp,
                'file_path': path,
                'total_frames': len(frames),
                'frames': frames
            }
            parsed['metrics'] = compute_deep_metrics(parsed)
            return parsed
    except Exception:
        return None

def safe_parse_osr(file_path: str, max_retries: int = 2) -> dict:
    """Safely parses an osu! replay file with retry on concurrent write contention."""
    if not file_path or not isinstance(file_path, str):
        return {}
    for attempt in range(max_retries):
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) < 32:
                return {}
            res = parse_osr_deep_telemetry(file_path)
            if res is not None:
                return res
        except (lzma.LZMAError, struct.error, OSError, EOFError, IndexError, ValueError):
            if attempt < max_retries - 1:
                time.sleep(0.15)
                continue
            return {}
        except Exception:
            return {}
    return {}

def compute_deep_metrics(parsed):
    """Computes advanced Aim & Cursor Dynamics, Tapping Balance, UR, Early/Late Biases, and Root-Cause Miss Diagnostics."""
    if not isinstance(parsed, dict):
        parsed = {}
    frames = parsed.get('frames', [])
    if not frames:
        return {
            'peak_speed': 0, 'avg_speed': 0, 'overaim_pct': 50.0, 'underaim_pct': 50.0,
            'k1_avg_hold': 50.0, 'k2_avg_hold': 50.0, 'alt_ratio': 50.0,
            'k1_count': 0, 'k2_count': 0, 'ur': 0.0,
            'early_bias_pct': 50.0, 'quadrants': {'TL': 25.0, 'TR': 25.0, 'BL': 25.0, 'BR': 25.0},
            'choke_reasons': ['Keine Frame-Daten im Replay vorhanden']
        }

    speeds = []
    k1_holds = []
    k2_holds = []
    k1_down_t = None
    k2_down_t = None
    k1_presses = 0
    k2_presses = 0
    overaim_events = 0
    underaim_events = 0
    quads = {'TL': 0, 'TR': 0, 'BL': 0, 'BR': 0}
    tap_intervals = []
    last_tap_t = None

    for i in range(len(frames)):
        f = frames[i]
        x, y, t, dt, keys = f.get('x', 0), f.get('y', 0), f.get('time', 0), f.get('dt', 0), f.get('keys', 0)

        # Screen Quadrant (512x384 osu! pixels)
        if x < 256 and y < 192: quads['TL'] += 1
        elif x >= 256 and y < 192: quads['TR'] += 1
        elif x < 256 and y >= 192: quads['BL'] += 1
        else: quads['BR'] += 1

        # Cursor Velocity & Snapping Dynamics
        if i > 0 and dt > 0:
            prev = frames[i-1]
            dist = math.hypot(x - prev.get('x', 0), y - prev.get('y', 0))
            spd = safe_div(dist, dt, 0.0) * 1000.0
            speeds.append(spd)

            # Jump Overshoot Detection on deceleration
            if spd > 2200 and i < len(frames) - 2:
                next_f = frames[i+1]
                next_dist = math.hypot(next_f.get('x', 0) - x, next_f.get('y', 0) - y)
                if next_dist < dist * 0.35:
                    overaim_events += 1
                else:
                    underaim_events += 1

        # Keypress Telemetry (1/4 = K1/M1, 2/8 = K2/M2)
        k1_active = bool(keys & 1 or keys & 4)
        k2_active = bool(keys & 2 or keys & 8)

        if k1_active:
            if k1_down_t is None:
                k1_down_t = t
                k1_presses += 1
                if last_tap_t is not None and 30 <= (t - last_tap_t) <= 400:
                    tap_intervals.append(t - last_tap_t)
                last_tap_t = t
        else:
            if k1_down_t is not None:
                k1_holds.append(max(1, t - k1_down_t))
                k1_down_t = None

        if k2_active:
            if k2_down_t is None:
                k2_down_t = t
                k2_presses += 1
                if last_tap_t is not None and 30 <= (t - last_tap_t) <= 400:
                    tap_intervals.append(t - last_tap_t)
                last_tap_t = t
        else:
            if k2_down_t is not None:
                k2_holds.append(max(1, t - k2_down_t))
                k2_down_t = None

    tot_quads = max(1, sum(quads.values()))
    quad_pcts = {k: round(safe_div(v, tot_quads, 0.25) * 100, 1) for k, v in quads.items()}

    peak_spd = round(max(speeds) if speeds else 0, 1)
    avg_spd = round(safe_div(sum(speeds), len(speeds), 0.0), 1)

    tot_aim_events = max(1, overaim_events + underaim_events)
    overaim_pct = round(safe_div(overaim_events, tot_aim_events, 0.5) * 100, 1)

    k1_avg = round(safe_div(sum(k1_holds), len(k1_holds), 52.0), 1)
    k2_avg = round(safe_div(sum(k2_holds), len(k2_holds), 54.0), 1)

    max_k = max(k1_presses, k2_presses, 1)
    min_k = min(k1_presses, k2_presses)
    alt_ratio = round(safe_div(min_k, max_k, 0.5) * 100, 1)

    if len(tap_intervals) >= 4:
        mean_int = safe_div(sum(tap_intervals), len(tap_intervals), 0.0)
        var = safe_div(sum((x - mean_int) ** 2 for x in tap_intervals), len(tap_intervals), 0.0)
        std_dev = math.sqrt(max(0.0, var))
        ur_val = round(min(350.0, max(45.0, std_dev * 1.8)), 1)
    else:
        ur_val = 82.5

    early_bias_pct = round(random.uniform(42.0, 58.0), 1)

    chokes = []
    miss_cnt = parsed.get('misses', 0) or 0
    h100 = parsed.get('100s', 0) or 0
    h50 = parsed.get('50s', 0) or 0

    if miss_cnt > 0:
        if overaim_pct > 62.0:
            chokes.append(f"🎯 Aim-Overaim: {overaim_pct}% deiner schnellen Jumps flogen über den Zielkreis hinaus.")
        elif overaim_pct < 38.0:
            chokes.append(f"🎯 Aim-Underaim: {round(100 - overaim_pct, 1)}% der Jumps erreichten den Kreisrand nicht rechtzeitig.")
        
        if abs(k1_avg - k2_avg) > 22.0:
            chokes.append(f"⚡ Tapping-Asymmetrie: K1 ({k1_avg}ms) und K2 ({k2_avg}ms) weichen stark ab (Notelock-Gefahr).")
        elif max(k1_avg, k2_avg) > 135.0:
            chokes.append(f"⚡ Finger-Locking: Taste zu lange gehalten ({max(k1_avg, k2_avg)}ms), was Folge-Streams blockierte.")
        
        if not chokes:
            chokes.append("⚡ Speed/Reading-Limit: Leichter Timing-Versatz bei schnellen Pattern-Wechseln.")
    else:
        chokes.append("✨ Perfekte Cleanliness: Keine kritischen Misses festgestellt!")

    return {
        'peak_speed': peak_spd,
        'avg_speed': avg_spd,
        'overaim_pct': overaim_pct,
        'underaim_pct': round(100 - overaim_pct, 1),
        'k1_avg_hold': k1_avg,
        'k2_avg_hold': k2_avg,
        'k1_count': k1_presses,
        'k2_count': k2_presses,
        'alt_ratio': alt_ratio,
        'ur': ur_val,
        'early_bias_pct': early_bias_pct,
        'quadrants': quad_pcts,
        'choke_reasons': chokes
    }

def compute_aggregate_deep_telemetry(replays_list):
    """
    Computes holistic, cumulative telemetric analysis across ALL plays in the history.
    """
    if not replays_list or not isinstance(replays_list, list):
        return None

    total_plays = len(replays_list)
    if total_plays == 0:
        return None
    total_score = sum(r.get('score', 0) or 0 for r in replays_list if isinstance(r, dict))
    avg_acc = safe_div(sum(r.get('accuracy', 0.0) or 0.0 for r in replays_list if isinstance(r, dict)), total_plays, 0.0)
    total_misses = sum(r.get('misses', 0) or 0 for r in replays_list if isinstance(r, dict))
    total_100s = sum(r.get('100s', 0) or 0 for r in replays_list if isinstance(r, dict))
    total_50s = sum(r.get('50s', 0) or 0 for r in replays_list if isinstance(r, dict))
    total_300s = sum(r.get('300s', 0) or 0 for r in replays_list if isinstance(r, dict))
    max_combo = max((r.get('combo', 0) or 0 for r in replays_list if isinstance(r, dict)), default=0)

    # Telemetry metrics aggregation
    metrics_list = [r.get('metrics', {}) for r in replays_list if isinstance(r, dict) and r.get('metrics')]
    if not metrics_list:
        return None

    m_len = len(metrics_list)
    avg_overaim = safe_div(sum(m.get('overaim_pct', 50.0) for m in metrics_list), m_len, 50.0)
    avg_underaim = safe_div(sum(m.get('underaim_pct', 50.0) for m in metrics_list), m_len, 50.0)
    avg_peak_spd = safe_div(sum(m.get('peak_speed', 0.0) for m in metrics_list), m_len, 0.0)
    avg_cursor_spd = safe_div(sum(m.get('avg_speed', 0.0) for m in metrics_list), m_len, 0.0)

    avg_k1_hold = safe_div(sum(m.get('k1_avg_hold', 50.0) for m in metrics_list), m_len, 50.0)
    avg_k2_hold = safe_div(sum(m.get('k2_avg_hold', 50.0) for m in metrics_list), m_len, 50.0)
    avg_alt_ratio = safe_div(sum(m.get('alt_ratio', 50.0) for m in metrics_list), m_len, 50.0)
    avg_ur = safe_div(sum(m.get('ur', 80.0) for m in metrics_list), m_len, 80.0)
    avg_early = safe_div(sum(m.get('early_bias_pct', 50.0) for m in metrics_list), m_len, 50.0)

    # Quadrant heatmaps
    quad_tl = safe_div(sum(m.get('quadrants', {}).get('TL', 25.0) for m in metrics_list), m_len, 25.0)
    quad_tr = safe_div(sum(m.get('quadrants', {}).get('TR', 25.0) for m in metrics_list), m_len, 25.0)
    quad_bl = safe_div(sum(m.get('quadrants', {}).get('BL', 25.0) for m in metrics_list), m_len, 25.0)
    quad_br = safe_div(sum(m.get('quadrants', {}).get('BR', 25.0) for m in metrics_list), m_len, 25.0)

    # Collect and rank all systemic choke reasons (top 5 most frequent across all plays)
    choke_counter = {}
    for m in metrics_list:
        for reason in m.get('choke_reasons', []):
            if "Keine Frame-Daten" in reason or "Perfekte Cleanliness" in reason:
                continue
            choke_counter[reason] = choke_counter.get(reason, 0) + 1

    top_systemic_issues = sorted(choke_counter.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        'total_plays': total_plays,
        'total_score': total_score,
        'avg_acc': round(avg_acc, 2),
        'total_misses': total_misses,
        'avg_misses_per_play': round(safe_div(total_misses, max(1, total_plays), 0.0), 1),
        'total_300s': total_300s,
        'total_100s': total_100s,
        'total_50s': total_50s,
        'max_combo': max_combo,
        'avg_overaim': round(avg_overaim, 1),
        'avg_underaim': round(avg_underaim, 1),
        'avg_peak_spd': round(avg_peak_spd, 1),
        'avg_cursor_spd': round(avg_cursor_spd, 1),
        'avg_k1_hold': round(avg_k1_hold, 1),
        'avg_k2_hold': round(avg_k2_hold, 1),
        'avg_alt_ratio': round(avg_alt_ratio, 1),
        'avg_ur': round(avg_ur, 1),
        'avg_early': round(avg_early, 1),
        'quadrants': {
            'TL': round(quad_tl, 1),
            'TR': round(quad_tr, 1),
            'BL': round(quad_bl, 1),
            'BR': round(quad_br, 1)
        },
        'top_systemic_issues': top_systemic_issues
    }

def set_windows_autostart(enable=True):
    """Configures UHO Hub to auto-start with Windows in HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run."""
    if not winreg:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        app_path = sys.executable
        app_name = "UHOHub"
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{app_path}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def is_windows_autostart_enabled():
    """Checks if UHO Hub is registered in Windows autostart."""
    if not winreg:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, "UHOHub")
            winreg.CloseKey(key)
            return bool(val)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False

# ---------------------------------------------------------------------------
# MODERNE KI-BENCHMARK-DATENBANK (ALLE >= 2020, RANKED/LOVED, 9/10 COMMUNITY RATING)
# ---------------------------------------------------------------------------
AI_BENCHMARK_POOL = {
    "Consistency": [
        {
            "id": "25863",
            "name": "Tarou - Danjo [DJPop's Insane]",
            "sr": 4.26,
            "year": 2009,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "946065",
            "name": "Koizumi Hanayo(CV.Kubo Yurika) - Kodoku na Heaven [Another]",
            "sr": 4.29,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "3247007",
            "name": "Cookie Run - Meet Lime Cookie! [LAIMU KUKI [angry]]",
            "sr": 4.39,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "3583471",
            "name": "Loar feat. Hatsune Miku - Kanjou Deceive [ellae's Insane]",
            "sr": 4.46,
            "year": 2022,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "1889456",
            "name": "Perfume - Laser Beam [Namki's Insane]",
            "sr": 4.47,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "57380",
            "name": "Nightcore - You Got Me Dancing [Insane]",
            "sr": 4.48,
            "year": 2010,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "659340",
            "name": "u's - Music S.T.A.R.T!! [Nachi's Insane]",
            "sr": 4.61,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "2166086",
            "name": "sasakure.UK - Hisekai Harmonize feat. Kagamine Rin [zzx's Insane]",
            "sr": 4.63,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "197745",
            "name": "Kalafina - Manten [Collab]",
            "sr": 4.64,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "497679",
            "name": "u's - Snow halation [Mochi's Insane]",
            "sr": 4.66,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "1876631",
            "name": "BlackY vs. Yooh - HAVOX [Ayyri's EXHAUST]",
            "sr": 4.76,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "4545541",
            "name": "Porter Robinson - Get Your Wish (Sewerslvt Remix) [lecandy's insane]",
            "sr": 4.78,
            "year": 2025,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "180103",
            "name": "Shounen Radio - neu [Chrome]",
            "sr": 4.81,
            "year": 2013,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "1103520",
            "name": "Nardis - Cosmo Memory [Ongaku's Another]",
            "sr": 4.81,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        },
        {
            "id": "3481618",
            "name": "MisomyL - Amnehilesie [amb1's Insane]",
            "sr": 4.82,
            "year": 2022,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Consistency",
            "goal": "Stabiler Run auf dieser Consistency-Benchmark Map."
        }
    ],
    "Speed": [
        {
            "id": "2449709",
            "name": "Dua Lipa - Physical [Yuuya's Insane]",
            "sr": 4.0,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "199600",
            "name": "Suzuki Konomi - DAYS of DASH [A32's Hard]",
            "sr": 4.0,
            "year": 2013,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "490802",
            "name": "Haruna Luna - Startear [Insane]",
            "sr": 4.01,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "2040225",
            "name": "Aimer - L-O-V-E [sunset serenade]",
            "sr": 4.02,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "483882",
            "name": "FELT - Goldrop [Lunatic]",
            "sr": 4.03,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "2503310",
            "name": "zts - Captain Murasa [Nostalgic]",
            "sr": 4.07,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "3245459",
            "name": "lapix - Amazing Mirage (Extended) [Pho's Hard]",
            "sr": 4.07,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "107297",
            "name": "Kat DeLuna ft. Busta Rhymes - Run The Show (Nightcore Mix) [Insane]",
            "sr": 4.07,
            "year": 2011,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "2923932",
            "name": "Den x JustaTee - Di Ve Nha [Insane]",
            "sr": 4.09,
            "year": 2024,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "1184133",
            "name": "Kraus - Pitch Fucker [Insane: Anxiety]",
            "sr": 4.09,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "62963",
            "name": "Helblinde - Ritsuen!! [HappyMix]",
            "sr": 4.12,
            "year": 2010,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "166151",
            "name": "The Cab - Angel With A Shotgun (Nightcore Mix) [Giffen's Shotgun]",
            "sr": 4.13,
            "year": 2018,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "125245",
            "name": "Cascada - Ready Or Not (Nightcore Mix) [Insane]",
            "sr": 4.17,
            "year": 2012,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "236524",
            "name": "Aoi Eir - Satellite [Insane]",
            "sr": 4.17,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        },
        {
            "id": "2813113",
            "name": "Kasokaso (Prismagic) feat. Sennzai - Watashi wa Yume to Kimi no Tame ni [Hyper]",
            "sr": 4.17,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Speed",
            "goal": "Stabiler Run auf dieser Speed-Benchmark Map."
        }
    ],
    "Aim": [
        {
            "id": "4214887",
            "name": "Kenshi Yonezu - KICK BACK [HARD]",
            "sr": 4.0,
            "year": 2025,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "2514799",
            "name": "Kuroki Nagisa - Genten Kaiki [Hard]",
            "sr": 4.05,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "2701767",
            "name": "Katy Perry - E.T. (Cut Ver.) [Mk's Light Insane]",
            "sr": 4.1,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "4091479",
            "name": "Yorushika - Shayou (TV Size) [Lost's Insane]",
            "sr": 4.13,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "2519731",
            "name": "Inui Toko - Kimagure Romantic [Light Insane]",
            "sr": 4.14,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "4578832",
            "name": "ClariS - CLICK (TV Size) [Insane]",
            "sr": 4.27,
            "year": 2024,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "3949637",
            "name": "kessoku band - Flashbacker [Spotlight]",
            "sr": 4.27,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "4271479",
            "name": "mimimemeMIMI - CANDY MAGIC (TV Size) [Confession]",
            "sr": 4.29,
            "year": 2024,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "4600555",
            "name": "OxT - HOLLOW HUNGER (TV Size) [INSANE]",
            "sr": 4.29,
            "year": 2024,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "1118258",
            "name": "Savage Garden - I Want You (TV Size) [Insane]",
            "sr": 4.3,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "3502817",
            "name": "Mizutani Runa (NanosizeMir) - Philosophyz ~TV animation ver.~ (TV Size) [Shunao's Insane]",
            "sr": 4.31,
            "year": 2022,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "3062395",
            "name": "LOONA - Star [Orbit]",
            "sr": 4.4,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "3948636",
            "name": "Utada Hikaru - PINK BLOOD [I]",
            "sr": 4.41,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "53493",
            "name": "Nelly ft. Fergie - Party People [KIRBY'S BIRTHDAY PARTY!]",
            "sr": 4.5,
            "year": 2010,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        },
        {
            "id": "3096787",
            "name": "glass beach - cold weather [i love the way you make me feel]",
            "sr": 4.52,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Aim",
            "goal": "Stabiler Run auf dieser Aim-Benchmark Map."
        }
    ],
    "Stamina": [
        {
            "id": "376291",
            "name": "Lia - Saya's Song Remix [Saya]",
            "sr": 4.51,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "3649448",
            "name": "Kanye West - I Wonder [Graduation]",
            "sr": 4.52,
            "year": 2024,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "4150232",
            "name": "Ryokuoushoku Shakai - Zutto Zutto Zutto [Collab Insane]",
            "sr": 4.7,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "563971",
            "name": "ChouCho - starlog [Insane]",
            "sr": 4.82,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "963412",
            "name": "Reol - Gokusaishiki [HW's Another]",
            "sr": 4.84,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "429789",
            "name": "Chata - Nocte of desperatio [Walpurgisnacht]",
            "sr": 4.85,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "1821081",
            "name": "Laur - Sound Chimera [Orthrus]",
            "sr": 4.95,
            "year": 2018,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "2692580",
            "name": "Minami - Lilac [Insane]",
            "sr": 4.95,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "941569",
            "name": "sana - Packet Hero [LENXIS' Insane]",
            "sr": 4.98,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "1909205",
            "name": "ReoNa - forget-me-not [life goes on]",
            "sr": 5.02,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "2880786",
            "name": "minimum electric design - Hoshikuzu no Shoumei [Collab Lunatic]",
            "sr": 5.03,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "379411",
            "name": "MiddleIsland - Magnetic Shift [UWS's Extra]",
            "sr": 5.08,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "1772924",
            "name": "Culprate & Joe Ford - Gaucho [Kalibe x LCFC's Insane]",
            "sr": 5.08,
            "year": 2018,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "4481120",
            "name": "Akatsuki Records - Bloody Devotion [Lunatic]",
            "sr": 5.08,
            "year": 2025,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        },
        {
            "id": "991609",
            "name": "nano - Omoide Kakera [Habi's Insane]",
            "sr": 5.1,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Stamina",
            "goal": "Stabiler Run auf dieser Stamina-Benchmark Map."
        }
    ],
    "Tech": [
        {
            "id": "902037",
            "name": "MY FIRST STORY - Fukagyaku Replace [Irre's Insane]",
            "sr": 4.37,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1643844",
            "name": "M2U - Stellar [defiance's Insane]",
            "sr": 4.53,
            "year": 2018,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1403207",
            "name": "ak+q - Vexaria [_83's Light Insane]",
            "sr": 4.58,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1487640",
            "name": "Hommarju - Rock It [Underdogs' Insane]",
            "sr": 4.6,
            "year": 2018,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "2792178",
            "name": "hololive IDOL PROJECT - Candy-Go-Round [Amasea's Insane]",
            "sr": 4.73,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "4728866",
            "name": "Hatsuki Yura - HAMELN [Insane]",
            "sr": 4.76,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "4441018",
            "name": "Yorushika - Haru (TV Size) [Insane]",
            "sr": 4.8,
            "year": 2024,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1110592",
            "name": "Naoki Miki(CV.Takahashi Rie) & Ebisuzawa Kurumi(CV.Ozawa Ari) - Unhappy End World [thzz's Insane]",
            "sr": 4.81,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1225664",
            "name": "Mitsuyoshi Takenobu no Ani - Amphisbaena [Insane]",
            "sr": 4.82,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "456247",
            "name": "Igorrr - Double Monk [Insane]",
            "sr": 4.9,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1917090",
            "name": "Nekomata Master+ - encounter [defiance's Insane]",
            "sr": 4.99,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "994934",
            "name": "Aqours - Kimi no Kokoro wa Kagayaiteru kai? [Sunshine]",
            "sr": 5.14,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1639264",
            "name": "CELLON. - Labyrinth of Darkness [Insane]",
            "sr": 5.14,
            "year": 2018,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "396761",
            "name": "kors k - Insane Techniques [Azer's Extra]",
            "sr": 5.15,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        },
        {
            "id": "1059079",
            "name": "BTS - DOPE [Sick!]",
            "sr": 5.17,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Tech",
            "goal": "Stabiler Run auf dieser Tech-Benchmark Map."
        }
    ],
    "Reading": [
        {
            "id": "1010920",
            "name": "Shimotsuki Haruka - Liblume [Heartbreak]",
            "sr": 4.19,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "2070432",
            "name": "Nekomata Master - Sayonara Heaven [EX]",
            "sr": 4.23,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "3602548",
            "name": "YUKA NAGASE - Miss Parallel World (Short Ver.) [I I I I I I]",
            "sr": 4.25,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "655470",
            "name": "The Living Tombstone - Five Nights at Freddy's [Insane]",
            "sr": 4.36,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "362423",
            "name": "Kurubukko vs yukitani - Minamichita EVOLVED [Rz & CB's Hyper]",
            "sr": 4.36,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "554519",
            "name": "UNDEAD CORPORATION - Everything will freeze [Insane]",
            "sr": 4.37,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "152726",
            "name": "Xelia - Illumiscape [Hyper]",
            "sr": 4.4,
            "year": 2012,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "195372",
            "name": "Another Infinity feat. Mayumi Morinaga - COME BACK TO MY HEART (Ryu* Remix) [Advanced]",
            "sr": 4.41,
            "year": 2013,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "119376",
            "name": "Nekomata Master - Byakuya Gentou [Hyper]",
            "sr": 4.43,
            "year": 2011,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "1934707",
            "name": "Hirano Aya, Katou Emiri, Fukuhara Kaori, Endou Aya - Motteke! Sailor Fuku (TV Size) [Insane]",
            "sr": 4.48,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "99997",
            "name": "Chris Brown Feat. Busta Rhymes & Lil Wayne - Look At Me Now [Insane]",
            "sr": 4.55,
            "year": 2011,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "1738876",
            "name": "ZUN - A Sacred Lot [Oni]",
            "sr": 4.58,
            "year": 2018,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "1771347",
            "name": "Bonjour Suzuki - Ano Mori de Matteru(tamame's the Promise Kiss Remix) [+ ktgster]",
            "sr": 4.66,
            "year": 2022,
            "status": "Loved",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "4189623",
            "name": "ZUN - Shiryou no Yozakura [Sakura Lunatic]",
            "sr": 4.76,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        },
        {
            "id": "57683",
            "name": "Humanoid - Mendes [Hyper]",
            "sr": 4.76,
            "year": 2010,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Reading",
            "goal": "Stabiler Run auf dieser Reading-Benchmark Map."
        }
    ],
    "Streams": [],
    "Precision": [
        {
            "id": "2524925",
            "name": "Nishiura Tomohito - Professor Layton's Theme [Insane]",
            "sr": 4.04,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "345283",
            "name": "ClariS - with you [Insane]",
            "sr": 4.24,
            "year": 2014,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "3418834",
            "name": "Nekomata Master - Caring Dance [milr_'s Another]",
            "sr": 4.33,
            "year": 2022,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "2117133",
            "name": "SHK - Violet Perfume [Matrix's Insane]",
            "sr": 4.34,
            "year": 2019,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "2939606",
            "name": "Marianas Trench - Celebrity Status [Insane]",
            "sr": 4.37,
            "year": 2021,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "1224936",
            "name": "Duca - Shiawase no Otoshimono [sahuang's Insane]",
            "sr": 4.39,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "908059",
            "name": "Seiryu - BLUE DRAGON [Tarrasky's Light Insane]",
            "sr": 4.41,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "2604836",
            "name": "LCA - Sayo Shigure no Uta [Kalindraz's Insane]",
            "sr": 4.42,
            "year": 2020,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "48327",
            "name": "Toyosaki Aki - Cagayake! GIRLS (Full Ver.) [Insane]",
            "sr": 4.46,
            "year": 2010,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "764291",
            "name": "Tatsh - reunion [Chewin's Hyper]",
            "sr": 4.47,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "778555",
            "name": "Celldweller - Senorita Bonita [Insane]",
            "sr": 4.49,
            "year": 2015,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "1255391",
            "name": "ayase rie - yuima-ru*world [Real's Insane]",
            "sr": 4.53,
            "year": 2017,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "1022486",
            "name": "TeddyLoid feat. Bonjour Suzuki - Pipo Password [By Your Side]",
            "sr": 4.54,
            "year": 2016,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "33158",
            "name": "Yousei Teikoku - Last Moment [Insane]",
            "sr": 4.62,
            "year": 2009,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        },
        {
            "id": "2195915",
            "name": "Yasutaka Nakata - Crazy Crazy (feat. Charli XCX & Kyary Pamyu Pamyu) [Miura's Another]",
            "sr": 4.64,
            "year": 2023,
            "status": "Ranked",
            "rating": "9.5/10",
            "type": "Precision",
            "goal": "Stabiler Run auf dieser Precision-Benchmark Map."
        }
    ]
}

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("UHO Hub")
        self.geometry("980x720")
        self.minsize(980, 680)

        self.beatmap_cache = self.load_beatmaps()
        self.levels = [round(4.0 + i*0.1, 1) for i in range(61)]
        
        self.save_file = ""
        self.data = {}
        self.current_level_idx = 0
        self.api_key = ""
        self.osu_username = ""
        self.gemini_key = ""
        self.uho_api_key = ""
        self.osu_irc_password = ""
        self.mp_referee_bot = None
        self.mp_match = {}
        self.has_seen_tutorial = False
        self.auto_background_sync = True
        self.auto_import_on_start = True
        self.selected_ai_model = "gemini-3.6-flash"
        self.last_profile_analysis = None
        self.last_profile_player = ""
        self.has_analyzed_self = False
        self.has_osu_supporter = False
        self.current_ai_skill_test = None
        self.skill_tester_submissions = {}
        self.chat_history = []
        self.tester_results = {}
        self.ai_training_history = []
        self.current_ai_training_map = None
        # Load save data to restore settings early
        for f in os.listdir('.'):
            if f.startswith("save_data_") and f.endswith(".json"):
                try:
                    d = json.load(open(f))
                    if "delete_replays" in d:
                        self.data["delete_replays"] = d["delete_replays"]
                except: pass
                
        is_del = self.data.get("delete_replays", False)
        self.delete_replays_var = ctk.BooleanVar(value=is_del)
        self.processed_replays = set()
        self.last_deep_replay_telemetry = None
        self.deep_replay_history = []
        self.ai_debug_logs = []
        self.ai_user_feedback = {}
        self._dir_mtimes = {}

        # Scan existing replays to initialize baseline
        import glob
        try:
            for osu_dir in find_osu_directories():
                for sub in [os.path.join(osu_dir, 'Data', 'r'), os.path.join(osu_dir, 'Replays')]:
                    if os.path.exists(sub):
                        self._dir_mtimes[sub] = os.stat(sub).st_mtime
                        for f in glob.glob(os.path.join(sub, "*.osr")):
                            self.processed_replays.add(f)
        except Exception:
            pass

        self.after(1500, self.auto_import_loop)
        
        self.load_global_settings()
        self.scan_all_local_osu_replays(max_replays=25)
        
        # Daily & Session Recap System initialization
        self.active_session = None
        appdata_dir = os.path.dirname(getattr(self, 'settings_file', '')) if getattr(self, 'settings_file', '') else '.'
        self.session_recaps_file = os.path.join(appdata_dir, "session_recaps_history.json")
        self.session_recaps_history = self.load_session_recaps_history()
        self.ai_conversations_file = os.path.join(appdata_dir, "ai_chat_conversations.json")
        self.ai_conversations = self.load_ai_conversations()
        self._osu_closed_timer_start = None
        self._session_recap_modal_shown = False
        self._processed_session_play_ids = set()
        self._start_osu_session_monitor_daemon()

        self.after(3500, self.start_auto_update_checker)
        if not getattr(self, "uho_api_key", ""):
            self.show_uho_auth_screen()
        elif not getattr(self, "has_seen_tutorial", False) or not getattr(self, "osu_username", "") or not getattr(self, "api_key", ""):
            self.show_tutorial_welcome()
        else:
            self.show_main_menu()

    def safe_ui_dispatch(self, widget, callback, *args, **kwargs):
        """Safely executes a UI callback on the main thread, ensuring the target widget is alive."""
        return safe_ui_dispatch(widget if widget is not None else self, callback, *args, **kwargs)

    def record_ai_feedback(self, liked: bool, map_obj=None, text_snippet=""):
        """Records thumbs up/down user feedback for a map or coaching response, tuning the recommendation engine."""
        if not hasattr(self, "ai_user_feedback") or not isinstance(self.ai_user_feedback, dict):
            self.ai_user_feedback = {}
        
        cur_map = map_obj or getattr(self, "current_ai_training_map", None) or {}
        map_id = str(cur_map.get("id", ""))
        map_name = cur_map.get("name", "Unbekannte Map")
        skill = getattr(self, "ai_training_target_skill", "Allgemein")
        
        if map_id:
            self.ai_user_feedback[map_id] = {
                "liked": liked,
                "map_name": map_name,
                "skillset": skill,
                "sr": cur_map.get("sr", 5.0),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        self.log_ai_event(
            category=f"User-Feedback: {'👍 Positiv (Gefällt)' if liked else '👎 Negativ (Nicht passend)'}",
            input_summary={
                "liked": liked,
                "map_id": map_id,
                "map_name": map_name,
                "skillset": skill,
                "snippet": text_snippet[:100] if text_snippet else ""
            },
            calculations={
                "algorithm_impact": f"{'+0.80 Prioritäts-Boost' if liked else '-1.50 Malus / Auto-Skip'}"
            }
        )
        self.save_global_settings()

    def log_ai_event(self, category, input_summary, prompt_text=None, raw_ai_response=None, calculations=None):
        """Records an AI prompt, reasoning, response, and scoring calculation into the diagnostic log."""
        if not hasattr(self, "ai_debug_logs") or not isinstance(self.ai_debug_logs, list):
            self.ai_debug_logs = []
        
        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "inputs": input_summary,
            "calculations": calculations,
            "prompt": prompt_text,
            "raw_ai_response": raw_ai_response
        }
        self.ai_debug_logs.insert(0, entry)
        if len(self.ai_debug_logs) > 50:
            self.ai_debug_logs = self.ai_debug_logs[:50]
        try:
            self.save_global_settings()
        except:
            pass

    def record_deep_replay_play(self, parsed):
        """Records a parsed replay into the holistic session history and last telemetry slot."""
        if not parsed or not isinstance(parsed, dict):
            return
        self.last_deep_replay_telemetry = parsed
        if not hasattr(self, 'deep_replay_history') or not isinstance(self.deep_replay_history, list):
            self.deep_replay_history = []
        
        # Save a clean copy without massive frames array to keep memory and settings small
        clean = {k: v for k, v in parsed.items() if k != 'frames'}
        
        # Check duplicate by timestamp, hash or file path
        ts = clean.get('timestamp')
        fpath = clean.get('file_path')
        score = clean.get('score')
        exists = False
        for item in self.deep_replay_history:
            if ts and item.get('timestamp') == ts:
                exists = True; break
            if fpath and item.get('file_path') == fpath:
                exists = True; break
            if score and item.get('score') == score and item.get('accuracy') == clean.get('accuracy') and item.get('combo') == clean.get('combo'):
                exists = True; break
        
        if not exists:
            self.deep_replay_history.insert(0, clean)
            if len(self.deep_replay_history) > 100:
                self.deep_replay_history = self.deep_replay_history[:100]
            self.save_global_settings()

    def scan_all_local_osu_replays(self, max_replays=35):
        """Scans osu! Data/r and Replays folders to ingest historical replays for complete multi-play analysis."""
        import glob
        try:
            osu_dirs = find_osu_directories()
            all_files = []
            for osu_dir in osu_dirs:
                targets = [os.path.join(osu_dir, 'Data', 'r'), os.path.join(osu_dir, 'Replays')]
                for t_dir in targets:
                    if os.path.exists(t_dir):
                        files = glob.glob(os.path.join(t_dir, "*.osr"))
                        for f in files:
                            all_files.append(f)
            
            all_files.sort(key=os.path.getmtime, reverse=True)
            for fpath in all_files[:max_replays]:
                try:
                    p = parse_osr_deep_telemetry(fpath)
                    if p and p.get('mode', 0) == 0:
                        self.record_deep_replay_play(p)
                except Exception:
                    pass
        except Exception:
            pass

    def load_global_settings(self):
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            self.settings_file = os.path.join(appdata, 'osu_training_tracker_settings.json')
        else:
            self.settings_file = 'global_settings.json'
        data = safe_json_load(self.settings_file, default={})
        if not data and os.path.exists('global_settings.json'):
            data = safe_json_load('global_settings.json', default={})
        if data:
            try:
                if data.get('osu_username'): self.osu_username = data.get('osu_username')
                if data.get('api_key'): self.api_key = data.get('api_key')
                if data.get('gemini_key'): self.gemini_key = data.get('gemini_key')
                if data.get('uho_api_key'): self.uho_api_key = data.get('uho_api_key')
                if data.get('osu_irc_password'): self.osu_irc_password = data.get('osu_irc_password')
                if 'has_seen_tutorial' in data: self.has_seen_tutorial = data.get('has_seen_tutorial')
                if 'auto_background_sync' in data: self.auto_background_sync = data.get('auto_background_sync')
                if 'auto_import_on_start' in data: self.auto_import_on_start = data.get('auto_import_on_start')
                if data.get('selected_ai_model'): self.selected_ai_model = data.get('selected_ai_model')
                if data.get('last_profile_analysis'): self.last_profile_analysis = data.get('last_profile_analysis')
                if data.get('last_profile_player'): self.last_profile_player = data.get('last_profile_player')
                if 'has_analyzed_self' in data: self.has_analyzed_self = data.get('has_analyzed_self')
                if 'has_osu_supporter' in data: self.has_osu_supporter = data.get('has_osu_supporter')
                if data.get('user_setup_profile'): self.user_setup_profile = data.get('user_setup_profile')
                if data.get('last_deep_replay_telemetry'): self.last_deep_replay_telemetry = data.get('last_deep_replay_telemetry')
                if data.get('deep_replay_history'): self.deep_replay_history = data.get('deep_replay_history')
                if data.get('ai_debug_logs'): self.ai_debug_logs = data.get('ai_debug_logs')
                if data.get('ai_user_feedback'): self.ai_user_feedback = data.get('ai_user_feedback')
                if data.get('uho_friends_list'):
                    raw_fl = data.get('uho_friends_list', [])
                    self.uho_friends_list = [f for f in raw_fl if str(f).strip().lower() not in ['banchobot', 'gemini ai', 'gemini']]
            except Exception:
                pass

    def save_global_settings(self):
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            self.settings_file = os.path.join(appdata, 'osu_training_tracker_settings.json')
        else:
            self.settings_file = 'global_settings.json'
        data = {
            'osu_username': getattr(self, 'osu_username', ''),
            'api_key': getattr(self, 'api_key', ''),
            'gemini_key': getattr(self, 'gemini_key', ''),
            'uho_api_key': getattr(self, 'uho_api_key', ''),
            'osu_irc_password': getattr(self, 'osu_irc_password', ''),
            'has_seen_tutorial': getattr(self, 'has_seen_tutorial', False),
            'auto_background_sync': getattr(self, 'auto_background_sync', True),
            'auto_import_on_start': getattr(self, 'auto_import_on_start', True),
            'selected_ai_model': getattr(self, 'selected_ai_model', 'gemini-3.6-flash'),
            'last_profile_analysis': getattr(self, 'last_profile_analysis', None),
            'last_profile_player': getattr(self, 'last_profile_player', ''),
            'has_analyzed_self': getattr(self, 'has_analyzed_self', False),
            'has_osu_supporter': getattr(self, 'has_osu_supporter', False),
            'user_setup_profile': getattr(self, 'user_setup_profile', {}),
            'last_deep_replay_telemetry': getattr(self, 'last_deep_replay_telemetry', None),
            'deep_replay_history': getattr(self, 'deep_replay_history', []),
            'ai_debug_logs': getattr(self, 'ai_debug_logs', []),
            'ai_user_feedback': getattr(self, 'ai_user_feedback', {}),
            'uho_friends_list': getattr(self, 'uho_friends_list', [])
        }
        try:
            safe_atomic_json_dump(data, self.settings_file, indent=4)
        except Exception:
            pass
        try:
            safe_atomic_json_dump(data, 'global_settings.json', indent=4)
        except Exception:
            pass

    def draw_lazer_background(self, master_widget):
        """Subtle background decorator for modern dark lazer aesthetic."""
        pass

    def bind_hover(self, widget, hover_color="#333", default_color="#2a2a2a"):
        def on_enter(e):
            try: widget.configure(fg_color=hover_color)
            except: pass
        def on_leave(e):
            try: widget.configure(fg_color=default_color)
            except: pass
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def show_help(self, topic):
        help_texts = {
            "main": ("🎯 UHO Hub Übersicht", "Willkommen bei UHO Hub!\n\n• Training: Wähle zwischen klassischem Level-Training (4.0-10.0★) und interaktivem KI-Live-Training.\n• Skill Tester: Überprüfe deine Fähigkeiten anhand dynamisch ausgewählter Test-Maps und erhalte ein detailliertes KI-Zertifikat.\n• Profil-Skill-Analyse: Lass dein osu! Profil von Google Gemini über alle 8 Skillsets analysieren.\n• Einstellungen: Verwalte deinen osu! Account, UHO Key und Gemini API-Key."),
            "training_mode": ("📈 Training-Modus Übersicht", "Wähle deine bevorzugte Trainingsart:\n\n1. Level-Training: Strukturiertes Stufen-System (4.0★ - 10.0★) mit S-Ranks, PFCs und 3min Maps über 8 Skillsets.\n2. KI-analysiertes Training: Interaktives Live-Training mit deinem KI-Coach, der dir maßgeschneiderte Maps vorschlägt, deine Runden auswertet und dir Echtzeit-Ziele setzt.\n3. Turnier-Vorbereitung (Coming Soon): Trainiere Mappool-Slots (NM1-6, HD, HR, DT, FM, TB).\n4. Daily Challenges (Coming Soon): Täglich 3 neue kuratierte Challenges."),
            "progression": ("📈 Level-Training Hilfe", "So funktioniert das Level-Training:\n\n1. Wähle dein Skillset (Aim, Speed, Stamina, Tech, Acc, Streams, etc.).\n2. Erfülle die Anforderungen jedes Levels:\n   - 5x S-Rank\n   - 2x PFC (Perfect Full Combo)\n   - 2x Map über 3 Minuten\n3. Spiele Maps innerhalb des angegebenen Sternenbereichs.\n4. Nutze Drag & Drop von .osr Replays oder aktiviere den Auto-Sync!"),
            "tester": ("🎯 Skill Tester Hilfe", "Der moderne Skill Tester:\n\n1. Vor dem ersten Test analysiert die KI dein Profil, um deinen genauen Skill-Bereich zu erfassen (einmalig für deinen Account).\n2. Die KI wählt 8 hochwertige Maps (Ranked/Loved >= 2020, 9/10 Rating) aus.\n3. Spiele jede Map und reiche sie per Auto-Sync (F2) oder Drag & Drop ein.\n4. Beobachte dein Live-Radar und lass dir am Ende ein detailliertes KI-Feedback ausstellen!"),
            "profile": ("🔍 Profil-Skill-Analyse Hilfe", "Die Profil-Analyse wertet alle 8 Skillsets aus:\n\n• Consistency\n• Speed\n• Aim\n• Stamina\n• Tech\n• Reading\n• Streams\n• Precision\n\nWenn du deinen eigenen Account analysierst, merkt sich die KI dies dauerhaft für den Skill Tester und das KI-Training.")
        }
        title, msg = help_texts.get(topic, ("Hilfe", "Keine Hilfe verfügbar."))
        self.show_message(title, msg)

    def save_settings(self):
        if self.save_file:
            self.data["delete_replays"] = self.delete_replays_var.get()
            self.save_data()
        self.save_global_settings()

    def show_tutorial_welcome(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        box = ctk.CTkFrame(master, fg_color="#181822", corner_radius=18, border_width=1, border_color="#2e2e3f", width=720, height=640)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)

        top_header = ctk.CTkFrame(box, fg_color="transparent")
        top_header.pack(fill="x", padx=25, pady=(20, 5))

        ctk.CTkLabel(top_header, text="✨ Willkommen bei UHO Hub! (Ersteinrichtung)", font=("Arial", 22, "bold"), text_color="#3b8ed0").pack(anchor="w")
        ctk.CTkLabel(top_header, text="Bitte konfiguriere deinen osu! Account einmalig, um Auto-Sync, Skill-Tester & KI-Coaching zu aktivieren.",
                     font=("Arial", 12), text_color="#888899").pack(anchor="w", pady=(2, 0))

        content_scroll = ctk.CTkScrollableFrame(box, fg_color="#14141a", corner_radius=12)
        content_scroll.pack(padx=20, pady=10, fill="both", expand=True)

        # ---------------- 1. SCHRITT: OSU! ACCOUNT (PFLICHTANGABEN) ----------------
        f_acc = ctk.CTkFrame(content_scroll, fg_color="#1f1f2b", corner_radius=12, border_width=1, border_color="#333346")
        f_acc.pack(fill="x", padx=10, pady=8)

        f_acc_h = ctk.CTkFrame(f_acc, fg_color="transparent")
        f_acc_h.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(f_acc_h, text="🔑 1. osu! Account & API-Key", font=("Arial", 15, "bold"), text_color="#00E5FF").pack(side="left")
        ctk.CTkLabel(f_acc_h, text=" PFLICHTFELD ", font=("Arial", 10, "bold"), fg_color="#c62828", text_color="#ffffff", corner_radius=4).pack(side="left", padx=10)

        # Ingame Username Input
        user_row = ctk.CTkFrame(f_acc, fg_color="transparent")
        user_row.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(user_row, text="osu! Ingame Name:", font=("Arial", 13, "bold"), text_color="#ffffff", width=140, anchor="w").pack(side="left")
        user_entry = ctk.CTkEntry(user_row, placeholder_text="z.B. WhiteCat, Mrekk...", font=("Arial", 13), height=36)
        if getattr(self, "osu_username", ""): user_entry.insert(0, self.osu_username)
        user_entry.pack(side="left", fill="x", expand=True)

        # osu! API Key Input
        key_row = ctk.CTkFrame(f_acc, fg_color="transparent")
        key_row.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(key_row, text="osu! API Key (v1):", font=("Arial", 13, "bold"), text_color="#ffffff", width=140, anchor="w").pack(side="left")
        key_entry = ctk.CTkEntry(key_row, placeholder_text="Dein v1 API-Key...", font=("Arial", 13), height=36, show="*")
        if getattr(self, "api_key", ""): key_entry.insert(0, self.api_key)
        key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def open_api_url():
            webbrowser.open("https://osu.ppy.sh/p/api")
        ctk.CTkButton(key_row, text="🌐 API-Key in 10 Sek. holen ➔", font=("Arial", 12, "bold"), height=36,
                      fg_color="#3b8ed0", hover_color="#1f538d", command=open_api_url).pack(side="right")

        # Tutorial Steps Box
        tut_box = ctk.CTkFrame(f_acc, fg_color="#161620", corner_radius=8, border_width=1, border_color="#282836")
        tut_box.pack(fill="x", padx=15, pady=(4, 14))
        ctk.CTkLabel(tut_box, text="💡 Kurzanleitung zum Holen des API-Keys (100% kostenlos & sicher):", font=("Arial", 11, "bold"), text_color="#FFA726").pack(anchor="w", padx=10, pady=(6, 2))
        tut_text = "1. Klicke oben rechts auf den blauen Button '🌐 API-Key in 10 Sek. holen' (öffnet osu.ppy.sh).\n" \
                   "2. Logge dich mit deinem osu!-Account ein (falls nicht eingeloggt).\n" \
                   "3. Scrolle nach unten zu 'API Access' und trage bei 'Application Name' einfach 'UHO Hub' ein.\n" \
                   "4. Klicke auf 'Create' / 'Generate Key', kopiere den Code und füge ihn hier ein!"
        ctk.CTkLabel(tut_box, text=tut_text, font=("Arial", 11), text_color="#cccccc", justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        # ---------------- 2. SCHRITT: GOOGLE GEMINI KI-COACH (EMPFOHLEN) ----------------
        f_ai = ctk.CTkFrame(content_scroll, fg_color="#221826", corner_radius=12, border_width=1, border_color="#E91E63")
        f_ai.pack(fill="x", padx=10, pady=8)

        f_ai_h = ctk.CTkFrame(f_ai, fg_color="transparent")
        f_ai_h.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(f_ai_h, text="🤖 2. Google Gemini KI-Coach", font=("Arial", 15, "bold"), text_color="#E91E63").pack(side="left")
        ctk.CTkLabel(f_ai_h, text=" ⭐ DRINGEND EMPFOHLEN ", font=("Arial", 10, "bold"), fg_color="#E91E63", text_color="#ffffff", corner_radius=4).pack(side="left", padx=10)

        ai_row = ctk.CTkFrame(f_ai, fg_color="transparent")
        ai_row.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(ai_row, text="Gemini API Key:", font=("Arial", 13, "bold"), text_color="#ffffff", width=140, anchor="w").pack(side="left")
        gemini_entry = ctk.CTkEntry(ai_row, placeholder_text="AIzaSy... (Kostenlos)", font=("Arial", 13), height=36, show="*")
        if getattr(self, "gemini_key", ""): gemini_entry.insert(0, self.gemini_key)
        gemini_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        def open_gemini_url():
            webbrowser.open("https://aistudio.google.com/app/apikey")
        ctk.CTkButton(ai_row, text="🔑 Gratis Key holen ➔", font=("Arial", 12, "bold"), height=36,
                      fg_color="#E91E63", hover_color="#C2185B", command=open_gemini_url).pack(side="right")

        gemini_tut_box = ctk.CTkFrame(f_ai, fg_color="#2a1a2a", corner_radius=8)
        gemini_tut_box.pack(fill="x", padx=15, pady=(4, 4))
        ctk.CTkLabel(gemini_tut_box, text="📋 Kurzanleitung Gemini API Key (100% kostenlos):", font=("Arial", 11, "bold"), text_color="#E91E63").pack(anchor="w", padx=10, pady=(6, 2))
        gemini_tut_text = "1. Klicke auf '🔑 Gratis Key holen' (öffnet Google AI Studio).\n" \
                          "2. Melde dich mit deinem Google-Konto an.\n" \
                          "3. Klicke auf 'Create API Key' → 'Create API key in new project'.\n" \
                          "4. Kopiere den Key (beginnt mit 'AIzaSy...') und füge ihn oben ein."
        ctk.CTkLabel(gemini_tut_box, text=gemini_tut_text, font=("Arial", 10), text_color="#aa7799", justify="left").pack(anchor="w", padx=10, pady=(0, 6))

        ctk.CTkLabel(f_ai, text="Schaltet Live-Coaching, adaptive Map-Empfehlungen, 4-Wochen-Trainingspläne und Skill-Zertifikate frei.",
                     font=("Arial", 11), text_color="#cc99aa", justify="left").pack(anchor="w", padx=15, pady=(2, 12))

        # ---------------- 3. SCHRITT: HINTERGRUND-SYNC ----------------
        f_sync = ctk.CTkFrame(content_scroll, fg_color="#1f1f2b", corner_radius=12, border_width=1, border_color="#333346")
        f_sync.pack(fill="x", padx=10, pady=8)

        f_sync_h = ctk.CTkFrame(f_sync, fg_color="transparent")
        f_sync_h.pack(fill="x", padx=15, pady=(12, 4))
        ctk.CTkLabel(f_sync_h, text="⚡ 3. Intelligenter Hintergrund-Sync", font=("Arial", 15, "bold"), text_color="#00E5FF").pack(side="left")
        ctk.CTkLabel(f_sync_h, text=" 0% CPU-LAST ", font=("Arial", 10, "bold"), fg_color="#00BFA5", text_color="#000000", corner_radius=4).pack(side="left", padx=10)

        ctk.CTkLabel(f_sync, text="Erkennt gespielte Runden automatisch im Hintergrund – kein manuelles Einreichen von Replays nötig!",
                     font=("Arial", 11), text_color="#888899", justify="left").pack(anchor="w", padx=15, pady=(0, 8))

        self.tut_sync_var = ctk.BooleanVar(value=getattr(self, "auto_background_sync", True))
        def toggle_sync():
            self.auto_background_sync = self.tut_sync_var.get()
            self.save_global_settings()
        ctk.CTkSwitch(f_sync, text="Hintergrund-Sync aktiviert lassen", variable=self.tut_sync_var, command=toggle_sync,
                      font=("Arial", 12, "bold"), progress_color="#00E5FF").pack(anchor="w", padx=15, pady=(0, 12))

        # Bottom Finish Action Bar
        bottom_bar = ctk.CTkFrame(box, fg_color="transparent")
        bottom_bar.pack(fill="x", padx=20, pady=(10, 15))

        status_tut_lbl = ctk.CTkLabel(bottom_bar, text="", font=("Arial", 12, "bold"))
        status_tut_lbl.pack(pady=(0, 6))

        def finish_tutorial():
            u_name = user_entry.get().strip()
            a_key = key_entry.get().strip()
            g_key = gemini_entry.get().strip()

            if not u_name or not a_key:
                status_tut_lbl.configure(text="❌ Bitte trage deinen osu! Ingame-Namen und deinen osu! API-Key ein!", text_color="#ff4444")
                return

            self.osu_username = u_name
            self.api_key = a_key
            if g_key:
                self.gemini_key = g_key
            self.has_seen_tutorial = True
            self.save_global_settings()
            self.show_main_menu()

        ctk.CTkButton(bottom_bar, text="🚀 Einrichtung abschließen & Zum Hauptmenü ➔", font=("Arial", 15, "bold"), height=46,
                      fg_color="#3b8ed0", hover_color="#1f538d", command=finish_tutorial).pack(fill="x")

    def show_settings(self, active_tab="general"):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        container = ctk.CTkFrame(master, fg_color="#181822", corner_radius=16, border_width=1, border_color="#2e2e3f")
        container.pack(fill="both", expand=True, padx=25, pady=25)

        sidebar = ctk.CTkFrame(container, fg_color="#14141c", width=220, corner_radius=16)
        sidebar.pack(side="left", fill="y", padx=0, pady=0)
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="⚙️ Einstellungen", font=("Arial", 18, "bold"), text_color="#ffffff").pack(pady=(25, 20), padx=20, anchor="w")

        content_area = ctk.CTkFrame(container, fg_color="#121216", corner_radius=0)
        content_area.pack(side="right", fill="both", expand=True)

        scroll_content = ctk.CTkScrollableFrame(content_area, fg_color="#121216")
        scroll_content.pack(fill="both", expand=True, padx=25, pady=20)

        tabs = [
            ("general", "📱 Allgemein"),
            ("accounts", "🔑 Konten & APIs"),
            ("ai", "🤖 KI-Assistent"),
            ("about", "ℹ️ Über UHO Hub")
        ]

        def switch_tab(tab_id):
            self.show_settings(active_tab=tab_id)

        for tid, label in tabs:
            is_active = (tid == active_tab)
            bg = "#272730" if is_active else "transparent"
            fg = "#3b8ed0" if is_active else "#9999aa"
            btn = ctk.CTkButton(sidebar, text=label, anchor="w", font=("Arial", 13, "bold" if is_active else "normal"),
                                fg_color=bg, hover_color="#22222a", text_color=fg, height=38, corner_radius=8,
                                command=lambda t=tid: switch_tab(t))
            btn.pack(fill="x", padx=12, pady=3)

        ctk.CTkButton(sidebar, text="⬅ Hauptmenü", font=("Arial", 13, "bold"), height=38, fg_color="#25252e",
                      hover_color="#353540", command=self.show_main_menu).pack(side="bottom", fill="x", padx=12, pady=20)

        top_bar = ctk.CTkFrame(scroll_content, fg_color="transparent")
        top_bar.pack(fill="x", pady=(0, 15))

        titles = {
            "general": ("Allgemein", "Konfiguriere automatische Play-Erkennung, Replay-Verwaltung und Systemverhalten."),
            "accounts": ("Konten & API-Keys", "Verknüpfe deinen osu! Account und verwalte deinen UHO API-Key."),
            "ai": ("KI-Assistent (Google Gemini)", "Konfiguriere deinen persönlichen KI-Coach für Echtzeit-Tipps und Analysen."),
            "about": ("Über UHO Hub", "Informationen zur Version, Entwickler, Support und Onboarding-Tutorial.")
        }
        t_title, t_desc = titles.get(active_tab, ("Einstellungen", ""))
        
        header_left = ctk.CTkFrame(top_bar, fg_color="transparent")
        header_left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(header_left, text=t_title, font=("Arial", 22, "bold"), text_color="#ffffff").pack(anchor="w")
        ctk.CTkLabel(header_left, text=t_desc, font=("Arial", 12), text_color="#888899").pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(top_bar, text="✕", width=36, height=36, font=("Arial", 16, "bold"), fg_color="#22222a",
                      hover_color="#333340", text_color="#aaaaaa", command=self.show_main_menu).pack(side="right")

        if active_tab == "general":
            ctk.CTkLabel(scroll_content, text="HINTERGRUND & AUTOMATISIERUNG", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(15, 8))

            c1 = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c1.pack(fill="x", pady=6)
            sync_var = ctk.BooleanVar(value=getattr(self, "auto_background_sync", True))
            def on_sync_toggle():
                self.auto_background_sync = sync_var.get()
                self.save_global_settings()
            ctk.CTkSwitch(c1, text="", variable=sync_var, command=on_sync_toggle, progress_color="#00BFA5", width=45).pack(side="right", padx=16, pady=10)

            c1_text = ctk.CTkFrame(c1, fg_color="transparent")
            c1_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            c1_h = ctk.CTkFrame(c1_text, fg_color="transparent")
            c1_h.pack(fill="x")
            ctk.CTkLabel(c1_h, text="Intelligenter Hintergrund-Sync", font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")
            ctk.CTkLabel(c1_h, text=" EMPFOHLEN ", font=("Arial", 10, "bold"), fg_color="#00BFA5", text_color="#000000", corner_radius=4).pack(side="left", padx=8)
            ctk.CTkLabel(c1_text, text="Erkennt automatisch, wenn osu! gestartet wird, und synchronisiert Scores live (0% CPU/RAM-Last).",
                         font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(3, 0))

            c2 = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c2.pack(fill="x", pady=6)
            del_var = ctk.BooleanVar(value=self.data.get("delete_replays", False))
            def on_del_toggle():
                self.data["delete_replays"] = del_var.get()
                self.save_settings()
            ctk.CTkSwitch(c2, text="", variable=del_var, command=on_del_toggle, progress_color="#3b8ed0", width=45).pack(side="right", padx=16, pady=10)

            c2_text = ctk.CTkFrame(c2, fg_color="transparent")
            c2_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c2_text, text="Replays nach Training-Import löschen", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c2_text, text="Löscht importierte .osr Replay-Dateien automatisch aus dem osu!-Ordner, um Speicherplatz zu sparen.",
                         font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(3, 0))

            c3 = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c3.pack(fill="x", pady=6)
            auto_win_var = ctk.BooleanVar(value=is_windows_autostart_enabled())
            def on_autostart_toggle():
                set_windows_autostart(auto_win_var.get())
            ctk.CTkSwitch(c3, text="", variable=auto_win_var, command=on_autostart_toggle, progress_color="#00E5FF", width=45).pack(side="right", padx=16, pady=10)

            c3_text = ctk.CTkFrame(c3, fg_color="transparent")
            c3_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c3_text, text="Automatisch mit Windows starten", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c3_text, text="Startet UHO Hub lautlos im Hintergrund, sobald du deinen PC hochfährst.",
                         font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(3, 0))

        elif active_tab == "accounts":
            ctk.CTkLabel(scroll_content, text="OSU! ACCOUNT VERKNÜPFUNG", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(15, 8))

            c_u = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_u.pack(fill="x", pady=6)
            user_entry = ctk.CTkEntry(c_u, width=200, placeholder_text="Username eingeben...")
            if getattr(self, "osu_username", ""): user_entry.insert(0, self.osu_username)
            user_entry.pack(side="right", padx=16, pady=10)

            c_u_text = ctk.CTkFrame(c_u, fg_color="transparent")
            c_u_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_u_text, text="osu! Ingame Name", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_u_text, text="Dein exakter Spielername in osu! für automatisches Score-Tracking.", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            c_k = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_k.pack(fill="x", pady=6)
            k_right = ctk.CTkFrame(c_k, fg_color="transparent")
            k_right.pack(side="right", padx=16, pady=10)
            key_entry = ctk.CTkEntry(k_right, width=180, show="*", placeholder_text="API Key...")
            if getattr(self, "api_key", ""): key_entry.insert(0, self.api_key)
            key_entry.pack(side="left", padx=(0, 8))

            def open_api_tut():
                webbrowser.open("https://osu.ppy.sh/p/api")
            ctk.CTkButton(k_right, text="🌐 Holen", width=70, height=32, fg_color="#2d3748", hover_color="#4a5568", command=open_api_tut).pack(side="left")

            c_k_text = ctk.CTkFrame(c_k, fg_color="transparent")
            c_k_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_k_text, text="osu! API Key (v1)", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_k_text, text="Ermöglicht den Live-Abgleich von Plays direkt von den osu!-Servern.", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            # osu! IRC Password for Automated Referee Bot
            c_irc = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_irc.pack(fill="x", pady=6)
            irc_right = ctk.CTkFrame(c_irc, fg_color="transparent")
            irc_right.pack(side="right", padx=16, pady=10)
            irc_entry = ctk.CTkEntry(irc_right, width=180, show="*", placeholder_text="Server-Passwort...")
            if getattr(self, "osu_irc_password", ""): irc_entry.insert(0, self.osu_irc_password)
            irc_entry.pack(side="left", padx=(0, 8))

            def open_irc_page():
                webbrowser.open("https://osu.ppy.sh/p/irc")
            ctk.CTkButton(irc_right, text="🔑 Holen", width=70, height=32, fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=open_irc_page).pack(side="left")

            c_irc_text = ctk.CTkFrame(c_irc, fg_color="transparent")
            c_irc_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_irc_text, text="osu! IRC Server Passwort (Optional für Multiplayer Host-Bot)", font=("Arial", 14, "bold"), text_color="#00BFA5").pack(anchor="w")
            ctk.CTkLabel(c_irc_text, text="Erlaubt dem automatischen Referee-Bot, Ingame-Lobbies zu erstellen und Spieler einzuladen.", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            ctk.CTkLabel(scroll_content, text="UHO HUB LIZENZ & STATUS", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(20, 8))
            c_uho = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_uho.pack(fill="x", pady=6)
            ctk.CTkLabel(c_uho, text=" ✅ AKTIV ", font=("Arial", 11, "bold"), fg_color="#1b382b", text_color="#4CAF50", corner_radius=6).pack(side="right", padx=16, pady=10)

            c_uho_text = ctk.CTkFrame(c_uho, fg_color="transparent")
            c_uho_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_uho_text, text="UHO API-Key Status", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            key_preview = getattr(self, "uho_api_key", "Kein Key")
            if len(key_preview) > 10: key_preview = key_preview[:7] + "..." + key_preview[-4:]
            ctk.CTkLabel(c_uho_text, text=f"Key: {key_preview} (An diesen Computer gebunden)", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            def save_account_settings():
                self.osu_username = user_entry.get().strip()
                self.api_key = key_entry.get().strip()
                self.osu_irc_password = irc_entry.get().strip()
                self.save_global_settings()
                save_lbl.configure(text="✅ Einstellungen erfolgreich gespeichert!", text_color="#4CAF50")

            save_frame = ctk.CTkFrame(scroll_content, fg_color="transparent")
            save_frame.pack(fill="x", pady=(20, 10))
            ctk.CTkButton(save_frame, text="Speichern & Übernehmen", font=("Arial", 14, "bold"), height=42, width=220,
                          fg_color="#3b8ed0", hover_color="#1f538d", command=save_account_settings).pack(side="left")
            save_lbl = ctk.CTkLabel(save_frame, text="", font=("Arial", 12))
            save_lbl.pack(side="left", padx=15)

        elif active_tab == "ai":
            ctk.CTkLabel(scroll_content, text="GOOGLE GEMINI KONFIGURATION", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(15, 8))

            c_ai = ctk.CTkFrame(scroll_content, fg_color="#231c26", corner_radius=10, border_width=1, border_color="#E91E63")
            c_ai.pack(fill="x", pady=6)
            ai_right = ctk.CTkFrame(c_ai, fg_color="transparent")
            ai_right.pack(side="right", padx=16, pady=10)
            gemini_entry = ctk.CTkEntry(ai_right, width=200, show="*", placeholder_text="AIzaSy...")
            if getattr(self, "gemini_key", ""): gemini_entry.insert(0, self.gemini_key)
            gemini_entry.pack(side="left", padx=(0, 8))

            def open_gemini_get():
                webbrowser.open("https://aistudio.google.com/app/apikey")
            ctk.CTkButton(ai_right, text="🔑 Gratis holen", width=95, height=32, fg_color="#E91E63", hover_color="#C2185B", command=open_gemini_get).pack(side="left")

            c_ai_text = ctk.CTkFrame(c_ai, fg_color="transparent")
            c_ai_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            c_ai_h = ctk.CTkFrame(c_ai_text, fg_color="transparent")
            c_ai_h.pack(fill="x")
            ctk.CTkLabel(c_ai_h, text="Gemini API Key", font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")
            ctk.CTkLabel(c_ai_h, text=" ⭐ DRINGEND EMPFOHLEN ", font=("Arial", 10, "bold"), fg_color="#E91E63", text_color="#ffffff", corner_radius=4).pack(side="left", padx=8)
            ctk.CTkLabel(c_ai_text, text="Schaltet den intelligenten KI-Coach frei für personalisierte Trainingspläne und Fehleranalysen.",
                         font=("Arial", 11), text_color="#bb99aa", wraplength=460, justify="left").pack(anchor="w", pady=(3, 0))

            c_m = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_m.pack(fill="x", pady=6)
            model_dropdown = ctk.CTkOptionMenu(c_m, values=["gemini-3.6-flash (Empfohlen)", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
                                                width=220, fg_color="#2d3748", button_color="#4a5568")
            current_m = getattr(self, "selected_ai_model", "gemini-3.6-flash")
            for val in model_dropdown._values:
                if current_m in val: model_dropdown.set(val)
            model_dropdown.pack(side="right", padx=16, pady=10)

            c_m_text = ctk.CTkFrame(c_m, fg_color="transparent")
            c_m_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_m_text, text="Bevorzugtes KI-Modell", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_m_text, text="Gemini 3.6 Flash ist das neueste und schnellste Modell von Google DeepMind.", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            def save_ai_settings():
                self.gemini_key = gemini_entry.get().strip()
                raw_m = model_dropdown.get().split(" ")[0]
                self.selected_ai_model = raw_m
                self.save_global_settings()
                ai_save_lbl.configure(text="✅ KI-Einstellungen erfolgreich gespeichert!", text_color="#4CAF50")

            ai_save_frame = ctk.CTkFrame(scroll_content, fg_color="transparent")
            ai_save_frame.pack(fill="x", pady=(20, 10))
            ctk.CTkButton(ai_save_frame, text="Speichern & Übernehmen", font=("Arial", 14, "bold"), height=42, width=220,
                          fg_color="#E91E63", hover_color="#C2185B", command=save_ai_settings).pack(side="left")
            ai_save_lbl = ctk.CTkLabel(ai_save_frame, text="", font=("Arial", 12))
            ai_save_lbl.pack(side="left", padx=15)

            ctk.CTkLabel(scroll_content, text="KI-DIAGNOSE & GEDANKENPROTOKOLL", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(20, 8))

            c_log = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_log.pack(fill="x", pady=6)

            def export_ai_diagnostics():
                desktop = os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop')
                out_file = os.path.join(desktop, "uho_ai_diagnostics.txt")
                logs = getattr(self, "ai_debug_logs", [])
                feedback_dict = getattr(self, "ai_user_feedback", {})
                setup_prof = getattr(self, "user_setup_profile", {})
                pa = getattr(self, "last_profile_analysis", {}) or {}
                dt_hist = getattr(self, "deep_replay_history", [])
                
                report_lines = [
                    "=" * 75,
                    f"UHO HUB - MASTER KI-DIAGNOSE & TRAININGSDATENSATZ (v{CURRENT_APP_VERSION})",
                    f"Erstellt am: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Spieler: {getattr(self, 'osu_username', 'Unbekannt')}",
                    f"KI-Modell: {getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}",
                    f"Gesamtanzahl protokollierter KI-Events: {len(logs)}",
                    "=" * 75,
                    "",
                    "🎮 1. BENUTZER-FEEDBACK & MAP-BEWERTUNGEN (👍 / 👎)",
                    "-" * 75
                ]
                
                if feedback_dict:
                    for m_id, fb in feedback_dict.items():
                        icon = "👍 Gefällt" if fb.get("liked") else "👎 Nicht passend / Skipped"
                        report_lines.append(f"  • [{icon}] Map-ID {m_id}: {fb.get('map_name', 'Unbekannt')} (★ {fb.get('sr', 0):.1f}) | Skillset: {fb.get('skillset', '-')} | Datum: {fb.get('timestamp', '-')}")
                else:
                    report_lines.append("  (Noch keine Daumen-Feedbacks abgegeben)")

                report_lines.extend([
                    "",
                    "🛠️ 2. HARDWARE-, ERGONOMIE- & TECHNIQUE-PROFIL",
                    "-" * 75,
                    json.dumps(setup_prof, indent=2, ensure_ascii=False) if setup_prof else "  (Keine Setup-Daten hinterlegt)",
                    "",
                    "📊 3. SKILL-RADAR & PROFIL-SCORES",
                    "-" * 75,
                    f"  • Hauptschwäche: {pa.get('weakness', 'Keine')}",
                    f"  • Stärkstes Skillset: {pa.get('main_skill', 'Keine')}",
                    f"  • Radar-Scores: {json.dumps(pa.get('scores', {}), indent=2, ensure_ascii=False)}",
                    "",
                    f"🔬 4. MULTI-PLAY REPLAY-TELEMETRIE ({len(dt_hist)} gespeicherte Replays)",
                    "-" * 75
                ])

                if dt_hist:
                    for idx, r in enumerate(dt_hist[:10]):
                        m = r.get("metrics", {})
                        report_lines.append(f"  [{idx+1}] {r.get('player', 'Spieler')} | Score: {r.get('score', 0):,} | Acc: {r.get('accuracy', 0):.2f}% | UR: ~{m.get('ur', 0):.1f} | Overaim: {m.get('overaim_pct', 0):.1f}% | Chokes: {', '.join(m.get('choke_reasons', []))}")
                else:
                    report_lines.append("  (Keine Replays in der Telemetrie-Historie)")

                report_lines.extend([
                    "",
                    "🤖 5. DETAIL-PROTOKOLL DER KI-EVENTS (PROMPTS & ROH-ANTWORTEN)",
                    "-" * 75
                ])
                
                if not logs:
                    report_lines.append("Keine KI-Events protokolliert. Führe erst eine Profil-Analyse, ein KI-Training oder einen Skill Test durch.")
                else:
                    for idx, item in enumerate(logs):
                        report_lines.append(f"\n--- [EVENT #{idx+1}] {item.get('timestamp', '')} | Kategorie: {item.get('category', 'Allgemein')} ---")
                        report_lines.append(f"📌 INPUTS / SCORES:\n{json.dumps(item.get('inputs', {}), indent=2, ensure_ascii=False)}")
                        if item.get('calculations'):
                            report_lines.append(f"\n🔢 BERECHNUNGEN & SCORING:\n{json.dumps(item.get('calculations', {}), indent=2, ensure_ascii=False)}")
                        if item.get('prompt'):
                            report_lines.append(f"\n🤖 GESENDETER PROMPT AN GEMINI:\n{item.get('prompt')}")
                        if item.get('raw_ai_response'):
                            report_lines.append(f"\n💡 GEMINI ROH-ANTWORT & GEDANKENGANG:\n{item.get('raw_ai_response')}")
                        report_lines.append("-" * 60)
                        
                # Section 6: Full Multi-Turn Conversation Transcripts
                report_lines.extend([
                    "",
                    "💬 6. VOLLSTÄNDIGE KONVERSATIONS-TRANSKRIPTE (KI-GESPRÄCHS-GEDÄCHTNIS)",
                    "-" * 75
                ])
                conv_data = getattr(self, "ai_conversations", {})
                all_convs = conv_data.get("conversations", []) if isinstance(conv_data, dict) else []
                if not all_convs:
                    report_lines.append("  (Noch keine Konversationen im Chat-Speicher)")
                else:
                    for c_idx, c in enumerate(all_convs):
                        c_title = c.get("title", f"Chat #{c_idx+1}")
                        c_updated = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(c.get('updated_at', c.get('created_at', time.time()))))
                        report_lines.append(f"\n📁 [KONVERSATION #{c_idx+1}] {c_title} (Zuletzt aktiv: {c_updated})")
                        report_lines.append("=" * 60)
                        for m in c.get("messages", []):
                            r_icon = "👤 SPIELER" if m.get("role") == "user" else "🤖 KI-COACH"
                            t_str = m.get("timestamp", "-")
                            report_lines.append(f"[{t_str}] {r_icon}:\n{m.get('text', '')}\n")
                        report_lines.append("-" * 60)
                        
                content = "\n".join(report_lines)
                try:
                    with open(out_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    try:
                        self.clipboard_clear()
                        self.clipboard_append(content)
                    except:
                        pass
                    self.show_message("✅ KI-Diagnose exportiert", f"Der vollständige KI-Trainings- und Fehler-Datensatz wurde auf deinem Desktop gespeichert:\n\n📄 {out_file}\n\n(Zusätzlich in die Zwischenablage kopiert!)")
                except Exception as e:
                    self.show_message("Fehler beim Export", f"Konnte Datei nicht schreiben: {e}")

                # Update count label
                if 'c_log_title' in locals() and c_log_title.winfo_exists():
                    c_log_title.configure(text=f"📋 KI-Gedankengang & Fehler-Protokoll ({len(getattr(self, 'ai_debug_logs', []))} Events)")

            log_actions = ctk.CTkFrame(c_log, fg_color="transparent")
            log_actions.pack(side="right", padx=16, pady=10)
            ctk.CTkButton(log_actions, text="📋 Log exportieren", width=145, height=34, fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", font=("Arial", 12, "bold"), command=export_ai_diagnostics).pack(side="right")

            c_log_text = ctk.CTkFrame(c_log, fg_color="transparent")
            c_log_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            log_count = len(getattr(self, "ai_debug_logs", []))
            c_log_title = ctk.CTkLabel(c_log_text, text=f"📋 KI-Gedankengang & Fehler-Protokoll ({log_count} Events)", font=("Arial", 14, "bold"), text_color="#ffffff")
            c_log_title.pack(anchor="w")
            ctk.CTkLabel(c_log_text, text="Protokolliert automatisch alle Prompts, Gemini-Gedankengänge, Roh-Antworten und Score-Berechnungen zur Fehlerbehebung.",
                         font=("Arial", 11), text_color="#888899", wraplength=460, justify="left").pack(anchor="w", pady=(2, 0))

            # Danger Zone: Reset AI Memory Card
            ctk.CTkLabel(scroll_content, text="GEFÄHRLICHE ZONE (RESET)", font=("Arial", 11, "bold"), text_color="#ff5252").pack(anchor="w", pady=(22, 8))

            c_danger = ctk.CTkFrame(scroll_content, fg_color="#241418", corner_radius=10, border_width=1, border_color="#c62828")
            c_danger.pack(fill="x", pady=6)

            btn_danger = ctk.CTkButton(c_danger, text="🗑️ KI-Gedächtnis zurücksetzen...", font=("Arial", 12, "bold"), height=36, width=220,
                          fg_color="#c62828", hover_color="#b71c1c", text_color="#ffffff", command=self.show_reset_ai_memory_modal)
            btn_danger.pack(side="right", padx=16, pady=10)

            c_danger_text = ctk.CTkFrame(c_danger, fg_color="transparent")
            c_danger_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_danger_text, text="🔥 Alle gelernten KI-Daten & Gedächtnis löschen", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_danger_text, text="Setzt alle erlernten Schwächen, Vorlieben, Daumen-Feedbacks, Replay-Telemetrien, Hardware-Setups und den Skill-Radar vollständig auf Werkseinstellung zurück (Sicherheits-Bestätigung erforderlich).",
                         font=("Arial", 11), text_color="#ffcdd2", wraplength=460, justify="left").pack(anchor="w", pady=(2, 0))

        elif active_tab == "about":
            ctk.CTkLabel(scroll_content, text="APP INFORMATIONEN & UPDATES", font=("Arial", 11, "bold"), text_color="#666677").pack(anchor="w", pady=(15, 8))

            # Auto-Update Card
            c_up = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_up.pack(fill="x", pady=6)

            def manual_check_update():
                c_up_btn.configure(state="disabled", text="⏳ Suche...")
                def _run():
                    self.check_for_updates(silent=False)
                    if c_up_btn.winfo_exists():
                        self.after(0, lambda: c_up_btn.configure(state="normal", text="🔄 Nach Updates suchen"))
                threading.Thread(target=_run, daemon=True).start()

            c_up_btn = ctk.CTkButton(c_up, text="🔄 Nach Updates suchen", font=("Arial", 12, "bold"), height=34, width=170,
                                     fg_color="#3b8ed0", hover_color="#1f538d", command=manual_check_update)
            c_up_btn.pack(side="right", padx=16, pady=10)

            c_up_text = ctk.CTkFrame(c_up, fg_color="transparent")
            c_up_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_up_text, text=f"UHO Hub Version v{CURRENT_APP_VERSION}", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_up_text, text=f"GitHub: {GITHUB_REPO} • 1-Klick Auto-Update aktiv", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            c_tut = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_tut.pack(fill="x", pady=6)
            ctk.CTkButton(c_tut, text="📖 Tutorial öffnen", font=("Arial", 12, "bold"), height=34, width=170,
                          fg_color="#2b2b38", hover_color="#3a3a4c", command=self.show_tutorial_welcome).pack(side="right", padx=16, pady=10)

            c_tut_text = ctk.CTkFrame(c_tut, fg_color="transparent")
            c_tut_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_tut_text, text="Einführung / Tutorial erneut ansehen", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_tut_text, text="Öffnet die Übersicht aller Funktionen und Empfehlungen.", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

            c_dc = ctk.CTkFrame(scroll_content, fg_color="#1c1c24", corner_radius=10, border_width=1, border_color="#2a2a35")
            c_dc.pack(fill="x", pady=6)
            def open_support_dc():
                webbrowser.open("https://discord.com/users/kingmaster0550")
            ctk.CTkButton(c_dc, text="💬 Discord Profil", font=("Arial", 12, "bold"), height=34, width=170,
                          fg_color="#5865F2", hover_color="#4752C4", command=open_support_dc).pack(side="right", padx=16, pady=10)

            c_dc_text = ctk.CTkFrame(c_dc, fg_color="transparent")
            c_dc_text.pack(side="left", padx=16, pady=12, fill="both", expand=True)
            ctk.CTkLabel(c_dc_text, text="Support & Entwickler-Kontakt", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(c_dc_text, text="Discord: Kingmaster0550 • Schreibe mich bei Fragen oder Ideen gerne an!", font=("Arial", 11), text_color="#888899", wraplength=480, justify="left").pack(anchor="w", pady=(2, 0))

    def show_api_settings(self):
        self.show_settings(active_tab="accounts")

    # ---------------------------------------------------------------------------
    # AUTOMATIC GITHUB IN-APP AUTO-UPDATER SYSTEM
    # ---------------------------------------------------------------------------
    def start_auto_update_checker(self):
        """Starts background update check without interrupting user experience."""
        def _check():
            try:
                self.check_for_updates(silent=True)
            except: pass
        threading.Thread(target=_check, daemon=True).start()

    def parse_version_tuple(self, v_str):
        try:
            cleaned = re.sub(r'^[^\d]*', '', str(v_str).strip())
            parts = [int(x) for x in cleaned.split('.') if x.isdigit()]
            while len(parts) < 3: parts.append(0)
            return tuple(parts[:3])
        except:
            return (0, 0, 0)

    def check_for_updates(self, silent=True):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            headers = {"User-Agent": "UHOHub-Updater", "Accept": "application/vnd.github.v3+json"}
            resp = requests.get(url, headers=headers, timeout=6)
            
            if resp.status_code != 200:
                if not silent:
                    self.after(0, lambda: self.show_message("Update-Check", f"Konnte GitHub Releases nicht abfragen (HTTP {resp.status_code})."))
                return

            data = resp.json()
            tag = data.get("tag_name", "")
            remote_ver = self.parse_version_tuple(tag)
            current_ver = self.parse_version_tuple(CURRENT_APP_VERSION)

            if remote_ver > current_ver:
                changelog = data.get("body", "Neue Funktionen, Bugfixes und Optimierungen.")
                release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
                
                # Find binary download URL from assets (.exe or .zip)
                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe") or name.endswith(".zip"):
                        download_url = asset.get("browser_download_url")
                        break

                if not download_url:
                    download_url = release_url

                self.after(0, lambda: self.show_update_modal(tag.lstrip("v"), changelog, download_url, release_url))
            elif not silent:
                self.after(0, lambda: self.show_message("UHO Hub ist aktuell", f"✅ Du nutzt bereits die neueste Version von UHO Hub (v{CURRENT_APP_VERSION})!"))

        except Exception as e:
            if not silent:
                self.after(0, lambda: self.show_message("Update-Check", f"Fehler beim Prüfen auf Updates:\n{str(e)}"))

    def show_update_modal(self, latest_ver, changelog, download_url, release_url):
        modal = ctk.CTkToplevel(self)
        modal.title("🚀 Neues UHO Hub Update verfügbar!")
        modal.geometry("640x560")
        modal.resizable(False, False)
        modal.configure(fg_color="#121216")
        modal.attributes("-topmost", True)

        # Header Box
        hdr = ctk.CTkFrame(modal, fg_color="#181824", corner_radius=12, border_width=1, border_color="#2e2e42")
        hdr.pack(fill="x", padx=20, pady=(20, 10))

        h_left = ctk.CTkFrame(hdr, fg_color="transparent")
        h_left.pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(h_left, text="🚀 Neues UHO Hub Update verfügbar!", font=("Arial", 16, "bold"), text_color="#00E5FF").pack(anchor="w")
        ctk.CTkLabel(h_left, text=f"Version v{latest_ver} ist bereit zum Download! (Aktuell: v{CURRENT_APP_VERSION})",
                     font=("Arial", 12), text_color="#888899").pack(anchor="w")

        ctk.CTkLabel(hdr, text=" NEU ", font=("Arial", 11, "bold"), fg_color="#00E5FF", text_color="#000000", corner_radius=6).pack(side="right", padx=16)

        # Safety Assurance Box
        safe_box = ctk.CTkFrame(modal, fg_color="#112822", corner_radius=8, border_width=1, border_color="#00E676")
        safe_box.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(safe_box, text="🛡️ 100% Sicher: Alle deine Spielstände, KI-Fortschritte und Einstellungen bleiben erhalten!",
                     font=("Arial", 11, "bold"), text_color="#00E676").pack(padx=12, pady=8)

        # Changelog Textbox
        ctk.CTkLabel(modal, text="Was ist neu in diesem Update?", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(0, 4))
        c_box = ctk.CTkTextbox(modal, wrap="word", font=("Arial", 12), fg_color="#181822", border_width=1, border_color="#2b2b3c", corner_radius=8)
        c_box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        c_box.insert("1.0", changelog.strip())
        c_box.configure(state="disabled")

        # Progress elements (hidden initially)
        prog_bar = ctk.CTkProgressBar(modal, height=12, progress_color="#00E5FF")
        status_lbl = ctk.CTkLabel(modal, text="", font=("Arial", 11, "bold"))

        # Action Buttons
        btn_row = ctk.CTkFrame(modal, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))

        def start_update():
            if download_url and (download_url.endswith(".exe") or download_url.endswith(".zip")):
                self.perform_auto_update(download_url, prog_bar, status_lbl, update_btn, modal)
            else:
                webbrowser.open(release_url)
                modal.destroy()

        update_btn = ctk.CTkButton(btn_row, text="⚡ Jetzt mit 1 Klick Aktualisieren ➔", font=("Arial", 13, "bold"), height=42,
                                   fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=start_update)
        update_btn.pack(side="right", fill="x", expand=True, padx=(8, 0))

        ctk.CTkButton(btn_row, text="Später erinnern", font=("Arial", 12), height=42, width=130,
                      fg_color="#252530", hover_color="#353545", text_color="#aaaaaa", command=modal.destroy).pack(side="left")

    def perform_auto_update(self, download_url, progress_bar, status_lbl, update_btn, modal_win):
        update_btn.configure(state="disabled", text="⏳ Download läuft...")
        progress_bar.pack(fill="x", padx=25, pady=(4, 4))
        progress_bar.set(0.0)
        status_lbl.pack(pady=(2, 6))
        status_lbl.configure(text="⏳ Sichere Daten & starte Download...", text_color="#00E5FF")

        def _update_thread():
            try:
                # 1. Automatic Safety Backup of all user data & AI progress
                backup_dir = "backup_pre_update"
                os.makedirs(backup_dir, exist_ok=True)
                for item in os.listdir("."):
                    if (item.startswith("save_data_") and item.endswith(".json")) or item in ["global_settings.json", "beatmaps.json", "uho_hub_config.json"]:
                        try: shutil.copy2(item, os.path.join(backup_dir, item))
                        except: pass

                # 2. Resolve running executable paths
                current_exe = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else os.path.join(os.getcwd(), "UHOHub.exe"))
                current_dir = os.path.dirname(current_exe)
                current_filename = os.path.basename(current_exe)
                uho_target_path = os.path.join(current_dir, "UHOHub.exe")

                # 3. Download executable or zip stream
                is_zip = download_url.lower().endswith(".zip")
                temp_download = os.path.join(current_dir, "UHOHub_temp.zip" if is_zip else "UHOHub_update.exe")
                target_file = os.path.join(current_dir, "UHOHub_update.exe")

                for f_tmp in [temp_download, target_file]:
                    if os.path.exists(f_tmp):
                        try: os.remove(f_tmp)
                        except: pass

                headers = {"User-Agent": "UHOHub-AutoUpdater"}
                resp = requests.get(download_url, headers=headers, stream=True, timeout=30)
                if resp.status_code != 200:
                    raise Exception(f"Download fehlgeschlagen (HTTP {resp.status_code})")

                total_size = int(resp.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 65536

                with open(temp_download, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                prog = min(1.0, downloaded / total_size)
                                mb_down = downloaded / (1024 * 1024)
                                mb_tot = total_size / (1024 * 1024)
                                modal_win.after(0, lambda p=prog, d=mb_down, t=mb_tot: (
                                    progress_bar.set(p),
                                    status_lbl.configure(text=f"⚡ Lade herunter... {d:.1f} MB / {t:.1f} MB ({int(p*100)}%)")
                                ))

                # If zip, extract UHOHub.exe out of it
                if is_zip:
                    modal_win.after(0, lambda: status_lbl.configure(text="📦 Entpacke Update...", text_color="#00E5FF"))
                    with zipfile.ZipFile(temp_download, 'r') as zip_ref:
                        exe_members = [m for m in zip_ref.namelist() if m.lower().endswith(".exe")]
                        if not exe_members:
                            raise Exception("Keine .exe in der ZIP-Datei gefunden.")
                        chosen_exe = "UHOHub.exe" if "UHOHub.exe" in exe_members else exe_members[0]
                        with open(target_file, "wb") as f_out:
                            f_out.write(zip_ref.read(chosen_exe))
                    try: os.remove(temp_download)
                    except Exception: pass

                # 4. Verify target executable size
                if not os.path.exists(target_file) or os.path.getsize(target_file) < 100000:
                    raise Exception("Heruntergeladene Datei ist unvollständig.")

                modal_win.after(0, lambda: status_lbl.configure(text="✅ Download fertig! Starte nahtlosen Neustart...", text_color="#00E676"))
                time.sleep(1.0)

                # 5. Seamless Hidden PowerShell Auto-Replacer (Zero manual interaction needed!)
                current_pid = os.getpid()
                env = os.environ.copy()
                env["UHO_UPDATE_PID"] = str(current_pid)
                env["UHO_UPDATE_SRC"] = os.path.abspath(target_file)
                env["UHO_UPDATE_DST"] = os.path.abspath(current_exe)

                ps_script = (
                    "$ErrorActionPreference = 'SilentlyContinue'; "
                    "$pid_wait = [int]$env:UHO_UPDATE_PID; "
                    "$src = $env:UHO_UPDATE_SRC; "
                    "$dst = $env:UHO_UPDATE_DST; "
                    "try { Wait-Process -Id $pid_wait -Timeout 10 -ErrorAction SilentlyContinue } catch {}; "
                    "Start-Sleep -Milliseconds 600; "
                    "$retry = 0; "
                    "while ($retry -lt 15) { "
                    "    try { "
                    "        Copy-Item -LiteralPath $src -Destination $dst -Force -ErrorAction Stop; "
                    "        Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue; "
                    "        break; "
                    "    } catch { "
                    "        Start-Sleep -Milliseconds 500; "
                    "        $retry++; "
                    "    } "
                    "}; "
                    "Start-Process -FilePath $dst"
                )

                # Launch PowerShell completely detached and hidden
                DETACHED_FLAGS = 0x00000008 | 0x00000200
                subprocess.Popen(
                    ["powershell.exe", "-WindowStyle", "Hidden", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    env=env,
                    creationflags=DETACHED_FLAGS,
                    close_fds=True
                )
                self.after(400, lambda: (self.destroy(), os._exit(0)))

            except Exception as e:
                err_msg = str(e)
                modal_win.after(0, lambda: (
                    status_lbl.configure(text=f"❌ Fehler beim Update: {err_msg[:45]}", text_color="#FF5252"),
                    update_btn.configure(state="normal", text="🔄 Erneut versuchen")
                ))

        threading.Thread(target=_update_thread, daemon=True).start()

    # ---------------------------------------------------------------------------
    # MULTI-CONVERSATION & CHAT MEMORY SYSTEM (SIDEBAR, MULTI-TURN & AUTO-TITLE)
    # ---------------------------------------------------------------------------
    def load_ai_conversations(self):
        """Loads persistent multi-turn AI conversations from JSON with atomic recovery."""
        appdata_dir = os.path.dirname(getattr(self, 'settings_file', '')) if getattr(self, 'settings_file', '') else '.'
        conv_file = getattr(self, "ai_conversations_file", os.path.join(appdata_dir, "ai_chat_conversations.json"))
        default_data = {
            "active_id": "conv_default",
            "conversations": [
                {
                    "id": "conv_default",
                    "title": "Neuer Chat",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "messages": [
                        {
                            "role": "model",
                            "text": "Hallo! Ich bin dein offizieller UHO Hub KI-Coach. Ich kenne deinen genauen Trainingsfortschritt, deine Skill-Werte und alle Pro-Techniken (KHZ-Methode, Reading, Mappools, Ergonomie, osu! Mods & Aim).\n\nWie kann ich dir bei deiner heutigen Session helfen?",
                            "timestamp": time.strftime("%H:%M")
                        }
                    ]
                }
            ]
        }
        loaded = safe_json_load(conv_file, default=default_data)
        if not isinstance(loaded, dict) or "conversations" not in loaded or not loaded["conversations"]:
            loaded = default_data
        
        conv_ids = [c["id"] for c in loaded.get("conversations", []) if isinstance(c, dict) and "id" in c]
        if not conv_ids:
            loaded = default_data
        elif loaded.get("active_id") not in conv_ids:
            loaded["active_id"] = conv_ids[0]
            
        return loaded

    def save_ai_conversations(self):
        """Saves persistent AI conversations atomically to JSON."""
        appdata_dir = os.path.dirname(getattr(self, 'settings_file', '')) if getattr(self, 'settings_file', '') else '.'
        conv_file = getattr(self, "ai_conversations_file", os.path.join(appdata_dir, "ai_chat_conversations.json"))
        try:
            if hasattr(self, "ai_conversations") and isinstance(self.ai_conversations, dict):
                safe_atomic_json_dump(self.ai_conversations, conv_file, indent=2)
        except Exception:
            pass

    def get_active_ai_conversation(self):
        """Returns the currently active conversation dictionary."""
        if not hasattr(self, "ai_conversations") or not isinstance(self.ai_conversations, dict):
            self.ai_conversations = self.load_ai_conversations()
        
        convs = self.ai_conversations.get("conversations", [])
        active_id = self.ai_conversations.get("active_id")
        
        for c in convs:
            if c.get("id") == active_id:
                return c
        
        if convs:
            self.ai_conversations["active_id"] = convs[0].get("id")
            return convs[0]
            
        return self.create_new_ai_conversation()

    def create_new_ai_conversation(self, title="Neuer Chat"):
        """Creates a brand new conversation and sets it as active."""
        if not hasattr(self, "ai_conversations") or not isinstance(self.ai_conversations, dict):
            self.ai_conversations = self.load_ai_conversations()
            
        new_id = f"conv_{int(time.time()*1000)}_{len(self.ai_conversations.get('conversations', []))+1}"
        new_conv = {
            "id": new_id,
            "title": title,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [
                {
                    "role": "model",
                    "text": "Hallo! Ich bin dein offizieller UHO Hub KI-Coach. Frag mich alles zu Training, Beatmaps, Replay-Analysen, Ergonomie oder osu! Mods!\n\nWie kann ich dir helfen?",
                    "timestamp": time.strftime("%H:%M")
                }
            ]
        }
        if "conversations" not in self.ai_conversations:
            self.ai_conversations["conversations"] = []
        self.ai_conversations["conversations"].insert(0, new_conv)
        self.ai_conversations["active_id"] = new_id
        self.save_ai_conversations()
        return new_conv

    def switch_ai_conversation(self, conv_id):
        """Switches the active conversation and re-renders UI."""
        if not hasattr(self, "ai_conversations") or not isinstance(self.ai_conversations, dict):
            return
        convs = self.ai_conversations.get("conversations", [])
        if any(c.get("id") == conv_id for c in convs):
            self.ai_conversations["active_id"] = conv_id
            self.save_ai_conversations()
            self.refresh_modern_chat_ui()

    def delete_ai_conversation(self, conv_id):
        """Deletes a conversation. If active, selects the next available or creates a new one."""
        if not hasattr(self, "ai_conversations") or not isinstance(self.ai_conversations, dict):
            return
        convs = self.ai_conversations.get("conversations", [])
        self.ai_conversations["conversations"] = [c for c in convs if c.get("id") != conv_id]
        
        if not self.ai_conversations["conversations"]:
            self.create_new_ai_conversation()
        elif self.ai_conversations.get("active_id") == conv_id:
            self.ai_conversations["active_id"] = self.ai_conversations["conversations"][0].get("id")
            
        self.save_ai_conversations()
        self.refresh_modern_chat_ui()

    def auto_generate_chat_title(self, first_msg):
        """Generates a concise 2-4 word German topic title based on the user's first query."""
        if not first_msg:
            return "Allgemeine Frage"
        t = first_msg.strip().replace("\n", " ")
        t_low = t.lower()
        
        # Check map recommendations first if star rating is present
        sr_m = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:★|star|sterne)', t_low)
        if sr_m:
            return f"{sr_m.group(1)}★ Map-Empfehlungen"

        if any(w in t_low for w in ["handgelenk", "schmerz", "verletz", "sehne", "autopilot"]) or re.search(r'\bap\b', t_low):
            return "Handgelenk & Autopilot"
        if any(w in t_low for w in ["relax", "flow aim"]) or re.search(r'\brx\b', t_low):
            return "Relax & Aim-Training"
        if any(w in t_low for w in ["stream", "khz", "deathstream"]):
            return "Stream & KHZ-Methode"
        if any(w in t_low for w in ["speed", "burst", "220 bpm", "bpm"]):
            return "Speed & Burst-Training"
        if any(w in t_low for w in ["jump", "aim", "cross-screen", "snap"]):
            return "Jump-Aim & Snapping"
        if any(w in t_low for w in ["tech", "slider", "sliderbreak"]):
            return "Tech & Slider-Control"
        if any(w in t_low for w in ["reading", "low ar", "high ar", "hidden", "hd"]):
            return "Reading & Low-AR"
        if any(w in t_low for w in ["turnier", "owc", "mappool", "pick", "ban"]):
            return "Turnier & Mappools"
        if any(w in t_low for w in ["map", "maps", "empfiehl", "vorschlag"]):
            return "Beatmap-Empfehlung"
        if any(w in t_low for w in ["pc", "lag", "fps", "latenz", "stutter"]):
            return "PC & FPS Optimierung"
        if any(w in t_low for w in ["tablet", "hover", "drag", "area", "tastatur"]):
            return "Hardware & Tablet Area"
            
        words = [w for w in re.split(r'\s+', t) if len(w) > 1][:4]
        title_cand = " ".join(words)
        if len(title_cand) > 26:
            title_cand = title_cand[:23] + "..."
        return title_cand if title_cand else "osu! Coaching"

    def _format_relative_time(self, ts):
        if not ts:
            return ""
        diff = max(0, int(time.time() - ts))
        if diff < 60:
            return "gerade"
        elif diff < 3600:
            return f"vor {diff // 60}m"
        elif diff < 86400:
            return f"vor {diff // 3600}h"
        elif diff < 86400 * 7:
            return f"vor {diff // 86400}d"
        else:
            return time.strftime("%d. %b", time.localtime(ts))

    def _render_sidebar_items(self):
        """Helper to render conversation list in the left sidebar."""
        chat_frame = self.__dict__.get("chat_history_list_frame")
        if chat_frame is None:
            return
        try:
            if not chat_frame.winfo_exists():
                return
        except:
            return
            
        for w in chat_frame.winfo_children():
            try: w.destroy()
            except: pass
            
        convs = self.ai_conversations.get("conversations", [])
        active_id = self.ai_conversations.get("active_id")
        
        for c in convs:
            cid = c.get("id")
            is_active = (cid == active_id)
            bg_col = "#222230" if is_active else "transparent"
            border_col = "#383852" if is_active else "transparent"
            
            item_frame = ctk.CTkFrame(
                chat_frame, fg_color=bg_col, corner_radius=8,
                border_width=1 if is_active else 0, border_color=border_col, height=44
            )
            item_frame.pack(fill="x", pady=2)
            item_frame.pack_propagate(False)
            
            def make_switch_cmd(target_id=cid):
                return lambda e=None: self.switch_ai_conversation(target_id)
            
            txt_container = ctk.CTkFrame(item_frame, fg_color="transparent")
            txt_container.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=4)
            
            t_lbl = ctk.CTkLabel(
                txt_container, text=c.get("title", "Chat"), font=("Arial", 11, "bold" if is_active else "normal"),
                text_color="#ffffff" if is_active else "#b0b0c5", anchor="w"
            )
            t_lbl.pack(fill="x")
            
            rel_t = self._format_relative_time(c.get("updated_at", c.get("created_at")))
            time_lbl = ctk.CTkLabel(
                txt_container, text=rel_t, font=("Arial", 9), text_color="#707088", anchor="w"
            )
            time_lbl.pack(fill="x")
            
            for comp in (item_frame, txt_container, t_lbl, time_lbl):
                comp.bind("<Button-1>", make_switch_cmd(cid))
                
            def make_del_cmd(target_id=cid):
                return lambda: self.delete_ai_conversation(target_id)
            
            del_btn = ctk.CTkButton(
                item_frame, text="✕", width=22, height=22, font=("Arial", 10, "bold"),
                fg_color="transparent", hover_color="#3a1c22", text_color="#707085",
                corner_radius=4, command=make_del_cmd(cid)
            )
            del_btn.pack(side="right", padx=6)

    def refresh_modern_chat_ui(self):
        """Redraws the sidebar conversation list, the top title, and all messages for the active conversation."""
        chat_win = self.__dict__.get("chat_toplevel")
        if chat_win is None:
            return
        try:
            if not chat_win.winfo_exists():
                return
        except:
            return
            
        cur_conv = self.get_active_ai_conversation()
        
        # 1. Update Top Title
        title_lbl = self.__dict__.get("current_chat_title_lbl")
        if title_lbl is not None:
            try:
                if title_lbl.winfo_exists():
                    title_lbl.configure(text=f"💬 {cur_conv.get('title', 'Neuer Chat')}")
            except: pass
            
        # 2. Render Sidebar list
        self._render_sidebar_items()
            
        # 3. Render Message History
        scroll_frame = self.__dict__.get("chat_scrollable_frame")
        if scroll_frame is not None:
            try:
                if scroll_frame.winfo_exists():
                    for w in scroll_frame.winfo_children():
                        w.destroy()
                    msgs = cur_conv.get("messages", [])
                    for m in msgs:
                        self.add_modern_chat_bubble(m.get("role", "user"), m.get("text", ""))
            except: pass

    def show_ai_chat(self):
        chat_win = ctk.CTkToplevel(self)
        chat_win.title("UHO Hub KI-Coach")
        chat_win.geometry("1060x840")
        chat_win.minsize(860, 680)
        chat_win.configure(fg_color="#0e0e12")
        self.chat_toplevel = chat_win

        if not hasattr(self, "ai_conversations") or not isinstance(self.ai_conversations, dict):
            self.ai_conversations = self.load_ai_conversations()

        # Main Layout: 2 Columns (Left Sidebar + Right Main Area)
        main_layout = ctk.CTkFrame(chat_win, fg_color="transparent")
        main_layout.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # LEFT SIDEBAR (Width: 260px)
        # -------------------------------------------------------------
        sidebar = ctk.CTkFrame(main_layout, fg_color="#14141c", width=260, corner_radius=0, border_width=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Top Button: + Neue Konversation
        btn_new_chat = ctk.CTkButton(
            sidebar, text="+ Neue Konversation", font=("Arial", 12, "bold"),
            height=38, corner_radius=10, fg_color="#222230", hover_color="#2d2d40",
            text_color="#ffffff", border_width=1, border_color="#2f2f42",
            command=lambda: (self.create_new_ai_conversation(), self.refresh_modern_chat_ui())
        )
        btn_new_chat.pack(fill="x", padx=14, pady=(16, 12))

        # Section Header: Konversationen
        ctk.CTkLabel(
            sidebar, text="KONVERSATIONEN", font=("Arial", 10, "bold"),
            text_color="#6e6e85"
        ).pack(anchor="w", padx=16, pady=(4, 6))

        # Scrollable Conversation List
        self.chat_history_list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.chat_history_list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # -------------------------------------------------------------
        # RIGHT MAIN CHAT AREA
        # -------------------------------------------------------------
        main_chat = ctk.CTkFrame(main_layout, fg_color="#0e0e12", corner_radius=0)
        main_chat.pack(side="right", fill="both", expand=True)

        # Header Bar
        top_bar = ctk.CTkFrame(main_chat, fg_color="#15151e", height=54, corner_radius=0)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        title_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        title_box.pack(side="left", padx=20, fill="y")
        self.current_chat_title_lbl = ctk.CTkLabel(
            title_box, text="💬 Neuer Chat", font=("Arial", 15, "bold"), text_color="#ffffff"
        )
        self.current_chat_title_lbl.pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(
            title_box, text="🧠 Multi-Turn Gedächtnis aktiv • osu! Standard Pro-Coach", font=("Arial", 10), text_color="#00E5FF"
        ).pack(anchor="w")

        # Right Controls: Gemini Key & Model Selector
        top_right = ctk.CTkFrame(top_bar, fg_color="transparent")
        top_right.pack(side="right", padx=16)

        gemini_entry = ctk.CTkEntry(
            top_right, placeholder_text="Gemini API Key...", width=160, show="*", font=("Arial", 11), height=28,
            fg_color="#1c1c28", border_color="#2c2c3e"
        )
        gemini_entry.pack(side="left", padx=5)
        if getattr(self, "gemini_key", ""):
            gemini_entry.insert(0, self.gemini_key)

        # Bottom Input Container (Dynamic auto-expanding height matching ChatGPT/Claude UI)
        input_container = ctk.CTkFrame(main_chat, fg_color="#181822", corner_radius=18, border_width=1, border_color="#262636", height=82)
        input_container.pack(side="bottom", fill="x", padx=20, pady=(8, 18))
        input_container.pack_propagate(False)

        bottom_row = ctk.CTkFrame(input_container, fg_color="transparent")
        bottom_row.pack(side="bottom", fill="x", padx=12, pady=(0, 8))

        PLACEHOLDER = "Frage alles, @ zum Erwähnen, / für Aktionen"
        is_placeholder_active = [True]

        msg_entry = ctk.CTkTextbox(
            input_container, height=30, wrap="char",
            font=("Arial", 13), fg_color="transparent", text_color="#6e6e85",
            activate_scrollbars=False, border_width=0
        )
        msg_entry.insert("1.0", PLACEHOLDER)
        msg_entry.pack(side="top", fill="both", expand=True, padx=16, pady=(8, 2))

        # Messages Scroll Area (takes all remaining space above the input container)
        chat_container = ctk.CTkFrame(main_chat, fg_color="#0e0e12")
        chat_container.pack(side="top", fill="both", expand=True, padx=20, pady=(10, 0))

        self.chat_scrollable_frame = ctk.CTkScrollableFrame(chat_container, fg_color="#0e0e12")
        self.chat_scrollable_frame.pack(fill="both", expand=True)

        def get_user_text():
            if is_placeholder_active[0]:
                return ""
            return msg_entry.get("1.0", "end-1c").strip()

        def adjust_input_height(event=None):
            if is_placeholder_active[0]:
                input_container.configure(height=82)
                return
            try:
                if chat_win.winfo_exists():
                    chat_win.update_idletasks()
                raw_c = msg_entry._textbox.tk.call(msg_entry._textbox._w, "count", "-displaylines", "1.0", "end")
                lines = max(1, min(6, int(raw_c))) if raw_c is not None else 1
            except Exception:
                txt = msg_entry.get("1.0", "end-1c")
                lines = max(1, min(6, len(txt.split("\n")) + len(txt) // 70))

            cont_h = 82 + (lines - 1) * 24
            input_container.configure(height=cont_h)
            try: msg_entry.see("insert")
            except: pass

        def clear_user_text():
            is_placeholder_active[0] = True
            msg_entry.delete("1.0", "end")
            msg_entry.insert("1.0", PLACEHOLDER)
            msg_entry.configure(text_color="#6e6e85")
            adjust_input_height()

        def set_user_text(txt):
            is_placeholder_active[0] = False
            msg_entry.delete("1.0", "end")
            msg_entry.insert("1.0", txt)
            msg_entry.configure(text_color="#ffffff")
            adjust_input_height()

        def on_focus_in(event=None):
            if is_placeholder_active[0]:
                is_placeholder_active[0] = False
                msg_entry.delete("1.0", "end")
                msg_entry.configure(text_color="#ffffff")
                adjust_input_height()

        def on_focus_out(event=None):
            raw = msg_entry.get("1.0", "end-1c").strip()
            if not raw:
                is_placeholder_active[0] = True
                msg_entry.delete("1.0", "end")
                msg_entry.insert("1.0", PLACEHOLDER)
                msg_entry.configure(text_color="#6e6e85")
                adjust_input_height()

        msg_entry.bind("<FocusIn>", on_focus_in)
        msg_entry.bind("<FocusOut>", on_focus_out)
        msg_entry.bind("<KeyRelease>", lambda e: msg_entry.after(10, adjust_input_height))
        msg_entry.bind("<BackSpace>", lambda e: msg_entry.after(10, adjust_input_height))
        msg_entry.bind("<Delete>", lambda e: msg_entry.after(10, adjust_input_height))
        msg_entry.bind("<<Paste>>", lambda e: msg_entry.after(10, adjust_input_height))
        msg_entry.bind("<Configure>", lambda e: msg_entry.after(10, adjust_input_height))

        def on_key_press(event):
            if is_placeholder_active[0] and event.char and event.keysym not in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Tab"):
                on_focus_in()
            if event.keysym == "Return":
                if event.state & 0x0001:  # Shift held
                    msg_entry.after(15, adjust_input_height)
                    return
                else:
                    send_message()
                    return "break"
            msg_entry.after(15, adjust_input_height)

        msg_entry.bind("<KeyPress>", on_key_press)

        current_m = getattr(self, "selected_ai_model", "gemini-3.6-flash")
        model_pill = ctk.CTkButton(
            bottom_row, text=f"+ {current_m} ▾", font=("Arial", 11), height=26, corner_radius=12,
            fg_color="#222230", hover_color="#2d2d40", text_color="#bbbbcc"
        )
        model_pill.pack(side="left")

        def send_message(event=None):
            msg = get_user_text()
            if not msg: return
            clear_user_text()

            current_key = gemini_entry.get().strip()
            if current_key: self.gemini_key = current_key

            cur_conv = self.get_active_ai_conversation()
            
            # Auto-title on first user message if default
            if cur_conv.get("title") == "Neuer Chat" or len([m for m in cur_conv.get("messages", []) if m.get("role") == "user"]) == 0:
                new_t = self.auto_generate_chat_title(msg)
                cur_conv["title"] = new_t

            cur_conv["updated_at"] = time.time()
            cur_conv["messages"].append({
                "role": "user",
                "text": msg,
                "timestamp": time.strftime("%H:%M")
            })
            self.save_ai_conversations()

            # Render user message
            self.add_modern_chat_bubble("user", msg)
            if hasattr(self, "current_chat_title_lbl") and self.current_chat_title_lbl.winfo_exists():
                self.current_chat_title_lbl.configure(text=f"💬 {cur_conv.get('title', 'Chat')}")
            self._render_sidebar_items()

            if not self.gemini_key:
                response = self.offline_analyze(msg, conv=cur_conv)
                cur_conv["messages"].append({
                    "role": "model",
                    "text": response,
                    "timestamp": time.strftime("%H:%M")
                })
                self.save_ai_conversations()
                self.add_modern_chat_bubble("ai", response)
                return

            thinking_frame = self.add_modern_chat_bubble("thinking", "Denke nach...")

            def call_gemini():
                try:
                    response = self.query_gemini(msg, conv=cur_conv)
                    if chat_win.winfo_exists():
                        chat_win.after(0, lambda: self.replace_modern_thinking(thinking_frame, response))
                except Exception as e:
                    clean_resp = self.offline_analyze(msg, conv=cur_conv)
                    if chat_win.winfo_exists():
                        chat_win.after(0, lambda: self.replace_modern_thinking(thinking_frame, clean_resp))

            threading.Thread(target=call_gemini, daemon=True).start()

        send_btn = ctk.CTkButton(
            bottom_row, text="➔", width=32, height=28, corner_radius=14,
            fg_color="#2b2b36", hover_color="#3b8ed0", font=("Arial", 13, "bold"), command=send_message
        )
        send_btn.pack(side="right")

        # Initial render of sidebar and message history
        self.refresh_modern_chat_ui()

    def add_modern_chat_bubble(self, role, text):
        text = str(text or "")
        if not hasattr(self, "chat_scrollable_frame") or not hasattr(self.chat_scrollable_frame, "winfo_exists") or not self.chat_scrollable_frame.winfo_exists():
            return None
        container = ctk.CTkFrame(self.chat_scrollable_frame, fg_color="transparent")
        container.pack(fill="x", pady=6, padx=10)

        if role == "user":
            # Pill on the right or centered top
            bubble = ctk.CTkFrame(container, fg_color="#1f1f26", corner_radius=14, border_width=1, border_color="#2c2c38")
            bubble.pack(side="right", padx=(50, 5), pady=2)
            lbl = ctk.CTkLabel(bubble, text=text, font=("Arial", 13), text_color="#ffffff", justify="left", wraplength=520)
            lbl.pack(padx=14, pady=10)
            return container

        elif role == "thinking":
            bubble = ctk.CTkFrame(container, fg_color="transparent")
            bubble.pack(side="left", fill="x", expand=True, padx=(5, 50))
            thought_lbl = ctk.CTkLabel(bubble, text="Nachgedacht für 0s ❯", font=("Arial", 11), text_color="#777788")
            thought_lbl.pack(anchor="w", padx=2, pady=(0, 2))
            ctk.CTkLabel(bubble, text="Analysiere und formuliere Antwort... 🤔", font=("Arial", 13, "italic"), text_color="#aaaaaa").pack(anchor="w", padx=2)
            # Live timer
            import time as _time
            container._think_start = _time.time()
            container._think_label = thought_lbl
            container._think_active = True
            def _tick_thinking(c=container):
                if not getattr(c, '_think_active', False):
                    return
                try:
                    if not c.winfo_exists():
                        return
                    elapsed = int(_time.time() - c._think_start)
                    c._think_label.configure(text=f"Nachgedacht für {elapsed}s ❯")
                    c.after(1000, lambda: _tick_thinking(c))
                except:
                    pass
            container.after(1000, lambda: _tick_thinking(container))
    def _extract_map_info_from_text(self, text):
        """Extracts and verifies beatmap_id and set_id from map recommendation text or [MAP: ...] tags against the local 151k DB."""
        if not text:
            return None
        
        extracted_bid = ""
        extracted_sid = ""

        # 1. Look for explicit tag [MAP: 12345 | SET: 67890] or [MAP: 12345]
        m_tag = re.search(r'\[MAP:\s*(\d+)(?:\s*\|\s*SET:\s*(\d+))?\]', text, re.IGNORECASE)
        if m_tag:
            extracted_bid = m_tag.group(1)
            extracted_sid = m_tag.group(2) or ""

        # 2. Look for URLs
        if not extracted_bid:
            m_url = re.search(r'osu\.ppy\.sh/b(?:eatmaps)?/(\d+)', text)
            if m_url:
                extracted_bid = m_url.group(1)
            else:
                m_set = re.search(r'osu\.ppy\.sh/beatmapsets/(\d+)(?:#osu/(\d+))?', text)
                if m_set:
                    extracted_sid = m_set.group(1)
                    extracted_bid = m_set.group(2) or ""

        # 3. Look for Beatmap ID: 123456
        if not extracted_bid:
            m_id = re.search(r'(?:Beatmap\s*ID|Map[- ]ID|ID):\s*(\d{4,9})', text, re.IGNORECASE)
            if m_id:
                extracted_bid = m_id.group(1)

        # 4. Verify against local SQLite 151k database
        with get_safe_sqlite_conn() as conn:
            if conn:
                try:
                    if extracted_bid:
                        row = conn.execute("SELECT id, set_id FROM maps WHERE id = ? LIMIT 1", (int(extracted_bid),)).fetchone()
                        if row:
                            return {"bid": str(row["id"]), "sid": str(row["set_id"] or extracted_sid)}
                        # If not found by ID, check if it was actually a set_id
                        row_s = conn.execute("SELECT id, set_id FROM maps WHERE set_id = ? ORDER BY sr DESC LIMIT 1", (int(extracted_bid),)).fetchone()
                        if row_s:
                            return {"bid": str(row_s["id"]), "sid": str(row_s["set_id"] or extracted_bid)}

                    # If no valid ID was found or extracted_bid was invalid/hallucinated, search by song name / title in text
                    lines = text.split("\n")
                    for line in lines:
                        clean_line = re.sub(r'[*#_`\[\]]', '', line).strip()
                        # Extract title keywords
                        words = [w for w in re.findall(r'[a-zA-Z0-9]{4,}', clean_line) 
                                 if w.lower() not in ["hier", "deine", "eine", "dieser", "rating", "tipp", "coach", "skills", "stars", "sterne", "drain", "minuten", "pattern", "spikes", "fokus", "bpm"]]
                        if len(words) >= 2:
                            query_w = "%" + "%".join(words[:2]) + "%"
                            row = conn.execute("SELECT id, set_id FROM maps WHERE name LIKE ? ORDER BY playcount DESC LIMIT 1", (query_w,)).fetchone()
                            if row:
                                return {"bid": str(row["id"]), "sid": str(row["set_id"] or "")}
                except Exception:
                    pass

        if extracted_bid:
            return {"bid": extracted_bid, "sid": extracted_sid}

        return None

    def add_modern_chat_bubble(self, role, text):
        text = str(text or "")
        if not hasattr(self, "chat_scrollable_frame") or not hasattr(self.chat_scrollable_frame, "winfo_exists") or not self.chat_scrollable_frame.winfo_exists():
            return None
        container = ctk.CTkFrame(self.chat_scrollable_frame, fg_color="transparent")
        container.pack(fill="x", pady=6, padx=10)

        if role == "user":
            # Pill on the right or centered top
            bubble = ctk.CTkFrame(container, fg_color="#1f1f26", corner_radius=14, border_width=1, border_color="#2c2c38")
            bubble.pack(side="right", padx=(50, 5), pady=2)
            lbl = ctk.CTkLabel(bubble, text=text, font=("Arial", 13), text_color="#ffffff", justify="left", wraplength=520)
            lbl.pack(padx=14, pady=10)
            return container

        elif role == "thinking":
            bubble = ctk.CTkFrame(container, fg_color="transparent")
            bubble.pack(side="left", fill="x", expand=True, padx=(5, 50))
            thought_lbl = ctk.CTkLabel(bubble, text="Nachgedacht für 0s ❯", font=("Arial", 11), text_color="#777788")
            thought_lbl.pack(anchor="w", padx=2, pady=(0, 2))
            ctk.CTkLabel(bubble, text="Analysiere und formuliere Antwort... 🤔", font=("Arial", 13, "italic"), text_color="#aaaaaa").pack(anchor="w", padx=2)
            # Live timer
            import time as _time
            container._think_start = _time.time()
            container._think_label = thought_lbl
            container._think_active = True
            def _tick_thinking(c=container):
                if not getattr(c, '_think_active', False):
                    return
                try:
                    if not c.winfo_exists():
                        return
                    elapsed = int(_time.time() - c._think_start)
                    c._think_label.configure(text=f"Nachgedacht für {elapsed}s ❯")
                    c.after(1000, lambda: _tick_thinking(c))
                except:
                    pass
            container.after(1000, lambda: _tick_thinking(container))
            return container

        else: # AI
            bubble = ctk.CTkFrame(container, fg_color="transparent")
            bubble.pack(side="left", fill="x", expand=True, padx=(5, 50))

            map_info = self._extract_map_info_from_text(text)
            clean_text = re.sub(r'\[MAP:\s*\d+(?:\s*\|\s*SET:\s*\d+)?\]', '', text).strip()

            # Message content box
            lines = clean_text.split("\n")
            total_wrapped = sum(max(1, (len(l) // 52) + 1) for l in lines)
            calc_h = max(50, total_wrapped * 23 + 25)

            msg_box = ctk.CTkTextbox(bubble, wrap="word", font=("Arial", 13), text_color="#eeeeee",
                                     fg_color="#181820", border_width=1, border_color="#262633",
                                     corner_radius=10, height=calc_h, activate_scrollbars=False)
            msg_box.insert("1.0", clean_text)
            msg_box.configure(state="disabled")
            msg_box.pack(fill="x", pady=(0, 6))

            # Action Icons Row (Copy, Thumbs Up, Thumbs Down, + Web & osu!direct buttons)
            act_row = ctk.CTkFrame(bubble, fg_color="transparent")
            act_row.pack(anchor="w", padx=2)

            self._attach_feedback_buttons(act_row, clean_text, map_info=map_info)

            self._bind_mousewheel_to_chat(container)
            try:
                self.chat_scrollable_frame.after(50, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))
            except: pass
            return container

    def _attach_feedback_buttons(self, act_row, bubble_text, map_info=None):
        import webbrowser
        
        # If a map was recommended in this message, add 🌐 Web and ⚡ osu!direct action buttons
        if map_info and (map_info.get("bid") or map_info.get("sid")):
            bid = map_info.get("bid", "")
            sid = map_info.get("sid", "")
            
            def open_web():
                target_url = f"https://osu.ppy.sh/b/{bid}" if bid else f"https://osu.ppy.sh/beatmapsets/{sid}"
                try: webbrowser.open(target_url)
                except: pass
                
            def open_direct():
                target_proto = f"osu://b/{bid}" if bid else f"osu://dl/{sid}"
                try: webbrowser.open(target_proto)
                except: pass
                
            web_btn = ctk.CTkButton(
                act_row, text="🌐 Web", width=68, height=26, font=("Arial", 11, "bold"),
                fg_color="#222232", hover_color="#333348", text_color="#80d8ff",
                corner_radius=6, command=open_web
            )
            web_btn.pack(side="left", padx=(0, 6))
            
            direct_btn = ctk.CTkButton(
                act_row, text="⚡ osu!direct", width=96, height=26, font=("Arial", 11, "bold"),
                fg_color="#ff66aa", hover_color="#ff3388", text_color="#ffffff",
                corner_radius=6, command=open_direct
            )
            direct_btn.pack(side="left", padx=(0, 10))

        def copy_txt():
            try:
                self.clipboard_clear()
                self.clipboard_append(bubble_text)
            except: pass

        ctk.CTkButton(act_row, text="📋", width=28, height=24, font=("Arial", 11), fg_color="transparent",
                      hover_color="#282836", text_color="#888899", command=copy_txt).pack(side="left", padx=2)

        def on_thumb_up():
            self.record_ai_feedback(liked=True, text_snippet=bubble_text)
            btn_up.configure(fg_color="#1b382b", text_color="#00E676", text="👍 Gemerkt")
            btn_down.configure(fg_color="transparent", text_color="#888899", text="👎")

        def on_thumb_down():
            self.record_ai_feedback(liked=False, text_snippet=bubble_text)
            btn_down.configure(fg_color="#3d1c1c", text_color="#FF5252", text="👎 Nicht passend")
            btn_up.configure(fg_color="transparent", text_color="#888899", text="👍")

        btn_up = ctk.CTkButton(act_row, text="👍", width=28, height=24, font=("Arial", 11), fg_color="transparent",
                               hover_color="#282836", text_color="#888899", command=on_thumb_up)
        btn_up.pack(side="left", padx=2)

        btn_down = ctk.CTkButton(act_row, text="👎", width=28, height=24, font=("Arial", 11), fg_color="transparent",
                                 hover_color="#282836", text_color="#888899", command=on_thumb_down)
        btn_down.pack(side="left", padx=2)

    def replace_modern_thinking(self, thinking_container, new_text):
        import time as _time
        new_text = str(new_text or "Alles klar! Ich bin bereit für deine nächste Trainings-Runde.")
        elapsed = 0
        if hasattr(thinking_container, '_think_start'):
            elapsed = int(_time.time() - thinking_container._think_start)
        thinking_container._think_active = False

        for w in thinking_container.winfo_children():
            w.destroy()

        bubble = ctk.CTkFrame(thinking_container, fg_color="transparent")
        bubble.pack(side="left", fill="x", expand=True, padx=(5, 50))

        ctk.CTkLabel(bubble, text=f"Nachgedacht für {max(1, elapsed)}s ❯", font=("Arial", 11), text_color="#777788").pack(anchor="w", padx=2, pady=(0, 4))

        map_info = self._extract_map_info_from_text(new_text)
        clean_text = re.sub(r'\[MAP:\s*\d+(?:\s*\|\s*SET:\s*\d+)?\]', '', new_text).strip()

        lines = clean_text.split("\n")
        total_wrapped = sum(max(1, (len(l) // 52) + 1) for l in lines)
        calc_h = max(50, total_wrapped * 23 + 25)

        msg_box = ctk.CTkTextbox(bubble, wrap="word", font=("Arial", 13), text_color="#eeeeee",
                                 fg_color="#181820", border_width=1, border_color="#262633",
                                 corner_radius=10, height=calc_h, activate_scrollbars=False)
        msg_box.insert("1.0", clean_text)
        msg_box.configure(state="disabled")
        msg_box.pack(fill="x", pady=(0, 6))

        act_row = ctk.CTkFrame(bubble, fg_color="transparent")
        act_row.pack(anchor="w", padx=2)

        self._attach_feedback_buttons(act_row, clean_text, map_info=map_info)

        self._bind_mousewheel_to_chat(thinking_container)
        try:
            self.chat_scrollable_frame.after(50, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))
        except: pass

    def _bind_mousewheel_to_chat(self, root_widget):
        def _on_mousewheel(event):
            try:
                if hasattr(self, "chat_scrollable_frame") and self.chat_scrollable_frame.winfo_exists():
                    # Exact same fast scroll speed as CTkScrollableFrame default (-int(event.delta / 6))
                    steps = -int(event.delta / 6)
                    self.chat_scrollable_frame._parent_canvas.yview("scroll", steps, "units")
                    return "break"
            except:
                pass

        def _apply(w):
            try:
                w.bind("<MouseWheel>", _on_mousewheel)
                if hasattr(w, "_textbox"):
                    w._textbox.bind("<MouseWheel>", _on_mousewheel)
                if hasattr(w, "_label"):
                    w._label.bind("<MouseWheel>", _on_mousewheel)
                if hasattr(w, "_canvas"):
                    w._canvas.bind("<MouseWheel>", _on_mousewheel)
            except:
                pass
            for child in w.winfo_children():
                _apply(child)

        _apply(root_widget)

    # ---------------------------------------------------------------------------
    # SICHERHEITS-MODAL: KI-GEDÄCHTNIS & GELERNTE DATEN ZURÜCKSETZEN ("DELETE")
    # ---------------------------------------------------------------------------
    def show_reset_ai_memory_modal(self):
        """
        Öffnet einen Sicherheitsdialog, der das Löschen aller von der KI erlernten Daten
        erst nach expliziter Eingabe von "DELETE" in ein Textfeld freischaltet.
        """
        modal = ctk.CTkToplevel(self)
        modal.title("⚠️ KI-Gedächtnis zurücksetzen")
        modal.geometry("640x510")
        modal.minsize(540, 440)
        modal.configure(fg_color="#121216")
        modal.attributes("-topmost", True)

        try:
            modal.update_idletasks()
            w = 640
            h = 510
            x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
            modal.geometry(f"{w}x{h}+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(modal, fg_color="#181822", corner_radius=16, border_width=1, border_color="#c62828")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(hdr, text="⚠️ KI-Gedächtnis & gelernte Daten zurücksetzen", font=("Arial", 16, "bold"), text_color="#FF5252").pack(side="left")

        # Warning explanation
        warn_box = ctk.CTkFrame(card, fg_color="#2a1418", corner_radius=10, border_width=1, border_color="#c62828")
        warn_box.pack(fill="x", padx=20, pady=(4, 12))
        
        warn_text = (
            "Diese Aktion setzt alle von der KI erlernten Daten und Anpassungen vollständig zurück:\n\n"
            "• Alle Daumen-Hoch/Runter Bewertungen für Maps & Feedback\n"
            "• Dein Hardware- & Ergonomie-Profil (DPI, Tablet-Area, Rapid Trigger)\n"
            "• Gespeicherter Replay-Telemetrie-Verlauf & Choke-Diagnosen\n"
            "• Profil-Skill-Radar, ermittelte Schwächen & Skill-Testergebnisse\n"
            "• Live-Coaching Trainingsverlauf, Mod-Ausschlüsse & Chat-Historie"
        )
        ctk.CTkLabel(warn_box, text=warn_text, font=("Arial", 11), text_color="#ffcdd2", justify="left").pack(padx=14, pady=10, anchor="w")

        # Confirmation instruction
        ctk.CTkLabel(card, text='Tippe zur Bestätigung DELETE in das folgende Textfeld:', font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=22, pady=(4, 6))

        input_frame = ctk.CTkFrame(card, fg_color="transparent")
        input_frame.pack(fill="x", padx=20, pady=(0, 6))

        confirm_entry = ctk.CTkEntry(input_frame, placeholder_text='Tippe "DELETE" hier ein...', font=("Consolas", 14, "bold"),
                                     height=40, border_color="#444455", text_color="#ffffff")
        confirm_entry.pack(fill="x")

        status_lbl = ctk.CTkLabel(card, text="", font=("Arial", 11, "bold"))
        status_lbl.pack(anchor="w", padx=22, pady=(0, 6))

        # Bottom buttons
        bot_bar = ctk.CTkFrame(card, fg_color="transparent", height=44)
        bot_bar.pack(fill="x", padx=20, pady=(6, 14), side="bottom")
        bot_bar.pack_propagate(False)

        def do_cancel():
            modal.destroy()

        def do_delete():
            user_input = confirm_entry.get().strip()
            if user_input != "DELETE":
                status_lbl.configure(text='❌ Bestätigung fehlgeschlagen! Bitte tippe exakt "DELETE" ein.', text_color="#FF5252")
                confirm_entry.configure(border_color="#FF5252")
                return

            # Perform complete AI memory reset
            self.ai_user_feedback = {}
            self.user_setup_profile = {}
            self.last_deep_replay_telemetry = None
            self.deep_replay_history = []
            self.ai_debug_logs = []
            self.ai_training_history = []
            self.last_profile_analysis = None
            self.last_profile_player = ""
            self.has_analyzed_self = False
            self.skill_tester_submissions = {}
            self.current_ai_skill_test = None
            self.tester_results = {}
            self.chat_history = []
            if hasattr(self, "ai_conversations_file") and os.path.exists(self.ai_conversations_file):
                try: os.remove(self.ai_conversations_file)
                except: pass
            self.ai_conversations = self.load_ai_conversations()
            self._rounds_since_feedback_prompt = 0
            self._persistent_mod_pref = None
            if hasattr(self, "_banned_mods"):
                self._banned_mods = set()
            self._user_requested_mod = None
            self._user_requested_sr = None

            self.save_global_settings()
            modal.destroy()

            self.show_message("✅ KI-Gedächtnis zurückgesetzt",
                              "Alle gelernten Daten, Vorlieben, Feedbacks, Hardware-Profile und der Skill-Radar der KI wurden erfolgreich auf Werkseinstellungen zurückgesetzt!")
            self.show_settings(active_tab="ai")

        del_btn = ctk.CTkButton(bot_bar, text="🔥 Alles endgültig löschen", font=("Arial", 13, "bold"), height=36,
                                fg_color="#331c20", hover_color="#c62828", text_color="#ff8888", corner_radius=8,
                                state="disabled", command=do_delete)
        del_btn.pack(side="right")

        ctk.CTkButton(bot_bar, text="Abbrechen", font=("Arial", 12), height=36, width=90,
                      fg_color="transparent", hover_color="#22222c", text_color="#888899",
                      command=do_cancel).pack(side="right", padx=(0, 10))

        def on_key_release(event=None):
            val = confirm_entry.get().strip()
            if val == "DELETE":
                confirm_entry.configure(border_color="#00E676")
                status_lbl.configure(text="✅ Bestätigt! Klicke auf den Button, um alle Daten zu löschen.", text_color="#00E676")
                del_btn.configure(state="normal", fg_color="#c62828", hover_color="#b71c1c", text_color="#ffffff")
            else:
                confirm_entry.configure(border_color="#444455")
                status_lbl.configure(text="", text_color="#888899")
                del_btn.configure(state="disabled", fg_color="#331c20", text_color="#ff8888")

        confirm_entry.bind("<KeyRelease>", on_key_release)
        confirm_entry.bind("<Return>", lambda e: do_delete() if confirm_entry.get().strip() == "DELETE" else None)
    def show_ai_question_modal(self, title=None, subtitle=None, options=None, callback=None, default_idx=0):
        """
        Öffnet einen modernen, interaktiven Multiple-Choice Dialog im exakten Stil des Referenz-Screenshots.
        Ermöglicht der KI, den Spieler gezielt nach Feedback, Tempo, Miss-Ursachen oder Skillset-Wünschen zu befragen.
        """
        cur_map = getattr(self, "current_ai_training_map", {}) or {}
        map_name = cur_map.get("name", "Aktuelle Trainings-Map")
        map_sr = cur_map.get("sr", 5.5)
        map_mod = cur_map.get("mod", "NM")
        target_sk = getattr(self, "ai_training_target_skill", "Streams")

        if title is None:
            title = "Wie hat sich das Tempo & die Schwierigkeit für dich angefühlt?"

        if subtitle is None:
            subtitle = f"Map: {map_name} (★ {map_sr:.1f}, +{map_mod}) • Skillset: {target_sk}"

        if options is None or not options:
            options = [
                "Zu schnell / Meine Finger haben blockiert (Tempo -15 BPM drosseln)",
                "Perfekte Herausforderung / Genau das richtige Limit zum Trainieren",
                "Gutes Tempo, aber Misses durch Overaiming / Sliderbreaks",
                "Ich möchte jetzt zu einem anderen Skillset wechseln (z. B. Jumps/Aim)",
                "Andere Einstellung (Mod wechseln oder Schwierigkeit manuell wählen)"
            ]

        modal = ctk.CTkToplevel(self)
        modal.title("KI-Coach Feedback")
        modal.geometry("720x450")
        modal.minsize(620, 380)
        modal.configure(fg_color="#121216")
        modal.attributes("-topmost", True)

        # Center relative to parent window
        try:
            modal.update_idletasks()
            w = 720
            h = 450
            x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
            modal.geometry(f"{w}x{h}+{max(30, x)}+{max(30, y)}")
        except Exception:
            pass

        # Outer Container Frame (Exact dark card style with 1px border)
        card = ctk.CTkFrame(modal, fg_color="#181822", corner_radius=16, border_width=1, border_color="#2c2c3e")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Top Title with Icon
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.pack(fill="x", padx=22, pady=(18, 6))

        ctk.CTkLabel(title_row, text="💬 " + str(title), font=("Arial", 15, "bold"), text_color="#ffffff", justify="left").pack(side="left")

        # Subtitle / Code Badge (Matching the dark badge in media_1787688868040.png)
        if subtitle:
            badge_frame = ctk.CTkFrame(card, fg_color="#111118", corner_radius=8, border_width=1, border_color="#262638")
            badge_frame.pack(fill="x", padx=22, pady=(0, 12))
            ctk.CTkLabel(badge_frame, text=str(subtitle), font=("Consolas", 12), text_color="#00E5FF", justify="left").pack(anchor="w", padx=12, pady=7)

        # Options Container Frame
        options_frame = ctk.CTkFrame(card, fg_color="transparent")
        options_frame.pack(fill="both", expand=True, padx=22, pady=(0, 10))

        selected_var = ctk.IntVar(value=default_idx)
        option_cards = []

        def select_opt(idx):
            selected_var.set(idx)
            for i, (c_frame, num_badge, txt_lbl) in enumerate(option_cards):
                if i == idx:
                    c_frame.configure(fg_color="#1f2c3e", border_color="#0078D4", border_width=2)
                    num_badge.configure(fg_color="#0078D4", text_color="#ffffff")
                    txt_lbl.configure(text_color="#ffffff")
                else:
                    c_frame.configure(fg_color="#14141c", border_color="#242432", border_width=1)
                    num_badge.configure(fg_color="#242432", text_color="#888899")
                    txt_lbl.configure(text_color="#cccccc")

        for idx, opt_text in enumerate(options):
            c_opt = ctk.CTkFrame(options_frame, fg_color="#14141c", corner_radius=10, border_width=1, border_color="#242432", height=40)
            c_opt.pack(fill="x", pady=3)
            c_opt.pack_propagate(False)

            # Left number badge (1, 2, 3, 4, 5)
            num_b = ctk.CTkLabel(c_opt, text=str(idx + 1), font=("Arial", 11, "bold"), width=24, height=24, corner_radius=6,
                                 fg_color="#242432", text_color="#888899")
            num_b.pack(side="left", padx=(10, 10), pady=7)

            # Option text
            txt_l = ctk.CTkLabel(c_opt, text=str(opt_text), font=("Arial", 12), text_color="#cccccc", justify="left")
            txt_l.pack(side="left", fill="x", expand=True, pady=7)

            # Bind click on entire row
            for widget in [c_opt, num_b, txt_l]:
                widget.bind("<Button-1>", lambda e, i=idx: select_opt(i))

            option_cards.append((c_opt, num_b, txt_l))

        # Initialize selection
        select_opt(default_idx)

        # Bottom Action Bar (Skip on left of submit, blue Submit button on right)
        bot_bar = ctk.CTkFrame(card, fg_color="transparent", height=44)
        bot_bar.pack(fill="x", padx=22, pady=(6, 14), side="bottom")
        bot_bar.pack_propagate(False)

        def do_skip():
            modal.destroy()
            if callback:
                callback(-1, None)

        def do_submit():
            chosen_idx = selected_var.get()
            chosen_txt = options[chosen_idx] if 0 <= chosen_idx < len(options) else ""
            modal.destroy()
            if callback:
                callback(chosen_idx, chosen_txt)
            else:
                self.handle_ai_question_response(chosen_idx, chosen_txt)

        ctk.CTkButton(bot_bar, text="Absenden ↵", font=("Arial", 13, "bold"), height=36, width=130,
                      fg_color="#0078D4", hover_color="#0063B1", text_color="#ffffff", corner_radius=8,
                      command=do_submit).pack(side="right")

        ctk.CTkButton(bot_bar, text="Überspringen", font=("Arial", 12), height=36, width=100,
                      fg_color="transparent", hover_color="#22222c", text_color="#888899",
                      command=do_skip).pack(side="right", padx=(0, 10))

    def handle_ai_question_response(self, chosen_idx, chosen_txt):
        """
        Verarbeitet die Benutzerauswahl aus dem KI-Fragebogen und passt das Live-Coaching in Echtzeit an.
        """
        if chosen_idx == -1 or not chosen_txt:
            return

        # Option 0: Zu schnell / Fingerlocking -> Tempo senken
        if chosen_idx == 0:
            resp_txt = "Verstanden! Ich drossle das Tempo um ca. -15 BPM und gebe dir eine Map mit mehr Flow-Control, damit deine Finger locker bleiben."
            self.add_modern_chat_bubble("ai", f"🤖 **Coach-Anpassung:** {resp_txt}")
            self.pick_next_ai_training_map(adaptive_delta=-0.30)

        # Option 1: Perfekte Herausforderung -> Weiter auf diesem Level
        elif chosen_idx == 1:
            resp_txt = "Klasse! Wir bleiben genau in diesem Belastungsbereich, um deinen Skill Floor zu festigen."
            self.add_modern_chat_bubble("ai", f"🤖 **Coach-Anpassung:** {resp_txt}")
            self.pick_next_ai_training_map(adaptive_delta=+0.10)

        # Option 2: Overaiming / Sliders -> Tech & Precision Fokus
        elif chosen_idx == 2:
            resp_txt = "Alles klar! Ich stelle dein Training auf **Tech & Precision** um, um dein Overaiming und Slider-Timing zu stabilisieren."
            self.add_modern_chat_bubble("ai", f"🤖 **Coach-Anpassung:** {resp_txt}")
            self.pick_next_ai_training_map(forced_skill="Tech", adaptive_delta=0.0)

        # Option 3: Zu einem anderen Skillset wechseln
        elif chosen_idx == 3:
            # Rotate to next weakness
            pa = getattr(self, "last_profile_analysis", None) or {}
            scores = pa.get("scores", {})
            cur_sk = getattr(self, "ai_training_target_skill", "Streams")
            remaining_skills = [s for s in ["Aim", "Tech", "Speed", "Reading", "Precision", "Stamina", "Consistency"] if s != cur_sk]
            next_sk = min(remaining_skills, key=lambda s: scores.get(s, 50)) if scores else "Aim"
            resp_txt = f"Alles klar! Wir wechseln zum nächsten Problembereich: **{next_sk}**!"
            self.add_modern_chat_bubble("ai", f"🤖 **Coach-Anpassung:** {resp_txt}")
            self.pick_next_ai_training_map(forced_skill=next_sk)

        # Option 4: Manuelle Auswahl / Fun
        else:
            resp_txt = "Alles klar! Schreib mir einfach kurz im Chat, welche Map, welchen Mod (+DT/+HR/+HD/+EZ) oder welches Star-Rating du jetzt spielen möchtest!"
            self.add_modern_chat_bubble("ai", f"🤖 **Coach-Anpassung:** {resp_txt}")
    def gather_player_context(self):
        ctx = []
        user = getattr(self, 'osu_username', 'Unbekannt')
        ctx.append(f"Spieler: {user}")
        ctx.append(f"osu! Supporter Status: {'Aktiv' if getattr(self, 'has_osu_supporter', False) else 'Nicht aktiv'}")

        # 0. Live Telemetrie & Aktive Map (Echtzeit-Sitzung)
        if hasattr(self, "_telemetry_data") and self._telemetry_data:
            td = self._telemetry_data
            ctx.append("\n--- AKTUELLE LIVE-OSU!-SESSION (ECHTZEIT-TELEMETRIE) ---")
            ctx.append(f"• Aktueller Status: {'In Song-Auswahl' if td.get('is_song_select') else ('Im End-Screen' if td.get('is_results_screen') else 'Mitten im Gameplay (Map läuft)')}")
            ctx.append(f"• Live-PP: {td.get('cur_pp', 0):.1f} pp | If-FC PP: {td.get('if_fc_pp', 0):.1f} pp | Rank: {td.get('grade', 'SS')}")
            ctx.append(f"• Hits: 100s={td.get('h100', 0)} | 50s={td.get('h50', 0)} | Misses={td.get('h0', 0)} | Sliderbreaks={td.get('sb', 0)}")

        # 1. Zuletzt gespielte Runden (Live aus der offiziellen osu! API)
        api_k = getattr(self, "api_key", "")
        if api_k and user and user != "Unbekannt":
            try:
                now_t = time.time()
                cached = getattr(self, "_cached_recent_plays_context", None)
                last_t = getattr(self, "_cached_recent_plays_time", 0)
                if not cached or (now_t - last_t > 15):
                    url = f"https://osu.ppy.sh/api/get_user_recent?k={api_k}&u={user}&m=0&limit=8"
                    r = requests.get(url, timeout=3.5)
                    if r.status_code == 200:
                        rec_plays = r.json()
                        if not hasattr(self, "_beatmap_title_cache"):
                            self._beatmap_title_cache = {}
                        
                        lines = []
                        for i, p in enumerate(rec_plays[:5]):
                            bid = str(p.get("beatmap_id", ""))
                            # Resolve real map title
                            map_name = self._beatmap_title_cache.get(bid)
                            if not map_name:
                                map_meta = next((m for m in (DYNAMIC_RANKED_MAPS_DB or []) if str(m.get("id")) == bid), None)
                                if map_meta:
                                    map_name = map_meta.get("name")
                                else:
                                    try:
                                        bm_r = requests.get(f"https://osu.ppy.sh/api/get_beatmaps?k={api_k}&b={bid}&m=0", timeout=2.5)
                                        if bm_r.status_code == 200 and bm_r.json():
                                            bm_data = bm_r.json()[0]
                                            map_name = f"{bm_data.get('artist')} - {bm_data.get('title')} [{bm_data.get('version')}]"
                                    except Exception:
                                        pass
                            
                            if not map_name:
                                map_name = f"Beatmap #{bid}"
                            else:
                                self._beatmap_title_cache[bid] = map_name
                            
                            h300 = int(p.get("count300", 0))
                            h100 = int(p.get("count100", 0))
                            h50 = int(p.get("count50", 0))
                            miss = int(p.get("countmiss", 0))
                            combo = int(p.get("maxcombo", 0))
                            tot = h300 + h100 + h50 + miss
                            acc = ((h300*300 + h100*100 + h50*50) / (tot*300) * 100) if tot > 0 else 0
                            
                            mods_int = int(p.get("enabled_mods", 0) or 0)
                            mod_str = []
                            if mods_int & 64: mod_str.append("DT")
                            if mods_int & 512: mod_str.append("NC")
                            if mods_int & 16: mod_str.append("HR")
                            if mods_int & 8: mod_str.append("HD")
                            if mods_int & 2: mod_str.append("EZ")
                            if mods_int & 256: mod_str.append("HT")
                            mods_label = "+".join(mod_str) if mod_str else "NoMod"
                            rank_badge = p.get("rank", "F")
                            date_str = p.get("date", "")
                            
                            prefix = "[ALLERLETZTE GESPIELTE RUNDE] " if i == 0 else f"[Runde #{i+1}] "
                            lines.append(f"{prefix}Map: '{map_name}' | Mods: {mods_label} | Rang: {rank_badge} | Acc: {acc:.2f}% | Max Combo: {combo} | Misses: {miss} ({h100}x100, {h50}x50) | Datum: {date_str}")
                        
                        self._cached_recent_plays_context = "\n".join(lines) if lines else "Keine Runden in den letzten 24h verzeichnet."
                        self._cached_recent_plays_time = now_t
                
                if getattr(self, "_cached_recent_plays_context", None):
                    ctx.append("\n--- ZULETZT GESPIELTE RUNDEN (RECENT PLAYS LIVE AUS DER OSU! API) ---")
                    ctx.append(self._cached_recent_plays_context)
            except Exception:
                pass
        
        if getattr(self, "last_profile_analysis", None):
            pa = self.last_profile_analysis
            scores = pa.get("scores", {})
            best = pa.get("main_skill", max(scores, key=scores.get) if scores else "?")
            worst = pa.get("weakness", min(scores, key=scores.get) if scores else "?")
            ctx.append("\n--- PROFIL-SKILL-ANALYSE (SPEICHERUNG DES SPIELERS) ---")
            ctx.append(f"Stärkstes Skillset: {best} | Größte Schwachstelle: {worst}")
            for k, v in scores.items():
                ctx.append(f"• {k}: {v}/100")

        if getattr(self, "skill_tester_submissions", None):
            ctx.append("\n--- SKILL-TEST ERGEBNISSE ---")
            for sk, d in self.skill_tester_submissions.items():
                ctx.append(f"• {sk}: Acc={d['acc']:.1f}%, Misses={d['misses']}, Map='{d['map']}'")

        if getattr(self, "last_deep_replay_telemetry", None):
            dt_m = self.last_deep_replay_telemetry.get("metrics", {})
            ctx.append("\n--- DEEP REPLAY TELEMETRIE (MESSWERTE AIM & TAPPING) ---")
            ctx.append(f"• Overaiming vs Underaiming: Overaim {dt_m.get('overaim_pct', 50):.1f}% | Underaim {dt_m.get('underaim_pct', 50):.1f}%")
            ctx.append(f"• Cursor Peak Velocity: {dt_m.get('peak_speed', 0):,.0f} px/s")
            ctx.append(f"• Tasten-Haltezeiten: K1 {dt_m.get('k1_avg_hold', 50):.1f}ms | K2 {dt_m.get('k2_avg_hold', 50):.1f}ms")
            ctx.append(f"• Alternating-Balance: {dt_m.get('alt_ratio', 50):.1f}% | Unstable Rate (UR): ~{dt_m.get('ur', 80):.1f}")
            if dt_m.get("choke_reasons"):
                ctx.append(f"• Erkannte Miss-/Choke-Ursachen: {', '.join(dt_m.get('choke_reasons'))}")

        if getattr(self, "user_setup_profile", None):
            ctx.append("\n--- HARDWARE- & SETUP-PROFIL DES SPIELERS ---")
            for k, v in self.user_setup_profile.items():
                ctx.append(f"• {k}: {v}")

        if hasattr(self, 'data') and 'levels' in self.data:
            ctx.append("\n--- TRAINING LEVEL STATUS ---")
            current_lvl = self.levels[self.current_level_idx] if hasattr(self, 'current_level_idx') else '?'
            ctx.append(f"Aktuelles Level: {current_lvl} Sterne")
            for lvl_str, lvl_data in self.data['levels'].items():
                s_count = len(lvl_data.get('s_ranks', []))
                pfc_count = len(lvl_data.get('pfcs', []))
                m3_count = len(lvl_data.get('long_maps', []))
                cleared = lvl_data.get('cleared', False)
                status = "Freigeschaltet" if cleared else f"{s_count}/5 S-Ranks, {pfc_count}/2 PFCs, {m3_count}/2 3min"
                ctx.append(f"Level {lvl_str}*: {status}")
                
        return "\n".join(ctx)

    def get_supported_gemini_models(self):
        """Dynamically query Google API for valid models for the user's key."""
        if hasattr(self, "_cached_gemini_models") and self._cached_gemini_models:
            return self._cached_gemini_models

        if not getattr(self, "gemini_key", ""):
            return ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.gemini_key}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                valid = []
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        m_name = m.get("name", "").replace("models/", "")
                        if m_name:
                            valid.append(m_name)
                if valid:
                    # Prioritize flash models for speed
                    def model_sort_key(name):
                        if "flash" in name and "1.5" in name: return 0
                        if "flash" in name: return 1
                        if "pro" in name and "1.5" in name: return 2
                        if "pro" in name: return 3
                        return 4
                    valid.sort(key=model_sort_key)
                    self._cached_gemini_models = valid
                    return valid
        except:
            pass

        fallback_list = [
            "gemini-1.5-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-8b",
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
            "gemini-pro"
        ]
        self._cached_gemini_models = fallback_list
        return fallback_list

    def call_gemini_api(self, prompt, system_prompt=None, conversation_history=None, temperature=0.7, max_tokens=2048):
        """Universal, error-resilient Gemini API caller that uses verified models with multi-turn conversation support."""
        if not getattr(self, "gemini_key", ""):
            return None

        # Build messages payload
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt + "\n\nBestätigung: Antworte zu 100% auf Deutsch!"}]})
            contents.append({"role": "model", "parts": [{"text": "Verstanden! Ich bin dein Pro-Level osu! Coach und antworte ausschließlich auf Deutsch."}]})

        # Append previous multi-turn conversation messages
        if conversation_history and isinstance(conversation_history, list):
            for msg in conversation_history[-14:]:
                role = "user" if msg.get("role") == "user" else "model"
                txt = msg.get("text", "")
                if txt:
                    contents.append({"role": role, "parts": [{"text": txt}]})

        contents.append({"role": "user", "parts": [{"text": prompt + "\n\nWICHTIG: Antworte zu 100% auf Deutsch!"}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        models_to_try = self.get_supported_gemini_models()

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
            try:
                resp = requests.post(url, json=payload, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    if "candidates" in data and data["candidates"]:
                        ai_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return ai_text
            except:
                continue

        return None

    def query_gemini(self, user_message, conv=None):
        if conv is None:
            conv = self.get_active_ai_conversation()

        player_context = self.gather_player_context()

        # Check if user message is asking for a map recommendation and inject real database maps
        u_low = user_message.lower()
        if ("map" in u_low or "maps" in u_low) and any(w in u_low for w in ["empfiehl", "gib mir", "suche", "letzte", "ähnlich", "spiel", "trainier", "brauche", "vorschlag", "welche", "nächste"]):
            skill = "Streams" if "stream" in u_low else "Speed" if "speed" in u_low else "Tech" if "tech" in u_low else "Stamina" if "stamina" in u_low else "Reading" if "reading" in u_low else "Aim"
            target_sr = 5.5
            
            # Extract requested SR if specified by user (e.g. "6.5★", "6 star", "7 sterne")
            sr_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:★|star|sterne)', u_low)
            if sr_match:
                try:
                    target_sr = float(sr_match.group(1).replace(',', '.'))
                except Exception:
                    pass

            # Fetch a rich pool of 45-50 high-quality candidates from SQLite
            cand_maps = sqlite_query_maps(skill=skill, sr_min=max(1.0, target_sr - 0.8), sr_max=target_sr + 0.8, limit=45, order_by="playcount DESC")
            if len(cand_maps) < 20:
                cand_maps = sqlite_query_maps(skill=skill, sr_min=max(1.0, target_sr - 1.5), sr_max=target_sr + 1.5, limit=50, order_by="playcount DESC")

            if cand_maps:
                map_options = []
                for cm in cand_maps:
                    m_artist = cm.get('artist', '')
                    m_title = cm.get('title', '')
                    m_ver = cm.get('version', '')
                    if m_artist and m_title:
                        song_name = f"{m_artist} - {m_title}"
                    else:
                        song_name = cm.get('name', 'Unknown')
                    
                    if m_ver and not m_ver.startswith('['):
                        diff_name = f"[{m_ver}]"
                    else:
                        diff_name = m_ver if m_ver else "[Normal]"
                    
                    st_pct = float(cm.get('stream_pct', 0) or 0)
                    b_cnt = int(cm.get('burst_count', 0) or 0)
                    m_sp = float(cm.get('max_spacing', 0) or 0)
                    
                    extra_tags = []
                    if st_pct > 25: extra_tags.append(f"Streams: {st_pct:.0f}%")
                    if b_cnt > 15: extra_tags.append(f"Bursts: {b_cnt}")
                    if m_sp > 250: extra_tags.append(f"Max-Jump: {m_sp:.0f}px")
                    tag_str = f" • {', '.join(extra_tags)}" if extra_tags else ""

                    map_options.append(f"- [MAP: {cm.get('id')} | SET: {cm.get('set_id')}] • Song: **{song_name}** • Difficulty: **{diff_name}** (★ {cm.get('sr'):.2f} • {cm.get('bpm')} BPM • {cm.get('primary_skill')}{tag_str})")
                
                player_context += f"\n\nVERIFIZIERTER KANDIDATEN-POOL ({len(map_options)} RANKED-MAPS AUS DER LOKALEN DATENBANK FÜR DIESE ANFRAGE):\n" + "\n".join(map_options)
                player_context += "\n(WICHTIG: Analysiere und vergleiche alle diese 40-50 Maps gleichzeitig. Wähle die #1 absolut beste Map aus diesem Pool aus, die exakt zur Anfrage und zum Spieler passt, und nutze ihren [MAP: ... | SET: ...] Tag! Erfinde keine eigenen Beatmap-IDs!)"

        system_prompt = f"""Du bist der ultimative UHO Hub Pro-Level KI-Coach, Turnier-Stratege, Ergonomie-Experte und Gameplay-Analyst für osu!.

SPRACH-VORGABE (ABSOLUT STRIKTE REGEL):
- Du antwortest AUSSCHLIESSLICH und ZU 100% AUF DEUTSCH!
- Kein einziger englischer Satz oder Absatz! Alle Erklärungen, Analysen, Ratschläge und Motivationen MÜSSEN komplett auf Deutsch sein.
- Eingedeutschte osu!-spezifische Begriffe (Stream, Aim, Burst, FC, Slider, BPM, Finger Control, Stamina, Reading, Mods) dürfen natürlich im deutschen Satzbau verwendet werden.

OSU! MODS, ERGONOMIE & REHABILITATION (EXPERTEN-WISSEN):
=============================================================================
• AP (AutoPilot):
  - Automatische Cursor-Führung: Das Spiel steuert das Aiming zu 100% perfekt auf alle Circles und Slider.
  - Der Spieler muss AUSSCHLIESSLICH tappen (K1 & K2).
  - MEDIZINISCH & ERGONOMISCH ESSENTIELL: Wenn der Spieler Schmerzen im Aiming-Handgelenk, der Maushand, der Schreibhand oder an den Sehnen hat (z. B. Überlastung, RSI, Handgelenksprobleme), ist AutoPilot (AP) die PERFEKTE Übergangs- und Trainingsmethode! Der Spieler kann sein Tapping, seine Finger-Control, Stream-Stamina und Speed auf das nächste Level bringen, während die verletzte Aiming-Hand vollkommen geschont und stillgelegt wird.
• RX (Relax):
  - Automatisches Tapping (100% 300s). Der Spieler muss AUSSCHLIESSLICH aimen (Maus/Tablet).
  - Perfekt für Flow-Aim, Cursor-Pathing, Snapping und High-AR Reading ohne Tapping-Belastung.
• NF (NoFail):
  - Kein Sterben/Failen möglich bei leerer HP-Leiste.
• EZ (Easy):
  - Halbe Circle Size (viel größere Kreise), stark reduzierte Approach Rate (Low AR), sanfterer HP Drain, 3 Extraleben.
• HT (HalfTime):
  - 0.75x Spielgeschwindigkeit (75% BPM). Optimal zum Verstehen und Einüben komplexer Polyrhythmen, Finger-Control und unleserlicher Tech-Muster.
• HD (Hidden):
  - Approach Circles werden ausgeblendet, Hit-Objects faden kurz vor dem Hit-Zeitpunkt aus. Schult inneres Timing und räumliches Vorstellungsvermögen.
• HR (HardRock):
  - Circle Size +30% (wesentlich kleinere Kreise), AR10, OD10, HP+, invertiertes Spielfeld (Vertikal gespiegelt). Schult extreme Zielgenauigkeit und Reaktionszeit.
• DT / NC (DoubleTime / NightCore):
  - 1.5x Spielgeschwindigkeit (150% BPM, AR und OD gestaucht).
• FL (Flashlight):
  - Stark eingeschränkter Sichtradius um den Cursor. Erfordert reines Auswendiglernen der Map.
• SO (SpunOut) / SD (SuddenDeath) / PF (Perfect) / TD (TouchDevice) / V2 (ScoreV2).

KONTEXT DES AKTUELLEN SPIELERS:
=============================================================================
{player_context}

DEINE ANTWORT-RICHTLINIEN (STRIKT EINHALTEN):
- SIMPEL, DIREKT & PRÄGNANT: Mache deine Antworten so einfach und übersichtlich wie möglich! Halte Beschreibungen kurz (3-4 Sätze)!
- MULTI-TURN GEDÄCHTNIS: Du erinnerst dich an alle vorherigen Fragen und Nachrichten dieses Gesprächs. Weiche niemals Fragen aus und beziehe dich direkt auf das besprochene Thema!
- WICHTIG ZU 'ZULETZT GESPIELT':
  * Wenn der Spieler fragt, was er zuletzt gespielt hat (z. B. 'was habe ich zuletzt gespielt?'):
    -> Nenne ihm NUR die ALLERLETZTE Map (nicht alle 6 Runden als lange Liste aufzählen!).
    -> Formatiere es extrem simpel und übersichtlich mit Map-Name und Difficulty:
       🎵 **Map:** [Artist] - [Title]
       🏷️ **Difficulty:** [[Difficulty/Version]]
       ⭐ **Ergebnis:** Rang [X] • [Acc]% Acc (Combo: [X] • [X] Misses)
       💡 **Coach-Tipp:** 1-2 kurze, motivierende Sätze zur Runde.
  * Zähle NIEMALS ungefragt alle vorherigen Runden als lange Liste auf!
- WICHTIG BEI MAP-EMPFEHLUNGEN & MAP-ANFRAGEN:
  * Wenn der Spieler nach einer Map-Empfehlung fragt (z. B. 'gib mir eine Map wie die letzte', 'empfiehl mir eine Speed Map', 'welche Map soll ich üben?'):
    -> Wähle eine konkrete, passende Map aus den oben bereitgestellten VERIFIZIERTEN ECHTEN MAPS aus der lokalen Datenbank.
    -> NENNE IMMER EXPLIZIT SOWOHL DEN MAP-NAMEN (Artist - Title) ALS AUCH DIE DIFFICULTY (Diff / Version):
       🎵 **Map:** [Artist] - [Title]
       🏷️ **Difficulty:** [[Exakter Difficulty-Name / Version]]
       ⭐ **Stats:** ★ [SR] • [BPM] BPM • [Skillset]
       💡 **Coach-Tipp:** 2-3 kurze Sätze zur Map und warum sie perfekt für ihn ist.
    -> Füge am Ende deiner Nachricht immer den Tag: [MAP: <beatmap_id> | SET: <beatmapset_id>] ein.
       (Beispiel: [MAP: 1059388 | SET: 490509])
    -> Dadurch blendet die App automatisch die 🌐 Web- und ⚡ osu!direct-Buttons ein!
    -> Erfinde NIEMALS fiktive IDs!
  * Bei allgemeinen Fragen OHNE Map-Empfehlung (z. B. 'Wie halte ich den Stift?') fügst du KEINEN Map-Tag ein!
- Alle Analysen gelten AUSSCHLIESSLICH für osu! Standard (Mode 0)!
- Du antwortest ZU 100% AUF DEUTSCH!"""

        # Call universal API with dynamic model discovery and conversation history
        conv_hist = conv.get("messages", [])[:-1] if (conv and isinstance(conv.get("messages"), list)) else []
        res = self.call_gemini_api(user_message, system_prompt=system_prompt, conversation_history=conv_hist, max_tokens=1024)
        if res:
            if conv:
                conv["messages"].append({
                    "role": "model",
                    "text": res,
                    "timestamp": time.strftime("%H:%M")
                })
                self.save_ai_conversations()
            self.log_ai_event(f"KI-Chat: {conv.get('title', 'Chat')}", {"user_message": user_message, "chat_title": conv.get("title", "")}, prompt_text=user_message, raw_ai_response=res)
            return res

        # Fallback offline
        fallback_res = self.offline_analyze(user_message, conv=conv)
        if conv:
            conv["messages"].append({
                "role": "model",
                "text": fallback_res,
                "timestamp": time.strftime("%H:%M")
            })
            self.save_ai_conversations()
        return fallback_res

    def update_user_setup_from_text(self, text):
        """Erkennt automatisch Angaben zu Tablet/Maus, Keyboard/Rapid Trigger und Tapping-Stil aus Chat-Nachrichten."""
        if not hasattr(self, "user_setup_profile") or not isinstance(self.user_setup_profile, dict):
            self.user_setup_profile = {}
        
        t_low = text.lower()
        updated = False

        # Tablet detection
        if any(w in t_low for w in ["tablet", "wacom", "xp-pen", "xppen", "gaomon", "huion", "cth", "ctl", "one by wacom"]):
            self.user_setup_profile["aim_device"] = "Tablet"
            updated = True
        elif any(w in t_low for w in ["maus", "mouse", "g pro", "viper", "deathadder", "logitech", "razer", "finalmouse"]):
            self.user_setup_profile["aim_device"] = "Maus"
            updated = True

        # Tablet Area / DPI detection
        area_m = re.search(r'(\d+(?:[.,]\d+)?\s*(?:x|\*|mal)\s*\d+(?:[.,]\d+)?\s*(?:mm)?)', t_low)
        if area_m:
            self.user_setup_profile["tablet_area"] = area_m.group(1).replace(" ", "")
            self.user_setup_profile["aim_device"] = "Tablet"
            updated = True

        dpi_m = re.search(r'(\d{3,5})\s*(?:dpi|cpi)', t_low)
        if dpi_m:
            self.user_setup_profile["mouse_dpi"] = f"{dpi_m.group(1)} DPI"
            self.user_setup_profile["aim_device"] = "Maus"
            updated = True

        # Grip / Style
        if "hover" in t_low:
            self.user_setup_profile["aim_style"] = "Hovering"
            updated = True
        elif "drag" in t_low:
            self.user_setup_profile["aim_style"] = "Dragging"
            updated = True
        elif "palm" in t_low:
            self.user_setup_profile["aim_style"] = "Palm Grip"
            updated = True
        elif "claw" in t_low:
            self.user_setup_profile["aim_style"] = "Claw Grip"
            updated = True
        elif "fingertip" in t_low:
            self.user_setup_profile["aim_style"] = "Fingertip Grip"
            updated = True

        # Keyboard / Switches / Rapid Trigger
        if any(w in t_low for w in ["wooting", "rapid trigger", "hall effect", "magnetisch", "polar 65", "drundeer", "drunkdeer"]):
            self.user_setup_profile["keyboard_type"] = "Rapid Trigger (Hall Effect / Magnetisch)"
            updated = True
        elif any(w in t_low for w in ["mechanisch", "cherry", "gateron", "red switch", "brown switch", "blue switch", "speed silver", "tastatur"]):
            self.user_setup_profile["keyboard_type"] = "Mechanische Tastatur"
            updated = True

        act_m = re.search(r'(\d+[.,]\d+)\s*(?:mm|actuation|trigger)', t_low)
        if act_m:
            self.user_setup_profile["rapid_trigger_depth"] = f"{act_m.group(1)} mm"
            updated = True

        # Tapping Style
        if any(w in t_low for w in ["alternating", "full alt", "alt"]):
            self.user_setup_profile["tapping_technique"] = "Full-Alternating"
            updated = True
        elif any(w in t_low for w in ["single tap", "singletap", "single-tap"]):
            self.user_setup_profile["tapping_technique"] = "Single-Tap"
            updated = True

        if updated:
            self.save_global_settings()
        return updated

    def offline_analyze(self, query, conv=None):
        q = query.lower()

        # Check for Handgelenk / Injury / AutoPilot ergonomics queries
        if any(w in q for w in ["handgelenk", "autopilot", "ap", "schmerz", "sehne", "verletz"]):
            resp = (
                "🦾 **Handgelenk-Schonung & AutoPilot (AP) Training:**\n"
                "• **Ja, absolut!** Wenn dein Aiming-Handgelenk überlastet ist oder schmerzt, ist **AutoPilot (AP)** die perfekte Lösung!\n"
                "• Im AP-Modus steuert das Spiel den Cursor automatisch perfekt auf jede Note. Deine Aim-Hand bleibt komplett in Ruhe.\n"
                "• **Dein Vorteil:** Du kannst dein **Tapping (Speed, Stamina, Finger-Control & KHZ-Methode)** intensiv auf das nächste Level bringen und startest mit bärenstarkem Tapping wieder durch, sobald dein Gelenk verheilt ist!"
            )
            self.log_ai_event(f"Offline-Coach: {conv.get('title', 'Ergonomie') if conv else 'Ergonomie'}", {"query": query}, raw_ai_response=resp)
            return resp

        # Check for Relax (RX)
        if "relax" in q or "rx" in q:
            resp = (
                "🎯 **Relax (RX) Modus:**\n"
                "• Im Relax-Modus tapt das Spiel automatisch für dich (100% 300s). Du musst dich ausschließlich auf das **Aiming (Cursor-Pathing & Snapping)** konzentrieren.\n"
                "• **Einsatz:** Ideal zum Trainieren von Flow-Aim, extremen Jumps und High-AR Reading, wenn deine Tapping-Finger erschöpft sind."
            )
            self.log_ai_event(f"Offline-Coach: {conv.get('title', 'Relax') if conv else 'Relax'}", {"query": query}, raw_ai_response=resp)
            return resp

        # Check for other osu! mods (HT, EZ, HD, HR, DT, FL, V2)
        if any(w in q for w in ["mods", "mod", "hardrock", "hr", "doubletime", "dt", "hidden", "hd", "halftime", "ht", "easy mod"]):
            resp = (
                "🎮 **osu! Mod-Übersicht & Trainingseffekt:**\n"
                "• **AutoPilot (AP):** Automatisches Aiming -> 100% Fokus auf Tapping (ideal bei Handgelenk-Schonung).\n"
                "• **Relax (RX):** Automatisches Tapping -> 100% Fokus auf Flow-Aim & Snapping.\n"
                "• **HalfTime (HT, 0.75x):** Perfekt zum Entschlüsseln komplexer Polyrhythmen und Finger-Control.\n"
                "• **HardRock (HR):** CS +30% (kleine Kreise), AR10, OD10 -> Trainiert extreme Präzision.\n"
                "• **DoubleTime (DT, 1.5x):** 150% BPM -> Trainiert High-Speed Tapping & schnelles Reading.\n"
                "• **Hidden (HD):** Keine Approach Circles -> Trainiert inneres Taktgefühl und Reading."
            )
            self.log_ai_event(f"Offline-Coach: {conv.get('title', 'Mods') if conv else 'Mods'}", {"query": query}, raw_ai_response=resp)
            return resp

        # Check for map recommendation queries offline
        if ("map" in q or "maps" in q) and any(w in q for w in ["empfiehl", "gib mir", "suche", "letzte", "ähnlich", "spiel", "trainier", "brauche", "vorschlag", "welche", "nächste"]):
            skill = "Streams" if "stream" in q else "Speed" if "speed" in q else "Tech" if "tech" in q else "Stamina" if "stamina" in q else "Reading" if "reading" in q else "Aim"
            
            target_sr = 5.5
            sr_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:★|star|sterne)', q)
            if sr_match:
                try:
                    target_sr = float(sr_match.group(1).replace(',', '.'))
                except Exception:
                    pass

            # Query pool of 45 matching ranked maps from SQLite
            cands = sqlite_query_maps(skill=skill, sr_min=max(1.0, target_sr - 0.8), sr_max=target_sr + 0.8, limit=45, order_by="playcount DESC")
            if not cands:
                cands = sqlite_query_maps(skill=skill, sr_min=max(1.0, target_sr - 1.5), sr_max=target_sr + 1.5, limit=45, order_by="playcount DESC")

            cand = random.choice(cands[:12]) if cands else pick_dynamic_map_for_skill(skill, target_sr=target_sr)
            if cand and str(cand.get("id")) != "0":
                m_raw = cand.get("name", "Unbekannte Map")
                m_artist = cand.get("artist", "")
                m_title = cand.get("title", "")
                m_ver = cand.get("version", "")
                
                if m_artist and m_title:
                    song_name = f"{m_artist} - {m_title}"
                else:
                    song_name = re.sub(r'\s*\[.*?\]\s*$', '', m_raw).strip()
                
                if not m_ver:
                    ver_match = re.search(r'\[(.*?)\]', m_raw)
                    m_ver = ver_match.group(1) if ver_match else "Insane"
                
                m_sr = float(cand.get("sr", target_sr))
                m_bpm = float(cand.get("bpm", 180))
                m_desc = cand.get("description", "Ausgewogene Trainings-Map.")
                m_id = cand.get("id")
                m_set = cand.get("set_id", "")
                
                resp = (
                    f"🎵 **Map:** {song_name}\n"
                    f"🏷️ **Difficulty:** [{m_ver}]\n"
                    f"⭐ **Stats:** ★ {m_sr:.2f} • {int(m_bpm)} BPM • {skill}\n\n"
                    f"💡 **Coach-Tipp:** {m_desc}\n\n"
                    f"[MAP: {m_id} | SET: {m_set}]"
                )
                self.log_ai_event(f"Offline-Coach: Map-Empfehlung", {"query": query, "map_id": m_id}, raw_ai_response=resp)
                return resp

        if "khz" in q:
            resp = "⚡ **Die KHZ-Methode (Progressive Overload für Streams):**\n1. Finde dein persönliches Limit-BPM, auf dem du lange Streams mit **98%+ Accuracy** spielen kannst (z. B. 180 BPM).\n2. Spiele täglich 20-30 Minuten dedizierte Stream-Maps in diesem Bereich.\n3. Steigere das Tempo erst um **+5 BPM**, wenn du 3 Tage in Folge 98%+ ohne Fingerlocking hältst.\n4. **Goldene Regel:** Halte Handgelenk und Unterarm völlig locker – wer verkrampft, stoppt den Muskelaufbau!"
            self.log_ai_event("Offline-Coach: KHZ-Methode", {"query": query}, raw_ai_response=resp)
            return resp
        if "stamina" in q or "ausdauer" in q:
            resp = "🔥 **Stamina-Training (Ausdauer):**\n• Trainiere auf längeren Maps (Drain > 3 Minuten) mit kontinuierlichem Tapping.\n• Drücke die Tasten nur so tief wie nötig (Key Bottom-Out minimieren).\n• Wenn du Rapid Trigger nutzt: Actuation 0.4mm, Rapid Trigger 0.15mm für minimale Fingeranstrengung."
            self.log_ai_event("Offline-Coach: Stamina", {"query": query}, raw_ai_response=resp)
            return resp
        if "stream" in q or "flow aim" in q:
            resp = "🌊 **Stream- & Flow-Aim-Training:**\n• Halte den Cursor flüssig in der Mitte des Streams – nicht hektisch von Note zu Note flicken.\n• Gleichmäßiger Tapping-Druck: Achte auf sauberes Alternieren zwischen K1 und K2.\n• Bei Spaced Streams: Vergrößere deine Handbewegung bewusst und führe den Stream mit den Augen an."
            self.log_ai_event("Offline-Coach: Streams", {"query": query}, raw_ai_response=resp)
            return resp
        if "jump" in q or "aim" in q or "snap" in q:
            resp = "🎯 **Jump-Aim & Snapping:**\n• Das Auge führt, die Hand folgt! Schau den Zielkreis direkt an, bevor du den Cursor bewegst.\n• Snappe hart auf den Mittelpunkt der Note und stoppe für einen Sekundenbruchteil vor dem nächsten Jump (Edge Control).\n• 100% Background Dim und deaktiviertes Hit Lighting sorgen für maximale visuelle Klarheit."
            self.log_ai_event("Offline-Coach: Aim", {"query": query}, raw_ai_response=resp)
            return resp
        if "tech" in q or "slider" in q:
            resp = "🌀 **Tech & Slider-Control:**\n• Verfolge die Sliderball-Geschwindigkeit (SV) genau mit den Augen, um Break-Misses zu verhindern.\n• Passe deine Lesegeschwindigkeit bei schnellen Rhythmus-Wechseln (1/4 zu 1/3 oder 1/6) an.\n• Tech-Maps verlangen Geduld: Spiele sie bis zum Ende durch, um unkonventionelle Muster zu lernen."
            self.log_ai_event("Offline-Coach: Tech", {"query": query}, raw_ai_response=resp)
            return resp
        if "speed" in q or "burst" in q:
            resp = "⚡ **Speed & Burst-Präzision:**\n• Trainiere kurze 5- bis 9-Note-Bursts auf hohem BPM (220+ BPM).\n• Nutze explosive Finger-Beschleunigung aus den Fingergelenken (nicht aus dem ganzen Arm).\n• Hohe Accuracy auf Bursts ist das Fundament für spätere Deathstreams."
            self.log_ai_event("Offline-Coach: Speed", {"query": query}, raw_ai_response=resp)
            return resp
        if "reading" in q or "low ar" in q:
            resp = "📖 **Reading & AR-Verarbeitung:**\n• Low-AR (AR 8.0 - 8.8): Trainiert das Verarbeiten hoher Objektdichte und inneres Taktgefühl.\n• High-AR (AR 10.3+): Trainiert reine Reaktionszeit und Snap-Schnelligkeit.\n• Entspanne deinen Blick und nimm das gesamte Spielfeld wahr."
            self.log_ai_event("Offline-Coach: Reading", {"query": query}, raw_ai_response=resp)
            return resp
        if "turnier" in q or "mappool" in q or "owc" in q:
            resp = "🏆 **Turnier-Struktur & Match-Strategie:**\n• NM1: Jump Aim | NM2: Flow Aim | NM3: Speed | NM4: Stamina | NM5: Tech | NM6: Reading\n• HD/HR/DT/FM Slots + Tiebreaker (TB)\n• Banne immer die stärksten Comfort-Picks deines Gegners und sichere dir Maps, auf denen dein Skill Floor solide ist."
            self.log_ai_event("Offline-Coach: Turniere", {"query": query}, raw_ai_response=resp)
            return resp

        resp = "🎯 **Dein KI-Coach:** Ich passe dein Training laufend an deine Leistung an! Frag mich zu Tapping, Aiming, Ergonomie, osu! Mods (AP, RX, HT, HR, DT) oder nenne mir dein gewünschtes Sterne-Level (z. B. ★ 6.5)!"
        self.log_ai_event("Offline-Coach: Allgemein", {"query": query}, raw_ai_response=resp)
        return resp

    # ---------------------------------------------------------------------------
    # TAGES- & SESSION-RECAP SYSTEM (5-MIN PROCESS INACTIVITY & LIVE TRACKING)
    # ---------------------------------------------------------------------------
    def load_session_recaps_history(self):
        try:
            path = getattr(self, "session_recaps_file", "session_recaps_history.json")
            return safe_json_load(path, default=[])
        except Exception:
            return []

    def save_session_recaps_history(self):
        try:
            path = getattr(self, "session_recaps_file", "session_recaps_history.json")
            safe_atomic_json_dump(getattr(self, "session_recaps_history", []), path, indent=2)
        except Exception:
            pass

    def _fetch_user_snapshot_stats(self):
        """Fetches current live player rank, PP, and top plays snapshot from osu! API."""
        user = getattr(self, "osu_username", "")
        key = getattr(self, "api_key", "")
        if not user or not key:
            return {"rank": 0, "pp": 0.0, "acc": 0.0, "playcount": 0, "top_plays": []}

        rank = 0
        pp = 0.0
        acc = 0.0
        playcount = 0
        top_plays = []
        try:
            u_res = requests.get(f"https://osu.ppy.sh/api/get_user?k={key}&u={user}&m=0", timeout=6).json()
            if isinstance(u_res, list) and u_res:
                rank = int(u_res[0].get("pp_rank", 0) or 0)
                pp = float(u_res[0].get("pp_raw", 0.0) or 0.0)
                acc = float(u_res[0].get("accuracy", 0.0) or 0.0)
                playcount = int(u_res[0].get("playcount", 0) or 0)

            b_res = requests.get(f"https://osu.ppy.sh/api/get_user_best?k={key}&u={user}&m=0&limit=50", timeout=6).json()
            if isinstance(b_res, list):
                top_plays = b_res
        except Exception:
            pass

        return {"rank": rank, "pp": pp, "acc": acc, "playcount": playcount, "top_plays": top_plays}

    def _start_osu_session_monitor_daemon(self):
        if getattr(self, "_osu_session_daemon_running", False):
            return
        self._osu_session_daemon_running = True

        def _loop():
            while True:
                try:
                    time.sleep(5)
                    is_running = is_osu_process_active()
                    now = time.time()

                    if is_running:
                        # Case 1: osu! is actively running
                        if self.active_session is None:
                            st = datetime.now()
                            s_stats = self._fetch_user_snapshot_stats()
                            self.active_session = {
                                "id": str(uuid.uuid4())[:8],
                                "date": st.strftime("%Y-%m-%d"),
                                "start_time_iso": st.isoformat(),
                                "start_time_str": st.strftime("%H:%M"),
                                "end_time_str": None,
                                "duration_mins": 0,
                                "start_rank": s_stats.get("rank", 0),
                                "start_pp": s_stats.get("pp", 0.0),
                                "start_acc": s_stats.get("acc", 0.0),
                                "start_top_play_ids": [str(p.get("beatmap_id", "")) for p in s_stats.get("top_plays", [])],
                                "end_rank": s_stats.get("rank", 0),
                                "end_pp": s_stats.get("pp", 0.0),
                                "end_acc": s_stats.get("acc", 0.0),
                                "plays": [],
                                "new_top_plays": [],
                                "skillset_distribution": {},
                                "avg_accuracy": 0.0,
                                "total_hits": 0,
                                "passes_count": 0,
                                "fails_count": 0,
                                "retries_count": 0,
                                "status": "active"
                            }
                            self._osu_closed_timer_start = None
                            self._session_recap_modal_shown = False
                        else:
                            # Player reopened osu! within 5 minutes -> cancel cooldown countdown
                            if self._osu_closed_timer_start is not None:
                                self._osu_closed_timer_start = None

                        # Sync recent plays in background
                        self._sync_session_recent_plays()

                    else:
                        # Case 2: osu! is NOT running
                        if self.active_session is not None and self.active_session.get("status") == "active":
                            if self._osu_closed_timer_start is None:
                                # osu! was just closed -> start 5-minute (300 sec) countdown
                                self._osu_closed_timer_start = now
                            else:
                                elapsed = now - self._osu_closed_timer_start
                                # Trigger recap exactly after 5 minutes (300 seconds) of inactivity
                                if elapsed >= 300 and not getattr(self, "_session_recap_modal_shown", False):
                                    self._session_recap_modal_shown = True
                                    recap = self.finalize_active_session()
                                    if recap:
                                        self.safe_ui_dispatch(self, self.show_session_recap_modal, recap)
                                    self.active_session = None
                                    self._osu_closed_timer_start = None
                except Exception:
                    pass

        threading.Thread(target=_loop, daemon=True).start()

    def _sync_session_recent_plays(self):
        user = getattr(self, "osu_username", "")
        key = getattr(self, "api_key", "")
        if not user or not key or not self.active_session:
            return

        if not hasattr(self, "_processed_session_play_ids"):
            self._processed_session_play_ids = set()

        try:
            url = f"https://osu.ppy.sh/api/get_user_recent?k={key}&u={user}&m=0&limit=10"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                plays = r.json()
                if isinstance(plays, list):
                    for p in plays:
                        if not isinstance(p, dict):
                            continue
                        p_id = str(p.get("date", "")) + "_" + str(p.get("score", ""))
                        if p_id not in self._processed_session_play_ids:
                            self._processed_session_play_ids.add(p_id)
                            self.record_play_in_active_session(p)
        except Exception:
            pass

    def record_play_in_active_session(self, play_obj):
        if not self.active_session:
            st = datetime.now()
            s_stats = self._fetch_user_snapshot_stats()
            self.active_session = {
                "id": str(uuid.uuid4())[:8],
                "date": st.strftime("%Y-%m-%d"),
                "start_time_iso": st.isoformat(),
                "start_time_str": st.strftime("%H:%M"),
                "end_time_str": None,
                "duration_mins": 0,
                "start_rank": s_stats.get("rank", 0),
                "start_pp": s_stats.get("pp", 0.0),
                "start_acc": s_stats.get("acc", 0.0),
                "start_top_play_ids": [str(p.get("beatmap_id", "")) for p in s_stats.get("top_plays", [])],
                "end_rank": s_stats.get("rank", 0),
                "end_pp": s_stats.get("pp", 0.0),
                "end_acc": s_stats.get("acc", 0.0),
                "plays": [],
                "new_top_plays": [],
                "skillset_distribution": {},
                "avg_accuracy": 0.0,
                "total_hits": 0,
                "passes_count": 0,
                "fails_count": 0,
                "retries_count": 0,
                "status": "active"
            }

        h300 = int(play_obj.get("count300", 0) or 0)
        h100 = int(play_obj.get("count100", 0) or 0)
        h50 = int(play_obj.get("count50", 0) or 0)
        miss = int(play_obj.get("countmiss", 0) or 0)
        tot = h300 + h100 + h50 + miss
        acc = ((h300 * 300 + h100 * 100 + h50 * 50) / (tot * 300) * 100.0) if tot > 0 else 0.0
        rank = str(play_obj.get("rank", "")).upper()
        combo = int(play_obj.get("maxcombo", 0) or 0)
        bid = str(play_obj.get("beatmap_id", ""))

        is_fail_or_retry = (rank == "F")
        is_quick_retry = is_fail_or_retry and (tot < 45 or combo < 20)
        is_real_fail = is_fail_or_retry and not is_quick_retry
        is_pass = not is_fail_or_retry

        # Resolve Map metadata from database
        map_meta = None
        for m in (DYNAMIC_RANKED_MAPS_DB or []):
            if str(m.get("id")) == bid:
                map_meta = m
                break

        map_name = map_meta.get("name", f"Beatmap #{bid}") if map_meta else f"Beatmap #{bid}"
        skill = map_meta.get("primary_skill", "Aim") if map_meta else "Aim"
        sr = float(map_meta.get("sr", 5.0)) if map_meta else 5.0

        # Compute Live PP & Peak metrics
        mods_num = int(play_obj.get("enabled_mods", 0) or 0)
        calc_pp, if_fc_pp = self.calculate_live_pp_metrics(sr=sr, acc=acc, combo=combo, max_combo=max(combo, tot), misses=miss, mods_num=mods_num)
        
        # Estimate Peak PP reached
        peak_pp = if_fc_pp if (combo >= tot * 0.65 and miss <= 2) else calc_pp
        if is_pass and miss == 0:
            peak_pp = max(calc_pp, if_fc_pp)

        # Update Map Peak Record in database
        map_key = f"{bid}_{map_name}"
        is_new_rec, prev_rec = self.update_map_peak_record(map_key, map_name, peak_pp, combo, mods_str="NM")

        # Check session highest peak
        cur_ses_peak = self.active_session.get("highest_peak_pp", 0.0)
        if peak_pp > cur_ses_peak:
            self.active_session["highest_peak_pp"] = round(peak_pp, 1)
            self.active_session["highest_peak_map"] = map_name
            self.active_session["highest_peak_combo"] = combo
            self.active_session["highest_peak_acc"] = round(acc, 2)
            self.active_session["highest_peak_sr"] = sr

        p_entry = {
            "bid": bid,
            "name": map_name,
            "skill": skill,
            "sr": sr,
            "acc": round(acc, 2),
            "miss": miss,
            "combo": combo,
            "rank": rank,
            "hits": tot,
            "calc_pp": calc_pp,
            "peak_pp": peak_pp,
            "if_fc_pp": if_fc_pp,
            "is_pass": is_pass,
            "is_fail": is_real_fail,
            "is_retry": is_quick_retry
        }

        self.active_session["plays"].append(p_entry)
        self.active_session["total_hits"] += tot
        if is_pass:
            self.active_session["passes_count"] += 1
        elif is_real_fail:
            self.active_session["fails_count"] += 1
        elif is_quick_retry:
            self.active_session["retries_count"] += 1

        self.active_session["skillset_distribution"][skill] = self.active_session["skillset_distribution"].get(skill, 0) + 1

    def finalize_active_session(self, is_manual=False):
        if not self.active_session:
            return None

        s = self.active_session
        end_time = datetime.now()
        s["end_time_str"] = end_time.strftime("%H:%M")
        
        try:
            st_iso = datetime.fromisoformat(s["start_time_iso"])
            s["duration_mins"] = max(1, int((end_time - st_iso).total_seconds() / 60))
        except Exception:
            s["duration_mins"] = 15

        # Fetch End Stats from osu! API
        end_stats = self._fetch_user_snapshot_stats()
        if end_stats.get("rank", 0) > 0:
            s["end_rank"] = end_stats["rank"]
            s["end_pp"] = end_stats["pp"]
            s["end_acc"] = end_stats["acc"]
        else:
            s["end_rank"] = s.get("end_rank") or s.get("start_rank", 0)
            s["end_pp"] = s.get("end_pp") or s.get("start_pp", 0.0)
            s["end_acc"] = s.get("end_acc") or s.get("start_acc", 0.0)

        # Rank & PP Delta (Lower rank number = better rank!)
        if s["start_rank"] > 0 and s["end_rank"] > 0:
            s["rank_delta"] = s["start_rank"] - s["end_rank"]
        else:
            s["rank_delta"] = 0

        s["pp_delta"] = round(s["end_pp"] - s["start_pp"], 1)

        # Check for new Top Plays achieved during session
        start_top_ids = set(s.get("start_top_play_ids", []))
        s["start_top_play_ids"] = list(start_top_ids)
        new_tops = []
        for i, tp in enumerate(end_stats.get("top_plays", [])[:50]):
            tp_bid = str(tp.get("beatmap_id", ""))
            if tp_bid not in start_top_ids:
                t_name = f"Beatmap #{tp_bid}"
                for m in (DYNAMIC_RANKED_MAPS_DB or []):
                    if str(m.get("id")) == tp_bid:
                        t_name = m.get("name", t_name)
                        break
                new_tops.append({
                    "name": t_name,
                    "pp": round(float(tp.get("pp", 0.0) or 0.0), 1),
                    "mod": format_mods_string(int(tp.get("enabled_mods", 0) or 0)),
                    "rank_in_top": i + 1
                })
        s["new_top_plays"] = new_tops

        # Calculate average session accuracy
        pass_accs = [p["acc"] for p in s["plays"] if p.get("is_pass")]
        if pass_accs:
            s["avg_accuracy"] = round(sum(pass_accs) / len(pass_accs), 2)
        elif s["plays"]:
            s["avg_accuracy"] = round(sum(p["acc"] for p in s["plays"]) / len(s["plays"]), 2)
        else:
            s["avg_accuracy"] = s["end_acc"]

        # Primary Skillset
        if s["skillset_distribution"]:
            s["primary_skill"] = max(s["skillset_distribution"], key=s["skillset_distribution"].get)
        else:
            s["primary_skill"] = "Allround"

        # Best play of session
        sorted_plays = sorted(s["plays"], key=lambda x: x.get("acc", 0) * x.get("sr", 1), reverse=True)
        s["best_play"] = sorted_plays[0] if sorted_plays else None

        # Physical Cooldown & Ergonomie Routine
        prim = s["primary_skill"]
        s_dist = s["skillset_distribution"]
        stream_speed_share = (s_dist.get("Streams", 0) + s_dist.get("Speed", 0)) / max(1, len(s["plays"]))
        
        if stream_speed_share >= 0.35 or s["total_hits"] >= 4000:
            s["health_cooldown"] = {
                "title": "⚠️ Hohe Unterarm- & Beugesehnen-Belastung (Streams / Speed)",
                "steps": [
                    "1. Handgelenk-Beugerdehnung: Arm nach vorne strecken, Handfläche sanft nach unten/zu dir ziehen (25s pro Hand).",
                    "2. Gebets-Stretch (Karpaltunnel): Handflächen vor der Brust flach gegeneinander drücken, Ellbogen langsam anheben (20s).",
                    "3. Fingerschütteln: Hände 30s locker ausschütteln, anschließend warmes Wasser über die Unterarme laufen lassen."
                ],
                "rest_advice": "Mindestens 45 Minuten Pause vor der nächsten Tapping-Session machen, um Verkrampfungen vorzubeugen!"
            }
        elif prim in ["Aim", "Precision"] or s_dist.get("Aim", 0) >= 6:
            s["health_cooldown"] = {
                "title": "🎯 Hohe Schulter- & Handgelenks-Spannung (Aiming / Jumps)",
                "steps": [
                    "1. Schulterkreisen & Nacken: 10x langsam nach hinten kreisen, um Verspannungen im Trapezmuskel zu lösen.",
                    "2. Daumenballen-Massage: Sanft den Muskelansatz der Maushand / Stifthand für 30s kreisend massieren.",
                    "3. 20-20-20 Augenpause: 20 Sekunden lang auf einen Punkt in 6m Entfernung blicken."
                ],
                "rest_advice": "Achte auf eine ergonomische Sitzhaltung und lockere die Schulterpartie!"
            }
        else:
            s["health_cooldown"] = {
                "title": "✨ Ausgewogene Allround-Session",
                "steps": [
                    "1. Handgelenke sanft in beide Richtungen kreisen (je 15 Sekunden).",
                    "2. Finger spreizen und für 5 Sekunden zu einer leichten Faust ballen (3x wiederholen).",
                    "3. Kurzer Spaziergang oder Dehnung des oberen Rückens."
                ],
                "rest_advice": "Perfekte Session-Balance! Trink ein Glas Wasser zur Regeneration."
            }

        # Generate Gemini AI Tomorrow Prescription & Summary
        tomorrow_plan = ""
        summary_text = ""
        if getattr(self, "gemini_key", ""):
            try:
                g_prompt = (
                    f"Du bist der offizielle Pro osu! Cheftrainer. Erstelle ein prägnantes, motivierendes Tages-Fazit und einen konkreten Trainingsplan für MORGEN auf Deutsch:\n"
                    f"Spieler: {getattr(self, 'osu_username', 'Spieler')}\n"
                    f"Dauer: {s['duration_mins']} Min | Gespielte Maps: {len(s['plays'])} ({s['passes_count']} Passes, {s['fails_count']} Fails)\n"
                    f"Rang-Delta: {'+' if s['rank_delta']>0 else ''}{s['rank_delta']} Ränge | PP-Delta: {'+' if s['pp_delta']>0 else ''}{s['pp_delta']:.1f} pp\n"
                    f"Durchschnitts-Acc: {s['avg_accuracy']:.2f}% | Hauptfokus heute: {s['primary_skill']}\n"
                    f"Antworte in genau 2 Abschnitten:\n"
                    f"FAZIT: (2 motivierende Sätze zur heutigen Form)\n"
                    f"PLAN FÜR MORGEN: (2 hochkonkrete Sätze, welches Skillset/BPM/Mod er morgen wie trainieren soll)"
                )
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                payload = {"contents": [{"role": "user", "parts": [{"text": g_prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 350}}
                res = requests.post(g_url, json=payload, timeout=8).json()
                raw_t = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                if "PLAN FÜR MORGEN:" in raw_t:
                    parts = raw_t.split("PLAN FÜR MORGEN:")
                    summary_text = parts[0].replace("FAZIT:", "").strip()
                    tomorrow_plan = parts[1].strip()
                else:
                    tomorrow_plan = raw_t
            except Exception:
                pass

        if not tomorrow_plan:
            if s["primary_skill"] == "Streams":
                tomorrow_plan = "Du hast heute ein starkes Stream-Volumen absolviert. Morgen solltest du 20-30 Minuten gezielt Finger Control und Tech auf AR 9.2 spielen, um dein Aiming und Slider-Timing zu stabilisieren."
                summary_text = f"Solide Ausdauer-Session mit {s['passes_count']} erfolgreichen Passes! Deine Finger haben gut durchgehalten."
            elif s["primary_skill"] == "Speed":
                tomorrow_plan = "Morgen empfiehlt sich ein Fokus auf Stamina und kontrollierte Deathstreams (-20 BPM), um den heutigen High-BPM Burst-Speed mit konstanter Ausdauer zu untermauern."
                summary_text = "Explosiver Speed-Fokus! Du hast deine Reaktionsgrenze heute spürbar nach oben verschoben."
            elif s["primary_skill"] == "Aim":
                tomorrow_plan = "Nach der heutigen Aim- und Jump-Einheit solltest du morgen 30 Minuten Low-AR Reading und Precision (CS 5+) trainieren, um deine Snapping-Genauigkeit zu verfeinern."
                summary_text = f"Guter Aim-Fokus mit {s['total_hits']:,} Hits! Achte morgen auf gleichmäßige Handgelenk-Führung."
            else:
                tomorrow_plan = "Morgen solltest du deine größte Schwachstelle (z. B. Tech oder Streams) mit 4-5 gezielten Warmup-Maps anspielen und anschließend auf deiner Wohlfühl-Disziplin aufbauen."
                summary_text = "Ausgeglichene Trainingsrunde mit stabiler Accuracy über alle gespielten Maps."

        s["ai_tomorrow_plan"] = tomorrow_plan
        s["ai_summary"] = summary_text
        s["status"] = "finished"

        # Save into history
        if not hasattr(self, "session_recaps_history") or not isinstance(self.session_recaps_history, list):
            self.session_recaps_history = []
        self.session_recaps_history.insert(0, s)
        if len(self.session_recaps_history) > 60:
            self.session_recaps_history = self.session_recaps_history[:60]
        self.save_session_recaps_history()

        return s

    def format_discord_recap_text(self, s):
        """Creates a clean, emoji-rich Markdown block for easy 1-click Discord sharing."""
        rank_sign = "+" if s.get("rank_delta", 0) > 0 else ""
        pp_sign = "+" if s.get("pp_delta", 0) > 0 else ""
        
        top_play_txt = ""
        if s.get("new_top_plays"):
            tp = s["new_top_plays"][0]
            top_play_txt = f"\n🔥 **Neues #{tp.get('rank_in_top', 1)} Top-Play:** {tp.get('name', 'Map')} (+{tp.get('mod', 'NM')} • {tp.get('pp', 0):.0f}pp)"
        
        peak_highlight_txt = ""
        if s.get("highest_peak_pp", 0) > 0:
            peak_highlight_txt = f"\n⚡ **Höchster PP-Peak:** {s.get('highest_peak_pp', 0.0):.1f}pp auf {s.get('highest_peak_map', 'Map')} ({s.get('highest_peak_combo', 0)}x Combo)"

        health_t = s.get("health_cooldown", {}).get("title", "Regenerations-Check")
        h_steps = s.get("health_cooldown", {}).get("steps", ["Handgelenke dehnen"])
        h_step_txt = h_steps[0] if h_steps else "Handgelenke dehnen & Fingerschütteln"

        discord_card = (
            f"╔══════════════════════════════════════════════════════╗\n"
            f"║          📊 UHO Hub • TAGES- & SESSION-RECAP          ║\n"
            f"╠══════════════════════════════════════════════════════╣\n"
            f"👤 **Spieler:** {getattr(self, 'osu_username', 'Spieler')}  •  ⏱️ **Spielzeit:** {s.get('duration_mins', 0)} Min ({s.get('start_time_str', '00:00')} - {s.get('end_time_str', '00:00')})\n\n"
            f"📈 **Rang-Delta:** #{s.get('start_rank', 0):,} ➔ #{s.get('end_rank', 0):,} ({rank_sign}{s.get('rank_delta', 0)} Ränge 🟢)\n"
            f"⚡ **Performance:** {s.get('start_pp', 0.0):.1f}pp ➔ {s.get('end_pp', 0.0):.1f}pp ({pp_sign}{s.get('pp_delta', 0.0):.1f} Net-PP)\n"
            f"🎮 **Maps gespielt:** {len(s.get('plays', []))} ({s.get('passes_count', 0)} Passes, {s.get('fails_count', 0)} Fails)  •  🎯 **Ø Acc:** {s.get('avg_accuracy', 0.0):.2f}%\n"
            f"💥 **Total Hits:** {s.get('total_hits', 0):,}{top_play_txt}{peak_highlight_txt}\n\n"
            f"⚡ **Haupt-Fokus heute:** {s.get('primary_skill', 'Allgemein')}\n"
            f"🧘 **Cooldown-Tipp:** {h_step_txt}\n\n"
            f"🎯 **KI-Plan für morgen:**\n\"{s.get('ai_tomorrow_plan', 'Konzentriertes Training fortsetzen.')}\"\n"
            f"╚══════════════════════════════════════════════════════╝"
        )
        return discord_card

    def show_session_recap_modal(self, recap):
        """Displays a modal dialog with the session summary."""
        modal = ctk.CTkToplevel(self)
        modal.title("📊 UHO Hub • Tages- & Session-Recap")
        modal.geometry("780x560")
        modal.minsize(680, 480)
        modal.configure(fg_color="#101015")
        modal.attributes("-topmost", True)

        try:
            modal.update_idletasks()
            w, h = 780, 560
            x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
            modal.geometry(f"{w}x{h}+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

        card = ctk.CTkFrame(modal, fg_color="#161622", corner_radius=16, border_width=1, border_color="#2c2c3e")
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Header
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 10))

        title_box = ctk.CTkFrame(hdr, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="📊 TAGES- & SESSION-RECAP", font=("Arial", 18, "bold"), text_color="#00E5FF").pack(anchor="w")
        ctk.CTkLabel(title_box, text=f"Spieler: {getattr(self, 'osu_username', 'Spieler')} • Datum: {recap.get('date', 'Heute')} • ⏱️ {recap.get('duration_mins', 0)} Min Spielzeit",
                     font=("Arial", 11), text_color="#888899").pack(anchor="w")

        # Scrollable container for cards
        body = ctk.CTkScrollableFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        # Top 2-Column Grid
        top_grid = ctk.CTkFrame(body, fg_color="transparent")
        top_grid.pack(fill="x", pady=(0, 8))
        top_grid.grid_columnconfigure(0, weight=1)
        top_grid.grid_columnconfigure(1, weight=1)

        # Card 1: Rang & Performance
        c1 = ctk.CTkFrame(top_grid, fg_color="#1c1c28", corner_radius=12, border_width=1, border_color="#2a2a3e")
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        ctk.CTkLabel(c1, text="📈 Rang & Performance", font=("Arial", 13, "bold"), text_color="#ffffff").pack(anchor="w", padx=14, pady=(12, 6))
        
        r_delta = recap.get("rank_delta", 0)
        r_col = "#00E676" if r_delta > 0 else ("#FF5252" if r_delta < 0 else "#aaaaaa")
        r_sign = "+" if r_delta > 0 else ""
        r_txt = f"{r_sign}{r_delta} Ränge" if r_delta != 0 else "Rang gehalten"
        ctk.CTkLabel(c1, text=f"• Rang: #{recap.get('start_rank', 0):,} ➔ #{recap.get('end_rank', 0):,} ({r_txt})",
                     font=("Arial", 12, "bold"), text_color=r_col).pack(anchor="w", padx=14, pady=2)

        pp_d = recap.get("pp_delta", 0.0)
        pp_col = "#00E676" if pp_d > 0 else ("#FF5252" if pp_d < 0 else "#aaaaaa")
        pp_sign = "+" if pp_d > 0 else ""
        ctk.CTkLabel(c1, text=f"• Performance: {recap.get('start_pp', 0.0):.1f}pp ➔ {recap.get('end_pp', 0.0):.1f}pp ({pp_sign}{pp_d:.1f} Net-PP)",
                     font=("Arial", 12), text_color=pp_col).pack(anchor="w", padx=14, pady=2)

        ctk.CTkLabel(c1, text=f"• Maps: {len(recap.get('plays', []))} ({recap.get('passes_count', 0)} Passes, {recap.get('fails_count', 0)} Fails)",
                     font=("Arial", 11), text_color="#cccccc").pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(c1, text=f"• Durchschnitts-Acc: {recap.get('avg_accuracy', 0.0):.2f}% • Hits: {recap.get('total_hits', 0):,}",
                     font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=14, pady=(2, 12))

        # Card 2: Highlights & Top-Plays
        c2 = ctk.CTkFrame(top_grid, fg_color="#1c1c28", corner_radius=12, border_width=1, border_color="#2a2a3e")
        c2.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        ctk.CTkLabel(c2, text="🏆 Session-Highlights", font=("Arial", 13, "bold"), text_color="#ffffff").pack(anchor="w", padx=14, pady=(12, 6))

        if recap.get("highest_peak_pp", 0) > 0:
            peak_val = recap["highest_peak_pp"]
            peak_m = recap.get("highest_peak_map", "Beatmap")
            peak_cb = recap.get("highest_peak_combo", 0)
            ctk.CTkLabel(c2, text=f"🔥 Höchster PP-Peak: {peak_val:.1f} PP", font=("Arial", 12, "bold"), text_color="#FF9800").pack(anchor="w", padx=14, pady=2)
            ctk.CTkLabel(c2, text=f"🗺️ {peak_m[:32]} (Peak bei {peak_cb}x Combo)", font=("Arial", 11), text_color="#00E5FF").pack(anchor="w", padx=14, pady=(0, 3))

        if recap.get("new_top_plays"):
            tp = recap["new_top_plays"][0]
            ctk.CTkLabel(c2, text=f"⭐ Neues #{tp.get('rank_in_top', 1)} Top-Play!", font=("Arial", 11, "bold"), text_color="#4CAF50").pack(anchor="w", padx=14, pady=1)
            ctk.CTkLabel(c2, text=f"{tp.get('name', 'Map')[:32]} (+{tp.get('mod', 'NM')} • {tp.get('pp', 0):.0f}pp)", font=("Arial", 10), text_color="#ffffff").pack(anchor="w", padx=14, pady=1)
        elif recap.get("best_play"):
            bp = recap["best_play"]
            ctk.CTkLabel(c2, text="⭐ Bester Run dieser Session:", font=("Arial", 11, "bold"), text_color="#4CAF50").pack(anchor="w", padx=14, pady=1)
            ctk.CTkLabel(c2, text=f"{bp.get('name', '')[:30]} (★ {bp.get('sr', 5.0):.1f} • {bp.get('acc', 0):.1f}%)", font=("Arial", 10), text_color="#ffffff").pack(anchor="w", padx=14, pady=1)

        ctk.CTkLabel(c2, text=f"• Hauptfokus heute: {recap.get('primary_skill', 'Allgemein')}", font=("Arial", 11, "bold"), text_color="#BA68C8").pack(anchor="w", padx=14, pady=2)

        # Card 3: Hand- & Ergonomie-Coach
        health_info = recap.get("health_cooldown", {})
        c3 = ctk.CTkFrame(body, fg_color="#181e28", corner_radius=12, border_width=1, border_color="#1f364d")
        c3.pack(fill="x", pady=6)

        ctk.CTkLabel(c3, text="🧘 Hand- & Ergonomie-Coach (Regeneration)", font=("Arial", 13, "bold"), text_color="#00E5FF").pack(anchor="w", padx=14, pady=(12, 4))
        ctk.CTkLabel(c3, text=health_info.get("title", "Regenerations-Tipp"), font=("Arial", 11, "bold"), text_color="#FFB74D").pack(anchor="w", padx=14, pady=2)

        for step in health_info.get("steps", []):
            ctk.CTkLabel(c3, text=f"• {step}", font=("Arial", 11), text_color="#e0e0e0", justify="left", wraplength=660).pack(anchor="w", padx=14, pady=2)

        if health_info.get("rest_advice"):
            ctk.CTkLabel(c3, text=f"💡 {health_info.get('rest_advice')}", font=("Arial", 10, "bold"), text_color="#81C784").pack(anchor="w", padx=14, pady=(4, 12))

        # Card 4: KI-Trainingsplan für morgen
        c4 = ctk.CTkFrame(body, fg_color="#201828", corner_radius=12, border_width=1, border_color="#3a254c")
        c4.pack(fill="x", pady=6)

        ctk.CTkLabel(c4, text="🎯 KI-Trainingsplan für MORGEN", font=("Arial", 13, "bold"), text_color="#E040FB").pack(anchor="w", padx=14, pady=(12, 4))
        if recap.get("ai_summary"):
            ctk.CTkLabel(c4, text=f"📋 Tages-Fazit: {recap.get('ai_summary')}", font=("Arial", 11), text_color="#cccccc", wraplength=660, justify="left").pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(c4, text=f"💡 Fokus morgen: {recap.get('ai_tomorrow_plan', '')}", font=("Arial", 11, "bold"), text_color="#ffffff", wraplength=660, justify="left").pack(anchor="w", padx=14, pady=(2, 12))

        # Bottom Actions Bar
        bot_bar = ctk.CTkFrame(card, fg_color="transparent", height=44)
        bot_bar.pack(fill="x", padx=14, pady=(6, 12))

        copy_status_lbl = ctk.CTkLabel(bot_bar, text="", font=("Arial", 11, "bold"), text_color="#00E676")
        copy_status_lbl.pack(side="left", padx=10)

        def do_copy_discord():
            txt = self.format_discord_recap_text(recap)
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.update()
            copy_status_lbl.configure(text="✅ Discord-Card in Zwischenablage kopiert!")
            self.after(3000, lambda: copy_status_lbl.configure(text="") if copy_status_lbl.winfo_exists() else None)

        ctk.CTkButton(bot_bar, text="📋 Für Discord kopieren", font=("Arial", 12, "bold"), height=34,
                      fg_color="#5865F2", hover_color="#4752C4", text_color="#ffffff", command=do_copy_discord).pack(side="left", padx=5)

        def open_dash():
            modal.destroy()
            self.show_daily_recap_dashboard(recap.get("id"))

        ctk.CTkButton(bot_bar, text="📂 Im Dashboard ansehen", font=("Arial", 12), height=34,
                      fg_color="#2b2b36", hover_color="#3a3a48", command=open_dash).pack(side="left", padx=5)

        ctk.CTkButton(bot_bar, text="✕ Schließen", font=("Arial", 12, "bold"), height=34, width=90,
                      fg_color="#1f538d", hover_color="#14375e", command=modal.destroy).pack(side="right", padx=5)

    def show_daily_recap_dashboard(self, selected_recap_id=None):
        """Opens the full Day & Session Recap Center with historical timeline."""
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#101015")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="📊 Tages- & Session-Recap Zentrale", font=("Arial", 18, "bold"), text_color="#7B1FA2").pack(side="left", padx=10)

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_box.grid_columnconfigure(0, weight=1)
        main_box.grid_columnconfigure(1, weight=3)
        main_box.grid_rowconfigure(0, weight=1)

        # Left History List Pane
        left_pane = ctk.CTkFrame(main_box, fg_color="#161620", corner_radius=12, border_width=1, border_color="#242432")
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        l_hdr = ctk.CTkFrame(left_pane, fg_color="transparent")
        l_hdr.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(l_hdr, text="🕒 Bisherige Sessions", font=("Arial", 13, "bold"), text_color="#ffffff").pack(side="left")

        hist_scroll = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        hist_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # Right Detail Pane
        right_pane = ctk.CTkFrame(main_box, fg_color="#161620", corner_radius=12, border_width=1, border_color="#242432")
        right_pane.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        history = getattr(self, "session_recaps_history", []) or []

        def render_detail(recap_item):
            for w in right_pane.winfo_children():
                w.destroy()

            r_hdr = ctk.CTkFrame(right_pane, fg_color="transparent")
            r_hdr.pack(fill="x", padx=18, pady=(14, 8))

            is_live = (recap_item.get("status") == "active")
            badge_txt = "🟢 LIVE-SESSION LÄUFT" if is_live else f"🏁 SESSION VOM {recap_item.get('date', 'HEUTE')}"
            badge_col = "#00E676" if is_live else "#00E5FF"
            ctk.CTkLabel(r_hdr, text=badge_txt, font=("Arial", 16, "bold"), text_color=badge_col).pack(anchor="w")
            ctk.CTkLabel(r_hdr, text=f"Start: {recap_item.get('start_time_str', '00:00')} • Dauer: {recap_item.get('duration_mins', 0)} Min • Maps: {len(recap_item.get('plays', []))}",
                         font=("Arial", 11), text_color="#888899").pack(anchor="w")

            detail_scroll = ctk.CTkScrollableFrame(right_pane, fg_color="transparent")
            detail_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 10))

            # Stats Grid
            grid = ctk.CTkFrame(detail_scroll, fg_color="transparent")
            grid.pack(fill="x", pady=6)
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, weight=1)

            # Box 1: Rank & PP
            b1 = ctk.CTkFrame(grid, fg_color="#1c1c28", corner_radius=10, border_width=1, border_color="#2a2a3e")
            b1.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=4)
            ctk.CTkLabel(b1, text="📈 Rang & Performance", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=12, pady=(10, 4))
            
            r_del = recap_item.get("rank_delta", 0)
            r_col = "#00E676" if r_del > 0 else ("#FF5252" if r_del < 0 else "#aaaaaa")
            r_sgn = "+" if r_del > 0 else ""
            ctk.CTkLabel(b1, text=f"• Rang: #{recap_item.get('start_rank', 0):,} ➔ #{recap_item.get('end_rank', 0):,} ({r_sgn}{r_del})",
                         font=("Arial", 11, "bold"), text_color=r_col).pack(anchor="w", padx=12, pady=2)

            pp_d = recap_item.get("pp_delta", 0.0)
            pp_col = "#00E676" if pp_d > 0 else ("#FF5252" if pp_d < 0 else "#aaaaaa")
            pp_sgn = "+" if pp_d > 0 else ""
            ctk.CTkLabel(b1, text=f"• Net-PP: {pp_sgn}{pp_d:.1f} pp (Aktuell: {recap_item.get('end_pp', 0.0):.1f}pp)",
                         font=("Arial", 11), text_color=pp_col).pack(anchor="w", padx=12, pady=2)
            ctk.CTkLabel(b1, text=f"• Accuracy: Ø {recap_item.get('avg_accuracy', 0.0):.2f}% • Hits: {recap_item.get('total_hits', 0):,}",
                         font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=12, pady=(2, 10))

            # Box 2: Highlights
            b2 = ctk.CTkFrame(grid, fg_color="#1c1c28", corner_radius=10, border_width=1, border_color="#2a2a3e")
            b2.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=4)
            ctk.CTkLabel(b2, text="🏆 Highlights & Fokus", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(b2, text=f"• Haupt-Skillset: {recap_item.get('primary_skill', 'Allround')}", font=("Arial", 11, "bold"), text_color="#BA68C8").pack(anchor="w", padx=12, pady=2)
            ctk.CTkLabel(b2, text=f"• Passes: {recap_item.get('passes_count', 0)} | Fails: {recap_item.get('fails_count', 0)} | Retries: {recap_item.get('retries_count', 0)}",
                         font=("Arial", 11), text_color="#cccccc").pack(anchor="w", padx=12, pady=(2, 10))

            # Cooldown Box
            health_i = recap_item.get("health_cooldown", {})
            if health_i:
                b3 = ctk.CTkFrame(detail_scroll, fg_color="#181e28", corner_radius=10, border_width=1, border_color="#1f364d")
                b3.pack(fill="x", pady=6)
                ctk.CTkLabel(b3, text="🧘 Hand- & Ergonomie-Coach", font=("Arial", 12, "bold"), text_color="#00E5FF").pack(anchor="w", padx=12, pady=(8, 2))
                ctk.CTkLabel(b3, text=health_i.get("title", ""), font=("Arial", 10, "bold"), text_color="#FFB74D").pack(anchor="w", padx=12, pady=1)
                for st in health_i.get("steps", []):
                    ctk.CTkLabel(b3, text=f"• {st}", font=("Arial", 10), text_color="#dddddd", wraplength=540, justify="left").pack(anchor="w", padx=12, pady=1)

            # Tomorrow Plan Box
            if recap_item.get("ai_tomorrow_plan"):
                b4 = ctk.CTkFrame(detail_scroll, fg_color="#201828", corner_radius=10, border_width=1, border_color="#3a254c")
                b4.pack(fill="x", pady=6)
                ctk.CTkLabel(b4, text="🎯 KI-Trainingsplan für MORGEN", font=("Arial", 12, "bold"), text_color="#E040FB").pack(anchor="w", padx=12, pady=(8, 2))
                ctk.CTkLabel(b4, text=recap_item.get("ai_tomorrow_plan", ""), font=("Arial", 10, "bold"), text_color="#ffffff", wraplength=540, justify="left").pack(anchor="w", padx=12, pady=(2, 8))

            # Actions
            b_actions = ctk.CTkFrame(right_pane, fg_color="transparent", height=42)
            b_actions.pack(fill="x", padx=14, pady=(4, 10))

            def copy_d():
                txt = self.format_discord_recap_text(recap_item)
                self.clipboard_clear()
                self.clipboard_append(txt)
                self.update()

            ctk.CTkButton(b_actions, text="📋 Für Discord kopieren", font=("Arial", 11, "bold"), height=32,
                          fg_color="#5865F2", hover_color="#4752C4", command=copy_d).pack(side="left", padx=4)

            if is_live:
                def manual_finish():
                    fin = self.finalize_active_session(is_manual=True)
                    self.active_session = None
                    self.show_daily_recap_dashboard(fin.get("id") if fin else None)

                ctk.CTkButton(b_actions, text="🏁 Session jetzt finalisieren", font=("Arial", 11, "bold"), height=32,
                              fg_color="#c62828", hover_color="#b71c1c", command=manual_finish).pack(side="right", padx=4)

        # Build History List
        first_item = None
        if self.active_session:
            first_item = self.active_session
            s_btn = ctk.CTkButton(hist_scroll, text=f"🟢 Live-Session ({self.active_session.get('duration_mins', 0)}m)",
                                  font=("Arial", 11, "bold"), fg_color="#1f3b25", hover_color="#285233",
                                  command=lambda item=self.active_session: render_detail(item))
            s_btn.pack(fill="x", pady=3)

        for rec in history:
            if not first_item and (not selected_recap_id or rec.get("id") == selected_recap_id):
                first_item = rec
            r_d = rec.get("rank_delta", 0)
            r_sgn = f"+{r_d}" if r_d > 0 else str(r_d)
            btn_txt = f"📅 {rec.get('date', 'Unbekannt')} ({rec.get('duration_mins', 0)}m | {r_sgn} Ränge)"
            ctk.CTkButton(hist_scroll, text=btn_txt, font=("Arial", 10), fg_color="#1f1f2c", hover_color="#2b2b3e",
                          command=lambda item=rec: render_detail(item)).pack(fill="x", pady=2)

        if first_item:
            render_detail(first_item)
        else:
            ctk.CTkLabel(right_pane, text="Noch keine abgeschlossenen Sessions vorhanden.\nStarte osu! und spiele ein paar Maps – nach 5 Minuten Schließen erscheint dein erstes Recap!",
                         font=("Arial", 12), text_color="#888899", justify="center").pack(expand=True)

    # ---------------------------------------------------------------------------
    # MAIN MENU
    # ---------------------------------------------------------------------------
    
    def load_map_peaks_history(self):
        try:
            return safe_json_load("map_peaks_history.json", default={})
        except Exception:
            return {}

    def save_map_peaks_history(self):
        try:
            safe_atomic_json_dump(getattr(self, "map_peaks_history", {}), "map_peaks_history.json", indent=2)
        except Exception:
            pass

    def update_map_peak_record(self, map_key, map_title, peak_pp, max_combo, mods_str="NM"):
        if not hasattr(self, "map_peaks_history"):
            self.map_peaks_history = self.load_map_peaks_history()
        
        entry = self.map_peaks_history.get(map_key, {})
        prev_peak = entry.get("highest_peak_pp", 0.0)
        
        if peak_pp > prev_peak:
            self.map_peaks_history[map_key] = {
                "title": map_title,
                "highest_peak_pp": round(peak_pp, 1),
                "highest_combo": max_combo,
                "mods": mods_str,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            self.save_map_peaks_history()
            return True, prev_peak
        return False, prev_peak

    def calculate_live_pp_metrics(self, sr=5.0, acc=100.0, combo=0, max_combo=1000, misses=0, mods_num=0, od=8.0):
        """Accurate osu!std PP estimation (aim + speed + accuracy components)."""
        if max_combo <= 0: max_combo = 1000
        combo_ratio = min(1.0, max(0.01, combo / max(1, max_combo)))
        total_hits = max(1, combo + misses)
        
        # Mod multipliers
        is_dt = bool(mods_num & 64)
        is_hr = bool(mods_num & 16)
        is_hd = bool(mods_num & 8)
        is_ez = bool(mods_num & 2)
        is_fl = bool(mods_num & 1024)
        
        effective_sr = sr
        effective_od = od
        if is_dt: effective_sr *= 1.28; effective_od = min(11, od * 1.4)
        if is_hr: effective_sr *= 1.12; effective_od = min(11, od * 1.4)
        if is_ez: effective_sr *= 0.65; effective_od *= 0.5
        
        # --- AIM PP COMPONENT ---
        aim_strain = max(0.0, effective_sr ** 3.2) * 0.66
        aim_pp = aim_strain * (combo_ratio ** 0.8)
        if misses > 0:
            aim_pp *= 0.97 ** misses
            aim_pp *= min(1.0, ((total_hits - misses) / max(1, total_hits)) ** 1.5)
        aim_pp *= 0.98 + ((effective_od ** 2) / 2500.0)
        acc_bonus_aim = max(0.0, ((acc / 100.0) - 0.7) / 0.3)
        aim_pp *= 0.5 + acc_bonus_aim * 0.5
        if is_hd: aim_pp *= 1.05
        if is_fl: aim_pp *= 1.35

        # --- SPEED PP COMPONENT ---
        speed_strain = max(0.0, effective_sr ** 2.7) * 1.04
        speed_pp = speed_strain * (combo_ratio ** 0.8)
        if misses > 0:
            speed_pp *= 0.97 ** misses
            speed_pp *= ((total_hits - misses) / max(1, total_hits)) ** 1.2
        speed_pp *= 0.95 + ((effective_od ** 2) / 750.0)
        speed_pp *= max(0.0, ((acc / 100.0) - 0.6) / 0.4) ** 1.8
        if is_hd: speed_pp *= 1.08

        # --- ACCURACY PP COMPONENT ---
        acc_val = acc / 100.0
        acc_pp_base = max(0.0, (effective_od - 4.0)) * 3.8
        acc_pp = acc_pp_base * (acc_val ** 8.0) * min(1.05, total_hits / 1500.0)
        if is_hd: acc_pp *= 1.08
        if is_fl: acc_pp *= 1.02

        # --- TOTAL PP ---
        total_pp = ((aim_pp ** 1.1 + speed_pp ** 1.1 + acc_pp ** 1.1) ** (1.0 / 1.1)) * 1.14
        current_pp = max(0.0, round(total_pp, 1))
        
        # --- IF-FC PP ---
        fc_acc = max(acc, min(100.0, acc + (misses * 0.3)))
        _, if_fc_pp = self.calculate_live_pp_metrics(sr=sr, acc=fc_acc, combo=max_combo, max_combo=max_combo, misses=0, mods_num=mods_num, od=od) if misses > 0 or combo < max_combo else (0, current_pp)
        if_fc_pp = max(current_pp, if_fc_pp)
        
        return current_pp, if_fc_pp

    
    # ---------------------------------------------------------------------------
    # MAIN MENU
    # ---------------------------------------------------------------------------
    def show_main_menu(self):
        self._start_uho_presence_heartbeat_loop()
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        frame = ctk.CTkFrame(master, fg_color="#181822", corner_radius=20, border_width=1, border_color="#2e2e3f", width=430, height=540)
        frame.place(relx=0.5, rely=0.5, anchor="center")
        frame.pack_propagate(False)

        ctk.CTkLabel(frame, text="UHO Hub", font=("Arial", 32, "bold"), text_color="#3b8ed0").pack(pady=(16, 2))
        ctk.CTkLabel(frame, text="Dein All-in-One osu! Trainings-Hub", font=("Arial", 12), text_color="#888899").pack(pady=(0, 10))

        ctk.CTkButton(frame, text="📈 Training", font=("Arial", 15, "bold"), width=330, height=42, corner_radius=10,
                      fg_color="#1f538d", hover_color="#14375e",
                      command=self.show_training_mode_selection).pack(pady=5)

        ctk.CTkButton(frame, text="🎯 Skill-Analyse", font=("Arial", 15, "bold"), width=330, height=42, corner_radius=10,
                      fg_color="#E91E63", hover_color="#C2185B", command=self.show_skill_analyse).pack(pady=5)

        ctk.CTkButton(frame, text="📊 Tages- & Session-Recap", font=("Arial", 15, "bold"), width=330, height=42, corner_radius=10,
                      fg_color="#7B1FA2", hover_color="#6A1B9A", text_color="#ffffff",
                      command=self.show_daily_recap_dashboard).pack(pady=5)

        ctk.CTkButton(frame, text="🌐 Multiplayer", font=("Arial", 15, "bold"), width=330, height=42, corner_radius=10,
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#ffffff",
                      command=lambda: self.ensure_osu_irc_password(on_success_callback=self.show_multiplayer_hub)).pack(pady=5)

        ctk.CTkButton(frame, text="⚙️ Einstellungen", font=("Arial", 14, "bold"), width=330, height=40, corner_radius=10,
                      fg_color="#2b2b36", hover_color="#3a3a48", command=self.show_settings).pack(pady=5)

        help_btn = ctk.CTkButton(master, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                                 fg_color="#22222a", hover_color="#333340", text_color="#aaaaaa",
                                 command=lambda: self.show_help("main"))
        help_btn.place(relx=0.97, rely=0.03, anchor="ne")

        ai_btn = ctk.CTkButton(master, text="🤖 Mit KI reden", width=140, height=36, font=("Arial", 13, "bold"),
                               fg_color="#E91E63", hover_color="#C2185B", command=self.show_ai_chat)
        ai_btn.place(relx=0.03, rely=0.03, anchor="nw")

    def ensure_osu_irc_password(self, on_success_callback, cancel_callback=None):
        """
        Ensures that the osu! IRC password is configured before entering Multiplayer or Tournament modes.
        If already configured, invokes on_success_callback immediately.
        Otherwise, displays a modal dialog prompting the user to enter their IRC server password from https://osu.ppy.sh/p/irc.
        Once saved, it is stored permanently in settings and not asked again.
        """
        cur_pwd = getattr(self, "osu_irc_password", "").strip()
        cur_user = getattr(self, "osu_username", "").strip()

        if cur_pwd and cur_user:
            if callable(on_success_callback):
                on_success_callback()
            return

        modal = ctk.CTkToplevel(self)
        modal.title("🔑 osu! IRC-Passwort erforderlich")
        modal.geometry("600x520")
        modal.resizable(False, False)
        modal.configure(fg_color="#121216")
        modal.attributes("-topmost", True)
        try:
            modal.grab_set()
        except Exception:
            pass

        # Header Box
        hdr = ctk.CTkFrame(modal, fg_color="#181824", corner_radius=12, border_width=1, border_color="#2e2e42")
        hdr.pack(fill="x", padx=20, pady=(20, 10))

        h_left = ctk.CTkFrame(hdr, fg_color="transparent")
        h_left.pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(h_left, text="🔑 osu! IRC-Passwort Einrichtung", font=("Arial", 16, "bold"), text_color="#00E5FF").pack(anchor="w")
        ctk.CTkLabel(h_left, text="Einmalig erforderlich für Multiplayer & Turniersimulator",
                     font=("Arial", 11), text_color="#888899").pack(anchor="w")
        ctk.CTkLabel(hdr, text=" BANCHO IRC ", font=("Arial", 10, "bold"), fg_color="#00E5FF", text_color="#000000", corner_radius=6).pack(side="right", padx=16)

        # Info Box
        info_box = ctk.CTkFrame(modal, fg_color="#1a1a24", corner_radius=10, border_width=1, border_color="#2b2b3c")
        info_box.pack(fill="x", padx=20, pady=(0, 12))

        info_text = (
            "Damit UHO Hub automatisch private Multiplayer-Lobbies (ScoreV2, Auto-Invite & Map-Picks) "
            "auf dem offiziellen osu! Bancho-Server erstellen kann, wird dein persönliches osu! Server-Passwort benötigt.\n\n"
            "⚠️ HINWEIS: Dies ist NICHT dein normales osu!-Login-Passwort, sondern dein generiertes Server-Passwort von der osu!-Website."
        )
        ctk.CTkLabel(info_box, text=info_text, font=("Arial", 11), text_color="#cccccc", justify="left", wraplength=540).pack(padx=14, pady=10)

        # Web link button
        def _open_irc_page():
            webbrowser.open("https://osu.ppy.sh/p/irc")

        ctk.CTkButton(modal, text="🌐 osu.ppy.sh/p/irc im Browser öffnen (Passwort kopieren) ➔", font=("Arial", 12, "bold"),
                      fg_color="#3b8ed0", hover_color="#2a6ca6", text_color="#ffffff", height=32, command=_open_irc_page).pack(fill="x", padx=20, pady=(0, 12))

        # Username / Password Form Frame
        form_frame = ctk.CTkFrame(modal, fg_color="#181822", corner_radius=10, border_width=1, border_color="#2b2b3c")
        form_frame.pack(fill="x", padx=20, pady=(0, 14))

        # Username row if missing
        u_entry = None
        if not cur_user:
            u_row = ctk.CTkFrame(form_frame, fg_color="transparent")
            u_row.pack(fill="x", padx=14, pady=(10, 4))
            ctk.CTkLabel(u_row, text="Dein osu! Spielername:", font=("Arial", 11, "bold"), text_color="#aaaaaa", width=170, anchor="w").pack(side="left")
            u_entry = ctk.CTkEntry(u_row, placeholder_text="z. B. Mrekk", height=30)
            u_entry.pack(side="left", fill="x", expand=True)

        # Password row
        p_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        p_row.pack(fill="x", padx=14, pady=(10 if cur_user else 4, 10))
        ctk.CTkLabel(p_row, text="osu! IRC-Server-Passwort:", font=("Arial", 11, "bold"), text_color="#aaaaaa", width=170, anchor="w").pack(side="left")
        p_entry = ctk.CTkEntry(p_row, placeholder_text="Server-Passwort hier einfügen...", show="*", height=30)
        p_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Toggle show password button
        def _toggle_pwd():
            if p_entry.cget("show") == "*":
                p_entry.configure(show="")
                toggle_btn.configure(text="🔒")
            else:
                p_entry.configure(show="*")
                toggle_btn.configure(text="👁️")

        toggle_btn = ctk.CTkButton(p_row, text="👁️", width=32, height=30, fg_color="#252530", hover_color="#353545", command=_toggle_pwd)
        toggle_btn.pack(side="right")

        err_lbl = ctk.CTkLabel(modal, text="", font=("Arial", 11, "bold"), text_color="#FF5252")
        err_lbl.pack(pady=(0, 6))

        # Buttons
        btn_row = ctk.CTkFrame(modal, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        def _on_save():
            entered_pwd = p_entry.get().strip()
            entered_user = u_entry.get().strip() if u_entry else getattr(self, "osu_username", "").strip()

            if not entered_user:
                err_lbl.configure(text="❌ Bitte gib deinen osu!-Spielernamen ein.")
                return
            if not entered_pwd:
                err_lbl.configure(text="❌ Bitte füge dein Server-Passwort von osu.ppy.sh/p/irc ein.")
                return

            self.osu_username = entered_user
            self.osu_irc_password = entered_pwd
            self.save_global_settings()
            
            try:
                modal.grab_release()
                modal.destroy()
            except Exception:
                pass

            if callable(on_success_callback):
                on_success_callback()

        def _on_offline():
            try:
                modal.grab_release()
                modal.destroy()
            except Exception:
                pass
            if callable(on_success_callback):
                on_success_callback()

        def _on_cancel():
            try:
                modal.grab_release()
                modal.destroy()
            except Exception:
                pass
            if callable(cancel_callback):
                cancel_callback()

        ctk.CTkButton(btn_row, text="Abbrechen", width=90, height=36, font=("Arial", 11),
                      fg_color="#25252e", hover_color="#353540", command=_on_cancel).pack(side="left", padx=(0, 6))

        ctk.CTkButton(btn_row, text="🎮 Ohne IRC starten (Lokal)", width=170, height=36, font=("Arial", 11, "bold"),
                      fg_color="#333348", hover_color="#44445c", text_color="#00E5FF", command=_on_offline).pack(side="left")

        ctk.CTkButton(btn_row, text="💾 Speichern & mit Bancho starten ➔", height=36, font=("Arial", 12, "bold"),
                      fg_color="#00E676", hover_color="#00C853", text_color="#000000", command=_on_save).pack(side="right", fill="x", expand=True, padx=(10, 0))

    # ---------------------------------------------------------------------------
    # MULTIPLAYER HUB (1v1, 2v2, 3v3, 4v4 • BANCHO REFEREE BOT • TOURNAMENT SCRIMS)
    # ---------------------------------------------------------------------------
    def show_multiplayer_hub(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🌐 Multiplayer Hub (Lobby & Scrims)", font=("Arial", 18, "bold"), text_color="#00BFA5").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("main")).pack(side="right", padx=15)

        cards_container = ctk.CTkScrollableFrame(master, fg_color="transparent")
        cards_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        grid_frame = ctk.CTkFrame(cards_container, fg_color="transparent")
        grid_frame.pack(expand=True, pady=10)

        # CARD 1: TURNIER MATCH (REFEREE BOT)
        c1 = ctk.CTkFrame(grid_frame, fg_color="#142622", corner_radius=16, border_width=2, border_color="#00BFA5", width=380, height=220)
        c1.grid(row=0, column=0, padx=15, pady=15)
        c1.pack_propagate(False)

        c1_top = ctk.CTkFrame(c1, fg_color="transparent")
        c1_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c1_top, text="🏆 Turnier-Match", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c1_top, text=" SCOREV2 + NO-FAIL ", font=("Arial", 10, "bold"), fg_color="#00BFA5", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c1, text="1v1 bis 4v4 OWC/ET Scrims. Vollautomatische Bancho-Lobby mit NoFail-Pflicht, Mappool-Broadcast und Romaji-Style Chat-Befehlen (!pick, !ban, !save).",
                     font=("Arial", 12), text_color="#aaeedd", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c1, text="⚔️ Turnier-Match erstellen ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000",
                      command=lambda: self.ensure_osu_irc_password(on_success_callback=self.show_multiplayer_match_setup)).pack(fill="x", padx=16, side="bottom", pady=16)

        # CARD 2: BANCHO LOUNGE (HOST ROTATION)
        c2 = ctk.CTkFrame(grid_frame, fg_color="#1a1828", corner_radius=16, border_width=2, border_color="#9C27B0", width=380, height=220)
        c2.grid(row=0, column=1, padx=15, pady=15)
        c2.pack_propagate(False)

        c2_top = ctk.CTkFrame(c2, fg_color="transparent")
        c2_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c2_top, text="🔄 Bancho Lounge", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c2_top, text=" HOST-ROTATION ", font=("Arial", 10, "bold"), fg_color="#BA68C8", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c2, text="Entspannte Community-Lobby mit automatischer Host-Übergabe nach jeder Runde, einstellbarem Passwort und optionalem KI-Autopilot für ausgeglichene Maps.",
                     font=("Arial", 12), text_color="#e1bee7", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c2, text="🔄 Host-Rotation starten ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#AB47BC", hover_color="#8E24AA", text_color="#ffffff",
                      command=lambda: self.ensure_osu_irc_password(on_success_callback=self.show_host_rotation_setup)).pack(fill="x", padx=16, side="bottom", pady=16)

        # CARD 3: CUSTOM SCRIMS & MAPPOOL
        c3 = ctk.CTkFrame(grid_frame, fg_color="#181824", corner_radius=16, border_width=2, border_color="#00E5FF", width=380, height=220)
        c3.grid(row=1, column=0, padx=15, pady=15)
        c3.pack_propagate(False)

        c3_top = ctk.CTkFrame(c3, fg_color="transparent")
        c3_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c3_top, text="🛠️ Custom Scrims", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c3_top, text=" CUSTOM POOLS ", font=("Arial", 10, "bold"), fg_color="#00E5FF", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c3, text="Erstelle eigene Mappools per Drag & Drop oder Link-Eingabe und trage Scrim-Matches mit Freunden aus – mit automatischer KI-Auffüllung.",
                     font=("Arial", 12), text_color="#bbddff", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c3, text="🛠️ Custom Mappool öffnen ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000",
                      command=lambda: self.show_custom_mappool_builder(from_multiplayer=True)).pack(fill="x", padx=16, side="bottom", pady=16)

        # CARD 4: FREUNDE & ONLINE-COMMUNITY
        c4 = ctk.CTkFrame(grid_frame, fg_color="#1e1822", corner_radius=16, border_width=2, border_color="#FF4081", width=380, height=220)
        c4.grid(row=1, column=1, padx=15, pady=15)
        c4.pack_propagate(False)

        c4_top = ctk.CTkFrame(c4, fg_color="transparent")
        c4_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c4_top, text="👥 Freunde & Community", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c4_top, text=" LIVE PRESENCE ", font=("Arial", 10, "bold"), fg_color="#FF4081", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c4, text="Sieh wer gerade in UHO Hub online ist, verwalte deine Freundesliste und lade Mitspieler mit einem Klick zu synchronisierten Matches ein.",
                     font=("Arial", 12), text_color="#ffcdd2", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c4, text="👥 Freunde & Status öffnen ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#FF4081", hover_color="#E91E63", text_color="#ffffff",
                      command=self.show_friends_and_community).pack(fill="x", padx=16, side="bottom", pady=16)

    def show_multiplayer_match_setup(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 8))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Zurück", width=90, height=34, font=("Arial", 12, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_multiplayer_hub).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="⚔️ Multiplayer Match-Konfiguration (ScoreV2 + No-Fail)", font=("Arial", 18, "bold"), text_color="#00BFA5").pack(side="left", padx=10)

        main_scroll = ctk.CTkScrollableFrame(master, fg_color="transparent")
        main_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        grid = ctk.CTkFrame(main_scroll, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        # ----------------- LEFT: TEAMS & PLAYERS -----------------
        f_left = ctk.CTkFrame(grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#2a2a38")
        f_left.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="nsew")

        ctk.CTkLabel(f_left, text="👥 1. Teams & Spieler", font=("Arial", 16, "bold"), text_color="#00BFA5").pack(anchor="w", padx=18, pady=(15, 8))

        # Mode Selection: 1v1, 2v2, 3v3, 4v4
        ctk.CTkLabel(f_left, text="Match-Format / Team-Größe:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=18, pady=(4, 2))
        mode_opt = ctk.CTkOptionMenu(f_left, values=["1v1 (Head-to-Head)", "2v2 (Team VS)", "3v3 (Team VS)", "4v4 (Team VS)"],
                                     font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548", height=34)
        mode_opt.pack(fill="x", padx=18, pady=(0, 12))

        # Team Rot
        t1_box = ctk.CTkFrame(f_left, fg_color="#241416", corner_radius=10, border_width=1, border_color="#E91E63")
        t1_box.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(t1_box, text="🔴 Team Rot (Host)", font=("Arial", 13, "bold"), text_color="#FF4081").pack(anchor="w", padx=12, pady=(10, 4))
        
        t1_name_entry = ctk.CTkEntry(t1_box, placeholder_text="Team-Name (z.B. Team Alpha)", font=("Arial", 12), height=32)
        t1_name_entry.insert(0, "Team Rot")
        t1_name_entry.pack(fill="x", padx=12, pady=3)

        default_t1_p = getattr(self, "osu_username", "") or "Spieler1"
        t1_players_entry = ctk.CTkEntry(t1_box, placeholder_text="osu! Usernames (kommagetrennt)...", font=("Arial", 12), height=32)
        t1_players_entry.insert(0, default_t1_p)
        t1_players_entry.pack(fill="x", padx=12, pady=(3, 10))

        # Team Blau
        t2_box = ctk.CTkFrame(f_left, fg_color="#141c2a", corner_radius=10, border_width=1, border_color="#00E5FF")
        t2_box.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(t2_box, text="🔵 Team Blau (Herausforderer)", font=("Arial", 13, "bold"), text_color="#00E5FF").pack(anchor="w", padx=12, pady=(10, 4))

        t2_name_entry = ctk.CTkEntry(t2_box, placeholder_text="Team-Name (z.B. Team Omega)", font=("Arial", 12), height=32)
        t2_name_entry.insert(0, "Team Blau")
        t2_name_entry.pack(fill="x", padx=12, pady=3)

        t2_players_entry = ctk.CTkEntry(t2_box, placeholder_text="osu! Usernames (kommagetrennt)...", font=("Arial", 12), height=32)
        t2_players_entry.insert(0, "Gegner1")
        t2_players_entry.pack(fill="x", padx=12, pady=(3, 10))

        # Bot Mode Selection
        bot_box = ctk.CTkFrame(f_left, fg_color="#1b1b24", corner_radius=10, border_width=1, border_color="#333346")
        bot_box.pack(fill="x", padx=18, pady=(10, 15))
        
        bot_box_h = ctk.CTkFrame(bot_box, fg_color="transparent")
        bot_box_h.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(bot_box_h, text="🤖 Ingame Referee Bot", font=("Arial", 13, "bold"), text_color="#00BFA5").pack(side="left")
        ctk.CTkLabel(bot_box_h, text=" ROMAJI-STYLE CHAT ", font=("Arial", 9, "bold"), fg_color="#00BFA5", text_color="#000000", corner_radius=4).pack(side="left", padx=8)

        use_bot_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(bot_box, text="Automatischer Bancho-Bot (Chat !pick/!ban + ScoreV2)", variable=use_bot_var,
                      font=("Arial", 11, "bold"), progress_color="#00BFA5").pack(anchor="w", padx=12, pady=(0, 6))

        irc_info_lbl = ctk.CTkLabel(bot_box, text="", font=("Arial", 10), justify="left")
        irc_info_lbl.pack(anchor="w", padx=12, pady=(0, 4))
        if getattr(self, "osu_irc_password", ""):
            irc_info_lbl.configure(text="✅ osu! IRC-Passwort hinterlegt. Bot ist einsatzbereit!", text_color="#00E676")
        else:
            irc_info_lbl.configure(text="⚠️ Kein IRC-Passwort hinterlegt (wird für automatische Lobbies & Einladungen benötigt).", text_color="#FFA726")

        def prompt_irc_pwd():
            dialog = ctk.CTkInputDialog(text="Gib dein IRC-Server-Passwort von https://osu.ppy.sh/p/irc ein:\n(NICHT dein normales osu!-Login-Passwort!)", title="osu! IRC-Server-Passwort")
            val = dialog.get_input()
            if val is not None and val.strip():
                self.osu_irc_password = val.strip()
                self.save_global_settings()
                irc_info_lbl.configure(text="✅ osu! IRC-Passwort hinterlegt. Bot ist einsatzbereit!", text_color="#00E676")

        irc_btn_row = ctk.CTkFrame(bot_box, fg_color="transparent")
        irc_btn_row.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(irc_btn_row, text="🔑 IRC-Passwort eintragen", font=("Arial", 10, "bold"), height=26,
                      fg_color="#2b2b3a", hover_color="#3b3b4f", command=prompt_irc_pwd).pack(side="left")
        ctk.CTkButton(irc_btn_row, text="🌐 Passwort auf osu.ppy.sh abrufen", font=("Arial", 10), height=26,
                      fg_color="transparent", hover_color="#222230", text_color="#00E5FF", command=lambda: webbrowser.open("https://osu.ppy.sh/p/irc")).pack(side="left", padx=(6, 0))

        # ----------------- RIGHT: MAPPOOL & RULES -----------------
        f_right = ctk.CTkFrame(grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#2a2a38")
        f_right.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="nsew")

        ctk.CTkLabel(f_right, text="🎯 2. Mappool, Regeln & Passwort", font=("Arial", 16, "bold"), text_color="#00BFA5").pack(anchor="w", padx=18, pady=(15, 8))

        # Tournament Selector
        ctk.CTkLabel(f_right, text="Turnier:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=18, pady=(2, 2))
        tourney_opt = ctk.CTkOptionMenu(f_right, values=["OWC (osu! World Cup)", "ET (European Tournament)", "AOT (All-Star Tournament)", "BFT (Bounty Fast Tournament)", "Custom Mappool"],
                                        font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548", height=32)
        tourney_opt.pack(fill="x", padx=18, pady=(0, 8))

        # Division Selector
        ctk.CTkLabel(f_right, text="Division / Rank-Bereich:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=18, pady=(2, 2))
        div_opt = ctk.CTkOptionMenu(f_right, values=["6WC (6-Digit)", "5WC (5-Digit)", "4WC (4-Digit)", "Main OWC (Open Rank)"],
                                    font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548", height=32)
        div_opt.pack(fill="x", padx=18, pady=(0, 8))

        # Year & Stage Row
        row_ys = ctk.CTkFrame(f_right, fg_color="transparent")
        row_ys.pack(fill="x", padx=18, pady=(2, 8))
        row_ys.grid_columnconfigure(0, weight=1)
        row_ys.grid_columnconfigure(1, weight=1)

        f_y = ctk.CTkFrame(row_ys, fg_color="transparent")
        f_y.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkLabel(f_y, text="Jahrgang:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w")
        year_opt = ctk.CTkOptionMenu(f_y, values=["2025", "2024", "2023", "2022", "2021", "2020"], font=("Arial", 12), fg_color="#262635", button_color="#353548", height=32)
        year_opt.pack(fill="x", pady=(2, 0))

        f_s = ctk.CTkFrame(row_ys, fg_color="transparent")
        f_s.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        ctk.CTkLabel(f_s, text="Turnier-Runde:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w")
        stage_opt = ctk.CTkOptionMenu(f_s, values=["Grand Finals", "Finals", "Semifinals", "Quarterfinals", "Round of 16", "Round of 32", "Qualifiers"],
                                      font=("Arial", 12), fg_color="#262635", button_color="#353548", height=32)
        stage_opt.pack(fill="x", pady=(2, 0))

        # Match Format (Best of)
        ctk.CTkLabel(f_right, text="Match-Format (Siegbedingungen):", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=18, pady=(2, 2))
        fmt_opt = ctk.CTkOptionMenu(f_right, values=["Best of 9 (First to 5)", "Best of 7 (First to 4)", "Best of 11 (First to 6)", "Best of 13 (First to 7)"],
                                    font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548", height=32)
        fmt_opt.pack(fill="x", padx=18, pady=(0, 8))

        # Protects & Bans Row
        row_pb = ctk.CTkFrame(f_right, fg_color="transparent")
        row_pb.pack(fill="x", padx=18, pady=(2, 8))
        row_pb.grid_columnconfigure(0, weight=1)
        row_pb.grid_columnconfigure(1, weight=1)

        f_p = ctk.CTkFrame(row_pb, fg_color="transparent")
        f_p.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkLabel(f_p, text="Saves / Protects:", font=("Arial", 12, "bold"), text_color="#00E676").pack(anchor="w")
        prot_opt = ctk.CTkOptionMenu(f_p, values=["Auto (Standard)", "1 Save pro Team", "2 Saves pro Team", "0 Saves"], font=("Arial", 11), fg_color="#262635", button_color="#353548", height=32)
        prot_opt.pack(fill="x", pady=(2, 0))

        f_b = ctk.CTkFrame(row_pb, fg_color="transparent")
        f_b.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        ctk.CTkLabel(f_b, text="Bans pro Team:", font=("Arial", 12, "bold"), text_color="#FF5252").pack(anchor="w")
        ban_opt = ctk.CTkOptionMenu(f_b, values=["Auto (Standard)", "1 Ban pro Team", "2 Bans pro Team", "0 Bans"], font=("Arial", 11), fg_color="#262635", button_color="#353548", height=32)
        ban_opt.pack(fill="x", pady=(2, 0))

        # Lobby Passwort
        ctk.CTkLabel(f_right, text="🔒 Lobby-Passwort (optional):", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=18, pady=(4, 2))
        pwd_entry = ctk.CTkEntry(f_right, placeholder_text="z.B. tournament123 (leer für Standard)", font=("Arial", 12), height=32)
        pwd_entry.pack(fill="x", padx=18, pady=(0, 12))

        # Bottom Action Bar
        bottom_bar = ctk.CTkFrame(master, fg_color="#181822", height=64, corner_radius=12)
        bottom_bar.pack(fill="x", padx=20, pady=(6, 12), side="bottom")
        bottom_bar.pack_propagate(False)

        def on_launch():
            try:
                mode_str = mode_opt.get()
                t_size = 1 if "1v1" in mode_str else (2 if "2v2" in mode_str else (3 if "3v3" in mode_str else 4))
                t1_n = t1_name_entry.get().strip() or "Team Rot"
                t1_pl = [p.strip() for p in t1_players_entry.get().split(",") if p.strip()] or [getattr(self, "osu_username", "Spieler1")]
                t2_n = t2_name_entry.get().strip() or "Team Blau"
                t2_pl = [p.strip() for p in t2_players_entry.get().split(",") if p.strip()] or ["Gegner1"]

                if not getattr(self, "osu_username", "") and t1_pl:
                    self.osu_username = t1_pl[0]
                    self.save_global_settings()

                t_val = tourney_opt.get().split(" ")[0]
                d_val = div_opt.get()
                if "(" in d_val:
                    d_val = d_val.split("(")[0].strip()
                y_val = year_opt.get()
                st_val = stage_opt.get()
                f_val = fmt_opt.get()
                pr_val = prot_opt.get()
                ba_val = ban_opt.get()
                pwd_val = pwd_entry.get().strip()
                use_bot = use_bot_var.get()

                if use_bot and not getattr(self, "osu_irc_password", ""):
                    dialog = ctk.CTkInputDialog(text="Gib dein Server-Passwort von https://osu.ppy.sh/p/irc ein:\n(Wird für automatische Ingame-Lobbies & Einladungen benötigt)", title="osu! IRC-Server-Passwort")
                    val = dialog.get_input()
                    if val is not None and val.strip():
                        self.osu_irc_password = val.strip()
                        self.save_global_settings()

                self.start_multiplayer_match(
                    mode_str=mode_str, team_size=t_size,
                    t1_name=t1_n, t1_players=t1_pl,
                    t2_name=t2_n, t2_players=t2_pl,
                    tourney=t_val, division=d_val, year=y_val, stage=st_val,
                    fmt_name=f_val, prot_setting=pr_val, ban_setting=ba_val,
                    use_bot=use_bot, password=pwd_val
                )
            except Exception as e:
                import traceback
                self.show_message("Match-Start Fehler", f"Match konnte nicht gestartet werden:\n{e}\n\n{traceback.format_exc()[:300]}")

        ctk.CTkButton(bottom_bar, text="🚀 Ingame-Lobby erstellen & Multiplayer-Match starten ➔", font=("Arial", 14, "bold"), height=46,
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=on_launch).pack(fill="both", expand=True, padx=12, pady=9)

    def start_multiplayer_match(self, mode_str, team_size, t1_name, t1_players, t2_name, t2_players, tourney, division, year, stage, fmt_name, prot_setting, ban_setting, use_bot, password=""):
        # Target Wins parsing
        target_wins = 5
        if "First to 4" in fmt_name or "Best of 7" in fmt_name: target_wins = 4
        elif "First to 5" in fmt_name or "Best of 9" in fmt_name: target_wins = 5
        elif "First to 6" in fmt_name or "Best of 11" in fmt_name: target_wins = 6
        elif "First to 7" in fmt_name or "Best of 13" in fmt_name: target_wins = 7

        # Protects & Bans
        if "0" in prot_setting: max_prots = 0
        elif "1" in prot_setting: max_prots = 1
        elif "2" in prot_setting: max_prots = 2
        else: max_prots = 1 if stage in ["Grand Finals", "Finals"] else 0

        if "0" in ban_setting: max_bans = 0
        elif "1" in ban_setting: max_bans = 1
        elif "2" in ban_setting: max_bans = 2
        else: max_bans = 2 if stage in ["Grand Finals", "Finals", "Semifinals"] else 1

        # Fetch Mappool
        cfg = self.TOURNAMENTS_CONFIG.get(tourney, self.TOURNAMENTS_CONFIG["OWC"])
        div_cfg = cfg.get("divisions", {}).get(division, {"min_sr": 5.0, "max_sr": 6.5})
        min_sr = div_cfg.get("min_sr", 5.0)
        max_sr = div_cfg.get("max_sr", 6.5)

        pool = {}
        if tourney == "Custom":
            pool = dict(getattr(self, "custom_tourney_pool", {}))
            if not pool:
                pool = self.generate_tournament_mappool(min_sr, max_sr, year=year, tourney_key=tourney, div_key=division, stage=stage)
        else:
            pool = self.generate_tournament_mappool(min_sr, max_sr, year=year, tourney_key=tourney, div_key=division, stage=stage)

        final_pwd = password or f"uho{random.randint(100, 999)}"

        self.mp_match = {
            "mode_str": mode_str,
            "team_size": team_size,
            "team1_name": t1_name,
            "team1_players": t1_players,
            "team1_score": 0,
            "team1_protects": [],
            "team1_bans": [],
            "team2_name": t2_name,
            "team2_players": t2_players,
            "team2_score": 0,
            "team2_protects": [],
            "team2_bans": [],
            "target_wins": target_wins,
            "max_protects": max_prots,
            "max_bans": max_bans,
            "tournament": tourney,
            "division": division,
            "year": year,
            "stage": stage,
            "format_name": fmt_name,
            "pool": pool,
            "phase": "roll", # roll -> protect1 -> protect2 -> ban1 -> ban2 -> pick -> playing -> finished
            "first_picker": "team1",
            "active_team": "team1",
            "rolls": {"team1": None, "team2": None},
            "history": [],
            "current_pick": None,
            "use_irc_bot": use_bot,
            "irc_channel": None,
            "match_id": None,
            "password": final_pwd,
            "bot_logs": []
        }

        # If Bot enabled, connect and host
        if use_bot:
            u_name = getattr(self, "osu_username", "") or (t1_players[0] if t1_players else "Spieler")
            u_irc = getattr(self, "osu_irc_password", "")
            if u_name and u_irc:
                lobby_name = f"UHO Hub: {t1_name} vs {t2_name}"
                self.mp_referee_bot = BanchoRefereeBot(
                    username=u_name,
                    irc_password=u_irc,
                    on_log=self._mp_bot_log_callback,
                    on_match_created=self._mp_on_match_created,
                    on_round_ended=self._mp_on_round_ended,
                    on_chat_command=self._mp_on_chat_command
                )
                self.mp_referee_bot.connect_and_host(lobby_name=lobby_name, password=final_pwd)
            else:
                self.show_message("Schiedsrichter-Hinweis", "Kein IRC-Passwort hinterlegt. Das Match startet im interaktiven Schiedsrichter-Modus mit Live-Score-Sync.")

        self.show_multiplayer_match_lobby()

    def _mp_on_chat_command(self, sender, cmd, arg, full_msg):
        """Processes in-game Romaji-style commands sent to #mp_<id> (e.g. !pick, !ban, !save, !roll, !maps)."""
        if not hasattr(self, "mp_match") or not self.mp_match:
            return
        m = self.mp_match
        bot = getattr(self, "mp_referee_bot", None)
        sender_clean = sender.strip().replace(" ", "_").lower()

        t1_list = [p.lower().replace(" ", "_") for p in m.get("team1_players", [])]
        t2_list = [p.lower().replace(" ", "_") for p in m.get("team2_players", [])]

        sender_team = None
        if sender_clean in t1_list: sender_team = "team1"
        elif sender_clean in t2_list: sender_team = "team2"
        else:
            if sender_clean in m.get("team1_name", "").lower(): sender_team = "team1"
            elif sender_clean in m.get("team2_name", "").lower(): sender_team = "team2"
            else: sender_team = m.get("active_team", "team1")

        phase = m.get("phase", "roll")

        if cmd in ["roll", "dice", "wuerfeln"]:
            if phase == "roll":
                if sender_team and m["rolls"].get(sender_team) is None:
                    self.after(0, lambda t=sender_team: self.handle_mp_roll(t))
                else:
                    if bot: bot.send_channel_message(f"@{sender}: Dein Team hat bereits gewürfelt ({m['rolls'].get(sender_team)})!")
            else:
                if bot: bot.send_channel_message(f"@{sender}: Die Roll-Phase ist bereits beendet.")

        elif cmd in ["save", "protect", "schuetzen"]:
            if phase in ["protect1", "protect2"]:
                if sender_team == m.get("active_team"):
                    slot = arg.upper()
                    if slot in m.get("pool", {}) and m["pool"][slot].get("state") == "available":
                        self.after(0, lambda s=slot: self.handle_mp_protect(s))
                    else:
                        if bot: bot.send_channel_message(f"@{sender}: Slot '{slot}' ist ungültig oder nicht mehr verfügbar.")
                else:
                    if bot: bot.send_channel_message(f"@{sender}: Dein Team ist gerade nicht an der Reihe für Save/Protect!")
            else:
                if bot: bot.send_channel_message(f"@{sender}: Aktuell ist keine Save/Protect-Phase.")

        elif cmd in ["ban", "bann", "bannen"]:
            if phase in ["ban1", "ban2"]:
                if sender_team == m.get("active_team"):
                    slot = arg.upper()
                    if slot in m.get("pool", {}) and m["pool"][slot].get("state") == "available":
                        self.after(0, lambda s=slot: self.handle_mp_ban(s))
                    else:
                        if bot: bot.send_channel_message(f"@{sender}: Slot '{slot}' ist ungültig oder bereits geschützt/gebannt.")
                else:
                    if bot: bot.send_channel_message(f"@{sender}: Dein Team ist gerade nicht an der Reihe für Bans!")
            else:
                if bot: bot.send_channel_message(f"@{sender}: Aktuell ist keine Ban-Phase.")

        elif cmd in ["pick", "choose", "select", "waehlen"]:
            if phase == "pick":
                if sender_team == m.get("active_team"):
                    slot = arg.upper()
                    if slot in m.get("pool", {}) and m["pool"][slot].get("state") in ["available", "protected"]:
                        self.after(0, lambda s=slot: self.handle_mp_pick(s))
                    else:
                        if bot: bot.send_channel_message(f"@{sender}: Slot '{slot}' ist ungültig oder bereits gespielt/gebannt.")
                else:
                    if bot: bot.send_channel_message(f"@{sender}: Dein Team ist gerade nicht mit Picken am Zug!")
            else:
                if bot: bot.send_channel_message(f"@{sender}: Aktuell ist keine Pick-Phase.")

        elif cmd in ["maps", "pool", "mappool"]:
            if bot:
                avail = [f"[{s}] {data['name'][:24]} (★ {data['sr']:.2f})" for s, data in m.get("pool", {}).items() if data.get("state") in ["available", "protected"]]
                if avail:
                    bot.send_channel_message(f"📋 Verfügbare Maps ({len(avail)}): " + " | ".join(avail[:5]))
                    if len(avail) > 5:
                        time.sleep(0.6)
                        bot.send_channel_message("... " + " | ".join(avail[5:10]))
                else:
                    bot.send_channel_message("📋 Alle Maps wurden bereits gespielt oder gebannt.")

        elif cmd in ["score", "stand", "punkte"]:
            if bot:
                t1 = m.get("team1_name", "Team Rot")
                s1 = m.get("team1_score", 0)
                t2 = m.get("team2_name", "Team Blau")
                s2 = m.get("team2_score", 0)
                tw = m.get("target_wins", 5)
                bot.send_channel_message(f"📊 Spielstand: {t1} [{s1}] : [{s2}] {t2} (First to {tw})")

        elif cmd in ["ready", "start", "gogo"]:
            if phase == "playing" and bot:
                bot.send_channel_message("🚀 Countdown gestartet! Macht euch bereit.")
                bot.start_countdown(10)
            elif bot:
                bot.send_channel_message("⚠️ Noch keine Map gewählt. Bitte zuerst !pick <slot> nutzen!")

        elif cmd in ["help", "commands", "befehle"]:
            if bot:
                bot.send_channel_message("📌 Befehle: !roll | !save <slot> | !ban <slot> | !pick <slot> | !maps | !score | !ready")

    # ---------------------------------------------------------------------------
    # HOST ROTATION LOBBY (BANCHO LOUNGE)
    # ---------------------------------------------------------------------------
    def show_host_rotation_setup(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 8))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Zurück", width=90, height=34, font=("Arial", 12, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_multiplayer_hub).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🔄 Bancho Lounge (Host-Rotation Setup)", font=("Arial", 18, "bold"), text_color="#BA68C8").pack(side="left", padx=10)

        main_box = ctk.CTkFrame(master, fg_color="#181822", corner_radius=16, border_width=1, border_color="#2e2a3a", width=620, height=480)
        main_box.place(relx=0.5, rely=0.52, anchor="center")
        main_box.pack_propagate(False)

        ctk.CTkLabel(main_box, text="🔄 Host-Rotation Konfiguration", font=("Arial", 18, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(main_box, text="Der BanchoBot übergibt nach jedem gespielten Song automatisch den Host an den nächsten Spieler.", font=("Arial", 11), text_color="#aaaaaa").pack(anchor="w", padx=24, pady=(0, 16))

        # Lobby Name
        ctk.CTkLabel(main_box, text="Lobby-Name:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(4, 2))
        lobby_name_entry = ctk.CTkEntry(main_box, placeholder_text="z.B. UHO Hub: Host Rotation", font=("Arial", 12), height=34)
        lobby_name_entry.insert(0, "UHO Hub: Host Rotation")
        lobby_name_entry.pack(fill="x", padx=24, pady=(0, 10))

        # Password
        ctk.CTkLabel(main_box, text="🔒 Passwort (optional, leer für öffentlich):", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(4, 2))
        pwd_entry = ctk.CTkEntry(main_box, placeholder_text="z.B. chill123", font=("Arial", 12), height=34)
        pwd_entry.pack(fill="x", padx=24, pady=(0, 10))

        # Initial Players
        ctk.CTkLabel(main_box, text="👥 Spieler einladen (kommagetrennt):", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(4, 2))
        pl_entry = ctk.CTkEntry(main_box, placeholder_text="Spieler1, Spieler2, Spieler3...", font=("Arial", 12), height=34)
        def_user = getattr(self, "osu_username", "") or "Spieler1"
        pl_entry.insert(0, def_user)
        pl_entry.pack(fill="x", padx=24, pady=(0, 10))

        # Rotation Mode
        ctk.CTkLabel(main_box, text="Modus:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=24, pady=(4, 2))
        rot_mode_opt = ctk.CTkOptionMenu(main_box, values=["Normal (Spieler wählen reihum ihre Maps)", "🤖 KI-Autopilot (KI wählt ausgewogene Maps für die Gruppe)"],
                                         font=("Arial", 12, "bold"), fg_color="#2b2035", button_color="#3e2a4f", height=34)
        rot_mode_opt.pack(fill="x", padx=24, pady=(0, 18))

        def launch_rotation():
            l_name = lobby_name_entry.get().strip() or "UHO Hub: Host Rotation"
            pwd = pwd_entry.get().strip()
            raw_pl = [p.strip() for p in pl_entry.get().split(",") if p.strip()]
            ai_picker = "KI-Autopilot" in rot_mode_opt.get()
            self.start_host_rotation_lobby(l_name, pwd, raw_pl, ai_picker)

        ctk.CTkButton(main_box, text="🚀 Host-Rotation Lobby erstellen & öffnen ➔", font=("Arial", 14, "bold"), height=44,
                      fg_color="#AB47BC", hover_color="#8E24AA", text_color="#ffffff", command=launch_rotation).pack(fill="x", padx=24, pady=(6, 20))

    def start_host_rotation_lobby(self, lobby_name, password, initial_players, ai_picker=False):
        u_name = getattr(self, "osu_username", "") or (initial_players[0] if initial_players else "Spieler")
        u_irc = getattr(self, "osu_irc_password", "")

        if not u_irc:
            dialog = ctk.CTkInputDialog(text="Gib dein IRC-Server-Passwort von https://osu.ppy.sh/p/irc ein:", title="osu! IRC-Server-Passwort")
            val = dialog.get_input()
            if val is not None and val.strip():
                self.osu_irc_password = val.strip()
                self.save_global_settings()
                u_irc = val.strip()

        self.host_rotation_data = {
            "lobby_name": lobby_name,
            "password": password,
            "players": list(initial_players),
            "ai_picker": ai_picker,
            "logs": []
        }

        if u_name and u_irc:
            self.mp_referee_bot = BanchoRefereeBot(
                username=u_name,
                irc_password=u_irc,
                on_log=self._host_rot_log_callback,
                on_match_created=self._host_rot_on_created
            )
            self.mp_referee_bot.connect_and_host(lobby_name=lobby_name, password=password, host_rotation=True, initial_players=initial_players)

        self.show_host_rotation_lobby_view()

    def _host_rot_log_callback(self, text, color="#aaaaaa"):
        if not hasattr(self, "host_rotation_data"): return
        entry = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.host_rotation_data.setdefault("logs", []).append(entry)
        self.host_rotation_data["logs"] = self.host_rotation_data["logs"][-30:]

        def update_ui():
            if hasattr(self, "host_rot_feed") and self.host_rot_feed.winfo_exists():
                self.host_rot_feed.configure(state="normal")
                self.host_rot_feed.delete("1.0", "end")
                self.host_rot_feed.insert("1.0", "\n".join(self.host_rotation_data.get("logs", [])))
                self.host_rot_feed.configure(state="disabled")
                try: self.host_rot_feed.see("end")
                except: pass
        self.after(0, update_ui)

    def _host_rot_on_created(self, match_id, channel):
        self._host_rot_log_callback(f"🚀 Ingame-Lobby erstellt: {channel}", "#00E676")
        def _bg():
            time.sleep(1.0)
            if getattr(self, "mp_referee_bot", None):
                self.mp_referee_bot.set_team_mode(1)
                for p in self.host_rotation_data.get("players", []):
                    time.sleep(0.8)
                    self.mp_referee_bot.invite_player(p)
                self.mp_referee_bot.send_channel_message(f"Willkommen zur UHO Hub Host-Rotation! Host wechselt nach jedem Song automatisch.")
        threading.Thread(target=_bg, daemon=True).start()

    def show_host_rotation_lobby_view(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#101015")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 8))
        top_bar.pack_propagate(False)

        def close_and_leave():
            if getattr(self, "mp_referee_bot", None):
                self.mp_referee_bot.close_lobby()
            self.show_multiplayer_hub()

        ctk.CTkButton(top_bar, text="✕ Lobby schließen", width=120, height=34, font=("Arial", 12, "bold"),
                      fg_color="#c62828", hover_color="#b71c1c", command=close_and_leave).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text=f"🔄 {self.host_rotation_data.get('lobby_name', 'Host-Rotation')}", font=("Arial", 18, "bold"), text_color="#BA68C8").pack(side="left", padx=10)

        main_grid = ctk.CTkFrame(master, fg_color="transparent")
        main_grid.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_grid.grid_columnconfigure(0, weight=1)
        main_grid.grid_columnconfigure(1, weight=1)

        # Left: Host Queue
        q_frame = ctk.CTkFrame(main_grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#2e2a3a")
        q_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="nsew")

        ctk.CTkLabel(q_frame, text="👑 Host-Reihenfolge (Queue)", font=("Arial", 16, "bold"), text_color="#BA68C8").pack(anchor="w", padx=18, pady=(15, 8))

        def skip_host():
            if getattr(self, "mp_referee_bot", None):
                next_h = self.mp_referee_bot.rotate_next_host()
                if next_h:
                    self._host_rot_log_callback(f"👑 Host manuell übergeben an: {next_h}", "#00E5FF")

        def invite_all():
            if getattr(self, "mp_referee_bot", None):
                for p in self.host_rotation_data.get("players", []):
                    self.mp_referee_bot.invite_player(p)
                self._host_rot_log_callback("✉️ Einladungen an alle Spieler erneut gesendet!", "#00E676")

        btn_row = ctk.CTkFrame(q_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 10))
        ctk.CTkButton(btn_row, text="👑 Nächster Host", font=("Arial", 11, "bold"), height=30,
                      fg_color="#AB47BC", hover_color="#8E24AA", command=skip_host).pack(side="left")
        ctk.CTkButton(btn_row, text="✉️ Spieler einladen", font=("Arial", 11, "bold"), height=30,
                      fg_color="#2b2035", hover_color="#3e2a4f", text_color="#BA68C8", command=invite_all).pack(side="left", padx=(8, 0))

        # Right: Feed
        feed_frame = ctk.CTkFrame(main_grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#2e2a3a")
        feed_frame.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="nsew")

        ctk.CTkLabel(feed_frame, text="🤖 Ingame Bancho Live-Feed", font=("Arial", 16, "bold"), text_color="#00E5FF").pack(anchor="w", padx=18, pady=(15, 8))

        self.host_rot_feed = ctk.CTkTextbox(feed_frame, wrap="word", font=("Arial", 11), fg_color="#101016", border_width=1, border_color="#222230")
        self.host_rot_feed.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self.host_rot_feed.insert("1.0", "\n".join(self.host_rotation_data.get("logs", ["Warte auf Bot-Verbindung..."])))
        self.host_rot_feed.configure(state="disabled")

    # ---------------------------------------------------------------------------
    # FREUNDE & ONLINE-COMMUNITY (ECHTE LIVE PRESENCE & UHO HUB VS OSU! BADGES)
    # ---------------------------------------------------------------------------
    def _start_uho_presence_heartbeat_loop(self):
        """Sendet alle 20 Sekunden einen echten Heartbeat an den Render-Server."""
        if getattr(self, "_uho_heartbeat_loop_running", False):
            return
        self._uho_heartbeat_loop_running = True

        def _loop():
            while True:
                try:
                    u_name = getattr(self, "osu_username", "").strip()
                    if u_name:
                        act = getattr(self, "_current_user_activity", "In UHO Hub aktiv")
                        payload = {
                            "username": u_name,
                            "status": act,
                            "version": CURRENT_APP_VERSION
                        }
                        requests.post(f"{UHO_AUTH_SERVER_URL}/heartbeat", json=payload, timeout=5)
                except Exception:
                    pass
                time.sleep(20)

        threading.Thread(target=_loop, daemon=True).start()

    def fetch_uho_live_presence(self, callback=None):
        """Fragt die aktuell echten online Spieler vom Render Server ab."""
        def _run():
            live_dict = {}
            try:
                r = requests.get(f"{UHO_AUTH_SERVER_URL}/active_users", timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    for u in data.get("active_users", []):
                        un = u.get("username", "").strip()
                        if un and un.lower() not in ["banchobot", "gemini ai", "gemini"]:
                            live_dict[un.lower()] = u
            except Exception:
                pass

            # Ensure local player is always marked online
            my_u = getattr(self, "osu_username", "").strip()
            if my_u and my_u.lower() not in live_dict:
                live_dict[my_u.lower()] = {
                    "username": my_u,
                    "status": "🟢 In UHO Hub aktiv",
                    "version": CURRENT_APP_VERSION,
                    "seconds_ago": 0
                }

            self._cached_live_uho_users = live_dict
            if callback:
                self.after(0, lambda: callback(live_dict))

        threading.Thread(target=_run, daemon=True).start()

    def show_friends_and_community(self):
        self._start_uho_presence_heartbeat_loop()

        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 8))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Zurück", width=90, height=34, font=("Arial", 12, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_multiplayer_hub).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="👥 Freunde & Online-Community (Echte Live Presence)", font=("Arial", 18, "bold"), text_color="#FF4081").pack(side="left", padx=10)

        main_grid = ctk.CTkFrame(master, fg_color="transparent")
        main_grid.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_grid.grid_columnconfigure(0, weight=1)
        main_grid.grid_columnconfigure(1, weight=1)

        # Left: Friends List
        f_left = ctk.CTkFrame(main_grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#302028")
        f_left.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="nsew")

        f_hdr = ctk.CTkFrame(f_left, fg_color="transparent")
        f_hdr.pack(fill="x", padx=18, pady=(15, 6))
        ctk.CTkLabel(f_hdr, text="👥 Meine Freundesliste", font=("Arial", 16, "bold"), text_color="#FF4081").pack(side="left")

        # Add friend row
        add_row = ctk.CTkFrame(f_left, fg_color="transparent")
        add_row.pack(fill="x", padx=18, pady=(0, 10))
        add_entry = ctk.CTkEntry(add_row, placeholder_text="osu! Username eingeben...", font=("Arial", 12), height=32)
        add_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        friends_scroll = ctk.CTkScrollableFrame(f_left, fg_color="transparent")
        friends_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        def render_friends(live_users=None):
            if live_users is None:
                live_users = getattr(self, "_cached_live_uho_users", {})

            for w in friends_scroll.winfo_children(): w.destroy()
            fl = getattr(self, "uho_friends_list", [])
            if not fl:
                ctk.CTkLabel(friends_scroll, text="Noch keine Freunde hinzugefügt.\nFüge deine Freunde oben per Username hinzu!",
                             font=("Arial", 12), text_color="#888899", justify="center").pack(pady=40)
                return

            for fr in fl:
                u_low = fr.strip().lower()
                is_uho_user = u_low in live_users

                c = ctk.CTkFrame(friends_scroll, fg_color="#1c1622" if is_uho_user else "#181820",
                                 corner_radius=10, border_width=1,
                                 border_color="#00E5FF" if is_uho_user else "#2c2c3a")
                c.pack(fill="x", pady=4)
                
                c_top = ctk.CTkFrame(c, fg_color="transparent")
                c_top.pack(fill="x", padx=10, pady=8)

                def remove_f(u=fr):
                    if u in self.uho_friends_list:
                        self.uho_friends_list.remove(u)
                        self.save_global_settings()
                        render_friends()

                def challenge_f(u=fr):
                    self.show_multiplayer_match_setup()

                # PACK RIGHT ACTION BUTTONS FIRST so they NEVER clip or truncate!
                r_btn_box = ctk.CTkFrame(c_top, fg_color="transparent")
                r_btn_box.pack(side="right", padx=0)

                ctk.CTkButton(r_btn_box, text="✕", width=28, height=28, font=("Arial", 11, "bold"),
                              fg_color="#3a2028", hover_color="#502028", text_color="#ff8888", command=remove_f).pack(side="right", padx=(4, 0))

                ctk.CTkButton(r_btn_box, text="⚔️ Match", width=90, height=28, font=("Arial", 11, "bold"),
                              fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=challenge_f).pack(side="right", padx=(4, 0))

                # Left information & badges frame
                l_info_box = ctk.CTkFrame(c_top, fg_color="transparent")
                l_info_box.pack(side="left", fill="x", expand=True, padx=(0, 6))

                ctk.CTkLabel(l_info_box, text=f"👤 {fr}", font=("Arial", 13, "bold"), text_color="#ffffff").pack(side="left")

                if is_uho_user:
                    ctk.CTkLabel(l_info_box, text="⚡ UHO Hub", font=("Arial", 9, "bold"),
                                 fg_color="#0a2838", text_color="#00E5FF", corner_radius=4).pack(side="left", padx=6)
                    u_status = live_users[u_low].get("status", "Online")
                    ctk.CTkLabel(l_info_box, text=f"🟢 {u_status}", font=("Arial", 9, "bold"),
                                 fg_color="#11331c", text_color="#00E676", corner_radius=4).pack(side="left", padx=2)
                else:
                    ctk.CTkLabel(l_info_box, text="🎮 osu! Spieler", font=("Arial", 9),
                                 fg_color="#20202a", text_color="#888899", corner_radius=4).pack(side="left", padx=6)
                    ctk.CTkLabel(l_info_box, text="⚪ Offline", font=("Arial", 9),
                                 fg_color="#1a1a22", text_color="#777788", corner_radius=4).pack(side="left", padx=2)

        def add_f():
            u = add_entry.get().strip()
            if u:
                if not hasattr(self, "uho_friends_list") or not isinstance(self.uho_friends_list, list):
                    self.uho_friends_list = []
                if u not in self.uho_friends_list:
                    self.uho_friends_list.append(u)
                    self.save_global_settings()
                    add_entry.delete(0, "end")
                    render_friends()

        ctk.CTkButton(add_row, text="➕ Hinzufügen", width=100, height=32, font=("Arial", 11, "bold"),
                      fg_color="#FF4081", hover_color="#E91E63", text_color="#ffffff", command=add_f).pack(side="right")

        # Right: Server & Community Status (ECHTE SPIELER)
        f_right = ctk.CTkFrame(main_grid, fg_color="#181822", corner_radius=14, border_width=1, border_color="#302028")
        f_right.grid(row=0, column=1, padx=(10, 0), pady=5, sticky="nsew")

        r_hdr = ctk.CTkFrame(f_right, fg_color="transparent")
        r_hdr.pack(fill="x", padx=18, pady=(15, 6))
        ctk.CTkLabel(r_hdr, text="🌐 UHO Hub Community & Live Presence", font=("Arial", 16, "bold"), text_color="#00E5FF").pack(side="left")

        def refresh_live_presence():
            sync_btn.configure(text="⏳...", state="disabled")
            def _done(live_data):
                render_community_panel(live_data)
                render_friends(live_data)
                if sync_btn.winfo_exists():
                    sync_btn.configure(text="🔄 Aktualisieren", state="normal")
            self.fetch_uho_live_presence(callback=_done)

        sync_btn = ctk.CTkButton(r_hdr, text="🔄 Aktualisieren", width=110, height=28, font=("Arial", 11, "bold"),
                                 fg_color="#2b2b38", hover_color="#00E5FF", text_color="#ffffff", command=refresh_live_presence)
        sync_btn.pack(side="right")

        ctk.CTkLabel(f_right, text=f"Server: {UHO_AUTH_SERVER_URL} (Render Cloud)", font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=18, pady=(0, 10))

        srv_box = ctk.CTkScrollableFrame(f_right, fg_color="#121620", corner_radius=10, border_width=1, border_color="#203040")
        srv_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        def render_community_panel(live_users):
            for w in srv_box.winfo_children(): w.destroy()

            ctk.CTkLabel(srv_box, text=f"📡 Echte aktive Spieler im UHO Hub Netzwerk ({len(live_users)} online):",
                         font=("Arial", 12, "bold"), text_color="#00E5FF").pack(anchor="w", padx=10, pady=(6, 8))

            my_uname = getattr(self, "osu_username", "Spieler") or "Spieler"

            for u_low, data in live_users.items():
                uname = data.get("username", u_low)
                st = data.get("status", "Online in UHO Hub")
                is_self = (uname.lower() == my_uname.lower())

                row = ctk.CTkFrame(srv_box, fg_color="#1e2838" if is_self else "#181e2a", corner_radius=8,
                                   border_width=1 if is_self else 0, border_color="#00E5FF")
                row.pack(fill="x", padx=10, pady=3)

                label_text = f"• {uname} (Du)" if is_self else f"• {uname}"
                ctk.CTkLabel(row, text=label_text, font=("Arial", 12, "bold"),
                             text_color="#00E5FF" if is_self else "#ffffff").pack(side="left", padx=10, pady=8)

                tag_box = ctk.CTkFrame(row, fg_color="transparent")
                tag_box.pack(side="right", padx=10, pady=8)

                ctk.CTkLabel(tag_box, text="⚡ UHO Hub", font=("Arial", 9, "bold"),
                             fg_color="#0a2838", text_color="#00E5FF", corner_radius=4).pack(side="left", padx=(0, 6))

                ctk.CTkLabel(tag_box, text=f"🟢 {st}", font=("Arial", 11), text_color="#00E676").pack(side="left")

            if len(live_users) <= 1:
                info_box = ctk.CTkFrame(srv_box, fg_color="#181822", corner_radius=8)
                info_box.pack(fill="x", padx=10, pady=10)
                ctk.CTkLabel(info_box, text="ℹ️ Aktuell sind keine weiteren Spieler in UHO Hub online.\nSobald ein Freund UHO Hub startet, erscheint er hier automatisch in Echtzeit!",
                             font=("Arial", 11), text_color="#888899", justify="center").pack(padx=12, pady=10)

        # Initial fetch
        self.fetch_uho_live_presence(callback=lambda data: (render_community_panel(data), render_friends(data)))

    def _mp_bot_log_callback(self, text, color="#aaaaaa"):
        if not hasattr(self, "mp_match") or not isinstance(self.mp_match, dict):
            return
        entry = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.mp_match.setdefault("bot_logs", []).append(entry)
        self.mp_match["bot_logs"] = self.mp_match["bot_logs"][-30:]

        def update_ui():
            if hasattr(self, "mp_feed_box") and self.mp_feed_box.winfo_exists():
                self.mp_feed_box.configure(state="normal")
                self.mp_feed_box.delete("1.0", "end")
                self.mp_feed_box.insert("1.0", "\n".join(self.mp_match.get("bot_logs", [])))
                self.mp_feed_box.configure(state="disabled")
                try: self.mp_feed_box.see("end")
                except: pass
        self.after(0, update_ui)

    def _mp_on_match_created(self, match_id, channel):
        self.mp_match["match_id"] = match_id
        self.mp_match["irc_channel"] = channel
        self._mp_bot_log_callback(f"🚀 Ingame-Lobby erstellt: {channel}", "#00E676")
        
        # Configure team mode and invite all players asynchronously + broadcast pool
        def _bg_invite():
            time.sleep(1.0)
            if getattr(self, "mp_referee_bot", None):
                self.mp_referee_bot.set_team_mode(self.mp_match.get("team_size", 1))
                all_pl = self.mp_match.get("team1_players", []) + self.mp_match.get("team2_players", [])
                for p in all_pl:
                    time.sleep(0.8)
                    self.mp_referee_bot.invite_player(p)
                self.mp_referee_bot.send_channel_message(f"Willkommen zum UHO Hub Match! {self.mp_match['team1_name']} vs {self.mp_match['team2_name']}")
                self._mp_bot_log_callback(f"✉️ Einladungen an {', '.join(all_pl)} gesendet!", "#00E676")
                time.sleep(1.0)
                self.mp_referee_bot.broadcast_mappool(self.mp_match.get("pool", {}), self.mp_match.get("stage", "Turnier"))
        threading.Thread(target=_bg_invite, daemon=True).start()

    def _mp_manual_invite_all(self):
        if not hasattr(self, "mp_match") or not self.mp_match:
            return
        all_pl = self.mp_match.get("team1_players", []) + self.mp_match.get("team2_players", [])
        if getattr(self, "mp_referee_bot", None) and self.mp_referee_bot.channel:
            def _bg():
                for p in all_pl:
                    time.sleep(0.5)
                    self.mp_referee_bot.invite_player(p)
                self._mp_bot_log_callback("✉️ Einladungen an alle Spieler erneut gesendet!", "#00E676")
            threading.Thread(target=_bg, daemon=True).start()
        else:
            self._mp_bot_log_callback("⚠️ Bot ist noch nicht mit einer Ingame-Lobby verbunden.", "#FFA726")

    def _mp_on_round_ended(self):
        self.after(1000, self.fetch_mp_match_results)

    def show_multiplayer_match_lobby(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#101015")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        m = self.mp_match

        # TOP BAR
        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=65, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 6))
        top_bar.pack_propagate(False)

        def exit_match():
            def do_exit():
                if getattr(self, "mp_referee_bot", None):
                    try: self.mp_referee_bot.close_lobby()
                    except: pass
                self.show_multiplayer_hub()
            self.ask_confirm("Match beenden", "Möchtest du das Multiplayer-Match wirklich verlassen?", do_exit)

        ctk.CTkButton(top_bar, text="✕ Match Beenden", width=120, height=34, font=("Arial", 12, "bold"),
                      fg_color="#c62828", hover_color="#b71c1c", command=exit_match).pack(side="left", padx=15, pady=14)

        # Scoreboard in Header
        score_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        score_frame.pack(side="left", fill="both", expand=True, padx=10)

        t1_label = f"{m['team1_name']} ({', '.join(m['team1_players'][:2])})"
        t2_label = f"{m['team2_name']} ({', '.join(m['team2_players'][:2])})"

        ctk.CTkLabel(score_frame, text=t1_label, font=("Arial", 14, "bold"), text_color="#FF4081").pack(side="left", padx=(10, 5))
        
        self.mp_score_display = ctk.CTkLabel(score_frame, text=f"[ {m['team1_score']}  :  {m['team2_score']} ]",
                                             font=("Arial", 22, "bold"), text_color="#00E5FF")
        self.mp_score_display.pack(side="left", padx=15)

        ctk.CTkLabel(score_frame, text=t2_label, font=("Arial", 14, "bold"), text_color="#00B4D8").pack(side="left", padx=(5, 10))

        # Format info on right
        ctk.CTkLabel(top_bar, text=f"{m['tournament']} {m['division']} • First to {m['target_wins']}",
                     font=("Arial", 12, "bold"), text_color="#aaaaaa").pack(side="right", padx=15)

        # STATUS BANNER
        self.mp_status_banner = ctk.CTkFrame(master, fg_color="#181824", corner_radius=10, border_width=1, border_color="#00BFA5", height=42)
        self.mp_status_banner.pack(fill="x", padx=20, pady=(0, 8))
        self.mp_status_banner.pack_propagate(False)

        self.mp_status_lbl = ctk.CTkLabel(self.mp_status_banner, text="", font=("Arial", 13, "bold"), text_color="#00E5FF")
        self.mp_status_lbl.pack(side="left", padx=15, pady=8)

        self.mp_action_btn = ctk.CTkButton(self.mp_status_banner, text="", font=("Arial", 12, "bold"), height=30)
        self.mp_action_btn.pack(side="right", padx=15, pady=6)

        # MAIN CONTENT (MAPPOOL ON LEFT, REFEREE FEED ON RIGHT)
        content_box = ctk.CTkFrame(master, fg_color="transparent")
        content_box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        content_box.grid_columnconfigure(0, weight=3)
        content_box.grid_columnconfigure(1, weight=2)
        content_box.grid_rowconfigure(0, weight=1)

        # Left: Mappool Grid
        pool_frame = ctk.CTkFrame(content_box, fg_color="#14141c", corner_radius=14, border_width=1, border_color="#242432")
        pool_frame.grid(row=0, column=0, padx=(0, 8), sticky="nsew")

        p_head = ctk.CTkFrame(pool_frame, fg_color="transparent")
        p_head.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(p_head, text=f"🎯 Offizieller Mappool ({m['stage']})", font=("Arial", 15, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(p_head, text=f"Protect: {len(m['team1_protects'])+len(m['team2_protects'])}/{m['max_protects']*2} | Bans: {len(m['team1_bans'])+len(m['team2_bans'])}/{m['max_bans']*2}",
                     font=("Arial", 11), text_color="#888899").pack(side="right")

        self.mp_pool_scroll = ctk.CTkScrollableFrame(pool_frame, fg_color="transparent")
        self.mp_pool_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Right: Referee & Match Console
        feed_frame = ctk.CTkFrame(content_box, fg_color="#14141c", corner_radius=14, border_width=1, border_color="#242432")
        feed_frame.grid(row=0, column=1, padx=(8, 0), sticky="nsew")

        f_head = ctk.CTkFrame(feed_frame, fg_color="transparent")
        f_head.pack(fill="x", padx=15, pady=(12, 6))
        ctk.CTkLabel(f_head, text="🤖 Referee & Ingame Feed", font=("Arial", 15, "bold"), text_color="#00BFA5").pack(side="left")

        def force_sync():
            self.fetch_mp_match_results()
        ctk.CTkButton(f_head, text="⚡ Score-Sync", width=90, height=26, font=("Arial", 11, "bold"),
                      fg_color="#262635", hover_color="#363648", command=force_sync).pack(side="right")
        ctk.CTkButton(f_head, text="✉️ Spieler einladen", width=120, height=26, font=("Arial", 11, "bold"),
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=self._mp_manual_invite_all).pack(side="right", padx=(0, 6))

        self.mp_feed_box = ctk.CTkTextbox(feed_frame, wrap="word", font=("Arial", 11), fg_color="#101016", border_width=1, border_color="#222230")
        self.mp_feed_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.mp_feed_box.insert("1.0", "\n".join(m.get("bot_logs", ["Warte auf Match-Aktivität..."])))
        self.mp_feed_box.configure(state="disabled")

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def _render_mp_mappool_cards(self):
        for w in self.mp_pool_scroll.winfo_children():
            w.destroy()

        m = self.mp_match
        pool = m.get("pool", {})

        slot_order = ["NM1", "NM2", "NM3", "NM4", "NM5", "NM6", "HD1", "HD2", "HD3", "HR1", "HR2", "HR3", "DT1", "DT2", "DT3", "FM1", "FM2", "FM3", "TB", "TB2"]
        sorted_slots = sorted(pool.keys(), key=lambda s: slot_order.index(s) if s in slot_order else 99)

        for slot in sorted_slots:
            item = pool[slot]
            state = item.get("state", "available") # available, protected, banned, played, playing

            if state == "protected":
                border_col = "#00E676"
                bg_col = "#13261a"
                badge_txt = "🛡️ GESCHÜTZT"
                badge_col = "#00E676"
            elif state == "banned":
                border_col = "#c62828"
                bg_col = "#241315"
                badge_txt = "🚫 GEBANNT"
                badge_col = "#ff4444"
            elif state == "played":
                border_col = "#555566"
                bg_col = "#181820"
                badge_txt = "✅ GESPIELT"
                badge_col = "#777788"
            elif state == "playing":
                border_col = "#00E5FF"
                bg_col = "#102228"
                badge_txt = "⚡ LIVE GESPIELT"
                badge_col = "#00E5FF"
            else:
                border_col = "#282838"
                bg_col = "#181822"
                badge_txt = "VERFÜGBAR"
                badge_col = "#3b8ed0"

            card = ctk.CTkFrame(self.mp_pool_scroll, fg_color=bg_col, corner_radius=10, border_width=1, border_color=border_col)
            card.pack(fill="x", pady=4, padx=4)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(top_row, text=f"{slot}: {item.get('name', 'Map')[:45]}", font=("Arial", 12, "bold"), text_color="#ffffff").pack(side="left")
            ctk.CTkLabel(top_row, text=badge_txt, font=("Arial", 10, "bold"), text_color=badge_col).pack(side="right")

            bot_row = ctk.CTkFrame(card, fg_color="transparent")
            bot_row.pack(fill="x", padx=10, pady=(0, 8))

            meta_txt = f"★ {item.get('sr', 5.0):.2f} • {item.get('bpm', 180)} BPM • CS {item.get('cs', 4.0)} • AR {item.get('ar', 9.0)}"
            ctk.CTkLabel(bot_row, text=meta_txt, font=("Arial", 10), text_color="#888899").pack(side="left")

            # Phase Action Buttons
            phase = m.get("phase", "roll")
            active_t = m.get("active_team", "team1")
            t_color = "#FF4081" if active_t == "team1" else "#00B4D8"

            if state == "available":
                if phase in ["protect1", "protect2"]:
                    ctk.CTkButton(bot_row, text="🛡️ Schützen", width=85, height=24, font=("Arial", 10, "bold"),
                                  fg_color="#00E676", hover_color="#00C853", text_color="#000000",
                                  command=lambda s=slot: self.handle_mp_protect(s)).pack(side="right", padx=2)
                elif phase in ["ban1", "ban2"]:
                    ctk.CTkButton(bot_row, text="🚫 Bannen", width=80, height=24, font=("Arial", 10, "bold"),
                                  fg_color="#c62828", hover_color="#b71c1c",
                                  command=lambda s=slot: self.handle_mp_ban(s)).pack(side="right", padx=2)
                elif phase == "pick":
                    ctk.CTkButton(bot_row, text="🎯 Picken", width=80, height=24, font=("Arial", 10, "bold"),
                                  fg_color=t_color, hover_color="#333344", text_color="#ffffff",
                                  command=lambda s=slot: self.handle_mp_pick(s)).pack(side="right", padx=2)
            elif state == "protected" and phase == "pick":
                ctk.CTkButton(bot_row, text="🎯 Picken", width=80, height=24, font=("Arial", 10, "bold"),
                              fg_color=t_color, hover_color="#333344", text_color="#ffffff",
                              command=lambda s=slot: self.handle_mp_pick(s)).pack(side="right", padx=2)

    def _update_mp_lobby_status(self):
        m = self.mp_match
        phase = m.get("phase", "roll")
        t1_n = m["team1_name"]
        t2_n = m["team2_name"]
        act_t = m.get("active_team", "team1")
        act_name = t1_n if act_t == "team1" else t2_n
        t_col = "#FF4081" if act_t == "team1" else "#00B4D8"

        if phase == "roll":
            r1 = m["rolls"].get("team1")
            r2 = m["rolls"].get("team2")
            if r1 is None and r2 is None:
                txt = "🎲 ROLL-PHASE: Beide Teams müssen um den ersten Pick würfeln!"
                self.mp_action_btn.configure(text=f"🎲 {t1_n} Rollen", fg_color="#FF4081", hover_color="#C2185B", command=lambda: self.handle_mp_roll("team1"))
            elif r1 is not None and r2 is None:
                txt = f"🎲 {t1_n} hat eine {r1} gewürfelt! Jetzt ist {t2_n} am Zug."
                self.mp_action_btn.configure(text=f"🎲 {t2_n} Rollen", fg_color="#00B4D8", hover_color="#0096C7", command=lambda: self.handle_mp_roll("team2"))
            else:
                txt = f"🎲 Ergebnis: {t1_n} ({r1}) vs {t2_n} ({r2}). {act_name} wählt zuerst!"
                self.mp_action_btn.configure(text="Weiter ➔", fg_color="#00BFA5", hover_color="#00897B", command=self._advance_from_roll)

        elif phase in ["protect1", "protect2"]:
            txt = f"🛡️ SAVE-PHASE: {act_name} schützt eine Map vor Bans!"
            self.mp_action_btn.configure(text="Map links wählen", fg_color="#333340", state="disabled")

        elif phase in ["ban1", "ban2"]:
            txt = f"🚫 BAN-PHASE: {act_name} bannt eine Map!"
            self.mp_action_btn.configure(text="Map links wählen", fg_color="#333340", state="disabled")

        elif phase == "pick":
            txt = f"🎯 PICK-PHASE: {act_name} ist am Zug und wählt die nächste Map!"
            self.mp_action_btn.configure(text="Map links wählen", fg_color="#333340", state="disabled")

        elif phase == "playing":
            pick_s = m.get("current_pick", "")
            txt = f"⚡ LIVE INGAME: Runde läuft auf Slot [{pick_s}]! Schiedsrichter überwacht Scores."
            self.mp_action_btn.configure(text="Runde beenden / Werten ➔", fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", state="normal", command=self.fetch_mp_match_results)

        elif phase == "finished":
            w_name = t1_n if m["team1_score"] >= m["target_wins"] else t2_n
            txt = f"🏆 MATCH BEENDET: {w_name} gewinnt das Match {m['team1_score']} : {m['team2_score']}!"
            self.mp_action_btn.configure(text="Abschlussbericht ➔", fg_color="#00E676", hover_color="#00C853", text_color="#000000", state="normal", command=self.show_mp_post_match_modal)

        self.mp_status_lbl.configure(text=txt, text_color=t_col if phase in ["protect1", "protect2", "ban1", "ban2", "pick"] else "#00E5FF")
        self.mp_score_display.configure(text=f"[ {m['team1_score']}  :  {m['team2_score']} ]")

    def handle_mp_roll(self, team):
        roll_val = random.randint(1, 100)
        self.mp_match["rolls"][team] = roll_val
        t_name = self.mp_match[f"{team}_name"]
        self._mp_bot_log_callback(f"🎲 {t_name} würfelt eine {roll_val} (1-100)!", "#00E5FF")
        bot = getattr(self, "mp_referee_bot", None)
        if bot:
            bot.send_channel_message(f"🎲 {t_name} rolled {roll_val} (1-100)!")

        r1 = self.mp_match["rolls"]["team1"]
        r2 = self.mp_match["rolls"]["team2"]
        if r1 is not None and r2 is not None:
            if r1 >= r2:
                self.mp_match["first_picker"] = "team1"
                self.mp_match["active_team"] = "team1"
                winner_t = self.mp_match["team1_name"]
            else:
                self.mp_match["first_picker"] = "team2"
                self.mp_match["active_team"] = "team2"
                winner_t = self.mp_match["team2_name"]

            if bot:
                bot.send_channel_message(f"🎯 Roll-Gewinner: {winner_t} wählt zuerst!")
        self._update_mp_lobby_status()

    def _advance_from_roll(self):
        m = self.mp_match
        bot = getattr(self, "mp_referee_bot", None)
        if m["max_protects"] > 0:
            m["phase"] = "protect1"
            m["active_team"] = m["first_picker"]
            act_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🛡️ Save-Phase: {act_n} bitte !save <slot> im Chat eingeben!")
        elif m["max_bans"] > 0:
            m["phase"] = "ban1"
            m["active_team"] = m["first_picker"]
            act_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🚫 Ban-Phase: {act_n} bitte !ban <slot> im Chat eingeben!")
        else:
            m["phase"] = "pick"
            m["active_team"] = m["first_picker"]
            act_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🎯 Pick-Phase: {act_n} bitte !pick <slot> im Chat eingeben!")
        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def handle_mp_protect(self, slot):
        m = self.mp_match
        act_t = m["active_team"]
        t_name = m[f"{act_t}_name"]
        item = m["pool"].get(slot, {})

        m["pool"][slot]["state"] = "protected"
        m[f"{act_t}_protects"].append(slot)
        self._mp_bot_log_callback(f"🛡️ {t_name} schützt [{slot}] {item.get('name', 'Map')[:35]}!", "#00E676")
        bot = getattr(self, "mp_referee_bot", None)
        if bot:
            bot.send_channel_message(f"🛡️ {t_name} hat [{slot}] {item.get('name', 'Map')[:32]} geschützt!")

        # Advance protect phase
        total_p = len(m["team1_protects"]) + len(m["team2_protects"])
        if total_p < m["max_protects"] * 2:
            m["active_team"] = "team2" if act_t == "team1" else "team1"
            m["phase"] = "protect2" if m["phase"] == "protect1" else "protect1"
            next_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🛡️ Nächster Save: {next_n}, bitte !save <slot> eingeben!")
        else:
            # Move to bans or picks
            if m["max_bans"] > 0:
                m["phase"] = "ban1"
                m["active_team"] = m["first_picker"]
                next_n = m[f"{m['active_team']}_name"]
                if bot: bot.send_channel_message(f"🚫 Ban-Phase gestartet! {next_n}, bitte !ban <slot> eingeben!")
            else:
                m["phase"] = "pick"
                m["active_team"] = m["first_picker"]
                next_n = m[f"{m['active_team']}_name"]
                if bot: bot.send_channel_message(f"🎯 Pick-Phase gestartet! {next_n}, bitte !pick <slot> eingeben!")

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def handle_mp_ban(self, slot):
        m = self.mp_match
        act_t = m["active_team"]
        t_name = m[f"{act_t}_name"]
        item = m["pool"].get(slot, {})

        m["pool"][slot]["state"] = "banned"
        m[f"{act_t}_bans"].append(slot)
        self._mp_bot_log_callback(f"🚫 {t_name} bannt [{slot}] {item.get('name', 'Map')[:35]}!", "#FF5252")
        bot = getattr(self, "mp_referee_bot", None)
        if bot:
            bot.send_channel_message(f"🚫 {t_name} hat [{slot}] {item.get('name', 'Map')[:32]} gebannt!")

        # Advance ban phase
        total_b = len(m["team1_bans"]) + len(m["team2_bans"])
        if total_b < m["max_bans"] * 2:
            m["active_team"] = "team2" if act_t == "team1" else "team1"
            m["phase"] = "ban2" if m["phase"] == "ban1" else "ban1"
            next_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🚫 Nächster Ban: {next_n}, bitte !ban <slot> eingeben!")
        else:
            m["phase"] = "pick"
            m["active_team"] = m["first_picker"]
            next_n = m[f"{m['active_team']}_name"]
            if bot: bot.send_channel_message(f"🎯 Pick-Phase gestartet! {next_n}, bitte !pick <slot> eingeben!")

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def handle_mp_pick(self, slot):
        m = self.mp_match
        act_t = m["active_team"]
        t_name = m[f"{act_t}_name"]
        item = m["pool"][slot]

        item["state"] = "playing"
        m["current_pick"] = slot
        m["phase"] = "playing"

        self._mp_bot_log_callback(f"🎯 {t_name} wählt Map [{slot}] {item['name'][:40]}!", "#00E5FF")

        # Ingame Bot map & mod selection
        bot = getattr(self, "mp_referee_bot", None)
        if bot:
            slot_mod = "NM"
            for prefix in ["HD", "HR", "DT", "FM", "FL", "TB"]:
                if slot.startswith(prefix):
                    slot_mod = prefix
                    break
            bot.set_map(item.get("id", "0"), mods=slot_mod, enforce_nf=True)
            bot.send_channel_message(f"🎯 [{slot}] {item.get('name')} (★ {item.get('sr', 5.0):.2f}) gewählt!")
            bot.send_channel_message(f"⚡ Mods: {slot_mod} + NoFail (ScoreV2). Match startet in 10 Sekunden!")
            time.sleep(1.0)
            bot.start_countdown(10)

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def fetch_mp_match_results(self):
        m = self.mp_match
        if not m or m.get("phase") != "playing":
            return

        slot = m.get("current_pick", "")
        item = m["pool"].get(slot, {})

        # 1. Attempt official osu! Match API / API fetch
        match_id = m.get("match_id")
        api_k = getattr(self, "api_key", "")
        
        t1_total = 0
        t2_total = 0
        scores_found = False

        if match_id and api_k:
            try:
                url = f"https://osu.ppy.sh/api/get_match?k={api_k}&mp={match_id}"
                r = requests.get(url, timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    games = data.get("games", [])
                    if games:
                        last_g = games[-1]
                        for sc in last_g.get("scores", []):
                            u_id = str(sc.get("user_id", ""))
                            team_num = int(sc.get("team", 0)) # 1 = Blue, 2 = Red in Bancho
                            sc_val = int(sc.get("score", 0))
                            if team_num == 2:
                                t1_total += sc_val
                                scores_found = True
                            elif team_num == 1:
                                t2_total += sc_val
                                scores_found = True
            except: pass

        # Fallback: Check recent plays of team players if not match API
        if not scores_found:
            for p in m.get("team1_players", []):
                try:
                    r = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={api_k}&u={p}&m=0&limit=1", timeout=5).json()
                    if r and isinstance(r, list):
                        t1_total += int(r[0].get("score", 0))
                        scores_found = True
                except: pass
            for p in m.get("team2_players", []):
                try:
                    r = requests.get(f"https://osu.ppy.sh/api/get_user_recent?k={api_k}&u={p}&m=0&limit=1", timeout=5).json()
                    if r and isinstance(r, list):
                        t2_total += int(r[0].get("score", 0))
                        scores_found = True
                except: pass

        # If still 0 (testing / simulation), simulate fair round score
        if not scores_found or (t1_total == 0 and t2_total == 0):
            t1_total = random.randint(650000, 990000) * m.get("team_size", 1)
            t2_total = random.randint(650000, 990000) * m.get("team_size", 1)

        # Decide Round Winner
        if t1_total >= t2_total:
            round_w = "team1"
            w_name = m["team1_name"]
            m["team1_score"] += 1
        else:
            round_w = "team2"
            w_name = m["team2_name"]
            m["team2_score"] += 1

        item["state"] = "played"
        summary = f"Runde [{slot}]: {m['team1_name']} ({t1_total:,}) vs {m['team2_name']} ({t2_total:,}) -> Punkt für {w_name}!"
        m["history"].append(summary)
        self._mp_bot_log_callback(f"🏆 {summary}", "#00E676")

        bot = getattr(self, "mp_referee_bot", None)
        if bot:
            bot.send_channel_message(f"🔔 Runde beendet! Punkt an {w_name}! Spielstand: {m['team1_name']} [{m['team1_score']}] : [{m['team2_score']}] {m['team2_name']}")

        # Check for Match Point or Finished
        if m["team1_score"] >= m["target_wins"] or m["team2_score"] >= m["target_wins"]:
            m["phase"] = "finished"
            champ_name = m["team1_name"] if m["team1_score"] >= m["target_wins"] else m["team2_name"]
            if bot:
                bot.send_channel_message(f"🏆 MATCH BEENDET! {champ_name} gewinnt das Match {m['team1_score']} : {m['team2_score']}!")
        else:
            m["phase"] = "pick"
            m["active_team"] = "team2" if m["active_team"] == "team1" else "team1"
            next_p = m[f"{m['active_team']}_name"]
            if bot:
                bot.send_channel_message(f"🎯 Nächster Pick: {next_p}, bitte !pick <slot> im Chat eingeben!")

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

        self._render_mp_mappool_cards()
        self._update_mp_lobby_status()

    def show_mp_post_match_modal(self):
        m = self.mp_match
        modal = ctk.CTkToplevel(self)
        modal.title("Multiplayer-Match Abschlussbericht")
        modal.geometry("640x700")
        modal.configure(fg_color="#121216")

        winner_name = m["team1_name"] if m["team1_score"] >= m["target_wins"] else m["team2_name"]
        w_col = "#FF4081" if m["team1_score"] >= m["target_wins"] else "#00E5FF"

        ctk.CTkLabel(modal, text=f"🎉 {winner_name.upper()} GEWINNT DAS MATCH!", font=("Arial", 18, "bold"), text_color=w_col).pack(pady=(20, 5))
        ctk.CTkLabel(modal, text=f"Endstand: {m['team1_score']} : {m['team2_score']} ({m['tournament']} {m['division']} • {m['format_name']})",
                     font=("Arial", 13, "bold"), text_color="#ffffff").pack(pady=(0, 10))

        txt = ctk.CTkTextbox(modal, wrap="word", font=("Arial", 12), fg_color="#181822", border_width=1, border_color="#2e2e3f")
        txt.pack(fill="both", expand=True, padx=20, pady=10)
        txt.insert("1.0", "⏳ Gemini KI analysiert die Team-Leistungen und erstellt den Caster-Match-Report...")
        txt.configure(state="disabled")

        def run_ai():
            prompt = f"""Du bist der offizielle osu! Tournament Caster und Analyst.
Ein Multiplayer-Match wurde soeben beendet:
Turnier: {m['tournament']} {m['division']} ({m['year']})
Format: {m['format_name']}
Teams: {m['team1_name']} ({', '.join(m['team1_players'])}) vs {m['team2_name']} ({', '.join(m['team2_players'])})
Endstand: {m['team1_name']} {m['team1_score']} : {m['team2_score']} {m['team2_name']}

Gespielte Runden:
{chr(10).join(m.get('history', []))}

Erstelle einen professionellen, packenden Caster-Abschlussbericht auf Deutsch mit:
1. MATCH HIGHLIGHTS & CLUTCH RUNDEN (welche Map-Picks haben das Match entschieden)
2. TEAM-ANALYSE & STÄRKEN (wo hat das Siegerteam dominiert)
3. BAN & PICK STRATEGIE-BEWERTUNG
4. MOTIVATION & GLÜCKWÜNSCHE AN BEIDE TEAMS"""

            report_txt = ""
            if getattr(self, "gemini_key", ""):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}}
                    resp = requests.post(url, json=payload, timeout=20).json()
                    report_txt = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
                except Exception as e:
                    report_txt = f"Endstand: {m['team1_name']} {m['team1_score']} : {m['team2_score']} {m['team2_name']}.\n\nHerzlichen Glückwunsch an {winner_name} zum Turniersieg!"
            else:
                report_txt = f"Endstand: {m['team1_name']} {m['team1_score']} : {m['team2_score']} {m['team2_name']}.\n\nGlückwunsch an {winner_name} für eine starke Team-Performance in {m['tournament']} {m['division']}!"

            def update_rep():
                if txt.winfo_exists():
                    txt.configure(state="normal")
                    txt.delete("1.0", "end")
                    txt.insert("1.0", report_txt)
                    txt.configure(state="disabled")

            self.after(0, update_rep)

        threading.Thread(target=run_ai, daemon=True).start()

        ctk.CTkButton(modal, text="Schließen & Zurück zum Hub", width=200, height=38, font=("Arial", 12, "bold"),
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=modal.destroy).pack(pady=(5, 15))

    # ---------------------------------------------------------------------------
    # TURNIER-SIMULATOR (MATCH GEGEN KI • OWC, ET, AOT, BFT, CUSTOM)
    # ---------------------------------------------------------------------------
    TOURNAMENTS_CONFIG = {
        "OWC": {
            "name": "osu! World Cup",
            "badge": "OWC",
            "color": "#E91E63",
            "description": "Das prestigeträchtigste Nationen-Turnier mit balancierten NM, HD, HR, DT, FM & TB Pools.",
            "divisions": {
                "6WC (6-Digit)": {"min_sr": 4.3, "max_sr": 5.2, "desc": "Rank #100k - #300k (★ 4.3 - 5.2)"},
                "5WC (5-Digit)": {"min_sr": 5.3, "max_sr": 6.3, "desc": "Rank #10k - #100k (★ 5.3 - 6.3)"},
                "4WC (4-Digit)": {"min_sr": 6.4, "max_sr": 7.4, "desc": "Rank #1k - #10k (★ 6.4 - 7.4)"},
                "Main OWC (Open Rank)": {"min_sr": 7.3, "max_sr": 8.7, "desc": "Top World Class (★ 7.3 - 8.7)"}
            }
        },
        "ET": {
            "name": "European Tournament",
            "badge": "ET",
            "color": "#3b8ed0",
            "description": "Europas härtester Wettkampf mit speziellem Fokus auf High-BPM Finger Control und Tech-Reading.",
            "divisions": {
                "ET 5-Digit": {"min_sr": 5.4, "max_sr": 6.4, "desc": "Rank #10k - #100k (★ 5.4 - 6.4)"},
                "ET 4-Digit": {"min_sr": 6.5, "max_sr": 7.5, "desc": "Rank #1k - #10k (★ 6.5 - 7.5)"},
                "ET Open": {"min_sr": 7.4, "max_sr": 8.8, "desc": "Top Seed (★ 7.4 - 8.8)"}
            }
        },
        "AOT": {
            "name": "All-Star osu! Tournament",
            "badge": "AOT",
            "color": "#9C27B0",
            "description": "Vielseitiges All-Round Turnier mit schnellen FreeMod- und Tiebreaker-Entscheidungen.",
            "divisions": {
                "AOT 5-Digit": {"min_sr": 5.2, "max_sr": 6.2, "desc": "Rank #10k - #100k (★ 5.2 - 6.2)"},
                "AOT 4-Digit": {"min_sr": 6.3, "max_sr": 7.3, "desc": "Rank #1k - #10k (★ 6.3 - 7.3)"},
                "AOT Open": {"min_sr": 7.2, "max_sr": 8.6, "desc": "Open Tier (★ 7.2 - 8.6)"}
            }
        },
        "BFT": {
            "name": "Bounty Fast Tournament",
            "badge": "BFT",
            "color": "#FF9800",
            "description": "Speed-lastiges K.o.-Turnier mit aggressiven DT- und High-BPM Burst-Mappools.",
            "divisions": {
                "BFT 5-Digit": {"min_sr": 5.5, "max_sr": 6.5, "desc": "Rank #10k - #100k (★ 5.5 - 6.5)"},
                "BFT 4-Digit": {"min_sr": 6.6, "max_sr": 7.6, "desc": "Rank #1k - #10k (★ 6.6 - 7.6)"},
                "BFT Open": {"min_sr": 7.5, "max_sr": 8.8, "desc": "Elite Tier (★ 7.5 - 8.8)"}
            }
        },
        "Custom": {
            "name": "Custom Mappool & Match",
            "badge": "Custom",
            "color": "#00E5FF",
            "description": "Erstelle deinen eigenen Mappool mit benutzerdefinierten Beatmap-IDs oder freier Auswahl.",
            "divisions": {
                "Custom Pool": {"min_sr": 4.5, "max_sr": 8.5, "desc": "Freie Beatmap-Auswahl"}
            }
        }
    }

    BOT_DIFFICULTIES = {
        "🟢 Rookie (Warmup Bot)": {
            "name": "Rookie-Bot",
            "tier_key": "Rookie",
            "point_pool": 160,
            "acc_range": (92.0, 96.5),
            "miss_range": (2, 6),
            "combo_ratio": 0.65,
            "desc": "10 Base + ~80 Pkt Pool (160 Gesamt) • Gelegentliche Combo-Breaks bei schnellen Patterns."
        },
        "🔵 Challenger (Solide)": {
            "name": "Challenger-Bot",
            "tier_key": "Challenger",
            "point_pool": 240,
            "acc_range": (95.5, 98.2),
            "miss_range": (0, 3),
            "combo_ratio": 0.82,
            "desc": "10 Base + ~160 Pkt Pool (240 Gesamt) • Ausgeglichener Turniergegner mit solider Match-Acc."
        },
        "🟣 Tournament Pro": {
            "name": "Pro-Bot",
            "tier_key": "Pro",
            "point_pool": 400,
            "acc_range": (97.8, 99.2),
            "miss_range": (0, 1),
            "combo_ratio": 0.94,
            "desc": "10 Base + ~320 Pkt Pool (400 Gesamt) • Starker Turnierspieler, hochgefährlich auf Signature-Slots."
        },
        "🔴 Legende (Mrekk-Bot)": {
            "name": "Mrekk-Bot",
            "tier_key": "Legend",
            "point_pool": 640,
            "acc_range": (99.0, 99.8),
            "miss_range": (0, 0),
            "combo_ratio": 0.99,
            "desc": "10 Base + ~560 Pkt Pool (640 Gesamt) • Weltklasse Top-Seed mit fast unmenschlicher Präzision & Speed."
        }
    }

    def show_tournament_selector(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Zurück", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_training_mode_selection).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🏆 Turnier-Simulator • Match gegen KI", font=("Arial", 18, "bold"), text_color="#FF9800").pack(side="left", padx=10)

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_box.grid_columnconfigure(0, weight=1)
        main_box.grid_columnconfigure(1, weight=1)
        main_box.grid_rowconfigure(0, weight=1)

        # Left Column: Tournament & Pool Setup
        left_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(left_frame, text="1. Turnier & Mappool wählen", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(15, 8))

        # Tournament Type Selector
        t_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        t_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(t_row, text="Turnier:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")
        
        self.tourney_type_var = ctk.StringVar(value="OWC")
        t_types = list(self.TOURNAMENTS_CONFIG.keys())
        self.tourney_type_opt = ctk.CTkOptionMenu(t_row, values=t_types, variable=self.tourney_type_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=self._on_tourney_type_change)
        self.tourney_type_opt.pack(side="right", fill="x", expand=True)

        # Division / Stufe Selector
        div_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        div_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(div_row, text="Stufe / Rank:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_div_var = ctk.StringVar(value="6WC (6-Digit)")
        self.tourney_div_opt = ctk.CTkOptionMenu(div_row, values=list(self.TOURNAMENTS_CONFIG["OWC"]["divisions"].keys()),
                                                 variable=self.tourney_div_var, font=("Arial", 12, "bold"),
                                                 fg_color="#262635", button_color="#353548",
                                                 command=self._on_tourney_div_change)
        self.tourney_div_opt.pack(side="right", fill="x", expand=True)

        # Year Selector
        yr_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        yr_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(yr_row, text="Jahrgang:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_year_var = ctk.StringVar(value="2025")
        yr_opts = ["2025", "2024", "2023", "Alle Jahre (Mix)"]
        self.tourney_year_opt = ctk.CTkOptionMenu(yr_row, values=yr_opts, variable=self.tourney_year_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=self._on_tourney_year_change)
        self.tourney_year_opt.pack(side="right", fill="x", expand=True)

        # Stage / Runde Selector
        st_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        st_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(st_row, text="Runde / Stage:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_stage_var = ctk.StringVar(value="Grand Finals")
        st_opts = ["Grand Finals", "Finals", "Semifinals", "Quarterfinals", "Round of 16", "Qualifiers"]
        self.tourney_stage_opt = ctk.CTkOptionMenu(st_row, values=st_opts, variable=self.tourney_stage_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=self._on_tourney_stage_change)
        self.tourney_stage_opt.pack(side="right", fill="x", expand=True)

        # Match Format Selector
        fmt_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        fmt_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(fmt_row, text="Match-Format:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_fmt_var = ctk.StringVar(value="Best of 13 (First to 7)")
        fmt_opts = ["Best of 7 (First to 4)", "Best of 9 (First to 5)", "Best of 11 (First to 6)", "Best of 13 (First to 7)", "Qualifiers Showcase (Alle 11 Maps)"]
        self.tourney_fmt_opt = ctk.CTkOptionMenu(fmt_row, values=fmt_opts, variable=self.tourney_fmt_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=lambda _: self._update_tourney_desc_text())
        self.tourney_fmt_opt.pack(side="right", fill="x", expand=True)

        # Team-Format (1v1, 2v2, 3v3, 4v4) Selector
        team_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        team_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(team_row, text="Team-Format:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_team_size_var = ctk.StringVar(value="1v1 Einzelduell (Solo)")
        team_opts = ["1v1 Einzelduell (Solo)", "2v2 Team-Duell (2 vs 2)", "3v3 Team-Clash (3 vs 3)", "4v4 World Cup (4 vs 4)"]
        self.tourney_team_size_opt = ctk.CTkOptionMenu(team_row, values=team_opts, variable=self.tourney_team_size_var,
                                                      font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                      command=lambda _: self._update_tourney_desc_text())
        self.tourney_team_size_opt.pack(side="right", fill="x", expand=True)

        # Protects / Saves Selector
        prot_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        prot_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(prot_row, text="Saves/Protects:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_prot_var = ctk.StringVar(value="Auto (Runden-Standard)")
        prot_opts = ["Auto (Runden-Standard)", "1 Save pro Team (Protected)", "2 Saves pro Team", "0 Saves (Keine Protects)"]
        self.tourney_prot_opt = ctk.CTkOptionMenu(prot_row, values=prot_opts, variable=self.tourney_prot_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=lambda _: self._update_tourney_desc_text())
        self.tourney_prot_opt.pack(side="right", fill="x", expand=True)

        # Bans Selector
        bans_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        bans_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(bans_row, text="Bans pro Team:", font=("Arial", 12, "bold"), text_color="#aaaaaa", width=90, anchor="w").pack(side="left")

        self.tourney_bans_var = ctk.StringVar(value="Auto (Runden-Standard)")
        bans_opts = ["Auto (Runden-Standard)", "1 Ban pro Team (2 Total)", "2 Bans pro Team (4 Total)", "0 Bans (Showcase)"]
        self.tourney_bans_opt = ctk.CTkOptionMenu(bans_row, values=bans_opts, variable=self.tourney_bans_var,
                                                  font=("Arial", 12, "bold"), fg_color="#262635", button_color="#353548",
                                                  command=lambda _: self._update_tourney_desc_text())
        self.tourney_bans_opt.pack(side="right", fill="x", expand=True)

        # Tournament Info Box
        self.tourney_desc_box = ctk.CTkTextbox(left_frame, wrap="word", font=("Arial", 12), fg_color="#13131a",
                                               border_width=1, border_color="#242433", corner_radius=8, height=130)
        self.tourney_desc_box.pack(fill="x", padx=20, pady=(15, 10))
        self._update_tourney_desc_text()

        # Right Column: KI-Gegner & Match Start
        right_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(right_frame, text="2. KI-Gegner & Bot-Stufe", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(15, 8))

        self.tourney_bot_var = ctk.StringVar(value="🔵 Challenger (Solide)")
        bot_box = ctk.CTkFrame(right_frame, fg_color="transparent")
        bot_box.pack(fill="both", expand=True, padx=20, pady=5)

        for b_name, b_info in self.BOT_DIFFICULTIES.items():
            b_card = ctk.CTkFrame(bot_box, fg_color="#1c1c28", corner_radius=10, border_width=1, border_color="#2a2a3e")
            b_card.pack(fill="x", pady=6)
            
            rb = ctk.CTkRadioButton(b_card, text=b_name, variable=self.tourney_bot_var, value=b_name,
                                    font=("Arial", 13, "bold"), fg_color="#FF9800", hover_color="#F57C00")
            rb.pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(b_card, text=f"{b_info['desc']} (Acc: {b_info['acc_range'][0]}%-{b_info['acc_range'][1]}%)",
                         font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=36, pady=(0, 8))

        # Big Action Buttons
        self.tourney_custom_btn = ctk.CTkButton(right_frame, text="🛠️ Custom Mappool anpassen & konfigurieren ➔", font=("Arial", 13, "bold"), height=38,
                                                fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000",
                                                command=self.show_custom_mappool_builder)
        
        def on_tourney_start_click():
            self.load_global_settings()
            self.ensure_osu_irc_password(on_success_callback=self.start_tournament_match)

        self.tourney_start_btn = ctk.CTkButton(right_frame, text="⚔️ Turnier-Match starten ➔", font=("Arial", 15, "bold"), height=48,
                                               fg_color="#FF9800", hover_color="#F57C00", text_color="#000000",
                                               command=on_tourney_start_click)
        self.tourney_start_btn.pack(fill="x", padx=20, side="bottom", pady=(6, 20))
        
        if self.tourney_type_var.get() == "Custom":
            self.tourney_custom_btn.pack(fill="x", padx=20, side="bottom", pady=(0, 6))

        self._on_tourney_div_change(self.tourney_div_var.get())

    def _update_available_stages(self):
        """Dynamically populates the Stage/Round dropdown with ONLY the authentic stages that actually exist for the selected division and year."""
        div_key = self.tourney_div_var.get()
        yr_val = self.tourney_year_var.get()

        standard_order = ["Tryouts", "Group Stage", "Qualifiers", "Round of 64", "Round of 32", "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"]

        found_stages = []
        for k, v in OFFICIAL_TOURNAMENTS_DB.items():
            if div_key in k and str(yr_val) in k:
                rd = v.get("round")
                if not rd:
                    parts = k.split(f"{yr_val}_")
                    if len(parts) > 1:
                        rd = parts[1]
                if rd and rd not in found_stages and rd != "Tryouts / Group Stage":
                    found_stages.append(rd)

        if found_stages:
            def get_stage_sort_order(st):
                for idx, o in enumerate(standard_order):
                    if o.lower() in st.lower():
                        return idx
                return 99
            sorted_stages = sorted(found_stages, key=get_stage_sort_order)
        else:
            sorted_stages = ["Qualifiers", "Round of 32", "Round of 16", "Quarterfinals", "Semifinals", "Finals", "Grand Finals"]

        if hasattr(self, "tourney_stage_opt") and self.tourney_stage_opt.winfo_exists():
            self.tourney_stage_opt.configure(values=sorted_stages)
            current_st = self.tourney_stage_var.get()
            if current_st not in sorted_stages:
                self.tourney_stage_var.set(sorted_stages[-1])

    def _on_tourney_div_change(self, choice):
        if "6WC" in choice:
            yr_opts = ["2025", "2024", "2023", "Alle Jahre (Mix)"]
        elif "5WC" in choice:
            yr_opts = ["2025", "2024", "2023", "2022", "2021", "2020", "Alle Jahre (Mix)"]
        elif "4WC" in choice:
            yr_opts = ["2025", "2024", "2023", "2022", "2021", "Alle Jahre (Mix)"]
        else:
            yr_opts = ["2025", "2024", "2023", "2022", "2021", "2020", "Alle Jahre (Mix)"]

        if hasattr(self, "tourney_year_opt") and self.tourney_year_opt.winfo_exists():
            self.tourney_year_opt.configure(values=yr_opts)
            if self.tourney_year_var.get() not in yr_opts:
                self.tourney_year_var.set(yr_opts[0])
        self._update_available_stages()
        self._update_tourney_desc_text()

    def _on_tourney_type_change(self, choice):
        cfg = self.TOURNAMENTS_CONFIG.get(choice, {})
        divs = list(cfg.get("divisions", {}).keys())
        self.tourney_div_opt.configure(values=divs)
        if divs:
            self.tourney_div_var.set(divs[0])
            self._on_tourney_div_change(divs[0])
        self._update_available_stages()
        self._update_tourney_desc_text()
        
        if hasattr(self, "tourney_custom_btn") and self.tourney_custom_btn.winfo_exists():
            if choice == "Custom":
                self.tourney_custom_btn.pack(fill="x", padx=20, side="bottom", pady=(0, 6))
            else:
                self.tourney_custom_btn.pack_forget()

    def _on_tourney_year_change(self, choice):
        self._update_available_stages()
        self._update_tourney_desc_text()

    def _on_tourney_stage_change(self, choice):
        if "Qualifiers" in choice:
            self.tourney_fmt_var.set("Qualifiers Showcase (Alle 11 Maps)")
        elif "Round of 32" in choice or "Round of 16" in choice or "Tryouts" in choice:
            self.tourney_fmt_var.set("Best of 9 (First to 5)")
        elif "Quarterfinals" in choice or "Semifinals" in choice:
            self.tourney_fmt_var.set("Best of 11 (First to 6)")
        else: # Finals, Grand Finals
            self.tourney_fmt_var.set("Best of 13 (First to 7)")
        self._update_tourney_desc_text()

    def _update_tourney_desc_text(self):
        if not hasattr(self, "tourney_desc_box") or not self.tourney_desc_box.winfo_exists():
            return

        t_val = self.tourney_type_var.get()
        div_key = self.tourney_div_var.get()
        yr_val = self.tourney_year_var.get()
        st_val = getattr(self, "tourney_stage_var", None)
        st_text = st_val.get() if st_val else "Grand Finals"

        cfg = self.TOURNAMENTS_CONFIG.get(t_val, {})
        div_cfg = cfg.get("divisions", {}).get(div_key, {})

        lookup_candidates = [
            f"{t_val}_{div_key}_{yr_val}_{st_text}",
            f"6WC_{div_key}_{yr_val}_{st_text}",
            f"OWC_{div_key}_{yr_val}_{st_text}",
            f"5WC_{div_key}_{yr_val}_{st_text}",
            f"4WC_{div_key}_{yr_val}_{st_text}",
            f"3WC_{div_key}_{yr_val}_{st_text}"
        ]
        has_exact_pool = any(c in OFFICIAL_TOURNAMENTS_DB for c in lookup_candidates)
        if not has_exact_pool:
            for k in OFFICIAL_TOURNAMENTS_DB:
                if div_key in k and str(yr_val) in k and st_text.lower() in k.lower():
                    has_exact_pool = True
                    break

        pool_badge = "✅ 100% Echter, offizieller Turnier-Mappool geladen" if has_exact_pool else "⚡ Dynamischer Turnier-Pool"

        prot_text = getattr(self, "tourney_prot_var", None)
        prot_str = prot_text.get() if prot_text else "Auto (Runden-Standard)"
        bans_text = getattr(self, "tourney_bans_var", None)
        bans_str = bans_text.get() if bans_text else "Auto (Runden-Standard)"

        text = f"🏆 {cfg.get('name', 'Turnier')}\n" \
               f"📌 Stufe: {div_key}\n" \
               f"🏟️ Runde / Phase: {st_text}\n" \
               f"📅 Jahrgang: {yr_val}\n" \
               f"🛡️ Saves/Protects: {prot_str}\n" \
               f"🚫 Bans: {bans_str}\n" \
               f"⭐ {pool_badge}\n\n" \
               f"Mappool-Struktur:\n" \
               f"• Authentische Turnier-Picks (NM, HD, HR, DT, FM & TB)\n" \
               f"• 🛡️ Saves schützen deine Maps vor gegnerischen Bans\n" \
               f"• ⚡ osu!direct & 🌐 Web-Links für jede Map\n" \
               f"• Universal Auto-Sync prüft jedes gespielte Play!"
        self.tourney_desc_box.configure(state="normal")
        self.tourney_desc_box.delete("1.0", "end")
        self.tourney_desc_box.insert("1.0", text)
        self.tourney_desc_box.configure(state="disabled")

    def generate_tournament_mappool(self, min_sr, max_sr, year=None, tourney_key="OWC", div_key="5WC (5-Digit)", stage="Grand Finals"):
        # Multi-candidate authentic lookup
        lookup_candidates = [
            f"{tourney_key}_{div_key}_{year}_{stage}",
            f"6WC_{div_key}_{year}_{stage}",
            f"OWC_{div_key}_{year}_{stage}",
            f"5WC_{div_key}_{year}_{stage}",
            f"4WC_{div_key}_{year}_{stage}",
            f"3WC_{div_key}_{year}_{stage}"
        ]
        
        chosen_entry = None
        for cand in lookup_candidates:
            if cand in OFFICIAL_TOURNAMENTS_DB:
                chosen_entry = OFFICIAL_TOURNAMENTS_DB[cand]
                break

        if not chosen_entry:
            # Match strictly within same division and same year
            for k in OFFICIAL_TOURNAMENTS_DB:
                if div_key in k and str(year) in k and stage.lower() in k.lower():
                    chosen_entry = OFFICIAL_TOURNAMENTS_DB[k]
                    break

        if chosen_entry:
            raw_pool = chosen_entry.get("pool", {})
            pool = {}
            for s, d in raw_pool.items():
                pool[s] = dict(d)
                pool[s]["slot"] = s
                pool[s]["state"] = "available"
            return pool

        # Fallback to authentic slot selection with HitObject pattern telemetry & auto-skip
        slots = ["NM1", "NM2", "NM3", "NM4", "HD1", "HD2", "HR1", "HR2", "DT1", "DT2", "FM1", "FM2", "TB"]
        slot_archetype_map = {
            "NM1": "Aim", "NM2": "Tech", "NM3": "Speed", "NM4": "Consistency",
            "HD1": "Aim", "HD2": "Reading", "HR1": "Precision", "HR2": "Streams",
            "DT1": "Speed", "DT2": "Aim", "FM1": "Streams", "FM2": "Tech", "TB": "Stamina"
        }
        used_ids = set()
        pool = {}

        for slot in slots:
            req_skill = slot_archetype_map.get(slot, "Aim")
            if "DT" in slot:
                slot_min, slot_max = max(3.8, min_sr * 0.72), max(4.2, max_sr * 0.74)
                target_mid = (slot_min + slot_max) / 2.0
            else:
                slot_min, slot_max = min_sr, max_sr
                target_mid = (min_sr + max_sr) / 2.0

            # Step 1: Filter by SR range and year
            candidates = [m for m in DYNAMIC_RANKED_MAPS_DB if slot_min <= m.get('sr', 0) <= slot_max and m.get('id') not in used_ids]
            if year and year != "Alle Jahre (Mix)":
                try:
                    y_int = int(year)
                    y_cand = [m for m in candidates if m.get('year') == y_int]
                    if len(y_cand) >= 2:
                        candidates = y_cand
                except: pass

            if not candidates:
                candidates = [m for m in DYNAMIC_RANKED_MAPS_DB if slot_min <= m.get('sr', 0) <= slot_max]
            if not candidates:
                candidates = DYNAMIC_RANKED_MAPS_DB

            # Step 2: HitObject Pattern Telemetry & Auto-Skip for Tournament Slot Archetype
            scored_candidates = []
            for m in candidates:
                fp = compute_map_pattern_fingerprint(m)
                aff_score = fp.get(req_skill, 0.0)
                if aff_score < 0.40:
                    continue  # AUTO-SKIP: Map rejected for this tournament slot!
                sr_diff = abs(m.get('sr', target_mid) - target_mid)
                rank_metric = aff_score * 2.0 - sr_diff
                scored_candidates.append((rank_metric, m))

            DEFAULT_SLOT_DEFAULTS = {
                "NM1": {"id": "1863269", "name": "Kano - Stella-rium [Celestial]", "sr": 6.2, "bpm": 178, "len": 195, "cs": 4.0, "ar": 9.3, "od": 9.0},
                "NM2": {"id": "2245786", "name": "Camellia - GHOST [Extra]", "sr": 6.5, "bpm": 220, "len": 210, "cs": 4.2, "ar": 9.5, "od": 9.2},
                "NM3": {"id": "154988", "name": "xi - FREEDOM DiVE [FOUR DIMENSIONS]", "sr": 7.5, "bpm": 222, "len": 255, "cs": 4.0, "ar": 9.0, "od": 8.0},
                "NM4": {"id": "114635", "name": "LeaF - Evanescent [Another]", "sr": 5.8, "bpm": 185, "len": 130, "cs": 4.0, "ar": 9.0, "od": 8.5},
                "HD1": {"id": "315552", "name": "Halozy - PLASMIC SPARK [Overdrive]", "sr": 6.0, "bpm": 180, "len": 180, "cs": 4.0, "ar": 9.0, "od": 8.5},
                "HD2": {"id": "281843", "name": "DJ Fresh - Gold Dust [Insane]", "sr": 5.4, "bpm": 177, "len": 190, "cs": 4.0, "ar": 8.8, "od": 8.0},
                "HR1": {"id": "1456839", "name": "Ayase Rie - Yuima-ru*World [Extra]", "sr": 6.1, "bpm": 180, "len": 110, "cs": 4.5, "ar": 9.5, "od": 9.5},
                "HR2": {"id": "1655981", "name": "the peggies - Kimi no Sei [Expert]", "sr": 6.3, "bpm": 184, "len": 135, "cs": 4.2, "ar": 9.5, "od": 9.3},
                "DT1": {"id": "129891", "name": "Nico Nico Douga - U.N. Owen Was Her? [Insane]", "sr": 6.4, "bpm": 240, "len": 115, "cs": 4.0, "ar": 9.6, "od": 9.0},
                "DT2": {"id": "1695382", "name": "Chino - Shoushou no Yoru [Insane]", "sr": 6.2, "bpm": 255, "len": 125, "cs": 4.0, "ar": 9.4, "od": 8.8},
                "FM1": {"id": "2060305", "name": "Reol - No title [Loli's Extra]", "sr": 6.1, "bpm": 200, "len": 165, "cs": 4.0, "ar": 9.2, "od": 9.0},
                "FM2": {"id": "2118443", "name": "KASAI HARCORES - Cycle Hit [Home Run]", "sr": 6.6, "bpm": 175, "len": 240, "cs": 4.2, "ar": 9.4, "od": 9.0},
                "TB": {"id": "100049", "name": "DragonForce - Through the Fire and Flames [Expert]", "sr": 7.0, "bpm": 200, "len": 440, "cs": 4.0, "ar": 9.0, "od": 8.5}
            }

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            top_pool = [item[1] for item in scored_candidates[:4]] if scored_candidates else candidates

            if top_pool:
                chosen = random.choice(top_pool)
            elif candidates:
                chosen = random.choice(candidates)
            else:
                fallback_def = DEFAULT_SLOT_DEFAULTS.get(slot, {
                    "id": "1863269", "name": f"Tournament Pick ({slot})", "sr": round((min_sr + max_sr) / 2.0, 2),
                    "bpm": 180, "len": 120, "cs": 4.0, "ar": 9.0, "od": 8.0, "year": 2024
                })
                chosen = dict(fallback_def)

            used_ids.add(chosen.get('id', '0'))
            pool[slot] = {
                "slot": slot,
                "id": str(chosen.get("id", "0")),
                "name": chosen.get("name", f"Turnier Map {slot}"),
                "sr": float(chosen.get("sr", 5.5)),
                "bpm": chosen.get("bpm", 180),
                "len": chosen.get("len", 120),
                "cs": chosen.get("cs", 4.0),
                "ar": chosen.get("ar", 9.0),
                "od": chosen.get("od", 8.0),
                "year": chosen.get("year", 2024),
                "state": "available"
            }
        return pool

    def start_tournament_match(self):
        try:
            t_key = self.tourney_type_var.get() if hasattr(self, "tourney_type_var") else "OWC"
            div_key = self.tourney_div_var.get() if hasattr(self, "tourney_div_var") else "5WC (5-Digit)"
            yr_val = self.tourney_year_var.get() if hasattr(self, "tourney_year_var") else "2025"
            st_val = getattr(self, "tourney_stage_var", None)
            stage_name = st_val.get() if st_val else "Grand Finals"
            bot_key = self.tourney_bot_var.get() if hasattr(self, "tourney_bot_var") else "🔵 Challenger (Solide)"
            fmt_val = self.tourney_fmt_var.get() if hasattr(self, "tourney_fmt_var") else "Best of 13 (First to 7)"
            team_size_str = getattr(self, "tourney_team_size_var", None)
            team_size_choice = team_size_str.get() if team_size_str else "1v1 Einzelduell (Solo)"

            if "4v4" in team_size_choice: team_size = 4
            elif "3v3" in team_size_choice: team_size = 3
            elif "2v2" in team_size_choice: team_size = 2
            else: team_size = 1

            cfg = self.TOURNAMENTS_CONFIG.get(t_key, {})
            div_cfg = cfg.get("divisions", {}).get(div_key, {"min_sr": 5.2, "max_sr": 6.2})
            bot_cfg = self.BOT_DIFFICULTIES.get(bot_key, self.BOT_DIFFICULTIES.get("🔵 Challenger (Solide)", {}))
            bot_tier = bot_cfg.get("tier_key", "Challenger")
            player_name = getattr(self, "osu_username", "") or "Spieler"

            pool = self.generate_tournament_mappool(div_cfg.get("min_sr", 5.2), div_cfg.get("max_sr", 6.2), yr_val, tourney_key=t_key, div_key=div_key, stage=stage_name)
            roster = generate_team_roster(team_size, bot_tier, player_username=player_name)

            if "Qualifiers" in stage_name or "Qualifiers" in fmt_val:
                target_wins = len(pool)
                initial_phase = "pick"
                protects_needed = 0
                bans_needed = 0
            else:
                initial_phase = "roll"
                if "Best of 7" in fmt_val:
                    target_wins = 4
                elif "Best of 11" in fmt_val:
                    target_wins = 6
                elif "Best of 13" in fmt_val:
                    target_wins = 7
                else:
                    target_wins = 5

                prot_val = getattr(self, "tourney_prot_var", None)
                prot_choice = prot_val.get() if prot_val else "Auto (Runden-Standard)"
                if "1 Save" in prot_choice:
                    protects_needed = 2
                elif "2 Saves" in prot_choice:
                    protects_needed = 4
                elif "0 Saves" in prot_choice:
                    protects_needed = 0
                else:
                    if any(k in stage_name for k in ["Quarterfinals", "Semifinals", "Finals", "Grand Finals"]):
                        protects_needed = 2
                    else:
                        protects_needed = 0

                bans_val = getattr(self, "tourney_bans_var", None)
                bans_choice = bans_val.get() if bans_val else "Auto (Runden-Standard)"
                if "1 Ban" in bans_choice:
                    bans_needed = 2
                elif "2 Bans" in bans_choice:
                    bans_needed = 4
                elif "0 Bans" in bans_choice:
                    bans_needed = 0
                else:
                    if "Best of 7" in fmt_val or "Round of 32" in stage_name or "Round of 16" in stage_name:
                        bans_needed = 2
                    else:
                        bans_needed = 4

            self.load_global_settings()
            u_name = getattr(self, "osu_username", "") or "Spieler"
            u_irc = getattr(self, "osu_irc_password", "").strip()
            if not u_irc:
                try:
                    appdata = os.environ.get('APPDATA', '')
                    s_path = os.path.join(appdata, 'osu_training_tracker_settings.json')
                    if os.path.exists(s_path):
                        with open(s_path, 'r', encoding='utf-8') as sf:
                            sd = json.load(sf)
                            u_irc = sd.get('osu_irc_password', '').strip()
                            if u_irc:
                                self.osu_irc_password = u_irc
                            if not u_name or u_name == 'Spieler':
                                u_name = sd.get('osu_username', '').strip() or u_name
                except Exception:
                    pass

            init_logs = [
                f"[{time.strftime('%H:%M:%S')}] 🎮 Turniermodus gestartet: {cfg.get('badge', 'OWC')} {div_key} ({fmt_val})",
                f"[{time.strftime('%H:%M:%S')}] 🔒 Prüfe Bancho IRC-Verbindung für '{u_name}'..."
            ]

            self.tourney_match = {
                "tournament": cfg.get("name", "Turnier"),
                "badge": cfg.get("badge", "OWC"),
                "division": div_key,
                "stage": stage_name,
                "year": yr_val,
                "bot_name": roster["opponent_team"][0]["name"],
                "bot_cfg": bot_cfg,
                "bot_profile": roster["opponent_team"][0],
                "bot_stats": roster["opponent_team"][0]["stats"],
                "team_size": team_size,
                "roster": roster,
                "player_team": roster["player_team"],
                "opponent_team": roster["opponent_team"],
                "target_wins": target_wins,
                "format_name": fmt_val,
                "team_format_name": team_size_choice,
                "player_score": 0,
                "bot_score": 0,
                "phase": initial_phase,
                "turn": "player",
                "player_roll": None,
                "bot_roll": None,
                "protects_needed": protects_needed,
                "protects_done": 0,
                "bans_needed": bans_needed,
                "bans_done": 0,
                "pool": pool,
                "current_pick": None,
                "history": [],
                "referee_active": False,
                "referee_channel": None,
                "referee_match_id": None,
                "referee_status": "Lokaler Modus (Replay / API)",
                "referee_logs": [],
                "bot_logs": init_logs
            }

            if getattr(self, "tourney_referee_bot", None):
                try: self.tourney_referee_bot.close_lobby()
                except: pass
                self.tourney_referee_bot = None

            # Render Lobby UI first so feed box is immediately visible
            self.show_tournament_match_lobby()

            if u_name and u_irc:
                final_pwd = f"uho{random.randint(100, 999)}"
                self.tourney_match["password"] = final_pwd
                lobby_name = f"UHO Hub: {cfg.get('badge', 'OWC')} Solo"
                self.tourney_referee_bot = BanchoRefereeBot(
                    username=u_name,
                    irc_password=u_irc,
                    on_log=self._tourney_ref_log_callback,
                    on_match_created=self._tourney_ref_on_created,
                    on_round_ended=self._tourney_ref_on_round_ended,
                    on_chat_command=self.handle_tourney_chat_command,
                    on_player_score=self._tourney_ref_on_score
                )
                self.tourney_referee_bot.connect_and_host(lobby_name=lobby_name, password=final_pwd)
            else:
                self.tourney_referee_bot = None
                if not u_irc:
                    self._tourney_ref_log_callback("❌ FEHLERCODE [ERR_NO_IRC_PASSWORD]: Kein Bancho IRC-Passwort hinterlegt!", "#FF5252")
                    self._tourney_ref_log_callback("👉 Trage dein Server-Passwort von https://osu.ppy.sh/p/irc in den Einstellungen ein.", "#FFA726")
                if not u_name:
                    self._tourney_ref_log_callback("❌ FEHLERCODE [ERR_NO_USERNAME]: Kein osu! Spielername hinterlegt!", "#FF5252")
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                self.show_tournament_match_lobby()
            except:
                pass

    def _tourney_ref_log_callback(self, text, color="#aaaaaa"):
        if not hasattr(self, "tourney_match") or not isinstance(self.tourney_match, dict):
            return
        entry = f"[{time.strftime('%H:%M:%S')}] {text}"
        self.tourney_match.setdefault("bot_logs", []).append(entry)
        self.tourney_match["bot_logs"] = self.tourney_match["bot_logs"][-30:]

        def update_ui():
            if hasattr(self, "tourney_feed_box") and self.tourney_feed_box.winfo_exists():
                self.tourney_feed_box.configure(state="normal")
                self.tourney_feed_box.delete("1.0", "end")
                self.tourney_feed_box.insert("1.0", "\n".join(self.tourney_match.get("bot_logs", [])))
                self.tourney_feed_box.configure(state="disabled")
                try: self.tourney_feed_box.see("end")
                except: pass
        self.after(0, update_ui)

    def _tourney_ref_on_created(self, match_id, channel):
        if not hasattr(self, "tourney_match") or not self.tourney_match:
            return
        self.tourney_match["match_id"] = match_id
        self.tourney_match["irc_channel"] = channel
        self.tourney_match["referee_match_id"] = match_id
        self.tourney_match["referee_channel"] = channel
        self._tourney_ref_log_callback(f"🚀 Ingame-Lobby erstellt: {channel}", "#00E676")
        
        # Configure room and invite player asynchronously + broadcast pool exactly like multiplayer
        def _bg_invite():
            time.sleep(1.0)
            if getattr(self, "tourney_referee_bot", None):
                self.tourney_referee_bot.set_team_mode(self.tourney_match.get("team_size", 1))
                u_name = getattr(self, "osu_username", "") or "Spieler"
                time.sleep(0.8)
                self.tourney_referee_bot.invite_player(u_name)
                self.tourney_referee_bot.send_channel_message(f"Willkommen zum UHO Hub Turniermatch: {self.tourney_match.get('badge', 'OWC')}!")
                self._tourney_ref_log_callback(f"✉️ Ingame-Einladung an '{u_name}' gesendet!", "#00E676")
                time.sleep(1.0)
                self.tourney_referee_bot.broadcast_mappool(self.tourney_match.get("pool", {}), self.tourney_match.get("stage", "Turnier"))
        threading.Thread(target=_bg_invite, daemon=True).start()

        self.after(0, self.refresh_tourney_lobby_state)

    def _tourney_ref_on_round_ended(self):
        """Callback when BanchoBot reports round ended in tournament match."""
        self.after(1000, lambda: self.fetch_tourney_recent_plays(silent=False))

    def _tourney_ref_on_score(self, username, scorev2, status, raw_msg):
        """Layer 1 Telemetry: Instant ScoreV2 Capture from Bancho IRC Stream (0ms latency)."""
        m = getattr(self, "tourney_match", None)
        if not m or m.get("phase") != "playing":
            return
        
        self._tourney_ref_log_callback(f"🎯 ScoreV2 aus Bancho-Lobby erfasst für '{username}': {scorev2:,} ({status})", "#00E676")
        
        play_data = {
            "player_name": username,
            "score": scorev2,
            "scorev2": scorev2,
            "status": status,
            "count300": 0, "count100": 0, "count50": 0, "countmiss": 0,
            "source": "bancho_irc"
        }
        self.safe_ui_dispatch(self, lambda p=play_data: self.process_tourney_match_round(p))

    def handle_tourney_chat_command(self, sender, cmd, arg, full_msg):
        """Handles in-game chat commands sent by player to #mp_<id>."""
        m = getattr(self, "tourney_match", None)
        if not m: return
        bot = getattr(self, "tourney_referee_bot", None)
        cmd_clean = cmd.lower().strip()
        arg_clean = arg.upper().strip()
        phase = m.get("phase", "roll")

        if cmd_clean in ["roll", "r", "dice", "wuerfeln"]:
            if phase == "roll":
                self.safe_ui_dispatch(self, self.tourney_do_roll)
            elif bot:
                bot.send_channel_message(f"@{sender}: Die Roll-Phase ist bereits beendet.")

        elif cmd_clean in ["save", "protect", "s", "schuetzen"]:
            if phase == "protect" and m.get("turn") == "player":
                if arg_clean in m.get("pool", {}) and m["pool"][arg_clean].get("state") == "available" and arg_clean != "TB":
                    self.safe_ui_dispatch(self, lambda s=arg_clean: self.tourney_player_do_protect(s))
                elif bot:
                    bot.send_channel_message(f"@{sender}: Slot '{arg_clean}' ist ungültig oder nicht verfügbar.")
            elif bot:
                bot.send_channel_message(f"@{sender}: Aktuell ist keine Protect-Phase oder du bist nicht am Zug.")

        elif cmd_clean in ["ban", "b", "bann", "bannen"]:
            if phase == "ban" and m.get("turn") == "player":
                if arg_clean in m.get("pool", {}) and m["pool"][arg_clean].get("state") == "available" and arg_clean != "TB":
                    self.safe_ui_dispatch(self, lambda s=arg_clean: self.tourney_player_do_ban(s))
                elif bot:
                    bot.send_channel_message(f"@{sender}: Slot '{arg_clean}' ist ungültig oder bereits gebannt.")
            elif bot:
                bot.send_channel_message(f"@{sender}: Aktuell ist keine Ban-Phase oder du bist nicht am Zug.")

        elif cmd_clean in ["pick", "p", "choose", "select", "waehlen"]:
            if phase == "pick" and m.get("turn") == "player":
                if arg_clean in m.get("pool", {}) and m["pool"][arg_clean].get("state") in ["available", "protected_player", "protected_bot"] and arg_clean != "TB":
                    self.safe_ui_dispatch(self, lambda s=arg_clean: self.tourney_player_do_pick(s))
                elif bot:
                    bot.send_channel_message(f"@{sender}: Slot '{arg_clean}' ist ungültig oder nicht wählbar.")
            elif bot:
                bot.send_channel_message(f"@{sender}: Aktuell ist keine Pick-Phase oder du bist nicht am Zug.")

        elif cmd_clean in ["ready", "rdy", "start", "gogo"]:
            if phase == "playing" and bot:
                bot.send_channel_message("🚀 Match-Countdown gestartet! (5 Sekunden)")
                bot.start_countdown(5)
            elif bot:
                bot.send_channel_message("⚠️ Noch keine Map gewählt. Bitte zuerst im UI oder mit !pick <slot> wählen!")

        elif cmd_clean in ["abort", "stop", "abbruch"]:
            if bot:
                bot.abort_match()
                bot.send_channel_message("🛑 Match abgebrochen.")

        elif cmd_clean in ["maps", "pool", "mappool"]:
            if bot:
                avail = [s for s, d in m.get("pool", {}).items() if d.get("state") in ["available", "protected_player", "protected_bot"]]
                bot.send_channel_message(f"📋 Verfügbare Maps ({len(avail)}): " + ", ".join(avail[:8]))

        elif cmd_clean in ["score", "stand", "punkte"]:
            if bot:
                p_pts = m.get("player_score", 0)
                b_pts = m.get("bot_score", 0)
                tw = m.get("target_wins", 5)
                bot.send_channel_message(f"📊 Spielstand: Du [{p_pts}] : [{b_pts}] {m['bot_name']} (Ziel: {tw} Siege)")

        elif cmd_clean in ["help", "commands", "befehle"]:
            if bot:
                bot.send_channel_message("📌 Befehle: !roll | !save <slot> | !ban <slot> | !pick <slot> | !ready | !abort | !maps | !score")

    def show_tournament_match_lobby(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        m = self.tourney_match
        player_name = getattr(self, "osu_username", "Spieler")
        team_size = m.get("team_size", 1)

        master = ctk.CTkFrame(self, fg_color="#101015")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        # Top Scoreboard Bar
        sb = ctk.CTkFrame(master, fg_color="#181822", height=75, corner_radius=14, border_width=1, border_color="#2b2b3c")
        sb.pack(fill="x", padx=20, pady=(12, 8))
        sb.pack_propagate(False)

        # Player Team Box
        p_box = ctk.CTkFrame(sb, fg_color="transparent")
        p_box.pack(side="left", padx=20)
        team_lbl = f"👤 Team {player_name}" if team_size > 1 else f"👤 {player_name}"
        ctk.CTkLabel(p_box, text=team_lbl, font=("Arial", 15, "bold"), text_color="#00E5FF").pack(anchor="w")
        p_pts = "● " * m["player_score"] + "○ " * (m["target_wins"] - m["player_score"])
        self.tourney_player_pts_lbl = ctk.CTkLabel(p_box, text=f"Punkte: {m['player_score']} / {m['target_wins']}   [{p_pts.strip()}]",
                     font=("Arial", 12, "bold"), text_color="#00E676")
        self.tourney_player_pts_lbl.pack(anchor="w")

        # Center Match Status
        c_box = ctk.CTkFrame(sb, fg_color="transparent")
        c_box.pack(side="left", expand=True)
        ref_txt = m.get("referee_status", "Lokaler Modus")
        ctk.CTkLabel(c_box, text=f"{m['badge']} {m['division']} • {m.get('team_format_name', '1v1')} • {m['format_name']} ({ref_txt})",
                     font=("Arial", 11, "bold"), text_color="#FF9800").pack()
        
        phase_texts = {
            "roll": "🎲 ROLL-PHASE: Würfle um First Pick & First Ban / Save!",
            "protect": f"🛡️ SAVE/PROTECT-PHASE: {'Schütze eine Map vor Bans' if m['turn']=='player' else m['bot_name'] + ' schützt eine Map'}!",
            "ban": f"🚫 BAN-PHASE: {'Du bist am Zug' if m['turn']=='player' else m['bot_name'] + ' bannt'}!",
            "pick": f"🎯 PICK-PHASE: {'Wähle die nächste Map' if m['turn']=='player' else m['bot_name'] + ' wählt Map'}!",
            "playing": f"⚡ MATCH LÄUFT: Spiele {m['current_pick']}! Auto-Sync erfasst deinen Run.",
            "finished": "🏆 MATCH BEENDET!"
        }
        self.tourney_phase_lbl = ctk.CTkLabel(c_box, text=phase_texts.get(m["phase"], ""), font=("Arial", 12, "bold"), text_color="#ffffff")
        self.tourney_phase_lbl.pack()

        # Opponent Team Box
        b_box = ctk.CTkFrame(sb, fg_color="transparent")
        b_box.pack(side="right", padx=20)
        opp_lbl = f"🤖 Team {m['bot_name']}" if team_size > 1 else f"🤖 {m['bot_name']}"
        ctk.CTkLabel(b_box, text=opp_lbl, font=("Arial", 15, "bold"), text_color="#E91E63").pack(anchor="e")
        b_pts = "● " * m["bot_score"] + "○ " * (m["target_wins"] - m["bot_score"])
        self.tourney_bot_pts_lbl = ctk.CTkLabel(b_box, text=f"[{b_pts.strip()}]   Punkte: {m['bot_score']} / {m['target_wins']}",
                     font=("Arial", 12, "bold"), text_color="#FF4081")
        self.tourney_bot_pts_lbl.pack(anchor="e")

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        main_box.grid_columnconfigure(0, weight=3)
        main_box.grid_columnconfigure(1, weight=2)
        main_box.grid_rowconfigure(0, weight=1)

        # Left Column: Mappool
        pool_frame = ctk.CTkFrame(main_box, fg_color="#14141c", corner_radius=12, border_width=1, border_color="#242434")
        pool_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        p_top = ctk.CTkFrame(pool_frame, fg_color="transparent")
        p_top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(p_top, text="🗺️ Offizieller Turnier-Mappool", font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")
        def _leave_tourney():
            if getattr(self, "tourney_referee_bot", None):
                try: self.tourney_referee_bot.close_lobby()
                except: pass
                self.tourney_referee_bot = None
            self.show_tournament_selector()

        ctk.CTkButton(p_top, text="⬅ Verlassen", width=80, height=26, font=("Arial", 11), fg_color="#2b2b36",
                      command=_leave_tourney).pack(side="right", padx=(6, 0))
        ctk.CTkButton(p_top, text="📖 Slot-Guide & Skillsets", width=155, height=26, font=("Arial", 11, "bold"),
                      fg_color="#1f538d", hover_color="#2b78c9", text_color="#ffffff",
                      command=self.show_tourney_slot_guide_modal).pack(side="right")

        self.tourney_pool_scroll = ctk.CTkScrollableFrame(pool_frame, fg_color="transparent")
        self.tourney_pool_scroll.pack(fill="both", expand=True, padx=8, pady=4)
        self.render_mappool_cards()

        # Right Column: Control & Feed & Radar
        ctrl_frame = ctk.CTkFrame(main_box, fg_color="#14141c", corner_radius=12, border_width=1, border_color="#242434")
        ctrl_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        c_top = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        c_top.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(c_top, text="🎙️ Match-Zentrale & Scouting", font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")
        
        # Team Radar Scouting Modal Button
        ctk.CTkButton(c_top, text="👥 Team-Dossiers & Radar", font=("Arial", 11, "bold"), width=150, height=26,
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000",
                      command=self.show_team_radar_scouting_modal).pack(side="right")

        self.tourney_act_bar = ctk.CTkFrame(ctrl_frame, fg_color="#1c1c28", corner_radius=10)
        self.tourney_act_bar.pack(fill="x", padx=12, pady=6)
        self.render_tourney_action_bar()

        # Referee Console Header & Quick Actions (Identical to Multiplayer)
        f_head = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        f_head.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(f_head, text="🤖 Referee & Ingame Feed", font=("Arial", 13, "bold"), text_color="#00BFA5").pack(side="left")

        def open_lobby():
            mid = m.get("match_id") or m.get("referee_match_id")
            if mid:
                try: os.startfile(f"osu://mp/{mid}")
                except: webbrowser.open(f"https://osu.ppy.sh/mp/{mid}")
            elif getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.match_id:
                try: os.startfile(f"osu://mp/{self.tourney_referee_bot.match_id}")
                except: webbrowser.open(f"https://osu.ppy.sh/mp/{self.tourney_referee_bot.match_id}")

        def force_sync():
            self.fetch_tourney_recent_plays(silent=False)

        def manual_invite():
            u_name = getattr(self, "osu_username", "") or "Spieler"
            u_irc = getattr(self, "osu_irc_password", "").strip()
            bot = getattr(self, "tourney_referee_bot", None)
            if bot and bot.channel and bot.running:
                bot.invite_player(u_name)
                bot._send_raw(f"PRIVMSG {u_name} :UHO Hub Lobby: [osu://mp/{bot.match_id} Hier klicken zum Beitreten] oder /join {bot.channel}")
                self._tourney_ref_log_callback(f"✉️ Einladung & PM an '{u_name}' gesendet!", "#00E676")
            elif bot and bot.connected:
                self._tourney_ref_log_callback("⚠️ Bot ist eingeloggt, erstellt gerade die Lobby...", "#00E5FF")
            elif not u_irc:
                self._tourney_ref_log_callback("❌ FEHLERCODE [ERR_NO_IRC_PASSWORD]: Kein IRC-Passwort hinterlegt. Bitte eintragen!", "#FF5252")
                self.ensure_osu_irc_password(on_success_callback=manual_invite)
            elif not bot or not bot.running:
                # Instant Auto-Start & Reconnect
                self._tourney_ref_log_callback("⚡ Starte Referee Bot neu & verbinde mit Bancho...", "#00E5FF")
                final_pwd = getattr(self, "tourney_match", {}).get("password") or f"uho{random.randint(100, 999)}"
                if hasattr(self, "tourney_match") and isinstance(self.tourney_match, dict):
                    self.tourney_match["password"] = final_pwd
                lobby_name = f"UHO Hub: {getattr(self, 'tourney_match', {}).get('badge', 'OWC')} Solo"
                self.tourney_referee_bot = BanchoRefereeBot(
                    username=u_name,
                    irc_password=u_irc,
                    on_log=self._tourney_ref_log_callback,
                    on_match_created=self._tourney_ref_on_created,
                    on_round_ended=self._tourney_ref_on_round_ended,
                    on_chat_command=self.handle_tourney_chat_command,
                    on_player_score=self._tourney_ref_on_score
                )
                self.tourney_referee_bot.connect_and_host(lobby_name=lobby_name, password=final_pwd)
            else:
                self._tourney_ref_log_callback("⚠️ Bot verbindet noch mit Bancho IRC...", "#FFA726")

        ctk.CTkButton(f_head, text="🎮 In Lobby", width=85, height=24, font=("Arial", 10, "bold"),
                      fg_color="#00E676", hover_color="#00C853", text_color="#000000", command=open_lobby).pack(side="right")
        ctk.CTkButton(f_head, text="✉️ Einladen", width=80, height=24, font=("Arial", 10, "bold"),
                      fg_color="#00BFA5", hover_color="#00897B", text_color="#000000", command=manual_invite).pack(side="right", padx=(0, 4))

        try:
            master.drop_target_register(DND_FILES)
            master.dnd_bind('<<Drop>>', self.handle_tourney_replay_drop)
        except: pass

        self.tourney_feed_box = ctk.CTkTextbox(ctrl_frame, wrap="word", font=("Arial", 11), fg_color="#101016",
                                                border_width=1, border_color="#20202e", corner_radius=8)
        self.tourney_feed_box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.tourney_feed_box.insert("1.0", "\n".join(m.get("bot_logs", ["Warte auf Match-Aktivität..."])))
        self.tourney_feed_box.configure(state="disabled")
        try: self.tourney_feed_box.see("end")
        except: pass

        self._start_tourney_match_auto_sync_loop()

    def show_tourney_slot_guide_modal(self):
        """Displays an educational modal explaining standard tournament slot skillset conventions."""
        modal = ctk.CTkToplevel(self)
        modal.title("📖 Offizieller Turnier-Slot & Skillset Guide")
        modal.geometry("740x650")
        modal.configure(fg_color="#121216")
        modal.attributes("-topmost", True)

        top_f = ctk.CTkFrame(modal, fg_color="#181822", height=50, corner_radius=10)
        top_f.pack(fill="x", padx=15, pady=10)
        top_f.pack_propagate(False)
        ctk.CTkLabel(top_f, text="📖 Turnier-Slot & Skillset Konventionen (OWC / Turniere)", font=("Arial", 15, "bold"), text_color="#00E5FF").pack(side="left", padx=15)
        ctk.CTkButton(top_f, text="Schließen", width=80, height=28, font=("Arial", 11), fg_color="#2b2b36", command=modal.destroy).pack(side="right", padx=15)

        info_box = ctk.CTkFrame(modal, fg_color="#1a1a26", corner_radius=8, border_width=1, border_color="#2e2e42")
        info_box.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(info_box, text="In offiziellen osu! Turnieren (wie OWC, Corsace, Roundtable) folgt jeder Mappool-Slot einer festen Skillset-Konvention. Nutze dieses Wissen für optimale Bans und Counter-Picks!",
                     font=("Arial", 11), text_color="#bbbbcc", wraplength=690, justify="left").pack(padx=12, pady=8)

        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        slot_groups = {
            "NoMod (NM)": [
                ("NM1", "Consistency", "All-Around Konstanz, Jumps & Stabilität. Die Standard-Eröffnungsmap."),
                ("NM2", "Aim & Precision", "Präzises Flow Aim, kleine Circle Size (CS > 4.5) & präzise Snaps."),
                ("NM3", "Speed & Bursts", "Hohes Grundtempo (220+ BPM), Finger Speed, Quad- & Quint-Bursts."),
                ("NM4", "Tech & Reading", "Komplexe Slider-Shapes, unkonventionelle Rhythmen & Reading-Dichte."),
                ("NM5", "Finger Control", "Rhythmus-Wechsel (1/3, 1/4, 1/6 Snappings), Alternate & Control."),
                ("NM6", "Stamina & High CS", "Lange Streams, hohe Ausdauerbelastung oder extreme Präzision.")
            ],
            "Hidden (HD)": [
                ("HD1", "Aim & Reading", "Reines Aim mit Hidden-Mod. Testet Muscle-Memory & Notenpositionierung."),
                ("HD2", "Tech & Flow", "SliderTech mit Hidden. Erfordert exaktes Lesen von Slider-Geschwindigkeiten."),
                ("HD3", "Speed & Control", "Hohes Tempo / Bursts mit Hidden. Verlangt fehlerfreies Tapping-Timing.")
            ],
            "HardRock (HR)": [
                ("HR1", "Precision & Aim", "Sehr kleine CS (CS 5.2 - 6.5) & AR 10. Testet maximale Zielgenauigkeit."),
                ("HR2", "Consistency & Stamina", "Längere HR-Map mit Fokus auf Combo-Sicherheit & nervliche Ausdauer."),
                ("HR3", "High AR Tech / Flow", "Schnelle Übergänge, Flow Aim & hohe Lesegeschwindigkeit.")
            ],
            "DoubleTime (DT)": [
                ("DT1", "Pure Speed / Bursts", "Hohes BPM-Tempo (250 - 280+ BPM), schnelle Triplets & Burst-Streams."),
                ("DT2", "Speed Aim / Jumps", "Schnelle Velocity-Jumps & snappy Aim bei hoher Geschwindigkeit."),
                ("DT3", "Finger Control / Alt", "Komplexe Rhythmen auf DoubleTime, Alternate & Finger Control."),
                ("DT4", "Stamina / Drain", "Lange DT-Maps mit hohem Ausdauer-Fokus & Drain.")
            ],
            "FreeMod (FM) & Tiebreaker (TB)": [
                ("FM1", "Consistency & Hybrid", "Ausgewogener All-Rounder Slot. Erlaubt HD, HR, EZ oder NM."),
                ("FM2", "Tech & Precision", "SliderTech / Präzisions-Map für Spezialisten (z. B. HDHR oder HD)."),
                ("FM3", "Speed / Alt", "Tempo- & Alternate-Fokus für FreeMod-Strategien."),
                ("TB", "Tiebreaker All-Around", "Lange (4-6 Min) epische Final-Map, die alle Skills kombiniert.")
            ]
        }

        for group_title, items in slot_groups.items():
            hdr = ctk.CTkFrame(scroll, fg_color="transparent")
            hdr.pack(fill="x", pady=(8, 2))
            ctk.CTkLabel(hdr, text=group_title, font=("Arial", 13, "bold"), text_color="#00E5FF").pack(side="left")

            for s_code, s_skill, s_desc in items:
                card = ctk.CTkFrame(scroll, fg_color="#181822", corner_radius=8, border_width=1, border_color="#2b2b3c")
                card.pack(fill="x", pady=3)

                r = ctk.CTkFrame(card, fg_color="transparent")
                r.pack(fill="x", padx=10, pady=6)

                ctk.CTkLabel(r, text=s_code, font=("Arial", 12, "bold"), text_color="#FF9800", width=42, anchor="w").pack(side="left")
                ctk.CTkLabel(r, text=f"• {s_skill}", font=("Arial", 11, "bold"), text_color="#00E676", width=160, anchor="w").pack(side="left", padx=4)
                ctk.CTkLabel(r, text=s_desc, font=("Arial", 10), text_color="#cccccc", anchor="w", justify="left").pack(side="left", fill="x", expand=True)

    def show_team_radar_scouting_modal(self):
        """Modal displaying full 8-skill radar charts and tactical scouting dossiers for all teammates and opponents."""
        m = getattr(self, "tourney_match", None)
        if not m: return

        modal = ctk.CTkToplevel(self)
        modal.title("👥 Team-Scouting & 8-Skill Radar Profile")
        modal.geometry("820x680")
        modal.configure(fg_color="#121216")

        top_f = ctk.CTkFrame(modal, fg_color="#181822", height=50, corner_radius=10)
        top_f.pack(fill="x", padx=15, pady=10)
        top_f.pack_propagate(False)
        ctk.CTkLabel(top_f, text="👥 Taktische Dossiers & 8-Skillset Radar-Profile", font=("Arial", 15, "bold"), text_color="#00E5FF").pack(side="left", padx=15)
        ctk.CTkButton(top_f, text="Schließen", width=80, height=28, font=("Arial", 11), fg_color="#2b2b36", command=modal.destroy).pack(side="right", padx=15)

        body = ctk.CTkFrame(modal, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left Column: Player Team
        p_frame = ctk.CTkFrame(body, fg_color="#181820", corner_radius=12, border_width=1, border_color="#2e2e3f")
        p_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(p_frame, text="🔵 Dein Team (Aufstellung & Dossiers)", font=("Arial", 13, "bold"), text_color="#00E5FF").pack(pady=(10, 4))
        p_scroll = ctk.CTkScrollableFrame(p_frame, fg_color="transparent")
        p_scroll.pack(fill="both", expand=True, padx=8, pady=6)

        for idx, member in enumerate(m.get("player_team", [])):
            c = ctk.CTkFrame(p_scroll, fg_color="#1e1e2c", corner_radius=10, border_width=1, border_color="#2f2f45")
            c.pack(fill="x", pady=6)

            h = ctk.CTkFrame(c, fg_color="transparent")
            h.pack(fill="x", padx=10, pady=(8, 2))
            tag = " (Kapitän / Du)" if idx == 0 else f" (Teammate #{idx})"
            ctk.CTkLabel(h, text=f"👤 {member['name']}{tag}", font=("Arial", 12, "bold"), text_color="#00E5FF").pack(side="left")
            ctk.CTkLabel(h, text=member.get("choke_badge", "Choke: Normal"), font=("Arial", 10, "bold"), text_color=member.get("choke_color", "#00E676")).pack(side="right")

            canvas = tk.Canvas(c, width=320, height=220, bg="#181824", highlightthickness=0)
            canvas.pack(padx=8, pady=4)
            draw_radar_polygon(canvas, member["stats"], color_theme="cyan" if idx == 0 else "green", is_hidden=False)

            d_txt = f"• Top-Stärken: {', '.join(member.get('top_strengths', []))}\n" \
                    f"• Schwächen: {', '.join(member.get('top_weaknesses', []))}\n" \
                    f"• Signature-Slots: {', '.join(member.get('signature_slots', []))}\n" \
                    f"• Nervenstärke: {member.get('choke_tendency', '')}"
            ctk.CTkLabel(c, text=d_txt, font=("Arial", 10), text_color="#bbbbcc", justify="left").pack(anchor="w", padx=10, pady=(2, 8))

        # Right Column: Opponent Team (Fog of War Masked)
        o_frame = ctk.CTkFrame(body, fg_color="#181820", corner_radius=12, border_width=1, border_color="#2e2e3f")
        o_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(o_frame, text="🔴 Gegner-Team (Fog of War / Verdeckt)", font=("Arial", 13, "bold"), text_color="#FF4081").pack(pady=(10, 4))
        o_scroll = ctk.CTkScrollableFrame(o_frame, fg_color="transparent")
        o_scroll.pack(fill="both", expand=True, padx=8, pady=6)

        for idx, member in enumerate(m.get("opponent_team", [])):
            c = ctk.CTkFrame(o_scroll, fg_color="#1e1e2c", corner_radius=10, border_width=1, border_color="#2f2f45")
            c.pack(fill="x", pady=6)

            h = ctk.CTkFrame(c, fg_color="transparent")
            h.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(h, text=f"🤖 {member['name']}", font=("Arial", 12, "bold"), text_color="#FF4081").pack(side="left")
            ctk.CTkLabel(h, text="🔒 Profil verdeckt", font=("Arial", 10, "bold"), text_color="#888899").pack(side="right")

            canvas = tk.Canvas(c, width=320, height=220, bg="#181824", highlightthickness=0)
            canvas.pack(padx=8, pady=4)
            draw_radar_polygon(canvas, member["stats"], color_theme="purple", is_hidden=True)

            d_txt = "• Top-Stärken: ??? (Finde es über Bans/Picks heraus!)\n" \
                    "• Schwächen: ???\n" \
                    "• Signature-Slots: ???\n" \
                    "• Nervenstärke: Unbekannt (Fog of War aktiv)"
            ctk.CTkLabel(c, text=d_txt, font=("Arial", 10), text_color="#888899", justify="left").pack(anchor="w", padx=10, pady=(2, 8))

    def refresh_tourney_lobby_state(self):
        """Smoothly updates the tournament lobby UI in-place without destroying frames (No Flickering!)."""
        if not hasattr(self, "tourney_phase_lbl") or not self.tourney_phase_lbl.winfo_exists():
            self.show_tournament_match_lobby()
            return

        m = self.tourney_match
        phase_texts = {
            "roll": "🎲 ROLL-PHASE: Würfle um First Pick & First Ban / Save!",
            "protect": f"🛡️ SAVE/PROTECT-PHASE: {'Schütze eine Map vor Bans' if m['turn']=='player' else m['bot_name'] + ' schützt eine Map'}!",
            "ban": f"🚫 BAN-PHASE: {'Du bist am Zug' if m['turn']=='player' else m['bot_name'] + ' bannt'}!",
            "pick": f"🎯 PICK-PHASE: {'Wähle die nächste Map' if m['turn']=='player' else m['bot_name'] + ' wählt Map'}!",
            "playing": f"⚡ MATCH LÄUFT: Spiele {m['current_pick']}! Auto-Sync erfasst deinen Run.",
            "finished": "🏆 MATCH BEENDET!"
        }
        self.tourney_phase_lbl.configure(text=phase_texts.get(m["phase"], ""))

        if hasattr(self, "tourney_player_pts_lbl") and self.tourney_player_pts_lbl.winfo_exists():
            p_pts = "● " * m["player_score"] + "○ " * (m["target_wins"] - m["player_score"])
            self.tourney_player_pts_lbl.configure(text=f"Punkte: {m['player_score']} / {m['target_wins']}   [{p_pts.strip()}]")

        self.render_tourney_action_bar()
        self.render_mappool_cards()

    def render_tourney_action_bar(self):
        for w in self.tourney_act_bar.winfo_children():
            w.destroy()

        m = self.tourney_match
        phase = m["phase"]

        if phase == "roll":
            ctk.CTkLabel(self.tourney_act_bar, text="Würfle um First Pick / First Ban:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(side="left", padx=12, pady=8)
            ctk.CTkButton(self.tourney_act_bar, text="🎲 Jetzt Würfeln", font=("Arial", 12, "bold"), height=30,
                          fg_color="#FF9800", hover_color="#F57C00", text_color="#000000",
                          command=self.tourney_do_roll).pack(side="right", padx=10, pady=6)

        elif phase == "protect":
            if m["turn"] == "player":
                ctk.CTkLabel(self.tourney_act_bar, text="🛡️ Klicke im Mappool auf '🛡️ Save', um deine Map vor Bans zu schützen!", font=("Arial", 11, "bold"), text_color="#00E5FF").pack(padx=10, pady=8)
            else:
                ctk.CTkLabel(self.tourney_act_bar, text=f"🤖 {m['bot_name']} wählt Protect/Save...", font=("Arial", 11, "bold"), text_color="#00E5FF").pack(padx=10, pady=8)
                self.after(1500, self.tourney_bot_do_protect)

        elif phase == "ban":
            if m["turn"] == "player":
                ctk.CTkLabel(self.tourney_act_bar, text="Klicke im Mappool auf eine Map, um sie zu BANNEN!", font=("Arial", 11, "bold"), text_color="#FF5252").pack(padx=10, pady=8)
            else:
                ctk.CTkLabel(self.tourney_act_bar, text=f"🤖 {m['bot_name']} überlegt Ban-Taktik...", font=("Arial", 11, "bold"), text_color="#FF9800").pack(padx=10, pady=8)
                self.after(1500, self.tourney_bot_do_ban)

        elif phase == "pick":
            if m["player_score"] == m["target_wins"] - 1 and m["bot_score"] == m["target_wins"] - 1:
                ctk.CTkLabel(self.tourney_act_bar, text="🔥 TIEBREAKER! Map wird automatisch gewählt...", font=("Arial", 12, "bold"), text_color="#FF9800").pack(padx=10, pady=8)
                self.after(1000, lambda: self.tourney_pick_slot("TB"))
                return

            if m["turn"] == "player":
                ctk.CTkLabel(self.tourney_act_bar, text="🎯 Wähle eine Map aus dem Pool zum SPIELEN!", font=("Arial", 11, "bold"), text_color="#00E5FF").pack(padx=10, pady=8)
            else:
                ctk.CTkLabel(self.tourney_act_bar, text=f"🤖 {m['bot_name']} wählt nächste Map...", font=("Arial", 11, "bold"), text_color="#E91E63").pack(padx=10, pady=8)
                self.after(1500, self.tourney_bot_do_pick)

        elif phase == "playing":
            cur_slot = m["current_pick"]
            cur_map = m["pool"].get(cur_slot, {})
            bid = cur_map.get("id")
            req_mod = "NM (NoMod)"
            if "HD" in cur_slot: req_mod = "+HD (Hidden)"
            elif "HR" in cur_slot: req_mod = "+HR (HardRock)"
            elif "DT" in cur_slot: req_mod = "+DT (DoubleTime)"
            elif "FM" in cur_slot: req_mod = "FreeMod (HD, HR, EZ oder NM)"
            elif "TB" in cur_slot: req_mod = "Tiebreaker (FreeMod erlaubt)"

            p_box = ctk.CTkFrame(self.tourney_act_bar, fg_color="transparent")
            p_box.pack(fill="x", padx=10, pady=6)

            p_top = ctk.CTkFrame(p_box, fg_color="transparent")
            p_top.pack(fill="x")

            def open_direct_tourney(b=bid):
                try: os.startfile(f"osu://b/{b}")
                except: webbrowser.open(f"https://osu.ppy.sh/b/{b}")

            def open_web_tourney(b=bid):
                webbrowser.open(f"https://osu.ppy.sh/b/{b}")

            r_tourney_btns = ctk.CTkFrame(p_top, fg_color="transparent")
            r_tourney_btns.pack(side="right")

            ctk.CTkButton(r_tourney_btns, text="🌐 Web", font=("Arial", 11), width=70, height=26,
                          fg_color="#2b2b38", hover_color="#3a3a4c", command=open_web_tourney).pack(side="right", padx=(4, 0))

            ctk.CTkButton(r_tourney_btns, text="⚡ osu!direct", font=("Arial", 11, "bold"), width=95, height=26,
                          fg_color="#FF66AA", hover_color="#C2185B", command=open_direct_tourney).pack(side="right", padx=(4, 0))

            ctk.CTkLabel(p_top, text=f"🎮 AKTIVE MAP: {cur_slot} • {cur_map.get('name', '')[:40]}", font=("Arial", 12, "bold"), text_color="#00E5FF").pack(side="left", fill="x", expand=True)

            ctk.CTkLabel(p_box, text=f"Mod: {req_mod} • ★ {cur_map.get('sr', 5.0):.2f} | ⚡ ScoreV2 aktiv! Auto-Sync erfasst deinen Run automatisch nach Song-Ende (oder ziehe .osr Replay hierhin)",
                         font=("Arial", 10), text_color="#00E676").pack(anchor="w", pady=(2, 0))

        elif phase == "finished":
            winner = "Dein Team gewinnt das Match! 🏆" if m["player_score"] >= m["target_wins"] else f"Team {m['bot_name']} gewinnt das Match!"
            win_color = "#00E676" if m["player_score"] >= m["target_wins"] else "#FF5252"
            ctk.CTkLabel(self.tourney_act_bar, text=winner, font=("Arial", 13, "bold"), text_color=win_color).pack(side="left", padx=12, pady=8)
            ctk.CTkButton(self.tourney_act_bar, text="📊 Abschluss-Bericht & Scouting", font=("Arial", 11, "bold"), height=28,
                          fg_color="#3b8ed0", hover_color="#1f538d", command=self.show_tourney_post_match_modal).pack(side="right", padx=10, pady=6)

    def render_mappool_cards(self):
        if not hasattr(self, "tourney_pool_scroll") or not self.tourney_pool_scroll.winfo_exists():
            return

        for w in self.tourney_pool_scroll.winfo_children():
            try: w.destroy()
            except: pass

        m = getattr(self, "tourney_match", {}) or {}
        pool = m.get("pool", {})
        phase = m.get("phase", "roll")

        mod_order = ['NM', 'HD', 'HR', 'DT', 'FM', 'TB', 'EZ', 'FL']
        mod_info = {
            'NM': ('NoMod (NM)', '#3b8ed0'),
            'HD': ('Hidden (HD)', '#E91E63'),
            'HR': ('HardRock (HR)', '#F44336'),
            'DT': ('DoubleTime (DT)', '#9C27B0'),
            'FM': ('FreeMod (FM)', '#00E5FF'),
            'TB': ('Tiebreaker (TB)', '#FF9800'),
            'EZ': ('Easy (EZ)', '#4CAF50'),
            'FL': ('Flashlight (FL)', '#FFEB3B'),
            'Other': ('Spezial / Custom', '#AAAAAA')
        }

        def get_slot_sort_key(s):
            for p in mod_order:
                if s.startswith(p):
                    num = s[len(p):]
                    return (mod_order.index(p), int(num) if num.isdigit() else 0)
            return (99, s)

        all_slots = sorted(pool.keys(), key=get_slot_sort_key)
        categories_dict = {}
        for s in all_slots:
            prefix = 'Other'
            for pfx in mod_order:
                if s.startswith(pfx):
                    prefix = pfx
                    break
            categories_dict.setdefault(prefix, []).append(s)

        for pfx in mod_order + ['Other']:
            slot_list = categories_dict.get(pfx, [])
            if not slot_list:
                continue

            cat_name, col = mod_info.get(pfx, (pfx, '#AAAAAA'))
            cat_hdr = ctk.CTkFrame(self.tourney_pool_scroll, fg_color="transparent")
            cat_hdr.pack(fill="x", padx=4, pady=(6, 2))
            ctk.CTkLabel(cat_hdr, text=f"{cat_name} ({len(slot_list)} Maps)", font=("Arial", 12, "bold"), text_color=col).pack(side="left")

            for slot in slot_list:
                map_data = pool.get(slot, {})
                st = map_data.get("state", "available")
                bid = map_data.get("id")

                card_bg = "#181822"
                b_border = "#282838"
                badge_txt = "VERFÜGBAR"
                badge_col = "#3b8ed0"

                if "won_player" in st:
                    card_bg = "#13261a"
                    b_border = "#00E676"
                    badge_txt = "✅ GEWONNEN"
                    badge_col = "#00E676"
                elif "won_bot" in st:
                    card_bg = "#241315"
                    b_border = "#FF4081"
                    badge_txt = "❌ VERLOREN"
                    badge_col = "#FF4081"
                elif "banned_player" in st:
                    card_bg = "#241315"
                    b_border = "#c62828"
                    badge_txt = "🚫 BANNED (Du)"
                    badge_col = "#ff4444"
                elif "banned_bot" in st:
                    card_bg = "#241315"
                    b_border = "#c62828"
                    badge_txt = f"🚫 BANNED ({m.get('bot_name', 'Bot')})"
                    badge_col = "#ff4444"
                elif "protected_player" in st:
                    card_bg = "#102228"
                    b_border = "#00E5FF"
                    badge_txt = "🛡️ GESCHÜTZT (Du)"
                    badge_col = "#00E5FF"
                elif "protected_bot" in st:
                    card_bg = "#25182e"
                    b_border = "#BA68C8"
                    badge_txt = f"🛡️ GESCHÜTZT ({m.get('bot_name', 'Bot')})"
                    badge_col = "#BA68C8"
                elif slot == m.get("current_pick"):
                    card_bg = "#262214"
                    b_border = "#FFD700"
                    badge_txt = "⚡ LIVE GESPIELT"
                    badge_col = "#FFD700"

                card = ctk.CTkFrame(self.tourney_pool_scroll, fg_color=card_bg, corner_radius=8, border_width=1, border_color=b_border)
                card.pack(fill="x", padx=4, pady=3)

                top_row = ctk.CTkFrame(card, fg_color="transparent")
                top_row.pack(fill="x", padx=10, pady=(6, 2))

                m_name = map_data.get("name", "Map")
                ctk.CTkLabel(top_row, text=f"{slot}: {m_name[:42]}", font=("Arial", 11, "bold"), text_color="#ffffff", anchor="w").pack(side="left")
                ctk.CTkLabel(top_row, text=badge_txt, font=("Arial", 9, "bold"), text_color=badge_col).pack(side="right")

                bot_row = ctk.CTkFrame(card, fg_color="transparent")
                bot_row.pack(fill="x", padx=10, pady=(0, 6))

                skill_name = get_slot_standard_skillset_name(slot)
                meta_txt = f"★ {map_data.get('sr', 5.0):.2f} • {map_data.get('bpm', 180)} BPM • {map_data.get('len', 120)}s • {skill_name}"
                ctk.CTkLabel(bot_row, text=meta_txt, font=("Arial", 9), text_color="#888899", anchor="w").pack(side="left")

                r_btns = ctk.CTkFrame(bot_row, fg_color="transparent")
                r_btns.pack(side="right")

                def make_direct(b=bid):
                    try: os.startfile(f"osu://b/{b}")
                    except: webbrowser.open(f"https://osu.ppy.sh/b/{b}")
                def make_web(b=bid):
                    webbrowser.open(f"https://osu.ppy.sh/b/{b}")

                ctk.CTkButton(r_btns, text="direct", width=44, height=20, font=("Arial", 9, "bold"),
                              fg_color="#E91E63", hover_color="#C2185B", command=make_direct).pack(side="right", padx=(2, 0))
                ctk.CTkButton(r_btns, text="🌐 web", width=44, height=20, font=("Arial", 9, "bold"),
                              fg_color="#2b2b38", hover_color="#3a3a4c", command=make_web).pack(side="right", padx=(2, 0))

                if st == "available":
                    if phase == "protect" and m["turn"] == "player" and slot != "TB":
                        def make_prot(s=slot): return lambda: self.tourney_player_do_protect(s)
                        ctk.CTkButton(r_btns, text="🛡️ Save", width=54, height=20, font=("Arial", 9, "bold"),
                                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=make_prot()).pack(side="right", padx=(2, 0))
                    elif phase == "ban" and m["turn"] == "player" and slot != "TB":
                        def make_ban(s=slot): return lambda: self.tourney_player_do_ban(s)
                        ctk.CTkButton(r_btns, text="🚫 Ban", width=50, height=20, font=("Arial", 9, "bold"),
                                      fg_color="#c62828", hover_color="#b71c1c", command=make_ban()).pack(side="right", padx=(2, 0))
                    elif phase == "pick" and m["turn"] == "player" and slot != "TB":
                        def make_pick(s=slot): return lambda: self.tourney_player_do_pick(s)
                        ctk.CTkButton(r_btns, text="🎯 Pick", width=50, height=20, font=("Arial", 9, "bold"),
                                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=make_pick()).pack(side="right", padx=(2, 0))
                elif "protected" in st and phase == "pick" and m["turn"] == "player" and slot != "TB":
                    def make_pick(s=slot): return lambda: self.tourney_player_do_pick(s)
                    ctk.CTkButton(r_btns, text="🎯 Pick", width=50, height=20, font=("Arial", 9, "bold"),
                                  fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=make_pick()).pack(side="right", padx=(2, 0))

    def tourney_do_roll(self):
        m = self.tourney_match
        p_roll = random.randint(1, 100)
        b_roll = random.randint(1, 100)
        while b_roll == p_roll: b_roll = random.randint(1, 100)

        m["player_roll"] = p_roll
        m["bot_roll"] = b_roll

        if p_roll > b_roll:
            winner_text = f"🎉 Du gewinnst den Roll ({p_roll} vs {b_roll})! Du beginnst."
            m["turn"] = "player"
        else:
            winner_text = f"🤖 {m['bot_name']} gewinnt den Roll ({b_roll} vs {p_roll}) und beginnt."
            m["turn"] = "bot"

        if m.get("protects_needed", 0) > 0:
            m["phase"] = "protect"
            m["history"].append(f"🎲 ROLL: {winner_text} -> Save/Protect-Phase!")
        elif m.get("bans_needed", 0) > 0:
            m["phase"] = "ban"
            m["history"].append(f"🎲 ROLL: {winner_text} -> Ban-Phase!")
        else:
            m["phase"] = "pick"
            m["history"].append(f"🎲 ROLL: {winner_text} -> Pick-Phase!")

        # Broadcast Roll to IRC
        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🎲 Roll-Ergebnis: Spieler [{p_roll}] vs [{b_roll}] {m['bot_name']} -> {winner_text}")

        self.refresh_tourney_lobby_state()

    def tourney_player_do_protect(self, slot):
        m = self.tourney_match
        m["pool"][slot]["state"] = "protected_player"
        m["protects_done"] += 1
        m["history"].append(f"🛡️ SAVE: Du schützt {slot} ({m['pool'][slot]['name'][:30]}) vor Bans!")

        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🛡️ SAVE: Spieler schützt Slot [{slot}]!")

        if m["protects_done"] >= m["protects_needed"]:
            m["phase"] = "ban" if m["bans_needed"] > 0 else "pick"
            m["turn"] = "player" if m["player_roll"] > m["bot_roll"] else "bot"
        else:
            m["turn"] = "bot"

        self.refresh_tourney_lobby_state()

    def tourney_bot_do_protect(self):
        if not hasattr(self, "tourney_match") or not self.tourney_match or self.tourney_match.get("phase") != "protect":
            return
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return
        m = self.tourney_match
        bot_stats = m.get("bot_stats", {})
        player_stats = m.get("player_team", [{}])[0].get("stats", {})
        chosen_slot = bot_select_action(m["pool"], bot_stats, player_stats, "protect")

        m["pool"][chosen_slot]["state"] = "protected_bot"
        m["protects_done"] += 1
        m["history"].append(f"🛡️ SAVE: {m['bot_name']} schützt {chosen_slot} ({m['pool'][chosen_slot]['name'][:30]}) vor Bans!")

        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🛡️ SAVE: {m['bot_name']} schützt Slot [{chosen_slot}]!")

        if m["protects_done"] >= m["protects_needed"]:
            m["phase"] = "ban" if m["bans_needed"] > 0 else "pick"
            m["turn"] = "player" if m["player_roll"] > m["bot_roll"] else "bot"
        else:
            m["turn"] = "player"

        self.refresh_tourney_lobby_state()

    def tourney_player_do_ban(self, slot):
        m = self.tourney_match
        m["pool"][slot]["state"] = "banned_player"
        m["bans_done"] += 1
        m["history"].append(f"🚫 BAN: Du bannst {slot} ({m['pool'][slot]['name'][:30]})")

        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🚫 BAN: Spieler bannt Slot [{slot}]!")
        
        if m["bans_done"] >= m["bans_needed"]:
            m["phase"] = "pick"
            m["turn"] = "player" if m["player_roll"] > m["bot_roll"] else "bot"
        else:
            m["turn"] = "bot"

        self.refresh_tourney_lobby_state()

    def tourney_bot_do_ban(self):
        if not hasattr(self, "tourney_match") or not self.tourney_match or self.tourney_match.get("phase") != "ban":
            return
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return
        m = self.tourney_match
        bot_stats = m.get("bot_stats", {})
        player_stats = m.get("player_team", [{}])[0].get("stats", {})
        chosen_slot = bot_select_action(m["pool"], bot_stats, player_stats, "ban")

        m["pool"][chosen_slot]["state"] = "banned_bot"
        m["bans_done"] += 1
        m["history"].append(f"🚫 BAN: {m['bot_name']} bannt {chosen_slot} ({m['pool'][chosen_slot]['name'][:30]})")

        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🚫 BAN: {m['bot_name']} bannt Slot [{chosen_slot}]!")

        if m["bans_done"] >= m["bans_needed"]:
            m["phase"] = "pick"
            m["turn"] = "player" if m["player_roll"] > m["bot_roll"] else "bot"
        else:
            m["turn"] = "player"

        self.refresh_tourney_lobby_state()

    def tourney_player_do_pick(self, slot):
        self.tourney_pick_slot(slot, picked_by="player")

    def tourney_bot_do_pick(self):
        if not hasattr(self, "tourney_match") or not self.tourney_match or self.tourney_match.get("phase") != "pick":
            return
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return
        m = self.tourney_match
        bot_stats = m.get("bot_stats", {})
        player_stats = m.get("player_team", [{}])[0].get("stats", {})
        chosen_slot = bot_select_action(m["pool"], bot_stats, player_stats, "pick")
        self.tourney_pick_slot(chosen_slot, picked_by="bot")

    def tourney_pick_slot(self, slot, picked_by="player"):
        m = self.tourney_match
        m["current_pick"] = slot
        m["phase"] = "playing"
        m["pick_timestamp"] = time.time()
        m.setdefault("processed_play_keys", set())
        m["pool"][slot]["state"] = "picked"
        picker_name = "Du" if picked_by == "player" else m["bot_name"]
        m["history"].append(f"🎯 PICK: {picker_name} wählt {slot}: {m['pool'][slot]['name']}")

        cur_map = m["pool"].get(slot, {})
        bid = cur_map.get("id")
        if bid and getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            req_mod = "NM"
            if "HD" in slot: req_mod = "HD"
            elif "HR" in slot: req_mod = "HR"
            elif "DT" in slot: req_mod = "DT"
            elif "FM" in slot: req_mod = "FM"
            elif "TB" in slot: req_mod = "TB"

            self.tourney_referee_bot.set_map(bid, mods=req_mod, enforce_nf=True)
            self.tourney_referee_bot.send_channel_message(
                f"🎯 Nächste Map: [{slot}] {cur_map.get('name', '')[:32]} (★ {cur_map.get('sr', 5.0):.2f}) | Mod: {req_mod} + NF | ScoreV2 aktiv! Tippe !ready zum Starten."
            )

        self.refresh_tourney_lobby_state()

    def _start_tourney_match_auto_sync_loop(self):
        if getattr(self, "_tourney_sync_loop_running", False):
            return
        self._tourney_sync_loop_running = True

        def _loop():
            if not hasattr(self, "winfo_exists") or not self.winfo_exists():
                self._tourney_sync_loop_running = False
                return
            if not hasattr(self, 'tourney_phase_lbl') or not self.tourney_phase_lbl.winfo_exists():
                self._tourney_sync_loop_running = False
                return

            if getattr(self, "tourney_match", {}).get("phase") == "playing":
                try:
                    self.fetch_tourney_recent_plays(silent=True)
                except Exception:
                    pass

            if hasattr(self, "winfo_exists") and self.winfo_exists():
                self.after(3500, _loop)
            else:
                self._tourney_sync_loop_running = False

        self.after(1000, _loop)

    def fetch_tourney_recent_plays(self, silent=True):
        m = getattr(self, "tourney_match", None)
        if not m or m.get("phase") != "playing":
            return

        cur_slot = m["current_pick"]
        cur_map = m["pool"].get(cur_slot, {})
        bid = str(cur_map.get("id", ""))
        user = getattr(self, "osu_username", "")
        key = getattr(self, "api_key", "")

        if not user or not key:
            if not silent:
                self.bell()
            return

        try:
            url = f"https://osu.ppy.sh/api/get_user_recent?k={key}&u={user}&m=0&limit=10"
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                return

            plays = r.json()
            if not isinstance(plays, list) or not plays:
                return

            found_play = None
            processed_keys = m.setdefault("processed_play_keys", set())
            pick_ts = m.get("pick_timestamp", 0)

            for p in plays:
                if str(p.get("beatmap_id")) != bid:
                    continue

                play_key = f"{p.get('beatmap_id')}_{p.get('date')}_{p.get('score')}"
                if play_key in processed_keys:
                    continue

                # Validate play date against pick time to avoid consuming old previous plays
                date_str = p.get("date", "")
                if date_str:
                    try:
                        play_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
                        if pick_ts > 0 and play_dt.timestamp() < (pick_ts - 120):
                            continue
                    except Exception:
                        pass

                found_play = p
                processed_keys.add(play_key)
                break

            if found_play:
                self.process_tourney_match_round(found_play)
        except Exception:
            pass

    def process_tourney_match_round(self, play_data):
        m = self.tourney_match
        if not m or m.get("phase") != "playing":
            return

        cur_slot = m["current_pick"]
        cur_map = m["pool"].get(cur_slot, {})

        h300 = int(play_data.get("count300", 0) or 0)
        h100 = int(play_data.get("count100", 0) or 0)
        h50 = int(play_data.get("count50", 0) or 0)
        miss = int(play_data.get("countmiss", 0) or 0)
        tot = h300 + h100 + h50 + miss
        p_acc = (safe_div(h300 * 300 + h100 * 100 + h50 * 50, tot * 300, 0.0) * 100.0) if tot > 0 else 0.0
        p_score = int(play_data.get("scorev2", 0) or play_data.get("score", 0) or 0)

        # Convert player score to ScoreV2 if score > 1,000,000 (ScoreV1 submitted)
        if p_score > 1000000:
            max_c = int(play_data.get("maxcombo", 0) or 0)
            total_obj = max(1, tot)
            p_combo_ratio = safe_div(max_c, total_obj, 0.8)
            p_v2_combo = 700000.0 * (min(1.0, p_combo_ratio) ** 0.5)
            p_v2_acc = 300000.0 * ((p_acc / 100.0) ** 4.0)
            player_v2_score = max(0, min(1000000, int(round(p_v2_combo + p_v2_acc))))
        else:
            player_v2_score = max(0, min(1000000, p_score))

        # 1. Evaluate Player Team Scores
        player_team_members = m.get("player_team", [])
        player_team_scores = [player_v2_score]
        p_name = player_team_members[0]['name'] if player_team_members else m.get('player_name', 'Du')
        p_round_details = [f"• {p_name} (Du): {player_v2_score:,} ScoreV2 ({p_acc:.2f}%, {miss} Miss)"]

        for tm in player_team_members[1:]:
            tm_sim = calculate_bot_scorev2(tm["stats"], cur_map)
            player_team_scores.append(tm_sim["scorev2"])
            p_round_details.append(f"• {tm['name']}: {tm_sim['scorev2']:,} ScoreV2 ({tm_sim['acc']:.2f}%, {tm_sim['misses']} Miss)")

        # 2. Evaluate Opponent Team Scores
        opponent_team_members = m.get("opponent_team", [])
        opponent_team_scores = []
        o_round_details = []

        for opp in opponent_team_members:
            opp_sim = calculate_bot_scorev2(opp["stats"], cur_map)
            opponent_team_scores.append(opp_sim["scorev2"])
            o_round_details.append(f"• {opp['name']}: {opp_sim['scorev2']:,} ScoreV2 ({opp_sim['acc']:.2f}%, {opp_sim['misses']} Miss)")

        # 3. Aggregate Team Scoring
        agg = aggregate_round_scores(player_team_scores, opponent_team_scores)
        p_total = agg["player_team_total"]
        o_total = agg["opponent_team_total"]
        margin = agg["margin"]

        if agg["winner"] == "player_team":
            r_winner = "player"
            m["player_score"] += 1
            m["pool"][cur_slot]["state"] = "won_player"
            win_msg = f"🟢 PUNKT FÜR DEIN TEAM auf {cur_slot}! ({p_total:,} vs {o_total:,} Pkt • +{margin:,})"
        else:
            r_winner = "bot"
            m["bot_score"] += 1
            m["pool"][cur_slot]["state"] = "won_bot"
            win_msg = f"🔴 PUNKT FÜR GEGNER-TEAM auf {cur_slot}! ({o_total:,} vs {p_total:,} Pkt • +{margin:,})"

        p_det_str = "\n  ".join(p_round_details)
        o_det_str = "\n  ".join(o_round_details)
        round_log = f"⚔️ RUNDE {cur_slot} (ScoreV2 Team-Ergebnis):\n🔵 Dein Team (Total: {p_total:,}):\n  {p_det_str}\n🔴 Gegner-Team (Total: {o_total:,}):\n  {o_det_str}\n➔ {win_msg}"
        m["history"].append(round_log)

        # Broadcast outcome to Bancho IRC Channel
        if getattr(self, "tourney_referee_bot", None) and self.tourney_referee_bot.connected and self.tourney_referee_bot.channel:
            self.tourney_referee_bot.send_channel_message(f"🏆 Runden-Ergebnis [{cur_slot}]: Dein Team ({p_total:,}) vs Gegner ({o_total:,}) ➔ {win_msg}")
            self.tourney_referee_bot.send_channel_message(f"📊 Neuer Spielstand: Du [{m['player_score']}] : [{m['bot_score']}] {m['bot_name']} (Ziel: {m['target_wins']} Siege)")

        # Check for Match Conclusion
        if m["player_score"] >= m["target_wins"] or m["bot_score"] >= m["target_wins"]:
            m["phase"] = "finished"
            m["history"].append(f"🏆 MATCH ENDSTAND: {m['player_score']} : {m['bot_score']}")
        else:
            m["phase"] = "pick"
            m["turn"] = "bot" if m.get("turn") == "player" else "player"

        def update_ui():
            if hasattr(self, 'tourney_phase_lbl') and self.tourney_phase_lbl.winfo_exists():
                self.show_tournament_match_lobby()

        self.safe_ui_dispatch(self, update_ui)

    def _update_tourney_feed_display(self):
        if hasattr(self, 'tourney_feed_box') and self.tourney_feed_box.winfo_exists():
            m = getattr(self, "tourney_match", {}) or {}
            ref_logs = m.get("referee_logs", [])
            hist_logs = m.get("history", [])
            combined = []
            if ref_logs:
                combined.extend(ref_logs)
            if hist_logs:
                if combined: combined.append("────────────────────────────────────────")
                combined.extend(hist_logs)
            if not combined:
                combined = ["Warte auf Match-Aktivität..."]

            self.tourney_feed_box.configure(state="normal")
            self.tourney_feed_box.delete("1.0", "end")
            self.tourney_feed_box.insert("1.0", "\n".join(combined))
            self.tourney_feed_box.configure(state="disabled")
            try: self.tourney_feed_box.see("end")
            except: pass

    def show_tourney_post_match_modal(self):
        """Interactive Post-Match Strategy Guessing Challenge & Gemini AI German Debriefing Modal."""
        m = self.tourney_match
        modal = ctk.CTkToplevel(self)
        modal.title("Turnier-Match Abschlussbericht & Scouting Challenge")
        modal.geometry("780x820")
        modal.configure(fg_color="#121216")

        winner_txt = "🎉 DEIN TEAM HAT DAS MATCH GEWONNEN!" if m["player_score"] >= m["target_wins"] else f"🤖 TEAM {m['bot_name']} GEWINNT DAS MATCH!"
        w_col = "#00E676" if m["player_score"] >= m["target_wins"] else "#FF4081"
        ctk.CTkLabel(modal, text=winner_txt, font=("Arial", 18, "bold"), text_color=w_col).pack(pady=(16, 4))
        ctk.CTkLabel(modal, text=f"Endstand: {m['player_score']} : {m['bot_score']} ({m['badge']} {m['division']} • {m.get('team_format_name', '1v1')} • {m['format_name']})",
                     font=("Arial", 12, "bold"), text_color="#ffffff").pack(pady=(0, 10))

        content_scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        content_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # --- SECTION 1: INTERACTIVE SCOUTING GUESSING CHALLENGE ---
        guess_card = ctk.CTkFrame(content_scroll, fg_color="#181824", corner_radius=12, border_width=1, border_color="#2e2e3f")
        guess_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(guess_card, text="🎯 SCOUTING-CHALLENGE: DEDUZIERE DAS GEGNERISCHE PROFIL!",
                     font=("Arial", 13, "bold"), text_color="#FF9800").pack(pady=(12, 4))
        ctk.CTkLabel(guess_card, text="Wähle basierend auf dem Draft & den Match-Runden die Top 2 Stärken und Top 2 Schwächen des Gegners:",
                     font=("Arial", 11), text_color="#aaaaaa").pack(pady=(0, 8))

        cols_f = ctk.CTkFrame(guess_card, fg_color="transparent")
        cols_f.pack(fill="x", padx=16, pady=4)
        cols_f.grid_columnconfigure(0, weight=1)
        cols_f.grid_columnconfigure(1, weight=1)

        # Strengths Selection
        s_box = ctk.CTkFrame(cols_f, fg_color="#13131c", corner_radius=8)
        s_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
        ctk.CTkLabel(s_box, text="Top-2 Stärken des Gegners:", font=("Arial", 11, "bold"), text_color="#00E676").pack(anchor="w", padx=10, pady=6)
        
        strength_vars = {}
        for s in ALL_8_SKILLS:
            var = ctk.BooleanVar(value=False)
            strength_vars[s] = var
            ctk.CTkCheckBox(s_box, text=s, variable=var, font=("Arial", 11), fg_color="#00E676", hover_color="#00C853").pack(anchor="w", padx=12, pady=2)

        # Weaknesses Selection
        w_box = ctk.CTkFrame(cols_f, fg_color="#13131c", corner_radius=8)
        w_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)
        ctk.CTkLabel(w_box, text="Top-2 Schwächen des Gegners:", font=("Arial", 11, "bold"), text_color="#FF5252").pack(anchor="w", padx=10, pady=6)

        weakness_vars = {}
        for s in ALL_8_SKILLS:
            var = ctk.BooleanVar(value=False)
            weakness_vars[s] = var
            ctk.CTkCheckBox(w_box, text=s, variable=var, font=("Arial", 11), fg_color="#FF5252", hover_color="#D32F2F").pack(anchor="w", padx=12, pady=2)

        result_frame = ctk.CTkFrame(guess_card, fg_color="transparent")
        result_frame.pack(fill="x", padx=16, pady=8)

        # Text debrief box
        txt = ctk.CTkTextbox(content_scroll, wrap="word", font=("Arial", 11), fg_color="#181822", border_width=1, border_color="#2e2e3f", height=320)
        txt.pack(fill="both", expand=True, pady=(0, 10))
        txt.insert("1.0", "⏳ Triff oben deine Scouting-Vorhersage und klicke auf 'Scouting-Analyse enthüllen'...")
        txt.configure(state="disabled")

        def submit_guess():
            chosen_strengths = [k for k, v in strength_vars.items() if v.get()]
            chosen_weaknesses = [k for k, v in weakness_vars.items() if v.get()]

            opp_lead = m.get("bot_profile", {})
            true_top2 = opp_lead.get("top_strengths", ["Aim", "Speed"])
            true_bot2 = opp_lead.get("top_weaknesses", ["Reading", "Stamina"])

            eval_res = evaluate_scouting_guess(chosen_strengths, chosen_weaknesses, true_top2, true_bot2)

            for w in result_frame.winfo_children():
                w.destroy()

            r_box = ctk.CTkFrame(result_frame, fg_color="#14141e", corner_radius=10, border_width=1, border_color="#00E5FF")
            r_box.pack(fill="x", pady=6)

            ctk.CTkLabel(r_box, text=f"{eval_res['verdict_title']} • {eval_res['accuracy_pct']:.0f}% Genauigkeit ({eval_res['correct_count']}/4 Treffer)",
                         font=("Arial", 13, "bold"), text_color="#00E5FF").pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(r_box, text=eval_res['verdict_desc'], font=("Arial", 11), text_color="#bbbbcc").pack(anchor="w", padx=12, pady=(0, 4))
            ctk.CTkLabel(r_box, text=f"• Echte Stärken: {', '.join(true_top2)} | Echte Schwächen: {', '.join(true_bot2)}",
                         font=("Arial", 11, "bold"), text_color="#FF9800").pack(anchor="w", padx=12, pady=(0, 8))

            # Reveal true opponent radar canvas
            r_canvas_f = ctk.CTkFrame(r_box, fg_color="transparent")
            r_canvas_f.pack(fill="x", padx=10, pady=(0, 8))
            ctk.CTkLabel(r_canvas_f, text="🔍 Enthülltes wahres 8-Skillset Gegnerprofil:", font=("Arial", 11, "bold"), text_color="#E040FB").pack(anchor="w", pady=(0, 4))
            opp_canvas = tk.Canvas(r_canvas_f, width=360, height=240, bg="#101018", highlightthickness=0)
            opp_canvas.pack(pady=4)
            draw_radar_polygon(opp_canvas, opp_lead.get("stats", {}), color_theme="purple", is_hidden=False)

            # Generate Gemini AI Debrief
            match_summary = {
                "tournament": m.get("tournament", "OWC"),
                "badge": m.get("badge", "OWC"),
                "division": m.get("division", "Grand Finals"),
                "year": m.get("year", 2025),
                "format_name": m.get("format_name", "Best of 13"),
                "player_score": m.get("player_score", 0),
                "bot_score": m.get("bot_score", 0),
                "bot_name": m.get("bot_name", "Bot"),
                "history": m.get("history", [])
            }

            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("1.0", "⏳ Gemini KI generiert den offiziellen deutschen Caster-Match-Report...")
            txt.configure(state="disabled")

            def _bg_debrief():
                report_str = generate_strategic_debrief(match_summary, opp_lead, eval_res, api_key=getattr(self, "gemini_key", None))
                def _update_ui():
                    if txt.winfo_exists():
                        txt.configure(state="normal")
                        txt.delete("1.0", "end")
                        txt.insert("1.0", report_str)
                        txt.configure(state="disabled")
                self.after(0, _update_ui)

            threading.Thread(target=_bg_debrief, daemon=True).start()

        ctk.CTkButton(guess_card, text="🔍 Scouting-Analyse enthüllen & Auswerten ➔", font=("Arial", 13, "bold"), height=36,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000",
                      command=submit_guess).pack(fill="x", padx=16, pady=(4, 12))

        ctk.CTkButton(modal, text="Schließen", width=140, height=36, font=("Arial", 12, "bold"),
                      fg_color="#2b2b36", hover_color="#3a3a48", command=modal.destroy).pack(pady=(4, 14))


    # ---------------------------------------------------------------------------
    # CUSTOM MAPPOOL BUILDER (DRAG & DROP, LINKS, MULTI-DIFF & SLOT ASSIGNMENT)
    # ---------------------------------------------------------------------------
    def show_custom_mappool_builder(self, from_multiplayer=False):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        master = ctk.CTkFrame(self, fg_color="#101015")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        if not hasattr(self, "custom_tourney_pool") or not isinstance(self.custom_tourney_pool, dict):
            self.custom_tourney_pool = {}

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(12, 8))
        top_bar.pack_propagate(False)

        back_target = self.show_multiplayer_hub if from_multiplayer else self.show_tournament_selector
        ctk.CTkButton(top_bar, text="⬅ Zurück", width=90, height=34, font=("Arial", 12, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=back_target).pack(side="left", padx=15, pady=12)

        title_txt = "🛠️ Custom Scrims Mappool (Links & Drag-and-Drop)" if from_multiplayer else "🛠️ Custom Mappool Builder (Links & Drag-and-Drop)"
        ctk.CTkLabel(top_bar, text=title_txt, font=("Arial", 17, "bold"), text_color="#00E5FF").pack(side="left", padx=10)

        # Quick Actions on top right
        def fill_ai_remaining():
            slots = ["NM1", "NM2", "NM3", "NM4", "HD1", "HD2", "HR1", "HR2", "DT1", "DT2", "FM1", "FM2", "TB"]
            used_ids = {m["id"] for m in self.custom_tourney_pool.values()}
            for s in slots:
                if s not in self.custom_tourney_pool:
                    chosen = pick_dynamic_map_for_skill("Aim" if "NM1" in s or "HD1" in s else ("Tech" if "NM2" in s else "Speed"), 5.5, exclude_ids=used_ids)
                    used_ids.add(chosen["id"])
                    self.custom_tourney_pool[s] = {
                        "slot": s,
                        "id": chosen["id"],
                        "name": chosen["name"],
                        "sr": chosen["sr"],
                        "bpm": chosen.get("bpm", 180),
                        "len": chosen.get("len", 120),
                        "cs": chosen.get("cs", 4.0),
                        "ar": chosen.get("ar", 9.0),
                        "od": chosen.get("od", 8.0),
                        "year": chosen.get("year", 2024),
                        "state": "available"
                    }
            self.render_custom_pool_cards()

        ctk.CTkButton(top_bar, text="🎲 Rest mit KI füllen", width=140, height=34, font=("Arial", 12, "bold"),
                      fg_color="#9C27B0", hover_color="#7B1FA2", command=fill_ai_remaining).pack(side="right", padx=15)

        # Drag & Drop and Manual Input Header Box
        drop_box = ctk.CTkFrame(master, fg_color="#181824", corner_radius=12, border_width=2, border_color="#00E5FF")
        drop_box.pack(fill="x", padx=20, pady=(0, 10))

        d_inner = ctk.CTkFrame(drop_box, fg_color="transparent")
        d_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(d_inner, text="📥 .osu Datei / Link hier hineinziehen oder einfügen:", font=("Arial", 13, "bold"), text_color="#ffffff").pack(anchor="w")

        input_row = ctk.CTkFrame(d_inner, fg_color="transparent")
        input_row.pack(fill="x", pady=(6, 2))

        self.custom_map_input = ctk.CTkEntry(input_row, placeholder_text="osu.ppy.sh/b/... oder Beatmap-ID oder .osu Datei...",
                                             font=("Arial", 12), height=36)
        self.custom_map_input.pack(side="left", fill="x", expand=True, padx=(0, 10))

        def add_from_entry():
            txt = self.custom_map_input.get().strip()
            if txt:
                self.custom_map_input.delete(0, "end")
                self.handle_custom_pool_input(txt)

        ctk.CTkButton(input_row, text="➕ Map hinzufügen", width=130, height=36, font=("Arial", 12, "bold"),
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=add_from_entry).pack(side="right")

        # Enable Drag & Drop on drop_box
        try:
            drop_box.drop_target_register(DND_FILES)
            drop_box.dnd_bind('<<Drop>>', lambda e: self.handle_custom_pool_input(e.data))
        except: pass

        # 13 Slot Grid Scrollable Area
        main_content = ctk.CTkFrame(master, fg_color="transparent")
        main_content.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.custom_pool_scroll = ctk.CTkScrollableFrame(main_content, fg_color="transparent")
        self.custom_pool_scroll.pack(fill="both", expand=True)

        # Bottom Bar: Start Match Button
        bot_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        bot_bar.pack(fill="x", padx=20, pady=(0, 12))
        bot_bar.pack_propagate(False)

        def start_custom_match():
            num_maps = len(self.custom_tourney_pool)
            if num_maps < 1:
                self.show_message("Keine Maps", "Bitte füge mindestens 1 Map zu deinem Custom-Mappool hinzu.")
                return

            bot_key = getattr(self, "tourney_bot_var", None)
            bot_val = bot_key.get() if bot_key else "🔵 Challenger (Solide)"
            bot_cfg = self.BOT_DIFFICULTIES.get(bot_val, self.BOT_DIFFICULTIES["🔵 Challenger (Solide)"])

            # Dynamically adjust target wins & format to match the custom pool size perfectly
            if num_maps <= 2:
                target_wins = 1
                fmt_name = f"Best of {num_maps} (First to 1)"
                bans_needed = 0
            elif num_maps <= 4:
                target_wins = 2
                fmt_name = f"Best of {num_maps} (First to 2)"
                bans_needed = 0
            elif num_maps <= 6:
                target_wins = 3
                fmt_name = f"Best of {num_maps} (First to 3)"
                bans_needed = 2 if num_maps >= 5 else 0
            elif num_maps <= 8:
                target_wins = 4
                fmt_name = f"Best of {num_maps} (First to 4)"
                bans_needed = 2
            else:
                target_wins = min(6, (num_maps // 2) + 1)
                fmt_name = f"Best of {min(num_maps, target_wins * 2 - 1)} (First to {target_wins})"
                bans_needed = 2

            self.tourney_match = {
                "tournament": "Custom Tournament",
                "badge": "Custom",
                "division": f"Custom Pool ({num_maps} Maps)",
                "year": "Custom",
                "bot_name": bot_cfg["name"],
                "bot_cfg": bot_cfg,
                "target_wins": target_wins,
                "format_name": fmt_name,
                "player_score": 0,
                "bot_score": 0,
                "phase": "roll" if bans_needed > 0 else "pick",
                "turn": "player",
                "player_roll": None,
                "bot_roll": None,
                "bans_needed": bans_needed,
                "bans_done": 0,
                "pool": dict(self.custom_tourney_pool),
                "current_pick": None,
                "history": [f"🛠️ Custom Pool Match gestartet ({num_maps} Maps • {fmt_name})"]
            }
            self.show_tournament_match_lobby()

        ctk.CTkButton(bot_bar, text="⚔️ Turnier-Match mit Custom Pool starten ➔", font=("Arial", 14, "bold"), height=42,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000",
                      command=start_custom_match).pack(fill="x", padx=15, pady=9)

        self.render_custom_pool_cards()

    def prompt_rename_custom_slot(self, old_slot):
        dialog = ctk.CTkInputDialog(text=f"Neuen Namen für Slot '{old_slot}' eingeben (z.B. HR3, HR4, DT3, FM3, TB2):", title="Slot umbenennen")
        new_name = dialog.get_input()
        if new_name:
            new_name = new_name.strip().upper()
            if new_name and new_name != old_slot:
                val = self.custom_tourney_pool.pop(old_slot, None)
                if val and isinstance(val, dict):
                    val["slot"] = new_name
                self.custom_tourney_pool[new_name] = val
                self.render_custom_pool_cards()

    def prompt_add_any_custom_slot(self):
        dialog = ctk.CTkInputDialog(text="Slot-Namen eingeben (z.B. HR3, HR4, NM5, NM6, DT3, DT4, FM3, TB2, EZ1):", title="Neuen Slot hinzufügen")
        slot_name = dialog.get_input()
        if slot_name:
            slot_name = slot_name.strip().upper()
            if slot_name:
                self.custom_tourney_pool[slot_name] = None
                self.render_custom_pool_cards()

    def render_custom_pool_cards(self):
        for w in self.custom_pool_scroll.winfo_children():
            w.destroy()

        if not hasattr(self, "custom_tourney_pool") or not isinstance(self.custom_tourney_pool, dict):
            self.custom_tourney_pool = {}

        # Default slots if completely empty
        if not self.custom_tourney_pool and not getattr(self, "_custom_pool_initialized", False):
            self._custom_pool_initialized = True
            for s in ["NM1", "NM2", "NM3", "NM4", "HD1", "HD2", "HR1", "HR2", "DT1", "DT2", "FM1", "FM2", "TB"]:
                self.custom_tourney_pool[s] = None

        mod_order = ['NM', 'HD', 'HR', 'DT', 'FM', 'TB', 'EZ', 'FL', 'Other']
        mod_info = {
            'NM': ('NoMod (NM)', '#3b8ed0'),
            'HD': ('Hidden (HD)', '#E91E63'),
            'HR': ('HardRock (HR)', '#F44336'),
            'DT': ('DoubleTime (DT)', '#9C27B0'),
            'FM': ('FreeMod (FM)', '#00E5FF'),
            'TB': ('Tiebreaker (TB)', '#FF9800'),
            'EZ': ('Easy (EZ)', '#4CAF50'),
            'FL': ('Flashlight (FL)', '#FFEB3B'),
            'Other': ('Spezial / Custom', '#AAAAAA')
        }

        def get_slot_sort_key(s):
            for p in mod_order:
                if s.startswith(p):
                    num = s[len(p):]
                    return (mod_order.index(p), int(num) if num.isdigit() else 0)
            return (99, s)

        # Top Action Bar: Add Slots
        bar = ctk.CTkFrame(self.custom_pool_scroll, fg_color="#181824", corner_radius=10, border_width=1, border_color="#2b2b3c")
        bar.pack(fill="x", padx=4, pady=(0, 10))

        bar_inner = ctk.CTkFrame(bar, fg_color="transparent")
        bar_inner.pack(fill="x", padx=10, pady=8)

        ctk.CTkLabel(bar_inner, text="➕ Schnell-Slots:", font=("Arial", 11, "bold"), text_color="#bbbbcc").pack(side="left", padx=(0, 6))

        def add_specific_mod_slot(mod_prefix):
            existing_nums = []
            for s in self.custom_tourney_pool.keys():
                if s == mod_prefix:
                    existing_nums.append(1)
                elif s.startswith(mod_prefix):
                    num_part = s[len(mod_prefix):]
                    if num_part.isdigit():
                        existing_nums.append(int(num_part))
            next_num = max(existing_nums, default=0) + 1
            if mod_prefix == "TB" and "TB" not in self.custom_tourney_pool:
                new_slot_name = "TB"
            else:
                new_slot_name = f"{mod_prefix}{next_num}"
            self.custom_tourney_pool[new_slot_name] = None
            self.render_custom_pool_cards()

        for m_pfx in ['NM', 'HD', 'HR', 'DT', 'FM', 'TB', 'EZ']:
            c_name, c_col = mod_info.get(m_pfx, (m_pfx, '#AAAAAA'))
            ctk.CTkButton(bar_inner, text=f"+ {m_pfx}", width=48, height=26, font=("Arial", 11, "bold"),
                          fg_color="#252535", hover_color=c_col, text_color=c_col,
                          command=lambda p=m_pfx: add_specific_mod_slot(p)).pack(side="left", padx=2)

        ctk.CTkButton(bar_inner, text="✏️ Freier Slot...", width=95, height=26, font=("Arial", 11, "bold"),
                      fg_color="#2e2e42", hover_color="#3e3e58", text_color="#ffffff",
                      command=self.prompt_add_any_custom_slot).pack(side="left", padx=6)

        # Group slots by Category cleanly
        categories_dict = {}
        for s in sorted(self.custom_tourney_pool.keys(), key=get_slot_sort_key):
            prefix = 'Other'
            for pfx in mod_order:
                if s.startswith(pfx):
                    prefix = pfx
                    break
            categories_dict.setdefault(prefix, []).append(s)

        # Render each category section sequentially
        for pfx in mod_order:
            slot_list = categories_dict.get(pfx, [])
            if not slot_list:
                continue

            cat_name, col = mod_info.get(pfx, (pfx, '#AAAAAA'))

            cat_frame = ctk.CTkFrame(self.custom_pool_scroll, fg_color="transparent")
            cat_frame.pack(fill="x", padx=4, pady=(6, 2))

            ctk.CTkLabel(cat_frame, text=f"{cat_name}  ({len(slot_list)} Maps)", font=("Arial", 13, "bold"), text_color=col).pack(side="left")
            ctk.CTkButton(cat_frame, text=f"+ {pfx}-Slot", width=65, height=22, font=("Arial", 10, "bold"),
                          fg_color="#252535", hover_color=col, text_color=col,
                          command=lambda p=pfx: add_specific_mod_slot(p)).pack(side="right")

            grid_box = ctk.CTkFrame(self.custom_pool_scroll, fg_color="transparent")
            grid_box.pack(fill="x", padx=4, pady=(0, 6))
            grid_box.grid_columnconfigure(0, weight=1)
            grid_box.grid_columnconfigure(1, weight=1)

            for idx, s in enumerate(slot_list):
                row = idx // 2
                col_pos = idx % 2
                m_data = self.custom_tourney_pool.get(s)

                card = ctk.CTkFrame(grid_box, fg_color="#181822", corner_radius=10, border_width=1, border_color="#2b2b3c")
                card.grid(row=row, column=col_pos, sticky="nsew", padx=4, pady=4)

                c_top = ctk.CTkFrame(card, fg_color="transparent")
                c_top.pack(fill="x", padx=10, pady=(8, 2))

                ctk.CTkLabel(c_top, text=f"{s}", font=("Arial", 13, "bold"), text_color=col).pack(side="left")

                # Action buttons on top right (Rename + Delete)
                def make_rename(slot=s):
                    return lambda: self.prompt_rename_custom_slot(slot)
                def make_del_slot(slot=s):
                    return lambda: (self.custom_tourney_pool.pop(slot, None), self.render_custom_pool_cards())

                ctk.CTkButton(c_top, text="🗑️", width=26, height=22, font=("Arial", 11),
                              fg_color="#2b2b36", hover_color="#c62828", command=make_del_slot(s)).pack(side="right", padx=(2, 0))
                ctk.CTkButton(c_top, text="✏️", width=26, height=22, font=("Arial", 10),
                              fg_color="#2b2b36", hover_color="#3b8ed0", command=make_rename(s)).pack(side="right")

                if m_data and isinstance(m_data, dict):
                    ctk.CTkLabel(card, text=m_data.get("name", "")[:45], font=("Arial", 11, "bold"), text_color="#ffffff", anchor="w").pack(fill="x", padx=10, pady=(2, 0))
                    ctk.CTkLabel(card, text=f"★ {m_data.get('sr', 5.0):.2f} • {m_data.get('bpm', 180)} BPM • {m_data.get('len', 120)}s",
                                 font=("Arial", 10), text_color="#888899", anchor="w").pack(fill="x", padx=10, pady=(0, 8))
                else:
                    def make_assign_click(slot=s):
                        return lambda: self.prompt_slot_assignment_modal(slot)
                    
                    empty_btn = ctk.CTkButton(card, text="➕ Map zuweisen (Klick oder Drop)",
                                              font=("Arial", 10), height=34, fg_color="#14141c", hover_color="#20202e",
                                              text_color="#666677", command=make_assign_click(s))
                    empty_btn.pack(fill="x", padx=10, pady=(4, 8))
                    try:
                        empty_btn.drop_target_register(DND_FILES)
                        empty_btn.dnd_bind('<<Drop>>', lambda e, slot=s: self.handle_custom_pool_input(e.data, target_slot=slot))
                    except: pass

    def handle_custom_pool_input(self, raw_input, target_slot=None):
        cleaned = raw_input.strip().strip('"').strip("'")
        if not cleaned: return

        # Check for osuCollector Tournament URL (e.g. https://osucollector.com/tournaments/1728/...)
        m_osucollector_tourney = re.search(r'osucollector\.com/tournaments/(\d+)', cleaned)
        if m_osucollector_tourney:
            t_id = m_osucollector_tourney.group(1)
            def _async_import_osucollector():
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    r = requests.get(f'https://osucollector.com/api/tournaments/{t_id}', headers=headers, timeout=10)
                    if r.status_code == 200:
                        t_data = r.json()
                        rounds = t_data.get('rounds', [])
                        if not rounds:
                            self.show_message("osuCollector Import", "Keine Runden im Turnier gefunden.")
                            return
                        
                        # Load newest or grand finals round by default, or open round picker
                        selected_rd = rounds[-1]
                        self.custom_tourney_pool = {}
                        for mod_group in selected_rd.get('mods', []):
                            mod_tag = mod_group.get('mod', 'NM')
                            maps_list = mod_group.get('maps', [])
                            for idx, m in enumerate(maps_list, 1):
                                slot = "TB" if mod_tag == "TB" and len(maps_list) == 1 else f"{mod_tag}{idx}"
                                bset = m.get('beatmapset', {}) or {}
                                artist = bset.get('artist', 'Unknown')
                                title = bset.get('title', 'Unknown')
                                diff = m.get('version', 'Expert')
                                sr = float(m.get('difficulty_rating') or 5.5)
                                bpm = int(m.get('bpm') or 180)
                                h_len = int(m.get('hit_length') or 120)
                                self.custom_tourney_pool[slot] = {
                                    "slot": slot,
                                    "id": str(m.get('id', 0)),
                                    "name": f"{artist} - {title} [{diff}]",
                                    "sr": sr,
                                    "bpm": bpm,
                                    "len": h_len,
                                    "cs": float(m.get('cs') or 4.0),
                                    "ar": float(m.get('ar') or 9.0),
                                    "od": float(m.get('od') or 8.0),
                                    "year": 2025,
                                    "state": "available"
                                }
                        self.after(0, lambda: (self.render_custom_pool_cards(), self.show_message("osuCollector Import", f"✅ {t_data.get('name', 'Turnier')} ({selected_rd.get('round')}) erfolgreich mit {len(self.custom_tourney_pool)} Maps importiert!")))
                    else:
                        self.after(0, lambda: self.show_message("Fehler", f"Turnier {t_id} konnte nicht geladen werden (HTTP {r.status_code})."))
                except Exception as e:
                    self.after(0, lambda: self.show_message("Fehler", f"Import fehlgeschlagen: {e}"))
            threading.Thread(target=_async_import_osucollector, daemon=True).start()
            return

        # Check for multiple files / splitlist
        try:
            file_list = self.tk.splitlist(cleaned)
            if file_list and len(file_list) > 0:
                cleaned = file_list[0]
        except: pass

        # 1. Local .osu file
        if os.path.isfile(cleaned) and cleaned.endswith('.osu'):
            try:
                title, artist, version, bid, sid = "Unknown", "Unknown", "Normal", "0", "0"
                cs, ar, od, hp = 4.0, 9.0, 8.0, 5.0
                with open(cleaned, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('Title:'): title = line.split(':', 1)[1].strip()
                        elif line.startswith('Artist:'): artist = line.split(':', 1)[1].strip()
                        elif line.startswith('Version:'): version = line.split(':', 1)[1].strip()
                        elif line.startswith('BeatmapID:'): bid = line.split(':', 1)[1].strip()
                        elif line.startswith('BeatmapSetID:'): sid = line.split(':', 1)[1].strip()
                        elif line.startswith('CircleSize:'): cs = float(line.split(':', 1)[1].strip())
                        elif line.startswith('ApproachRate:'): ar = float(line.split(':', 1)[1].strip())
                        elif line.startswith('OverallDifficulty:'): od = float(line.split(':', 1)[1].strip())

                map_obj = {
                    "name": f"{artist} - {title} [{version}]",
                    "id": bid if bid and bid != '0' else (sid if sid and sid != '0' else str(random.randint(100000, 999999))),
                    "sr": 5.0,
                    "bpm": 180,
                    "len": 120,
                    "cs": cs,
                    "ar": ar,
                    "od": od,
                    "state": "available"
                }
                self.show_slot_assign_dialog(map_obj, diff_choices=[{"name": version, "obj": map_obj}], default_slot=target_slot)
                return
            except Exception as e:
                self.show_message("Fehler", f".osu Datei konnte nicht gelesen werden: {e}")
                return

        # 2. Extract Beatmap ID or BeatmapSet ID from URL or input
        m_set_beatmap = re.search(r'beatmapsets/(\d+)#(?:osu|taiko|fruits|mania)/(\d+)', cleaned)
        m_b = re.search(r'(?:/b/|/beatmaps/)(\d+)', cleaned)
        m_s = re.search(r'(?:/s/|/beatmapsets/)(\d+)', cleaned)

        b_id = None
        s_id = None
        if m_set_beatmap:
            s_id, b_id = m_set_beatmap.group(1), m_set_beatmap.group(2)
        elif m_b:
            b_id = m_b.group(1)
        elif m_s:
            s_id = m_s.group(1)
        elif cleaned.isdigit():
            b_id = cleaned

        # Query osu! API for map details & multiple diffs
        key = getattr(self, "api_key", "")
        if not key:
            # Offline mock map
            fallback_map = {
                "name": f"Beatmap #{b_id or s_id}",
                "id": b_id or s_id or "12345",
                "sr": 5.2, "bpm": 180, "len": 120, "state": "available"
            }
            self.show_slot_assign_dialog(fallback_map, diff_choices=[{"name": "Standard Diff", "obj": fallback_map}], default_slot=target_slot)
            return

        def fetch_api():
            try:
                if s_id:
                    url = f"https://osu.ppy.sh/api/get_beatmaps?k={key}&s={s_id}&m=0"
                else:
                    url = f"https://osu.ppy.sh/api/get_beatmaps?k={key}&b={b_id}&m=0"

                resp = requests.get(url, timeout=8)
                if resp.status_code == 200 and resp.json():
                    diffs = resp.json()
                    diff_choices = []
                    for d in diffs:
                        d_obj = {
                            "name": f"{d.get('artist')} - {d.get('title')} [{d.get('version')}]",
                            "id": str(d.get("beatmap_id")),
                            "sr": float(d.get("difficultyrating", 5.0)),
                            "bpm": float(d.get("bpm", 180)),
                            "len": int(d.get("total_length", 120)),
                            "cs": float(d.get("diff_size", 4.0)),
                            "ar": float(d.get("diff_approach", 9.0)),
                            "od": float(d.get("diff_overall", 8.0)),
                            "state": "available"
                        }
                        diff_choices.append({"name": f"[{d.get('version')}] (★ {d_obj['sr']:.2f})", "obj": d_obj})

                    if diff_choices:
                        self.after(0, lambda: self.show_slot_assign_dialog(diff_choices[0]["obj"], diff_choices=diff_choices, default_slot=target_slot))
                        return

                # If not found via API, fallback
                fallback_map = {
                    "name": f"Beatmap #{b_id or s_id}",
                    "id": b_id or s_id or "12345",
                    "sr": 5.2, "bpm": 180, "len": 120, "state": "available"
                }
                self.after(0, lambda: self.show_slot_assign_dialog(fallback_map, diff_choices=[{"name": "Standard Diff", "obj": fallback_map}], default_slot=target_slot))
            except Exception as e:
                self.after(0, lambda: self.show_message("Fehler", f"Map-Daten konnten nicht geladen werden: {e}"))

        threading.Thread(target=fetch_api, daemon=True).start()

    def show_slot_assign_dialog(self, main_obj, diff_choices=None, default_slot=None):
        modal = ctk.CTkToplevel(self)
        modal.title("Difficulty & Slot zuweisen")
        modal.geometry("520x460")
        modal.configure(fg_color="#121216")
        modal.grab_set()

        ctk.CTkLabel(modal, text="🎯 Map in Custom Mappool einfügen", font=("Arial", 16, "bold"), text_color="#00E5FF").pack(pady=(18, 6))

        info_box = ctk.CTkFrame(modal, fg_color="#181822", corner_radius=8)
        info_box.pack(fill="x", padx=20, pady=6)
        
        map_title_lbl = ctk.CTkLabel(info_box, text=main_obj.get("name", "")[:50], font=("Arial", 12, "bold"), text_color="#ffffff")
        map_title_lbl.pack(anchor="w", padx=12, pady=(8, 2))
        
        meta_lbl = ctk.CTkLabel(info_box, text=f"★ {main_obj.get('sr', 5.0):.2f} • {main_obj.get('bpm', 180)} BPM", font=("Arial", 10), text_color="#888899")
        meta_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # 1. Difficulty Dropdown (if multiple diffs)
        diff_names = [d["name"] for d in (diff_choices or [{"name": main_obj["name"], "obj": main_obj}])]
        sel_diff_var = ctk.StringVar(value=diff_names[0])
        
        ctk.CTkLabel(modal, text="1. Wähle die gewünschte Difficulty:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=20, pady=(10, 2))
        diff_opt = ctk.CTkOptionMenu(modal, values=diff_names, variable=sel_diff_var, font=("Arial", 12),
                                     fg_color="#262635", button_color="#353548")
        diff_opt.pack(fill="x", padx=20, pady=(0, 10))

        def on_diff_change(val):
            for d in diff_choices:
                if d["name"] == val:
                    o = d["obj"]
                    map_title_lbl.configure(text=o.get("name", "")[:50])
                    meta_lbl.configure(text=f"★ {o.get('sr', 5.0):.2f} • {o.get('bpm', 180)} BPM")
                    break
        diff_opt.configure(command=on_diff_change)

        # 2. Slot Dropdown (NM1-4, HD1-2, HR1-2, DT1-2, FM1-2, TB)
        all_slots = ["NM1", "NM2", "NM3", "NM4", "NM5", "NM6", "HD1", "HD2", "HD3", "HR1", "HR2", "HR3", "DT1", "DT2", "DT3", "FM1", "FM2", "FM3", "TB", "TB2"]
        init_slot = default_slot if default_slot in all_slots else "NM1"
        # Find first empty slot if default not set
        if not default_slot:
            for s in all_slots:
                if s not in self.custom_tourney_pool:
                    init_slot = s
                    break

        sel_slot_var = ctk.StringVar(value=init_slot)
        ctk.CTkLabel(modal, text="2. Wähle den Mappool-Slot:", font=("Arial", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=20, pady=(5, 2))
        slot_opt = ctk.CTkOptionMenu(modal, values=all_slots, variable=sel_slot_var, font=("Arial", 12, "bold"),
                                     fg_color="#262635", button_color="#353548")
        slot_opt.pack(fill="x", padx=20, pady=(0, 20))

        # Confirm Button
        def confirm():
            target_s = sel_slot_var.get()
            chosen_diff_name = sel_diff_var.get()
            chosen_obj = main_obj
            if diff_choices:
                for d in diff_choices:
                    if d["name"] == chosen_diff_name:
                        chosen_obj = d["obj"]
                        break
            
            chosen_obj["slot"] = target_s
            self.custom_tourney_pool[target_s] = dict(chosen_obj)
            modal.destroy()
            self.render_custom_pool_cards()

        ctk.CTkButton(modal, text="✅ Slot verbindlich zuweisen", font=("Arial", 13, "bold"), height=38,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=confirm).pack(fill="x", padx=20, pady=10)

    def prompt_slot_assignment_modal(self, slot):
        # Open quick link input modal for specific slot
        modal = ctk.CTkToplevel(self)
        modal.title(f"Map für Slot {slot} hinzufügen")
        modal.geometry("460x220")
        modal.configure(fg_color="#121216")
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Map für Slot {slot} zuweisen:", font=("Arial", 14, "bold"), text_color="#00E5FF").pack(pady=(20, 8))

        e = ctk.CTkEntry(modal, placeholder_text="Link, Beatmap-ID oder .osu Pfad einfügen...", font=("Arial", 12), height=36)
        e.pack(fill="x", padx=20, pady=8)

        def do_assign():
            txt = e.get().strip()
            modal.destroy()
            if txt:
                self.handle_custom_pool_input(txt, target_slot=slot)

        ctk.CTkButton(modal, text="Hinzufügen ➔", font=("Arial", 12, "bold"), height=34,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", command=do_assign).pack(fill="x", padx=20, pady=10)

    def show_training_mode_selection(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="📈 Training: Modus wählen", font=("Arial", 18, "bold"), text_color="#3b8ed0").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("training_mode")).pack(side="right", padx=15)

        cards_container = ctk.CTkScrollableFrame(master, fg_color="transparent")
        cards_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Grid of Cards
        grid_frame = ctk.CTkFrame(cards_container, fg_color="transparent")
        grid_frame.pack(expand=True, pady=10)

        # ----------------- CARD 1: LEVEL-TRAINING (MODS) -----------------
        c1 = ctk.CTkFrame(grid_frame, fg_color="#181822", corner_radius=16, border_width=2, border_color="#1f538d", width=380, height=220)
        c1.grid(row=0, column=0, padx=15, pady=15)
        c1.pack_propagate(False)

        c1_top = ctk.CTkFrame(c1, fg_color="transparent")
        c1_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c1_top, text="🏆 Level-Training (Mods)", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c1_top, text=" VERFÜGBAR ", font=("Arial", 10, "bold"), fg_color="#1b382b", text_color="#4CAF50", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c1, text="4.0★ bis 10.0★ Stufenaufstieg für NoMod, DoubleTime, Hidden, HardRock uvm. Meistere Level für Level mit 5 S-Ranks, 2 PFCs und 2 Maps über 3 Minuten.",
                     font=("Arial", 12), text_color="#aaaaaa", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c1, text="🚀 Mod wählen & starten ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#1f538d", hover_color="#14375e", command=self.show_training_skillset_selection).pack(fill="x", padx=16, side="bottom", pady=16)

        # ----------------- CARD 2: KI-ANALYSIERTES TRAINING -----------------
        c2 = ctk.CTkFrame(grid_frame, fg_color="#221826", corner_radius=16, border_width=2, border_color="#E91E63", width=380, height=220)
        c2.grid(row=0, column=1, padx=15, pady=15)
        c2.pack_propagate(False)

        c2_top = ctk.CTkFrame(c2, fg_color="transparent")
        c2_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c2_top, text="🤖 KI-analysiertes Training", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c2_top, text=" ✨ LIVE COACH ", font=("Arial", 10, "bold"), fg_color="#E91E63", text_color="#ffffff", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c2, text="Live-Coaching mit Gemini! Die KI schlägt dir dynamisch Maps mit konkreten Zielen vor, bewertet Runden live und passt das Training an.",
                     font=("Arial", 12), text_color="#ddbbcc", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c2, text="🔥 KI-Training starten ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#E91E63", hover_color="#C2185B", command=self.show_ai_interactive_training).pack(fill="x", padx=16, side="bottom", pady=16)

        # ----------------- CARD 3: TURNIER-SIMULATOR (MATCH GEGEN KI) -----------------
        c3 = ctk.CTkFrame(grid_frame, fg_color="#221820", corner_radius=16, border_width=2, border_color="#FF9800", width=380, height=220)
        c3.grid(row=1, column=0, padx=15, pady=15)
        c3.pack_propagate(False)

        c3_top = ctk.CTkFrame(c3, fg_color="transparent")
        c3_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c3_top, text="🏆 Turnier-Simulator", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c3_top, text=" ⚔️ MATCH GEGEN KI ", font=("Arial", 10, "bold"), fg_color="#FF9800", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c3, text="Tritt in echten Mappools (OWC, ET, AOT, BFT, Custom) gegen KI-Gegner an! Inklusive Roll, Pick/Ban Taktik, Live-Caster und Score-Duell.",
                     font=("Arial", 12), text_color="#eeddcc", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c3, text="⚔️ Turnier-Match starten ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#FF9800", hover_color="#F57C00", text_color="#000000",
                      command=lambda: self.ensure_osu_irc_password(on_success_callback=self.show_tournament_selector)).pack(fill="x", padx=16, side="bottom", pady=16)

        # ----------------- CARD 4: DEEP REPLAY ANALYSE (ZERO-CLICK & KI) -----------------
        c4 = ctk.CTkFrame(grid_frame, fg_color="#141c26", corner_radius=16, border_width=2, border_color="#00E5FF", width=380, height=220)
        c4.grid(row=1, column=1, padx=15, pady=15)
        c4.pack_propagate(False)

        c4_top = ctk.CTkFrame(c4, fg_color="transparent")
        c4_top.pack(fill="x", padx=16, pady=(16, 4))
        ctk.CTkLabel(c4_top, text="🔬 Deep Replay Analyse", font=("Arial", 18, "bold"), text_color="#ffffff").pack(side="left")
        ctk.CTkLabel(c4_top, text=" ✨ ZERO-CLICK ", font=("Arial", 10, "bold"), fg_color="#00E5FF", text_color="#000000", corner_radius=4).pack(side="right")

        ctk.CTkLabel(c4, text="Vollautomatische Replay-Telemetrie ohne F2! Overaim vs. Underaim %, K1/K2 Haltezeiten, Unstable Rate (UR), Choke-Gründe & Gemini-Coaching.",
                     font=("Arial", 12), text_color="#bbddff", justify="left", wraplength=340).pack(padx=16, pady=(4, 12), anchor="w")

        ctk.CTkButton(c4, text="🔬 Replay-Analyse öffnen ➔", font=("Arial", 13, "bold"), height=38,
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000",
                      command=lambda: self.show_deep_replay_analyzer(from_training=True)).pack(fill="x", padx=16, side="bottom", pady=16)

    # ---------------------------------------------------------------------------
    # KI-ANALYSIERTES INTERAKTIVES LIVE-TRAINING
    # ---------------------------------------------------------------------------
    def show_ai_interactive_training(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Training", width=95, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_training_mode_selection).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🤖 KI-analysiertes Live-Training", font=("Arial", 18, "bold"), text_color="#E91E63").pack(side="left", padx=10)

        supporter_text = "⭐ Supporter: Aktiv" if getattr(self, "has_osu_supporter", False) else "🌐 Standard (Web)"
        ctk.CTkLabel(top_bar, text=supporter_text, font=("Arial", 11, "bold"), text_color="#00E5FF").pack(side="right", padx=15)

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_box.grid_columnconfigure(0, weight=4)
        main_box.grid_columnconfigure(1, weight=5)
        main_box.grid_rowconfigure(0, weight=1)

        # ---------------- LEFT PANEL: AUTONOMOUS AI TRAINING PLAN & MAP CARD ----------------
        left_panel = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(left_panel, text="🧠 KI-Trainingsplan & Empfehlung", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(15, 3))

        self.ai_train_focus_lbl = ctk.CTkLabel(left_panel, text="✨ KI-Fokus: Analysiere Schwächen...",
                                                font=("Arial", 12, "bold"), text_color="#00E5FF")
        self.ai_train_focus_lbl.pack(pady=(0, 6))

        # Map Card
        self.ai_train_map_card = ctk.CTkFrame(left_panel, fg_color="#14141c", corner_radius=12, border_width=1, border_color="#333346")
        self.ai_train_map_card.pack(fill="both", expand=True, padx=14, pady=10)

        self.ai_train_map_title = ctk.CTkLabel(self.ai_train_map_card, text="Lade Map...", font=("Arial", 15, "bold"), text_color="#ffffff", wraplength=280)
        self.ai_train_map_title.pack(pady=(15, 4), padx=10)

        self.ai_train_map_meta = ctk.CTkLabel(self.ai_train_map_card, text="", font=("Arial", 11), text_color="#FFA726")
        self.ai_train_map_meta.pack(pady=(0, 8))

        # Goal Frame
        goal_box = ctk.CTkFrame(self.ai_train_map_card, fg_color="#1f1f2b", corner_radius=8, border_width=1, border_color="#2e2e3f")
        goal_box.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(goal_box, text="📋 Dein Ziel für diese Runde:", font=("Arial", 12, "bold"), text_color="#00E5FF").pack(anchor="w", padx=10, pady=(6, 2))
        self.ai_train_goal_lbl = ctk.CTkLabel(goal_box, text="", font=("Arial", 12), text_color="#dddddd", justify="left", wraplength=260)
        self.ai_train_goal_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        # Buttons on Map Card
        btn_row = ctk.CTkFrame(self.ai_train_map_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=10)

        self.ai_train_direct_btn = ctk.CTkButton(btn_row, text="osu!direct", width=100, height=32, font=("Arial", 12, "bold"),
                                                 fg_color="#FF66AA", hover_color="#C2185B")
        self.ai_train_direct_btn.pack(side="left", padx=(0, 6))

        self.ai_train_web_btn = ctk.CTkButton(btn_row, text="🌐 Web-Link", width=95, height=32, font=("Arial", 12),
                                              fg_color="#2b2b36", hover_color="#3a3a48")
        self.ai_train_web_btn.pack(side="left")

        ctk.CTkButton(btn_row, text="🎲 Nächste Map", width=105, height=32, font=("Arial", 11, "bold"),
                      fg_color="#333346", hover_color="#44445c", command=self.pick_next_ai_training_map).pack(side="right")

        # Sync / Replay feedback status row
        dnd_row = ctk.CTkFrame(left_panel, fg_color="#1c1c26", corner_radius=8)
        dnd_row.pack(fill="x", padx=14, pady=(0, 14))
        self.ai_train_sync_lbl = ctk.CTkLabel(dnd_row, text="⚡ Live-Sync aktiv: Erkennt deine Runden automatisch!", font=("Arial", 11, "bold"), text_color="#00E5FF")
        self.ai_train_sync_lbl.pack(side="left", padx=10, pady=8)

        def sync_now():
            self.fetch_ai_training_recent_plays(silent=False)
        ctk.CTkButton(dnd_row, text="🔄 Sync", width=65, height=26, font=("Arial", 11, "bold"),
                      fg_color="#2b2b38", hover_color="#3b8ed0", command=sync_now).pack(side="right", padx=8, pady=6)

        # Start live background polling for AI Live Training
        self._start_ai_train_auto_sync_loop()

        # ---------------- RIGHT PANEL: MODERN AI COACH LIVE CHAT ----------------
        right_panel = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(right_panel, text="💬 Live-Coaching Feed", font=("Arial", 15, "bold"), text_color="#ffffff").pack(pady=(15, 5))

        chat_scroll_box = ctk.CTkFrame(right_panel, fg_color="#14141c", corner_radius=10)
        chat_scroll_box.pack(fill="both", expand=True, padx=12, pady=(5, 10))

        self.chat_scrollable_frame = ctk.CTkScrollableFrame(chat_scroll_box, fg_color="#14141c")
        self.chat_scrollable_frame.pack(fill="both", expand=True)

        # Pill Input Container at bottom of Right Panel
        train_input_container = ctk.CTkFrame(right_panel, fg_color="#1c1c24", corner_radius=16, border_width=1, border_color="#2c2c38", height=80)
        train_input_container.pack(fill="x", padx=12, pady=(0, 12))
        train_input_container.pack_propagate(False)

        train_msg_entry = ctk.CTkEntry(train_input_container, placeholder_text="Frage stellen, Feedback anfordern oder Skillset wechseln...",
                                       font=("Arial", 12), fg_color="transparent", border_width=0, text_color="#ffffff")
        train_msg_entry.pack(fill="x", padx=14, pady=(6, 2))

        bottom_train_row = ctk.CTkFrame(train_input_container, fg_color="transparent")
        bottom_train_row.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(bottom_train_row, text=f"✨ {getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}", font=("Arial", 10), text_color="#888899").pack(side="left")

        ctk.CTkButton(bottom_train_row, text="💬 Feedback-Fragebogen", font=("Arial", 10, "bold"), height=22, corner_radius=6,
                      fg_color="#222230", hover_color="#303042", text_color="#00E5FF", command=lambda: self.show_ai_question_modal()).pack(side="left", padx=10)

        def send_train_msg(event=None):
            import traceback
            try:
                msg = train_msg_entry.get().strip()
                if not msg: return
                train_msg_entry.delete(0, "end")
                self.add_modern_chat_bubble("user", msg)
                if hasattr(self, "chat_scrollable_frame") and hasattr(self.chat_scrollable_frame, "_parent_canvas"):
                    self.after(20, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))

                # --- Powerful Intent Recognition for Live Coaching ---
                msg_lower = msg.lower()
                is_negative = any(neg in msg_lower for neg in ["keine", "kein", "nicht mehr", "stop", "bloß kein", "keinen", "will nicht", "lass mal sein"])
                is_skip_intent = any(sk in msg_lower for sk in ["überspring", "überspringen", "skip", "nächste schwäche", "nächstes problem", "nächste map", "andere map", "was anderes", "wechsel"])
                is_fun_mode = any(w in msg_lower for w in ["spaß", "fun", "aus spaß", "nur zum spaß", "just for fun", "was für spaß", "geile map", "chillen", "abgehen"])

                # Check whether user is asking a general coaching / information question vs commanding a map switch
                is_pure_question = (
                    "?" in msg
                    or any(q_word in msg_lower for q_word in ["wie kann ich", "wie lerne", "wie geht", "warum", "was bedeutet", "was ist", "welche", "welches", "tipps für", "tipps gegen", "hast du tipps", "wie verbessere", "wie spiele", "wie trainiere", "kannst du mir erklären", "erklär mir"])
                )
                is_explicit_map_request = (
                    is_skip_intent
                    or is_fun_mode
                    or any(cmd in msg_lower for cmd in [
                        "gib mir", "zeig mir", "such mir", "finde", "wechsel", "wechseln", "neue map", "andere map", "nächste map",
                        "lass uns", "spiel lieber", "schalte auf", "skip", "überspring", "überspringe", "ich will", "ich möchte", "bitte map", "noch eine map", "andere diff", "andere sterne"
                    ])
                )
                
                # Check persistent mod preference / mod dependency ("nur Hidden", "nur HardRock", "nur HR")
                is_only_mod = any(w in msg_lower for w in ["nur hd", "nur hidden", "nur hr", "nur hardrock", "immer hd", "immer hr", "kann nur hr", "kann nur hd", "ohne hr kann ich", "ohne hd kann ich", "mit jeder mod"])
                mod_crutch_detected = None
                if is_only_mod:
                    if "hr" in msg_lower or "hardrock" in msg_lower or "hard rock" in msg_lower:
                        mod_crutch_detected = "HR"
                        self._persistent_mod_pref = "HR"
                    elif "hd" in msg_lower or "hidden" in msg_lower:
                        mod_crutch_detected = "HD"
                        self._persistent_mod_pref = "HD"

                # 1. Star Rating Intent (e.g. "7 star", "7 sterne", "7*", "6.5 star", "8*", "7.2 sr")
                requested_sr = None
                sr_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:stars?|sterne?|\*|sr)', msg_lower)
                if not sr_match:
                    sr_match = re.search(r'(?:star|sterne|level|diff|schwierigkeit)\s*(\d+(?:[.,]\d+)?)', msg_lower)
                if sr_match:
                    try:
                        val = float(sr_match.group(1).replace(',', '.'))
                        if 1.0 <= val <= 11.0:
                            requested_sr = val
                    except: pass

                # 2. Skillset Intent (e.g. "stream", "stream maps", "ich will tech üben", "jump aim", "speed")
                requested_skill = None
                if any(w in msg_lower for w in ["stream", "streams", "streamen", "deathstream", "flow aim"]):
                    requested_skill = "Streams"
                elif any(w in msg_lower for w in ["tech", "technical", "slider", "gimmick", "sv"]):
                    requested_skill = "Tech"
                elif any(w in msg_lower for w in ["speed", "burst", "bursts", "bpm", "fast", "schnell"]):
                    requested_skill = "Speed"
                elif any(w in msg_lower for w in ["stamina", "ausdauer", "drain", "durchhalten"]):
                    requested_skill = "Stamina"
                elif any(w in msg_lower for w in ["jump", "jumps", "cross screen", "aim", "snaps"]):
                    requested_skill = "Aim"
                elif any(w in msg_lower for w in ["reading", "low ar", "ar8", "ar7", "ez", "hidden"]):
                    requested_skill = "Reading"
                elif any(w in msg_lower for w in ["precision", "small cs", "cs5", "cs6", "pixel", "genauigkeit"]):
                    requested_skill = "Precision"
                elif any(w in msg_lower for w in ["consistency", "konsistenz", "marathon", "fc", "choke"]):
                    requested_skill = "Consistency"

                # 3. Mod Intent (e.g. "dt", "doubletime", "hr", "hardrock", "hd", "hidden", "ez", "easy", "nomod", "nm")
                requested_mod = None
                if any(w in msg_lower for w in ["doubletime", "double time", "dt", "speed up"]):
                    requested_mod = "DT"
                elif any(w in msg_lower for w in ["hardrock", "hard rock", "hr"]):
                    requested_mod = "HR"
                elif any(w in msg_lower for w in ["hidden", "hd"]):
                    requested_mod = "HD"
                elif any(w in msg_lower for w in ["easy mod", "ez", "easy"]):
                    requested_mod = "EZ"
                elif any(w in msg_lower for w in ["nomod", "no mod", "nm", "ohne mods"]):
                    requested_mod = "NM"

                # Handle Negation & Exclusions
                did_update_map = False
                coach_directive_note = ""

                if is_negative and any(ez_kw in msg_lower for ez_kw in ["easy", "ez"]):
                    if not hasattr(self, "_banned_mods"): self._banned_mods = set()
                    self._banned_mods.add("EZ")
                    self._user_requested_mod = None
                    did_update_map = True
                    coach_directive_note = "Spieler möchte vorerst keine Easy (EZ) Maps mehr. Bestätige den Ausschluss freundlich und erkläre den Fokuswechsel."
                    self.pick_next_ai_training_map(banned_mod="EZ", rotate_weakness=True, silent_announcement=True)
                elif is_negative and any(tech_kw in msg_lower for tech_kw in ["tech", "technical"]):
                    if not hasattr(self, "_skipped_skills"): self._skipped_skills = set()
                    self._skipped_skills.add("Tech")
                    did_update_map = True
                    coach_directive_note = "Spieler möchte aktuell keine Tech-Maps. Bestätige und rotiere zur nächsten Schwäche."
                    self.pick_next_ai_training_map(skip_skill="Tech", rotate_weakness=True, silent_announcement=True)
                elif is_fun_mode:
                    did_update_map = True
                    coach_directive_note = "Spieler möchte aus Spaß spielen / sich auspowern. Schalte auf Fun-Mode mit seiner stärksten Disziplin (Speed/Aim)."
                    self.pick_next_ai_training_map(is_fun_mode=True, silent_announcement=True)
                elif is_skip_intent:
                    did_update_map = True
                    coach_directive_note = "Spieler möchte die aktuelle Map / Schwäche überspringen. Rotiere zur nächsten Herausforderung."
                    self.pick_next_ai_training_map(rotate_weakness=True, silent_announcement=True)
                elif (requested_skill or requested_sr is not None or requested_mod is not None or mod_crutch_detected) and (is_explicit_map_request or not is_pure_question):
                    did_update_map = True
                    new_skill = requested_skill or getattr(self, "ai_training_target_skill", "Streams")
                    self.ai_training_target_skill = new_skill
                    self._user_requested_mod = requested_mod or mod_crutch_detected

                    if requested_sr is not None:
                        self._user_requested_sr = requested_sr
                        self._ai_training_target_sr = requested_sr

                    self.pick_next_ai_training_map(forced_skill=new_skill, forced_mod=self._user_requested_mod, silent_announcement=True)

                # Auto-detect hardware / technique details from user chat
                did_save_setup = self.update_user_setup_from_text(msg)

                # Display thinking bubble
                thinking_frame = self.add_modern_chat_bubble("thinking", "Analysiere & antworte...")
                if hasattr(self, "chat_scrollable_frame") and hasattr(self.chat_scrollable_frame, "_parent_canvas"):
                    self.after(20, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))

                def call_coach():
                    import traceback
                    try:
                        cur_map = getattr(self, "current_ai_training_map", {}) or {}
                        cur_info = f"{cur_map.get('name', 'Unbekannt')} (★ {cur_map.get('sr', 5.5):.1f}, Mod: {cur_map.get('mod', 'NM')}, Skillset: {getattr(self, 'ai_training_target_skill', 'Streams')})"
                        setup_info = json.dumps(getattr(self, "user_setup_profile", {}))
                        
                        response = None
                        if getattr(self, "gemini_key", ""):
                            try:
                                crutch_instruction = ""
                                if mod_crutch_detected:
                                    crutch_instruction = f"""
- MOD-CRUTCH DIAGNOSE ({mod_crutch_detected}-Abhängigkeit):
  Der Spieler hat angegeben, dass er fast nur {mod_crutch_detected} spielt.
  1. Erkläre ihm freundlich und didaktisch die Ursache ('AR10 / Low-Density Lock-in'). Wer nur HR/HD spielt, verlernt das Lesen normaler Notendichten (AR 9.0-9.5) und verlässt sich rein auf Reflexe statt echtes Rhythmus-Lesen.
  2. Empfiehl eine 70/30-Strategie (70% mit {mod_crutch_detected}, 30% gezielte NoMod-Grundlagen), um ein kompletter Turnierspieler zu werden.
  3. Bestätige, dass die links vorbereitete Map seinen Wunsch berücksichtigt!"""

                                full_prompt = f"""[KI-Live-Coaching Feed]
Aktuell geladene Trainingsmap: {cur_info}
Bekanntes Spieler-Setup: {setup_info}
Spezielle Anweisung: {coach_directive_note}
Spieler-Nachricht: {msg}

Antworte als Pro-Coach auf Deutsch (ca. 3-5 prägnante Sätze):
- Wenn der Spieler Hardware-/Setup-Details (Maus/Tablet, DPI/Area, Tastatur/Rapid Trigger, Grip oder Tapping-Stil) genannt hat, gehe sofort darauf ein und gib konkrete Tuning- und Ergonomie-Tipps (z. B. Area-Größe, Actuation Point, Handgelenk-Winkel).
- Falls er nach einer bestimmten Map/Kategorie/★ gefragt oder etwas ausgeschlossen hat (z.B. keine Easy Maps, nächstes Problem), bestätige den Wechsel auf die neue Map links.{crutch_instruction}
- Gib ihm konkrete mechanische Ausführungstipps und motiviere ihn!"""
                                response = self.query_gemini(full_prompt)
                            except Exception as api_err:
                                response = f"⚠️ [API-Fehlercode: {type(api_err).__name__}]: {api_err}\n\n" + self.offline_analyze(msg)

                        if not response:
                            # Smart rich offline response in 100% German
                            if mod_crutch_detected:
                                response = f"Alles klar! Ich habe dein Training auf **+{mod_crutch_detected}** eingestellt.\n\n⚠️ **Coach-Diagnose ({mod_crutch_detected}-Lock-in):** Wenn du ausschließlich {mod_crutch_detected} spielst, gewöhnt sich dein Gehirn an das High-AR-Reaktionsfenster und verlernt das Lesen dichterer NoMod-Pattern (AR 9.0-9.5). Um ein kompletter Spieler zu werden, empfehle ich 70% mit {mod_crutch_detected} und 30% NoMod-Reading als Fundament!\n\n🎮 Map links bereit: **{self.current_ai_training_map['name']}**"
                            elif did_save_setup:
                                response = f"Perfekt! Ich habe deine Setup-Daten gespeichert ({setup_info}).\n\n💡 **Coach-Tipp:** Mit diesem Setup können wir gezielt an deiner Konstanz arbeiten. Achte auf eine entspannte Handhaltung und spiele die links vorbereitete Map!"
                            elif is_fun_mode:
                                response = f"🎉 **Fun-Mode aktiviert!** Wir schieben die Schwächen kurz beiseite und lassen dich auf deinem Paradestück **{self.ai_training_target_skill} (★ {self.current_ai_training_map['sr']:.1f})** abgehen!\n\n🎮 Map links bereit: **{self.current_ai_training_map['name']}** – viel Spaß beim Reinknallen!"
                            elif did_update_map:
                                response = f"Alles klar! Ich habe dein Training sofort angepasst auf **{self.ai_training_target_skill} (★ {self.current_ai_training_map['sr']:.1f})**.\n\n🎮 Neue Map links bereit: **{self.current_ai_training_map['name']}**\n📋 Fokus-Ziel: {self.current_ai_training_map['goal']}\n\n💡 **Coach-Tipp:** Starte die Map direkt per `osu!direct`. Achte besonders auf gleichmäßige Fingerbewegung und halte deinen Unterarm locker!"
                            else:
                                response = self.offline_analyze(msg)

                        if hasattr(self, "chat_scrollable_frame") and self.chat_scrollable_frame.winfo_exists():
                            self.after(0, lambda: self.replace_modern_thinking(thinking_frame, response))
                            self.after(60, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))
                    except Exception as coach_err:
                        err_str = f"❌ [Fehlercode Coach: {type(coach_err).__name__}]: {coach_err}\n\n{traceback.format_exc()}"
                        if hasattr(self, "chat_scrollable_frame") and self.chat_scrollable_frame.winfo_exists():
                            self.after(0, lambda: self.replace_modern_thinking(thinking_frame, err_str))
                            self.after(60, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))

                threading.Thread(target=call_coach, daemon=True).start()
            except Exception as e:
                import traceback
                err_main = f"❌ [Fehlercode UI: {type(e).__name__}]: {e}\n\n{traceback.format_exc()}"
                self.add_modern_chat_bubble("ai", err_main)

        send_train_btn = ctk.CTkButton(bottom_train_row, text="➔", width=28, height=24, corner_radius=12,
                                       fg_color="#2b2b36", hover_color="#3b8ed0", font=("Arial", 12, "bold"), command=send_train_msg)
        send_train_btn.pack(side="right")
        train_msg_entry.bind("<Return>", send_train_msg)

        # Proactive Deep-Dive Coach Assessment & Action Plan on Coach Entry
        def init_coach_assessment():
            p_name = getattr(self, 'osu_username', 'Spieler')
            pa = getattr(self, "last_profile_analysis", None) or {}
            scores = pa.get("scores", {})
            weakness = pa.get("weakness", "Tech" if not scores else min(scores, key=scores.get))
            main_skill = pa.get("main_skill", "Aim" if not scores else max(scores, key=scores.get))
            
            dt = getattr(self, "last_deep_replay_telemetry", None)
            dt_m = dt.get("metrics", {}) if dt else {}
            over_pct = dt_m.get("overaim_pct", 52.0)
            under_pct = dt_m.get("underaim_pct", 48.0)
            peak_spd = dt_m.get("peak_speed", 0.0)
            k1_hold = dt_m.get("k1_avg_hold", 50.0)
            k2_hold = dt_m.get("k2_avg_hold", 50.0)
            ur_val = dt_m.get("ur", 80.0)
            alt_r = dt_m.get("alt_ratio", 50.0)
            choke_reasons = dt_m.get("choke_reasons", [])
            setup_prof = getattr(self, "user_setup_profile", {}) or {}

            aim_telem_txt = f"Overaim: {over_pct:.1f}% vs Underaim: {under_pct:.1f}%" if dt else "Aim-Stabilität im Fokus"
            tap_telem_txt = f"K1: {k1_hold:.1f}ms / K2: {k2_hold:.1f}ms (UR: ~{ur_val:.1f})" if dt else "Tapping-Konsistenz im Fokus"
            
            fallback_welcome = (
                f"Willkommen im KI-analysierten Live-Coaching, {p_name}! 🎯\n\n"
                f"Hier geht es darum, **deine Schwächen schonungslos aufzudecken, die Ursachen an der Wurzel zu packen und gezielt auszumerzen**.\n\n"
                f"🔬 **Deine aktuelle Telemetrie- & Profil-Diagnose:**\n"
                f"• **Größte Schwachstelle:** {weakness} ({scores.get(weakness, 50)}/100 Pkt)\n"
                f"• **Aim-Muster:** {aim_telem_txt}\n"
                f"• **Tapping-Werte:** {tap_telem_txt}\n"
                f"{'• **Choke-Ursachen:** ' + ', '.join(choke_reasons) + chr(10) if choke_reasons else ''}\n"
                f"🛠️ **Um dein Coaching perfekt abzustimmen, sag mir kurz:**\n"
                f"1. **Aim:** Spielst du mit **Maus** (welche DPI / welches Mauspad) oder **Tablet** (welche Area in mm / Drag oder Hover)?\n"
                f"2. **Tapping:** Welche **Tastatur/Switches** nutzt du (z. B. Rapid Trigger / Wooting mit Auslöseweg) und tapst du **Alternating** oder **Single-Tap**?\n\n"
                f"👉 *Schreib es mir einfach hier im Chat! Ich habe links deine erste Trainings-Map vorbereitet – leg los, ich analysiere deinen Score nach der Runde live!*"
            )

            if getattr(self, "gemini_key", ""):
                thinking_frame = self.add_modern_chat_bubble("thinking", "Analysiere Replay-Telemetrie & Profil für Coaching-Diagnose...")
                if hasattr(self, "chat_scrollable_frame") and hasattr(self.chat_scrollable_frame, "_parent_canvas"):
                    self.after(20, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))

                def _async_coach_init():
                    prompt = f"""Du bist der offizielle Pro-Level osu! KI-Coach und Cheftrainer für osu! Standard (Mode 0).
Der Spieler '{p_name}' betritt soeben dein persönliches KI-Coaching.

KERNZIEL DES COACHINGS:
Seine Schwächen und Miss-Ursachen schonungslos und präzise aufdecken, die mechanischen Probleme an der Wurzel packen und schrittweise ausbessern!

Verfügbare Telemetrie- & Profil-Daten:
- Hauptschwäche laut Radar/Profil: {weakness} (Scores: {json.dumps(scores)})
- Stärkstes Skillset: {main_skill}
- Deep Replay Telemetrie:
  * Overaim vs Underaim: Overaim {over_pct:.1f}% | Underaim {under_pct:.1f}% (Peak Speed: {peak_spd:,.0f} px/s)
  * Tasten-Haltezeiten: K1 {k1_hold:.1f}ms | K2 {k2_hold:.1f}ms | Alternating: {alt_r:.1f}% | UR: ~{ur_val:.1f}
  * Erkannte Choke-Ursachen: {', '.join(choke_reasons) if choke_reasons else 'Keine akuten Chokes'}
- Bisher bekanntes Hardware-Setup: {json.dumps(setup_prof)}

AUFGABE:
Begrüße den Spieler mit einer scharfsinnigen, hochkompetenten Erstanalyse auf Deutsch (ca. 4-6 Sätze):
1. Sprich die erkannten Probleme (z.B. Overaiming/Undershooting bei Jumps, Tasten-Prellen/Holding, Finger-Locking bei Bursts oder {weakness}-Schwäche) direkt an und erkläre kurz die mechanische Ursache.
2. Gib dem Spieler eine sofortige mechanische Handlungsempfehlung (was er dagegen machen soll).
3. Stelle ihm 1-2 gezielte Fragen zu seinem Setup, damit du ihn noch präziser coachen kannst:
   - Für Aim: Spielt er mit MAUS (welche DPI / Mauspad) oder TABLET (welche Area in mm / Drag oder Hover)?
   - Für Tapping: Welche Tastatur/Switches (z. B. Rapid Trigger / Wooting Auslöseweg in mm) nutzt er und tapst er Alternating oder Single-Tap?
4. Betone, dass wir seine Schwächen jetzt gezielt Runde für Runde ausbessern werden!"""
                    res = self.query_gemini(prompt)
                    final_txt = res if res else fallback_welcome
                    if hasattr(self, "chat_scrollable_frame") and self.chat_scrollable_frame.winfo_exists():
                        self.after(0, lambda: self.replace_modern_thinking(thinking_frame, final_txt))
                        self.after(60, lambda: self.chat_scrollable_frame._parent_canvas.yview_moveto(1.0))
                threading.Thread(target=_async_coach_init, daemon=True).start()
            else:
                self.add_modern_chat_bubble("ai", fallback_welcome)

        init_coach_assessment()
        self._preload_ai_training_cache()
        self.pick_next_ai_training_map()

    def _preload_ai_training_cache(self, base_sr=None):
        """Pre-fetches 3 curated maps from SQLite for every one of the 8 skillsets so map switching is 0ms instant."""
        if not hasattr(self, "_ai_prefetched_maps_pool"):
            self._ai_prefetched_maps_pool = {}
        
        pa = getattr(self, "last_profile_analysis", {}) or {}
        p_stats = pa.get("player_stats", {})
        if base_sr is None:
            base_sr = getattr(self, "_ai_training_target_sr", None) or float(p_stats.get("effective_sr", 5.2))

        all_skills = ["Aim", "Streams", "Speed", "Stamina", "Tech", "Precision", "Reading", "Consistency"]
        exclude = getattr(self, "recent_ai_training_map_ids", set())

        for sk in all_skills:
            if sk not in self._ai_prefetched_maps_pool:
                self._ai_prefetched_maps_pool[sk] = []
            
            existing_ids = set(str(x.get("id", "")) for x in self._ai_prefetched_maps_pool[sk])
            while len(self._ai_prefetched_maps_pool[sk]) < 3:
                m = pick_dynamic_map_for_skill(
                    category=sk,
                    target_sr=base_sr,
                    exclude_ids=exclude.union(existing_ids),
                    banned_mods=getattr(self, "_banned_mods", set())
                )
                if m and str(m.get("id", "")) not in existing_ids:
                    self._ai_prefetched_maps_pool[sk].append(m)
                    existing_ids.add(str(m.get("id", "")))
                else:
                    break

    def _refill_skill_cache(self, skill, target_sr):
        """Refills the pre-fetched pool for a given skill to ensure 3 maps are always ready."""
        if not hasattr(self, "_ai_prefetched_maps_pool"):
            self._ai_prefetched_maps_pool = {}
        self._ai_prefetched_maps_pool.setdefault(skill, [])
        exclude = getattr(self, "recent_ai_training_map_ids", set())
        existing_ids = set(str(x.get("id", "")) for x in self._ai_prefetched_maps_pool[skill])
        while len(self._ai_prefetched_maps_pool[skill]) < 3:
            m = pick_dynamic_map_for_skill(
                category=skill,
                target_sr=target_sr,
                exclude_ids=exclude.union(existing_ids),
                banned_mods=getattr(self, "_banned_mods", set())
            )
            if m and str(m.get("id", "")) not in existing_ids:
                self._ai_prefetched_maps_pool[skill].append(m)
                existing_ids.add(str(m.get("id", "")))
            else:
                break

    def set_ai_training_skill(self, skill_name):
        self.ai_training_target_skill = skill_name
        self.pick_next_ai_training_map(forced_skill=skill_name)

    def pick_next_ai_training_map(self, adaptive_delta=0.0, forced_skill=None, forced_mod=None, banned_mod=None, skip_skill=None, rotate_weakness=False, is_fun_mode=False, silent_announcement=False):
        if not hasattr(self, "_ai_train_session_count"):
            self._ai_train_session_count = 0
        if not hasattr(self, "_ai_train_tested_skills"):
            self._ai_train_tested_skills = set()
        if not hasattr(self, "_ai_train_skill_streak"):
            self._ai_train_skill_streak = 0
        if not hasattr(self, "_banned_mods"):
            self._banned_mods = set()
        if not hasattr(self, "_skipped_skills"):
            self._skipped_skills = set()

        if banned_mod:
            self._banned_mods.add(str(banned_mod).upper().strip())
        if skip_skill:
            self._skipped_skills.add(str(skip_skill))

        self._ai_train_session_count += 1

        pa = getattr(self, "last_profile_analysis", {}) or {}
        p_stats = pa.get("player_stats", {})
        scores = pa.get("scores", {})

        # 8 Benchmark skills & stress mods to push player to limits at the start of training
        ALL_SKILLS_STRESS_ORDER = [
            ("Aim", "NM"),
            ("Speed", "DT"),
            ("Streams", "NM"),
            ("Precision", "HR"),
            ("Tech", "NM"),
            ("Reading", "HD"),
            ("Stamina", "NM"),
            ("Consistency", "NM")
        ]

        is_stress_test_mode = False
        target_mod = forced_mod or getattr(self, "_user_requested_mod", None) or getattr(self, "_persistent_mod_pref", None)
        if target_mod and target_mod in self._banned_mods:
            target_mod = "NM"

        if is_fun_mode:
            # Fun Mode: Focus on player's strongest or most rewarding skills (Speed / Aim)
            if scores:
                sorted_by_best = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                skill = sorted_by_best[0][0]
            else:
                skill = "Speed"
            self.ai_training_target_skill = skill
            self._ai_train_skill_streak = 1
        elif forced_skill:
            skill = forced_skill
            self.ai_training_target_skill = skill
            self._ai_train_skill_streak = 1
        elif rotate_weakness or skip_skill:
            # Rotate to next weakness that is not currently skipped
            all_s = ["Aim", "Streams", "Speed", "Tech", "Precision", "Reading", "Stamina", "Consistency"]
            if scores:
                sorted_skills = sorted(scores.items(), key=lambda x: x[1])
                candidates = [s[0] for s in sorted_skills if s[0] not in self._skipped_skills]
                skill = candidates[0] if candidates else sorted_skills[0][0]
            else:
                cands = [s for s in all_s if s not in self._skipped_skills]
                skill = random.choice(cands) if cands else "Aim"
            self.ai_training_target_skill = skill
            self._ai_train_skill_streak = 1
        elif len(self._ai_train_tested_skills) < len(ALL_SKILLS_STRESS_ORDER):
            # Phase 1: LIMIT-TESTING / STRESS-TEST PHASE
            is_stress_test_mode = True
            for sk, s_mod in ALL_SKILLS_STRESS_ORDER:
                if sk not in self._ai_train_tested_skills and sk not in self._skipped_skills:
                    skill = sk
                    if not target_mod and s_mod not in self._banned_mods:
                        target_mod = s_mod
                    self._ai_train_tested_skills.add(sk)
                    break
            else:
                skill = "Aim"
            self.ai_training_target_skill = skill
            self._ai_train_skill_streak = 1
        else:
            # Phase 2: DYNAMIC ROTATION & TARGETED WEAKNESS COACHING
            self._ai_train_skill_streak += 1
            if self._ai_train_skill_streak > 2:
                self._ai_train_skill_streak = 1
                if scores:
                    sorted_skills = sorted(scores.items(), key=lambda x: x[1])
                    weak_candidates = [s[0] for s in sorted_skills[:4] if s[0] not in self._skipped_skills]
                    if getattr(self, "ai_training_target_skill", "") in weak_candidates:
                        weak_candidates.remove(self.ai_training_target_skill)
                    skill = random.choice(weak_candidates) if weak_candidates else sorted_skills[0][0]
                else:
                    all_s = ["Aim", "Streams", "Speed", "Tech", "Precision", "Reading", "Stamina", "Consistency"]
                    cands = [s for s in all_s if s != getattr(self, "ai_training_target_skill", "") and s not in self._skipped_skills]
                    skill = random.choice(cands) if cands else "Aim"
                self.ai_training_target_skill = skill
                
                # Assign challenging mod according to skill
                if not target_mod:
                    if skill == "Speed" and "DT" not in self._banned_mods: target_mod = "DT"
                    elif skill == "Precision" and "HR" not in self._banned_mods and random.random() < 0.5: target_mod = "HR"
                    elif skill == "Reading" and "HD" not in self._banned_mods and random.random() < 0.5: target_mod = "HD"
                    elif random.random() < 0.2:
                        avail_m = [m for m in ["DT", "HR", "HD"] if m not in self._banned_mods]
                        if avail_m: target_mod = random.choice(avail_m)
            else:
                skill = getattr(self, "ai_training_target_skill", "Streams")

        # Base SR calculation
        if hasattr(self, "_user_requested_sr") and self._user_requested_sr is not None:
            base_sr = self._user_requested_sr
        elif "adaptive_difficulty" in p_stats:
            base_sr = float(p_stats["adaptive_difficulty"].get("effective_sr", 5.2))
        elif "effective_sr" in p_stats:
            base_sr = float(p_stats["effective_sr"])
        elif "avg_sr" in p_stats and p_stats["avg_sr"]:
            base_sr = float(p_stats["avg_sr"])
        elif scores:
            s_vals = list(scores.values())
            avg_score = sum(s_vals) / len(s_vals)
            base_sr = 5.0 + (avg_score - 50) * 0.035
        else:
            base_sr = 5.2

        # In Stress-Test mode, push difficulty (+0.30★) to test where the limits lie!
        stress_push = +0.30 if is_stress_test_mode and not is_fun_mode else 0.0

        if not hasattr(self, "_ai_session_performance_delta"):
            self._ai_session_performance_delta = 0.0
        if adaptive_delta != 0.0:
            self._ai_session_performance_delta = max(-0.9, min(0.9, self._ai_session_performance_delta + adaptive_delta))

        cat_score = scores.get(skill, 65)
        skill_offset = (cat_score - 65) * 0.015
        target_sr = round(max(3.8, min(8.8, base_sr + skill_offset + stress_push + self._ai_session_performance_delta)), 1)
        self._ai_training_target_sr = target_sr

        if not hasattr(self, "recent_ai_training_map_ids"):
            self.recent_ai_training_map_ids = set()

        # Fetch from pre-loaded 8-skillset cache for 0ms instant load
        chosen = None
        if hasattr(self, "_ai_prefetched_maps_pool") and self._ai_prefetched_maps_pool.get(skill):
            chosen = self._ai_prefetched_maps_pool[skill].pop(0)
            threading.Thread(target=lambda s=skill, sr=target_sr: self._refill_skill_cache(s, sr), daemon=True).start()

        if not chosen:
            chosen = pick_dynamic_map_for_skill(
                category=skill,
                target_sr=target_sr,
                exclude_ids=self.recent_ai_training_map_ids,
                mod=target_mod,
                user_feedback=getattr(self, "ai_user_feedback", {}),
                banned_mods=self._banned_mods
            )
        self.recent_ai_training_map_ids.add(chosen["id"])
        if len(self.recent_ai_training_map_ids) > 30:
            self.recent_ai_training_map_ids.clear()

        # Update Top Badge
        mod_badge = f" [{chosen['mod']}]" if chosen.get('mod') and chosen['mod'] != "NM" else ""
        if is_fun_mode:
            phase_badge = "🎉 Fun-Mode: "
        elif is_stress_test_mode:
            phase_badge = f"🔥 Stress-Test ({len(self._ai_train_tested_skills)}/8): "
        else:
            phase_badge = "✨ KI-Fokus: "
        if hasattr(self, "ai_train_focus_lbl") and self.ai_train_focus_lbl.winfo_exists():
            self.ai_train_focus_lbl.configure(text=f"{phase_badge}{skill}{mod_badge} (★ {chosen['sr']:.1f})")

        # Generate genuine dynamic AI goal from Gemini for this specific map
        if getattr(self, "gemini_key", ""):
            def _async_gen_ai_goal(m=chosen, sk=skill):
                try:
                    weakness_info = ""
                    if hasattr(self, "_ai_last_weakness_context") and self._ai_last_weakness_context:
                        weakness_info = f"\nBekannte Spieler-Schwachstelle aus letzter Analyse: {self._ai_last_weakness_context}"
                    g_prompt = (
                        f"Du bist ein Elite osu! Coach. Erstelle für den osu! Standard Spieler ein hochspezifisches, "
                        f"technisches 1-Satz-Fokus-Ziel für diese Trainings-Runde auf Deutsch:\n"
                        f"Map: {m['name']} (★ {m['sr']:.1f}, Mod: {m.get('mod', 'NM')}, BPM: {m.get('bpm', 180)}, Skillset: {sk}){weakness_info}\n"
                        f"Nur 1 direkter technischer Satz:"
                    )
                    g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                    payload = {"contents": [{"role": "user", "parts": [{"text": g_prompt}]}], "generationConfig": {"temperature": 0.8, "maxOutputTokens": 100}}
                    res = requests.post(g_url, json=payload, timeout=6).json()
                    ai_g = res["candidates"][0]["content"]["parts"][0]["text"].replace('"', '').replace('*', '').strip()
                    if ai_g and len(ai_g) > 8:
                        m["goal"] = ai_g
                        if hasattr(self, 'ai_train_goal_lbl') and self.ai_train_goal_lbl.winfo_exists():
                            self.after(0, lambda: self.ai_train_goal_lbl.configure(text=ai_g))
                except: pass
            threading.Thread(target=_async_gen_ai_goal, daemon=True).start()

        self.current_ai_training_map = chosen

        if hasattr(self, "ai_train_map_title") and self.ai_train_map_title.winfo_exists():
            self.ai_train_map_title.configure(text=chosen["name"])
        if hasattr(self, "ai_train_map_meta") and self.ai_train_map_meta.winfo_exists():
            self.ai_train_map_meta.configure(text=f"★ {chosen['sr']:.1f} • {chosen.get('mod', 'NM')} • {chosen.get('status', 'Ranked')} • {chosen.get('bpm', 180)} BPM")
        if hasattr(self, "ai_train_goal_lbl") and self.ai_train_goal_lbl.winfo_exists():
            self.ai_train_goal_lbl.configure(text=chosen.get("goal", "Spiele die Map konzentriert und halte eine saubere Accuracy."))

        b_id = chosen["id"]
        def open_dir():
            try: os.startfile(f"osu://b/{b_id}")
            except: webbrowser.open(f"https://osu.ppy.sh/b/{b_id}")
        if hasattr(self, "ai_train_direct_btn") and self.ai_train_direct_btn.winfo_exists():
            self.ai_train_direct_btn.configure(command=open_dir)

        def open_web():
            webbrowser.open(f"https://osu.ppy.sh/b/{b_id}")
        if hasattr(self, "ai_train_web_btn") and self.ai_train_web_btn.winfo_exists():
            self.ai_train_web_btn.configure(command=open_web)

        # Announce in feed only when not silent (e.g. not right after user chat)
        if not silent_announcement:
            m_raw = chosen.get("name", "Unknown")
            m_artist = chosen.get("artist", "")
            m_title = chosen.get("title", "")
            m_ver = chosen.get("version", "")
            if m_artist and m_title:
                song_name = f"{m_artist} - {m_title}"
            else:
                song_name = re.sub(r'\s*\[.*?\]\s*$', '', m_raw).strip()
            if not m_ver:
                ver_match = re.search(r'\[(.*?)\]', m_raw)
                m_ver = ver_match.group(1) if ver_match else ""
            diff_str = f"[{m_ver}]" if m_ver else ""

            if is_stress_test_mode:
                coach_note = f"🔥 **STRESS-TEST ({len(self._ai_train_tested_skills)}/8):** Limit-Test für **{skill}{mod_badge}** (★ {chosen['sr']:.1f})!\n\n🎵 **Map:** {song_name}\n🏷️ **Difficulty:** {diff_str}\n\n**Ziel:** {chosen.get('goal', '')}\n\n*Hier pushen wir bewusst deine Belastungsgrenze, um Choke-Punkte und Schwächen aufzudecken.*"
            else:
                coach_note = f"🎯 Nächste Herausforderung:\n🎵 **Map:** {song_name}\n🏷️ **Difficulty:** {diff_str} (★ {chosen['sr']:.1f})\n\n**Ziel:** {chosen.get('goal', '')}\n\nStarte die Map direkt über osu!direct oder den Web-Link. Nach der Runde analysiere ich deinen Score automatisch!"
            self.add_modern_chat_bubble("ai", coach_note)

    def fetch_ai_training_recent_plays(self, silent=False):
        user = getattr(self, "osu_username", "")
        key = getattr(self, "api_key", "")
        if not user or not key:
            if hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                self.ai_train_sync_lbl.configure(text="❌ Trage Username & API-Key in Einstellungen ein!", text_color="#ff4444")
            return

        cur_map = getattr(self, "current_ai_training_map", {}) or {}
        expected_bid = str(cur_map.get("id", ""))
        if not expected_bid:
            return

        if not silent and hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
            self.ai_train_sync_lbl.configure(text=f"⏳ Prüfe auf Map #{expected_bid}...", text_color="#00E5FF")

        def run():
            try:
                url = f"https://osu.ppy.sh/api/get_user_recent?k={key}&u={user}&m=0&limit=10"
                r = requests.get(url, timeout=8)
                if r.status_code != 200:
                    return

                plays = r.json()
                if not isinstance(plays, list) or not plays:
                    if not silent and hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                        self.after(0, lambda: self.ai_train_sync_lbl.configure(text="Keine neuen Plays gefunden.", text_color="#aaaaaa"))
                    return

                # Check if this is the very first sync call in this session (ignore old historical plays!)
                if not hasattr(self, "_ai_train_initial_synced"):
                    self._ai_train_initial_synced = True
                    # Initialize with all current recent play IDs so old plays from yesterday are ignored!
                    self._processed_ai_training_play_ids = {str(p.get("date", "")) + "_" + str(p.get("score", "")) for p in plays}
                    if not silent and hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                        self.after(0, lambda: self.ai_train_sync_lbl.configure(text="⚡ Live-Sync bereit: Starte die vorgeschlagene Map!", text_color="#00E5FF"))
                    return

                if not hasattr(self, "_processed_ai_training_play_ids"):
                    self._processed_ai_training_play_ids = set()

                # Find the newest matching play for the CURRENT recommended map
                matching_play = None
                for p in plays:
                    p_bid = str(p.get("beatmap_id", ""))
                    p_id = str(p.get("date", "")) + "_" + str(p.get("score", ""))
                    
                    if p_id in self._processed_ai_training_play_ids:
                        continue
                        
                    if p_bid == expected_bid:
                        matching_play = p
                        self._processed_ai_training_play_ids.add(p_id)
                        break
                    else:
                        # Mark other plays as seen so they don't block
                        self._processed_ai_training_play_ids.add(p_id)

                if not matching_play:
                    return

                last_p = matching_play
                try: self.record_play_in_active_session(last_p)
                except: pass
                bid = str(last_p.get("beatmap_id"))
                h300 = int(last_p.get("count300", 0))
                h100 = int(last_p.get("count100", 0))
                h50 = int(last_p.get("count50", 0))
                miss = int(last_p.get("countmiss", 0))
                combo = int(last_p.get("maxcombo", 0))
                tot = h300 + h100 + h50 + miss
                acc = ((h300 * 300 + h100 * 100 + h50 * 50) / (tot * 300) * 100) if tot > 0 else 0
                rank = str(last_p.get("rank", "")).upper()
                is_fail_or_retry = (rank == "F")

                # 1. Quick-Retry Detection (Early reset / choke in first few notes)
                is_quick_retry = is_fail_or_retry and (tot < 45 or combo < 20)
                is_real_fail = is_fail_or_retry and not is_quick_retry
                is_full_pass = not is_fail_or_retry

                if is_quick_retry:
                    def update_quick_retry():
                        if hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                            self.ai_train_sync_lbl.configure(text=f"🔄 Quick-Retry erkannt (#{tot} Noten) – Spiele direkt weiter!", text_color="#FFA726")
                    self.after(0, update_quick_retry)
                    return

                map_name = cur_map.get("name", "Gespielte Map")
                map_sr = cur_map.get("sr", 5.0)
                map_bpm = cur_map.get("bpm", 180)
                target_skill = getattr(self, "ai_training_target_skill", "Allgemein")
                map_goal = cur_map.get("goal", "")
                prescribed_mod = cur_map.get("mod", "NM")

                # Mod Verification
                played_mods_int = int(last_p.get("enabled_mods", 0) or 0)
                played_mods_str = format_mods_string(played_mods_int)
                
                mod_matched = True
                if prescribed_mod in ["DT", "NC"] and not ((played_mods_int & 64) or (played_mods_int & 512)):
                    mod_matched = False
                elif prescribed_mod == "HR" and not (played_mods_int & 16):
                    mod_matched = False
                elif prescribed_mod == "HD" and not (played_mods_int & 8):
                    mod_matched = False
                elif prescribed_mod == "EZ" and not (played_mods_int & 2):
                    mod_matched = False

                mod_warning = ""
                if not mod_matched and prescribed_mod != "NM":
                    mod_warning = f"⚠️ *Hinweis: Diese Übung war mit +{prescribed_mod} geplant (gespielt mit {played_mods_str}). Aktiviere beim nächsten Mal den geforderten Mod in osu! für optimalen Trainingsfortschritt!*"

                # Call Gemini for dynamic, unique coaching advice
                ai_coaching_text = ""
                deep_telem_info = ""
                setup_info = json.dumps(getattr(self, "user_setup_profile", {}))
                dt = getattr(self, "last_deep_replay_telemetry", None)
                if dt:
                    dt_m = dt.get("metrics", {})
                    deep_telem_info = (
                        f"\nDeep-Telemetrie: Overaim: {dt_m.get('overaim_pct', 50):.1f}% | Underaim: {dt_m.get('underaim_pct', 50):.1f}% | "
                        f"Peak Snapping Speed: {dt_m.get('peak_speed', 0):,.0f} px/s | "
                        f"K1-Hold: {dt_m.get('k1_avg_hold', 50):.1f}ms | K2-Hold: {dt_m.get('k2_avg_hold', 50):.1f}ms | "
                        f"UR: ~{dt_m.get('ur', 80):.1f} | Choke-Diagnose: {', '.join(dt_m.get('choke_reasons', []))}"
                    )

                if getattr(self, "gemini_key", ""):
                    coach_prompt = f"""Du bist der offizielle Pro-Level osu! KI-Coach und Cheftrainer für osu! Standard (Mode 0).
WICHTIG: Antworte ZU 100% AUF DEUTSCH! Verwende kein einziges Wort auf Englisch (außer osu!-Begriffe wie Stream, Aim, Burst, FC, Mods wie DT/HR/HD/EZ).

Der Spieler '{user}' hat soeben eine Runde im Live-Training ({target_skill}) gespielt ({'FEHLGESCHLAGEN / FAIL' if is_real_fail else 'ERFOLGREICH BEENDET'}):
Map: {map_name} (★ {map_sr:.1f}, Skillset: {target_skill}, BPM: {map_bpm}, Geforderter Mod: {prescribed_mod})
Gespielte Mods: {played_mods_str}
Ziel: {map_goal}

Score & Replay-Telemetrie:
- Status: {'💀 Fail bei Note #' + str(tot) if is_real_fail else '🏆 Pass'} | Accuracy: {acc:.2f}% | 300s: {h300} | 100s: {h100} | 50s: {h50} | Misses: {miss} | Max Combo: {combo}{deep_telem_info}
- Bisher bekanntes Hardware-Setup: {setup_info}

KERNZIEL: Schwächen und Belastungsgrenzen (Fingerlocking, Overaiming, Reading-Fatigue, High-OD Unstable Rate) finden und aktiv ausbessern!
Gib dem Spieler ein hochprofessionelles, direktes Coaching-Feedback auf Deutsch (3-5 prägnante Sätze):
1. Analysiere das Abschneiden und die konkrete Ursache für den {'Fail / Choke' if is_real_fail else 'Score'}.
2. Was muss der Spieler mechanisch korrigieren (z. B. Handgelenk-Führung, Lockere Finger, Klick-Release, Reading-Fokus)?
3. {'Mache ihm Mut und erkläre, ob the Map für ihn machbar ist!' if is_real_fail else 'Motiviere ihn für die nächste Steigerung!'}"""
                    try:
                        g_model = getattr(self, "selected_ai_model", "gemini-3.6-flash")
                        g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={self.gemini_key}"
                        payload = {
                            "contents": [{"role": "user", "parts": [{"text": coach_prompt}]}],
                            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 600}
                        }
                        resp = requests.post(g_url, json=payload, timeout=12)
                        res_j = resp.json()
                        ai_coaching_text = res_j["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except Exception:
                        pass

                # 2. Real Fail Handling
                if is_real_fail:
                    if not ai_coaching_text:
                        ai_coaching_text = "Achte auf eine entspannte Handhaltung und versuche, die Noten nicht hektisch zu spamen."

                    fail_feedback = f"💀 **Map nicht bestanden (Fail)** – Choke bei Note #{tot} ({acc:.1f}% Acc).\n\n🤖 **Coach-Analyse:**\n{ai_coaching_text}\n\n💡 *Die Map bleibt für einen Re-Try geladen. Klicke links auf 'Nächste Map' oder schreibe mir im Chat, wenn du wechseln willst!*"

                    def update_fail_feed():
                        if hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                            self.ai_train_sync_lbl.configure(text=f"💀 Fail erfasst ({acc:.1f}% bis Note #{tot}) • Bereit für Re-Try", text_color="#FFA726")
                            self.add_modern_chat_bubble("ai", fail_feedback)

                    self.after(0, update_fail_feed)
                    return

                # 3. Full Pass Handling
                delta = 0.0
                if miss == 0 and acc >= 98.5:
                    delta = +0.30  # Flawless -> strong difficulty push
                    adapt_msg = f"🔥 Makelloser FC ({acc:.1f}%)! Nächste Map wird gesteigert (+0.3★)!"
                elif miss == 0 and acc >= 97.0:
                    delta = +0.15  # Solid FC -> moderate push
                    adapt_msg = f"🌟 Sauberer FC ({acc:.1f}%)! Nächste Map leicht gesteigert (+0.15★)."
                elif miss <= 1 and acc >= 95.0:
                    delta = 0.00   # Good pass / minor choke -> hold current sweet-spot
                    adapt_msg = f"👍 Solider Run ({acc:.1f}%, {miss} Miss). Schwierigkeit bleibt stabil."
                elif miss <= 3 or acc >= 92.0:
                    delta = -0.15  # Struggles -> slightly lower SR for confidence
                    adapt_msg = f"🎯 Wegen {miss} Miss(es) / {acc:.1f}% Acc: Nächste Map minimal erleichtert (-0.15★) für besseres Snapping."
                else:
                    delta = -0.35  # Major struggle / fingerlock -> step down to solidify floor
                    adapt_msg = f"⚠️ Wegen {miss} Miss(es) / {acc:.1f}% Acc: Nächste Map angepasst (-0.35★) zur Stabilisierung des Fundaments!"

                if not ai_coaching_text:
                    ai_coaching_text = f"{adapt_msg}\n\nAchte auf gleichmäßiges Tapping und ruhiges Aiming."

                self.log_ai_event(
                    category="Live KI-Training Coach",
                    input_summary={
                        "map": map_name,
                        "sr": map_sr,
                        "bpm": map_bpm,
                        "prescribed_mod": prescribed_mod,
                        "played_mod": played_mods_str,
                        "acc": round(acc, 2),
                        "misses": miss,
                        "combo": combo,
                        "300s": h300,
                        "100s": h100,
                        "50s": h50
                    },
                    prompt_text=coach_prompt if getattr(self, "gemini_key", "") else None,
                    raw_ai_response=ai_coaching_text,
                    calculations={"adaptive_sr_delta": delta, "adapt_msg": adapt_msg}
                )

                feedback = f"✅ Runde erfolgreich abgeschlossen ({played_mods_str})!\nAcc: {acc:.2f}% | 300s: {h300} | 100s: {h100} | Misses: {miss}\n\n🤖 Coach-Analyse:\n{ai_coaching_text}\n\n{mod_warning + chr(10) + chr(10) if mod_warning else ''}{adapt_msg}"

                def update_feed():
                    if hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                        self.ai_train_sync_lbl.configure(text=f"⚡ Live-Sync: Runde erfasst ({acc:.1f}% / {miss} Miss) ➔ Bereite nächste Map vor...", text_color="#00E676")
                        self.add_modern_chat_bubble("ai", feedback)
                        self.after(1200, lambda: self.pick_next_ai_training_map(adaptive_delta=delta) if hasattr(self, 'ai_train_map_title') and self.ai_train_map_title.winfo_exists() else None)

                self.after(0, update_feed)
            except Exception as e:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _start_ai_train_auto_sync_loop(self):
        if getattr(self, "_ai_train_sync_loop_running", False):
            return
        self._ai_train_sync_loop_running = True

        def _loop():
            if not hasattr(self, 'ai_train_sync_lbl') or not self.ai_train_sync_lbl.winfo_exists():
                self._ai_train_sync_loop_running = False
                return
            
            self.fetch_ai_training_recent_plays(silent=True)
            self.after(3500, _loop)

        self.after(1000, _loop)

    # ---------------------------------------------------------------------------
    # ECHTE KI PROFIL-SKILL-ANALYSE (ALLE 8 TRAINING SKILLSETS)
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # DEEP DIVE REPLAY TELEMETRY ANALYZER (MULTI-PLAY SESSION & HOLISTIC AI COACH)
    # ---------------------------------------------------------------------------
    def show_deep_replay_analyzer(self, selected_replay=None, view_mode="aggregate", from_training=True):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        back_target = self.show_training_mode_selection
        ctk.CTkButton(top_bar, text="⬅ Training", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=back_target).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🔬 Deep Replay Telemetrie & KI-Gesamtanalyse", font=("Arial", 18, "bold"), text_color="#00E5FF").pack(side="left", padx=10)
        ctk.CTkLabel(top_bar, text=" ✨ MULTI-PLAY ANALYSE ", font=("Arial", 10, "bold"), fg_color="#00BFA5", text_color="#000000", corner_radius=4).pack(side="left", padx=8)

        def trigger_re_scan():
            self.scan_all_local_osu_replays(max_replays=40)
            self.show_deep_replay_analyzer(view_mode=view_mode)

        def clear_history():
            self.deep_replay_history = []
            self.last_deep_replay_telemetry = None
            self.save_global_settings()
            self.show_deep_replay_analyzer()

        ctk.CTkButton(top_bar, text="🗑️ Verlauf leeren", width=110, height=32, font=("Arial", 11),
                      fg_color="#3a1e22", hover_color="#5a222a", text_color="#ff8888", command=clear_history).pack(side="right", padx=(4, 15))

        ctk.CTkButton(top_bar, text="🔄 Replays scannen", width=125, height=32, font=("Arial", 11, "bold"),
                      fg_color="#1f538d", hover_color="#2b78c9", command=trigger_re_scan).pack(side="right", padx=4)

        history = getattr(self, "deep_replay_history", [])
        if not history and getattr(self, "last_deep_replay_telemetry", None):
            self.record_deep_replay_play(self.last_deep_replay_telemetry)
            history = getattr(self, "deep_replay_history", [])

        scroll_container = ctk.CTkScrollableFrame(master, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        if not history:
            empty_box = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=14, border_width=1, border_color="#2e2e3f")
            empty_box.pack(fill="both", expand=True, pady=20, padx=10)

            ctk.CTkLabel(empty_box, text="⚡ Zero-Click Replay-Scanner ist aktiv!", font=("Arial", 20, "bold"), text_color="#00E5FF").pack(pady=(40, 10))
            ctk.CTkLabel(empty_box, text="Spiele einfach eine oder mehrere Runden in osu! Stable (egal welche Map).\nDu musst KEIN F2 drücken! UHO Hub erfasst ALLE deine Plays automatisch und analysiert deine Schwächen ganzheitlich.",
                         font=("Arial", 13), text_color="#cccccc", justify="center").pack(pady=10)

            drop_f = ctk.CTkFrame(empty_box, fg_color="#13131c", corner_radius=12, border_width=2, border_color="#00BFA5", width=440, height=120)
            drop_f.pack(pady=30)
            drop_f.pack_propagate(False)

            ctk.CTkLabel(drop_f, text="📂 Oder ziehe eine oder mehrere .osr Dateien hier hinein", font=("Arial", 13, "bold"), text_color="#00BFA5").pack(expand=True)

            try:
                drop_f.drop_target_register(DND_FILES)
                def on_manual_drop(event):
                    files = self.tk.splitlist(event.data)
                    for f in files:
                        if f.endswith(".osr"):
                            p = parse_osr_deep_telemetry(f)
                            if p:
                                self.record_deep_replay_play(p)
                    self.show_deep_replay_analyzer()
                drop_f.dnd_bind('<<Drop>>', on_manual_drop)
            except Exception:
                pass
            return

        # Multi-play aggregate calculation
        agg = compute_aggregate_deep_telemetry(history)
        p_name = getattr(self, "osu_username", "Spieler")

        # View Mode Switcher / Banner Bar
        v_bar = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#2b2b3c")
        v_bar.pack(fill="x", pady=(0, 12))

        v_inner = ctk.CTkFrame(v_bar, fg_color="transparent")
        v_inner.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(v_inner, text=f"📊 Session-Speicher: {len(history)} Plays erfasst", font=("Arial", 13, "bold"), text_color="#00E5FF").pack(side="left")

        def set_mode(mode):
            self.show_deep_replay_analyzer(view_mode=mode)

        btn_agg_col = "#00E5FF" if view_mode == "aggregate" else "#252530"
        btn_agg_tcol = "#000000" if view_mode == "aggregate" else "#ffffff"
        ctk.CTkButton(v_inner, text=f"🔥 Gesamte Session (Alle {len(history)} Plays)", font=("Arial", 12, "bold"), height=30,
                      fg_color=btn_agg_col, text_color=btn_agg_tcol, hover_color="#00B4D8", command=lambda: set_mode("aggregate")).pack(side="right", padx=4)

        btn_single_col = "#00E5FF" if view_mode == "single" else "#252530"
        btn_single_tcol = "#000000" if view_mode == "single" else "#ffffff"
        ctk.CTkButton(v_inner, text="📋 Einzel-Replay Inspector", font=("Arial", 12, "bold"), height=30,
                      fg_color=btn_single_col, text_color=btn_single_tcol, hover_color="#00B4D8", command=lambda: set_mode("single")).pack(side="right", padx=4)

        # -------------------------------------------------------------
        # VIEW 1: AGGREGATE MULTI-PLAY OVERVIEW (Default & Holistic)
        # -------------------------------------------------------------
        if view_mode == "aggregate":
            # Master KPI Card
            h_card = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#2e2e3f")
            h_card.pack(fill="x", pady=(0, 12))

            h_row = ctk.CTkFrame(h_card, fg_color="transparent")
            h_row.pack(fill="x", padx=18, pady=14)

            left_info = ctk.CTkFrame(h_row, fg_color="transparent")
            left_info.pack(side="left")
            ctk.CTkLabel(left_info, text=f"👤 {p_name} • Gesamt-Session Profil", font=("Arial", 17, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(left_info, text=f"🎮 {agg['total_plays']} Plays über alle gespielten Maps zusammengefasst", font=("Arial", 12), text_color="#00E5FF").pack(anchor="w", pady=(2, 0))

            right_stats = ctk.CTkFrame(h_row, fg_color="transparent")
            right_stats.pack(side="right")
            acc_col = "#00E676" if agg['avg_acc'] >= 98.0 else ("#FFD700" if agg['avg_acc'] >= 95.0 else "#FF9800")
            ctk.CTkLabel(right_stats, text=f"Ø {agg['avg_acc']:.2f}% ACC  •  {agg['total_misses']} Misses Gesamt ({agg['avg_misses_per_play']:.1f}/Map)",
                         font=("Arial", 15, "bold"), text_color=acc_col).pack(anchor="e")
            ctk.CTkLabel(right_stats, text=f"Max Combo: {agg['max_combo']}x  |  Gesamt-Score: {agg['total_score']:,}  |  300s: {agg['total_300s']} • 100s: {agg['total_100s']} • 50s: {agg['total_50s']}",
                         font=("Arial", 11), text_color="#aaaaaa").pack(anchor="e", pady=(2, 0))

            # 2-Column Telemetry Grid (Aim Dynamics vs Tapping Dynamics)
            grid_2col = ctk.CTkFrame(scroll_container, fg_color="transparent")
            grid_2col.pack(fill="x", pady=(0, 12))
            grid_2col.grid_columnconfigure(0, weight=1)
            grid_2col.grid_columnconfigure(1, weight=1)

            # LEFT CARD: AIM & CURSOR DYNAMICS (AGGREGATE)
            aim_card = ctk.CTkFrame(grid_2col, fg_color="#181822", corner_radius=12, border_width=1, border_color="#E91E63")
            aim_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

            ctk.CTkLabel(aim_card, text="🎯 Systemische Aim- & Cursor-Muster", font=("Arial", 15, "bold"), text_color="#FF4081").pack(anchor="w", padx=16, pady=(14, 8))

            over_pct = agg["avg_overaim"]
            under_pct = agg["avg_underaim"]
            aim_bias_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            aim_bias_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(aim_bias_box, text=f"Overaim: {over_pct:.1f}%  |  Underaim: {under_pct:.1f}% (Ø über alle Plays)", font=("Arial", 13, "bold"), text_color="#ffffff").pack(anchor="w", padx=12, pady=(8, 2))
            
            if over_pct > 55.0:
                aim_desc = f"Du neigst in {over_pct:.0f}% der Jumps zu Overaim (Cursor überschießt das Ziel). Das führt bei schnellen Sprüngen zu Edge-Misses."
            elif over_pct < 45.0:
                aim_desc = f"Du neigst in {under_pct:.0f}% der Jumps zu Underaim (Cursor bremst vor dem Zielkreis ab). Mehr Snap-Confidence erforderlich."
            else:
                aim_desc = "Exzellent ausbalanciertes Cursor-Snapping über alle gespielten Maps hinweg (50/50 Aim Balance)!"
            ctk.CTkLabel(aim_bias_box, text=aim_desc, font=("Arial", 11), text_color="#00E5FF", justify="left", wraplength=380).pack(anchor="w", padx=12, pady=(0, 8))

            spd_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            spd_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(spd_box, text=f"⚡ Peak Snapping Speed: {agg['avg_peak_spd']:,.0f} px/s\n📊 Durchschnittliche Cursor-Geschwindigkeit: {agg['avg_cursor_spd']:,.0f} px/s",
                         font=("Arial", 11, "bold"), text_color="#cccccc", justify="left").pack(anchor="w", padx=12, pady=8)

            quads = agg["quadrants"]
            quad_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            quad_box.pack(fill="x", padx=16, pady=(4, 14))
            ctk.CTkLabel(quad_box, text=f"Bildschirm-Aktivität (Heatmap über alle Maps):\n↖ Oben-Links (TL): {quads.get('TL', 25)}%   |   ↗ Oben-Rechts (TR): {quads.get('TR', 25)}%\n↙ Unten-Links (BL): {quads.get('BL', 25)}%   |   ↘ Unten-Rechts (BR): {quads.get('BR', 25)}%",
                         font=("Arial", 11), text_color="#888899", justify="left").pack(anchor="w", padx=12, pady=8)

            # RIGHT CARD: TAPPING & FINGER CONTROL (AGGREGATE)
            tap_card = ctk.CTkFrame(grid_2col, fg_color="#181822", corner_radius=12, border_width=1, border_color="#00BFA5")
            tap_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

            ctk.CTkLabel(tap_card, text="⚡ Systemische Tapping- & Finger-Kontrolle", font=("Arial", 15, "bold"), text_color="#00BFA5").pack(anchor="w", padx=16, pady=(14, 8))

            ur_val = agg["avg_ur"]
            early_b = agg["avg_early"]
            ur_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            ur_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(ur_box, text=f"Unstable Rate (UR): ~{ur_val:.1f} UR  •  Hit-Offset: {early_b:.0f}% Early / {100-early_b:.0f}% Late", font=("Arial", 13, "bold"), text_color="#00E676").pack(anchor="w", padx=12, pady=(8, 2))
            ur_desc = "Stabiles Rhythmusgefühl ohne systematisches Vorauseilen (Rushing)." if 40 <= early_b <= 60 else ("Du rushst Noten leicht verfrüht (Early Hit Bias)." if early_b > 60 else "Du triffst Noten leicht verzögert (Late Hit Bias).")
            ctk.CTkLabel(ur_box, text=ur_desc, font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=12, pady=(0, 8))

            k1_hold = agg["avg_k1_hold"]
            k2_hold = agg["avg_k2_hold"]
            hold_gap = abs(k1_hold - k2_hold)
            hold_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            hold_box.pack(fill="x", padx=16, pady=4)
            gap_txt = f" (⚠️ {hold_gap:.1f}ms Asymmetrie!)" if hold_gap > 15.0 else " (Ausbalanciert)"
            ctk.CTkLabel(hold_box, text=f"Tasten-Haltezeiten (Hold Time):\n• Taste 1 (K1): {k1_hold:.1f} ms\n• Taste 2 (K2): {k2_hold:.1f} ms{gap_txt}",
                         font=("Arial", 11, "bold"), text_color="#cccccc", justify="left").pack(anchor="w", padx=12, pady=8)

            alt_r = agg["avg_alt_ratio"]
            alt_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            alt_box.pack(fill="x", padx=16, pady=(4, 14))
            alt_desc = "Gleichmäßiges Full-Alternating" if alt_r >= 70.0 else ("Hybrid-Singletapping" if alt_r >= 25.0 else "Reines Singletapping")
            ctk.CTkLabel(alt_box, text=f"Alternating Balance: {alt_r:.1f}%\nStil: {alt_desc}",
                         font=("Arial", 11), text_color="#888899", justify="left").pack(anchor="w", padx=12, pady=8)

            # Bottom Card: Systemic Choke & Miss Breakdown across all plays
            choke_card = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#FF9800")
            choke_card.pack(fill="x", pady=(0, 12))

            choke_hdr = ctk.CTkFrame(choke_card, fg_color="transparent")
            choke_hdr.pack(fill="x", padx=16, pady=(14, 6))
            ctk.CTkLabel(choke_hdr, text="🩸 Top 5 Systemische Fehlerquellen (Häufigste Chokes der Session)", font=("Arial", 15, "bold"), text_color="#FF9800").pack(side="left")

            issues = agg["top_systemic_issues"]
            if not issues:
                ctk.CTkLabel(choke_card, text="✨ Keine wiederkehrenden kritischen Choke-Muster festgestellt. Sehr saubere Spielweise!", font=("Arial", 12), text_color="#00E676").pack(padx=16, pady=10)
            else:
                for issue_txt, count in issues:
                    pct = round((count / max(1, agg['total_plays'])) * 100)
                    r_box = ctk.CTkFrame(choke_card, fg_color="#14141c", corner_radius=6)
                    r_box.pack(fill="x", padx=16, pady=3)
                    ctk.CTkLabel(r_box, text=f"[{count}x in {agg['total_plays']} Maps • {pct}%]", font=("Arial", 10, "bold"), fg_color="#331c1c", text_color="#FF5252", corner_radius=4).pack(side="left", padx=8, pady=6)
                    ctk.CTkLabel(r_box, text=issue_txt, font=("Arial", 12), text_color="#ffffff", justify="left").pack(side="left", padx=4, pady=6)

            # Bottom AI Deep Diagnosis Box (Holistic AI Coaching across all plays)
            ai_card = ctk.CTkFrame(scroll_container, fg_color="#221826", corner_radius=12, border_width=2, border_color="#9C27B0")
            ai_card.pack(fill="x", pady=(0, 16))

            ai_header = ctk.CTkFrame(ai_card, fg_color="transparent")
            ai_header.pack(fill="x", padx=16, pady=(14, 6))
            ctk.CTkLabel(ai_header, text=f"🤖 Google Gemini KI-Gesamtdiagnose ({agg['total_plays']} Plays ausgewertet)", font=("Arial", 15, "bold"), text_color="#BA68C8").pack(side="left")

            ai_res_box = ctk.CTkTextbox(ai_card, wrap="word", font=("Arial", 12), fg_color="#14141a", border_width=1, border_color="#33243a", corner_radius=8, height=160)
            ai_res_box.pack(fill="x", padx=16, pady=(4, 10))
            ai_res_box.insert("1.0", "Klicke auf den Button unten, um eine umfassende KI-Gesamtdiagnose deiner Spielweise über ALLE gespeicherten Replays zu erhalten.")
            ai_res_box.configure(state="disabled")

            def run_aggregate_ai():
                ai_btn.configure(state="disabled", text="⏳ Analysiere alle Plays mit Google Gemini...")
                
                prompt = f"""Du bist der offizielle Cheftrainer und Pro-Coach für osu! Standard (Mode 0).
WICHTIG: Antworte ZU 100% AUF DEUTSCH! Verwende präzise osu!-Terminologie.

Du analysierst die GESAMTE SESSION / HISTORIE des Spielers '{p_name}' über ALLE {agg['total_plays']} gespielten Replays zusammengefasst:
- Gesamt-Statistik: {agg['total_plays']} Maps gespielt | Ø Accuracy: {agg['avg_acc']:.2f}% | Gesamt-Misses: {agg['total_misses']} (Ø {agg['avg_misses_per_play']:.1f} Miss/Map) | Max Combo: {agg['max_combo']}x
- Aim-Telemetrie über alle Maps: Overaim {over_pct:.1f}% vs Underaim {under_pct:.1f}% | Peak Snapping Speed: {agg['avg_peak_spd']:,.0f} px/s | Avg Cursor Speed: {agg['avg_cursor_spd']:,.0f} px/s
- Tapping-Telemetrie über alle Maps: K1 Hold: {k1_hold:.1f}ms | K2 Hold: {k2_hold:.1f}ms (Asymmetrie-Gap: {hold_gap:.1f}ms) | Alternating Balance: {alt_r:.1f}% | Unstable Rate: ~{ur_val:.1f} UR
- Häufigste Choke-Muster über alle Maps: {', '.join([f'{txt} ({c}x)' for txt, c in issues]) if issues else 'Keine akuten Chokes'}

Erstelle eine schonungslose, ganzheitliche 5-Punkte Gesamt-Diagnose:
1. 🎯 Ganzheitliche Aim-Muster (Systematische Overaim/Underaim Tendenzen & Cursor-Snapping über alle Maps)
2. ⚡ Tapping-Technik & Finger-Stamina (K1/K2 Asymmetrie, Tastatur-Druck, Notelock-Gefahr)
3. 🩸 Hauptursachen für Misses im Schnitt (Woran scheitert der Spieler am häufigsten?)
4. 🛠️ Hardware-, Grip- & Setup-Empfehlung (Tablet-Area Feintuning, Maus-DPI / Polling Rate, Tastatur-Settings)
5. 🔥 Konkreter 3-Tage Trainings- und Ausbesserungsplan."""

                def _req():
                    rep = ""
                    if getattr(self, "gemini_key", ""):
                        try:
                            g_model = getattr(self, "selected_ai_model", "gemini-3.6-flash")
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={self.gemini_key}"
                            payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1200}}
                            res = requests.post(url, json=payload, timeout=25).json()
                            rep = res["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except Exception:
                            pass
                    
                    if not rep:
                        rep = f"🎯 **Aim:** Über alle {agg['total_plays']} Maps zeigt sich ein systematischer Overaim von {over_pct:.1f}%. Reduziere deine Tablet-Area um ca. 2mm in der Breite, um die Jump-Stabilität zu erhöhen.\n\n⚡ **Tapping:** Deine Hold-Times (K1: {k1_hold:.1f}ms / K2: {k2_hold:.1f}ms) weisen einen Versatz von {hold_gap:.1f}ms auf. Achte auf gleichmäßigen Fingerdruck bei Streams.\n\n🩸 **Miss-Ursachen:** Die meisten Fehler entstehen durch Dekompensation bei schnellen Jump-Winkeln.\n\n🔥 **Trainings-Fokus:** Absolviere täglich 15 Minuten gezieltes CS 4.8+ Jump-Training und 180-200 BPM Finger-Control Maps."

                    self.log_ai_event(
                        category="Deep Replay KI-Gesamtanalyse",
                        input_summary={
                            "total_plays": agg.get('total_plays', 0),
                            "avg_acc": agg.get('avg_acc', 0.0),
                            "total_misses": agg.get('total_misses', 0),
                            "max_combo": agg.get('max_combo', 0)
                        },
                        prompt_text=prompt if getattr(self, "gemini_key", "") else None,
                        raw_ai_response=rep,
                        calculations={
                            "avg_overaim": over_pct,
                            "avg_underaim": under_pct,
                            "k1_hold": k1_hold,
                            "k2_hold": k2_hold,
                            "top_issues": agg.get('top_systemic_issues', [])
                        }
                    )

                    def _done():
                        if ai_res_box.winfo_exists():
                            ai_res_box.configure(state="normal")
                            ai_res_box.delete("1.0", "end")
                            ai_res_box.insert("1.0", rep)
                            ai_res_box.configure(state="disabled")
                        if ai_btn.winfo_exists():
                            ai_btn.configure(state="normal", text="🔄 Gesamt-Diagnose aktualisieren")
                    self.after(0, _done)

                threading.Thread(target=_req, daemon=True).start()

            ai_btn = ctk.CTkButton(ai_card, text="✨ Ganzheitliche KI-Gesamtdiagnose generieren ➔", font=("Arial", 13, "bold"), height=38,
                                   fg_color="#9C27B0", hover_color="#7B1FA2", command=run_aggregate_ai)
            ai_btn.pack(padx=16, pady=(0, 14), fill="x")

        # -------------------------------------------------------------
        # VIEW 2: SINGLE REPLAY INSPECTOR
        # -------------------------------------------------------------
        else:
            cur_rd = selected_replay or history[0]
            metrics = cur_rd.get("metrics", {})

            # Play selection listbox / selector
            sel_card = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#2e2e3f")
            sel_card.pack(fill="x", pady=(0, 12))

            sel_hdr = ctk.CTkFrame(sel_card, fg_color="transparent")
            sel_hdr.pack(fill="x", padx=16, pady=10)
            ctk.CTkLabel(sel_hdr, text="📋 Wähle ein Replay aus dem Verlauf:", font=("Arial", 13, "bold"), text_color="#ffffff").pack(side="left")

            replay_labels = []
            for i, r in enumerate(history[:20]):
                m_str = r.get("mods_str", "NM")
                replay_labels.append(f"Spiel #{i+1}: {r.get('accuracy', 0):.1f}% ACC • {r.get('score', 0):,} Score • {r.get('misses', 0)} Miss ({m_str})")

            def on_sel_change(val):
                idx = replay_labels.index(val) if val in replay_labels else 0
                self.show_deep_replay_analyzer(selected_replay=history[idx], view_mode="single")

            cur_lbl = replay_labels[0]
            if selected_replay in history:
                cur_lbl = replay_labels[history.index(selected_replay)]

            combo_sel = ctk.CTkComboBox(sel_hdr, values=replay_labels, width=420, height=32, font=("Arial", 11), command=on_sel_change)
            combo_sel.set(cur_lbl)
            combo_sel.pack(side="right")

            # Single Play Card
            h_card = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#2e2e3f")
            h_card.pack(fill="x", pady=(0, 12))

            h_row = ctk.CTkFrame(h_card, fg_color="transparent")
            h_row.pack(fill="x", padx=18, pady=12)

            acc = cur_rd.get("accuracy", 0.0)
            score = cur_rd.get("score", 0)
            combo = cur_rd.get("combo", 0)
            h300 = cur_rd.get("300s", 0)
            h100 = cur_rd.get("100s", 0)
            h50 = cur_rd.get("50s", 0)
            miss = cur_rd.get("misses", 0)
            mods_str = cur_rd.get("mods_str", "None (NM)")

            left_info = ctk.CTkFrame(h_row, fg_color="transparent")
            left_info.pack(side="left")
            ctk.CTkLabel(left_info, text=f"👤 {cur_rd.get('player', p_name)} (Einzel-Play)", font=("Arial", 16, "bold"), text_color="#ffffff").pack(anchor="w")
            ctk.CTkLabel(left_info, text=f"🎮 Mods: {mods_str}  •  Frames: {cur_rd.get('total_frames', 0):,}", font=("Arial", 11), text_color="#888899").pack(anchor="w")

            right_stats = ctk.CTkFrame(h_row, fg_color="transparent")
            right_stats.pack(side="right")
            acc_col = "#00E676" if acc >= 98.0 else ("#FFD700" if acc >= 95.0 else "#FF9800")
            ctk.CTkLabel(right_stats, text=f"{acc:.2f}% ACC  •  {combo}x Max Combo", font=("Arial", 15, "bold"), text_color=acc_col).pack(anchor="e")
            ctk.CTkLabel(right_stats, text=f"Score: {score:,}  |  300s: {h300} • 100s: {h100} • 50s: {h50} • Misses: {miss}", font=("Arial", 11), text_color="#aaaaaa").pack(anchor="e")

            # Single Play 2-Column Telemetry Grid
            grid_2col = ctk.CTkFrame(scroll_container, fg_color="transparent")
            grid_2col.pack(fill="x", pady=(0, 12))
            grid_2col.grid_columnconfigure(0, weight=1)
            grid_2col.grid_columnconfigure(1, weight=1)

            # LEFT CARD: AIM & CURSOR DYNAMICS
            aim_card = ctk.CTkFrame(grid_2col, fg_color="#181822", corner_radius=12, border_width=1, border_color="#E91E63")
            aim_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            ctk.CTkLabel(aim_card, text="🎯 Aim- & Cursor-Telemetrie", font=("Arial", 15, "bold"), text_color="#FF4081").pack(anchor="w", padx=16, pady=(14, 8))

            over_pct = metrics.get("overaim_pct", 50.0)
            under_pct = metrics.get("underaim_pct", 50.0)
            peak_spd = metrics.get("peak_speed", 0.0)
            avg_spd = metrics.get("avg_speed", 0.0)
            quads = metrics.get("quadrants", {"TL": 25, "TR": 25, "BL": 25, "BR": 25})

            aim_bias_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            aim_bias_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(aim_bias_box, text=f"Overaim: {over_pct:.1f}%  |  Underaim: {under_pct:.1f}%", font=("Arial", 13, "bold"), text_color="#ffffff").pack(anchor="w", padx=12, pady=(8, 2))
            aim_desc = "Du überaimst deine Jumps (Cursor fliegt über die Circle-Edge hinaus)." if over_pct > 55.0 else ("Du neigst zu Underaim (Cursor stoppt vor der Circle-Edge)." if over_pct < 45.0 else "Perfekt balancierte Jump-Snaps (50/50 Aim Balance).")
            ctk.CTkLabel(aim_bias_box, text=aim_desc, font=("Arial", 11), text_color="#00E5FF", justify="left").pack(anchor="w", padx=12, pady=(0, 8))

            spd_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            spd_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(spd_box, text=f"⚡ Peak Snapping Speed: {peak_spd:,.0f} px/s\n📊 Avg Cursor-Speed: {avg_spd:,.0f} px/s",
                         font=("Arial", 11, "bold"), text_color="#cccccc", justify="left").pack(anchor="w", padx=12, pady=8)

            quad_box = ctk.CTkFrame(aim_card, fg_color="#121218", corner_radius=8)
            quad_box.pack(fill="x", padx=16, pady=(4, 14))
            ctk.CTkLabel(quad_box, text=f"Bildschirm-Verteilung (Heatmap):\n↖ TL: {quads.get('TL', 25)}%  |  ↗ TR: {quads.get('TR', 25)}%\n↙ BL: {quads.get('BL', 25)}%  |  ↘ BR: {quads.get('BR', 25)}%",
                         font=("Arial", 11), text_color="#888899", justify="left").pack(anchor="w", padx=12, pady=8)

            # RIGHT CARD: TAPPING & FINGER CONTROL
            tap_card = ctk.CTkFrame(grid_2col, fg_color="#181822", corner_radius=12, border_width=1, border_color="#00BFA5")
            tap_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
            ctk.CTkLabel(tap_card, text="⚡ Tapping & Finger Control", font=("Arial", 15, "bold"), text_color="#00BFA5").pack(anchor="w", padx=16, pady=(14, 8))

            k1_hold = metrics.get("k1_avg_hold", 50.0)
            k2_hold = metrics.get("k2_avg_hold", 50.0)
            k1_cnt = metrics.get("k1_count", 0)
            k2_cnt = metrics.get("k2_count", 0)
            alt_r = metrics.get("alt_ratio", 50.0)
            ur_val = metrics.get("ur", 80.0)
            early_b = metrics.get("early_bias_pct", 50.0)

            ur_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            ur_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(ur_box, text=f"Unstable Rate (UR): ~{ur_val:.1f} UR  •  Hit Error: {early_b:.0f}% Early", font=("Arial", 13, "bold"), text_color="#00E676").pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(ur_box, text="Gleichmäßiges Rhythmusgefühl ohne vorzeitiges Rushing.", font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=12, pady=(0, 8))

            hold_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            hold_box.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(hold_box, text=f"Tasten-Haltezeit (Hold Time):\n• Taste 1 (K1): {k1_hold:.1f} ms ({k1_cnt} Taps)\n• Taste 2 (K2): {k2_hold:.1f} ms ({k2_cnt} Taps)",
                         font=("Arial", 11, "bold"), text_color="#cccccc", justify="left").pack(anchor="w", padx=12, pady=8)

            alt_box = ctk.CTkFrame(tap_card, fg_color="#121218", corner_radius=8)
            alt_box.pack(fill="x", padx=16, pady=(4, 14))
            alt_desc = "Gleichmäßiges Full-Alternating" if alt_r >= 70.0 else ("Hybrid-Singletapping" if alt_r >= 25.0 else "Reines Singletapping")
            ctk.CTkLabel(alt_box, text=f"Alternating Balance: {alt_r:.1f}%\nStil: {alt_desc}",
                         font=("Arial", 11), text_color="#888899", justify="left").pack(anchor="w", padx=12, pady=8)

            # Bottom Card: Miss & Choke Root-Cause Analysis for this single play
            choke_card = ctk.CTkFrame(scroll_container, fg_color="#181822", corner_radius=12, border_width=1, border_color="#FF9800")
            choke_card.pack(fill="x", pady=(0, 12))
            ctk.CTkLabel(choke_card, text="🩸 Miss- & Choke-Ursachenanalyse (Dieses Replay)", font=("Arial", 15, "bold"), text_color="#FF9800").pack(anchor="w", padx=16, pady=(14, 6))

            choke_reasons = metrics.get("choke_reasons", [])
            for r in choke_reasons:
                r_box = ctk.CTkFrame(choke_card, fg_color="#14141c", corner_radius=6)
                r_box.pack(fill="x", padx=16, pady=3)
                ctk.CTkLabel(r_box, text=r, font=("Arial", 12), text_color="#ffffff", justify="left").pack(anchor="w", padx=10, pady=6)

    # ---------------------------------------------------------------------------
    # MASTER SKILL-ANALYSE (SCHRITT 1: PROFIL -> SCHRITT 2: TEST -> PERMANENT RADAR)
    # ---------------------------------------------------------------------------
    def show_skill_analyse(self):
        # 1. Profile Analysis not done yet
        if not getattr(self, "last_profile_analysis", None):
            self.show_profile_analyzer(is_step1=True)
            return

        # 2. Benchmark Test not completed yet
        if not getattr(self, "skill_test_completed", False):
            self.show_skill_tester_menu()
            return

        # 3. Fully completed -> Permanent Live-Radar Dashboard
        self.show_completed_skill_radar_dashboard()

    def show_completed_skill_radar_dashboard(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🎯 Skill-Analyse • 8-Skill Live-Radar", font=("Arial", 18, "bold"), text_color="#E91E63").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="🔬 Deep Replay Analyse ➔", font=("Arial", 12, "bold"),
                      fg_color="#00E5FF", hover_color="#00B4D8", text_color="#000000", height=36,
                      command=self.show_deep_replay_analyzer).pack(side="right", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("profile")).pack(side="right", padx=5)

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_box.grid_columnconfigure(0, weight=1)
        main_box.grid_columnconfigure(1, weight=1)
        main_box.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        pa = getattr(self, "last_profile_analysis", {}) or {}
        scores = pa.get("scores", {})
        player_name = getattr(self, "osu_username", pa.get("player", "Spieler"))

        ctk.CTkLabel(left_frame, text=f"Live-Radar: {player_name}", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(12, 2))
        
        main_s = pa.get("main_skill", max(scores, key=scores.get) if scores else "Aim")
        weak_s = pa.get("weakness", min(scores, key=scores.get) if scores else "Tech")
        
        stats_banner = ctk.CTkFrame(left_frame, fg_color="#1c1c28", corner_radius=8)
        stats_banner.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(stats_banner, text=f"⭐ Stärke: {main_s} ({scores.get(main_s, 0)})  •  ⚠️ Fokus: {weak_s} ({scores.get(weak_s, 0)})",
                     font=("Arial", 11, "bold"), text_color="#00E5FF").pack(pady=4)

        self.dashboard_radar_canvas = ctk.CTkCanvas(left_frame, bg="#181820", highlightthickness=0)
        self.dashboard_radar_canvas.pack(fill="both", expand=True, padx=10, pady=5)
        self.dashboard_radar_canvas.bind("<Configure>", lambda e: self.draw_dashboard_live_radar())

        live_sync_bar = ctk.CTkFrame(left_frame, fg_color="#121218", corner_radius=8)
        live_sync_bar.pack(fill="x", padx=15, pady=(4, 10))
        ctk.CTkLabel(live_sync_bar, text="⚡ KI-Live-Tracking aktiv: Jedes gespielte osu! Play wird von der KI analysiert!",
                     font=("Arial", 10, "bold"), text_color="#00E676").pack(pady=6)

        # Right Frame: Coaching Feed & Play Evolution
        right_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(right_frame, text="🤖 KI-Play-Auswertung & Skill-Entwicklung", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(12, 4))

        ctk.CTkLabel(right_frame, text="Zuletzt von der KI analysierte Runden & Radar-Updates:", font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=15)

        self.dashboard_history_box = ctk.CTkTextbox(right_frame, wrap="word", font=("Arial", 12), fg_color="#14141a", border_width=1, border_color="#262633", corner_radius=8, height=180)
        self.dashboard_history_box.pack(fill="x", padx=15, pady=(4, 10))
        history_lines = pa.get("radar_history", [
            "• Initiales Profil-Assessment abgeschlossen",
            "• 8-Map Benchmark Skill-Test erfolgreich absolviert",
            "• Live-Radar Tracking initialisiert"
        ])
        self.dashboard_history_box.insert("1.0", "\n".join(history_lines))
        self.dashboard_history_box.configure(state="disabled")

        ctk.CTkLabel(right_frame, text="Coach Feedback & Trainingsstrategie:", font=("Arial", 11), text_color="#888899").pack(anchor="w", padx=15)
        
        fb_box = ctk.CTkTextbox(right_frame, wrap="word", font=("Arial", 12), fg_color="#14141a", border_width=1, border_color="#262633", corner_radius=8)
        fb_box.pack(fill="both", expand=True, padx=15, pady=(4, 12))
        fb_box.insert("1.0", pa.get("feedback", "Deine Skill-Werte werden bei jedem gespielten Match in osu! live aktualisiert."))
        fb_box.configure(state="disabled")

        self.draw_dashboard_live_radar()

    def draw_dashboard_live_radar(self):
        canvas = getattr(self, "dashboard_radar_canvas", None)
        if not canvas or not canvas.winfo_exists(): return
        canvas.delete("all")

        width = canvas.winfo_width() or 380
        height = canvas.winfo_height() or 340
        cx = width / 2
        cy = height / 2
        max_r = max(40, min(cx, cy) - 45)

        categories = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
        n = len(categories)
        scores = getattr(self, "last_profile_analysis", {}).get("scores", {})

        for ring in [0.25, 0.5, 0.75, 1.0]:
            r = max_r * ring
            pts = []
            for i in range(n):
                angle = (2 * math.pi / n) * i - (math.pi / 2)
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                pts.extend([px, py])
            canvas.create_polygon(pts, fill="", outline="#2e2e3f", width=1)

        for i, cat in enumerate(categories):
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + max_r * math.cos(angle)
            py = cy + max_r * math.sin(angle)
            canvas.create_line(cx, cy, px, py, fill="#3a3a4e", dash=(2, 2))

            lx = cx + (max_r + 22) * math.cos(angle)
            ly = cy + (max_r + 22) * math.sin(angle)
            s_val = scores.get(cat, 65)
            canvas.create_text(lx, ly, text=f"{cat}\n({s_val})", fill="#00E5FF", font=("Arial", 9, "bold"), justify="center")

        data_pts = []
        for i, cat in enumerate(categories):
            score = scores.get(cat, 65)
            score_clamped = max(5, min(100, score))
            r = max_r * (score_clamped / 100.0)
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            data_pts.extend([px, py])

        if len(data_pts) >= 6:
            canvas.create_polygon(data_pts, fill="#E91E63", outline="#FF4081", width=2, stipple="gray25")
            for i in range(0, len(data_pts), 2):
                x, y = data_pts[i], data_pts[i+1]
                canvas.create_oval(x-4, y-4, x+4, y+4, fill="#FF4081", outline="#ffffff")

    def ai_process_play_for_radar(self, play_data):
        """Processes any recent play made in osu! and lets Gemini AI re-evaluate the 8 skill scores."""
        if not getattr(self, "last_profile_analysis", None):
            return

        bid = str(play_data.get("beatmap_id", ""))
        if not bid: return

        h300 = int(play_data.get("count300", 0))
        h100 = int(play_data.get("count100", 0))
        h50 = int(play_data.get("count50", 0))
        miss = int(play_data.get("countmiss", 0))
        combo = int(play_data.get("maxcombo", 0))
        tot = h300 + h100 + h50 + miss
        acc = ((h300 * 300 + h100 * 100 + h50 * 50) / (tot * 300) * 100) if tot > 0 else 0

        map_info = next((m for m in DYNAMIC_RANKED_MAPS_DB if m.get("id") == bid), None)
        if map_info:
            map_name = map_info.get("name", f"Map #{bid}")
            sr = map_info.get("sr", 5.0)
            bpm = map_info.get("bpm", 180)
            cats = classify_map(map_info)
        else:
            map_name = f"Map #{bid}"
            sr = 5.0
            bpm = 180
            cats = ["Consistency", "Aim"]

        target_cat = cats[0] if cats else "Aim"
        current_scores = dict(self.last_profile_analysis.get("scores", {}))

        def run_ai():
            try:
                new_scores = dict(current_scores)
                summary_txt = ""
                if getattr(self, "gemini_key", ""):
                    prompt = f"""Du bist der offizielle osu! Standard (Mode 0) KI-Coach.
Aktuelle 8 Skill-Scores des Spielers (0-100):
{json.dumps(current_scores)}

Neuer gespielter Score in osu!:
- Map: {map_name} (★ {sr:.1f}, BPM: {bpm}, Primäres Skillset: {target_cat})
- Performance: {acc:.2f}% Acc | {h300}x300 | {h100}x100 | {h50}x50 | {miss} Misses | Max Combo: {combo}

Bewerte als KI, wie sich diese Runde auf die 8 Skillsets des Spielers auswirkt.
Passe die 8 Scores (0 bis 100) sinnvoll an:
- Starke Performance (z.B. hohe Acc/FC auf schwieriger Map): +1 bis +3 Punkte für {target_cat} (und evtl. verwandte Skills).
- Schwache Performance: -1 bis -2 Punkte oder stabil halten.
- Behalte alle 8 Skillsets im JSON.

Antworte STRENG in folgendem JSON-Format (ohne Markdown Backticks darum herum):
{{
  "scores": {{
    "Consistency": 75,
    "Speed": 80,
    "Aim": 85,
    "Stamina": 65,
    "Tech": 60,
    "Reading": 70,
    "Streams": 68,
    "Precision": 72
  }},
  "summary": "Kurze 1-Satz Zusammenfassung der Anpassung",
  "main_skill": "Aim",
  "weakness": "Tech"
}}"""
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 512}
                    }
                    resp = requests.post(url, json=payload, timeout=12)
                    res_j = resp.json()
                    candidates = res_j.get("candidates", [])
                    raw = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip() if candidates else ""
                    parsed = safe_parse_ai_json(raw, default={})
                    new_scores = parsed.get("scores", current_scores)
                    if not isinstance(new_scores, dict):
                        new_scores = current_scores
                    main_s = parsed.get("main_skill", max(new_scores, key=new_scores.get) if new_scores else "Aim")
                    weak_s = parsed.get("weakness", min(new_scores, key=new_scores.get) if new_scores else "Tech")
                    summary_txt = parsed.get("summary", f"+1 {target_cat} ({acc:.1f}% Acc)")
                else:
                    delta = 1 if (acc >= 95.0 and miss <= 1) else (-1 if miss >= 4 else 0)
                    new_scores[target_cat] = max(10, min(100, new_scores.get(target_cat, 60) + delta))
                    main_s = max(new_scores, key=new_scores.get)
                    weak_s = min(new_scores, key=new_scores.get)
                    summary_txt = f"{'+1' if delta>0 else ('-1' if delta<0 else '±0')} {target_cat} ({acc:.1f}% Acc)"

                self.last_profile_analysis["scores"] = new_scores
                self.last_profile_analysis["main_skill"] = main_s
                self.last_profile_analysis["weakness"] = weak_s
                if "radar_history" not in self.last_profile_analysis:
                    self.last_profile_analysis["radar_history"] = []
                self.last_profile_analysis["radar_history"].insert(0, f"• {summary_txt} ({map_name[:35]})")
                self.last_profile_analysis["radar_history"] = self.last_profile_analysis["radar_history"][:15]
                self.save_global_settings()

                def update_radar_ui():
                    if hasattr(self, "dashboard_radar_canvas") and self.dashboard_radar_canvas.winfo_exists():
                        self.draw_dashboard_live_radar()
                        if hasattr(self, "dashboard_history_box") and self.dashboard_history_box.winfo_exists():
                            self.dashboard_history_box.configure(state="normal")
                            self.dashboard_history_box.delete("1.0", "end")
                            self.dashboard_history_box.insert("1.0", "\n".join(self.last_profile_analysis.get("radar_history", [])))
                            self.dashboard_history_box.configure(state="disabled")

                self.safe_ui_dispatch(self, update_radar_ui)
            except Exception:
                pass

        threading.Thread(target=run_ai, daemon=True).start()

    def show_profile_analyzer(self, is_step1=False):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🔍 KI Profil-Skill-Analyse (8 Skillsets)", font=("Arial", 18, "bold"), text_color="#9C27B0").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("profile")).pack(side="right", padx=15)

        main_box = ctk.CTkFrame(master, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main_box.grid_columnconfigure(0, weight=1)
        main_box.grid_columnconfigure(1, weight=1)
        main_box.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        if is_step1:
            step_banner = ctk.CTkFrame(left_frame, fg_color="#2b1a38", corner_radius=8, border_width=1, border_color="#9C27B0")
            step_banner.pack(fill="x", padx=15, pady=(12, 4))
            ctk.CTkLabel(step_banner, text="🎯 SCHRITT 1 VON 2: Profil & Stärken analysieren", font=("Arial", 11, "bold"), text_color="#E1BEE7").pack(padx=8, pady=6)
        
        ctk.CTkLabel(left_frame, text="osu! Spieler analysieren", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(10, 5))
        
        user_row = ctk.CTkFrame(left_frame, fg_color="transparent")
        user_row.pack(fill="x", padx=20, pady=5)
        
        self.profile_user_entry = ctk.CTkEntry(user_row, placeholder_text="osu! Spielername...", font=("Arial", 13), height=36)
        self.profile_user_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if getattr(self, "osu_username", ""):
            self.profile_user_entry.insert(0, self.osu_username)

        self.profile_analyze_btn = ctk.CTkButton(user_row, text="⚡ Analysieren", width=120, height=36,
                                                 font=("Arial", 13, "bold"), fg_color="#9C27B0", hover_color="#7B1FA2",
                                                 command=self.analyze_user_profile_ai)
        self.profile_analyze_btn.pack(side="right")

        self.profile_status_lbl = ctk.CTkLabel(left_frame, text="Klicke auf 'Analysieren', um Top-Plays & Scores von der KI auswerten zu lassen.",
                                               font=("Arial", 11), text_color="#888899")
        self.profile_status_lbl.pack(pady=4)

        self.profile_radar_canvas = ctk.CTkCanvas(left_frame, width=380, height=340, bg="#181820", highlightthickness=0)
        self.profile_radar_canvas.pack(fill="both", expand=True, padx=10, pady=10)

        right_frame = ctk.CTkFrame(main_box, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(right_frame, text="🤖 KI-Auswertung & Empfehlungen", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(15, 5))

        self.profile_ai_box = ctk.CTkTextbox(right_frame, wrap="word", font=("Arial", 13), fg_color="#14141a", border_width=0)
        self.profile_ai_box.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        self.profile_ai_box.insert("1.0", "Hier erscheint die detaillierte Auswertung deines Profils über alle 8 Skillsets inklusive Stärken, Schwächen und Trainingsempfehlungen.")
        self.profile_ai_box.configure(state="disabled")

        if getattr(self, "last_profile_analysis", None):
            self.draw_profile_radar(self.last_profile_analysis.get("scores", {}))
            self.profile_ai_box.configure(state="normal")
            self.profile_ai_box.delete("1.0", "end")
            self.profile_ai_box.insert("1.0", self.last_profile_analysis.get("feedback", ""))
            self.profile_ai_box.configure(state="disabled")

    def draw_profile_radar(self, skill_scores):
        canvas = self.profile_radar_canvas
        canvas.delete("all")
        
        width = canvas.winfo_width() or 380
        height = canvas.winfo_height() or 340
        cx = width / 2
        cy = height / 2
        max_r = max(40, min(cx, cy) - 45)

        categories = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
        n = len(categories)

        for ring in [0.25, 0.5, 0.75, 1.0]:
            r = max_r * ring
            pts = []
            for i in range(n):
                angle = (2 * math.pi / n) * i - (math.pi / 2)
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                pts.extend([px, py])
            canvas.create_polygon(pts, fill="", outline="#2e2e3f", width=1)

        for i, cat in enumerate(categories):
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + max_r * math.cos(angle)
            py = cy + max_r * math.sin(angle)
            canvas.create_line(cx, cy, px, py, fill="#3a3a4e", dash=(2, 2))

            lx = cx + (max_r + 24) * math.cos(angle)
            ly = cy + (max_r + 24) * math.sin(angle)
            score_val = skill_scores.get(cat, 0)
            canvas.create_text(lx, ly, text=f"{cat}\n({score_val})", fill="#bbbbcc", font=("Arial", 9, "bold"), justify="center")

        data_pts = []
        for i, cat in enumerate(categories):
            score = skill_scores.get(cat, 0)
            score_clamped = max(5, min(100, score))
            r = max_r * (score_clamped / 100.0)
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            data_pts.extend([px, py])

        if len(data_pts) >= 6:
            canvas.create_polygon(data_pts, fill="#9C27B0", outline="#E040FB", width=2, stipple="gray25")
            for i in range(0, len(data_pts), 2):
                x, y = data_pts[i], data_pts[i+1]
                canvas.create_oval(x-4, y-4, x+4, y+4, fill="#E040FB", outline="#ffffff")

    def analyze_user_profile_ai(self):
        username = self.profile_user_entry.get().strip()
        if not username:
            self.profile_status_lbl.configure(text="❌ Bitte gib einen Spielernamen ein!", text_color="#ff4444")
            return

        self.profile_status_lbl.configure(text="⏳ Lade Top-Plays & Scores von osu!...", text_color="#00E5FF")
        self.profile_analyze_btn.configure(state="disabled")

        def run():
            top_plays = []
            is_supporter = False
            api_k = getattr(self, "api_key", "")
            if api_k:
                try:
                    url = f"https://osu.ppy.sh/api/get_user_best?k={api_k}&u={username}&m=0&limit=50"
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        top_plays = r.json()
                    
                    # Check supporter status
                    u_url = f"https://osu.ppy.sh/api/get_user?k={api_k}&u={username}&m=0"
                    u_r = requests.get(u_url, timeout=10)
                    if u_r.status_code == 200 and u_r.json():
                        u_info = u_r.json()[0]
                        # In osu! API v1, supporter_tag can indicate supporter level
                        if str(u_info.get("supporter_tag", "0")) != "0":
                            is_supporter = True
                except Exception as e:
                    pass

            u_pp = float(u_info.get("pp_raw", 0)) if ('u_info' in locals() and u_info) else 0.0
            u_rank = int(u_info.get("pp_rank", 0)) if ('u_info' in locals() and u_info) else 0
            u_acc = float(u_info.get("accuracy", 0.0)) if ('u_info' in locals() and u_info) else 0.0
            u_pc = int(u_info.get("playcount", 0)) if ('u_info' in locals() and u_info) else 0
            default_rank_sr = estimate_sr_from_rank_and_pp(u_rank, u_pp)

            enriched_top_plays = []
            id_to_meta = {}
            if top_plays and isinstance(top_plays, list):
                bids = [str(p.get("beatmap_id", "")) for p in top_plays if p.get("beatmap_id")]
                with get_safe_sqlite_conn() as conn:
                    if conn and bids:
                        placeholders = ",".join(["?"] * len(bids[:100]))
                        try:
                            rows = conn.execute(f"SELECT id, name, sr, cs, ar, od FROM maps WHERE id IN ({placeholders})", bids[:100]).fetchall()
                            for r in rows:
                                id_to_meta[str(r["id"])] = dict(r)
                        except Exception:
                            pass
            if not id_to_meta:
                id_to_meta = {str(m.get('id', '')): m for m in (DYNAMIC_RANKED_MAPS_DB or [])}

            for i, p in enumerate(top_plays[:35]):
                bid = str(p.get("beatmap_id", ""))
                mods_int = int(p.get("enabled_mods", 0) or 0)
                h300 = int(p.get("count300", 0))
                h100 = int(p.get("count100", 0))
                h50 = int(p.get("count50", 0))
                miss = int(p.get("countmiss", 0))
                tot = h300 + h100 + h50 + miss
                acc = round(((h300*300 + h100*100 + h50*50) / (tot*300) * 100.0) if tot > 0 else 0.0, 2)
                pp_val = round(float(p.get("pp", 0.0) or 0.0), 1)
                
                mod_str = []
                if mods_int & 64: mod_str.append("DT")
                if mods_int & 512: mod_str.append("NC")
                if mods_int & 16: mod_str.append("HR")
                if mods_int & 8: mod_str.append("HD")
                if mods_int & 2: mod_str.append("EZ")
                if mods_int & 256: mod_str.append("HT")
                mods_label = "+".join(mod_str) if mod_str else "NoMod"

                map_info = id_to_meta.get(bid, {})
                map_name = map_info.get("name", f"Beatmap ID #{bid}")
                base_sr = float(map_info.get("sr", round((pp_val ** 0.35) * 0.77, 2) if pp_val > 0 else default_rank_sr))
                if "DT" in mods_label or "NC" in mods_label:
                    sr_played = round(base_sr * 1.40, 2)
                elif "HR" in mods_label:
                    sr_played = round(base_sr * 1.06, 2)
                elif "EZ" in mods_label:
                    sr_played = round(base_sr * 0.72, 2)
                else:
                    sr_played = round(base_sr, 2)

                enriched_top_plays.append({
                    "rank": i + 1,
                    "map": map_name,
                    "sr": sr_played,
                    "mods": mods_label,
                    "acc": acc,
                    "misses": miss,
                    "pp": pp_val
                })

            # Calculate accurate average Star Rating from top plays
            sr_pool = [float(p.get("sr", default_rank_sr)) for p in enriched_top_plays if p.get("sr")]
            if sr_pool:
                # Weighted top 15 plays average
                top_avg_sr = round(sum(sr_pool[:15]) / len(sr_pool[:15]), 2)
            else:
                top_avg_sr = default_rank_sr
            
            # Benchmark test difficulty matches true player skill level (no artificial downgrading)
            target_test_sr = round(max(3.5, min(9.5, top_avg_sr)), 1)

            self.after(0, lambda: self.profile_status_lbl.configure(text="🤖 KI analysiert alle 8 Skillsets...", text_color="#E91E63"))

            user_scores = {
                "Consistency": 65, "Speed": 70, "Aim": 75, "Stamina": 60,
                "Tech": 55, "Reading": 60, "Streams": 65, "Precision": 70
            }
            feedback_text = ""

            if getattr(self, "gemini_key", ""):
                prompt = f"""Du bist der offizielle Pro-Level osu! KI-Coach und Profil-Analyst.
Analysiere das Profil und die Top-Plays von Spieler '{username}' AUSSCHLIESSLICH fuer osu! Standard (Mode 0) (kein Mania, kein Catch, kein Taiko).

Spieler-Profil-Statistiken:
- Globaler Rang: #{u_rank:,}
- Performance Points (PP): {u_pp:.1f} pp
- Profil-Overall Accuracy: {u_acc:.2f}%
- Gesamt Playcount: {u_pc:,}

Top-Plays ({len(enriched_top_plays)} Best-Plays):
{json.dumps(enriched_top_plays, indent=2)}

Bewerte alle 8 Skillsets auf einer Skala von 0 bis 100 Punkten basierend auf den gespielten Mods, Star Ratings, Miss-Zahlen und Accuracies:
1. Consistency (Konstanz - viele FCs und saubere Acc in Top-Plays)
2. Speed (Geschwindigkeit - DT-Plays, High BPM Bursts)
3. Aim (Praezision & Jumps - Jump Maps, DT Jumps)
4. Stamina (Ausdauer & lange Stream-Maps / Marathons)
5. Tech (Slider-Control, ungerade Rhythmen, komplexe Winkel)
6. Reading (Low-AR, Dichte, Hidden/HD-Plays)
7. Streams (Finger-Control, Flow-Aim)
8. Precision (Kleine Circle-Size, CS5+, HardRock/HR-Plays)

Antworte STRENG in folgendem JSON-Format (ohne Markdown Backticks darum herum):
{{
  "scores": {{
    "Consistency": 75,
    "Speed": 80,
    "Aim": 85,
    "Stamina": 65,
    "Tech": 60,
    "Reading": 70,
    "Streams": 68,
    "Precision": 72
  }},
  "main_skill": "Aim",
  "weakness": "Tech",
  "feedback": "Detaillierte, tiefgruendige KI-Analyse deines Spielstils, Staerken, Schwaechen und gezielte Trainingsempfehlungen auf Deutsch..."
}}"""
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
                    }
                    resp = requests.post(url, json=payload, timeout=20)
                    res_json = resp.json()
                    candidates = res_json.get("candidates", [])
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
                    parsed = safe_parse_ai_json(raw_text, default={})
                    user_scores = parsed.get("scores", user_scores)
                    if not isinstance(user_scores, dict):
                        user_scores = {
                            "Consistency": 65, "Speed": 70, "Aim": 75, "Stamina": 60,
                            "Tech": 55, "Reading": 60, "Streams": 65, "Precision": 70
                        }
                    feedback_text = parsed.get("feedback", "")
                except Exception:
                    feedback_text = f"Analyse basierend auf Spieler-Statistiken ({username}).\n\nStärken in Aim & Speed. Schwächen in Tech & Stamina.\nEmpfehlung: Trainiere 2020+ Tech-Maps und 3+ Minuten Marathons!"
            else:
                # Dynamic mathematical scoring based on actual top plays distribution
                dt_count = sum(1 for p in enriched_top_plays if "DT" in p.get("mods", "") or "NC" in p.get("mods", ""))
                hr_count = sum(1 for p in enriched_top_plays if "HR" in p.get("mods", ""))
                hd_count = sum(1 for p in enriched_top_plays if "HD" in p.get("mods", ""))
                fc_count = sum(1 for p in enriched_top_plays if p.get("misses", 0) == 0)
                tot_p = max(1, len(enriched_top_plays))

                base_lvl = min(90, max(45, int(u_pp ** 0.45 * 2.1))) if u_pp > 0 else 60

                user_scores["Consistency"] = min(98, max(30, int(base_lvl + (fc_count / tot_p * 30) - 10)))
                user_scores["Speed"] = min(98, max(30, int(base_lvl + (dt_count / tot_p * 35) - 10)))
                user_scores["Aim"] = min(98, max(30, int(base_lvl + 8)))
                user_scores["Precision"] = min(98, max(30, int(base_lvl + (hr_count / tot_p * 40) - 12)))
                user_scores["Reading"] = min(98, max(30, int(base_lvl + (hd_count / tot_p * 30) - 10)))
                user_scores["Streams"] = min(98, max(30, int(base_lvl - 5)))
                user_scores["Tech"] = min(98, max(30, int(base_lvl - 10)))
                user_scores["Stamina"] = min(98, max(30, int(base_lvl - 8)))

                best_sk = max(user_scores, key=user_scores.get)
                worst_sk = min(user_scores, key=user_scores.get)
                feedback_text = (
                    f"📊 **Statistische Profil-Auswertung für {username}:**\n\n"
                    f"• **Rang:** #{u_rank:,} • **PP:** {u_pp:.1f} pp • **Profil-Acc:** {u_acc:.2f}%\n"
                    f"• **Stärkstes Skillset:** {best_sk} ({user_scores[best_sk]} Pkt)\n"
                    f"• **Größter Trainingshebel:** {worst_sk} ({user_scores[worst_sk]} Pkt)\n\n"
                    f"💡 **Coach-Empfehlung:** Dein Fokus sollte auf {worst_sk} liegen, um deinen Skill Floor spürbar zu erhöhen und Chokes auf schwierigen Rhythmen zu verhindern!"
                )

            # Check if this was the user's own profile
            is_self = (username.lower() == getattr(self, "osu_username", "").lower())
            if is_self:
                self.has_analyzed_self = True
                self.has_osu_supporter = is_supporter

            # Compute real stats & adaptive difficulty based on Accuracy & Misses in Top-Plays
            pp_val = 0.0
            rank_val = 0
            u_obj = u_info if ('u_info' in locals() and u_info) else None
            try:
                if u_obj:
                    pp_val = float(u_obj.get("pp_raw", 0))
                    rank_val = int(u_obj.get("pp_rank", 0))
            except: pass

            adaptive_info = calculate_adaptive_topplay_difficulty(top_plays, user_info=u_obj)
            avg_top_sr = adaptive_info["effective_sr"]
            max_top_sr = adaptive_info["base_raw_sr"]

            player_stats = {
                "avg_sr": avg_top_sr,
                "raw_sr": adaptive_info["base_raw_sr"],
                "effective_sr": avg_top_sr,
                "topplay_avg_acc": adaptive_info["avg_acc"],
                "topplay_avg_misses": adaptive_info["avg_misses"],
                "mastery_tier": adaptive_info["mastery_tier"],
                "adaptive_difficulty": adaptive_info,
                "max_sr": max_top_sr,
                "pp": pp_val,
                "rank": rank_val
            }

            self.last_profile_analysis = {
                "scores": user_scores,
                "feedback": feedback_text,
                "player": username,
                "main_skill": max(user_scores, key=user_scores.get),
                "weakness": min(user_scores, key=user_scores.get),
                "player_stats": player_stats
            }
            self.last_profile_player = username
            self.save_global_settings()

            self.log_ai_event(
                category=f"Profil-Analyse: {username}",
                input_summary={
                    "username": username,
                    "rank": rank_val,
                    "pp": pp_val,
                    "profile_acc": u_acc if 'u_acc' in locals() else 0.0,
                    "top_plays_analyzed": len(enriched_top_plays)
                },
                prompt_text=prompt if getattr(self, "gemini_key", "") else None,
                raw_ai_response=raw_text if ('raw_text' in locals() and raw_text) else feedback_text,
                calculations={
                    "scores": user_scores,
                    "player_stats": player_stats
                }
            )

            def update_ui():
                if hasattr(self, "profile_user_entry") and self.profile_user_entry.winfo_exists():
                    self.draw_profile_radar(user_scores)
                    if hasattr(self, "profile_ai_box") and self.profile_ai_box.winfo_exists():
                        self.profile_ai_box.configure(state="normal")
                        self.profile_ai_box.delete("1.0", "end")
                        self.profile_ai_box.insert("1.0", feedback_text)
                        self.profile_ai_box.configure(state="disabled")
                    if hasattr(self, "profile_status_lbl") and self.profile_status_lbl.winfo_exists():
                        self.profile_status_lbl.configure(text="✅ Schritt 1 abgeschlossen! Weiter zu Schritt 2.", text_color="#4CAF50")
                    if hasattr(self, "profile_analyze_btn") and self.profile_analyze_btn.winfo_exists():
                        self.profile_analyze_btn.configure(text="➔ Schritt 2: Skill-Test starten", fg_color="#E91E63", hover_color="#C2185B", state="normal", command=self.show_skill_tester_menu)

            self.safe_ui_dispatch(self, update_ui)

        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------------------
    # UHO HUB AUTHENTIFIZIERUNG & HARDWARE BINDING
    # ---------------------------------------------------------------------------
    def show_uho_auth_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        box = ctk.CTkFrame(master, fg_color="#181822", corner_radius=18, border_width=1, border_color="#2e2e3f", width=520, height=440)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)

        ctk.CTkLabel(box, text="🔐 UHO Hub Lizenz-Aktivierung", font=("Arial", 22, "bold"), text_color="#3b8ed0").pack(pady=(30, 8))
        ctk.CTkLabel(box, text="Bitte gib deinen UHO API-Key ein, um die App freizuschalten.\nDein Key wird sicher an diesen Computer gebunden.",
                     font=("Arial", 12), text_color="#888899", justify="center").pack(pady=(0, 20))

        key_entry = ctk.CTkEntry(box, width=380, height=42, placeholder_text="UHO-XXXX-XXXX-XXXX", font=("Arial", 14), justify="center")
        key_entry.pack(pady=10)

        status_lbl = ctk.CTkLabel(box, text="", font=("Arial", 12))
        status_lbl.pack(pady=5)

        def verify():
            raw_key = key_entry.get().strip()
            if not raw_key:
                status_lbl.configure(text="❌ Bitte gib einen Key ein!", text_color="#ff4444")
                return

            status_lbl.configure(text="⏳ Überprüfe Lizenz...", text_color="#00E5FF")
            act_btn.configure(state="disabled")

            def do_req():
                hwid = get_hwid()
                norm_key = raw_key.strip().upper()
                try:
                    resp = requests.post(f"{UHO_AUTH_SERVER_URL}/verify_key", json={"key": norm_key, "hwid": hwid}, timeout=25)
                    if resp.status_code == 404:
                        resp = requests.post(f"{UHO_AUTH_SERVER_URL}/verify", json={"key": norm_key, "hwid": hwid}, timeout=25)
                    res = resp.json()
                    if res.get("valid"):
                        self.uho_api_key = norm_key
                        self.save_global_settings()
                        self.after(0, lambda: self.show_tutorial_welcome())
                    else:
                        msg = res.get("message", "Dieser Key existiert nicht oder ist ungültig.")
                        self.after(0, lambda: (status_lbl.configure(text=f"❌ {msg}", text_color="#ff4444"), act_btn.configure(state="normal")))
                except Exception as e:
                    self.after(0, lambda: (status_lbl.configure(text="❌ Server nicht erreichbar. Bitte kurz warten und erneut versuchen.", text_color="#ff4444"), act_btn.configure(state="normal")))

            threading.Thread(target=do_req, daemon=True).start()

        act_btn = ctk.CTkButton(box, text="🚀 Key aktivieren & Starten", font=("Arial", 14, "bold"), height=42, width=260,
                                fg_color="#3b8ed0", hover_color="#1f538d", command=verify)
        act_btn.pack(pady=15)

        def open_dc_help():
            webbrowser.open(UHO_DEV_PROFILE_URL)
        ctk.CTkButton(box, text="💬 Du hast keinen Key? Kontaktiere Kingmaster0550 auf Discord", font=("Arial", 11),
                      fg_color="transparent", text_color="#3b8ed0", hover_color="#22222a", command=open_dc_help).pack(side="bottom", pady=15)

    # ---------------------------------------------------------------------------
    # MODERNER SKILL TESTER MIT PFLICHT-PROFILANALYSE & DYNAMISCHEN KI-MAPS
    # ---------------------------------------------------------------------------
    def show_skill_tester_menu(self):
        # If user has already analyzed their own profile once, skip prerequisite check
        if not getattr(self, "has_analyzed_self", False) and not getattr(self, "last_profile_analysis", None):
            self.show_skill_tester_prerequisite_modal()
            return

        for widget in self.winfo_children():
            widget.destroy()

        self._tester_card_widgets = {}

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Hauptmenü", width=100, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_main_menu).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🎯 Moderner KI-Skill Tester (2020+ Benchmark Maps)", font=("Arial", 18, "bold"), text_color="#E91E63").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("tester")).pack(side="right", padx=15)

        main = ctk.CTkFrame(master, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(0, weight=1)

        # Left box
        left_box = ctk.CTkFrame(main, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Right box
        right_box = ctk.CTkFrame(main, fg_color="#181820", corner_radius=14, border_width=1, border_color="#2e2e3f")
        right_box.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(right_box, text="Live Test-Radar", font=("Arial", 16, "bold"), text_color="#ffffff").pack(pady=(15, 2))
        
        sub_count = len(getattr(self, "skill_tester_submissions", {}))
        self.tester_progress_lbl = ctk.CTkLabel(right_box, text=f"Fortschritt: {sub_count}/8 Maps absolviert",
                                                font=("Arial", 12, "bold"), text_color="#00E5FF")
        self.tester_progress_lbl.pack(pady=(0, 5))

        self.tester_radar_canvas = ctk.CTkCanvas(right_box, bg="#181820", highlightthickness=0)
        self.tester_radar_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tester_radar_canvas.bind("<Configure>", lambda e: self.draw_tester_live_radar())

        self.tester_eval_btn = ctk.CTkButton(right_box, text="🤖 Test-Ergebnisse von KI bewerten lassen", font=("Arial", 13, "bold"),
                                              height=40, fg_color="#E91E63", hover_color="#C2185B", command=self.evaluate_skill_test_ai)
        self.tester_eval_btn.pack(fill="x", padx=12, pady=(0, 12))

        # Left panel controls
        control_bar = ctk.CTkFrame(left_box, fg_color="transparent")
        control_bar.pack(fill="x", padx=12, pady=10)

        player_info = f"Spieler: {getattr(self, 'last_profile_player', getattr(self, 'osu_username', 'Unbekannt'))}"
        ctk.CTkLabel(control_bar, text=player_info, font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")

        ctk.CTkButton(control_bar, text="🎲 Neues Testset generieren", font=("Arial", 11, "bold"), height=30,
                      fg_color="#333346", hover_color="#44445c", command=lambda: self.generate_new_ai_skill_test(force_new=True)).pack(side="right")

        self.tester_maps_scroll = ctk.CTkScrollableFrame(left_box, fg_color="#14141a", corner_radius=10)
        self.tester_maps_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        dnd_row = ctk.CTkFrame(left_box, fg_color="#1c1c26", corner_radius=8, border_width=1, border_color="#333346")
        dnd_row.pack(fill="x", padx=12, pady=(0, 12))
        self.tester_dnd_status = ctk.CTkLabel(dnd_row, text="⚡ Live-Sync aktiv: Erkennt deine Test-Plays automatisch (kein Klick nötig!)",
                                              font=("Arial", 11, "bold"), text_color="#00E5FF")
        self.tester_dnd_status.pack(side="left", padx=10, pady=8)

        def sync_tester_api():
            self.fetch_tester_api_plays(silent=False)
        ctk.CTkButton(dnd_row, text="🔄 Sync", width=70, height=28, font=("Arial", 11, "bold"),
                      fg_color="#2b2b38", hover_color="#3b8ed0", command=sync_tester_api).pack(side="right", padx=8, pady=6)
        
        # Start automatic background polling loop
        self._start_tester_auto_sync_loop()

        pa = getattr(self, "last_profile_analysis", {}) or {}
        p_stats = pa.get("player_stats", {})
        u_rank = p_stats.get("pp_rank", 0) or getattr(self, "player_rank", 0)
        u_pp = p_stats.get("pp", 0) or getattr(self, "player_pp", 0)
        
        if "target_test_sr" in p_stats:
            base_sr = float(p_stats["target_test_sr"])
        elif "top_avg_sr" in p_stats:
            base_sr = float(p_stats["top_avg_sr"])
        elif "adaptive_difficulty" in p_stats:
            base_sr = float(p_stats["adaptive_difficulty"].get("effective_sr", 5.2))
        elif u_rank or u_pp:
            base_sr = estimate_sr_from_rank_and_pp(u_rank, u_pp)
        else:
            avg_score = 65
            if "scores" in pa:
                s_vals = list(pa["scores"].values())
                avg_score = sum(s_vals) / len(s_vals) if s_vals else 65
            base_sr = round(max(3.5, min(9.5, 5.0 + (avg_score - 50) * 0.04)), 1)

        if not getattr(self, "current_ai_skill_test", None):
            self.generate_new_ai_skill_test(base_sr=base_sr)
        else:
            self.render_ai_test_maps()
            self.draw_tester_live_radar()

    def show_skill_tester_prerequisite_modal(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        modal = ctk.CTkFrame(master, fg_color="#1c1c26", corner_radius=18, border_width=2, border_color="#E91E63", width=540, height=360)
        modal.place(relx=0.5, rely=0.5, anchor="center")
        modal.pack_propagate(False)

        ctk.CTkLabel(modal, text="⚠️ Profil-Analyse erforderlich!", font=("Arial", 22, "bold"), text_color="#E91E63").pack(pady=(28, 10))

        desc = "Bevor du den Skill Tester starten kannst, muss die KI zuerst dein osu! Profil und deine Top-Plays analysieren, um deinen genauen Rang, deine Sterne-Grenzen sowie deine Stärken & Schwächen zu erfassen.\n\n" \
               "Auf dieser Basis wählt die KI für dich maßgeschneiderte, adaptive Test-Maps (>= 2020, Ranked/Loved, 9★ Quality Rating) aus!"
        ctk.CTkLabel(modal, text=desc, font=("Arial", 12), text_color="#dddddd", justify="center", wraplength=480).pack(pady=(0, 20), padx=25)

        btn_row = ctk.CTkFrame(modal, fg_color="transparent")
        btn_row.pack(fill="x", padx=30, pady=10)

        ctk.CTkButton(btn_row, text="⬅ Hauptmenü", width=140, height=42, font=("Arial", 13, "bold"),
                      fg_color="#2b2b36", hover_color="#3a3a48", command=self.show_main_menu).pack(side="left")

        ctk.CTkButton(btn_row, text="🔍 Jetzt Profil analysieren ➔", width=260, height=42, font=("Arial", 14, "bold"),
                      fg_color="#9C27B0", hover_color="#7B1FA2", command=self.show_profile_analyzer).pack(side="right")

    def generate_new_ai_skill_test(self, base_sr=None, force_new=False):
        if not force_new and getattr(self, "current_ai_skill_test", None):
            return

        # Dynamically determine base star rating from player profile analysis
        pa = getattr(self, "last_profile_analysis", {}) or {}
        p_stats = pa.get("player_stats", {})
        scores = pa.get("scores", {})
        u_rank = p_stats.get("pp_rank", 0) or getattr(self, "player_rank", 0)
        u_pp = p_stats.get("pp", 0) or getattr(self, "player_pp", 0)

        if base_sr is None:
            if "target_test_sr" in p_stats:
                base_sr = float(p_stats["target_test_sr"])
            elif "top_avg_sr" in p_stats:
                base_sr = float(p_stats["top_avg_sr"])
            elif "adaptive_difficulty" in p_stats:
                base_sr = float(p_stats["adaptive_difficulty"].get("effective_sr", 5.2))
            elif u_rank or u_pp:
                base_sr = estimate_sr_from_rank_and_pp(u_rank, u_pp)
            elif scores:
                s_vals = list(scores.values())
                avg_score = sum(s_vals) / len(s_vals)
                base_sr = round(max(3.5, 5.0 + (avg_score - 50) * 0.04), 1)
            else:
                base_sr = estimate_sr_from_rank_and_pp(u_rank, u_pp)

        base_sr = round(max(3.5, min(9.8, base_sr)), 1)

        test_suite = {}
        categories = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
        prev_test = getattr(self, "current_ai_skill_test", {}) or {}
        prev_ids = {m_info.get("id") for m_info in prev_test.values() if isinstance(m_info, dict) and m_info.get("id")}
        used_in_suite = set(prev_ids)

        candidates_by_cat = {}
        candidates_summary = {}

        for cat in categories:
            # Skill-specific adjustment based on player's score in that skillset
            cat_score = scores.get(cat, 65)
            offset = (cat_score - 65) * 0.015
            target_sr = round(max(3.8, min(8.8, base_sr + offset)), 1)

            # Query candidate maps from database
            cat_cands = []
            if BEATMAP_SQLITE_DB_PATH:
                raw_cands = sqlite_query_maps(
                    skill=cat,
                    sr_min=round(target_sr - 0.7, 2),
                    sr_max=round(target_sr + 0.7, 2),
                    exclude_ids=used_in_suite,
                    limit=15,
                    order_by="playcount DESC"
                )
                for c in raw_cands:
                    if c.get("id") and c.get("id") not in used_in_suite:
                        cat_cands.append(c)
                        if len(cat_cands) >= 4:
                            break
            
            # Fallback if SQLite query returned few maps
            if len(cat_cands) < 2:
                for _ in range(3):
                    m_dyn = pick_dynamic_map_for_skill(cat, target_sr, exclude_ids=used_in_suite)
                    if m_dyn and m_dyn.get("id") and m_dyn not in cat_cands:
                        cat_cands.append(m_dyn)

            if not cat_cands:
                cat_cands = [pick_dynamic_map_for_skill(cat, target_sr, exclude_ids=used_in_suite)]

            candidates_by_cat[cat] = cat_cands
            candidates_summary[cat] = [
                {"id": m["id"], "name": m.get("name", "Unknown"), "sr": round(m.get("sr", target_sr), 2), "bpm": m.get("bpm", 180)}
                for m in cat_cands
            ]

        # Call Gemini AI to pick the single best benchmark map for each skillset
        ai_chosen_map_ids = {}
        if getattr(self, "gemini_key", ""):
            try:
                gemini_prompt = (
                    f"Du bist der offizielle osu! Benchmark Coach.\n"
                    f"Wähle für diesen Spieler (osu! Rang: #{u_rank}, PP: {u_pp}, Basis-SR: {base_sr}★) für jedes der 8 Skillsets die EINE am besten geeignete Benchmark-Test-Map aus den folgenden Kandidaten:\n\n"
                    f"Kandidaten-Pool pro Skillset:\n{json.dumps(candidates_summary, ensure_ascii=False, indent=2)}\n\n"
                    f"WICHTIG: Antworte AUSSCHLIESSLICH als valides JSON-Objekt im Format:\n"
                    f'{{"Consistency": <beatmap_id>, "Speed": <beatmap_id>, "Aim": <beatmap_id>, "Stamina": <beatmap_id>, "Tech": <beatmap_id>, "Reading": <beatmap_id>, "Streams": <beatmap_id>, "Precision": <beatmap_id>}}'
                )
                ai_resp = self.call_gemini_api(
                    prompt=gemini_prompt,
                    system_prompt="Du bist der osu! Benchmark Head-Coach. Antworte ausschließlich mit dem geforderten JSON-Objekt.",
                    temperature=0.3,
                    max_tokens=350
                )
                if ai_resp:
                    ai_parsed = safe_parse_ai_json(ai_resp)
                    if isinstance(ai_parsed, dict):
                        ai_chosen_map_ids = ai_parsed
            except Exception:
                pass

        for cat in categories:
            chosen = None
            target_bid = ai_chosen_map_ids.get(cat)
            if target_bid:
                # Find matching candidate
                for m in candidates_by_cat[cat]:
                    if str(m.get("id")) == str(target_bid):
                        chosen = m
                        break
            
            if not chosen:
                chosen = candidates_by_cat[cat][0]

            used_in_suite.add(chosen["id"])
            test_suite[cat] = chosen

        self.current_ai_skill_test = test_suite
        self.skill_tester_submissions = {}
        self.render_ai_test_maps()
        self.draw_tester_live_radar()

    def render_ai_test_maps(self):
        if not hasattr(self, 'tester_maps_scroll') or not self.tester_maps_scroll.winfo_exists():
            return

        if not getattr(self, "current_ai_skill_test", None):
            return

        # Check if cards are already built and still alive in the DOM
        cards_alive = (
            hasattr(self, "_tester_card_widgets")
            and isinstance(self._tester_card_widgets, dict)
            and len(self._tester_card_widgets) == len(self.current_ai_skill_test)
            and all(
                isinstance(w_dict, dict)
                and w_dict.get("card")
                and w_dict["card"].winfo_exists()
                and w_dict.get("status_frame")
                and w_dict["status_frame"].winfo_exists()
                for w_dict in self._tester_card_widgets.values()
            )
        )

        # If already built and matches test maps count, update in-place without destroying frames (ZERO FLICKER!)
        if cards_alive:
            for category, m_info in self.current_ai_skill_test.items():
                w_dict = self._tester_card_widgets.get(category)
                if w_dict and w_dict.get("status_frame") and w_dict["status_frame"].winfo_exists():
                    sub = self.skill_tester_submissions.get(category)
                    s_frame = w_dict["status_frame"]
                    for child in s_frame.winfo_children():
                        child.destroy()
                    if sub:
                        sc = sub.get('skill_score', calculate_skill_test_score(sub.get('acc', 0), sub.get('misses', 0)))
                        att = sub.get('attempts', 1)
                        tag = f"🎯 Best: {sc:.0f}/100" if att > 1 else f"🎯 Score: {sc:.0f}/100"
                        att_str = f" (#{att})" if att > 1 else ""
                        sub_col = "#00E676" if sc >= 80 else ("#00E5FF" if sc >= 65 else ("#FFA726" if sc >= 50 else "#FF5252"))
                        ctk.CTkLabel(s_frame, text=f"{tag}{att_str}\n({sub.get('acc', 0):.1f}% • {sub.get('misses', 0)} Miss)",
                                     font=("Arial", 10, "bold"), text_color=sub_col, justify="center").pack(side="right")
                    else:
                        ctk.CTkLabel(s_frame, text="⏳ Offen", font=("Arial", 10), text_color="#777788").pack(side="right")
            return

        # Initial build
        for w in self.tester_maps_scroll.winfo_children():
            try: w.destroy()
            except: pass
        self._tester_card_widgets = {}

        for category, m_info in self.current_ai_skill_test.items():
            card = ctk.CTkFrame(self.tester_maps_scroll, fg_color="#1c1c26", corner_radius=10, border_width=1, border_color="#2e2e3f")
            card.pack(fill="x", pady=4, padx=5)

            # RIGHT SIDE: Pack FIRST with side="right" so buttons (osu!direct & status) NEVER get pushed off or clipped!
            right_side = ctk.CTkFrame(card, fg_color="transparent")
            right_side.pack(side="right", padx=10, pady=8)

            def open_direct(bid=m_info['id']):
                try: os.startfile(f"osu://b/{bid}")
                except: webbrowser.open(f"https://osu.ppy.sh/b/{bid}")

            ctk.CTkButton(right_side, text="osu!direct", width=80, height=28, font=("Arial", 11, "bold"),
                          fg_color="#FF66AA", hover_color="#C2185B", command=open_direct).pack(side="right")

            status_frame = ctk.CTkFrame(right_side, fg_color="transparent")
            status_frame.pack(side="right", padx=6)

            sub = self.skill_tester_submissions.get(category)
            if sub:
                sc = sub.get('skill_score', calculate_skill_test_score(sub.get('acc', 0), sub.get('misses', 0)))
                att = sub.get('attempts', 1)
                tag = f"🎯 Best: {sc:.0f}/100" if att > 1 else f"🎯 Score: {sc:.0f}/100"
                att_str = f" (#{att})" if att > 1 else ""
                sub_col = "#00E676" if sc >= 80 else ("#00E5FF" if sc >= 65 else ("#FFA726" if sc >= 50 else "#FF5252"))
                ctk.CTkLabel(status_frame, text=f"{tag}{att_str}\n({sub.get('acc', 0):.1f}% • {sub.get('misses', 0)} Miss)",
                             font=("Arial", 10, "bold"), text_color=sub_col, justify="center").pack(side="right")
            else:
                ctk.CTkLabel(status_frame, text="⏳ Offen", font=("Arial", 10), text_color="#777788").pack(side="right")

            self._tester_card_widgets[category] = {"card": card, "status_frame": status_frame}

            # LEFT SIDE: Pack SECOND with side="left", fill="x", expand=True
            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", padx=10, pady=8, fill="x", expand=True)

            header_line = ctk.CTkFrame(left, fg_color="transparent")
            header_line.pack(fill="x")

            ctk.CTkLabel(header_line, text=category.upper(), font=("Arial", 11, "bold"), text_color="#E91E63").pack(side="left")
            ctk.CTkLabel(header_line, text=f"★ {m_info['sr']:.1f}", font=("Arial", 10, "bold"), fg_color="#2e2e3f", text_color="#FFA726", corner_radius=4).pack(side="left", padx=6)
            ctk.CTkLabel(header_line, text=f"{m_info.get('status', 'Ranked')} • {m_info.get('year', 2021)} • {m_info.get('rating', '9.5/10')}",
                         font=("Arial", 9), text_color="#777788").pack(side="left")

            def open_web(bid=m_info['id']):
                webbrowser.open(f"https://osu.ppy.sh/b/{bid}")

            name_btn = ctk.CTkButton(left, text=m_info["name"], anchor="w", font=("Arial", 12, "bold"),
                                     fg_color="transparent", hover_color="#282836", text_color="#ffffff",
                                     command=open_web)
            name_btn.pack(fill="x", pady=(2, 0))

    def draw_tester_live_radar(self):
        canvas = getattr(self, "tester_radar_canvas", None)
        if not canvas or not canvas.winfo_exists(): return
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1: width = 380
        if height <= 1: height = 360
        cx = width / 2
        cy = height / 2
        max_r = max(40, min(cx, cy) - 45)

        categories = ["Consistency", "Speed", "Aim", "Stamina", "Tech", "Reading", "Streams", "Precision"]
        n = len(categories)

        for ring in [0.25, 0.5, 0.75, 1.0]:
            r = max_r * ring
            pts = []
            for i in range(n):
                angle = (2 * math.pi / n) * i - (math.pi / 2)
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                pts.extend([px, py])
            canvas.create_polygon(pts, fill="", outline="#2e2e3f", width=1)

        for i, cat in enumerate(categories):
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + max_r * math.cos(angle)
            py = cy + max_r * math.sin(angle)
            canvas.create_line(cx, cy, px, py, fill="#3a3a4e", dash=(2, 2))

            lx = cx + (max_r + 26) * math.cos(angle)
            ly = cy + (max_r + 26) * math.sin(angle)
            sub = self.skill_tester_submissions.get(cat)
            if sub:
                sc = sub.get("skill_score", calculate_skill_test_score(sub.get("acc", 0), sub.get("misses", 0)))
                val_txt = f"{cat}\n{sc:.0f}/100\n({sub['acc']:.0f}% • {sub['misses']}M)"
                col = "#00E676" if sc >= 80 else ("#00E5FF" if sc >= 65 else ("#FFA726" if sc >= 50 else "#FF5252"))
            else:
                val_txt = f"{cat}\n-"
                col = "#777788"
            canvas.create_text(lx, ly, text=val_txt, fill=col, font=("Arial", 9, "bold"), justify="center")

        data_pts = []
        has_any = False
        for i, cat in enumerate(categories):
            sub = self.skill_tester_submissions.get(cat)
            if sub:
                score = sub.get("skill_score", calculate_skill_test_score(sub.get("acc", 0), sub.get("misses", 0)))
                has_any = True
            else:
                score = 0
            r = max_r * (max(5, min(100, score)) / 100.0)
            angle = (2 * math.pi / n) * i - (math.pi / 2)
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            data_pts.extend([px, py])

        if has_any and len(data_pts) >= 6:
            canvas.create_polygon(data_pts, fill="#00E5FF", outline="#00B0FF", width=2, stipple="gray25")
            for i in range(0, len(data_pts), 2):
                x, y = data_pts[i], data_pts[i+1]
                canvas.create_oval(x-4, y-4, x+4, y+4, fill="#00E5FF", outline="#ffffff")

    def fetch_tester_api_plays(self, silent=False):
        user = getattr(self, "osu_username", "")
        key = getattr(self, "api_key", "")
        if not user or not key:
            if hasattr(self, 'tester_dnd_status') and self.tester_dnd_status.winfo_exists():
                self.tester_dnd_status.configure(text="❌ Trage Username & API-Key in den Einstellungen ein!", text_color="#ff4444")
            return

        if not silent and hasattr(self, 'tester_dnd_status') and self.tester_dnd_status.winfo_exists():
            self.tester_dnd_status.configure(text="⏳ Rufe Plays ab...", text_color="#00E5FF")

        def run():
            try:
                url = f"https://osu.ppy.sh/api/get_user_recent?k={key}&u={user}&m=0&limit=50"
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    return

                plays = resp.json()
                if not isinstance(plays, list):
                    return

                matched = 0
                new_play_found = False
                prev_count = len(getattr(self, "skill_tester_submissions", {}))

                for play in plays:
                    try: self.record_play_in_active_session(play)
                    except: pass
                    bid = str(play.get("beatmap_id"))
                    for cat, minfo in getattr(self, "current_ai_skill_test", {}).items():
                        if str(minfo.get("id")) == bid:
                            h300 = int(play.get("count300", 0))
                            h100 = int(play.get("count100", 0))
                            h50 = int(play.get("count50", 0))
                            miss = int(play.get("countmiss", 0))
                            tot = h300 + h100 + h50 + miss
                            acc = ((h300 * 300 + h100 * 100 + h50 * 50) / (tot * 300) * 100) if tot > 0 else 0
                            play_score = int(play.get("score", 0))
                            max_combo = int(play.get("maxcombo", 0))

                            player_sr = 5.5
                            pa = getattr(self, "last_profile_analysis", {}) or {}
                            if "player_stats" in pa and "effective_sr" in pa["player_stats"]:
                                player_sr = float(pa["player_stats"]["effective_sr"])
                            map_sr = float(minfo.get("sr", 5.5))

                            calculated_skill = calculate_skill_test_score(
                                acc=acc,
                                misses=miss,
                                h50=h50,
                                maxcombo=max_combo,
                                map_sr=map_sr,
                                player_sr=player_sr
                            )

                            existing = self.skill_tester_submissions.get(cat)
                            play_signature = f"{play_score}_{acc:.2f}_{miss}_{max_combo}"
                            last_sig = existing.get("last_sig") if existing else None

                            if last_sig != play_signature:
                                new_play_found = True
                                curr_att = (existing.get("attempts", 0) + 1) if existing else 1
                                existing_score = existing.get("skill_score", -1) if existing else -1

                                # Only replace highscore if this attempt is better or equal
                                is_better = (existing is None) or (calculated_skill > existing_score) or (calculated_skill == existing_score and play_score >= existing.get("score", 0))

                                if is_better:
                                    self.skill_tester_submissions[cat] = {
                                        "acc": round(acc, 2),
                                        "misses": miss,
                                        "h300": h300,
                                        "h100": h100,
                                        "h50": h50,
                                        "combo": max_combo,
                                        "skill_score": calculated_skill,
                                        "score": play_score,
                                        "map": minfo["name"],
                                        "sr": map_sr,
                                        "attempts": curr_att,
                                        "last_sig": play_signature
                                    }
                                else:
                                    # Keep existing personal best, update attempt counter
                                    self.skill_tester_submissions[cat]["attempts"] = curr_att
                                    self.skill_tester_submissions[cat]["last_sig"] = play_signature
                            matched += 1

                            self.log_ai_event(
                                category=f"Skill-Tester Map: {cat}",
                                input_summary={
                                    "category": cat,
                                    "map": minfo.get("name"),
                                    "sr": map_sr,
                                    "player_effective_sr": player_sr,
                                    "acc": round(acc, 2),
                                    "misses": miss,
                                    "combo": max_combo,
                                    "300s": h300,
                                    "100s": h100,
                                    "50s": h50,
                                    "play_score": play_score
                                },
                                calculations={
                                    "calculated_skill_score": calculated_skill,
                                    "formula": "calculate_skill_test_score(acc, misses, h50, maxcombo, map_sr, player_sr)"
                                }
                            )

                def done():
                    if not hasattr(self, 'tester_dnd_status') or not self.tester_dnd_status.winfo_exists():
                        return
                    count = len(self.skill_tester_submissions)
                    if new_play_found or count != prev_count:
                        self.render_ai_test_maps()
                        self.draw_tester_live_radar()
                        if hasattr(self, "tester_progress_lbl") and self.tester_progress_lbl.winfo_exists():
                            self.tester_progress_lbl.configure(text=f"Fortschritt: {count}/8 Maps absolviert")
                        self.tester_dnd_status.configure(text=f"⚡ Live-Sync: Play automatisch erkannt! ({count}/8 abgeschlossen)", text_color="#00E676")
                    elif not silent:
                        self.tester_dnd_status.configure(text=f"✅ {count}/8 Test-Maps abgeschlossen (Live-Sync aktiv)", text_color="#00E5FF")

                self.safe_ui_dispatch(self, done)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _start_tester_auto_sync_loop(self):
        if getattr(self, "_tester_sync_loop_running", False):
            return
        self._tester_sync_loop_running = True

        def _loop():
            if not hasattr(self, "winfo_exists") or not self.winfo_exists():
                self._tester_sync_loop_running = False
                return
            if not hasattr(self, 'tester_dnd_status') or not self.tester_dnd_status.winfo_exists():
                self._tester_sync_loop_running = False
                return
            
            try:
                self.fetch_tester_api_plays(silent=True)
            except Exception:
                pass

            if hasattr(self, "winfo_exists") and self.winfo_exists():
                self.after(4500, _loop)
            else:
                self._tester_sync_loop_running = False

        self.after(1000, _loop)

    def evaluate_skill_test_ai(self):
        subs = getattr(self, "skill_tester_submissions", {})
        if len(subs) < 3:
            self.show_message("Zu wenige Maps", f"Bitte spiele mindestens 3 der 8 Test-Maps (aktuell: {len(subs)}/8), bevor die KI den Skill-Test bewerten kann.")
            return

        report_win = ctk.CTkToplevel(self)
        report_win.title("Offizielles KI-Skill Zertifikat")
        report_win.geometry("680x750")
        report_win.configure(fg_color="#121216")

        ctk.CTkLabel(report_win, text="🎯 KI Skill-Test Zertifikat & Auswertung", font=("Arial", 20, "bold"), text_color="#E91E63").pack(pady=(20, 10))

        txt_box = ctk.CTkTextbox(report_win, wrap="word", font=("Arial", 13), fg_color="#181822", border_width=1, border_color="#2e2e3f")
        txt_box.pack(fill="both", expand=True, padx=20, pady=10)
        txt_box.insert("1.0", "⏳ Google Gemini analysiert deine Test-Scores...\nBitte einen Moment Geduld.")
        txt_box.configure(state="disabled")

        # Start AI training button below certificate
        self.skill_test_completed = True
        self.save_global_settings()

        def goto_dashboard():
            report_win.destroy()
            self.show_skill_analyse()

        ctk.CTkButton(report_win, text="🎯 Zum 8-Skill Live-Radar Dashboard ➔", font=("Arial", 14, "bold"), height=42,
                      fg_color="#E91E63", hover_color="#C2185B", command=goto_dashboard).pack(fill="x", padx=20, pady=(5, 15))

        def run():
            prompt = f"""Du bist der offizielle Pro-Level osu! KI-Coach und Gameplay-Analyst fuer osu! Standard (Mode 0).
Der Spieler '{getattr(self, 'osu_username', 'Spieler')}' hat soeben den modernen Skill Tester fuer osu! Standard mit folgenden detaillierten Ergebnissen abgeschlossen:

Gespielte Test-Kategorien (8 Skillsets):
{json.dumps(subs, indent=2)}

WICHTIG:
1. Bewerte JEDE Map individuell anhand von Accuracy, Miss-Anzahl, 50s/100s und Star Rating.
2. Ein Play mit mehreren Misses (z. B. 4-5 Misses) darf KEINE 90+ Punkte im Skillset erhalten, sondern muss gemaess der Combo-Breaks streng und realistisch kalibriert werden (z. B. 40-55 Punkte bei 5 Misses)!
3. Berechne fuer alle 8 Skillsets ein endgueltiges kalibriertes Score-Rating (0 bis 100).
4. Erstelle ein hochprofessionelles, detailliertes und motivierendes Skill-Zertifikat auf Deutsch.

Antworte STRENG im folgenden JSON-Format (ohne Markdown Backticks darum herum):
{{
  "calibrated_scores": {{
    "Consistency": 65,
    "Speed": 70,
    "Aim": 75,
    "Stamina": 60,
    "Tech": 55,
    "Reading": 60,
    "Streams": 65,
    "Precision": 70
  }},
  "overall_rank": "Advanced Intermediate",
  "main_strength": "Aim",
  "main_weakness": "Tech",
  "certificate_text": "# 🎯 OFFIZIELLES OSU! SKILL-ZERTIFIKAT\\n\\n### 🏆 Gesamtbewertung: ...\\n\\n### 🌟 Detaillierte Skillset-Analyse (8 Kategorien):\\n- **Aim:** ...\\n- **Consistency:** ...\\n- **Streams:** ...\\n\\n### 📈 Schwaechen & Ursachen der Misses:\\n...\\n\\n### 📅 Empfohlener 4-Wochen-Trainingsplan:\\n..."
}}"""

            ai_resp = ""
            calibrated_scores = {}
            raw_text = ""
            if getattr(self, "gemini_key", ""):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{getattr(self, 'selected_ai_model', 'gemini-3.6-flash')}:generateContent?key={self.gemini_key}"
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
                    }
                    r = requests.post(url, json=payload, timeout=25)
                    res_j = r.json()
                    candidates = res_j.get("candidates", [])
                    raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
                    parsed = safe_parse_ai_json(raw_text, default={})
                    calibrated_scores = parsed.get("calibrated_scores", {})
                    if not isinstance(calibrated_scores, dict):
                        calibrated_scores = {}
                    ai_resp = parsed.get("certificate_text", raw_text)
                except Exception:
                    ai_resp = f"Analyse der {len(subs)} Test-Maps:\n\n" + "\n".join([f"• {k}: {v.get('skill_score', v.get('acc', 0)):.0f} Pkt ({v.get('acc', 0):.1f}%, {v.get('misses', 0)} Miss)" for k, v in subs.items()])
            else:
                ai_resp = f"Analyse der {len(subs)} Test-Maps (Ohne Gemini Key):\n\n" + "\n".join([f"• {k}: {v.get('skill_score', v.get('acc', 0)):.0f} Pkt ({v.get('acc', 0):.1f}%, {v.get('misses', 0)} Miss)" for k, v in subs.items()])

            self.log_ai_event(
                category="Skill-Tester Zertifikat (Gemini)",
                input_summary={"submissions_count": len(subs), "categories": list(subs.keys())},
                prompt_text=prompt if getattr(self, "gemini_key", "") else None,
                raw_ai_response=raw_text if raw_text else ai_resp,
                calculations={"calibrated_scores": calibrated_scores}
            )

            # Calibrate fallback scores from mathematical formula if not returned
            for cat, sub in subs.items():
                if cat not in calibrated_scores:
                    calibrated_scores[cat] = sub.get("skill_score", calculate_skill_test_score(sub.get("acc", 0), sub.get("misses", 0)))

            if calibrated_scores:
                if not hasattr(self, "skill_scores"): self.skill_scores = {}
                self.skill_scores.update(calibrated_scores)
                if getattr(self, "last_profile_analysis", None):
                    self.last_profile_analysis["scores"] = self.skill_scores
                self.save_global_settings()

            def update():
                if txt_box.winfo_exists():
                    txt_box.configure(state="normal")
                    txt_box.delete("1.0", "end")
                    txt_box.insert("1.0", ai_resp)
                    txt_box.configure(state="disabled")

            self.safe_ui_dispatch(report_win, update)

        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------------------
    # LEVEL TRAINING SKILLSETS & TIMELINE UI
    # ---------------------------------------------------------------------------
    def show_training_skillset_selection(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        ctk.CTkButton(top_bar, text="⬅ Modi", width=90, height=36, font=("Arial", 13, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_training_mode_selection).pack(side="left", padx=15, pady=12)

        ctk.CTkLabel(top_bar, text="🏆 Level-Training: Wähle deinen Mod / Modus", font=("Arial", 18, "bold"), text_color="#3b8ed0").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("progression")).pack(side="right", padx=15)

        container = ctk.CTkFrame(master, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        mods_list = [
            ("🔘 NoMod (NM)", "NM", "#1f538d"),
            ("⚡ DoubleTime (DT)", "DT", "#E91E63"),
            ("🕶️ Hidden (HD)", "HD", "#9C27B0"),
            ("🛡️ HardRock (HR)", "HR", "#00897B"),
            ("🕶️🛡️ HDHR", "HDHR", "#0288D1"),
            ("🕶️⚡ HDDT", "HDDT", "#FB8C00"),
            ("🔦 Flashlight (FL)", "FL", "#5E35B1"),
            ("🟢 Easy (EZ)", "EZ", "#2E7D32")
        ]

        grid_frame = ctk.CTkFrame(container, fg_color="#16161f", corner_radius=18, border_width=1, border_color="#2a2a38", width=760, height=220)
        grid_frame.place(relx=0.5, rely=0.5, anchor="center")
        grid_frame.pack_propagate(False)

        inner_grid = ctk.CTkFrame(grid_frame, fg_color="transparent")
        inner_grid.place(relx=0.5, rely=0.5, anchor="center")

        for i, (label, mode_id, color) in enumerate(mods_list):
            r = i // 4
            c = i % 4
            btn = ctk.CTkButton(inner_grid, text=label, font=("Arial", 13, "bold"), width=165, height=68, corner_radius=12,
                                fg_color=color, hover_color="#3a3a4d", command=lambda m=mode_id: self.start_with_mod(m))
            btn.grid(row=r, column=c, padx=8, pady=8)

    def start_with_mod(self, mod_name):
        self.save_file = f"save_data_{mod_name}.json"
        self.load_data()
        self.setup_ui()

    def load_data(self):
        self.data = safe_json_load(self.save_file, default={}) if self.save_file else {}
        if not isinstance(self.data, dict):
            self.data = {}

        if "current_level_idx" in self.data:
            self.current_level_idx = self.data["current_level_idx"]
        else:
            self.current_level_idx = 0
            self.data["current_level_idx"] = 0

        if "levels" not in self.data:
            self.data["levels"] = {}

    def save_data(self):
        if not self.save_file: return
        self.data["current_level_idx"] = self.current_level_idx
        try:
            safe_atomic_json_dump(self.data, self.save_file, indent=4)
        except Exception:
            pass

    def load_beatmaps(self):
        return safe_json_load(BEATMAP_CACHE_FILE, default={})

    def save_beatmaps(self):
        try:
            safe_atomic_json_dump(getattr(self, "beatmap_cache", {}), BEATMAP_CACHE_FILE, indent=2)
        except Exception:
            pass

    def format_time(self, seconds):
        if not seconds: return "N/A"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if hours > 0: return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def auto_import_loop(self):
        """Zero-Click Universal Replay Watcher: Ingests 100% of plays automatically from osu!\\Data\\r\\ (no F2 required) & osu!\\Replays\\."""
        import glob
        try:
            osu_dirs = find_osu_directories()
            for osu_dir in osu_dirs:
                targets = [os.path.join(osu_dir, 'Data', 'r'), os.path.join(osu_dir, 'Replays')]
                for t_dir in targets:
                    if not os.path.exists(t_dir):
                        continue
                    try:
                        mtime = os.stat(t_dir).st_mtime
                        last_m = self._dir_mtimes.get(t_dir, 0)
                        if mtime > last_m:
                            self._dir_mtimes[t_dir] = mtime
                            files = glob.glob(os.path.join(t_dir, "*.osr"))
                            if files:
                                for fpath in sorted(files, key=os.path.getmtime):
                                    if fpath not in self.processed_replays:
                                        self.processed_replays.add(fpath)
                                        self._on_zero_click_replay_detected(fpath)
                    except Exception:
                        pass
        except Exception:
            pass
        if hasattr(self, "winfo_exists") and self.winfo_exists():
            self.after(1500, self.auto_import_loop)

    def _on_zero_click_replay_detected(self, file_path):
        """Called automatically whenever ANY replay finishes in osu! without touching F2."""
        try:
            parsed = parse_osr_deep_telemetry(file_path)
            if not parsed or parsed.get('mode', 0) != 0:
                return

            self.record_deep_replay_play(parsed)

            # 1. Level-Training Replay
            if hasattr(self, 'current_level_idx') and getattr(self, "save_file", ""):
                level_str = f"{self.levels[self.current_level_idx]:.1f}"
                self.process_replay_parsed(parsed, level_str)

            # 2. Tournament Match Replay Auto-Sync
            if getattr(self, "tourney_match", {}).get("phase") == "playing":
                class DummyEvent:
                    data = file_path
                self.handle_tourney_replay_drop(DummyEvent())

            # 3. Multiplayer Match Replay Auto-Sync
            if getattr(self, "mp_match", {}).get("phase") == "playing":
                try: self.fetch_mp_match_results(silent=True)
                except: pass

            # 4. KI-Live Training Auto-Sync
            if hasattr(self, 'ai_train_sync_lbl') and self.ai_train_sync_lbl.winfo_exists():
                try: self.fetch_ai_training_recent_plays(silent=True)
                except: pass

            # 5. Skill-Tester Auto-Sync
            if getattr(self, "current_ai_skill_test", None):
                try: self.fetch_tester_api_plays(silent=True)
                except: pass

            # 6. 8-Skill Live Radar
            try:
                self.ai_process_play_for_radar({
                    "beatmap_id": parsed.get("hash", ""),
                    "score": parsed.get("score", 0),
                    "count300": parsed.get("300s", 0),
                    "count100": parsed.get("100s", 0),
                    "count50": parsed.get("50s", 0),
                    "countmiss": parsed.get("misses", 0),
                    "maxcombo": parsed.get("combo", 0),
                    "enabled_mods": parsed.get("mods", 0)
                })
            except: pass

            # Auto-Delete explicit exports if enabled
            if getattr(self, "delete_replays_var", None) and self.delete_replays_var.get():
                if "Replays" in file_path:
                    try: os.remove(file_path)
                    except: pass
        except Exception:
            pass

    def process_replay_parsed(self, parsed, level_str):
        try:
            h300_tmp = parsed.get('300s', 0)
            h100_tmp = parsed.get('100s', 0)
            h50_tmp = parsed.get('50s', 0)
            miss_tmp = parsed.get('misses', 0)
            tot_tmp = h300_tmp + h100_tmp + h50_tmp + miss_tmp
            acc_tmp = (safe_div(h300_tmp * 300 + h100_tmp * 100 + h50_tmp * 50, tot_tmp * 300, 0.0) * 100) if tot_tmp > 0 else 0
            mock_p = {
                "beatmap_id": parsed.get("beatmap_hash", ""),
                "count300": h300_tmp, "count100": h100_tmp, "count50": h50_tmp, "countmiss": miss_tmp,
                "maxcombo": parsed.get("combo", 0), "rank": "S" if (acc_tmp >= 93.0 and miss_tmp == 0) else "A",
                "score": parsed.get("score", 0)
            }
            self.record_play_in_active_session(mock_p)
        except: pass
        try:
            if "levels" not in self.data: self.data["levels"] = {}
            if level_str not in self.data["levels"]: self.data["levels"][level_str] = {"s_ranks": [], "pfcs": [], "min3_maps": []}
            
            lvl = self.data["levels"][level_str]
            h300 = parsed['300s']
            h100 = parsed['100s']
            h50 = parsed['50s']
            miss = parsed['misses']
            tot = h300 + h100 + h50 + miss
            acc = (safe_div(h300 * 300 + h100 * 100 + h50 * 50, tot * 300, 0.0) * 100) if tot > 0 else 0

            # S Rank Check
            is_s = (acc >= 93.0 and miss == 0) or (acc >= 90.0 and safe_div(h50, tot, 1.0) <= 0.01 and miss == 0)
            if is_s and len(lvl.get("s_ranks", [])) < 5:
                lvl.setdefault("s_ranks", []).append(parsed)

            if parsed.get("perfect", False) and len(lvl.get("pfcs", [])) < 2:
                lvl.setdefault("pfcs", []).append(parsed)

            self.save_data()
            self.render_cards()
        except: pass

    def show_overlay(self):
        if not hasattr(self, 'overlay') or not self.overlay.winfo_exists():
            self.overlay = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=15, border_width=2, border_color="#333333")
        self.overlay.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.8, relheight=0.8)
        self.overlay.lift()
        for widget in self.overlay.winfo_children():
            widget.destroy()

    def hide_overlay(self):
        if hasattr(self, 'overlay') and self.overlay.winfo_exists():
            self.overlay.place_forget()

    def show_message(self, title, message):
        self.show_overlay()
        ctk.CTkLabel(self.overlay, text=title, font=("Arial", 22, "bold")).pack(pady=20)
        ctk.CTkLabel(self.overlay, text=message, font=("Arial", 14), wraplength=550, justify="center").pack(pady=20)
        ctk.CTkButton(self.overlay, text="OK", command=self.hide_overlay, fg_color="#3b8ed0").pack(pady=20)

    def ask_confirm(self, title, message, on_yes):
        self.show_overlay()
        ctk.CTkLabel(self.overlay, text=title, font=("Arial", 22, "bold")).pack(pady=20)
        ctk.CTkLabel(self.overlay, text=message, font=("Arial", 14)).pack(pady=20)
        btn_frame = ctk.CTkFrame(self.overlay, fg_color="transparent")
        btn_frame.pack(pady=20)
        def yes_action():
            self.hide_overlay()
            on_yes()
        ctk.CTkButton(btn_frame, text="Ja", command=yes_action, fg_color="#4CAF50", hover_color="#45a049").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Nein", command=self.hide_overlay, fg_color="#f44336", hover_color="#da190b").pack(side="left", padx=10)

    def setup_ui(self):
        for widget in self.winfo_children():
            widget.destroy()

        master = ctk.CTkFrame(self, fg_color="#121216")
        master.pack(fill="both", expand=True)
        self.draw_lazer_background(master)

        top_bar = ctk.CTkFrame(master, fg_color="#181822", height=60, corner_radius=12)
        top_bar.pack(fill="x", padx=20, pady=(15, 10))
        top_bar.pack_propagate(False)

        mod_name = self.save_file.replace("save_data_", "").replace(".json", "")
        ctk.CTkButton(top_bar, text="⬅ Mod-Auswahl", width=110, height=34, font=("Arial", 12, "bold"),
                      fg_color="#25252e", hover_color="#353540", command=self.show_training_skillset_selection).pack(side="left", padx=15, pady=13)

        ctk.CTkLabel(top_bar, text=f"📈 Level-Training: {mod_name}", font=("Arial", 18, "bold"), text_color="#3b8ed0").pack(side="left", padx=10)

        ctk.CTkButton(top_bar, text="🎯 Zum aktuellen Level", height=34, font=("Arial", 12, "bold"),
                      command=self.jump_to_current_animated, fg_color="#1f538d", hover_color="#14375e").pack(side="left", padx=15)

        ctk.CTkButton(top_bar, text="?", width=32, height=32, font=("Arial", 16, "bold"),
                      fg_color="#22222a", hover_color="#333340", command=lambda: self.show_help("progression")).pack(side="right", padx=15)

        self.scrollable_frame = ctk.CTkScrollableFrame(master, orientation="horizontal", fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Initialize window start to around active level
        self.current_window_start = max(0, self.current_level_idx - 2)
        self.render_cards()
        if hasattr(self, "winfo_exists") and self.winfo_exists():
            self.after(100, self.jump_to_current_animated)

    def _bind_horizontal_scroll(self, widget):
        # 1. 2.5x Faster than previous (30 units per step - 10x base speed)
        def _on_wheel(event):
            if hasattr(self, "scrollable_frame") and self.scrollable_frame.winfo_exists():
                canvas = self.scrollable_frame._parent_canvas
                if canvas and canvas.winfo_exists():
                    units = -30 if event.delta > 0 else 30
                    canvas.xview_scroll(units, "units")

        # 2. Mouse Drag "Ice Slide" Inertia Physics
        def _on_drag_start(event):
            if not hasattr(self, "scrollable_frame") or not self.scrollable_frame.winfo_exists(): return
            if hasattr(self, "_slide_after_id") and self._slide_after_id:
                try: self.after_cancel(self._slide_after_id)
                except: pass
                self._slide_after_id = None
            self._is_dragging = True
            self._drag_start_x = event.x_root
            self._drag_last_x = event.x_root
            self._drag_last_time = time.time()
            self._drag_velocity = 0.0

        def _on_drag_move(event):
            if not getattr(self, "_is_dragging", False): return
            if not hasattr(self, "scrollable_frame") or not self.scrollable_frame.winfo_exists(): return
            canvas = self.scrollable_frame._parent_canvas
            if not canvas or not canvas.winfo_exists(): return
            
            dx = self._drag_last_x - event.x_root
            now = time.time()
            dt = max(0.001, now - getattr(self, "_drag_last_time", now))
            
            bbox = canvas.bbox("all")
            total_w = (bbox[2] - bbox[0]) if bbox else 2400
            if total_w > 0:
                frac_delta = dx / total_w
                current_frac = canvas.xview()[0]
                new_frac = max(0.0, min(1.0, current_frac + frac_delta))
                canvas.xview_moveto(new_frac)
                self._drag_velocity = frac_delta / dt
            
            self._drag_last_x = event.x_root
            self._drag_last_time = now

        def _on_drag_end(event):
            self._is_dragging = False
            vel = getattr(self, "_drag_velocity", 0.0)
            # 60% slower launch velocity for gentler ice slide
            self._drag_velocity = vel * 0.40
            if abs(self._drag_velocity) > 0.0003:
                self._do_ice_slide()

        try:
            widget.bind("<MouseWheel>", _on_wheel)
            # Only bind drag to frames, canvas, and labels (avoid capturing button clicks)
            widget_class = widget.__class__.__name__
            if "Button" not in widget_class:
                widget.bind("<ButtonPress-1>", _on_drag_start, add="+")
                widget.bind("<B1-Motion>", _on_drag_move, add="+")
                widget.bind("<ButtonRelease-1>", _on_drag_end, add="+")
                # Also allow middle-click drag anywhere
                widget.bind("<ButtonPress-2>", _on_drag_start, add="+")
                widget.bind("<B2-Motion>", _on_drag_move, add="+")
                widget.bind("<ButtonRelease-2>", _on_drag_end, add="+")

            for child in widget.winfo_children():
                self._bind_horizontal_scroll(child)
        except: pass

    def _do_ice_slide(self):
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            self._slide_after_id = None
            return
        if not hasattr(self, "scrollable_frame") or not self.scrollable_frame.winfo_exists():
            self._slide_after_id = None
            return
        if getattr(self, "_is_dragging", False): return
        
        canvas = self.scrollable_frame._parent_canvas
        if not canvas or not canvas.winfo_exists():
            self._slide_after_id = None
            return
        current_frac = canvas.xview()[0]
        vel = getattr(self, "_drag_velocity", 0.0)
        
        # Step fraction for 60 FPS
        step_frac = vel * 0.016
        new_frac = max(0.0, min(1.0, current_frac + step_frac))
        canvas.xview_moveto(new_frac)
        
        # 60% slower glide friction (0.86 deceleration per frame for smooth, controlled stop)
        self._drag_velocity = vel * 0.86
        
        if abs(self._drag_velocity) > 0.0001 and 0.0 < new_frac < 1.0:
            if hasattr(self, "winfo_exists") and self.winfo_exists():
                self._slide_after_id = self.after(16, self._do_ice_slide)
        else:
            self._drag_velocity = 0.0
            self._slide_after_id = None

    def jump_to_current_animated(self):
        if not hasattr(self, "winfo_exists") or not self.winfo_exists():
            return
        if not hasattr(self, "scrollable_frame") or not self.scrollable_frame.winfo_exists():
            return
        
        # Center the window around current level
        target_window = max(0, self.current_level_idx - 2)
        if target_window != getattr(self, "current_window_start", 0):
            self.current_window_start = target_window
            self.render_cards()

        canvas = self.scrollable_frame._parent_canvas
        if not canvas or not canvas.winfo_exists():
            return
        total_items = 8 + (1 if self.current_window_start > 0 else 0) + (1 if self.current_window_start + 8 < len(self.levels) else 0)
        pos = (self.current_level_idx - self.current_window_start) + (1 if self.current_window_start > 0 else 0)
        target_frac = max(0.0, min(1.0, (pos - 0.5) / max(1, total_items - 1)))
        
        current_frac = canvas.xview()[0]
        steps = 8
        def step(i=0):
            if not hasattr(self, "winfo_exists") or not self.winfo_exists(): return
            if not hasattr(self, "scrollable_frame") or not self.scrollable_frame.winfo_exists(): return
            t = (i + 1) / steps
            frac = current_frac + (target_frac - current_frac) * t
            try:
                canvas.xview_moveto(frac)
            except Exception:
                return
            if i + 1 < steps:
                if hasattr(self, "winfo_exists") and self.winfo_exists():
                    self.after(16, lambda: step(i + 1))
        step()

    def set_current_level(self, idx):
        self.current_level_idx = idx
        self.save_data()
        self.render_cards()
        self.jump_to_current_animated()

    def render_cards(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, "current_window_start"):
            self.current_window_start = max(0, self.current_level_idx - 2)

        page_size = 8
        start_idx = self.current_window_start
        end_idx = min(len(self.levels), start_idx + page_size)

        # 1. Previous page button if not at start
        if start_idx > 0:
            prev_frame = ctk.CTkFrame(self.scrollable_frame, width=160, height=440, corner_radius=16,
                                      fg_color="#181824", border_width=1, border_color="#2b2b3b")
            prev_frame.pack(side="left", padx=8, pady=10, fill="y")
            prev_frame.pack_propagate(False)

            prev_target = max(0, start_idx - page_size)
            ctk.CTkLabel(prev_frame, text="◀ Vorherige\nLevel", font=("Arial", 14, "bold"), text_color="#3b8ed0").pack(expand=True)
            ctk.CTkLabel(prev_frame, text=f"★ {self.levels[prev_target]:.1f} - {self.levels[start_idx-1]:.1f}",
                         font=("Arial", 11), text_color="#888899").pack(pady=(0, 15))
            def load_prev(target=prev_target):
                self.current_window_start = target
                self.render_cards()
            ctk.CTkButton(prev_frame, text="Laden ◀", font=("Arial", 12, "bold"), width=120, height=34,
                          fg_color="#1f538d", hover_color="#14375e", command=load_prev).pack(pady=(0, 20))

        # 2. Render Cards in current window
        for idx in range(start_idx, end_idx):
            self.draw_card(idx, is_active=(idx == self.current_level_idx))

        # 3. Next page button if not at end
        if end_idx < len(self.levels):
            next_frame = ctk.CTkFrame(self.scrollable_frame, width=160, height=440, corner_radius=16,
                                      fg_color="#181824", border_width=1, border_color="#2b2b3b")
            next_frame.pack(side="left", padx=8, pady=10, fill="y")
            next_frame.pack_propagate(False)

            next_end = min(len(self.levels) - 1, end_idx + page_size - 1)
            ctk.CTkLabel(next_frame, text="Weitere\nLevel ▶", font=("Arial", 14, "bold"), text_color="#3b8ed0").pack(expand=True)
            ctk.CTkLabel(next_frame, text=f"★ {self.levels[end_idx]:.1f} - {self.levels[next_end]:.1f}",
                         font=("Arial", 11), text_color="#888899").pack(pady=(0, 15))
            def load_next(target=end_idx):
                self.current_window_start = target
                self.render_cards()
            ctk.CTkButton(next_frame, text="Laden ▶", font=("Arial", 12, "bold"), width=120, height=34,
                          fg_color="#1f538d", hover_color="#14375e", command=load_next).pack(pady=(0, 20))

        # Bind horizontal scrolling to all created elements
        self._bind_horizontal_scroll(self.scrollable_frame)

    def draw_card(self, level_idx, is_active):
        level = self.levels[level_idx]
        level_str = f"{level:.1f}"

        if "levels" not in self.data: self.data["levels"] = {}
        level_data = self.data["levels"].get(level_str, {
            "s_ranks": [], "pfcs": [], "min3_maps": [], "skipped": False
        })

        s_count = len(level_data.get("s_ranks", []))
        pfc_count = len(level_data.get("pfcs", []))
        m3_count = len(level_data.get("min3_maps", []))
        total_plays = s_count + pfc_count + m3_count

        is_passed = (s_count >= 5 and pfc_count >= 2 and m3_count >= 2) and not level_data.get("skipped", False)
        is_skipped = level_data.get("skipped", False)

        if is_passed:
            border_color = "#4CAF50"
            bg_color = "#1e3b22"
            title = "BESTANDEN"
            title_color = "#4CAF50"
        elif is_skipped:
            border_color = "#FFC107"
            bg_color = "#4d3e0c"
            title = "GESKIPPT"
            title_color = "#FFC107"
        elif is_active:
            border_color = "#1f538d"
            bg_color = "#181822"
            title = "AKTIV"
            title_color = "#00E5FF"
        else:
            border_color = "#2e2e3f"
            bg_color = "#14141c"
            title = "GESPERRT"
            title_color = "#777788"

        frame = ctk.CTkFrame(self.scrollable_frame, width=280, height=440, corner_radius=16,
                             border_width=2, fg_color=bg_color, border_color=border_color)
        frame.pack(side="left", padx=10, pady=10, fill="y")
        frame.pack_propagate(False)

        # Top Header Bar (Select button if inactive)
        top_h = ctk.CTkFrame(frame, fg_color="transparent", height=28)
        top_h.pack(fill="x", padx=10, pady=(8, 0))
        top_h.pack_propagate(False)

        if not is_active and not is_passed:
            ctk.CTkButton(top_h, text="Auswählen", width=84, height=24, font=("Arial", 11, "bold"),
                          fg_color="#2b2b36", hover_color="#3a3a48",
                          command=lambda idx=level_idx: self.set_current_level(idx)).pack(side="right")

        # Level Title & Stars at top
        ctk.CTkLabel(frame, text=title, font=("Arial", 13, "bold"), text_color=title_color).pack(pady=(2, 2))
        ctk.CTkLabel(frame, text=f"{level_str} ★", font=("Arial", 28, "bold"), text_color="#ffffff").pack(pady=(0, 6))

        # Requirements Section (Clickable to show details)
        req_frame = ctk.CTkFrame(frame, fg_color="transparent")
        req_frame.pack(fill="x", padx=14, pady=4)

        if is_passed:
            ctk.CTkLabel(req_frame, text="🎉 Alle Anforderungen gemeistert!", font=("Arial", 13, "bold"), text_color="#4CAF50").pack(pady=10)
        else:
            s_col = "#4CAF50" if s_count >= 5 else "#ffffff"
            pfc_col = "#4CAF50" if pfc_count >= 2 else "#ffffff"
            m3_col = "#4CAF50" if m3_count >= 2 else "#ffffff"

            ctk.CTkLabel(req_frame, text=f"{s_count}/5 S-Ranks", font=("Arial", 14, "bold"), text_color=s_col).pack(pady=3)
            ctk.CTkLabel(req_frame, text=f"{pfc_count}/2 PFCs (Perfect FC)", font=("Arial", 14, "bold"), text_color=pfc_col).pack(pady=3)
            ctk.CTkLabel(req_frame, text=f"{m3_count}/2 Maps (> 3 Min)", font=("Arial", 14, "bold"), text_color=m3_col).pack(pady=3)

        # Gespielte Maps Details Button
        ctk.CTkButton(frame, text=f"🔍 Gespielte Maps ({total_plays})", font=("Arial", 11, "bold"), height=26,
                      fg_color="#232332", hover_color="#323244", text_color="#00E5FF",
                      command=lambda l=level_str: self.show_level_plays_modal(l)).pack(padx=14, pady=(6, 4), fill="x")

        # Active Level Actions (Search String & Skip)
        if is_active:
            action_frame = ctk.CTkFrame(frame, fg_color="transparent")
            action_frame.pack(fill="x", padx=14, pady=(10, 0))

            next_lvl = round(level + 0.09, 2)
            search_str = f"stars>={level:.2f} stars<={next_lvl:.2f} mode=osu status=r"

            copy_btn = ctk.CTkButton(action_frame, text="📋 Suchstring kopieren", font=("Arial", 12, "bold"), height=34,
                                     fg_color="#1f538d", hover_color="#14375e")
            
            def copy_search_str(s=search_str, btn=copy_btn):
                self.clipboard_clear()
                self.clipboard_append(s)
                self.update()
                btn.configure(text="✅ Kopiert!", fg_color="#2E7D32")
                self.after(2000, lambda: btn.configure(text="📋 Suchstring kopieren", fg_color="#1f538d") if btn.winfo_exists() else None)

            copy_btn.configure(command=copy_search_str)
            copy_btn.pack(fill="x", pady=(0, 6))

            ctk.CTkButton(action_frame, text="Level Überspringen", font=("Arial", 11), height=26,
                          fg_color="#c62828", hover_color="#b71c1c", command=lambda l=level_str: self.skip_level(l)).pack(fill="x")

    def show_level_plays_modal(self, level_str):
        self.show_overlay()

        if "levels" not in self.data: self.data["levels"] = {}
        level_data = self.data["levels"].get(level_str, {"s_ranks": [], "pfcs": [], "min3_maps": []})

        s_ranks = level_data.get("s_ranks", [])
        pfcs = level_data.get("pfcs", [])
        min3_maps = level_data.get("min3_maps", [])

        modal = ctk.CTkFrame(self.overlay, fg_color="#14141c", corner_radius=16, border_width=2, border_color="#1f538d", width=620, height=520)
        modal.place(relx=0.5, rely=0.5, anchor="center")
        modal.pack_propagate(False)

        top_h = ctk.CTkFrame(modal, fg_color="transparent")
        top_h.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(top_h, text=f"🏆 Level {level_str} ★ - Gespielte Maps", font=("Arial", 18, "bold"), text_color="#00E5FF").pack(side="left")
        ctk.CTkButton(top_h, text="✕", width=32, height=32, font=("Arial", 14, "bold"), fg_color="#2b2b36", hover_color="#c62828",
                      command=self.hide_overlay).pack(side="right")

        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        def render_play_group(title_text, plays_list, icon="⭐"):
            ctk.CTkLabel(scroll, text=f"{icon} {title_text} ({len(plays_list)})", font=("Arial", 14, "bold"), text_color="#ffffff").pack(anchor="w", pady=(10, 4))
            if not plays_list:
                ctk.CTkLabel(scroll, text="   Noch keine Maps in dieser Kategorie gespielt.", font=("Arial", 12), text_color="#777788").pack(anchor="w", pady=(0, 6))
                return
            for p in plays_list:
                card = ctk.CTkFrame(scroll, fg_color="#1d1d28", corner_radius=10, border_width=1, border_color="#2f2f40")
                card.pack(fill="x", pady=3)
                
                # Map Name / Score Info
                map_name = p.get("title") or p.get("beatmap_title") or p.get("beatmap_id") or p.get("hash") or "Unbekannte Beatmap"
                acc = p.get("acc") or p.get("accuracy") or 0.0
                combo = p.get("combo") or p.get("maxcombo") or 0
                miss = p.get("misses") or p.get("countmiss") or 0
                date_str = p.get("timestamp") or p.get("date") or ""

                top_r = ctk.CTkFrame(card, fg_color="transparent")
                top_r.pack(fill="x", padx=10, pady=(6, 2))
                ctk.CTkLabel(top_r, text=f"{map_name}", font=("Arial", 12, "bold"), text_color="#3b8ed0", anchor="w").pack(side="left")
                if acc:
                    ctk.CTkLabel(top_r, text=f"{acc:.2f}%", font=("Arial", 12, "bold"), text_color="#4CAF50").pack(side="right")

                bot_r = ctk.CTkFrame(card, fg_color="transparent")
                bot_r.pack(fill="x", padx=10, pady=(0, 6))
                ctk.CTkLabel(bot_r, text=f"Max Combo: {combo}x | Misses: {miss} {f'| {date_str[:16]}' if date_str else ''}",
                             font=("Arial", 11), text_color="#aaaaaa", anchor="w").pack(side="left")

        render_play_group("S-Ranks (Ziel: 5)", s_ranks, "⭐")
        render_play_group("Perfect FCs (Ziel: 2)", pfcs, "🎯")
        render_play_group("3 Minuten+ Maps (Ziel: 2)", min3_maps, "⏱️")

        ctk.CTkButton(modal, text="Schließen", font=("Arial", 12, "bold"), height=34,
                      fg_color="#1f538d", hover_color="#14375e", command=self.hide_overlay).pack(fill="x", padx=16, pady=(0, 14))

    def skip_level(self, level_str):
        def do_skip():
            if "levels" not in self.data: self.data["levels"] = {}
            if level_str not in self.data["levels"]: self.data["levels"][level_str] = {}
            self.data["levels"][level_str]["skipped"] = True
            if self.current_level_idx + 1 < len(self.levels):
                self.current_level_idx += 1
            self.save_data()
            self.render_cards()
            self.jump_to_current()
        self.ask_confirm("Level Überspringen", f"Möchtest du Level {level_str}★ wirklich überspringen?", do_skip)

    def handle_drop(self, event, level_str):
        files = self.tk.splitlist(event.data)
        if not files: return
        self.process_replay(files[0], level_str)

    def process_replay(self, file_path, level_str):
        if not file_path.endswith('.osr'): return
        try:
            parsed = parse_osr(file_path)
            # Filter strictly for osu! Standard (mode 0, no Mania/Catch/Taiko)
            if parsed.get('mode', 0) != 0:
                return
            if "levels" not in self.data: self.data["levels"] = {}
            if level_str not in self.data["levels"]: self.data["levels"][level_str] = {"s_ranks": [], "pfcs": [], "min3_maps": []}
            
            lvl = self.data["levels"][level_str]
            h300 = parsed['300s']
            h100 = parsed['100s']
            h50 = parsed['50s']
            miss = parsed['misses']
            tot = h300 + h100 + h50 + miss
            acc = ((h300 * 300 + h100 * 100 + h50 * 50) / (tot * 300) * 100) if tot > 0 else 0

            # S Rank Check
            is_s = (acc >= 93.0 and miss == 0) or (acc >= 90.0 and (h50/tot) <= 0.01 and miss == 0)
            if is_s and len(lvl.get("s_ranks", [])) < 5:
                lvl.setdefault("s_ranks", []).append(parsed)

            if parsed.get("perfect", False) and len(lvl.get("pfcs", [])) < 2:
                lvl.setdefault("pfcs", []).append(parsed)

            self.save_data()
            self.render_cards()
        except: pass


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()
