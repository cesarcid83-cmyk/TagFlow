import os
import glob
import json
import csv
from datetime import datetime

def parsear_fecha_costanera(fecha_str):
    try:
        dt = datetime.strptime(fecha_str.strip(), "%d/%m/%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return fecha_str.strip()

def parsear_fecha_rutapass(fecha_str, hora_str):
    try:
        fecha_limpia = fecha_str.strip()
        hora_limpia = hora_str.strip()
        if len(hora_limpia.split(":")) == 2:
            hora_limpia += ":00"
        dt = datetime.strptime(f"{fecha_limpia} {hora_limpia}", "%d-%m-%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return f"{fecha_str} {hora_str}".strip()

def limpiar_monto(monto_raw):
    if not monto_raw:
        return 0.0
    s = str(monto_raw).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def procesar_csv_costanera(ruta_archivo):
    registros = []
    with open(ruta_archivo, mode="r", encoding="utf-8-sig", errors="ignore") as f:
        lector = csv.DictReader(f, delimiter=";")
        for fila in lector:
            patente = fila.get("Patente", "").strip().replace('"', '')
            if not patente:
                continue

            fecha_norm = parsear_fecha_costanera(fila.get("FechaHora", "").strip().replace('"', ''))
            portico = fila.get("PuntoCobro", "").strip().replace('"', '')
            tarifa = limpiar_monto(fila.get("Importe", "0"))
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

def procesar_excel_rutapass_facturado(ruta_archivo):
    import pandas as pd
    registros = []
    try:
        df = pd.read_excel(ruta_archivo)
        for _, fila in df.iterrows():
            registros.append({
                "autopista": str(fila.get("Autopista", "RutaPass")),
                "patente": str(fila.get("Patente", "")).strip(),
                "fecha_entrada": str(fila.get("Fecha Entrada", "")).strip(),
                "portico_entrada": str(fila.get("Pórtico Entrada", fila.get("Portico Entrada", "---"))).strip(),
                "portico_salida": str(fila.get("Pórtico Salida", fila.get("Portico Salida", "---"))).strip(),
                "tarifa": float(fila.get("Tarifa", 0.0)),
                "estado": str(fila.get("Estado", "Facturada")),
                "boleta": str(fila.get("Boleta", "3457040"))
            })
    except Exception as e:
        print(f"[AVISO] Error al leer {ruta_archivo}: {e}")
    return registros

def consolidar_cliente(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)

    carpeta_crudos = os.path.join(directorio_raiz, "crudos", id_cliente)
    ruta_destino_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    todos_los_viajes = []

    # Cargar datos existentes en data.json (AVO, etc.)
    if os.path.exists(ruta_destino_json):
        try:
            with open(ruta_destino_json, "r", encoding="utf-8") as f:
                todos_los_viajes = json.load(f)
                print(f"[INFO] Datos previos cargados: {len(todos_los_viajes)} registros.")
        except Exception as e:
            print(f"[AVISO] No se pudo leer {ruta_destino_json}: {e}")

    # 1. Costanera Norte
    archivos_costanera = glob.glob(os.path.join(carpeta_crudos, "Costanera_*.csv"))
    for arch in archivos_costanera:
        nuevos = procesar_csv_costanera(arch)
        todos_los_viajes.extend(nuevos)

    # 2. RutaPass Facturado (Excel procesado)
    archivos_facturas_rp = glob.glob(os.path.join(directorio_raiz, "RutaPass_Factura_*.xlsx"))
    for arch in archivos_facturas_rp:
        print(f"[PROCESANDO] Factura RutaPass: {os.path.basename(arch)}")
        nuevos = procesar_excel_rutapass_facturado(arch)
        todos_los_viajes.extend(nuevos)

    # Deduplicación por clave única
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