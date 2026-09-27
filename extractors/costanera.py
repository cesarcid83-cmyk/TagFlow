import os
import sys
import json
import time
import glob
import shutil
import traceback
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

def obtener_clientes_activos():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    ruta_json = os.path.join(directorio_raiz, "config", "clients.json")

    if not os.path.exists(ruta_json):
        print(f"[ERROR] No se encontró el archivo de credenciales en: {ruta_json}")
        return []

    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            clientes = json.load(f)
            return [c for c in clientes if c.get("active", True)]
    except Exception as e:
        print(f"[ERROR] Error al leer clients.json: {e}")
        return []

def extraer_costanera_cliente(id_cliente, rut, password, carpeta_descargas_temp, carpeta_destino_base):
    print(f"\n==========================================")
    print(f"[PROCESO] Iniciando extracción Costanera Norte para: {id_cliente}")
    print(f"RUT: {rut}")
    print(f"==========================================")

    carpeta_cliente = os.path.join(carpeta_destino_base, "crudos", id_cliente)
    os.makedirs(carpeta_cliente, exist_ok=True)
    os.makedirs(carpeta_descargas_temp, exist_ok=True)

    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)
    fecha_inicio = hace_30_dias.strftime("%d/%m/%Y")
    fecha_fin = hoy.strftime("%d/%m/%Y")

    opciones = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": carpeta_descargas_temp,
        "download.prompt_for_download": False
    }
    opciones.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=opciones)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get("https://www.costaneranorte.cl/convenios.dll/login")
        
        partes_rut = rut.split('-')
        rut_numero = partes_rut[0].replace(".", "")
        rut_dv = partes_rut[1] if len(partes_rut) > 1 else ""

        wait.until(EC.presence_of_element_located((By.ID, "RUT"))).send_keys(rut_numero)
        driver.find_element(By.ID, "RUTDV").send_keys(rut_dv)
        driver.find_element(By.ID, "PASSWORD").send_keys(password)

        print("[INFO] Esperando 10 segundos por verificación en pantalla...")
        time.sleep(10) 
        
        try:
            driver.find_element(By.ID, "send").click()
        except:
            pass 

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Tránsitos no facturados"))).click()
        print("[INFO] Accediendo a los filtros...")

        vehiculos = Select(wait.until(EC.presence_of_element_located((By.NAME, "IndiceVehiculo"))))
        vehiculos.select_by_value("") 

        concesionarias = Select(driver.find_element(By.NAME, "Concesionaria"))
        concesionarias.select_by_value("") 

        driver.execute_script(f"document.getElementById('FechaDesde').value = '{fecha_inicio}';")
        driver.execute_script(f"document.getElementById('divFechaDesde').innerText = '{fecha_inicio}';")
        
        driver.execute_script(f"document.getElementById('FechaHasta').value = '{fecha_fin}';")
        driver.execute_script(f"document.getElementById('divFechaHasta').innerText = '{fecha_fin}';")

        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Filtrar')]"))).click()
        time.sleep(4) 

        print("[INFO] Solicitando descarga de CSV...")
        driver.execute_script("DescargarUltimosConsumos('CSV');")
        time.sleep(12) 

        archivos = glob.glob(os.path.join(carpeta_descargas_temp, "*_NoFacturados*.csv")) or glob.glob(os.path.join(carpeta_descargas_temp, "*.csv"))
        if archivos:
            archivo_reciente = max(archivos, key=os.path.getctime)
            nuevo_nombre = f"Costanera_{fecha_inicio.replace('/','')}_{fecha_fin.replace('/','')}_{datetime.now().strftime('%H%M%S')}.csv"
            ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
            
            if os.path.exists(ruta_final): os.remove(ruta_final)
            shutil.move(archivo_reciente, ruta_final)
            print(f"[ÉXITO] Archivo guardado correctamente en: {ruta_final}")
        else:
            print("[AVISO] No se detectó archivo descargado en la carpeta temporal.")

    except Exception as e:
        print(f"[ERROR] Fallo en proceso Costanera Norte para {id_cliente}: {e}")
        traceback.print_exc()
    finally:
        try: driver.quit()
        except: pass

def ejecutar():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    descargas_temp = os.path.join(directorio_raiz, "temp_downloads")

    clientes = obtener_clientes_activos()
    if not clientes:
        print("[AVISO] No hay clientes activos configurados.")
        return

    for c in clientes:
        cliente_id = c.get("id")
        credenciales = c.get("credentials", {})
        rut = credenciales.get("rut_empresa")
        password = credenciales.get("password_portal")

        if rut and password:
            extraer_costanera_cliente(cliente_id, rut, password, descargas_temp, directorio_raiz)

if __name__ == "__main__":
    ejecutar()