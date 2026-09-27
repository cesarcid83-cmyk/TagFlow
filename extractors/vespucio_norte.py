import os
import sys
import json
import time
import glob
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

def formatear_rut_puntos(rut_str):
    rut_limpio = rut_str.replace(".", "").replace("-", "").strip()
    if len(rut_limpio) < 2: return rut_str
    cuerpo, dv = rut_limpio[:-1], rut_limpio[-1]
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"

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

def extraer_vespucionorte_cliente(id_cliente, rut, password, carpeta_descargas_temp, carpeta_destino_base):
    print(f"\n==========================================")
    print(f"[PROCESO] Iniciando extraccion Vespucio Norte para: {id_cliente}")
    print(f"RUT: {rut}")
    print(f"==========================================")

    carpeta_cliente = os.path.join(carpeta_destino_base, "crudos", id_cliente)
    os.makedirs(carpeta_cliente, exist_ok=True)
    os.makedirs(carpeta_descargas_temp, exist_ok=True)

    rut_formateado = formatear_rut_puntos(rut)

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

    # Elimina el indicador navigator.webdriver que gatilla el 403 Forbidden
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """}
    )

    try:
        # Carga la página principal
        driver.get("https://www.vespucionorte.cl/")
        time.sleep(4)
        
        btn_login = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "login-btn")))
        btn_login.click()
        time.sleep(2)
        
        input_rut = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "login-rut")))
        input_rut.clear()
        input_rut.send_keys(rut_formateado)
        
        input_pass = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "login-pass")))
        input_pass.clear()
        input_pass.send_keys(password)
        input_pass.send_keys(Keys.RETURN)
        
        print("[INFO] Esperando autenticacion en Vespucio Norte...")
        time.sleep(6)
        
        try:
            btn_continuar = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'CONTINUAR A OFICINA VIRTUAL')]"))
            )
            driver.execute_script("arguments[0].click();", btn_continuar)
            time.sleep(3)
        except Exception:
            pass
        
        form_boletas = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//form[@action='/VirtualOffice/BoletasConsumo']"))
        )
        driver.execute_script("arguments[0].submit();", form_boletas)
        time.sleep(4)
        
        select_element = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "selectClienteBol")))
        select = Select(select_element)
        
        opciones_cuentas = [opt.get_attribute("value") for opt in select.options if opt.get_attribute("value")]
        if opciones_cuentas:
            select.select_by_value(opciones_cuentas[0])
        time.sleep(1)
        
        btn_buscar = driver.find_element(By.ID, "btnBuscarCliente")
        driver.execute_script("arguments[0].click();", btn_buscar)
        time.sleep(4)
        
        tab_transitos = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Tránsitos no facturados')]"))
        )
        driver.execute_script("arguments[0].click();", tab_transitos)
        time.sleep(3)
        
        btn_excel = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Exportar Excel')]"))
        )
        driver.execute_script("arguments[0].click();", btn_excel)
        print("[INFO] Descargando archivo de Vespucio Norte...")
        time.sleep(8)

        archivos = glob.glob(os.path.join(carpeta_descargas_temp, "*_AVN_*.xlsx")) or glob.glob(os.path.join(carpeta_descargas_temp, "*.xlsx"))
        if archivos:
            archivo_reciente = max(archivos, key=os.path.getctime)
            nuevo_nombre = f"VespucioNorte_{datetime.now().strftime('%d%m%Y_%H%M%S')}.xlsx"
            ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
            
            if os.path.exists(ruta_final): os.remove(ruta_final)
            shutil.move(archivo_reciente, ruta_final)
            print(f"[EXITO] Archivo Vespucio Norte guardado: {nuevo_nombre}")
            print(f"Ruta completa: {ruta_final}")
        else:
            print("[AVISO] No se detecto archivo descargado en Vespucio Norte.")

    except Exception as e:
        print(f"[ERROR] Fallo en proceso Vespucio Norte para {id_cliente}: {e}")
    finally:
        try: driver.quit()
        except Exception: pass

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
            extraer_vespucionorte_cliente(cliente_id, rut, password, descargas_temp, directorio_raiz)

if __name__ == "__main__":
    ejecutar()