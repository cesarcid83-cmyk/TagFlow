import os
import json
from datetime import datetime

def normalizar_fecha_iso(fecha_raw):
    if not fecha_raw or str(fecha_raw).strip() == "" or str(fecha_raw).lower() == "nan":
        return ""
    
    texto = str(fecha_raw).strip().replace('"', '')
    texto = texto.replace("  ", " ")
    
    formatos = [
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M"
    ]
    for fmt in formatos:
        try:
            dt = datetime.strptime(texto, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
    return texto

def sanear_data_json(id_cliente="automaas"):
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    ruta_json = os.path.join(directorio_raiz, "docs", id_cliente, "data.json")

    if not os.path.exists(ruta_json):
        print(f"[ERROR] No se encontró {ruta_json}")
        return

    with open(ruta_json, "r", encoding="utf-8") as f:
        registros = json.load(f)

    print(f"[INFO] Registros leídos: {len(registros)}")

    # 1. Normalizar todas las fechas al formato ISO estricto
    for r in registros:
        r["fecha_entrada"] = normalizar_fecha_iso(r.get("fecha_entrada", ""))

    # 2. Deduplicar ahora que todas las fechas tienen la misma estructura
    viajes_unicos = {}
    for r in registros:
        clave = f"{r.get('autopista')}_{r.get('patente')}_{r.get('fecha_entrada')}_{r.get('portico_entrada')}_{r.get('tarifa')}"
        viajes_unicos[clave] = r

    lista_final = list(viajes_unicos.values())
    lista_final.sort(key=lambda x: x.get("fecha_entrada", ""), reverse=True)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(lista_final, f, indent=2, ensure_ascii=False)

    print(f"[ÉXITO] Fechas corregidas y duplicados purgados.")
    print(f"Total registros finales: {len(lista_final)}")

if __name__ == "__main__":
    sanear_data_json("automaas")