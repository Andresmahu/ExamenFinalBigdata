import os
import json
import pytest
from unittest import mock
 
# Importamos directamente el módulo que queremos probar
import app
 
 
@pytest.fixture(autouse=True)
def reset_app_module(monkeypatch):
    """
    Este fixture se ejecuta antes de cada prueba y:
      1) Asegura que la variable de entorno GLUE_CRAWLER_NAME no esté establecida de forma persistente.
      2) Reemplaza el objeto glue_client por un Mock limpio.
    """
    # Forzamos que la variable de módulo quede sin valor inicialmente
    monkeypatch.setenv("GLUE_CRAWLER_NAME", "")
    # Reinicializamos la variable de módulo
    app.GLUE_CRAWLER_NAME = None
 
    # Reemplazamos el cliente real de boto3 por un Mock
    mock_glue = mock.Mock()
    app.glue_client = mock_glue
 
    yield
 
    # --- (Opcional) Limpieza tras cada test: no hace falta en este caso ---
 
 
def test_lambda_handler_sin_env_var(monkeypatch):
    """
    Si no está definida GLUE_CRAWLER_NAME, la función debe retornar statusCode 500
    y un body con el mensaje 'Glue Crawler name not configured'.
    """
    # 1) Nos aseguramos de borrar cualquier valor en la variable de módulo
    app.GLUE_CRAWLER_NAME = None
 
    event_falso = {"foo": "bar"}
    resultado = app.lambda_handler(event_falso, None)
 
    assert resultado["statusCode"] == 500
 
    # El body viene en formato JSON-string
    body = json.loads(resultado["body"])
    assert body.get("message") == "Glue Crawler name not configured"
 
 
def test_lambda_handler_arranque_exitoso(monkeypatch):
    """
    Simula que start_crawler devuelve un dict vacío (o cualquier valor)
    y verifica que el statusCode sea 200 con el mensaje de éxito.
    """
    # 1) Definimos un nombre de crawler para el módulo
    app.GLUE_CRAWLER_NAME = "mi-prueba-crawler"
 
    # 2) Preparamos el mock para start_crawler
    mock_response = {"CrawlerArn": "arn:aws:glue:..."}  # puede ser cualquier dict
    app.glue_client.start_crawler.return_value = mock_response
 
    event_falso = {"alguna": "info"}
    resultado = app.lambda_handler(event_falso, None)
 
    # Verificamos que glue_client.start_crawler haya sido invocado con el nombre correcto
    app.glue_client.start_crawler.assert_called_once_with(Name="mi-prueba-crawler")
 
    # Chequeamos el status code y el mensaje
    assert resultado["statusCode"] == 200
    body = json.loads(resultado["body"])
    assert "Successfully started Glue Crawler mi-prueba-crawler" in body
 
 
def test_lambda_handler_crawler_ya_en_ejecucion(monkeypatch):
    """
    Simula que start_crawler lanza una CrawlerRunningException personalizada.
    Debe atraparse y devolver statusCode 200 con un mensaje indicando que ya está en ejecución.
    """
    # 1) Definimos un nombre de crawler para el módulo
    app.GLUE_CRAWLER_NAME = "mi-prueba-crawler"
 
    # 2) Creamos un fake para la excepción CrawlerRunningException y la inyectamos
    class FakeExceptions:
        class CrawlerRunningException(Exception):
            pass
 
    # Hacemos que glue_client.exceptions apunte a nuestro FakeExceptions
    app.glue_client.exceptions = FakeExceptions
 
    # Configuramos el mock de start_crawler para que levante esa excepción
    app.glue_client.start_crawler.side_effect = FakeExceptions.CrawlerRunningException()
 
    event_falso = {}
    resultado = app.lambda_handler(event_falso, None)
 
    # Como la excepción es CrawlerRunningException, debería atraparse y devolver statusCode 200
    assert resultado["statusCode"] == 200
    body = json.loads(resultado["body"])
    assert f"Crawler {app.GLUE_CRAWLER_NAME} is already running." in body
 
 
def test_lambda_handler_excepcion_generica(monkeypatch):
    """
    Simula que start_crawler lanza una excepción genérica (Exception),
    en cuyo caso la función debe devolver statusCode 500 y el error en el body.
    """
    app.GLUE_CRAWLER_NAME = "mi-prueba-crawler"
 
    # Para que no entre en el bloque de CrawlerRunningException,
    # seguimos definiendo exceptions pero lanzamos otra Exception cualquiera.
    class FakeExceptions:
        class CrawlerRunningException(Exception):
            pass
 
    app.glue_client.exceptions = FakeExceptions
 
    # Ahora levantamos una excepción genérica
    app.glue_client.start_crawler.side_effect = Exception("Problema inesperado")
 
    event_falso = {}
    resultado = app.lambda_handler(event_falso, None)
 
    assert resultado["statusCode"] == 500
    body = json.loads(resultado["body"])
    assert "Error starting Glue Crawler mi-prueba-crawler: Problema inesperado" in body