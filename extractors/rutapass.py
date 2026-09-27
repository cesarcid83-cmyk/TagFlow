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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

def formatear_rut_puntos(rut_str):
    """Asegura el formato con puntos y guion: XX.XXX.XXX-X"""
    rut_limpio = rut_str.replace(".", "").replace("-", "").strip()
    if len(rut_limpio) < 2:
        return rut_str
    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]
    cuerpo_con_puntos = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_con_puntos}-{dv}"

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

def extraer_rutapass_cliente(id_cliente, rut, password, carpeta_descargas_temp, carpeta_destino_base):
    print(f"\n==========================================")
    print(f"[PROCESO] Iniciando extraccion RutaPass para: {id_cliente}")
    print(f"RUT: {rut}")
    print(f"==========================================")

    carpeta_cliente = os.path.join(carpeta_destino_base, "crudos", id_cliente)
    os.makedirs(carpeta_cliente, exist_ok=True)
    os.makedirs(carpeta_descargas_temp, exist_ok=True)

    rut_formateado = formatear_rut_puntos(rut)

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    prefs = {
        "download.default_directory": carpeta_descargas_temp,
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)

    try:
        driver.get("https://www.rutapass.cl/")
        time.sleep(4)
        
        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(1)
        
        driver.execute_script("""
            var elements = document.querySelectorAll('.modal, [class*="popup"], [id*="popup"], .modal-backdrop, [class*="overlay"]');
            elements.forEach(e => e.remove());
            document.body.style.overflow = 'auto';
        """)
        time.sleep(1)

        input_rut = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "username")))
        input_rut.clear()
        input_rut.send_keys(rut_formateado)
        time.sleep(1)
        
        input_pass = driver.find_element(By.ID, "password")
        input_pass.clear()
        input_pass.send_keys(password)
        time.sleep(1)
        
        btn_ingresar = driver.find_element(By.XPATH, "//button[@type='submit']")
        driver.execute_script("arguments[0].click();", btn_ingresar)
        time.sleep(5)
        
        driver.get("https://oficina-virtual.rutapass.cl/privada/detalle-de-transitos")
        time.sleep(3)
        
        btn_consultar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Consultar')]"))
        )
        driver.execute_script("arguments[0].click();", btn_consultar)
        time.sleep(5)
        
        btn_descargar = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Descargar detalle de tránsitos')]"))
        )
        
        driver.execute_script("""
            var flotante = document.getElementById('sticky-emergencia');
            if (flotante) { flotante.remove(); }
            var floatingBtns = document.querySelectorAll('.flotante, [class*="consultas"]');
            floatingBtns.forEach(el => el.remove());
        """)
        time.sleep(1)
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_descargar)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", btn_descargar)
        time.sleep(10)

        archivos = glob.glob(os.path.join(carpeta_descargas_temp, "Transitos__*.xls*")) or glob.glob(os.path.join(carpeta_descargas_temp, "*.xls*"))
        if archivos:
            archivo_reciente = max(archivos, key=os.path.getctime)
            nuevo_nombre = f"RutaPass_{datetime.now().strftime('%d%m%Y_%H%M%S')}.xls"
            ruta_final = os.path.join(carpeta_cliente, nuevo_nombre)
            
            if os.path.exists(ruta_final): os.remove(ruta_final)
            shutil.move(archivo_reciente, ruta_final)
            print(f"[EXITO] Archivo RutaPass guardado: {nuevo_nombre}")
            print(f"Ruta completa: {ruta_final}")
        else:
            print("[AVISO] No se detecto archivo descargado en RutaPass.")

    except Exception as e:
        print(f"[ERROR] Fallo en proceso RutaPass para {id_cliente}: {e}")
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
            extraer_rutapass_cliente(cliente_id, rut, password, descargas_temp, directorio_raiz)

if __name__ == "__main__":
    ejecutar()