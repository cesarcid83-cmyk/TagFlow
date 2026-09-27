import os
import sys
import json
import time
import glob
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def obtener_clientes_activos():
    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    directorio_raiz = os.path.dirname(directorio_actual)
    ruta_json = os.path.join(directorio_raiz, "config", "clients.json")

    if not os.path.exists(ruta_json):
        print(f"[ERROR] No se encontro el archivo de credenciales en: {ruta_json}")
        return []

    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            clientes = json.load(f)
            return [c for c in clientes if c.get("active", True)]
    except Exception as e:
        print(f"[ERROR] Error al leer clients.json: {e}")
        return []

def extraer_vespuciosur_cliente(id_cliente, rut, password, carpeta_descargas_temp, carpeta_destino_base):
    print(f"\n==========================================")
    print(f"[PROCESO] Iniciando extraccion Vespucio Sur para: {id_cliente}")
    print(f"RUT: {rut}")
    print(f"==========================================")

    carpeta_cliente = os.path.join(carpeta_destino_base, "crudos", id_cliente)
    os.makedirs(carpeta_cliente, exist_ok=True)
    os.makedirs(carpeta_descargas_temp, exist_ok=True)

    partes_rut = rut.split('-')
    rut_numero = partes_rut[0].replace(".", "")
    rut_dv = partes_rut[1] if len(partes_rut) > 1 else ""

    # Rango de fechas: Desde 01/08/2026 hasta hoy
    fecha_inicio = "01/08/2026"
    fecha_fin = datetime.now().strftime("%d/%m/%Y")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    prefs = {
        "download.default_directory": carpeta_descargas_temp,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)

    # Evasion basica de deteccion
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"}
    )

    try:
        driver.get("https://oficina.vespuciosur.cl/sucursal_virtual/login.html")
        
        input_rut = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "RUT")))
        input_rut.clear()
        input_rut.send_keys(rut_numero)
        
        input_dv = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "RUTDV")))
        input_dv.clear()
        input_dv.send_keys(rut_dv)
        
        input_pass = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "PASSWORD")))
        input_pass.clear()
        input_pass.send_keys(password)
        
        btn_ingresar = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "send")))
        driver.execute_script("arguments[0].click();", btn_ingresar)
        print("[INFO] Autenticando en Vespucio Sur...")
        time.sleep(5)
        
        link_transitos = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Tránsitos no facturados')]"))
        )
        driver.execute_script("arguments[0].click();", link_transitos)
        time.sleep(4)
        
        print(f"[INFO] Aplicando rango de fechas: {fecha_inicio} a {fecha_fin}...")
        driver.execute_script(f"""
            var fDesde = document.getElementById('FechaDesde') || document.querySelector("input[name*='Desde']");
            if (fDesde) {{ fDesde.value = '{fecha_inicio}'; }}
            var fHasta = document.getElementById('FechaHasta') || document.querySelector("input[name*='Hasta']");
            if (fHasta) {{ fHasta.value = '{fecha_fin}'; }}
        """)
        time.sleep(1)

        # Clic en boton Filtrar
        btn_filtrar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@value='Filtrar'] | //button[contains(text(),'Filtrar')] | //a[contains(text(),'Filtrar')]"))
        )
        driver.execute_script("arguments[0].click();", btn_filtrar)
        time.sleep(4)

        # Comprobar si hay consumos registrados en pantalla
        cuerpo_pagina = driver.page_source.lower()
        if "no hay consumos registrados" in cuerpo_pagina or "no hay tránsitos" in cuerpo_pagina:
            print("[INFO] Vespucio Sur no registra transitos no facturados en el periodo indicado.")
            return

        # Si hay datos, disparar descarga CSV
        print("[INFO] Disparando descarga de CSV...")
        try:
            driver.execute_script("DescargarUltimosConsumos('CSV');")
        except Exception:
            btn_csv = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, \"DescargarUltimosConsumos('CSV')\")] | //a[contains(text(), 'CSV')]"))
            )
            driver.execute_script("arguments[0].click();", btn_csv)

        time.sleep(10)

        archivos = glob.glob(os.path.join(carpeta_descargas_temp, "*_NoFacturados*.csv")) or glob.glob(os.path.join(carpeta_descargas_temp, "*.csv"))
        if archivos:
            archivo_reciente = max(archivos, key=os.path.getctime)
            nuevo_nombre = f"VespucioSur_{datetime.now().strftime('%d%m%Y_%H%M%S')}.csv"
            ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
            
            if os.path.exists(ruta_final): 
                os.remove(ruta_final)
            shutil.move(archivo_reciente, ruta_final)
            print(f"[EXITO] Archivo Vespucio Sur guardado: {nuevo_nombre}")
            print(f"Ruta: {ruta_final}")
        else:
            print("[AVISO] No se detecto archivo descargado en la carpeta temporal.")

    except Exception as e:
        print(f"[ERROR] Fallo en proceso Vespucio Sur para {id_cliente}: {e}")
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
            extraer_vespuciosur_cliente(cliente_id, rut, password, descargas_temp, directorio_raiz)

if __name__ == "__main__":
    ejecutar()