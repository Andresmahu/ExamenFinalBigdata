import json
import boto3
import io
import csv
from bs4 import BeautifulSoup
import re
from datetime import datetime
import unicodedata

s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Lambda que:
    1. Se dispara al subir un archivo HTML a S3.
    2. Descarga ese HTML, lo parsea con BeautifulSoup para extraer noticias.
    3. Crea un CSV en memoria con las noticias y lo vuelve a subir a S3.
    """
    # 1. Obtener bucket y key del evento S3
    # Cada evento de S3 viene en event['Records']
    for record in event.get('Records', []):
        bucket_name = record['s3']['bucket']['name']
        object_key = record['s3']['object']['key']
        # Suponemos que el HTML subido tiene extensión .html
        if not object_key.lower().endswith('.html'):
            print(f"El objeto {object_key} no es un HTML; se omite.")
            continue
        
        try:
            # 2. Descargar el contenido del archivo HTML desde S3
            response = s3.get_object(Bucket=bucket_name, Key=object_key)
            html_bytes = response['Body'].read()
            html_content = html_bytes.decode('utf-8')
            print(f"HTML descargado correctamente: s3://{bucket_name}/{object_key}")
        except Exception as e:
            print(f"Error al descargar {object_key} de {bucket_name}: {e}")
            continue
        
        # 3. Parsear con BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        noticias = []
        if re.search(r'(?i)\beltiempo\b', object_key):
            base_url = "https://www.eltiempo.com"
            for article in soup.find_all('article'):
                t = article.find(['h2', 'h3'])
                a = article.find('a', href=True)
                
                if not t or not a:
                    continue
                titular = t.get_text(strip=True)
                texto_nfd = unicodedata.normalize('NFD', titular)
                titular_sin_tildes = re.sub(r'[\u0300-\u036f]', '', texto_nfd)
                titulo_sin_caracteres = re.sub(r'[^A-Za-z0-9\s]', '', titular_sin_tildes)
                titular_final = re.sub(r",", " ", titulo_sin_caracteres)
                enlace = a['href']
            
                if not enlace.startswith('http'):
                    enlace = base_url + enlace
                parts = enlace.split('/')
                categoria = parts[3] if len(parts) > 3 else ''
                noticias.append({
                    'Categoria': categoria,
                    'Titular': titular_final,
                    'Enlace': enlace
                })
            periodico='eltiempo'
        elif re.search(r'(?i)\bpublimetro\b', object_key):
            base_url = "https://www.publimetro.co"
            for article in soup.find_all(['h2','h3'], class_='c-heading'):
                t = article.find(['a'])
                a = article.find('a', href=True)
                
                if not a:
                    continue
                titular = t.get_text(strip=True)
                texto_nfd = unicodedata.normalize('NFD', titular)
                titular_sin_tildes = re.sub(r'[\u0300-\u036f]', '', texto_nfd)
                titulo_sin_caracteres = re.sub(r'[^A-Za-z0-9\s]', '', titular_sin_tildes)
                titular_final = re.sub(r",", " ", titulo_sin_caracteres)
                enlace = a['href']
                
                if not enlace.startswith('http') and base_url:
                    enlace = base_url + enlace
            
                parts = enlace.split('/')
                categoria = parts[3] if len(parts) > 3 else ''
                noticias.append({
                    'Categoria': categoria,
                    'Titular': titular_final,
                    'Enlace': enlace
                })
            periodico='publimetro'
        else:
            return None
        
        print(f"Total de noticias extraídas: {len(noticias)}")
        
        # 4. Crear un CSV en memoria con las noticias
        csv_buffer = io.StringIO()
        escritor = csv.DictWriter(csv_buffer,fieldnames=['Categoria', 'Titular', 'Enlace'])
        escritor.writeheader()
        for noticia in noticias:
            escritor.writerow(noticia)
        
        csv_key = f'headlines/final/periodico={periodico}/{datetime.now().strftime("year=%Y/month=%m/day=%d")}/{periodico}.csv'
        
        try:
            # 6. Subir el CSV a S3
            s3.put_object(
                Bucket=bucket_name,
                Key=csv_key,
                Body=csv_buffer.getvalue().encode('utf-8'),
                ContentType='text/csv'
            )
        except Exception as e:
            print(f"Error al subir el CSV a {bucket_name}/{csv_key}: {e}")
            continue
    # 7. Retornar un mensaje de confirmación
    return {
        'statusCode': 200,
        'body': json.dumps('Procesamiento de noticias completado.')
    }
