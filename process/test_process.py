# tests/test_process_app.py

import pytest
import json
from unittest.mock import patch, MagicMock
import app

# Ejemplo de HTML de prueba para El Tiempo (2 artículos válidos)
SAMPLE_HTML_ELTIEMPO = """
<html><body>
  <article>
    <h2><a href="/mundo/noticia-uno-123">Titular Uno, con tilde á</a></h2>
  </article>
  <article>
    <h3><a href="http://externo.com/vida/noticia-dos-456">Titular Dos & especial</a></h3>
  </article>
</body></html>
"""

# Ejemplo de HTML de prueba para Publimetro (2 enlaces válidos)
SAMPLE_HTML_PUBLI = """
<html><body>
  <h2 class="c-heading"><a href="/deportes/noticia-tres-789">Fútbol Colombiano ¡Emoción!</a></h2>
  <h3 class="c-heading"><a href="https://www.publimetro.co/entretenimiento/not4">Noticia cuatro, cine</a></h3>
  <!-- Un heading sin <a href> válido -->
  <h2 class="c-heading">Sin enlace aquí</h2>
</body></html>
"""

@pytest.fixture(autouse=True)
def patch_datetime(monkeypatch):
    """
    Forzamos datetime.now() para que la ruta del CSV sea siempre la misma (2025-06-10).
    """
    class DummyDateTime:
        @staticmethod
        def now():
            from datetime import datetime
            return datetime(2025, 6, 10)
        @staticmethod
        def strftime(fmt):
            return DummyDateTime.now().strftime(fmt)

    # Sustituimos app.datetime por DummyDateTime
    monkeypatch.setattr(app, 'datetime', DummyDateTime)

@patch('app.s3')
def test_process_eltiempo_success(mock_s3, patch_datetime):
    """
    1) El key coincide con 'eltiempo', 2) get_object devuelve SAMPLE_HTML_ELTIEMPO,
    3) Debe llamarse a put_object exactamente una vez con el CSV (header + 2 filas).
    """
    # Simulamos el evento S3 con key="eltiempo-2025-06-10.html"
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'examenfinalbigdata'},
                    'object': {'key': 'headlines/raw/eltiempo-2025-06-10.html'}
                }
            }
        ]
    }

    # Mockeamos get_object para devolver el HTML de ejemplo
    body_mock = MagicMock()
    body_mock.read.return_value = SAMPLE_HTML_ELTIEMPO.encode('utf-8')
    mock_s3.get_object.return_value = {'Body': body_mock}

    # Ejecutamos la lambda
    response = app.lambda_handler(event, None)

    # Comprobamos que get_object se llamó con los parámetros correctos
    mock_s3.get_object.assert_called_once_with(
        Bucket='examenfinalbigdata',
        Key='headlines/raw/eltiempo-2025-06-10.html'
    )

    # Ahora debe invocar put_object exactamente una vez
    assert mock_s3.put_object.call_count == 1

    put_args = mock_s3.put_object.call_args[1]
    # Bucket debe ser el mismo
    assert put_args['Bucket'] == 'examenfinalbigdata'
    # El Key debe contener "periodico=eltiempo/year=2025/month=06/day=10/eltiempo.csv"
    assert 'headlines/final/periodico=eltiempo/year=2025/month=06/day=10/eltiempo.csv' in put_args['Key']
    # ContentType debe ser 'text/csv'
    assert put_args['ContentType'] == 'text/csv'

    # Verificar que el Body (bytes) comience con la cabecera CSV, ignorando el '\r'
    body_str = put_args['Body'].decode('utf-8')
    # Accept CRLF or LF: comprobamos que empiece con "Categoria,Titular,Enlace" sin diferenciar si viene "\r\n"
    assert body_str.startswith("Categoria,Titular,Enlace")

    # SAMPLE_HTML_ELTIEMPO tiene 2 artículos, así que debe haber 3 líneas con contenido:
    #   1: header
    #   2: primer artículo
    #   3: segundo artículo
    filas = [l for l in body_str.splitlines() if l.strip() != ""]
    assert len(filas) == 3

    # Verificar la respuesta del handler
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == 'Procesamiento de noticias completado.'


