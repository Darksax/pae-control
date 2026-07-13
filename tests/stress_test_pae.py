"""
stress_test_pae.py — Active load-test loop for MiAppoderado's scan pipeline.

Runs logic.procesar_scan() (the exact code path the scanner triggers on
scan_screen._on_scan) against a COPY of the production DB, simulating
Monday's queue: hundreds of students scanned back-to-back.

Scenarios:
  1. Throughput   — 1000 unique students scanned sequentially (the Monday queue)
  2. Re-scan      — the whole queue scanned again (must all be 'ya_reg')
  3. Double-read  — scanner reads the same card twice instantly
  4. Fuzz         — invalid/hostile inputs (bad DV, garbage, SQL injection, huge strings)
  5. Strikes      — absence detection when a previous meal operated
  6. Concurrency  — 4 threads scanning simultaneously (locked-database check)
  7. Growth       — 100k historical rows injected, latency re-measured
  8. Endurance    — repeated scan cycles, memory growth check
  9. Integrity    — PRAGMA integrity_check + duplicate detection
"""

import os, sys, shutil, sqlite3, time, statistics, threading, random
try:
    import resource          # Unix only — en Windows se omite la medición de RAM
except ImportError:
    resource = None
from datetime import date, datetime, timedelta

SCRATCH = os.path.dirname(os.path.abspath(__file__))
# Si el script vive en pae_control/tests/, el código está un nivel arriba
_parent = os.path.dirname(SCRATCH)
APP_DIR = _parent if os.path.exists(os.path.join(_parent, "db.py")) else "/Users/macbook/pae_control"
LIVE_DB = os.path.join(os.path.expanduser("~"), "pae_control", "pae.db")
if not os.path.exists(LIVE_DB):
    LIVE_DB = os.path.join(APP_DIR, "pae.db")
TEST_DB = os.path.join(SCRATCH, "pae_test.db")

# ── 1. Copy live DB → scratchpad, NEVER touch the original ──────────────────
for suffix in ("", "-wal", "-shm"):
    src = LIVE_DB + suffix
    if os.path.exists(src):
        shutil.copy2(src, TEST_DB + suffix)
print(f"[setup] test DB: {TEST_DB} ({os.path.getsize(TEST_DB)//1024} KB)")

# ── 2. Import app modules and redirect db module to the copy ────────────────
sys.path.insert(0, APP_DIR)
import db
db.DB_DIR = SCRATCH
db.DB_PATH = TEST_DB
import utils
import logic

db.init_db()  # run migrations on the copy

# ── 3. Make the test deterministic ───────────────────────────────────────────
HOY = date.today().isoformat()
AYER = (date.today() - timedelta(days=1)).isoformat()

conn = db.get_conn()
# Meal 3 always "active" regardless of wall-clock time
conn.execute("UPDATE comidas SET hora_inicio='00:00', hora_fin='00:01' WHERE id=1")
conn.execute("UPDATE comidas SET hora_inicio='00:02', hora_fin='00:03' WHERE id=2")
conn.execute("UPDATE comidas SET hora_inicio='00:04', hora_fin='23:59' WHERE id=3")
# No quota exception / suspension for today
try:
    conn.execute("DELETE FROM quota_exceptions WHERE fecha=?", (HOY,))
except sqlite3.OperationalError:
    pass
# Clean today's registros/strikes in the COPY so runs are repeatable
conn.execute("DELETE FROM registros WHERE fecha IN (?,?)", (HOY, AYER))
conn.execute("DELETE FROM strikes  WHERE fecha IN (?,?)", (HOY, AYER))
conn.commit()
conn.close()

# ── 4. Synthetic students with VALID check digits ────────────────────────────
def dv_of(cuerpo: int) -> str:
    suma, mult, n = 0, 2, cuerpo
    while n > 0:
        suma += (n % 10) * mult
        n //= 10
        mult = (mult - 1) % 6 + 2
    resto = 11 - (suma % 11)
    return "0" if resto == 11 else ("K" if resto == 10 else str(resto))

def make_students(start_body: int, n: int, prefix: str):
    conn = db.get_conn()
    runs = []
    for i in range(n):
        cuerpo = start_body + i
        run = f"{cuerpo}-{dv_of(cuerpo)}"
        runs.append(run)
        conn.execute("""
            INSERT OR REPLACE INTO students
              (run, nombres, apellido_paterno, curso, activo, lista_espera)
            VALUES (?,?,?,?,1,0)
        """, (run, f"{prefix}{i}", "TEST", "1° medioT"))
    conn.commit()
    conn.close()
    return runs

