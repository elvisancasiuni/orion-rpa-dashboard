          
import selenium
import os
import re
import pandas as pd
import numpy as np
import hashlib
from pathlib import Path
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException

import time                       # Línea 17: Para usar time.sleep()
from datetime import datetime     # Línea 18
from datetime import time as dt_time  # Línea 19: Con alias para no pisar a la línea 17
# === ORION DASHBOARD ===
from orion_dashboard_tracker import registrar_envio
from github_dashboard_sync import sync_dashboard
import threading 
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import traceback
import re
import sqlite3 as sql
from tabulate import tabulate
from colorama import Fore
import certifi
import ssl

import tkinter as tk
from tkinter import ttk
import threading

# NOTA: El RPA está preparado para ejecutarse desde la carpeta
# del .py o del .exe y mantener CACHE_IA junto al ejecutable.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



printupdatedtickets="VALOR INICIAL"
checknewtik="VALOR INICIAL"
sendoldtickets="VALOR INICIAL"
ConfirmarData="VALOR INICIAL"
ConfirmarUsers="VALOR INICIAL"
ConfirmarData_2="VALOR INICIAL"
tj="VALOR INICIAL"
time_run_rpa="VALOR INICIAL"
reboot_rpa="VALOR INICIAL"
time_reboot_rpa="VALOR INICIAL"
time_range_rpa="VALOR INICIAL"
no_time_range_rpa=0
tipo_planta_externa2="valorinicial"
tipo_planta_externa="valorinicial"
maximo_delay_to_assign="valorinicial"
wait_after_first_request="VALOR INICIAL"
UseOrChangeData="VALOR INICIAL"
UseOrChangeData_2="VALOR INICIAL"

scapenewticket_1=0
scapenewticket_2=0


checktime_tick_for_updt=[]
checktime_tick_for_updt=datetime(datetime.now().year,datetime.now().month, datetime.now().day,0,0)
#print(checktime_tick_for_updt)

wd=webdriver.Chrome()

# =====================================================
# CONTROL VISUAL DE PAUSA Y CONTINUAR
# =====================================================

pause_event = threading.Event()

# El evento inicia activado: el RPA puede ejecutarse
pause_event.set()


def esperar_si_pausado():
    """
    Bloquea el RPA mientras esté pausado.
    Al presionar CONTINUAR, permite seguir.
    """
    pause_event.wait()


def crear_ventana_control():

    ventana = tk.Tk()

    ventana.title("ORION RPA - Control")
    ventana.geometry("350x190")
    ventana.resizable(False, False)

    ventana.attributes("-topmost", True)

    estado = tk.StringVar(value="ESTADO: EJECUTANDO")

    titulo = ttk.Label(
        ventana,
        text="ORION RPA",
        font=("Arial", 16, "bold")
    )

    titulo.pack(pady=10)

    etiqueta_estado = ttk.Label(
        ventana,
        textvariable=estado,
        font=("Arial", 11)
    )

    etiqueta_estado.pack(pady=5)

    def pausar():

        pause_event.clear()

        estado.set("ESTADO: PAUSADO")

        print("RPA PAUSADO")

    def continuar():

        pause_event.set()

        estado.set("ESTADO: EJECUTANDO")

        print("RPA CONTINUANDO")

    frame_botones = ttk.Frame(ventana)

    frame_botones.pack(pady=15)

    boton_pausar = ttk.Button(
        frame_botones,
        text="PAUSAR",
        command=pausar
    )

    boton_pausar.grid(
        row=0,
        column=0,
        padx=10
    )

    boton_continuar = ttk.Button(
        frame_botones,
        text="CONTINUAR",
        command=continuar
    )

    boton_continuar.grid(
        row=0,
        column=1,
        padx=10
    )

    ventana.mainloop()

# =====================================================
# INICIAR VENTANA DE CONTROL
# =====================================================

hilo_control = threading.Thread(
    target=crear_ventana_control,
    daemon=True
)

hilo_control.start()

print("Ventana de control iniciada.")

# =====================================================
def extraer_empresa(texto):
    """
    Extrae el nombre de la empresa de una cadena.
    """

    if " - " in texto:
        return texto.split(" - ")[0].strip()

    return texto.strip()

def extraer_empresa_from_right(texto):
    """
    Extrae el nombre de la empresa tomando como referencia
    el último ' - ' de la cadena.
    """

    if " - " in texto:
        return texto.rsplit(" - ", 1)[0].strip()

    return texto.strip()
# =====================================================
# CONFIGURACION DE RUTAS / CACHE IA
# =====================================================

# Carpeta donde se encuentra este .py o el .exe.
# La arquitectura portable queda:
#
# RPA_GITHUB/
# ├── ORION_RPA-MONITOREO_Y_CORREOS_GITHUB_AUTO.py
# ├── clientes.xlsx
# └── CACHE_IA/
#     ├── modelo/
#     ├── clientes.pkl
#     ├── clientes_hash.txt
#     └── embeddings.npy
#
# Si se compila con auto-py-to-exe en modo One Directory,
# esta misma estructura puede mantenerse junto al .exe.

BASE_DIR = Path(__file__).resolve().parent

CACHE_IA_DIR = BASE_DIR / "CACHE_IA"
MODELO_DIR = CACHE_IA_DIR / "modelo"
CLIENTES_CACHE = CACHE_IA_DIR / "clientes.pkl"
CLIENTES_HASH = CACHE_IA_DIR / "clientes_hash.txt"
EMBEDDINGS_CACHE = CACHE_IA_DIR / "embeddings.npy"

CACHE_IA_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================
# FUNCIONES DE CACHE
# =====================================================

def calcular_hash_archivo(ruta):
    """Calcula SHA-256 del archivo para detectar cambios."""
    sha256 = hashlib.sha256()

    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            sha256.update(bloque)

    return sha256.hexdigest()


def cache_clientes_valido(ruta_excel):
    """Verifica si el clientes.pkl corresponde al Excel actual."""
    if not CLIENTES_CACHE.exists():
        return False

    if not CLIENTES_HASH.exists():
        return False

    try:
        hash_actual = calcular_hash_archivo(ruta_excel)
        hash_guardado = CLIENTES_HASH.read_text(
            encoding="utf-8"
        ).strip()

        return hash_actual == hash_guardado

    except Exception as exc:
        print("No se pudo validar CACHE de clientes:", exc)
        return False


def guardar_hash_clientes(ruta_excel):
    """Guarda el hash actual de clientes.xlsx."""
    hash_actual = calcular_hash_archivo(ruta_excel)

    CLIENTES_HASH.write_text(
        hash_actual,
        encoding="utf-8"
    )


def embeddings_cache_valido(cantidad_empresas):
    """Verifica que el cache de embeddings corresponda a las empresas."""
    if not EMBEDDINGS_CACHE.exists():
        return False

    try:
        datos = np.load(
            EMBEDDINGS_CACHE,
            mmap_mode="r"
        )

        # Primera dimensión = cantidad de empresas.
        return datos.ndim == 2 and datos.shape[0] == cantidad_empresas

    except Exception as exc:
        print("No se pudo validar CACHE de embeddings:", exc)
        return False


# =====================================================
# CARGAR MODELO IA
# =====================================================

print("========================================")
print("INICIALIZACION DE INTELIGENCIA ARTIFICIAL")
print("========================================")

if (MODELO_DIR / "config.json").exists():

    print("Cargando modelo BAAI/bge-m3 desde CACHE local...")

    model = SentenceTransformer(
        str(MODELO_DIR)
    )

    print("Modelo local cargado.")

else:

    print("Modelo BAAI/bge-m3 no encontrado localmente.")
    print("Descargando modelo por primera vez...")

    model = SentenceTransformer(
        "BAAI/bge-m3"
    )

    print("Guardando modelo en CACHE_IA/modelo...")

    MODELO_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model.save(
        str(MODELO_DIR)
    )

    print("Modelo guardado correctamente.")

print("Modelo cargado.")

# =====================================================
# NORMALIZACIÓN
# =====================================================

ABREVIATURAS = {
    "S.A": " ",
    "SAC": " ",
    "S.A.C": " ",
    "S.A.A": " ",
    "SRL": " ",
    "EIRL": " ",
    "LTDA": " ",
    "CIA": " ",
    "COMPANIA": " ",
    "CORPORACION": " ",
    "CORP": " "
}


def limpiar(texto):

    if pd.isna(texto):
        return ""

    texto = str(texto).upper()

    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")

    texto = re.sub(r"[^A-Z0-9 ]", " ", texto)

    for k, v in ABREVIATURAS.items():
        texto = texto.replace(k, v)

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()

def extraer_celulares(texto):

    texto = str(texto)

    # Une números separados por espacios
    texto = re.sub(r'(\d{3})\s+(\d{3})\s+(\d{3})', r'\1\2\3', texto)

    # Cambia guiones por espacios
    texto = texto.replace("-", " ")

    celulares = re.findall(r'\b9\d{8}\b', texto)

    return celulares

# =====================================================
# LIMPIEZA AVANZADA PARA ALARMAS
# =====================================================

PALABRAS_BASURA = [
    "DBA",
    "DBI",
    "TDA",
    "CID",
    "NODE",
    "NODO",
    "GPON",
    "OLT",
    "PUERTO",
    "ALARMA",
    "STATUS",
    "DOWN",
    "UP",
    "S",
    "PR",
    "TX",
]

def limpiar_avanzado(texto):

    # Primero aplica la limpieza básica
    texto = limpiar(texto)

    # Eliminar códigos OIT: S377372, S432333...
    texto = re.sub(r"\bS\d+\b", " ", texto)

    # Eliminar números: 16600079, 336684...
    texto = re.sub(r"\b\d+\b", " ", texto)

    palabras = []

    for p in texto.split():

        if p not in PALABRAS_BASURA:

            if len(p) > 2:

                palabras.append(p)

    return " ".join(palabras)
# =====================================================
# LEER EXCEL / CACHE DE CLIENTES
# =====================================================

RUTA_CLIENTES = BASE_DIR / "clientes.xlsx"

print("")
print("========================================")
print("BASE DE CLIENTES")
print("========================================")

if not RUTA_CLIENTES.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {RUTA_CLIENTES}"
    )


if cache_clientes_valido(RUTA_CLIENTES):

    print("clientes.xlsx no ha cambiado.")
    print("Cargando clientes desde CACHE...")

    df = pd.read_pickle(
        CLIENTES_CACHE
    )

    print(
        f"Clientes cargados desde CACHE: {len(df)}"
    )

else:

    print("CACHE de clientes no existe o está desactualizado.")
    print("Leyendo clientes.xlsx...")

    df = pd.read_excel(
        RUTA_CLIENTES
    )

    df["CLIENTE"] = df["CLIENTE"].ffill()

    print(
        f"Empresas cargadas desde Excel: {len(df)}"
    )

    print("Guardando clientes.pkl...")

    df.to_pickle(
        CLIENTES_CACHE
    )

    guardar_hash_clientes(
        RUTA_CLIENTES
    )

    print("CACHE de clientes actualizado.")


# =====================================================
# LIMPIAR EMPRESAS
# =====================================================

empresas = (
    df["CLIENTE"]
    .fillna("")
    .astype(str)
    .tolist()
)

print(
    f"Registros de empresas disponibles: {len(empresas)}"
)

empresas_limpias = [
    limpiar(x)
    for x in empresas
]


# =====================================================
# CREAR / CARGAR EMBEDDINGS
# =====================================================

print("")
print("========================================")
print("EMBEDDINGS")
print("========================================")

if embeddings_cache_valido(
    len(empresas_limpias)
):

    print("Embeddings encontrados en CACHE.")
    print("Cargando embeddings.npy...")

    import torch

    embeddings_np = np.load(
        EMBEDDINGS_CACHE
    )

    embeddings = torch.from_numpy(
        embeddings_np
    )

    print(
        f"Embeddings cargados: {embeddings.shape}"
    )