@patch('app.s3')
def test_process_publimetro_success(mock_s3, patch_datetime):
    """
    1) El key coincide con 'publimetro', 2) get_object devuelve SAMPLE_HTML_PUBLI.
    3) Debe invocar put_object una vez con un CSV de 2 artículos + header.
    """
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'examenfinalbigdata'},
                    'object': {'key': 'headlines/raw/publimetro-2025-06-10.html'}
                }
            }
        ]
    }

    # Mock de get_object devolviendo SAMPLE_HTML_PUBLI
    body_mock = MagicMock()
    body_mock.read.return_value = SAMPLE_HTML_PUBLI.encode('utf-8')
    mock_s3.get_object.return_value = {'Body': body_mock}

    response = app.lambda_handler(event, None)

    # Confirmamos que get_object recibió los parámetros correctos
    mock_s3.get_object.assert_called_once_with(
        Bucket='examenfinalbigdata',
        Key='headlines/raw/publimetro-2025-06-10.html'
    )

    # Debe invocar put_object EXACTAMENTE una vez
    assert mock_s3.put_object.call_count == 1

    put_args = mock_s3.put_object.call_args[1]
    # Verificamos que la key contenga "...periodico=publimetro/year=2025/month=06/day=10/publimetro.csv"
    assert 'headlines/final/periodico=publimetro/year=2025/month=06/day=10/publimetro.csv' in put_args['Key']

    # Comprobamos que el Body contenga 1 header + 2 filas
    body_str = put_args['Body'].decode('utf-8')
    filas = [l for l in body_str.splitlines() if l.strip() != ""]
    # La primera línea (filas[0]) debe ser la cabecera; luego dos filas de datos
    assert filas[0].startswith("Categoria,Titular,Enlace")
    assert len(filas) == 3

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == 'Procesamiento de noticias completado.'


@patch('app.s3')
def test_process_non_html_key(mock_s3):
    """
    Si el key no termina en '.html', no debe llamar a get_object ni a put_object,
    pero sí regresa statusCode 200.
    """
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'examenfinalbigdata'},
                    'object': {'key': 'headlines/raw/archivo.txt'}
                }
            }
        ]
    }

    response = app.lambda_handler(event, None)

    mock_s3.get_object.assert_not_called()
    mock_s3.put_object.assert_not_called()
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == 'Procesamiento de noticias completado.'


@patch('app.s3')
def test_process_get_object_error(mock_s3):
    """
    Si s3.get_object lanza excepción, no debe invocar put_object pero sí
    regresar statusCode 200.
    """
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'examenfinalbigdata'},
                    'object': {'key': 'headlines/raw/eltiempo-2025-06-10.html'}
                }
            }
        ]
    }
    # Simulamos falla en get_object
    mock_s3.get_object.side_effect = Exception("No encontrado")

    response = app.lambda_handler(event, None)

    mock_s3.get_object.assert_called_once()
    mock_s3.put_object.assert_not_called()
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == 'Procesamiento de noticias completado.'


@patch('app.s3')
def test_process_html_without_articles(mock_s3, patch_datetime):
    """
    HTML válido pero sin <article> → el código sigue, crea CSV con solo cabecera,
    y sí invoca put_object UNA vez.
    """
    event = {
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'examenfinalbigdata'},
                    'object': {'key': 'headlines/raw/eltiempo-2025-06-10.html'}
                }
            }
        ]
    }
    # HTML sin ningún <article>
    html_sin_article = "<html><body><p>No hay artículos aquí</p></body></html>"
    body_mock = MagicMock()
    body_mock.read.return_value = html_sin_article.encode('utf-8')
    mock_s3.get_object.return_value = {'Body': body_mock}

    response = app.lambda_handler(event, None)

    # get_object se llamó, y put_object TAMBIÉN se llama una vez (ese CSV solo trae la cabecera)
    mock_s3.get_object.assert_called_once()
    assert mock_s3.put_object.call_count == 1

    put_args = mock_s3.put_object.call_args[1]
    # Comprobamos que el Body del CSV solo contenga la cabecera
    body_str = put_args['Body'].decode('utf-8')
    # splitlines() remueve el '\r\n' y nos queda solo la línea "Categoria,Titular,Enlace"
    filas = body_str.splitlines()
    assert filas == ["Categoria,Titular,Enlace"]

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == 'Procesamiento de noticias completado.'
