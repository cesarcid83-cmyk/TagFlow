import os
import glob
import json
import csv
from datetime import datetime
import pandas as pd

def normalizar_fecha_iso(fecha_raw, hora_raw="00:00:00"):
    """
    Convierte cualquier formato a 'YYYY-MM-DD HH:MM:SS' estricto.
    Elimina comillas, espacios residuales y garantiza compatibilidad con el dashboard.
    """
    if not fecha_raw or str(fecha_raw).strip() == "" or str(fecha_raw).lower() == "nan":
        return ""
    
    f_str = str(fecha_raw).strip().replace('"', '')
    h_str = str(hora_raw).strip().replace('"', '') if hora_raw else "00:00:00"

    # Si la fecha ya incluye la hora
    if " " in f_str:
        partes = f_str.split(" ")
        f_str = partes[0]
        h_str = partes[1]

    # Formatear hora con segundos garantizados
    partes_hora = h_str.split(":")
    if len(partes_hora) == 2:
        h_str = f"{partes_hora[0].zfill(2)}:{partes_hora[1].zfill(2)}:00"
    elif len(partes_hora) >= 3:
        h_str = f"{partes_hora[0].zfill(2)}:{partes_hora[1].zfill(2)}:{partes_hora[2].zfill(2)}"

    cadena_unida = f"{f_str} {h_str}"

    formatos_posibles = [
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M"
    ]

    for fmt in formatos_posibles:
        try:
            dt = datetime.strptime(cadena_unida, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

    return cadena_unida

def limpiar_monto(monto_raw):
    if monto_raw is None:
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

            fechahora_raw = fila.get("FechaHora", "").strip().replace('"', '')
            if not fechahora_raw:
                f_part = fila.get("Fecha", "").strip().replace('"', '')
                h_part = fila.get("Hora", "00:00:00").strip().replace('"', '')
                fecha_norm = normalizar_fecha_iso(f_part, h_part)
            else:
                fecha_norm = normalizar_fecha_iso(fechahora_raw)

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

def procesar_rutapass_no_facturado(ruta_archivo):
    registros = []
    try:
        try:
            df = pd.read_excel(ruta_archivo)
        except Exception:
            df = pd.read_html(ruta_archivo)[0]

        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec = str(fila.get("Fecha", "")).strip()
            hor = str(fila.get("Hora", "00:00:00")).strip()
            fecha_norm = normalizar_fecha_iso(fec, hor)
            pto = str(fila.get("Punto_Cobro", "---")).strip()
            tarifa = limpiar_monto(fila.get("Monto", 0))

            registros.append({
                "autopista": "RutaPass",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": pto if pto != "nan" else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "No Facturada",
                "boleta": "---"
            })
    except Exception as e:
        print(f"[AVISO] Error al leer RutaPass no facturado ({ruta_archivo}): {e}")
    return registros

def procesar_rutapass_facturado(ruta_archivo):
    registros = []
    try:
        df = pd.read_excel(ruta_archivo)
        df.columns = [str(c).strip() for c in df.columns]
        for _, fila in df.iterrows():
            pat = str(fila.get("Patente", "")).strip()
            if not pat or pat.lower() == "nan":
                continue

            fec_raw = str(fila.get("Fecha Entrada", "")).strip()
            fecha_norm = normalizar_fecha_iso(fec_raw)
            pto = str(fila.get("Pórtico Entrada", fila.get("Portico Entrada", "---"))).strip()
            tarifa = limpiar_monto(fila.get("Tarifa", 0))
            boleta = str(fila.get("Boleta", "3457040")).strip()

            registros.append({
                "autopista": "RutaPass",
                "patente": pat,
                "fecha_entrada": fecha_norm,
                "portico_entrada": pto if pto != "nan" else "---",
                "portico_salida": "---",
                "tarifa": tarifa,
                "estado": "Facturada",
                "boleta": boleta if boleta else "3457040"
            })
    except Exception as e:
        print(f"[AVISO] Error al leer factura RutaPass ({ruta_archivo}): {e}")
    return registros

def regenerar_desde_cero(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)

    carpeta_crudos = os.path.join(directorio_raiz, "crudos", id_cliente)
    ruta_destino_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    print("\n=======================================================")
    print(f"RECONSTRUCCIÓN LIMPIA DE DATA.JSON PARA: {id_cliente}")
    print("=======================================================")

    todos_los_viajes = []

    # 1. Conservar ÚNICAMENTE las autopistas que no sean Costanera ni RutaPass (ej. AVO)
    if os.path.exists(ruta_destino_json):
        try:
            with open(ruta_destino_json, "r", encoding="utf-8") as f:
                anteriores = json.load(f)
                for v in anteriores:
                    if v.get("autopista") not in ["Costanera Norte", "RutaPass"]:
                        todos_los_viajes.append(v)
            print(f"[PURGA REALIZADA] Registros previos de Costanera y RutaPass descartados.")
            print(f"[BASE MANTENIDA] Registros de otras autopistas (AVO): {len(todos_los_viajes)}")
        except Exception as e:
            print(f"[AVISO] No se pudo leer {ruta_destino_json}: {e}")

    # 2. Reingesta limpia de Costanera Norte desde crudos/
    archivos_costanera = sorted(glob.glob(os.path.join(carpeta_crudos, "Costanera_*.csv")))
    for arch in archivos_costanera:
        print(f"[PROCESANDO] Crudo Costanera: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_csv_costanera(arch))

    # 3. Reingesta limpia de RutaPass No Facturado desde crudos/
    archivos_rutapass_nofac = sorted(glob.glob(os.path.join(carpeta_crudos, "RutaPass_*.xls*")))
    for arch in archivos_rutapass_nofac:
        print(f"[PROCESANDO] Crudo RutaPass (No Facturado): {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_no_facturado(arch))

    # 4. Reingesta limpia de RutaPass Facturado desde el Excel procesado
    archivos_facturas = sorted(glob.glob(os.path.join(directorio_raiz, "RutaPass_Factura_*.xlsx")) or 
                               glob.glob(os.path.join(carpeta_crudos, "RutaPass_Factura_*.xlsx")))
    for arch in archivos_facturas:
        print(f"[PROCESANDO] Factura RutaPass: {os.path.basename(arch)}")
        todos_los_viajes.extend(procesar_rutapass_facturado(arch))

    # 5. Deduplicación canónica
    viajes_unicos = {}
    for v in todos_los_viajes:
        clave = f"{v.get('autopista')}_{v.get('patente')}_{v.get('fecha_entrada')}_{v.get('portico_entrada')}_{v.get('tarifa')}"
        viajes_unicos[clave] = v

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    os.makedirs(os.path.dirname(ruta_destino_json), exist_ok=True)
    with open(ruta_destino_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    print("\n=======================================================")
    print(f"[ÉXITO] Archivo data.json reescrito completamente.")
    print(f"-> Total registros únicos en formato ISO: {len(lista_final)}")
    print(f"-> Ruta: {ruta_destino_json}")
    print("=======================================================\n")

if __name__ == "__main__":
    regenerar_desde_cero("automaas")