QUEUE    = make_students(90_000_001, 1000, "Alumno")     # scenario 1/2/8
STRIKERS = make_students(91_000_001, 40,  "Strike")      # scenario 5
THREADED = make_students(92_000_001, 400, "Conc")        # scenario 6

def pct(v, p):
    v = sorted(v)
    return v[min(len(v)-1, int(len(v)*p/100))]

def scan_all(runs, label):
    lat, states = [], {}
    t0 = time.perf_counter()
    for r in runs:
        s = time.perf_counter()
        res = logic.procesar_scan(r)
        lat.append((time.perf_counter() - s) * 1000)
        states[res["estado"]] = states.get(res["estado"], 0) + 1
    total = time.perf_counter() - t0
    print(f"[{label}] {len(runs)} scans in {total:.2f}s → {len(runs)/total:.0f} scans/s | "
          f"avg {statistics.mean(lat):.1f}ms  p50 {pct(lat,50):.1f}  p95 {pct(lat,95):.1f}  "
          f"p99 {pct(lat,99):.1f}  max {max(lat):.1f}ms | states={states}")
    return states, lat

print("\n════ SCENARIO 1 — Throughput: Monday queue, 1000 unique students ════")
s1_states, s1_lat = scan_all(QUEUE, "throughput")
assert s1_states.get("ok") == 1000, f"expected 1000 ok, got {s1_states}"

print("\n════ SCENARIO 2 — Entire queue re-scanned (expect 100% ya_reg) ════")
s2_states, _ = scan_all(QUEUE, "rescan")
assert s2_states.get("ya_reg") == 1000, f"expected 1000 ya_reg, got {s2_states}"

print("\n════ SCENARIO 3 — Scanner double-read (same card twice, no pause) ════")
victim = STRIKERS[0]
r1 = logic.procesar_scan(victim); r2 = logic.procesar_scan(victim)
print(f"1st: {r1['estado']}  2nd: {r2['estado']}")
assert r1["estado"] == "ok" and r2["estado"] == "ya_reg"

print("\n════ SCENARIO 4 — Fuzz: invalid / hostile input ════")
fuzz_cases = [
    ("", "run_inv"), ("   ", "run_inv"), ("abc", "run_inv"),
    ("12345678-5", None),            # wrong DV → run_inv (dv computed below)
    ("99999999-9", None),            # valid-format unknown RUN
    ("'; DROP TABLE students;--", "run_inv"),
    ("<script>alert(1)</script>", "run_inv"),
    ("00000000-0", None),
    ("A" * 5000, "run_inv"),
    ("11.111.111-1", None),          # dots format
    ("111111111", None),             # 9 digits no dash
    ("11111111k", None),             # lowercase k
    ("-5", "run_inv"), ("5-", "run_inv"), ("--", "run_inv"),
    ("١٢٣٤٥٦٧٨", "run_inv"),         # arabic digits
    ("🎓🎓🎓", "run_inv"),
    (None, None),                    # None input — what does the pipeline do?
]
fuzz_fail = []
for raw, _expected in fuzz_cases:
    try:
        res = logic.procesar_scan(raw)
        disp = repr(raw)[:40]
        print(f"  {disp:<42} → {res['estado']}")
        if res["estado"] in ("ok", "strike"):
            fuzz_fail.append((raw, "REGISTERED ATTENDANCE for invalid input!"))
    except Exception as e:
        print(f"  {repr(raw)[:42]:<42} → EXCEPTION {type(e).__name__}: {e}")
        fuzz_fail.append((raw, f"exception {type(e).__name__}: {e}"))
# students table still alive?
assert db.get_student(QUEUE[0]) is not None, "students table damaged by fuzz input!"
print(f"  fuzz issues: {fuzz_fail if fuzz_fail else 'none — all handled gracefully'}")

print("\n════ SCENARIO 5 — Strike detection (missed previous meal) ════")
# Seed: meal 2 'operated' today (one registro) ; STRIKERS[1] attended meal 2, [2] didn't.
conn = db.get_conn()
now = datetime.now().isoformat(timespec="seconds")
conn.execute("INSERT OR IGNORE INTO registros (run_estudiante, fecha, comida_id, comida_nombre, timestamp, metodo, periodo) VALUES (?,?,?,?,?,?,?)",
             (STRIKERS[1], HOY, 2, "Almuerzo", now, "scan", "2026-S1"))
