import os
import glob
import json
import csv
from datetime import datetime

def parsear_fecha_costanera(fecha_str):
    # Convierte "28/08/2026 06:34:00" a "2026-08-28 06:34:00"
    try:
        dt = datetime.strptime(fecha_str.strip(), "%d/%m/%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return fecha_str.strip()

def procesar_csv_costanera(ruta_archivo):
    registros = []
    with open(ruta_archivo, mode="r", encoding="utf-8-sig", errors="ignore") as f:
        lector = csv.DictReader(f, delimiter=";")
        for fila in lector:
            patente = fila.get("Patente", "").strip().replace('"', '')
            if not patente:
                continue

            fecha_hora_raw = fila.get("FechaHora", "").strip().replace('"', '')
            fecha_norm = parsear_fecha_costanera(fecha_hora_raw)
            portico = fila.get("PuntoCobro", "").strip().replace('"', '')
            importe_str = fila.get("Importe", "0").strip().replace('"', '').replace('.', '').replace(',', '.')
            
            try:
                tarifa = float(importe_str)
            except ValueError:
                tarifa = 0.0

            nombre_corto = fila.get("NombreCorto", "CN").strip().replace('"', '')
            autopista = "Costanera Norte" if nombre_corto == "CN" else nombre_corto

            registros.append({
                "autopista": autopista,
                "patente": patente,
                "fecha_entrada": fecha_norm,
                "portico_entrada": portico if portico else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "No Facturada",
                "boleta": "---"
            })
    return registros

def consolidar_cliente(id_cliente="automaas"):
    # Como merge.py está en scripts/, subimos un nivel a la raíz de TagFlow
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)

    carpeta_crudos = os.path.join(directorio_raiz, "crudos", id_cliente)
    ruta_destino_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    todos_los_viajes = []

    # Cargar datos existentes en data.json (para conservar los de AVO u otros)
    if os.path.exists(ruta_destino_json):
        try:
            with open(ruta_destino_json, "r", encoding="utf-8") as f:
                todos_los_viajes = json.load(f)
                print(f"[INFO] Datos previos cargados: {len(todos_los_viajes)} registros.")
        except Exception as e:
            print(f"[AVISO] No se pudo leer {ruta_destino_json}: {e}")

    # Procesar archivos CSV de Costanera Norte
    archivos_costanera = glob.glob(os.path.join(carpeta_crudos, "Costanera_*.csv"))
    for arch in archivos_costanera:
        print(f"[PROCESANDO] Leyendo: {os.path.basename(arch)}")
        nuevos = procesar_csv_costanera(arch)
        todos_los_viajes.extend(nuevos)

    # Deduplicación con clave única
    viajes_unicos = {}
    for v in todos_los_viajes:
        clave = f"{v.get('autopista')}_{v.get('patente')}_{v.get('fecha_entrada')}_{v.get('portico_entrada')}_{v.get('tarifa')}"
        viajes_unicos[clave] = v

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    os.makedirs(os.path.dirname(ruta_destino_json), exist_ok=True)
    with open(ruta_destino_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    print(f"\n[ÉXITO] Consolidación completada:")
    print(f"-> Total registros únicos en data.json: {len(lista_final)}")
    print(f"-> Guardado en: {ruta_destino_json}")

if __name__ == "__main__":
    consolidar_cliente("automaas")