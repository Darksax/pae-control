-- ╔══════════════════════════════════════════════════════════╗
-- ║  PAE Control — Migración Supabase                        ║
-- ║  Pega este SQL en: Supabase > SQL Editor > New query     ║
-- ║  Es seguro ejecutarlo aunque ya existan las columnas.    ║
-- ╚══════════════════════════════════════════════════════════╝

-- ── 1. students: columna para teléfono del apoderado ─────────────────────────
ALTER TABLE students
    ADD COLUMN IF NOT EXISTS telefono_apoderado TEXT DEFAULT '';

-- ── 2. student_suspensions: columnas de Inspectoría ──────────────────────────
--    (atrasos, inasistencias, retiros, licencias + firma de apoderado)

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS creado_en   TEXT    DEFAULT '';

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS tipo        TEXT    DEFAULT 'suspension';

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado     INTEGER DEFAULT 0;

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado_en  TEXT    DEFAULT '';

ALTER TABLE student_suspensions
    ADD COLUMN IF NOT EXISTS firmado_por TEXT    DEFAULT '';

-- ── Verificar resultado ───────────────────────────────────────────────────────
SELECT column_name, data_type, column_default
FROM   information_schema.columns
WHERE  table_name IN ('students', 'student_suspensions')
ORDER  BY table_name, ordinal_position;
