# download/test_download.py

import pytest
from unittest.mock import patch, MagicMock
import app 

class DummyResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP {self.status_code}")

@pytest.fixture(autouse=True)
def patch_datetime(monkeypatch):
    """
    Forzamos datetime.now() a una fecha fija para que la key S3 sea predecible.
    """
    class DummyDateTime:
        @staticmethod
        def now():
            from datetime import datetime
            return datetime(2025, 6, 10)
        @staticmethod
        def strftime(fmt):
            return DummyDateTime.now().strftime(fmt)

    # Aquí reemplazamos app.datetime por DummyDateTime
    monkeypatch.setattr(app, 'datetime', DummyDateTime)

@patch('app.boto3')
@patch('app.requests.get')
def test_download_and_save_success(mock_get, mock_boto3):
    """
    Caso exitoso: requests.get devuelve HTML y boto3.client('s3').put_object no falla.
    """
    # 1) Simular requests.get() con DummyResponse(status_code=200)
    html_content = "<html><body><p>contenido prueba</p></body></html>"
    dummy_resp = DummyResponse(html_content, status_code=200)
    mock_get.return_value = dummy_resp

    # 2) Mock de boto3.client('s3')
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    # 3) Llamar a la función a testear
    success = app.download_and_save_to_s3("eltiempo", "https://www.eltiempo.com")

    # 4) Verificar retorno y que put_object fue llamado correctamente
    assert success is True
    mock_boto3.client.assert_called_once_with('s3')
    expected_key = "headlines/raw/eltiempo-2025-06-10.html"
    mock_s3_client.put_object.assert_called_once_with(
        Bucket=app.BUCKET_NAME,
        Key=expected_key,
        Body=html_content.encode('utf-8'),
        ContentType='text/html'
    )

@patch('app.boto3')
@patch('app.requests.get')
def test_download_and_save_http_error(mock_get, mock_boto3):
    """
    Caso en que requests.get devuelve status_code != 200, raise_for_status lanza excepción.
    Esperamos que download_and_save_to_s3 devuelva False y no invoque put_object.
    """
    # Simular HTTP 404
    dummy_resp = DummyResponse("Not Found", status_code=404)
    mock_get.return_value = dummy_resp

    # Mock boto3.client('s3')
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    success = app.download_and_save_to_s3("publimetro", "https://www.publimetro.co")
    assert success is False
    mock_s3_client.put_object.assert_not_called()

@patch('app.boto3')
@patch('app.requests.get')
def test_download_and_save_put_object_error(mock_get, mock_boto3):
    """
    Caso en que requests.get es exitoso pero put_object lanza excepción → retorno False.
    """
    # Simular descarga exitosa
    dummy_resp = DummyResponse("<html></html>", status_code=200)
    mock_get.return_value = dummy_resp

    # boto3.client('s3') cuyo put_object lanza excepción
    mock_s3_client = MagicMock()
    mock_s3_client.put_object.side_effect = Exception("S3 fallo")
    mock_boto3.client.return_value = mock_s3_client

    success = app.download_and_save_to_s3("eltiempo", "https://www.eltiempo.com")
    assert success is False

@patch.object(app, 'download_and_save_to_s3')
def test_lambda_handler_combined(mock_download):
    """
    Simular que la primera llamada a download_and_save_to_s3 devuelve True
    y la segunda False. Verificar que lambda_handler retorne lo esperado.
    """
    mock_download.side_effect = [True, False]

    # Ejecutar el handler
    event = {}  # su contenido no importa para esta prueba
    result = app.lambda_handler(event, None)

    assert result['statusCode'] == 200
    assert result['body'] == {'eltiempo': True, 'publimetro': False}

    # Comprobar orden de llamadas
    calls = [c.args[0] for c in mock_download.call_args_list]
    assert calls == ['eltiempo', 'publimetro']