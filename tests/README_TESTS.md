# Tests de carga — MiAppoderado

Simulan la fila del lunes ejecutando `logic.procesar_scan()` (el mismo código
que dispara el escáner) contra una **COPIA** de la base de datos. La base real
(`~/pae_control/pae.db`) nunca se toca.

## Cómo correr

```bash
cd ~/pae_control/tests
python3 stress_test_pae.py        # suite completa: 9 escenarios (~30 s)
python3 stress_test_breakfast.py  # simulación lunes 07:30 (desayuno + strikes de ayer)
```

En Windows: `python stress_test_pae.py` (la medición de RAM se omite sola).

## Qué cubre

| Escenario | Qué prueba |
|---|---|
| Throughput | 1000 alumnos únicos escaneados seguidos (fila del lunes) |
| Re-scan | toda la fila de nuevo → 100% `ya_reg`, cero dobles registros |
| Doble lectura | escáner lee la misma credencial 2 veces sin pausa |
| Fuzz | RUN inválido, DV malo, inyección SQL, strings de 5000 chars, emoji, `None` |
| Strikes | ausencia a comida anterior operada → strike correcto |
| Concurrencia | 4 hilos escaneando a la vez → sin `database is locked` |
| Crecimiento | +100k registros históricos → latencia se mantiene |
| Resistencia | 2000 scans extra → sin fuga de memoria |
| Integridad | `PRAGMA integrity_check` + búsqueda de duplicados |

El test de desayuno además verifica los 3 perfiles de ayer (asistió todo /
faltó última comida / faltó día completo) y que un re-scan no duplique strikes.

Los archivos `pae_test.db*` / `pae_breakfast.db*` que quedan en esta carpeta
son las copias de prueba — se pueden borrar cuando quieras (están en .gitignore).
