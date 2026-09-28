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

    # Limpiar temporales previos
    for f in glob.glob(os.path.join(carpeta_descargas_temp, "*")):
        try:
            if os.path.isfile(f): os.remove(f)
        except Exception:
            pass

    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)
    fecha_inicio = hace_30_dias.strftime("%d/%m/%Y")
    fecha_fin = hoy.strftime("%d/%m/%Y")

    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--start-maximized")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    prefs = {
        "download.default_directory": carpeta_descargas_temp,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1
    }
    opciones.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=opciones)
    wait = WebDriverWait(driver, 20)

    try:
        print("[INFO] Accediendo a Costanera Norte...")
        driver.get("https://www.costaneranorte.cl/convenios.dll/login")
        
        partes_rut = rut.split('-')
        rut_numero = partes_rut[0].replace(".", "")
        rut_dv = partes_rut[1] if len(partes_rut) > 1 else ""

        wait.until(EC.presence_of_element_located((By.ID, "RUT"))).send_keys(rut_numero)
        driver.find_element(By.ID, "RUTDV").send_keys(rut_dv)
        driver.find_element(By.ID, "PASSWORD").send_keys(password)

        print("[INFO] Esperando resolución de pantalla y login...")
        time.sleep(8) 
        
        try:
            driver.find_element(By.ID, "send").click()
        except Exception:
            pass 

        print("[INFO] Navegando a 'Tránsitos no facturados'...")
        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Tránsitos no facturados"))).click()
        time.sleep(3)

        print("[INFO] Configurando filtros de consulta...")
        try:
            vehiculos = Select(wait.until(EC.presence_of_element_located((By.NAME, "IndiceVehiculo"))))
            vehiculos.select_by_value("") 
        except Exception:
            pass

        try:
            concesionarias = Select(driver.find_element(By.NAME, "Concesionaria"))
            concesionarias.select_by_value("") 
        except Exception:
            pass

        driver.execute_script(f"document.getElementById('FechaDesde').value = '{fecha_inicio}';")
        driver.execute_script(f"document.getElementById('divFechaDesde').innerText = '{fecha_inicio}';")
        
        driver.execute_script(f"document.getElementById('FechaHasta').value = '{fecha_fin}';")
        driver.execute_script(f"document.getElementById('divFechaHasta').innerText = '{fecha_fin}';")

        wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Filtrar')]"))).click()
        print("[INFO] Filtro aplicado, esperando carga de registros...")
        time.sleep(6) 

        # Ejecución estricta de CSV mediante JavaScript nativo de Costanera
        print("[INFO] Solicitando exportación exclusiva a CSV...")
        driver.execute_script("DescargarUltimosConsumos('CSV');")

        # Gestionar cualquier alerta de JavaScript si apareciera
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            alerta = driver.switch_to.alert
            print(f"[AVISO] Alerta del portal detectada: {alerta.text}")
            alerta.accept()
        except Exception:
            pass

        print("[INFO] Esperando generación del archivo CSV en disco...")
        archivo_descargado = None
        for _ in range(12):
            time.sleep(2)
            archivos = [
                f for f in glob.glob(os.path.join(carpeta_descargas_temp, "*"))
                if os.path.isfile(f) and not f.endswith(".crdownload") and not f.endswith(".tmp")
            ]
            if archivos:
                archivo_descargado = max(archivos, key=os.path.getctime)
                break

        if archivo_descargado:
            nuevo_nombre = f"Costanera_{fecha_inicio.replace('/','')}_{fecha_fin.replace('/','')}_{datetime.now().strftime('%H%M%S')}.csv"
            ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
            
            if os.path.exists(ruta_final): 
                os.remove(ruta_final)
            shutil.move(archivo_descargado, ruta_final)
            print(f"[ÉXITO] Archivo guardado correctamente en: {ruta_final}")
        else:
            print("[AVISO] No se detectó archivo descargado en la carpeta temporal.")

    except Exception as e:
        print(f"[ERROR] Fallo en proceso Costanera Norte para {id_cliente}: {e}")
        traceback.print_exc()
    finally:
        try: 
            driver.quit()
        except Exception: 
            pass

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