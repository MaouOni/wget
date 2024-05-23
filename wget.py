#!/usr/bin/python3
import re
import requests
import lxml
import threading
from concurrent.futures import ThreadPoolExecutor
from os import chdir, makedirs
from os.path import basename, realpath, isfile, isdir, splitext
from urllib.parse import urlsplit, urljoin
from urllib.request import urlopen, urlretrieve

from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; CustomBot/1.0; +http://example.com/bot)'}
visited = set()
lock = threading.Lock()

RED = '\033[91m'
GREEN = '\022[92m'
ENDC = '\033[0m'

def get_tipo_contenido(sitio):
    try:
        r = requests.get(sitio, headers=HEADERS)
        return r.headers['content-type']
    except Exception as e:
        print(f"\t{RED}[ERROR/Contenido]{ENDC}\tImposible descargar el enlace ({sitio})")
        return "unknown"

def get_codificacion(sitio):
    try:
        return requests.get(sitio, headers=HEADERS).encoding
    except Exception as e:
        print(f"\t{RED}[ERROR/Codificación]{ENDC}\tNo se pudo obtener la codificación ({e})")

def descargar_sitio(sitio, nombre):
    try:
        urlab = urlopen(sitio).url
        realp = realpath(__file__).replace(basename(realpath(__file__)), "")
        chdir(realp)
        uri = obtener_uri_real(sitio)
        novositio = sitio.replace(uri, "")

        makedirs(novositio, exist_ok=True)
        chdir(novositio)
        urlretrieve(urlab, nombre + ".html")
        chdir(realp)
        return f"{nombre}.html [OK]"
    except Exception as e:
        print(f"\t{RED}[ERROR/HTML]{ENDC}\t\tNo se pudo descargar ({e})")
        return False

def descargar_archivo(sitio):
    try:
        urlab = urlopen(sitio).url
        realp = realpath(__file__).replace(basename(realpath(__file__)), "")
        chdir(realp)
        uri = obtener_uri_real(sitio)
        nombre_archivo = basename(urlab)
        novositio = sitio.replace(uri, "").replace(nombre_archivo, "")

        makedirs(novositio, exist_ok=True)
        chdir(novositio)
        urlretrieve(urlab, nombre_archivo)
        chdir(realp)
        return f"{nombre_archivo}[OK]"
    except Exception as e:
        print(f"\t{RED}[ERROR/Descarga]{ENDC}\tNo se pudo descargar ({e})")
        return False

def validar_url(sitio):
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, sitio) is not None

def abrir_sitio(sitio):
    if sitio.startswith("ftp://"):
        print(f"\t{RED}[ERROR/Sitio]{ENDC}\t\tFTP no soportado")
        return None
    try:
        website = urlopen(sitio)
        return website.read().decode(get_codificacion(sitio))
    except Exception as e:
        print(f"\t{RED}[ERROR/Apertura]{ENDC}\tSitio no leído ({e})")
        return None

def obtener_uri_real(sitio):
    return "{0.scheme}://{0.netloc}/".format(urlsplit(sitio))

def fix_enlace(sitios):
    return [item.replace('//', '') if item.startswith("//") else item for item in sitios if item not in ["#", "https://", "ftp://", "http://", "/"] and not item.startswith("{{")]

def concat_prefijo(sitios):
    return ["https://" + item if not item.startswith("http") and not item.startswith("data:") else item for item in sitios]

def fix_subenlace(sitios, uri):
    return [(uri + item[1:]) if item.startswith("/") else item for item in sitios]

def concat_sitio_padre(listaSitios, uri):
    return [item for item in listaSitios if item.startswith(uri)]

def get_nombre_pagina(sopa):
    if sopa.title and sopa.title.string:
        return sopa.title.string.strip()
    else:
        return "sin_titulo"

def fix_diagonal(lista_sitios, uri):
    return [uri + item if not validar_url(item) else item for item in lista_sitios]

def sanitize_filename(filename):
    return re.sub(r'[/*?:"<>|]', "_", filename)

def manejar_url(links, base, depth, max_depth):
    if depth > max_depth:
        return
    newArreglo = [link for link in links if len(link) > len(base) and '?' not in link]
    for link in newArreglo:
        threading.Thread(target=wpyget, args=(link, depth + 1, max_depth)).start()

def wpyget(sitio, depth, max_depth):
    with lock:
        if sitio in visited or depth > max_depth:
            return
        visited.add(sitio)

    if validar_url(sitio):
        html = abrir_sitio(sitio)
        if html is None:
            print(f"\t[DESCARGANDO]\t\t{descargar_archivo(sitio)}")
            return
        uri = obtener_uri_real(sitio)
        try:
            sopa = BeautifulSoup(html, "lxml")
        except Exception as e:
            print(f"\t{RED}[ERROR/Lectura]{ENDC}\tError al leer la página. Use lxml en la línea 55: {e}")
            sopa = BeautifulSoup(html, features="html.parser")

        tituloPagina = re.sub('\W+', '', get_nombre_pagina(sopa)).replace(" ", "")
        tituloPagina = sanitize_filename(tituloPagina)
        print(f"\t[NAME]\t\t\t{tituloPagina}")

        try:
            makedirs(tituloPagina, exist_ok=True)
            chdir(tituloPagina)
        except Exception as e:
            print(f"\t{RED}[ERROR/Directorios]{ENDC}\tNo se pudo crear o cambiar al directorio ({e})")
            return

        print(f"\t[HTML/DESCARGANDO]\t{descargar_sitio(sitio, tituloPagina)}")

        links = [a.get('href') for a in sopa.find_all('a', href=True)]
        links_recursos = [a['src'] for a in sopa.find_all(src=True)]
        recursos = set(concat_sitio_padre(fix_subenlace(fix_enlace(re.findall('src="([^"]+)"', str(html))), uri), uri) + concat_sitio_padre(fix_subenlace(fix_enlace(links_recursos), uri), uri))
        linksexternos = concat_sitio_padre(fix_diagonal(fix_subenlace(fix_enlace(links), uri), sitio), uri)

        arrayImgFiles = ['tif', 'tiff', 'bmp', 'jpg', 'jpeg', 'gif', 'png']

        for recurso in recursos:
            print(f"\t[SRC/DESCARGANDO]\t{recurso} {descargar_archivo(recurso)}")

        url_finales = []
        for i in linksexternos:
            if "application" in get_tipo_contenido(i) or any(ext in i for ext in arrayImgFiles):
                print(f"\t[LINK/DESCARGANDO]\t{i} {descargar_archivo(i)}")
            else:
                print(f"\t[LINK]\t\t\t{i}")
                url_finales.append(i)

        print(f"\t[URI]\t\t\t{uri}")
        manejar_url(url_finales, sitio, depth, max_depth)

if __name__ == "__main__":
    try:
        executor = ThreadPoolExecutor(max_workers=5)
        pagina = "http://148.204.58.221/axel/aplicaciones/"
        max_depth = 5
        wpyget(pagina, 0, max_depth)
    except Exception as e:
        print(f"{RED}[ERROR/MAIN]{ENDC}\t{e}")
