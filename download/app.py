import os
import time
import logging
from datetime import datetime

import requests
import boto3

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Nombre del bucket de S3 (se recomienda mover a variable de entorno via Zappa)
BUCKET_NAME = os.environ.get("BUCKET_NAME", "examenfinalbigdata")

# Diccionario de sitios a consultar: clave = nombre interno, valor = URL
SITES = {
    "eltiempo": "https://www.eltiempo.com",
    "publimetro": "https://www.publimetro.co"
}


def download_and_save_to_s3(site_name: str, url: str) -> bool:
    """
    Descarga el contenido HTML de un sitio web y lo guarda en un bucket de S3 en formato raw.

    Flujo:
        1. Hace una petición HTTP GET a la URL especificada.
        2. Verifica el status code; si no es 2xx, lanza excepción.
        3. Construye la clave de S3 usando el nombre del sitio y la fecha actual.
        4. Sube el contenido HTML (codificado en UTF-8) al bucket de S3.
        5. Retorna True si todo fue exitoso, False si ocurre cualquier excepción.

    Parámetros:
        site_name (str): Etiqueta interna del sitio (por ejemplo, "eltiempo" o "publimetro").
        url (str): URL completa desde donde descargar el HTML.

    Retorna:
        bool: True si la descarga y carga en S3 fueron exitosas; False en caso de error.
    """
    try:
        logger.info("Downloading data from %s", url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/58.0.3029.110 Safari/537.3"
            )
        }

        # Petición GET con timeout de 10 segundos
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Levanta HTTPError si status_code no es 2xx
        content = response.text

        # Cliente de S3
        s3_client = boto3.client("s3")

        # Formar la clave en S3: headlines/raw/<sitio>-YYYY-MM-DD.html
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"headlines/raw/{site_name}-{today_str}.html"

        # Subir el objeto a S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/html"
        )
        logger.info("Data saved to S3 bucket %s at %s", BUCKET_NAME, key)
        return True

    except requests.RequestException as http_err:
        # Captura errores relacionados con HTTP (timeout, conexión, status no OK, etc.)
        logger.error(
            "HTTP error while downloading from %s: %s", url, http_err, exc_info=True
        )
        return False

    except boto3.exceptions.Boto3Error as s3_err:
        # Captura errores de boto3 al interactuar con S3
        logger.error(
            "S3 error while saving content for site %s: %s", site_name, s3_err, exc_info=True
        )
        return False

    except Exception as e:
        # Cualquier otra excepción inesperada
        logger.exception(
            "Unexpected error in download_and_save_to_s3 for site %s: %s", site_name, e
        )
        return False


def lambda_handler(event: dict, context: object) -> dict:
    """
    Lambda handler que recorre la lista de sitios (SITES), descarga su HTML
    y lo guarda en S3 mediante download_and_save_to_s3().

    Flujo:
        1. Itera sobre cada entrada en SITES (clave = site_name, valor = url).
        2. Invoca download_and_save_to_s3 con el nombre y la URL.
        3. Agrega el resultado (True/False) al diccionario `results`.
        4. Retorna un dict con statusCode 200 y `results` en el body.

    Parámetros:
        event (dict): Objeto de evento AWS Lambda (no se utiliza en este caso).
        context (object): Objeto de contexto AWS Lambda (no se utiliza).

    Retorna:
        dict: {
            "statusCode": 200,
            "body": {
                "<site_name>": <True/False>,
                ...
            }
        }
    """
    results = {}

    for site_name, url in SITES.items():
        logger.info("Processing site: %s", site_name)
        success = download_and_save_to_s3(site_name, url)
        results[site_name] = success

        # Breve pausa para no sobrecargar el servidor ni anti-bots
        time.sleep(1)

    return {
        "statusCode": 200,
        "body": results
    }
