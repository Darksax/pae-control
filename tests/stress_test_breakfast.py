"""
stress_test_breakfast.py — Monday-morning simulation for MiAppoderado.

First meal of the day is the HEAVIEST logic path: for every scanned student,
detectar_ausencias_previas() checks the whole previous day (3 COUNT queries +
suspension lookup + per-student registro fetch). This is exactly what happens
at 07:30 on Monday. Also approximates the extra UI work per scan
(get_capacidad_info → what _refresh_stats triggers).
"""

import os, sys, shutil, sqlite3, time, statistics
from datetime import date, datetime, timedelta

SCRATCH = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(SCRATCH)
APP_DIR = _parent if os.path.exists(os.path.join(_parent, "db.py")) else "/Users/macbook/pae_control"
LIVE_DB = os.path.join(os.path.expanduser("~"), "pae_control", "pae.db")
if not os.path.exists(LIVE_DB):
    LIVE_DB = os.path.join(APP_DIR, "pae.db")
TEST_DB = os.path.join(SCRATCH, "pae_breakfast.db")

for suffix in ("", "-wal", "-shm"):
    src = LIVE_DB + suffix
    if os.path.exists(src):
        shutil.copy2(src, TEST_DB + suffix)

sys.path.insert(0, APP_DIR)
import db
db.DB_DIR = SCRATCH
db.DB_PATH = TEST_DB
import utils, logic

db.init_db()

HOY  = date.today().isoformat()
AYER = (date.today() - timedelta(days=1)).isoformat()

conn = db.get_conn()
# Breakfast (comida 1) active NOW; others out of window
conn.execute("UPDATE comidas SET hora_inicio='00:00', hora_fin='23:59' WHERE id=1")
conn.execute("UPDATE comidas SET hora_inicio='23:58', hora_fin='23:59' WHERE id IN (2,3)")
conn.execute("DELETE FROM registros WHERE fecha IN (?,?)", (HOY, AYER))
conn.execute("DELETE FROM strikes  WHERE fecha IN (?,?)", (HOY, AYER))
conn.commit(); conn.close()

def dv_of(cuerpo: int) -> str:
    suma, mult, n = 0, 2, cuerpo
    while n > 0:
        suma += (n % 10) * mult; n //= 10; mult = (mult - 1) % 6 + 2
    r = 11 - (suma % 11)
    return "0" if r == 11 else ("K" if r == 10 else str(r))

def make_students(start, n, prefix):
    conn = db.get_conn(); runs = []
    for i in range(n):
        c = start + i
        run = f"{c}-{dv_of(c)}"
        runs.append(run)
        conn.execute("INSERT OR REPLACE INTO students (run,nombres,apellido_paterno,curso,activo,lista_espera) VALUES (?,?,?,?,1,0)",
                     (run, f"{prefix}{i}", "TEST", "1° medioT"))
    conn.commit(); conn.close()
    return runs

FULL   = make_students(95_000_001, 100, "Full")    # attended everything yesterday
MISSED = make_students(95_100_001, 100, "Missed")  # missed LAST meal yesterday
GHOST  = make_students(95_200_001, 100, "Ghost")   # attended nothing yesterday

# Seed yesterday: FULL attended meals 1-3; MISSED attended 1-2 only; GHOST none.
conn = db.get_conn()
ts = AYER + "T12:00:00"
for r in FULL:
    for cid, nom in ((1, "Desayuno"), (2, "Almuerzo"), (3, "Tercera colación")):
        conn.execute("INSERT OR IGNORE INTO registros (run_estudiante,fecha,comida_id,comida_nombre,timestamp,metodo,periodo) VALUES (?,?,?,?,?,?,?)",
                     (r, AYER, cid, nom, ts, "scan", "2026-S1"))
for r in MISSED:
    for cid, nom in ((1, "Desayuno"), (2, "Almuerzo")):
        conn.execute("INSERT OR IGNORE INTO registros (run_estudiante,fecha,comida_id,comida_nombre,timestamp,metodo,periodo) VALUES (?,?,?,?,?,?,?)",
                     (r, AYER, cid, nom, ts, "scan", "2026-S1"))
conn.commit(); conn.close()

def pct(v, p):
    v = sorted(v); return v[min(len(v)-1, int(len(v)*p/100))]

print("════ Monday 07:30 — breakfast scans with yesterday-absence check ════")
lat, states = [], {}
order = [x for triple in zip(FULL, MISSED, GHOST) for x in triple]  # interleaved queue
t0 = time.perf_counter()
results = {}
for r in order:
    s = time.perf_counter()
    res = logic.procesar_scan(r)
    lat.append((time.perf_counter() - s) * 1000)
    states[res["estado"]] = states.get(res["estado"], 0) + 1
    results[r] = res
total = time.perf_counter() - t0
print(f"{len(order)} scans in {total:.2f}s → {len(order)/total:.0f} scans/s | "
      f"avg {statistics.mean(lat):.1f}ms p95 {pct(lat,95):.1f} p99 {pct(lat,99):.1f} max {max(lat):.1f}ms")
print("states:", states)

rf, rm, rg = results[FULL[0]], results[MISSED[0]], results[GHOST[0]]
print(f"\nFULL   (attended all yesterday): {rf['estado']} strikes={rf['strikes_total']} faltadas={[f['comida_nombre'] for f in rf['comidas_faltadas']]}")
print(f"MISSED (skipped last meal):      {rm['estado']} strikes={rm['strikes_total']} faltadas={[f['comida_nombre'] for f in rm['comidas_faltadas']]}")
print(f"GHOST  (absent whole day):       {rg['estado']} strikes={rg['strikes_total']} faltadas={[f['comida_nombre'] for f in rg['comidas_faltadas']]}")
assert rf["estado"] == "ok" and rf["strikes_total"] == 0
assert rm["estado"] == "strike" and rm["strikes_total"] == 1
assert rg["estado"] == "strike" and rg["strikes_total"] == 0  # dia_completo: not an individual strike

print("\n════ Full UI-loop approximation (procesar_scan + stats refresh) ════")
EXTRA = make_students(95_300_001, 200, "Ui")
lat2 = []
for r in EXTRA:
    s = time.perf_counter()
    logic.procesar_scan(r)
    logic.get_capacidad_info()          # what _refresh_stats recomputes
    comidas = db.get_comidas()
    if comidas:
        db.count_registros_comida(HOY, comidas[0]["id"])
    lat2.append((time.perf_counter() - s) * 1000)
print(f"200 scans w/ stats refresh | avg {statistics.mean(lat2):.1f}ms "
      f"p95 {pct(lat2,95):.1f} max {max(lat2):.1f}ms")

print("\n════ Same student, first meal of day, scanned twice (strike double-count?) ════")
victim = GHOST[1]
res2 = logic.procesar_scan(victim)   # already scanned above → ya_reg, no new strike
conn = db.get_conn()
nstr = conn.execute("SELECT COUNT(*) AS n FROM strikes WHERE run_estudiante=?", (victim,)).fetchone()["n"]
conn.close()
print(f"2nd scan: {res2['estado']} | strike rows for student: {nstr} (expect 1 — the dia_completo)")
assert res2["estado"] == "ya_reg" and nstr == 1

print("\n[done] breakfast simulation OK")
