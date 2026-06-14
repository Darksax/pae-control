"""
logic.py — Lógica de negocio PAE Control.

Resultado del escaneo:
  - "ok"         → verde, ingresa
  - "ya_reg"     → naranja, ya comió esta comida
  - "strike"     → rojo, faltó a comida anterior
  - "no_activo"  → gris, no está activo o en lista de espera
  - "no_existe"  → rojo, RUN no encontrado
  - "run_inv"    → rojo, RUN inválido
"""

from datetime import date, timedelta
import db
import utils


# ─────────────────────── SCAN PRINCIPAL ───────────────────────

def procesar_scan(raw_input: str) -> dict:
    """
    Procesa el input del escáner o manual.
    Retorna un dict con:
      estado, estudiante, comida, mensaje, strikes_total,
      max_strikes, comidas_faltadas
    """
    result = {
        "estado": None,
        "estudiante": None,
        "comida": None,
        "mensaje": "",
        "strikes_total": 0,
        "max_strikes": int(db.get_config("max_strikes", "3")),
        "comidas_faltadas": [],  # comidas anteriores no asistidas
        "comida_fria": False,    # True si hoy es día de ración fría
        "descripcion_fria": "",  # qué se sirve en la ración fría
    }

    # 1. Normalizar y validar RUN
    run = utils.normalizar_run(raw_input)
    if not run or "-" not in run:
        result["estado"] = "run_inv"
        result["mensaje"] = f"RUN inválido: «{raw_input}»"
        return result

    if not utils.validar_run(run):
        result["estado"] = "run_inv"
        result["mensaje"] = f"RUN con dígito verificador incorrecto: {utils.run_display(run)}"
        return result

    # 2. Buscar estudiante
    estudiante = db.get_student(run)
    if not estudiante:
        result["estado"] = "no_existe"
        result["mensaje"] = f"RUN {utils.run_display(run)} no encontrado en la base de datos"
        return result

    result["estudiante"] = dict(estudiante)

    # 3. Verificar si el día está suspendido + comida fría
    hoy_str = date.today().isoformat()
    _, suspendido, motivo_susp = db.get_quota_for_date(hoy_str)
    if suspendido:
        result["estado"] = "suspendido"
        result["mensaje"] = f"Sin servicio hoy: {motivo_susp}" if motivo_susp else "Sin servicio hoy"
        return result

    es_fria, desc_fria = db.get_comida_fria_for_date(hoy_str)
    result["comida_fria"]     = es_fria
    result["descripcion_fria"] = desc_fria

    # 4. Verificar estado del estudiante
    if not estudiante["activo"]:
        result["estado"] = "no_activo"
        result["mensaje"] = "Estudiante inactivo"
        return result

    if estudiante["lista_espera"]:
        result["estado"] = "no_activo"
        result["mensaje"] = "Estudiante en lista de espera (cupo no asignado)"
        return result

    # 5. Determinar comida actual
    comidas = db.get_comidas()
    if not comidas:
        result["estado"] = "error"
        result["mensaje"] = "No hay comidas configuradas"
        return result

    comida = utils.comida_actual(comidas)
    result["comida"] = dict(comida)

    hoy = date.today().isoformat()

    # 6. ¿Ya registrado?
    if db.ya_registrado(run, comida["id"], hoy):
        result["estado"] = "ya_reg"
        result["mensaje"] = f"Ya registrado en {comida['nombre']} de hoy"
        return result

    # 7. Verificar ausencias anteriores → posibles strikes
    comidas_faltadas = detectar_ausencias_previas(run, comida["id"], comidas)
    result["comidas_faltadas"] = comidas_faltadas

    # 8. Registrar asistencia (con flag comida_fria si aplica)
    db.registrar_asistencia(
        run, comida["id"], comida["nombre"],
        comida_fria=1 if es_fria else 0
    )

    # 9. Registrar strikes por faltados
    for cf in comidas_faltadas:
        db.registrar_strike(run, cf["comida_id"], cf["comida_nombre"], cf["tipo"])

    result["strikes_total"] = db.count_strikes(run)
    result["max_strikes"]   = int(db.get_config("max_strikes", "3"))

    if comidas_faltadas:
        nombres_faltados = ", ".join(cf["comida_nombre"] for cf in comidas_faltadas)
        result["estado"] = "strike"
        result["mensaje"] = f"Faltó a: {nombres_faltados}"
    else:
        result["estado"] = "ok"
        result["mensaje"] = "Ingreso registrado correctamente"

    return result


# ─────────────────────── DETECCIÓN AUSENCIAS ───────────────────────