else:

    print("Embeddings no encontrados o desactualizados.")
    print("Generando embeddings...")

    embeddings = model.encode(
        empresas_limpias,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    print(
        f"Embeddings generados: {embeddings.shape}"
    )

    print("Guardando embeddings.npy...")

    np.save(
        EMBEDDINGS_CACHE,
        embeddings.cpu().numpy()
    )

    print("Embeddings guardados correctamente.")


print("")
print("========================================")
print("CACHE IA LISTA")
print("========================================")
print(f"Modelo     : {MODELO_DIR}")
print(f"Clientes   : {CLIENTES_CACHE}")
print(f"Hash Excel : {CLIENTES_HASH}")
print(f"Embeddings : {EMBEDDINGS_CACHE}")
print("========================================")
print("")

# =====================================================
# BUSCADOR
# =====================================================

def buscar_empresa(texto):

    texto = limpiar_avanzado(texto)

    emb = model.encode(
        texto,
        convert_to_tensor=True,
        normalize_embeddings=True
    )

    similitudes = cos_sim(
        emb,
        embeddings
    )[0]

    mejores = similitudes.topk(k=10) # mejores = similitudes.topk(k=20)

    mejor_empresa = ""
    mejor_score = 0

    print("\nTop 20 candidatos:\n")

    for indice, score in zip(mejores.indices, mejores.values):

        indice = int(indice)

        empresa = empresas[indice]
        empresa_limpia = empresas_limpias[indice]

        fuzzy = fuzz.token_set_ratio(
            texto,
            empresa_limpia
        )

        score_final = (
            float(score) * 100 * 0.75 +
            fuzzy * 0.25
        )

        print(f"{empresa}")
        print(f"Embedding : {float(score)*100:.2f}")
        print(f"RapidFuzz: {fuzzy:.2f}")
        print(f"Final     : {score_final:.2f}")
        print("-"*50)

        if score_final > mejor_score:
            mejor_score = score_final
            mejor_empresa = empresa

    print("\n==============================")
    print("MEJOR COINCIDENCIA")     
    print("==============================")
    print("Empresa :", mejor_empresa)      #print("Empresa :", empresa)
    print(f"Score   : {mejor_score:.2f}")  #print(f"Score   : {score:.2f}")  

    return mejor_empresa, mejor_score

# =====================================================
# OBTENER CONTACTOS DEL CLIENTE
# =====================================================

def obtener_contactos(cliente):

    # Filtrar todas las filas del cliente
    filas = df[df["CLIENTE"].fillna("") == cliente]

    telefonos = []
    correos = []
    contactos_telefonos = {}

    for _, fila in filas.iterrows():
                # CONTACTO
        # ==========================
        contacto = str(fila["CONTACTO"]).strip()
        # =============================
        # TELEFONOS
        # =============================
        numero = fila["NÚMERO DE CONTACTO"]
      
        telefonos.extend(extraer_celulares(numero))

        # Asociar cada teléfono con su contacto
        for n in extraer_celulares(numero):
            if n not in contactos_telefonos:
                contactos_telefonos[n] = contacto
        # =============================
        # CORREOS
        # =============================
        correo = str(fila["CORREO ELECTRÓNICO"]).strip()

        if correo and correo.lower() != "nan":
            correos.append(correo)

    # Eliminar duplicados conservando el orden
    telefonos = list(dict.fromkeys(telefonos))
    correos = list(dict.fromkeys(correos))

    return telefonos, correos, contactos_telefonos

def extraer_OITs(texto):
    patron = r'(?<!\d)S?(\d{6})(?!\d)'
    return re.findall(patron, texto.upper())
# =====================================================
# =====================================================

maximo_delay_to_assign="VALOR INICIAL"


List_All_name_empresa_acotado=[]
List_All_empresa=[]

List_name_empresa_acotado_Mayor_80=[]
List_name_empresa_acotado_Menor_80=[]


for j in range(1000):
     List_All_name_empresa_acotado.append("")
     List_All_empresa.append("")
     List_name_empresa_acotado_Mayor_80.append("")
     List_name_empresa_acotado_Menor_80.append("")


while True :
     try:
          wd.maximize_window()           
          break
     except : 
          pass

print("INGRESAR EL TIEMPO LIMITE DE ASIGNACION DE ALARMA (MIN)")

while type(maximo_delay_to_assign) !=float or maximo_delay_to_assign==0:
     try: 
          maximo_delay_to_assign = float(input("INGRESAR EL TIEMPO (MINUTOS) : "))
     except:
          pass

print("")
print("")
print("¿QUIERE MONITOREAR LOS CLIENTES CON RESIDENTES?")
print("")
print("INGRESAR '1' COMO RESPUESTA AFIRMATIVA")
print("INGRESAR '0' EN CASO CONTRARIO")

print("")

enviar_casos_residente="VALOR INICIAL"

while enviar_casos_residente  !=0 and enviar_casos_residente  !=1:
     try: 
          enviar_casos_residente  = int(input("Ingresar '1' o '0' : "))
     except:
          pass
print("")

while True :
     try:
          wd.get("https://orion.entel.pe/orion/netperfmon/alerts.aspx")      
          break
     except : 
          pass
print("========================================")
print("INGRESAR CREDENCIALES ORION")

#while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
     try:
          """wd.find_element(By.XPATH,'//*[@id="ctl00_BodyContent_Username"]').send_keys("elvis.ancasi")
          time.sleep(1)
          wd.find_element(By.XPATH,'//*[@id="ctl00_BodyContent_Password"]').send_keys("vJFjSP9#@koGsz#8DqjBnN")
          time.sleep(1)

          #wd.find_element(By.XPATH,'//*[@id="login-jsp-btn"]').click()
          wd.find_element(By.XPATH,'//*[@id="ctl00_BodyContent_LoginButton"]').click()
          time.sleep(2)"""
          #user_orion=wd.find_element(By.XPATH,'//*[@id="ctl00_BodyContent_Username"]').text
          wd.find_element(By.XPATH,'//*[@id="content"]') # CAMBIO 03-09-26
     
          break
     except : 
          pass

     """while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
          try:
               wd.find_element(By.XPATH,'//*[@id="mega-menu-alerts"]/span[1]').click()
               time.sleep(1)
               #//*[@id="user-menu-dropdown"]/span[2]
               user_orion=wd.find_element(By.XPATH,'//*[@id="user-menu-dropdown"]/span[2]').text
               break
          except : 
               pass """

     """while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
          try:
               wd.find_element(By.XPATH,'//*[@id="alerts-item-0"]').click()
               user_orion=wd.find_element(By.XPATH,'//*[@id="user-menu-dropdown"]/span[2]').text
               time.sleep(1)
               break
          except : 
               pass"""
               
while True :
     try:
          wd.find_element(By.XPATH,'//*[@id="alertGrid"]/div[2]/h1')
          user_orion=wd.find_element(By.XPATH,'//*[@id="user-menu-dropdown"]/span[2]').text
          break
     except :
          #wd.refresh()
          #time.sleep(2)
          pass
print("")

user_orion=user_orion.lower()

ndt=0
x=0
y=0
xx=0
r=0
rr=0
zz=0
#######################3

while True :
     try:
          wd.execute_script ("window.open('http://192.168.62.112/saf/login/')")
          break
     except : 
          pass

wd.switch_to.window(wd.window_handles[1])


while True :
     try:

          wd.find_element(By.XPATH,'//*[@id="id_user"]').send_keys("tlo_asalvador")
          wd.find_element(By.XPATH,'//*[@id="id_passwd"]').send_keys("Zeuss_yoyo6995")
          time.sleep(2) 
          wd.find_element(By.XPATH,'//*[@id="sign-in"]').click()
          time.sleep(4)
          wd.find_element(By.XPATH,'//*[@id="site-name2"]')

          break
     except :
          wd.refresh()

          while True :
               try:
                    wd.find_element(By.XPATH,'//*[@id="id_user"]')
                    break
               except:
                    pass
          pass


while True :
     try:
         
          wd.execute_script("window.open('https://outlook.cloud.microsoft/mail/inbox/id/AAkALgAAAAAAHYQDEapmEc2byACqAC%2FEWg0A9DohycTzw0iPk68LzsVqFQADQ%2Bb6ygAA?deeplink=mail%2F')")
          wd.get("chrome://settings/")
          wd.execute_script("chrome.settingsPrivate.setDefaultZoom(0.75);")


          
          wd.execute_script("document.body.style.zoom='75%'")

          break
     except : 
          pass

wd.execute_script("document.body.style.zoom='75%'")
     
wd.switch_to.window(wd.window_handles[2])

print("LOGARSE EN OUTLOOK")

while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
     try:
          wd.find_element(By.XPATH,'//*[@id="588"]/button[1]/span[2]')
          break
     except : 
          pass

time.sleep(1)


while True :
     try:
          wd.execute_script ("window.open('https://web.whatsapp.com/')")
          break
     except : 
          pass

print("Escanear el codigo QR")

wd.switch_to.window(wd.window_handles[3])

while True :
          #Este bucle me ayudo bastante hasta que carge el elemento WEB
          #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
     try:
          wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')
          wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()

          break
     except : 
          pass

wd.switch_to.window(wd.window_handles[0]) 

newticket=0

list_trigger_time_sent=[]
Lista_alarmas_already_checked=[]
trigger_time_already_checked=[]

Lista_alarmas=[]
trigger_time=[]
Acknowledged_by=[]

Lista_alarmas_2=[]
trigger_time_2=[]
Acknowledged_by_2=[]

list_mail_alarma_sent=[]
list_mail_trigger_time_sent=[]

#alarm_empresa_Solarwins=[['PRISONTEC S.A.C. - S383862 - AVENIDA DE LA CULTURA NRO. S/N KILOMETRO 5.5 (SAN JERONIMO - CUSCO - CUSCO) (REF: COORDENADAS -13.543611 -71.893056)'],['HARD DISCOUNT - S443653 - DBA'],['COMPAÑIA HARD DISCOUNT S.A.C. - S446024 - DBA'],['COMPAÑIA HARD DISCOUNT - S446017 - DBA - 5Mbps - Av. TRUJILLO NRO. S/N MZ. C LTE. 5 URB. ROMA - LIBERTAD'],['ORANGE - DBI - S362140 - LO64701786_LENOVO_CID 153247'],['SUTRAN - DBA - S379807 - CARRETERA PANAMERICANA NORTE KILOMETRO 588 (CHICAMA - ASCOPE - LA LIBERTAD)'],['ORANGE - DBI -  S400100 - COLGATE - BK'],['ORANGE - DBI - S430997']]
#mail_empresa=[['edu.nunez@prisontec.com','gustavo.sandoval@prisontec.com','miguel.altamirano@prisontec.com','maribel.huaman@prisontec.com'],['experis-johnny.llanos@spsa.pe','experis-daniel.llanos@spsa.pe','experis-kelly.laca@spsa.pe,monitoreo.central@intercorpretail.pe'],['experis-johnny.llanos@spsa.pe','experis-daniel.llanos@spsa.pe','experis-kelly.laca@spsa.pe,monitoreo.central@intercorpretail.pe'],['experis-johnny.llanos@spsa.pe','experis-daniel.llanos@spsa.pe','experis-kelly.laca@spsa.pe,monitoreo.central@intercorpretail.pe'],['redes@minjus.gob.pe','dquispe@minjus.gob.pe','jcarrasco@minjus.gob.pe','mtrinidad@minjus.gob.pe','oist30@minjus.gob.pe','oist37@minjus.gob.pe','moises.lopez@entel.pe'],['rio.im@orange.com','rio.pm@orange.com','alexandre.araujo@orange.com','lucas.motta@orange.com','karoline.mendes@orange.com','gabriel.fernandes@orange.com'],['lromero@sutran.gob.pe'],['rio.im@orange.com','rio.pm@orange.com','alexandre.araujo@orange.com','lucas.motta@orange.com','karoline.mendes@orange.com','gabriel.fernandes@orange.com'],['rio.im@orange.com','rio.pm@orange.com','alexandre.araujo@orange.com','lucas.motta@orange.com','karoline.mendes@orange.com','gabriel.fernandes@orange.com']]
               
ntk= 4  # IMPORTANTE # IMPORTANTE # IMPORTANTE
ntk_01=0
#ntk= 10   # IMPORTANTE 
#yy=1  # MOMENTANEO
ultimo_refresh = time.time()

#print("Hora de incio de ejecucion de RPA =" ,time.time())

var_first_check=0

inicio_ejecucion=time.time()

print("Hora de incio de ejecucion de RPA =" ,inicio_ejecucion)

check_to_add=0
while True :
     N_excep=0

     esperar_si_pausado()

     do_click_01=0
     do_click_02=0
     do_click_03=0
     do_click_04=0
     do_click_05=0
     do_click_06=0

     yy=1 # CAMBIO 03-09-2026
     zz=1 # CAMBIO 03-09-2026
     k=1
     #yy=1 # CAMBIO 03-09-2026
     #zz=1 # CAMBIO 03-09-2026
     var_to_continue=1
     id_new_trigger_time=[]
     id_new_trigger_time_repeated=[[]]

     List_i_to_eliminate=[]
     List2_i_to_eliminate=[]

     #Lista_alarmas=[]
     #trigger_time=[]
     #Acknowledged_by=[]
 
     Lista_alarmas_new=[]
     new_lista_Lista_alarmas_new=[]
     List_empresa_filter_alarm=[]
     List_oit_filter_alarm=[]
     List_address_filter_alarm=[]

     Lista_alarmas_to_send=[]
     trigger_time_to_send=[]
     Acknowledged_by_to_send=[]


     NEW_Lista_alarmas_new = []
     NEW_Lista_trigger_time_new = []
     NEW_Lista_Acknowledged_by_new = []

     List_address=[]
     List_OITs=[]
     trigger_time_new=[]
     Acknowledged_by_new=[]
     
     Lista_alarmas_new_no_cleaned=[]
     trigger_time_new_no_cleaned=[]
     Acknowledged_by_new_no_cleaned=[]
     
     Lista_alarmas_repeated=[[]]
     Lista_alarmas_repeated_cleaned=[[]]

     trigger_time_repeated=[[]]
     Acknowledged_by_repeated=[[]]

     # === ORION DASHBOARD - PUBLICACION INICIAL ===
     try:
          ok_dashboard, msg_dashboard = sync_dashboard(force=True)
          print("ORION Dashboard:", msg_dashboard)
     except Exception as exc_dashboard:
          print("ORION Dashboard: publicación inicial no disponible:", exc_dashboard)

     
     if time.time() - ultimo_refresh >=300:  # 600 segundos = 10 min   # CAMBIO 03-09-26
               
            try:            
               print("Recargando página...")
               print("Hora de refresh =" ,time.time())

               wd.find_element(By.XPATH,'//*[@id="alertGrid"]/div[2]/h1').click() 
               wd.refresh()
               wd.switch_to.window(wd.window_handles[1])

               print()
               # Esperar a que cargue nuevamente
               time.sleep(4)
               wd.switch_to.window(wd.window_handles[0])
               wd.find_element(By.XPATH,'//*[@id="alertGrid"]/div[2]/h1').click()
               ultimo_refresh = time.time()
            except:
                 pass
         
     if len(Lista_alarmas_already_checked)>0:
          
          print("Lista_alarmas_already_checked =" , Lista_alarmas_already_checked)
          #else:  # len(Lista_alarmas_already_checked) >= 0:
          
          while True :
               while True :
                    try:
                         List_element= wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(zz)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text                                                
                         break
                    except :
                         if zz >=250:
                              break
                         pass
               while True :
                    try:
                         trigger_element= wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(zz)+']/table/tbody/tr/td[7]/div/span').text                                                 
                         break

                    except : 
                         if zz >=250:
                              break
                         pass
               while True :
                    try:
                         Acknowledged_element= wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(zz)+']/table/tbody/tr/td[8]/div/span').text                                                 
                         break
                    except : 
                         if zz >=250:
                              break
                         pass
               if List_element in Lista_alarmas_already_checked:
                    if trigger_element in trigger_time_already_checked:
                         ntk_01=zz-1  # ntk=1+zz-1  # ACA "ntk" tomara un valor de "0" cuando no haya nuevas alarmas o "zz-1" cuando haya cualquier cantidad de nuevas alarmas
                         #ntk=zz # CAMBIO 05-09-2026
                         break
                    else:
                         zz=zz+1
                         
                         fecha_trigger = datetime.strptime(trigger_element, "%m/%d/%Y %I:%M %p").timestamp()
                         First_trigger_time_already_checked = datetime.strptime(trigger_time_already_checked[0], "%m/%d/%Y %I:%M %p").timestamp()

                         if fecha_trigger < First_trigger_time_already_checked:
                              ntk_01=zz-1   # ESTO SE ME ESTABA PASANDO DESAPERCIBIDO
                              break

               else:
                    zz=zz+1

                    fecha_trigger = datetime.strptime(trigger_element, "%m/%d/%Y %I:%M %p").timestamp()
                    First_trigger_time_already_checked = datetime.strptime(trigger_time_already_checked[0], "%m/%d/%Y %I:%M %p").timestamp()

                    if fecha_trigger < First_trigger_time_already_checked:
                         ntk_01=zz-1   # ESTO SE ME ESTABA PASANDO DESAPERCIBIDO
                         break
                    #if zz >=250:
                    #     print("Valor de zz =",zz )
                    #     ntk=250
                    #     break
                         
          ################################
          #if var_to_continue==1 and ntk>=1 :
     f=0
     for x in range(ntk+ntk_01+len(Lista_alarmas)): # CAMBIO 28-09-26
     #for x in range(788): # CAMBIO 28-09-26

          while True :

               try:                                   
                    if x<250:
                         print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                         print("Valor de YY = ",yy)
                         
                         var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text                            
                         var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                         var_trigger_time=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text 
                         
                            # CHANGE 27-10-26
                         """ # SOLO PARA TESTEAR Y FORZAR UNA MASIVA
                         if yy<4:
                              var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text                            
                              var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              var_trigger_time=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text 
                         else:
                              var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text                            
                              var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              var_trigger_time='11/6/2026 10:50 AM'
                         """# SOLO PARA TESTEAR Y FORZAR UNA MASIVA  

                    elif x<500:
                         #elif x<350:
                         print("Rastreo_01")

                         print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                         print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                         #print("type(get_attribute('value')) = ",type(wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')))
               
                         while True :
                              try: 
                                   print("Rastreo_02")
                                   print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                                   print("Rastreo_00002")

                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="1" and do_click_01==0 :
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click()
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
                                        print("Rastreo_03")
                                        do_click_01=1
                              
                                   break
                              except :
                                   print("Rastreo_04") 
                                   pass   

                         while True :
                              try: 
                                   print("Rastreo_05") 
                                   wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]')   
                                   print("Rastreo_06")                              
                                   break
                              except : 
                                   print("Rastreo_07") 
                                   pass   

                         print("Rastreo_08")
                         print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                         print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                         print("")
                         if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="2":
                              print("Rastreo_09") 
                              print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                              do_click_01=0

                              var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text
                              var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              var_trigger_time=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text  
                              print("Rastreo_10") 

                    elif x<750:
                    #elif x<450:
                         print("Rastreo_11") 
                         print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                         print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
               
                         while True :
                              try:
                                   print("Rastreo_12") 
                                   print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                                   print("Rastreo_11112") 
                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="1" and do_click_02==0:
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click() 
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
                                        do_click_02=1
                                        print("Rastreo_13")    

                                   break
                              except : 
                                   pass   

                         while True :
                              try:
                                   print("Rastreo_14")
                                   print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                                   print("Rastreo_11114")
                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="2" and do_click_03==0:
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click()  
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click() 
                                        do_click_03=1
                                        print("Rastreo_15")   
                    
                                   break
                              except : 
                                   pass   


                         while True :
                              try:
                                   print("Rastreo_16") 
                                   wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]')
                                   print("Rastreo_17")                                 
                                   break
                              except : 
                                   pass   

                         print("Rastreo_18") 
                         print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                         print("Rastreo_11118") 

                         if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="3":
                              do_click_02=0
                              do_click_03=0


                              print("Rastreo_19")  
                              print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                              var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text
                              var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              var_trigger_time=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text  
                              print("Rastreo_20") 

                    elif x<1000:
                    #elif x<550:
                         print("Rastreo_21") 
                         print("((wd.get_attribute('value'))) = ",wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute("value"))
                         print("Valor de YYYYYYYYYYYYYYYYY = ",yy)

                         while True :
                              try:
                                   print("Rastreo_22")
                                   print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                                   print("Rastreo_22222") 
                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="1" and do_click_04==0: 
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click()  
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
                                        do_click_04=1
                                        print("Rastreo_23")   

                                   break
                              except : 
                                   pass   

                         while True :
                              try:
                                   print("Rastreo_24")
                                   print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                                   print("Rastreo_22224")
                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="2" and do_click_05==0:
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click() 
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
                                        do_click_05=1
                                        print("Rastreo_25")       
          
                                   break
                              except : 
                                   pass   

                         while True :
                              try:
                                   print("Rastreo_26")
                                   print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                                   print("Rastreo_222226")
                                   if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="3" and do_click_06==0:
                                        #wd.find_element(By.XPATH,'//*[@id="ext-gen85"]').click()  
                                        WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
                                        do_click_06=1
                                        print("Rastreo_27")        
                    
                                   break
                              except : 
                                   pass   

                         while True :
                              try:
                                   print("Rastreo_28") 
                                   wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]')   
                                   print("Rastreo_29")                              
                                   break
                              except : 
                                   pass   

                         print("Rastreo_30") 

                         print("wd.get_attribute('value') ", wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value'))
                         print("Rastreo_333330") 
                         if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="4":
                              

                              do_click_04=0
                              do_click_05=0
                              do_click_06=0

                              print("Rastreo_31") 
                              print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                              
                              var_Acknowledged_by=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text
                              var_Lista_alarmas=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              var_trigger_time=wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text  

                              print("Rastreo_32") 
               
                    print("Rastreo_33")
                    break  # CAMBIO 28-09-2026 REVERTIR DESPUES DE LA PRUEBA
               except :

                    if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="4":
                         break
                    
                    """if wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')=="4":                       
                         N_excep=N_excep+1
                    if N_excep>60:
                         print("N_excep = ", N_excep)
                         break """

                    print("Rastreo_34") 
                    pass  

          if var_first_check==0:
               #list_user_Acknowledged=['Acknowledge'] # luego rollback
               list_user_Acknowledged=['Acknowledge','renzo.ramos.olitel','yonal.cordova','dexter.izarra.olitel','juan.chavez.olitel','melanie.cotrina.olitel','elvis.ancasi','anthony.flores.externo','luis.olivares.olitel','paula.arellano.externo','ezio.gonzales.olitel','adilson.olivares.olitel','yoselin.ignacio.olitel','john.pereda.externo'] # CHANGE 27-10-26
          else:
               #list_user_Acknowledged=['Acknowledge',user_orion] # luego rollback
               list_user_Acknowledged=['Acknowledge','renzo.ramos.olitel','yonal.cordova','dexter.izarra.olitel','juan.chavez.olitel','melanie.cotrina.olitel','anthony.flores.externo','luis.olivares.olitel','paula.arellano.externo','ezio.gonzales.olitel','adilson.olivares.olitel','yoselin.ignacio.olitel','john.pereda.externo'] # CHANGE 27-10-26

          if var_Acknowledged_by in list_user_Acknowledged:   # CAMBIO 01-10-26
              
               find_resident_1=var_Lista_alarmas.lower().find('falabella')
               find_resident_2=var_Lista_alarmas.lower().find('sencico')
               find_resident_3=var_Lista_alarmas.lower().find('compartamos')
               find_resident_4=var_Lista_alarmas.lower().find('alfin banco')
               find_resident_5=var_Lista_alarmas.lower().find('sernanp')
               find_resident_6=var_Lista_alarmas.lower().find('tinka')
               find_tienda=var_Lista_alarmas.find('TDA_ENTEL')
               find_VP=var_Lista_alarmas.lower().find('entel vp')
               find_defensa_banda=var_Lista_alarmas.lower().find('defensa banda')

               var_time = datetime.strptime(var_trigger_time, "%m/%d/%Y %I:%M %p")
             
               dia = var_time.weekday()
               hora = var_time.time()

               # Horario general
               # L-V: 00:00-08:30 o 18:00-23:59
               # S-D: todo el día
               horario_general = (dia >= 5 or(dia <= 4 and (hora < dt_time(8, 30) or hora >= dt_time(18, 0))))

               # Horario TINKA
               # L-V: 00:00-08:30 o 18:00-23:59
               # Sábado: 00:00-08:30 o 12:30-23:59
               # Domingo: todo el día
               horario_tinka = (dia == 6 or (dia <= 4 and (hora < dt_time(8, 30) or hora >= dt_time(18, 0))) or (dia == 5 and (hora < dt_time(8, 30) or hora >= dt_time(12, 30))))

               cliente_residente = (find_resident_1 != -1 or find_resident_2 != -1 or find_resident_3 != -1 or find_resident_4 != -1 or find_resident_5 != -1)
               es_tinka = find_resident_6 != -1

               fecha_timestamp = datetime.strptime(var_trigger_time, "%m/%d/%Y %I:%M %p").timestamp()

               #if fecha_timestamp >= inicio_ejecucion:  # ROALLBACK 06-11-26 # SUCEDIO UN ERROR , REVISAR LOG EN WHATSAPP GUARDADO FECHA 03:05 AM __10-10-26
               
               if ( enviar_casos_residente == 1 or (enviar_casos_residente == 0 and ((not cliente_residente and not es_tinka) or(cliente_residente and horario_general) or (es_tinka and horario_tinka)))):
                    if find_tienda==-1 and find_VP==-1 and find_defensa_banda==-1:

                         # SIGUIENTE LÍNEA DE TU RPA
                         print("PASA")
                         time_with_except=0
                         """ # ROLLBACK LUEGO DE TEST , LINEA 1363
                         while True: # LO DESHABILITO PORQUE AL QUERER HACER CLICK NUEVAMENTE GENERA UN ERROR INFITO PORQUE YA  NO PUEDE HACERSE CLICK UNA SEGUNDA VEZ
                              try: # CAMBIO FOR TEST 06-10-26
                                   #element = WebDriverWait(wd,5).until(EC.element_to_be_clickable((By.XPATH, "//span[contains(@class,'sw-btn') and .//span[normalize-space()='Acknowledge']]")))
                                   #############################
                                   xpath_acknowledge = ('//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]//span[@automation="Acknowledge"]')
                                   element = WebDriverWait(wd,3).until(EC.element_to_be_clickable((By.XPATH, xpath_acknowledge)))
                                   element.click()
                                   print("Me asigne la alarma")
                                   ##############################
                                   break # ACA LA FREGUE 04-10-26 , ESTE BREAK NO DEBIA ESTAR SOLO ERA VALIDA CUANDO ESTA EL "WHILE TRUE" PERO ESTA DESHABILITADO
                              except:
                                   time_with_except=time_with_except+1
                                   if time_with_except>=5:
                                        print("entre a IF , linea 1358")
                                        break
                                   pass
                         """
                         print("Rastreo_previo a IF (LINE-1289)") 
                         
                         
                         # CAMBIO FOR TEST 06-10-26

                         #if find_tienda==-1 and find_VP==-1 and find_defensa_banda==-1:
                         
                         if var_Lista_alarmas not in Lista_alarmas_already_checked:
                              if var_trigger_time not in trigger_time_already_checked:
                                   print("Rastreo LINE-1293") 
                                   w1=''
                                   w2=''
                                   w3=''
                                   while w1 =='' or w2=='' or w3=='':
                                        while True :
                                             try:
                                                  #Lista_alarmas.append(wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text) # CHANGE 27-10-26
                                                  Lista_alarmas.append(var_Lista_alarmas)                                     
                                                  print("Rastreo_37")

                                                  break
                                             except : 
                                                  pass
                                        while True :
                                             try:
                                                  #trigger_time.append(wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[7]/div/span').text) # CHANGE 27-10-26                                     
                                                  trigger_time.append(var_trigger_time)
                                                  print("Rastreo_38")
                                                  break
                                             except : 
                                                  pass
                                        while True :
                                             try:
                                                  #Acknowledged_by.append(wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(yy)+']/table/tbody/tr/td[8]/div/span').text) # CHANGE 27-10-26
                                                  Acknowledged_by.append(var_Acknowledged_by)
                                                  print("Rastreo_36")  
                                                  break
                                             except :
                                                  pass  
                                        check_to_add=1  
                                        f=f+1

                                        w1=Lista_alarmas[-1]
                                        w2=trigger_time[-1]
                                        w3=Acknowledged_by[-1]  
                                        print("Rastreo_39 , LINEA 1400")
                                        print("========================================")
                                        print("Lista_alarmas=",Lista_alarmas)
                                        print("")
                                        print("trigger_time=",trigger_time)
                                        print("")
                                        print("Acknowledged_by=",Acknowledged_by)
                                        print("========================================")
                                        print("Rastreo_LINEA 1408")

          yy=yy+1
          #if yy>=251:
          if yy>=251:  # CAMBIO 28-09-26
               yy=1

               var_get_attribute=wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')
               Integer_varget_attribute=int(var_get_attribute)
               
               WebDriverWait(wd, 10).until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "x-tbar-page-next")]'))).click()
               print("Rastreo_03030303")
               #do_click_01=1
               
               while wd.find_element(By.XPATH,'//input[contains(@class,"x-tbar-page-number")]').get_attribute('value')!=str(Integer_varget_attribute+1):
                    try:
                         print("Rastreo_00003")
                         yy=1
                         print("Valor de YYYYYYYYYYYYYYYYY = ",yy)
                         print("Rastreo_000000003")
                    except:
                         pass
          
               print("Valor de YYYYYYYYYYYYYYYYY = ",yy)

     if check_to_add==1:

          Lista_alarmas_already_checked=Lista_alarmas_already_checked + Lista_alarmas[len(Lista_alarmas)-f:]    #CHANGE 09-10-2026 
          print("Lista_alarmas_already_checked = " , Lista_alarmas_already_checked) #CHANGE 09-10-2026 
          print("")                                  #CHANGE 09-10-2026 
          trigger_time_already_checked=trigger_time_already_checked + trigger_time[len(trigger_time)-f:]           #CHANGE 91-10-2026
          print("trigger_time_already_checked = " , trigger_time_already_checked)   #CHANGE 09-10-2026 
          check_to_add=0

     print("")
     var_first_check=1
     print("var_first_check = ",var_first_check)

     vistos =[]
     repetidos =[]

     check_to_send=0

     Lista_alarmas_to_send=[]
     trigger_time_to_send=[]
     Acknowledged_by_to_send=[]

     for i,element in enumerate(trigger_time):  # ACA DEBO COMPARAR EL TIEMPO SI QUIERO ESPERAR UN TIEMPO ANTES DE ALERTAR
          print("Lista_alarmas[i] = ",Lista_alarmas[i])
          print("trigger_time[i] = ",trigger_time[i])

          ### ACA VOY A COMPARAR TIEMPOS ###
          element_new_format = datetime.strptime(element, "%m/%d/%Y %I:%M %p")

          diftime =datetime.now()-element_new_format
          #maximo_delay_to_assign=120
          diftime_horas=diftime.total_seconds()/60
          
          if diftime_horas >=maximo_delay_to_assign:
               ######## NEW CODING FOR CHECK IF ALARMA CONTINUE AFTER 10 MIN ###############
               zz=1 
               check_to_send=0  
                  # ROLLBACK CHANGE 28-10-2026 ESTO SOLO PARA FORZAR LA PRUEBA , LUEGO HABILITARLO   
               while True :
                    
                    while True :
                         try:
                              var_alarm= wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(zz)+']/table/tbody/tr/td[5]/div/div/span[1]/a/span').text
                              print("Rastreo_linea 1458")                                                
                              break
                         except :
                              if zz >=250:
                                   print("Rastreo_linea 1462")
                                   break
                              pass
                    while True :
                         try:
                              var_triger= wd.find_element(By.XPATH,'//*[@id="ext-gen54"]/div['+str(zz)+']/table/tbody/tr/td[7]/div/span').text 
                              print("Rastreo_linea 1468")                                                
                              break

                         except : 
                              if zz >=250:
                                   print("Rastreo_linea 1473")
                                   break
                              pass

                    if var_alarm == Lista_alarmas[i]:
                         print("Rastreo_linea 1478")
                         if var_triger == trigger_time[i]:
                 
                              print("Rastreo_linea 1480")
                              Lista_alarmas_to_send.append(Lista_alarmas[i])
                              trigger_time_to_send.append(trigger_time[i])
                              Acknowledged_by_to_send.append(Acknowledged_by[i])
                              print("Linea 1538")

                              #ntk_01=zz-1  # ntk=1+zz-1  # ACA "ntk" tomara un valor de "0" cuando no haya nuevas alarmas o "zz-1" cuando haya cualquier cantidad de nuevas alarmas
                              check_to_send=1
                              #ntk=zz # CAMBIO 05-09-2026
                              break
                         else:
                               print("Rastreo_linea 1486")
                               zz=zz+1

                               fecha_trigger = datetime.strptime(var_triger, "%m/%d/%Y %I:%M %p").timestamp()
                               Form_trigger_time = datetime.strptime(trigger_time[i], "%m/%d/%Y %I:%M %p").timestamp()
                               
                               if fecha_trigger < Form_trigger_time:
                                   #ntk_01=zz-1   # ESTO SE ME ESTABA PASANDO DESAPERCIBIDO
                                   check_to_send=0
                                   List_i_to_eliminate.append(i)
                                   print("List_i_to_eliminate = " , List_i_to_eliminate)
                                   print("Linea 1555")
                                   break
                    else:
                         print("Rastreo_linea 1498")
                         zz=zz+1
                         fecha_trigger = datetime.strptime(var_triger, "%m/%d/%Y %I:%M %p").timestamp()
                         Form_trigger_time = datetime.strptime(trigger_time[i], "%m/%d/%Y %I:%M %p").timestamp()

                         if fecha_trigger < Form_trigger_time:
                              #ntk_01=zz-1   # ESTO SE ME ESTABA PASANDO DESAPERCIBIDO
                              check_to_send=0
                              List_i_to_eliminate.append(i)
                              print("Rastreo_linea 1506")
                              print("List_i_to_eliminate = " , List_i_to_eliminate)
                              print("Linea 1569")
                              break
               
                    ######## NEW CODING FOR CHECK IF ALARMA CONTINUE AFTER 10 MIN ###############

               #check_to_send=1    # ROLLBACK CHANGE 28-10-2026 ESTO SOLO PARA FORZAR LA PRUEBA , LUEGO DESHABILITARLO
               if check_to_send==1:
                    print("Rastreo_linea 1511")
                         
                    if element in vistos:
                         repetidos.append(element) # Aca element=repetidos[-1] , por eso en el siguiete IF comparto repetidos[-2]....
                                                  # .....para crear una nueva lista de repetidos (Lista_alarmas_repeated,trigger_time_repeated,Acknowledged_by_repeated )
                         try:
                              if element != repetidos[-2]:
                                   Lista_alarmas_repeated.append([])
                                   Lista_alarmas_repeated[-1].append(Lista_alarmas[i])
                                   trigger_time_repeated.append([])
                                   trigger_time_repeated[-1].append(element)
                                   Acknowledged_by_repeated.append([])
                                   Acknowledged_by_repeated[-1].append(Acknowledged_by[i])
                              else:
                                   Lista_alarmas_repeated[-1].append(Lista_alarmas[i])
                                   trigger_time_repeated[-1].append(element)
                                   Acknowledged_by_repeated[-1].append(Acknowledged_by[i])
                         except:
                              Lista_alarmas_repeated[-1].append(Lista_alarmas[i])
                              trigger_time_repeated[-1].append(element)
                              Acknowledged_by_repeated[-1].append(Acknowledged_by[i])

                    else:  # ACA TODAVIA  Lista_alarmas_new , trigger_time_new , Acknowledged_by_new , CONTIENEN UN AL MENOS ELEMENTO REPETIDO
                         vistos.append(element) 
                         Lista_alarmas_new.append(Lista_alarmas[i])
                         trigger_time_new.append(element)
                         Acknowledged_by_new.append(Acknowledged_by[i])
                         # =========================================================================================================                    
                         #full_alarm = extraer_empresa(Lista_alarmas[i])  # ACA NO DEBI PONER ESTAS LINEAS DE CODIGO ERA TERMINANDO EL : FOR (for i,element in enumerate(new_list_trigger_time_repeated):)
                         #empresa, score = buscar_empresa(full_alarm)     # ACA NO DEBI PONER ESTAS LINEAS DE CODIGO ERA TERMINANDO EL : FOR (for i,element in enumerate(new_list_trigger_time_repeated):)
                         #if score >=60:                                  # ACA NO DEBI PONER ESTAS LINEAS DE CODIGO ERA TERMINANDO EL : FOR (for i,element in enumerate(new_list_trigger_time_repeated):)
                         #List_empresa_filter_alarm.append(empresa)       # ACA NO DEBI PONER ESTAS LINEAS DE CODIGO ERA TERMINANDO EL : FOR (for i,element in enumerate(new_list_trigger_time_repeated):)
               
                    #trigger_time.pop(i)
                    #Lista_alarmas.pop(i)
                    #Acknowledged_by.pop(i)
                    List_i_to_eliminate.append(i)
                    print("List_i_to_eliminate = " , List_i_to_eliminate)
                    print("Linea 1615")

     new_list_trigger_time_repeated=[]
     try:
          for element in trigger_time_repeated:
               new_list_trigger_time_repeated.append(element[0])
     except:
          pass
     
     if not trigger_time_repeated[0]:
          #print("PARA REVISAR CASUSITICA EXTRAÑA O Validar comando anterior : if not trigger_time_repeated[0]:")
          pass
     else:

          for i,element in enumerate(new_list_trigger_time_repeated):
               try:
                    indexsearched=trigger_time_new.index(element)                              
                    Lista_alarmas_repeated[i].append(Lista_alarmas_new.pop(indexsearched))    # ENTONCES ACA , "Lista_alarmas_new" se convertiria en la lista "Lista_alarmas_new" solo con elementos unicos
                    trigger_time_repeated[i].append(trigger_time_new.pop(indexsearched))      # ENTONCES ACA , "trigger_time_new" se convertiria en la lista "trigger_time_new" solo con elementos unicos
                    Acknowledged_by_repeated[i].append(Acknowledged_by_new.pop(indexsearched))# ENTONCES ACA , "Acknowledged_by_new" se convertiria en la lista "Acknowledged_by_new" solo con elementos unicos
                    # =========================================================================================================
                    #Lista_alarmas_repeated_cleaned[i].append(List_empresa_filter_alarm.pop(indexsearched))
                    # =========================================================================================================                         
               except:
                    pass

          for x in range(len(trigger_time_repeated)):

               ultimo = Lista_alarmas_repeated[x].pop()
               Lista_alarmas_repeated[x].insert(0, ultimo)
               ultimo = trigger_time_repeated[x].pop()
               trigger_time_repeated[x].insert(0, ultimo)
               ultimo = Acknowledged_by_repeated[x].pop()
               Acknowledged_by_repeated[x].insert(0, ultimo)

          wd.refresh()
          ############################## 22-08-2026   ##############################
          ############################## 22-08-2026   ##############################
          ##### DENTRO DE ESTE FOR DEBO BUSCAR LA DIRECCCION #######################
     print("========================================")
     print("Lista_alarmas_new =",Lista_alarmas_new)
     print("")
     print("trigger_time_new =",trigger_time_new)
     print("")
     print("Acknowledged_by_new =",Acknowledged_by_new)
     print("========================================")

     print("========================================")
     print("Lista_alarmas_repeated=",Lista_alarmas_repeated)
     print("")
     print("trigger_time_repeated=",trigger_time_repeated)
     print("")
     print("Acknowledged_by_repeated=",Acknowledged_by_repeated)
     print("========LO DE ARRIBA ES ANTES DE BUSCAR EN EL SOIT ========")
     """
     #NEW_Lista_alarmas_new = Lista_alarmas_new + Lista_alarmas_repeated # CHANGE 27-10-26
     #NEW_Lista_trigger_time_new = trigger_time_new + trigger_time_repeated
     #NEW_Lista_Acknowledged_by_new = Acknowledged_by_new + Acknowledged_by_repeated

     #print("NEW_Lista_alarmas_new = ",NEW_Lista_alarmas_new)
     #print("NEW_Lista_trigger_time_new = ",NEW_Lista_trigger_time_new)
     #print("NEW_Lista_Acknowledged_by_new = ",NEW_Lista_Acknowledged_by_new)
     #for i,element in enumerate(new_lista_Lista_alarmas_new): # CHANGE 27-10-26

     #Lista_alarmas_2 = NEW_Lista_alarmas_new.copy()
     #trigger_time_2 = NEW_Lista_trigger_time_new.copy()
     #Acknowledged_by_2 = NEW_Lista_Acknowledged_by_new.copy()
     """

     Lista_alarmas_2 = Lista_alarmas_to_send.copy()
     trigger_time_2 = trigger_time_to_send.copy()
     Acknowledged_by_2 = Acknowledged_by_to_send.copy()

     #Lista_alarmas_2 = Lista_alarmas.copy()
     #trigger_time_2 = trigger_time.copy()
     #cknowledged_by_2 = Acknowledged_by.copy()

     #if check_to_send==1:   # NUEVO CAMBIO NECESARIO PARA CONDICIONAR LA CREACION DE List_empresa_filter_alarm 
                            # Y CON ELLO SOLO ENVIAR CORREOS MAS ADELANTE CUANDO RELAMENTE SE DEBA ENVIAR
          
     for i,element in enumerate(Lista_alarmas_to_send): # CHANGE 27-10-26
     #for i,element in enumerate(Lista_alarmas): # CHANGE 27-10-26

     #for i,element in enumerate(NEW_Lista_alarmas_new): # CHANGE 06-11-26
     #for i,element in enumerate(Lista_alarmas_new):   # CHANGE 27-10-26
     #if i in List_i_to_send:
     
          List_OITs=extraer_OITs(element)
          List_oit_filter_alarm.append(List_OITs) # CAMBIO 14-07-26

          wd.switch_to.window(wd.window_handles[1])
          if len(List_OITs)>0:
                    
               for element_oit in List_OITs:

                    while True:
                         try:                     
                              wd.get('http://192.168.62.112/saf/soit/oit/ver/'+str(element_oit)+'/')
                              break
                         except:
                              wd.get("http://192.168.62.112/saf/soit/oit/ver/"+str(element_oit[0])+"/")
                              break

          
                    razon_social= wd.find_element(By.XPATH,'//*[@id="changelist"]/div/fieldset[2]/table/tbody/tr/td[2]').text
                    element_List_address=wd.find_element(By.XPATH,'//*[@id="changelist"]/div/fieldset[2]/table/tbody/tr/td[7]').text.split('\n')[0]                                 
                    List_address.append(element_List_address)

                    name_empresa_acotado = extraer_empresa(element)
                    List_All_name_empresa_acotado.append(name_empresa_acotado)
                    empresa, score = buscar_empresa(name_empresa_acotado)
                    List_All_empresa.append(empresa)
                    
                    if score >=70: 
                         List_empresa_filter_alarm.append(empresa)  # List_empresa_filter_alarm ,despues de la limpieza guarda el nombre de la empresa 
                         List_name_empresa_acotado_Mayor_80[i]=empresa
                         #List_oit_filter_alarm.append(element_oit) # CAMBIO 14-07-26
                         List_address_filter_alarm.append(element_List_address)  
                    else:
                         wd.switch_to.window(wd.window_handles[1])
                         name_empresa_acotado = extraer_empresa(razon_social)
                         empresa, score = buscar_empresa(name_empresa_acotado)
                         if score >=70:  # FORZOSAMENTE YA DEBE TOMAR UN VALOR  # CAMBIO 17-09-2026

                              List_empresa_filter_alarm.append(empresa)
                              List_name_empresa_acotado_Mayor_80[i]=empresa
                              #List_oit_filter_alarm.append(element_oit) # CAMBIO 14-07-26
                              List_address_filter_alarm.append(element_List_address) 
                         else:
                              List_empresa_filter_alarm.append('')  # CHANGE 27-10-26
                              List_address_filter_alarm.append(element_List_address)
                              wd.switch_to.window(wd.window_handles[3])   # CAMBIO 23-09-2026 REVERTIR DESPUES DE LA PRUEBA
                              List_name_empresa_acotado_Menor_80[i]=empresa
                              Find_Orange=element.lower().find("orange")
                              if Find_Orange !=-1:
                                   print('score = ',score)
                                   print('element = ' , element)
                                   print('name_empresa_acotado = ' , name_empresa_acotado)
                                   print('empresa = ' , empresa)

                              for x in range(1):                                 
                                   while True :
                                        #Este bucle me ayudo bastante hasta que carge el elemento WEB
                                        #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
                                        try:
                                             wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')          
                                             wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()
                                                                 
                                             break
                                        except : 
                                             pass
                                   
                                   while True :
                                        while True :
                                             try:
                                                  xpath_busqueda = (
                                                  "//input[@role='textbox' "
                                                  "and @aria-label='Buscar un chat o iniciar uno nuevo']"
                                                  )

                                                  campo_busqueda = WebDriverWait(wd, 20).until(
                                                  EC.element_to_be_clickable(
                                                       (By.XPATH, xpath_busqueda)
                                                  )
                                                  )

                                                  campo_busqueda.click()
                                                  campo_busqueda.send_keys("NOTIFICACION REMEDY HELIX")
                                             
                                                  time.sleep(2)
                                                  break
                                             except :
                                                  pass

                                        while True :
                                             
                                             try:
                                                  wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]')
                                                  wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]').click()
                                                  break
                                             except : 
                                                  pass
                                        Grupo_to_send="any"

                                        while True :

                                             try:   
                                                  Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/span').click() # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO SE ENVIA A UN GRUPO
                                                  Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/span').text    # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO SE ENVIA A UN GRUPO
                                                  #Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/div/div/span[1]').click() # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO ME ENVIO A MI MISMO
                                                  #Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/div/div/span[1]').text    # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO ME ENVIO A MI MISMO                                                                
                                                  break         
                                             except :
                                                  pass

                                        if Grupo_to_send !="NOTIFICACION REMEDY HELIX": # CAMBIO 20-09-26
                                        #if Grupo_to_send !="+51 980 768 752": # CAMBIO 20-09-26
                                             wd.refresh()

                                             while True :

                                                  try:
                                                       wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')
                                                       wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()
                                                       break
                                                  except : 
                                                       pass
                                        else:
                                             break

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*AVISO : NO SE ENCONTRO UNA RELACION ENTRE LA ALARMA EN ORION Y LA BASE CLIENTE*') # CAMBIO PARA TEST 03-09-26
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[2]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys('*Alarma:* ',str(element)) # CAMBIO PARA TEST 31-08-2026 
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys(Keys.ALT,Keys.ENTER)

                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys('Score = ',score) # CAMBIO PARA TEST 31-08-2026 
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER)

                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[5]').send_keys('name_empresa_acotado = ' , name_empresa_acotado) # CAMBIO PARA TEST 31-08-2026 
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[5]').send_keys(Keys.ALT,Keys.ENTER)

                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys('empresa = ' , empresa) # CAMBIO PARA TEST 31-08-2026 
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys('*Fecha y hora :* ',str(trigger_time_to_send[i])) # CAMBIO PARA TEST 31-08-2026 
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys('*Fecha y hora :* ',str(NEW_Lista_trigger_time_new[i])) # CAMBIO PARA TEST 31-08-2026 
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[5]').send_keys('*QUE MAT2 REVISE Y ENVIE CORREO PARA ESTA ALARMA*')

                                   while True:
                                        try:
                                             wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div/div/div[3]/div/button').click()    
                                             break
                                        except:
                                             print("Error al querer retroceder dentro de whatsapp")
                                             pass                          

                                   time.sleep(1)    
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ENTER)  # ENVIO_NO SE ENCONTRO UNA RELACION ENTRE LA ALARMA EN ORION Y LA BASE CLIENTE

                                   time.sleep(4) 
                              
                    wd.switch_to.window(wd.window_handles[0])
                    break
          else:
               List2_i_to_eliminate.append(i)


     for i,element in enumerate(List2_i_to_eliminate):   # " List2_i_to_eliminate "
          print("Rastreo_linea 1806")

          trigger_time_2.pop(element-i)
          Lista_alarmas_2.pop(element-i)
          Acknowledged_by_2.pop(element-i)
          List_oit_filter_alarm.pop(element-i)
     ##########################################################################
     #ntk=0
     ######################### 26-08-2026 ###############
     
     #wd.switch_to.window(wd.window_handles[2])  29-08-26 MALA POSICION DE wd.switch cuando no hay correos por enviar
     print("")
     
     print("List_empresa_filter_alarm (para enviar los correos)=",List_empresa_filter_alarm)
     print("")
     print("List_oit_filter_alarm (para enviar los correos)=",List_oit_filter_alarm)
     print("")
     print("List_address_filter_alarm (para enviar los correos)=",List_address_filter_alarm)
     print("========================================")
     print("Lista_alarmas_repeated=",Lista_alarmas_repeated)
     print("")
     print("trigger_time_repeated=",trigger_time_repeated)
     print("")
     print("Acknowledged_by_repeated=",Acknowledged_by_repeated)
     print("========================================")

     print("")
     print("ANTES DE ELIMINAR")
     print("========================================")
     print("Lista_alarmas =", Lista_alarmas)
     print("")
     print("trigger_time =", trigger_time)
     print("")
     print("Acknowledged_by =", Acknowledged_by)
     print("")

     #for element in List_i_to_eliminate:
     
     for i,element in enumerate(List_i_to_eliminate):
          print("Rastreo_linea 1793")
          ntk=0
          trigger_time.pop(element-i)
          Lista_alarmas.pop(element-i)
          Acknowledged_by.pop(element-i)
     
     print("")
     print("DESPUES DE ELIMINAR")
     print("========================================")
     print("Lista_alarmas =", Lista_alarmas)
     print("")
     print("trigger_time =", trigger_time)
     print("")
     print("Acknowledged_by =", Acknowledged_by)

     print("========================================")

     for i,element in enumerate(List_empresa_filter_alarm): # ENVIAR CORREOS  # CAMBIO 01-10-26 
               if element !='': # CHANGE 27-10-26

                    print("CLIENTE : ",element)  # CAMBIO 03-09-26      

                    wd.switch_to.window(wd.window_handles[2])  #29-08-26 BUENAS POSICION DE wd.switch cuando no hay / O HAY correos por enviar
                    time.sleep(1)
                    
                    #d.find_element(By.XPATH,'//*[@id="588"]/button[1]/span[2]').click()
                    while True :
                         try:
                              wd.find_element(By.XPATH,'//*[@id="588"]/button[1]/span[2]').click()                                               
                              break
                         except : 
                              pass

                    time.sleep(1)

                    while True :
                         try:
                              elemento = wd.switch_to.active_element                                             
                              break
                         except : 
                              pass
                    
                    #list_cell , list_mail , dic_contactos_telefonos = obtener_contactos(List_empresa_filter_alarm[i]) # CAMBIO 15-09-26
                    print("")
                    #print("LISTA DE CORREOS RELACIONADOS :" ,list_mail) # CAMBIO 03-09-26

                    client_1=element.lower().find("transportadora de gas del peru")
                    client_2=element.lower().find('tgp')
                    #find_starlink=Lista_alarmas_new[i].lower().find('starlink')
                    find_starlink=element.lower().find('starlink')

                    client_3=element.lower().find('ucv')
                    client_4=element.lower().find('universidad cesar vallejo')

                    client_5=element.lower().find('sencico')

                    list_mail=[]    #ESTO PARA USAR EL "list_mail" ANTERIOR GUARDADO
                    dic_contactos_telefonos=[] #ESTO PARA USAR EL "dic_contactos_telefonos" ANTERIOR GUARDADO

                    #if element=="TRANSPORTADORA DE GAS DEL PERU":
                    if client_1 != -1 or client_2 != -1:
                         if find_starlink != -1 :

                              if List_oit_filter_alarm[i][0] in ["403644","403645","403650","403654","403655","403657"]:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","aruiza@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                   dic_contactos_telefonos=["997543256","997543402","965714652"]
                              elif List_oit_filter_alarm[i][0] in ["403646","403648","403649","403651","403656"]:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","lsalazar@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                   dic_contactos_telefonos=["997543256","997543402","989029083"]
                              else:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                   dic_contactos_telefonos=["997543256","997543402"]
                         else:

                              if List_oit_filter_alarm[i][0] in ["403644","403645","403650","403654","403655","403657"]:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","aruiza@tgp.com.pe"]
                                   dic_contactos_telefonos=["997543256","997543402","965714652"]
                              elif List_oit_filter_alarm[i][0] in ["403646","403648","403649","403651","403656"]:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","lsalazar@tgp.com.pe"]
                                   dic_contactos_telefonos=["997543256","997543402","989029083"]
                              else:
                                   list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe"]
                                   dic_contactos_telefonos=["997543256","997543402"]


                    elif client_3 != -1 or client_4 != -1:
                         if List_oit_filter_alarm[i][0] in ["427258"]:
                              list_mail=["ecajahuanca@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649","971404022"]
                         elif List_oit_filter_alarm[i][0] in ["427250"]:
                              list_mail=["jhuamanc@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                              dic_contactos_telefonos=["975171829","971404022"]
                         elif List_oit_filter_alarm[i][0] in ["427246"]:
                              list_mail=["cquintana@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                              dic_contactos_telefonos=["979996664","971404022"]
                         elif List_oit_filter_alarm[i][0] in ["427244"]:
                              list_mail=["wreque@ucv.edu.pe","jblas@ucv.edu.pe"]
                              dic_contactos_telefonos=["943628772","943481026"]
                         elif List_oit_filter_alarm[i][0] in ["427256"]:
                              list_mail=["ecajahuanca@ucv.edu.pe","eaudante@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649","967795214"]
                         elif List_oit_filter_alarm[i][0] in ["471047"]:
                              list_mail=["ecajahuanca@ucv.edu.pe","nvarillas@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649","987557869"]
                         elif List_oit_filter_alarm[i][0] in ["427252"]:
                              list_mail=["ecajahuanca@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649","961400865"]
                         elif List_oit_filter_alarm[i][0] in ["427249"]:
                              list_mail=["llopezc@ucv.edu.pe","jpastor@ucv.edu.pe"]
                              dic_contactos_telefonos=["969521491","969170135"]
                         elif List_oit_filter_alarm[i][0] in ["427240"]:
                              list_mail=["jhuamanc@ucv.edu.pe","malvan@ucv.edu.pe"]
                              dic_contactos_telefonos=["975171829","925045731"]
                         elif List_oit_filter_alarm[i][0] in ["427242"]:
                              list_mail=["jhuamanc@ucv.edu.pe","malvan@ucv.edu.pe"]
                              dic_contactos_telefonos=["975171829","925045731"]
                         elif List_oit_filter_alarm[i][0] in ["427238"]:
                              list_mail=["jhuamanc@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                              dic_contactos_telefonos=["975171829","996599185"]
                         elif List_oit_filter_alarm[i][0] in ["374238"]:
                              list_mail=["cleonm@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                              dic_contactos_telefonos=["944233776","996599185"]                   
                         elif List_oit_filter_alarm[i][0] in ["427260"]:
                              list_mail=["jleyva@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                              dic_contactos_telefonos=["955307099","996599185"]
                         elif List_oit_filter_alarm[i][0] in ["440193"]:
                              list_mail=["jleyva@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                              dic_contactos_telefonos=["955307099","996599185"]              
                         elif List_oit_filter_alarm[i][0] in ["486044"]:
                              list_mail=["emolocho@ucv.edu.pe","ecajahuanca@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649"]
                         elif List_oit_filter_alarm[i][0] in ["469903","472505","483345"]:
                              list_mail=["ecajahuanca@ucv.edu.pe"]
                              dic_contactos_telefonos=["988893649"]

                    elif client_5 != -1 :
                         
                         if List_oit_filter_alarm[i][0] in ["411458","411459"]:    # APURIMAC 
                              list_mail=["czc_apurimac@sencico.gob.pe"]
                              dic_contactos_telefonos=[]
                         elif List_oit_filter_alarm[i][0] in ["411428","411429","411440","411441"]:  #AREQUIPA
                              list_mail=["bcalderon@sencico.gob.pe","slopezm@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411446","411447"]: # AYACUCHO
                              list_mail=["rzamora@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411448","411449"]: # CAJAMARCA
                              list_mail=["mzavaleta@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411424","411425"]: # CHICLAYO
                              list_mail=["radchiclayo@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411442","411443"]: # CHORRILLOS
                              list_mail=["rsantisteban@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411422","411423"]: # CUSCO
                              list_mail=["ics_cusco@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411444","411445"]: # HUANCAVELICA
                              list_mail=["khuallpa@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411434","411435"]: # HUANCAYO
                              list_mail=["craez@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411436","411437"]: # ICA
                              list_mail=["asolar@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411464","411465"]: # LORETO
                              list_mail=["iquitos01@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411432","411433"]: # OLIVOS
                              list_mail=["cmorales@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411456","411457"]: # MADRE DE DIOS
                              list_mail=["ycgmadrededios@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411460","411461"]: # MOQUEGUA
                              list_mail=["tacna04@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411454","411455"]: # MOYOBAMBA
                              list_mail=["jrios@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411430","411431"]: # PIURA
                              list_mail=["jchavez@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411452","411453"]: # PUCALLPA
                              list_mail=["rlopez@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411462","411463","411438","411439"]: # PUNO
                              list_mail=["atm_puno@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411420","411421"]: # SAN BORJA
                              list_mail=["mhuaroc@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["S411450","S411451"]: # TACNA
                              list_mail=["dgonzalo@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["441847","441850","411426","411427"]: # TRUJILLO
                              list_mail=["jpalacios@sencico.gob.pe","trujillo09@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                         elif List_oit_filter_alarm[i][0] in ["411420","411421"]: # LIMA
                              list_mail=["mhuaroc@sencico.gob.pe"]
                              dic_contactos_telefonos=[]

                    else:
                         list_cell , list_mail , dic_contactos_telefonos = obtener_contactos(element) # CAMBIO 15-09-26
                         print("LISTA DE CORREOS RELACIONADOS :" ,list_mail)
                              
                    try:       
                                                  # CAMBIO PARA TEST 31-08-2026                              
                         for correo in list_mail: # ANTES ERA SOLO ESTA FOR PERO SE AGREGO 2 "IFs" anteriores por TGP y UCV                                 
                              #print("Cliente afectado : ",element)  
                              while True :
                                   try:
                                        elemento.send_keys(correo,Keys.TAB)
                                        time.sleep(1)
                                        elemento.send_keys(Keys.TAB) 
                                        time.sleep(2)                                            
                                        break
                                   except : 
                                        pass
                    except:
                         pass
                    time.sleep(1)
                    #elemento.send_keys(Keys.TAB)

                    #time.sleep(1)
                    while True :
                         try:
                              elemento.send_keys(Keys.TAB)                                            
                              break
                         except : 
                              pass
                    time.sleep(2)

                    #print("TEST CRITICO DE DONDE SE UBICA EL CURSOR:")
                    elemento_02 = wd.switch_to.active_element

                    #print("Elemento con foco:")
                    #print(elemento_02.get_attribute("outerHTML"))

                    elemento_02.click()

                    while True :
                         try:
                              elemento_02.send_keys("mat2@entel.pe",Keys.TAB) # CAMBIO PARA TEST 31-08-2026   
                              #elemento_02.send_keys("elvis.ancasi.uni@gmail.com",Keys.TAB) # CAMBIO PARA TEST 31-08-2026   
                              time.sleep(1) 
                              elemento_02.send_keys(Keys.TAB)                                       
                              break
                         except : 
                              pass

                    time.sleep(2) 
          
                    elemento_02.click()
                    
                    while True :
                         try: 
                              elemento_02.send_keys("tac@entel.pe",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              #elemento_02.send_keys("elvizz2002@gmail.com",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              time.sleep(1)  
                              elemento_02.send_keys(Keys.TAB)                                  
                              break
                         except : 
                              pass
                    time.sleep(2)

                    elemento_02.click()
                    
                    while True :
                         try: 
                              elemento_02.send_keys("empresaspremiumfija@entel.pe",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              #elemento_02.send_keys("elvizz2002@gmail.com",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              time.sleep(1)  
                              elemento_02.send_keys(Keys.TAB)                                  
                              break
                         except : 
                              pass
                    time.sleep(2)

                    elemento_02.click()
                    
                    while True :
                         try: 
                              elemento_02.send_keys("sactecnico@entel.pe",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              #elemento_02.send_keys("elvizz2002@gmail.com",Keys.TAB)   # CAMBIO PARA TEST 31-08-2026 
                              time.sleep(1)  
                              elemento_02.send_keys(Keys.TAB)                                  
                              break
                         except : 
                              pass
                    time.sleep(2)
                    #elemento.send_keys(Keys.TAB)
                    while True :
                         try:
                              elemento_02.send_keys(Keys.TAB)                                    
                              break
                         except : 
                              pass
                    time.sleep(1)
                    #wd.find_element(By.XPATH,'//*[@id="0"]').send_keys("raul.arambulo@entel.pe")

                    while True :
                         try:
                              elemento_03 = wd.switch_to.active_element                                 
                              break
                         except : 
                              pass
                    time.sleep(1)
                    #elemento.send_keys("PRUEBA DE BOT PARA ENVIO DE CORREO")
                    while True :
                         try:
                              #elemento_03.send_keys("MONITOREO | STATUS: SERVICE DOWN | ",str(Lista_alarmas_new[i])  ,Keys.ENTER)    # CHANGE 27-10-26 
                              elemento_03.send_keys("MONITOREO | STATUS: SERVICE DOWN | ",str(Lista_alarmas_2[i])  ,Keys.ENTER)    # ASUNTO_CORREOS # CAMBIO 03-09-26 
                              #elemento_03.send_keys("PRUEBA DE CORREO | STATUS: SERVICE DOWN | ",str(Lista_alarmas_new[i])  ,Keys.ENTER)    # ASUNTO_CORREOS   # CAMBIO 03-09-26                                      
                              break
                         except : 
                              pass
                    time.sleep(1)

                    while True :
                         try:
                              elemento_04 = wd.switch_to.active_element                       
                              break
                         except : 
                              pass
                    time.sleep(1)

                    # new_lista_Lista_alarmas_new=Lista_alarmas_new + Lista_alarmas_repeated # CHANGE 27-10-26
                    Evento_individual=0
                    
                    if Lista_alarmas_2[i] in Lista_alarmas_new:  # CHANGE 27-10-26
                    
                         mensaje = "Estimados ", str(element),"\n\nSe observa enlace en DOWN, con la OIT ", str(List_oit_filter_alarm[i])," y dirección : ""\n\n",str(List_address_filter_alarm[i]),"\n\nFavor de confirmar que no tengan corte de energía en la zona, así como también revisar que los equipos estén correctamente conectados y energizados adjuntando fotos.\n\nPara poder seguir atendiendo su incidencia, por favor contactar a nuestra mesa SAC 080077500.\n\nSaludos cordiales/ Best regards"
                         Evento_individual=1
                    
                    else:
                         mensaje = "Estimados ", str(element),"\n\nSe observa enlace en DOWN, con la OIT ", str(List_oit_filter_alarm[i])," y dirección : ""\n\n",str(List_address_filter_alarm[i]),"\n\nEs posible que se encuentre dentro de un evento masivo.\n\nLo estaremos manteniendo informado por este medio.\n\nSaludos cordiales/ Best regards"
  
                    # mensaje = "Estimados ", str(element),"\n\nSe observa enlace en DOWN, con la OIT ", str(List_oit_filter_alarm[i])," y dirección : ""\n\n",str(List_address_filter_alarm[i]),"\n\nFavor de confirmar que no tengan corte de energía en la zona, así como también revisar que los equipos estén correctamente conectados y energizados adjuntando fotos.\n\nPara poder seguir atendiendo su incidencia, por favor contactar a nuestra mesa SAC 080077500.\n\nSaludos cordiales/ Best regards"


                    time.sleep(1)
                    while True :
                         try:
                              elemento_04.send_keys(mensaje)                     
                              break
                         except : 
                              pass
                    time.sleep(2)
                    #list_mail_alarma_sent.append(element)
                    while True :
                         try:
                              list_mail_alarma_sent.append(element)                   
                              break
                         except : 
                              pass

                    while True :
                         try:
                              #list_mail_trigger_time_sent.append(trigger_time_new[i])     # CAMBIO 27-10-26     
                              list_mail_trigger_time_sent.append(trigger_time_2[i])     # CAMBIO 27-10-26    
                              break
                         except : 
                              pass

                    #while True : # ROLLBACK CHANGE 27-10-26
                    try: # ROLLBACK
                         elemento_04.send_keys(Keys.CONTROL, Keys.ENTER)   # ENVIO_CORREOS  # ROLLBACK
                    except : # ROLLBACK
                         pass # ROLLBACK
                    # === ORION_DASHBOARD_CORREO ===
                    if Evento_individual==1:
                    
                         registrar_envio(
                              "correo_individual",
                              #asunto="MONITOREO | STATUS: SERVICE DOWN | " + str(Lista_alarmas_new[i]), # CHANGE 27-10-26
                              asunto="MONITOREO | STATUS: SERVICE DOWN | " + str(Lista_alarmas_2[i]),  # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                              detalle="Correo enviado",
                              referencia=str(element)   # relacionado al campo CLIENTE 
                         )   
                    else:

                         registrar_envio(
                              "correo_masiva",
                              #asunto="MONITOREO | STATUS: SERVICE DOWN | " + str(Lista_alarmas_new[i]), # CHANGE 27-10-26
                              asunto="MONITOREO | STATUS: SERVICE DOWN | " + str(Lista_alarmas_2[i]), # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                              detalle="Correo enviado",
                              referencia=str(element)   # relacionado al campo CLIENTE 
                         )    

               
                    #except : 
                    #     pass
                    time.sleep(1)    
               
# ======== ENVIO DE ALARMAS MASIVAS ========
     try:

          if not trigger_time_repeated[0]:
               pass
               #print("PARA REVISAR CASUSITICA EXTRAÑA_1, O Validar comando anterior : if not trigger_time_repeated[0]: ")
               #print("PARA REVISAR CASUSITICA EXTRAÑA_1, O Validar comando anterior : if not trigger_time_repeated[0]: ")
          else:
               wd.switch_to.window(wd.window_handles[3])
               #ListaGrupos=["GESTION N2 (TAC & MAT2)"]  # CHANGE 1-11-26 , THEN ROLLBACK
               ListaGrupos=["GESTION N2 (TAC & MAT2)","NOTIFICACION REMEDY HELIX"]  # CAMBIO 10-10-26

               String_lista_alarms=""
               #for x in range(1):         # CAMBIO 10-10-26
               for element in ListaGrupos: # CAMBIO 10-10-26

                    while True :
                         #Este bucle me ayudo bastante hasta que carge el elemento WEB
                         #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
                         try:
                              wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')          
                              wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()
                                                  
                              break
                         except : 
                              pass
                    
                    while True :
                         while True :
               
                              try:
                                   #elemento = wd.switch_to.active_element
                                   #elemento.click()

                                   #elemento.send_keys("GESTION N2 (TAC & MAT2)") # CAMBIO 21-09-26
                                   #elemento.send_keys("+51 980 768 752") # CAMBIO 17-09-26

                                   #wd.find_element(By.XPATH,'//*[@id="_r_d_"]').send_keys("+51 980 768 752") # CAMBIO 21-09-26

                                   xpath_busqueda = (
                                   "//input[@role='textbox' "
                                   "and @aria-label='Buscar un chat o iniciar uno nuevo']"
                                   )

                                   campo_busqueda = WebDriverWait(wd, 20).until(
                                   EC.element_to_be_clickable(
                                        (By.XPATH, xpath_busqueda)
                                   )
                                   )

                                   campo_busqueda.click()
                                   #campo_busqueda.send_keys("+51 980 768 752")

                                   campo_busqueda.send_keys(element)                    # CAMBIO 10-10-26
                                   #campo_busqueda.send_keys("GESTION N2 (TAC & MAT2)") # CAMBIO 10-10-26

                                   time.sleep(2)
                                   break
                              except :
                                   pass

                         while True :
                              
                              try:
                                   wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]')
                                   wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]').click()
                                   break
                              except : 
                                   pass
                         Grupo_to_send="any"

                         while True :

                              try:   

                                   Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/span').click() # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO SE ENVIA A UN GRUPO
                                   Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/span').text    # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO SE ENVIA A UN GRUPO

                                   #Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/div/div/span[1]').click() # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO ME ENVIO A MI MISMO
                                   #Grupo_to_send=wd.find_element(By.XPATH,'//*[@id="pane-side"]/div[1]/div/div/div[2]/div/div/div/div[2]/div[1]/div[1]/div/div/span[1]').text    # CAMBIO 23-09-26 ESTO FUNCIONA CUANDO ME ENVIO A MI MISMO
     
                                   break         
                              except :
                                   pass

                         if Grupo_to_send !=element:                    # CAMBIO 10-10-26
                         #if Grupo_to_send !="GESTION N2 (TAC & MAT2)": # CAMBIO 10-10-26
                              wd.refresh()

                              while True :

                                   try:
                                        wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')
                                        wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()
                                        break
                                   except : 
                                        pass
                         else:
                              break

                    #String_lista_alarms=""
                    
                    if len(list_trigger_time_sent)==0 :
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*MONITOREO DE SOLARWINS*') # CAMBIO PARA TEST 03-09-26
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*PRUEBA* MONITOREO DE SOLARWINS') # CAMBIO PARA TEST 03-09-26
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[2]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys("*#### LISTA DE ALARMAS MASIVAS ####*") # CAMBIO PARA TEST 31-08-2026 
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER)

                                   varhelp=5
                                   list_2_oit=[]
                                   for x in range(len(Lista_alarmas_repeated)):
               
                                        for y in range(len(Lista_alarmas_repeated[x])): # BEFORE : for y in range(ndt)
          
                                             #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(5+y)+']').send_keys('*',str(Lista_alarmas_repeated[x][y]),'*')
                                             wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(5+y)+']').send_keys(str(Lista_alarmas_repeated[x][y]))
                                             wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(5+y)+']').send_keys(Keys.ALT,Keys.ENTER)
                                             String_lista_alarms=String_lista_alarms+str(Lista_alarmas_repeated[x][y])+"\n"
                                             """
                                             list_2_oit=extraer_OITs(Lista_alarmas_repeated[x][y])

                                             for element_oit in list_2_oit:

                                                  while True:
                                                       try:                     
                                                            wd.get('http://192.168.62.112/saf/soit/oit/ver/'+str(element_oit)+'/')
                                                            for i,element in enumerate(List_empresa_filter_alarm)

                                                            break
                                                       except:
                                                            wd.get("http://192.168.62.112/saf/soit/oit/ver/"+str(element_oit[0])+"/")
                                                            break
                                             """       

                                             #mensaje = "Estimados ", str(element),"\n\nSe observa enlace en DOWN, con la OIT ", str(List_oit_filter_alarm[i])," y dirección : ""\n\n",str(List_address_filter_alarm[i]),"\n\nEs posible que se encuentre dentro de un evento masivo.\n\nLo estaremos manteniendo informado por este medio.\n\nSaludos cordiales/ Best regards"
                                             #### HOY 14-10-2024

                                        list_trigger_time_sent.append(trigger_time_repeated[x][0])

                                        varhelp=varhelp+len(Lista_alarmas_repeated[x])

                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp)+']').send_keys('*Fecha y hora :* ',str(trigger_time_repeated[x][0]))  #FALTA VERIFICAR ESTE PARTE
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp)+']').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp+1)+']').send_keys(Keys.ALT,Keys.ENTER)
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp+2)+']').send_keys(String_lista_alarms) # ROLLBACK 03-11-26
                    else:
                                                                                
                                   for i,element in enumerate(new_list_trigger_time_repeated):
                                        if element not in list_trigger_time_sent:
                                             id_to_next=i
                                             break
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*MONITOREO DE SOLARWINS*') # CAMBIO PARA TEST 03-09-26
                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*PRUEBA* MONITOREO DE SOLARWINS') # CAMBIO PARA TEST 07-09-26

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[2]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys("*#### LISTA DE ALARMAS MASIVAS ####*")
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER) 
                                   
                                   varhelp=5

                                   try: 
                                        for x in range(len(Lista_alarmas_repeated)-id_to_next):
                    
                                             for y in range(len(Lista_alarmas_repeated[x+id_to_next])): # BEFORE : for y in range(ndt)
               
                                                  wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(5+y)+']').send_keys('*',str(Lista_alarmas_repeated[x+id_to_next][y]),'*')
                                                  wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(5+y)+']').send_keys(Keys.ALT,Keys.ENTER)
                                                  String_lista_alarms=String_lista_alarms+str(Lista_alarmas_repeated[x][y])+"\n"
                                                  #### HOY 14-10-2024
                                             list_trigger_time_sent.append(trigger_time_repeated[x+id_to_next][0])
                                             varhelp=varhelp+len(Lista_alarmas_repeated[x+id_to_next])
                                             wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp)+']').send_keys('*Fecha y hora :* ',str(trigger_time_repeated[x+id_to_next][0]))  #FALTA VERIFICAR ESTE PARTE
                                             wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp)+']').send_keys(Keys.ALT,Keys.ENTER)
                                             wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p['+str(varhelp+1)+']').send_keys(Keys.ALT,Keys.ENTER)
                                   except:
                                        pass
                    while True:
                         try:
                              wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div/div/div[3]/div/button').click()    
                              break
                         except:
                              print("Error al querer retroceder dentro de whatsapp")
                              pass                          

                    time.sleep(1)    
                    wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ENTER)  # ENVIO_DE_MASIVAS
                    list_trigger_time_sent=[]
                    time.sleep(4) 
                    # === ORION_DASHBOARD_MASIVA ===
                    """
                    registrar_envio(
                         "masiva",
                         #asunto="LISTA DE ALARMAS MASIVAS",
                         asunto=String_lista_alarms, # CHANGE 03-11-26 # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                         detalle="Evento masivo enviado por WhatsApp",
                         referencia="masivo"  # relacionado al campo CLIENTE 
                    )
                    """
                    #time.sleep(2) # MUY NECESARIO PARA QUE NO MUESTRE ERRROR DE ENVIO EN WHTASAPP
                    print("LONGITUD DE Lista_alarmas = ", len(Lista_alarmas))
               

               registrar_envio(
                    "masiva",
                    #asunto="LISTA DE ALARMAS MASIVAS",
                    asunto=String_lista_alarms, # CHANGE 03-11-26 # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                    detalle="Evento masivo enviado por WhatsApp",
                    referencia="masivo"  # relacionado al campo CLIENTE 
               )
               #wd.switch_to.window(wd.window_handles[0])
     except:
          pass

     
     ###################################################
     ###################################################
          # ======== ENVIO DE ALARMAS INDIVIDUALES + NOTIFICACION DE ALARMAS QUE EL BOT NO HA DETERMINADO SU CLIENTE ========
     # CAMBIO 01-10-26
     
     try:
          if not List_empresa_filter_alarm[0]:
               #print("PARA REVISAR CASUSITICA EXTRAÑA_2, O Validar comando anterior : if not List_empresa_filter_alarm[0]:")
               wd.switch_to.window(wd.window_handles[0])
          else:
               wd.switch_to.window(wd.window_handles[3])

               wd.refresh()

               while True :                         
                         #Este bucle me ayudo bastante hasta que carge el elemento WEB
                         #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
                         try:
                              wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')          
                              wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()                                             
                              break
                         except : 
                              pass
               print("")
               #for x in range(1):
               for i,element in enumerate(List_empresa_filter_alarm):
                    
                    if element !='': # CHANGE 27-10-26

                         ########### CAMBIO 19-05-26 ##################### (down)
                         ########### CAMBIO 19-05-26 ##################### (down)

                         client_1=element.lower().find("transportadora de gas del peru")
                         client_2=element.lower().find('tgp')
                         find_starlink=element.lower().find('starlink')

                         client_3=element.lower().find('ucv')
                         client_4=element.lower().find('universidad cesar vallejo')

                         client_5=element.lower().find('sencico')

                         list_mail=[]    #ESTO PARA USAR EL "list_mail" ANTERIOR GUARDADO
                         dic_contactos_telefonos=[] #ESTO PARA USAR EL "dic_contactos_telefonos" ANTERIOR GUARDADO

                         #if element=="TRANSPORTADORA DE GAS DEL PERU":
                         if client_1 != -1 or client_2 != -1:
                              if find_starlink != -1 :

                                   if List_oit_filter_alarm[i][0] in ["403644","403645","403650","403654","403655","403657"]:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","aruiza@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                        dic_contactos_telefonos=["997543256","997543402","965714652"]
                                   elif List_oit_filter_alarm[i][0] in ["403646","403648","403649","403651","403656"]:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","lsalazar@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                        dic_contactos_telefonos=["997543256","997543402","989029083"]
                                   else:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","atencionalcliente@axessnet.com","cesar.castro@hispasat.com","cristian.solarte@hispasat.com"]
                                        dic_contactos_telefonos=["997543256","997543402"]

                              else:

                                   if List_oit_filter_alarm[i][0] in ["403644","403645","403650","403654","403655","403657"]:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","aruiza@tgp.com.pe"]
                                        dic_contactos_telefonos=["997543256","997543402","965714652"]
                                   elif List_oit_filter_alarm[i][0] in ["403646","403648","403649","403651","403656"]:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe","lsalazar@tgp.com.pe"]
                                        dic_contactos_telefonos=["997543256","997543402","989029083"]
                                   else:
                                        list_mail=["dlira@tgp.com.pe","npaz@tgp.com.pe","jtarazona@tgp.com.pe","NOC@tgp.com.pe"]
                                        dic_contactos_telefonos=["997543256","997543402"]

                         elif client_3 != -1 or client_4 != -1:
                              if List_oit_filter_alarm[i][0] in ["427258"]:
                                   list_mail=["ecajahuanca@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649","971404022"]
                              elif List_oit_filter_alarm[i][0] in ["427250"]:
                                   list_mail=["jhuamanc@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                                   dic_contactos_telefonos=["975171829","971404022"]
                              elif List_oit_filter_alarm[i][0] in ["427246"]:
                                   list_mail=["cquintana@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                                   dic_contactos_telefonos=["979996664","971404022"]
                              elif List_oit_filter_alarm[i][0] in ["427244"]:
                                   list_mail=["wreque@ucv.edu.pe","jblas@ucv.edu.pe"]
                                   dic_contactos_telefonos=["943628772","943481026"]
                              elif List_oit_filter_alarm[i][0] in ["427256"]:
                                   list_mail=["ecajahuanca@ucv.edu.pe","eaudante@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649","967795214"]
                              elif List_oit_filter_alarm[i][0] in ["471047"]:
                                   list_mail=["ecajahuanca@ucv.edu.pe","nvarillas@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649","987557869"]
                              elif List_oit_filter_alarm[i][0] in ["427252"]:
                                   list_mail=["ecajahuanca@ucv.edu.pe","jyesquen@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649","961400865"]
                              elif List_oit_filter_alarm[i][0] in ["427249"]:
                                   list_mail=["llopezc@ucv.edu.pe","jpastor@ucv.edu.pe"]
                                   dic_contactos_telefonos=["969521491","969170135"]
                              elif List_oit_filter_alarm[i][0] in ["427240"]:
                                   list_mail=["jhuamanc@ucv.edu.pe","malvan@ucv.edu.pe"]
                                   dic_contactos_telefonos=["975171829","925045731"]
                              elif List_oit_filter_alarm[i][0] in ["427242"]:
                                   list_mail=["jhuamanc@ucv.edu.pe","malvan@ucv.edu.pe"]
                                   dic_contactos_telefonos=["975171829","925045731"]
                              elif List_oit_filter_alarm[i][0] in ["427238"]:
                                   list_mail=["jhuamanc@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                                   dic_contactos_telefonos=["975171829","996599185"]
                              elif List_oit_filter_alarm[i][0] in ["374238"]:
                                   list_mail=["cleonm@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                                   dic_contactos_telefonos=["944233776","996599185"]                   
                              elif List_oit_filter_alarm[i][0] in ["427260"]:
                                   list_mail=["jleyva@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                                   dic_contactos_telefonos=["955307099","996599185"]
                              elif List_oit_filter_alarm[i][0] in ["440193"]:
                                   list_mail=["jleyva@ucv.edu.pe","jvergaray@ucv.edu.pe"]
                                   dic_contactos_telefonos=["955307099","996599185"]              
                              elif List_oit_filter_alarm[i][0] in ["486044"]:
                                   list_mail=["emolocho@ucv.edu.pe","ecajahuanca@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649"]
                              elif List_oit_filter_alarm[i][0] in ["469903","472505","483345"]:
                                   list_mail=["ecajahuanca@ucv.edu.pe"]
                                   dic_contactos_telefonos=["988893649"]

                         elif client_5 != -1 :
                                   
                                   if List_oit_filter_alarm[i][0] in ["411458","411459"]:    # APURIMAC 
                                        list_mail=["czc_apurimac@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]
                                   elif List_oit_filter_alarm[i][0] in ["411428","411429","411440","411441"]:  #AREQUIPA
                                        list_mail=["bcalderon@sencico.gob.pe","slopezm@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411446","411447"]: # AYACUCHO
                                        list_mail=["rzamora@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411448","411449"]: # CAJAMARCA
                                        list_mail=["mzavaleta@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411424","411425"]: # CHICLAYO
                                        list_mail=["radchiclayo@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411442","411443"]: # CHORRILLOS
                                        list_mail=["rsantisteban@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411422","411423"]: # CUSCO
                                        list_mail=["ics_cusco@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411444","411445"]: # HUANCAVELICA
                                        list_mail=["khuallpa@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411434","411435"]: # HUANCAYO
                                        list_mail=["craez@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411436","411437"]: # ICA
                                        list_mail=["asolar@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411464","411465"]: # LORETO
                                        list_mail=["iquitos01@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411432","411433"]: # OLIVOS
                                        list_mail=["cmorales@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411456","411457"]: # MADRE DE DIOS
                                        list_mail=["ycgmadrededios@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411460","411461"]: # MOQUEGUA
                                        list_mail=["tacna04@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411454","411455"]: # MOYOBAMBA
                                        list_mail=["jrios@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411430","411431"]: # PIURA
                                        list_mail=["jchavez@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411452","411453"]: # PUCALLPA
                                        list_mail=["rlopez@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411462","411463","411438","411439"]: # PUNO
                                        list_mail=["atm_puno@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411420","411421"]: # SAN BORJA
                                        list_mail=["mhuaroc@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["S411450","S411451"]: # TACNA
                                        list_mail=["dgonzalo@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["441847","441850","411426","411427"]: # TRUJILLO
                                        list_mail=["jpalacios@sencico.gob.pe","trujillo09@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                                   elif List_oit_filter_alarm[i][0] in ["411420","411421"]: # LIMA
                                        list_mail=["mhuaroc@sencico.gob.pe"]
                                        dic_contactos_telefonos=[]

                         else:

                              list_cell , list_mail , dic_contactos_telefonos = obtener_contactos(List_empresa_filter_alarm[i]) # CAMBIO 15-09-26
                              #list_cell , list_mail , dic_contactos_telefonos= obtener_contactos(element)

                              print("LISTA DE CORREOS RELACIONADOS :" ,list_mail)

                         ########### CAMBIO 19-05-26 ##################### (up)
                         ########### CAMBIO 19-05-26 ##################### (up)


                         #list_cell , list_mail , dic_contactos_telefonos= obtener_contactos(element) # CAMBIO 19-09-26
                         #print("LISTA DE CONTACTOS RELACIONADOS : " ,dic_contactos_telefonos) # CAMBIO 19-09-26
                         
                         #dic_contactos_telefonos=["+51 902 786 884","+51 997 326 903","+51 969 726 874"] # SOLO PRUEBA , LUEGO DESHABILITAR 02-10-26
                         print("contactos_telefonos: ", dic_contactos_telefonos)
                         for telefono in dic_contactos_telefonos:  # CAMBIO 20-09-2026
                              
                              #print("TRASTEO DE SALTO_0000")
                           #for x in range(1): # CAMBIO 20-09-2026
                    
                              while True :
                                   #Este bucle me ayudo bastante hasta que carge el elemento WEB
                                   #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
                                   try: 
                                        #print("TRASTEO DE SALTO_0001")
                                        wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]')    
                                        #print("TRASTEO DE SALTO_0002")      
                                        wd.find_element(By.XPATH,'//*[@id="side"]/div[1]/div/div/div/div/div[1]').click()
                                        #print("TRASTEO DE SALTO_0003")
                                                            
                                        break
                                   except :
                                        #print("TRASTEO DE SALTO_0004")
                                        pass
                                        #print("TRASTEO DE SALTO_0005")
                              
                              while True :

                                   try:
                                        wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[3]/header/header/div/span/div/div[2]/span/div/button/div/div/div[1]/span').click()
                                        #wd.find_element(By.XPATH,'//*[@id="_r_9a_"]').send_keys(telefono)
                                        ######################### 26-08-2026 ###############
                                        ######################### 26-08-2026 ###############
                                        buscador = WebDriverWait(wd, 7).until(
                                             EC.element_to_be_clickable((
                                                  By.XPATH,
                                                  "//input[@role='textbox' and @aria-label='Buscar nombre, núm. o @nombre de usuario']"
                                             ))
                                             )

                                        buscador.click()
                                        buscador.send_keys(telefono) # CAMBIO PARA TEST 20-09-2026 
                                        time.sleep(4)
                                        #buscador.send_keys("980768752") # CAMBIO PARA TEST 20-09-2026 

                                        ####################################################

                                        header_whastapp='any_value'
                                        var_contacto_no_tiene_whatsapp=0

                                   
                                        while header_whastapp !=telefono and var_contacto_no_tiene_whatsapp !=1 :
                                             #print("RASTREO DE SALTO_000000")
                                        
                                             while True :
                                                  #Este bucle me ayudo bastante hasta que carge el elemento WEB
                                                  #En la siguiente linea de comando , es un caso particular : a pesar que no terminaba de cargar el elemento WEB , no arrojaba ERROR de "ELEMENT NO FOUND FOR XPATH"
                                                  try:  # EN CASO: NO TENGO GUARDADO Y NO TIENE FOTO (SOLO NUMERO DESCONOCIDO)
                                                       #print("RASTREO DE SALTO_00")
                                                        # OLD //*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div[3]/div[2]/div[2]/div[2]/div/div/span'
                                                                 
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div/div/span')              
                                                       #print("RASTREO DE SALTO_0000")
                                                       telefono=wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div/div/span').text              
                                                       #print("RASTREO DE SALTO_01")
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div/div/span').click() 
                                                       #print("RASTREO DE SALTO_02")  
                                                                                                                        
                                                       break
                                                  except :
                                                       #print("RASTREO DE SALTO_03")
                                                       pass
                                                       #print("RASTREO DE SALTO_04")
                                                  try: # EN CASO: NO TENGO GUARDADO PERO TIENE CON FOTO o "@"+nic_name:
                                                       #print("RASTREO DE SALTO_05")

                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[1]/div/span')
                                                       #print("RASTREO DE SALTO_06")
                                                       telefono=wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[1]/div/span').text
                                                       #print("RASTREO DE SALTO_0606")
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[1]/div/span').click()                                                       
                                                       #print("RASTREO DE SALTO_07") 
                                                                                                                                            
                                                       break
                                                  except : 
                                                       #print("RASTREO DE SALTO_08")
                                                       pass
                                                       #print("RASTREO DE SALTO_09")
                                                  try: # EN CASO: NO TENGO GUARDADO PERO TIENE CON FOTO o "@"+nic_name ( pero justo el que esta debajo del numero o debajo de "@" ("Coincide con este número."))
                                                       #print("RASTREO DE SALTO_10")
                                                                           
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[2]/div/span')
                                                       #print("RASTREO DE SALTO_11")
                                                       telefono=wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[2]/div/span').text
                                                       #print("RASTREO DE SALTO_1111")
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div[2]/div[2]/div[2]/div/span').click()     
                                                       #print("RASTREO DE SALTO_12")   
                                                                                                                        
                                                       break
                                                  except : 
                                                       #print("RASTREO DE SALTO_13")
                                                       pass
                                                       #print("RASTREO DE SALTO_14")
                                                  try: # EN CASO EL CONTACTO SEA UN NUMERO QUE SI TENGO GUARDADO
                                                       #print("RASTREO DE SALTO_15")
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div/div/div/div/div/div[2]/div/div[1]/div/span/div/div/span')
                                                       #print("RASTREO DE SALTO_16")
                                                       telefono=wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div/div/div/div/div/div[2]/div/div[1]/div/span/div/div/span').text
                            
                                                       #print("RASTREO DE SALTO_1616")
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div/div/div/div/div/div[2]/div/div[1]/div/span/div/div/span').click()   
                                                       #print("RASTREO DE SALTO_17")  
                                                                 
                                                       break
                                                  except : 
                                                       #print("RASTREO DE SALTO_18")
                                                       pass
                                                       #print("RASTREO DE SALTO_19")
                                                  try: # EN CASO EL CONTACTO NO TIENE WHASTAPP:
                                                       #print("RASTREO DE SALTO_20")
                                                       #wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div[3]/div[2]/div/div/div/h2/span') # HASTA EL 28-10-26 QUE ACTUALIZO WHATSAPP
                                                       wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div/div[1]/div/div[3]/div[2]/div/div/div/h2/span')
                                                       #wd.find_element(By.XPATH,'//*[@id="app"]/div/div/div[3]/div/div[2]/div[1]/div/span/div/span/div/div/div[3]/div[2]/div/div/div/h2/span').click() # INNCESARIO PORQUE EL CONTACTO NO TIENE WHATSAPP
                                                       var_contacto_no_tiene_whatsapp=1
                                                       wd.refresh()

                                                       #print("RASTREO DE SALTO_21")                                                                                                 
                                                       break
                                                  except : 
                                                       #print("RASTREO DE SALTO_22")
                                                       pass
                                                       #print("RASTREO DE SALTO_23")
                                                  
                                             time.sleep(2)
                                             try:
                                                  #print("RASTREO DE SALTO_24")
                                                  header_whastapp=wd.find_element(By.XPATH,'//*[@id="main"]/header/div[1]/div[2]/div/div/div/div/div/span').text

                                                                           
                                                  #print("RASTREO DE SALTO_25")
                                             except:
                                                  #print("RASTREO DE SALTO_26")
                                                  pass
                                                  #print("RASTREO DE SALTO_27")

                                        
                                        #time.sleep(2)
                                        #print("TRASTEO DE SALTO_24")
                                        #print("RASTREO DE SALTO_28")
                                        break
                                   
                                   except :
                                        #print("RASTREO DE SALTO_29")
                                        pass
                                        #print("RASTREO DE SALTO_30")

                              try:

                                   #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('*PRUEBA* NOTIFICACION DE CAIDA DE SERVICIO') # CAMBIO 03-09-06
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys('NOTIFICACION DE CAIDA DE SERVICIO') # CAMBIO 03-09-06
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[2]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys("Estimado ",str(element))
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[3]').send_keys(Keys.ALT,Keys.ENTER)
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[4]').send_keys(Keys.ALT,Keys.ENTER)

                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[5]').send_keys('Se observa enlace en DOWN, con la OIT ', str(List_oit_filter_alarm[i])," y dirección : ",str(List_address_filter_alarm[i]))
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[5]').send_keys(Keys.ALT,Keys.ENTER)

                                   if Lista_alarmas_2[i] in Lista_alarmas_new:  # CHANGE 27-10-26

                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[6]').send_keys('Favor de confirmar que no tengan corte de energía en la zona, así como también revisar que los equipos estén correctamente conectados y energizados adjuntando fotos.')  #FALTA VERIFICAR ESTE PARTE
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[6]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[7]').send_keys("Para poder seguir atendiendo su incidencia, por favor contactar a nuestra mesa SAC 080077500.")
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[7]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[8]').send_keys('Correo :sactecnico@entel.pe')
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[8]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[9]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[10]').send_keys('Quedamos atentos a sus comentarios')
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[10]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[11]').send_keys('Saludos cordiales')

                                   else:
                                   
                                        #mensaje = "Estimados ", str(element),"\n\nSe observa enlace en DOWN, con la OIT ", str(List_oit_filter_alarm[i])," y dirección : ""\n\n",str(List_address_filter_alarm[i]),"\n\nEs posible que se encuentre dentro de un evento masivo.\n\nLo estaremos manteniendo informado por este medio.\n\nSaludos cordiales/ Best regards"

                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[6]').send_keys('Es posible que se encuentre dentro de un evento masivo')  #FALTA VERIFICAR ESTE PARTE
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[6]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[7]').send_keys("Lo estaremos manteniendo informado por este medio")
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[7]').send_keys(Keys.ALT,Keys.ENTER)
                                        wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[8]').send_keys('Saludos cordiales') # CHANGE 27-10-26

                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[8]').send_keys('Correo :sactecnico@entel.pe')
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[8]').send_keys(Keys.ALT,Keys.ENTER)
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[9]').send_keys(Keys.ALT,Keys.ENTER)
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[10]').send_keys('Quedamos atentos a sus comentarios')
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[10]').send_keys(Keys.ALT,Keys.ENTER)
                                        #wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div/p[11]').send_keys('Saludos cordiales')
               
                                   time.sleep(1)    
                                   wd.find_element(By.XPATH,'//*[@id="main"]/footer/div[1]/div/span/div/div/div/div[3]/div[1]/p').send_keys(Keys.ENTER) # ENVIO_WHASTAPP
                                   # === ORION_DASHBOARD_WHATSAPP ===
                                   registrar_envio(
                                        "whatsapp",
                                        asunto=telefono, # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                                        #asunto="NOTIFICACION DE CAIDA DE SERVICIO", # RELACIONARLO A NUEVO CAMPO ASUNTO | ALARMAS | CONTACTO
                                        detalle="Mensaje WhatsApp enviado", # CHANGE 03-11-26
                                        #detalle=telefono,
                                        referencia=str(element) # relacionado al campo CLIENTE 
                                   )

                                   time.sleep(3) # MUY NECESARIO PARA QUE NO MUESTRE ERRROR DE ENVIO EN WHTASAPP

                              except:
                                   #wd.refresh() # CAMBIO 04-09-26
                                   #print("TRASTEO DE SALTO_29")
                                   wd.refresh() # CAMBIO 04-09-26
                                   #print("TRASTEO DE SALTO_30")
                                   #time.sleep(2)
                                   pass
        
                              #print("LONGITUD DE Lista_alarmas = ", len(Lista_alarmas))
                              #break
                         # linea 2895
                          
               #print("TRASTEO DE SALTO_31")
               wd.switch_to.window(wd.window_handles[0])    
     except:
          #print("TRASTEO DE SALTO_32")
          wd.switch_to.window(wd.window_handles[0]) #CAMBIO 01-09-2026 REVISAR BIEN ESTE SWITCH
          pass # CAMBIO 01-10-26

     

                         
                               
  