conn.execute("INSERT OR IGNORE INTO registros (run_estudiante, fecha, comida_id, comida_nombre, timestamp, metodo, periodo) VALUES (?,?,?,?,?,?,?)",
             (STRIKERS[3], HOY, 2, "Almuerzo", now, "scan", "2026-S1"))
conn.commit(); conn.close()
res_att  = logic.procesar_scan(STRIKERS[1])   # attended meal2 → ok, no strike
res_miss = logic.procesar_scan(STRIKERS[2])   # missed meal2 while it operated → strike
print(f"attended meal2:  {res_att['estado']}  strikes={res_att['strikes_total']}")
print(f"missed meal2:    {res_miss['estado']}  strikes={res_miss['strikes_total']}  faltadas={[f['comida_nombre'] for f in res_miss['comidas_faltadas']]}")
assert res_att["estado"] == "ok" and res_att["strikes_total"] == 0
assert res_miss["estado"] == "strike" and res_miss["strikes_total"] == 1

print("\n════ SCENARIO 6 — Concurrency: 4 threads scanning at once ════")
errors, lock_errors = [], []
def worker(chunk):
    for r in chunk:
        try:
            logic.procesar_scan(r)
        except sqlite3.OperationalError as e:
            (lock_errors if "locked" in str(e).lower() else errors).append(str(e))
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
chunks = [THREADED[i::4] for i in range(4)]
threads = [threading.Thread(target=worker, args=(c,)) for c in chunks]
t0 = time.perf_counter()
[t.start() for t in threads]; [t.join() for t in threads]
dt = time.perf_counter() - t0
conn = db.get_conn()
n_reg = conn.execute("SELECT COUNT(DISTINCT run_estudiante) AS n FROM registros WHERE fecha=? AND run_estudiante LIKE '92000%'", (HOY,)).fetchone()["n"]
conn.close()
print(f"400 scans / 4 threads in {dt:.2f}s | registered={n_reg}/400 | "
      f"locked-errors={len(lock_errors)} other-errors={len(errors)}")
if lock_errors: print("  e.g.:", lock_errors[0])
if errors:      print("  e.g.:", errors[0])

print("\n════ SCENARIO 7 — DB growth: +100k historical rows, re-measure ════")
conn = db.get_conn()
rows = []
base_day = date.today() - timedelta(days=200)
all_runs = QUEUE + THREADED
for d in range(180):
    f = (base_day + timedelta(days=d)).isoformat()
    for r in random.sample(all_runs, 550):
        rows.append((r, f, random.choice([1, 2, 3]), "Hist", f + "T12:00:00", "scan", "2026-S1"))
conn.executemany("INSERT OR IGNORE INTO registros (run_estudiante, fecha, comida_id, comida_nombre, timestamp, metodo, periodo) VALUES (?,?,?,?,?,?,?)", rows)
conn.commit()
total_rows = conn.execute("SELECT COUNT(*) AS n FROM registros").fetchone()["n"]
conn.close()
print(f"registros table now: {total_rows} rows "
      f"({os.path.getsize(TEST_DB)//1024//1024} MB)")
# re-scan queue (all ya_reg — the heaviest read path) and fresh students
FRESH = make_students(93_000_001, 300, "Fresh")
scan_all(QUEUE[:300], "grown-db rescan (read path)")
scan_all(FRESH, "grown-db fresh scans (write path)")

print("\n════ SCENARIO 8 — Endurance: 10 cycles, memory growth ════")
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 * 1024) if resource else 0
for cycle in range(10):
    for r in QUEUE[:200]:
        logic.procesar_scan(r)          # all ya_reg — pure read cycle
rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // (1024 * 1024) if resource else 0
print(f"2000 extra scans done | maxRSS before={rss0}MB after={rss1}MB" if resource
      else "2000 extra scans done (RAM check omitido en Windows)")

print("\n════ SCENARIO 9 — Integrity ════")
conn = db.get_conn()
ic = conn.execute("PRAGMA integrity_check").fetchone()
dups = conn.execute("""
    SELECT run_estudiante, fecha, comida_id, COUNT(*) c FROM registros
    GROUP BY run_estudiante, fecha, comida_id HAVING c > 1
""").fetchall()
today_regs = conn.execute("SELECT COUNT(*) AS n FROM registros WHERE fecha=?", (HOY,)).fetchone()["n"]
conn.close()
print(f"integrity_check: {list(ic.values())[0]} | duplicate (run,fecha,comida): {len(dups)} | today's registros: {today_regs}")

print("\n[done] live DB untouched:", LIVE_DB)
