import os
import json
import logging

import boto3

# Configuración del cliente de AWS Glue
glue_client = boto3.client("glue")

# Nombre del crawler de Glue, provisto vía variable de entorno (Zappa)
GLUE_CRAWLER_NAME = os.environ.get("GLUE_CRAWLER_NAME")

# Configuración básica de logging en lugar de usar print()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def lambda_handler(event: dict, context: object) -> dict:
    """
    Manejador principal de la función Lambda para iniciar un AWS Glue Crawler.

    Este handler realiza las siguientes acciones:
      1. Valida que la variable de entorno GLUE_CRAWLER_NAME esté configurada.
      2. Intenta arrancar el crawler de Glue cuyo nombre se especifica en la variable de entorno.
      3. Captura la excepción CrawlerRunningException si el crawler ya se encuentra en ejecución.
      4. Captura cualquier otra excepción y devuelve un error 500.

    Parámetros:
        event (dict): Objeto con la información del evento que disparó la función Lambda.
        context (object): Información de contexto provista por AWS Lambda (no se utiliza aquí).

    Retorna:
        dict: Diccionario con claves:
            - statusCode (int): Código HTTP simulado (200 en caso de éxito o 500 en error).
            - body (str): Mensaje en formato JSON (string) con el resultado de la operación.
    """
    # Registrar el evento recibido para facilitar debugging
    logger.info("Received event: %s", json.dumps(event))

    # Verificar que exista el nombre del crawler en las variables de entorno
    if not GLUE_CRAWLER_NAME:
        logger.error("GLUE_CRAWLER_NAME environment variable not set.")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Glue Crawler name not configured"}),
        }

    try:
        # Intentar iniciar el crawler
        logger.info("Starting Glue Crawler: %s", GLUE_CRAWLER_NAME)
        response = glue_client.start_crawler(Name=GLUE_CRAWLER_NAME)
        logger.info("Successfully started crawler: %s", response)

        return {
            "statusCode": 200,
            "body": json.dumps(f"Successfully started Glue Crawler {GLUE_CRAWLER_NAME}"),
        }

    except glue_client.exceptions.CrawlerRunningException:
        # Si el crawler ya está en ejecución, devolvemos 200 pero indicamos que ya corría
        logger.warning("Crawler %s is already running. Skipping start.", GLUE_CRAWLER_NAME)
        return {
            "statusCode": 200,
            "body": json.dumps(f"Crawler {GLUE_CRAWLER_NAME} is already running."),
        }

    except Exception as e:
        # Cualquier otra excepción se registra y se devuelve error 500
        logger.exception("Error starting Glue Crawler %s: %s", GLUE_CRAWLER_NAME, e)
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error starting Glue Crawler {GLUE_CRAWLER_NAME}: {e}"),
        }
