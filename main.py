import os
import json
import uuid
import mimetypes
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Em produção (Railway), usar /data (volume persistente). Localmente usar a pasta do projeto.
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)
DATA_FILE = os.path.join(DATA_DIR, 'data.json')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads', 'audios')

os.makedirs(UPLOADS_DIR, exist_ok=True)

def load_data() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_FILE):
        save_data([])
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and 'audios' in raw:
            return raw['audios']
        return []
    except Exception:
        save_data([])
        return []

def save_data(data: List[Dict[str, Any]]):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

app = FastAPI(
    title='Gravador API',
    description='API para guardar gravações de áudio',
    version='2.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Servir ficheiros de áudio uploads
uploads_root = os.path.join(DATA_DIR, 'uploads')
os.makedirs(uploads_root, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=uploads_root), name='uploads')

@app.get('/')
def get_root():
    data = load_data()
    return {
        'status': 'online',
        'name': 'Gravador API',
        'total_audios': len(data),
        'docs_url': '/docs'
    }

@app.get('/api/items')
def list_items():
    return load_data()

@app.get('/api/items/{item_id}')
def get_item(item_id: str):
    for item in load_data():
        if item['id'] == item_id:
            return item
    raise HTTPException(status_code=404, detail='Item não encontrado')

@app.post('/api/upload')
async def upload_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    content = await file.read()

    file_id = str(uuid.uuid4())
    original_ext = os.path.splitext(file.filename or '')[1]
    ext = original_ext if original_ext else '.m4a'
    saved_filename = f'{file_id}{ext}'
    saved_path = os.path.join(UPLOADS_DIR, saved_filename)

    with open(saved_path, 'wb') as f:
        f.write(content)

    item_title = title.strip() if title else os.path.splitext(file.filename or 'gravacao')[0]
    created_at = datetime.utcnow().isoformat() + 'Z'
    mime = file.content_type or mimetypes.guess_type(file.filename or '')[0] or 'audio/m4a'

    record = {
        'id': file_id,
        'filename': saved_filename,
        'original_name': file.filename,
        'mime_type': mime,
        'size_bytes': len(content),
        'title': item_title,
        'description': description or '',
        'created_at': created_at,
        'url': f'/uploads/audios/{saved_filename}'
    }

    data = load_data()
    data.insert(0, record)
    save_data(data)

    return {'message': 'Áudio guardado com sucesso', 'item': record}

@app.delete('/api/items/{item_id}')
def delete_item(item_id: str):
    data = load_data()
    item = next((i for i in data if i['id'] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail='Item não encontrado')

    file_path = os.path.join(UPLOADS_DIR, item['filename'])
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f'Aviso: não foi possível apagar o ficheiro: {e}')

    updated = [i for i in data if i['id'] != item_id]
    save_data(updated)
    return {'message': 'Áudio eliminado', 'item_id': item_id}

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', 8000))
    print(f'Servidor iniciado em http://0.0.0.0:{port}')
    uvicorn.run(app, host='0.0.0.0', port=port)