def detectar_ausencias_previas(run: str, comida_actual_id: int,
                               comidas: list) -> list:
    """
    Revisa las comidas anteriores (hoy + ayer) y retorna lista de
    comidas a las que faltó (que generan strike).

    Regla:
    - Si faltó a comida anterior del mismo día → strike individual
    - Si faltó a comida del día anterior:
        - Si faltó a TODAS las comidas de ese día → tipo 'dia_completo' (no strike individual)
        - Si solo faltó a esa → strike individual
    """
    hoy = date.today()
    ayer = (hoy - timedelta(days=1)).isoformat()
    hoy_str = hoy.isoformat()

    ids_comidas = [c["id"] for c in comidas]
    map_comidas = {c["id"]: c for c in comidas}

    try:
        idx_actual = ids_comidas.index(comida_actual_id)
    except ValueError:
        return []

    faltadas = []

    # Comidas anteriores del mismo día (antes de la actual)
    for i in range(idx_actual - 1, -1, -1):
        cid = ids_comidas[i]
        if not db.ya_registrado(run, cid, hoy_str):
            # Excusar si el alumno tenía suspensión escolar ese día
            suspendido_hoy, _ = db.is_student_suspended(run, hoy_str)
            if not suspendido_hoy:
                faltadas.append({
                    "comida_id":     cid,
                    "comida_nombre": map_comidas[cid]["nombre"],
                    "fecha":         hoy_str,
                    "tipo":          "individual",
                })
        # Solo revisamos la comida inmediatamente anterior
        break

    # Si es la primera comida del día, revisar ayer
    if idx_actual == 0:
        # Si ayer tenía suspensión escolar, excusar completamente
        suspendido_ayer, _ = db.is_student_suspended(run, ayer)
        if suspendido_ayer:
            return faltadas  # ningún strike por ausencia de ayer

        registros_ayer = db.get_registros_estudiante(run, ayer)
        ids_asistio_ayer = {r["comida_id"] for r in registros_ayer}

        # ¿Faltó a TODAS las comidas de ayer?
        if not ids_asistio_ayer:
            # Ausencia día completo → registrar como tal, no es strike individual
            if ids_comidas:
                ultima_comida_ayer = map_comidas[ids_comidas[-1]]
                faltadas.append({
                    "comida_id":     ultima_comida_ayer["id"],
                    "comida_nombre": f"Día completo ({ayer})",
                    "fecha":         ayer,
                    "tipo":          "dia_completo",
                })
        else:
            # Asistió a algunas pero no a la última comida de ayer
            ultima_cid = ids_comidas[-1]
            if ultima_cid not in ids_asistio_ayer:
                faltadas.append({
                    "comida_id":     ultima_cid,
                    "comida_nombre": map_comidas[ultima_cid]["nombre"] + " (ayer)",
                    "fecha":         ayer,
                    "tipo":          "individual",
                })

    return faltadas


# ─────────────────────── CAPACIDAD ───────────────────────

def get_capacidad_info(fecha = None) -> dict:
    """
    Retorna info de capacidad para una fecha dada (default: hoy).
    Usa cuota del día si hay excepción, si no usa cupos_totales de config.

    'disponibles' = cupos_totales − registros_comida_actual_hoy
    (decrece en tiempo real a medida que se escanea).
    """
    if fecha is None:
        fecha = date.today().isoformat()
    conteo = db.count_students()
    total_cupos, suspendido, _ = db.get_quota_for_date(fecha)
    activos = conteo["activos"]

    if suspendido:
        disponibles = 0
    else:
        # Usar registros de la comida activa para calcular cuántos quedan
        comidas    = db.get_comidas()
        comida_act = utils.comida_actual(comidas) if comidas else None
        if comida_act:
            registros_hoy = db.count_registros_comida(fecha, comida_act["id"])
            disponibles   = max(0, total_cupos - registros_hoy)
        else:
            # Sin comida activa: mostrar cupos sin descontar
            disponibles = max(0, total_cupos)

    return {
        "total_cupos":  total_cupos,
        "activos":      activos,
        "disponibles":  disponibles,
        "lista_espera": conteo["espera"],
        "suspendido":   suspendido,
    }


# ─────────────────────── PROMOVER LISTA ESPERA ───────────────────────

def promover_desde_espera(run: str) -> bool:
    """Activa un estudiante de lista de espera si hay cupo disponible."""
    info = get_capacidad_info()
    if info["disponibles"] <= 0:
        return False
    db.update_student_status(run, activo=1, lista_espera=0)
    return True


# ─────────────────────── REPORTE FIN DE SEMANA ───────────────────────

def generar_reporte_semana() -> dict:
    resumen = db.get_resumen_semana()
    top25   = db.get_top_ausentes_semana(25)
    return {
        "resumen": resumen,
        "top25":   [dict(r) for r in top25],
    }
