"""Genera las tablas de traducción ruso -> español del dataset Predict Future Sales.

Salidas (carpeta references/, sí se versionan en git):
    - traduccion_tiendas.csv     : shop_id, shop_name_ru, shop_name_es      (traducción manual)
    - traduccion_categorias.csv  : item_category_id, item_category_name_ru, item_category_name_es (traducción manual)
    - traduccion_items.csv       : item_id, item_name_ru, item_name_es      (traducción automática + correcciones manuales)

Los nombres de productos (22,170) se traducen automáticamente con Google Translate. Los nombres sin caracteres
cirílicos (p. ej. títulos en inglés) se conservan tal cual. El proceso guarda su avance y puede reanudarse.

Uso (desde la raíz del proyecto, con los CSV de Kaggle en data/raw/):
    python -m future_sales.traducciones
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]  # Raíz del proyecto
DATA_RAW = RAIZ / "data" / "raw"  # Datos originales de Kaggle
REFERENCES = RAIZ / "references"  # Carpeta de salida de las traducciones

# Abreviaturas usadas en los nombres de tiendas:
#   CC  = Centro Comercial (ТЦ / ТК)
#   CCE = Centro Comercial y de Entretenimiento (ТРЦ / ТРК / МТРЦ)
TIENDAS_ES = {
    0: '!Yakutsk Ordzhonikidze, 56 (franquicia)',
    1: '!Yakutsk CC "Tsentralny" (franquicia)',
    2: 'Adygea CC "Mega"',
    3: 'Balashikha CCE "Oktyabr-Kinomir"',
    4: 'Volzhski CC "Volga Mall"',
    5: 'Vologda CCE "Marmelad"',
    6: 'Vorónezh (Plekhanovskaya, 13)',
    7: 'Vorónezh CCE "Maksimir"',
    8: 'Vorónezh CCE City-Park "Grad"',
    9: 'Venta itinerante',
    10: 'Zhukovski calle Chkalova 39m?',
    11: 'Zhukovski calle Chkalova 39m²',
    12: 'Tienda en línea ChS',
    13: 'Kazán CC "Bekhetle"',
    14: 'Kazán CC "ParkHouse" II',
    15: 'Kaluga CCE "XXI Vek"',
    16: 'Kolomna CC "Rio"',
    17: 'Krasnoyarsk CC "Vzletka Plaza"',
    18: 'Krasnoyarsk CC "Iyun"',
    19: 'Kursk CC "Pushkinsky"',
    20: 'Moscú "Liquidación"',
    21: 'Moscú CCE multifuncional "Afi Mall"',
    22: 'Moscú Tienda C21',
    23: 'Moscú CC "Budenovsky" (pabellón A2)',
    24: 'Moscú CC "Budenovsky" (pabellón K7)',
    25: 'Moscú CCE "Atrium"',
    26: 'Moscú CC "Areal" (Belyaevo)',
    27: 'Moscú CC "MEGA Belaya Dacha II"',
    28: 'Moscú CC "MEGA Tyoply Stan" II',
    29: 'Moscú CC "Novy Vek" (Novokosino)',
    30: 'Moscú CC "Perlovsky"',
    31: 'Moscú CC "Semyonovsky"',
    32: 'Moscú CC "Serebryany Dom"',
    33: 'Mytishchi CCE "XL-3"',
    34: 'Nizhni Nóvgorod CCE "RIO"',
    35: 'Nizhni Nóvgorod CCE "Fantastika"',
    36: 'Novosibirsk CCE "Galereya Novosibirsk"',
    37: 'Novosibirsk CC "Mega"',
    38: 'Omsk CC "Mega"',
    39: 'Rostov del Don CCE "Megatsentr Gorizont"',
    40: 'Rostov del Don CCE "Megatsentr Gorizont" Isla',
    41: 'Rostov del Don CC "Mega"',
    42: 'San Petersburgo CC "Nevsky Tsentr"',
    43: 'San Petersburgo CC "Sennaya"',
    44: 'Samara CC "Melodiya"',
    45: 'Samara CC "ParkHouse"',
    46: 'Sergiev Posad CC "7Ya"',
    47: 'Surgut CCE "City Mall"',
    48: 'Tomsk CCE "Izumrudny Gorod"',
    49: 'Tiumén CCE "Kristall"',
    50: 'Tiumén CC "Goodwin"',
    51: 'Tiumén CC "Zeleny Bereg"',
    52: 'Ufá CC "Tsentralny"',
    53: 'Ufá CC "Semya" 2',
    54: 'Jimki CC "Mega"',
    55: 'Almacén digital 1C-Online',
    56: 'Chéjov CCE "Karnaval"',
    57: 'Yakutsk Ordzhonikidze, 56',
    58: 'Yakutsk CC "Tsentralny"',
    59: 'Yaroslavl CC "Altair"',
}

CATEGORIAS_ES = {
    0: "PC - Auriculares/Audífonos",
    1: "Accesorios - PS2",
    2: "Accesorios - PS3",
    3: "Accesorios - PS4",
    4: "Accesorios - PSP",
    5: "Accesorios - PSVita",
    6: "Accesorios - XBOX 360",
    7: "Accesorios - XBOX ONE",
    8: "Boletos (digital)",
    9: "Envío de productos",
    10: "Consolas - PS2",
    11: "Consolas - PS3",
    12: "Consolas - PS4",
    13: "Consolas - PSP",
    14: "Consolas - PSVita",
    15: "Consolas - XBOX 360",
    16: "Consolas - XBOX ONE",
    17: "Consolas - Otras",
    18: "Juegos - PS2",
    19: "Juegos - PS3",
    20: "Juegos - PS4",
    21: "Juegos - PSP",
    22: "Juegos - PSVita",
    23: "Juegos - XBOX 360",
    24: "Juegos - XBOX ONE",
    25: "Juegos - Accesorios para juegos",
    26: "Juegos Android - Digital",
    27: "Juegos MAC - Digital",
    28: "Juegos PC - Ediciones adicionales",
    29: "Juegos PC - Ediciones de colección",
    30: "Juegos PC - Ediciones estándar",
    31: "Juegos PC - Digital",
    32: "Tarjetas de pago (cine, música, juegos)",
    33: "Tarjetas de pago - Live!",
    34: "Tarjetas de pago - Live! (digital)",
    35: "Tarjetas de pago - PSN",
    36: "Tarjetas de pago - Windows (digital)",
    37: "Cine - Blu-Ray",
    38: "Cine - Blu-Ray 3D",
    39: "Cine - Blu-Ray 4K",
    40: "Cine - DVD",
    41: "Cine - De colección",
    42: "Libros - Artbooks, enciclopedias",
    43: "Libros - Audiolibros",
    44: "Libros - Audiolibros (digital)",
    45: "Libros - Audiolibros 1C",
    46: "Libros - Literatura de negocios",
    47: "Libros - Cómics, manga",
    48: "Libros - Literatura de computación",
    49: "Libros - Materiales metodológicos 1C",
    50: "Libros - Postales",
    51: "Libros - Divulgación",
    52: "Libros - Guías de viaje",
    53: "Libros - Ficción",
    54: "Libros - Digital",
    55: "Música - CD de producción local",
    56: "Música - CD de producción original (de marca)",
    57: "Música - MP3",
    58: "Música - Vinilo",
    59: "Música - Video musical",
    60: "Música - Ediciones de regalo",
    61: "Regalos - Artículos de marca (merchandising)",
    62: "Regalos - Gadgets, robots, deporte",
    63: "Regalos - Peluches",
    64: "Regalos - Juegos de mesa",
    65: "Regalos - Juegos de mesa (compactos)",
    66: "Regalos - Postales, calcomanías",
    67: "Regalos - Juegos educativos",
    68: "Regalos - Certificados, servicios",
    69: "Regalos - Souvenirs",
    70: "Regalos - Souvenirs (colgantes)",
    71: "Regalos - Bolsas, álbumes, alfombrillas de ratón",
    72: "Regalos - Figuras",
    73: "Programas - 1C:Enterprise 8",
    74: "Programas - MAC (digital)",
    75: "Programas - Hogar y oficina",
    76: "Programas - Hogar y oficina (digital)",
    77: "Programas - Educativos",
    78: "Programas - Educativos (digital)",
    79: "Servicio",
    80: "Servicio - Boletos",
    81: "Medios vírgenes (spindle)",
    82: "Medios vírgenes (unidad)",
    83: "Baterías",
}

# Correcciones manuales de la traducción automática para productos citados en el análisis
CORRECCIONES_ITEMS = {
    20949: "Bolsa de marca tipo camiseta 1C Interes blanca (34*42) 45 micras",
    17717: "Recepción de pagos para 1C-Online",
    11373: "Entrega a punto de recogida (Boxberry)",
    11365: "Entrega (EMS)",
    6066: "Radmin 3 - 522 licencias",
    6675: "Sony PlayStation 4 (500 GB) Negra (CUH-1008A/1108A/B01)",
    5822: "Playstation Store recarga de monedero: tarjeta de pago 1000 rublos",
}

URL = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=ru&tl=es"  # Endpoint de Google Translate
CIRILICO = re.compile(r"[А-Яа-яЁё]")  # Detecta si un texto tiene caracteres cirílicos


def traducir_lote(textos, reintentos=5):
    """Traduce una lista de textos de ruso a español en una sola consulta."""
    datos = urllib.parse.urlencode([("q", t) for t in textos]).encode("utf-8")  # Varios parámetros q en un POST
    for intento in range(reintentos):
        try:
            req = urllib.request.Request(URL, data=datos, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                resultado = json.loads(r.read().decode("utf-8"))
            resultado = [x if isinstance(x, str) else x[0] for x in resultado]  # Normaliza el formato de respuesta
            if len(resultado) == len(textos):
                return resultado
        except Exception as e:  # Errores de red o límite de consultas: esperamos y reintentamos
            print(f"  reintento {intento + 1}: {e}")
        time.sleep(2 * (intento + 1))
    raise RuntimeError("No se pudo traducir el lote")


def generar_tiendas_y_categorias():
    """Escribe las traducciones manuales de tiendas y categorías."""
    shops = pd.read_csv(DATA_RAW / "shops.csv")
    shops["shop_name_es"] = shops["shop_id"].map(TIENDAS_ES)
    assert shops["shop_name_es"].notna().all(), "Faltan tiendas por traducir"
    shops.rename(columns={"shop_name": "shop_name_ru"})[["shop_id", "shop_name_ru", "shop_name_es"]].to_csv(
        REFERENCES / "traduccion_tiendas.csv", index=False, encoding="utf-8"
    )
    cats = pd.read_csv(DATA_RAW / "item_categories.csv")
    cats["item_category_name_es"] = cats["item_category_id"].map(CATEGORIAS_ES)
    assert cats["item_category_name_es"].notna().all(), "Faltan categorías por traducir"
    cats.rename(columns={"item_category_name": "item_category_name_ru"})[
        ["item_category_id", "item_category_name_ru", "item_category_name_es"]
    ].to_csv(REFERENCES / "traduccion_categorias.csv", index=False, encoding="utf-8")
    print("Tiendas y categorías escritas en", REFERENCES)


def generar_items(tam_lote=40, pausa=0.4):
    """Traduce los nombres de productos (reanudable) y escribe traduccion_items.csv."""
    salida = REFERENCES / "traduccion_items.csv"
    items = pd.read_csv(DATA_RAW / "items.csv")[["item_id", "item_name"]].rename(columns={"item_name": "item_name_ru"})
    hechos = {}
    if salida.exists():  # Reanudar: cargamos lo ya traducido
        previo = pd.read_csv(salida)
        hechos = dict(zip(previo["item_id"], previo["item_name_es"]))
    pendientes = items[~items["item_id"].isin(hechos.keys())]
    sin_cirilico = pendientes[~pendientes["item_name_ru"].str.contains(CIRILICO)]  # Nombres que no requieren traducción
    hechos.update(dict(zip(sin_cirilico["item_id"], sin_cirilico["item_name_ru"].str.strip())))
    por_traducir = pendientes[pendientes["item_name_ru"].str.contains(CIRILICO)]
    print(f"Productos: {len(items):,} | sin cirílico: {len(sin_cirilico):,} | por traducir: {len(por_traducir):,}")

    for i in range(0, len(por_traducir), tam_lote):
        lote = por_traducir.iloc[i : i + tam_lote]
        textos = lote["item_name_ru"].str.strip().str.replace(r"\s+", " ", regex=True).tolist()  # Limpia espacios repetidos
        hechos.update(dict(zip(lote["item_id"], traducir_lote(textos))))
        if (i // tam_lote) % 25 == 0:  # Guardado periódico del avance
            _guardar(items, hechos, salida)
            print(f"  {i + len(lote):,} / {len(por_traducir):,}", flush=True)
        time.sleep(pausa)
    _guardar(items, hechos, salida)
    print("Productos escritos en", salida)


def _guardar(items, hechos, salida):
    """Guarda las traducciones disponibles aplicando las correcciones manuales."""
    df = items[items["item_id"].isin(hechos.keys())].copy()
    df["item_name_es"] = df["item_id"].map(hechos)
    df.loc[df["item_id"].isin(CORRECCIONES_ITEMS), "item_name_es"] = df["item_id"].map(CORRECCIONES_ITEMS)
    df.to_csv(salida, index=False, encoding="utf-8")


if __name__ == "__main__":
    REFERENCES.mkdir(exist_ok=True)
    generar_tiendas_y_categorias()
    generar_items()
