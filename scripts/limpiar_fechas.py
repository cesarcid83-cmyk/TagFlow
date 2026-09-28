import os
import json
import re

def purgar_registros_corruptos(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    ruta_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    if not os.path.exists(ruta_json):
        print(f"[ERROR] No se encontró {ruta_json}")
        return

    with open(ruta_json, "r", encoding="utf-8") as f:
        registros = json.load(f)

    total_inicial = len(registros)
    print(f"[INFO] Registros iniciales: {total_inicial}")

    registros_validos = []
    formato_iso = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    for r in registros:
        fecha = str(r.get("fecha_entrada", "")).strip()
        autopista = str(r.get("autopista", "")).strip()
        patente = str(r.get("patente", "")).strip()

        # Descartar registros que generen 'undefined' o tengan fecha inválida
        if "undefined" in fecha.lower():
            print(f"[PURGADO] Descartado registro con 'undefined': {autopista} - {patente} - {fecha}")
            continue

        # Si es el registro duplicado de AMB con formato no estándar (ej. DD/MM/YYYY)
        if autopista == "AMB" and not formato_iso.match(fecha):
            print(f"[PURGADO] Descartado AMB con formato no ISO: {patente} - {fecha}")
            continue

        registros_validos.append(r)

    # Deduplicación canónica final
    viajes_unicos = {}
    for r in registros_validos:
        clave = f"{r.get('autopista')}_{r.get('patente')}_{r.get('fecha_entrada')}_{r.get('portico_entrada')}_{r.get('tarifa')}"
        viajes_unicos[clave] = r

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    eliminados = total_inicial - len(lista_final)
    print(f"\n[ÉXITO] Saneamiento completado.")
    print(f"-> Registros eliminados/purgados: {eliminados}")
    print(f"-> Total registros limpios en data.json: {len(lista_final)}")

if __name__ == "__main__":
    purgar_registros_corruptos("automaas")