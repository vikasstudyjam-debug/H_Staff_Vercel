import os
import uuid
from pathlib import Path
from typing import Dict, Any
from fastapi import UploadFile, HTTPException

ALLOWED_MIME_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
UPLOAD_DIR = Path('data/uploads')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DocumentVerificationService:
    @classmethod
    async def save_kyc_document(cls, file: UploadFile, document_label: str = 'Government ID Document') -> Dict[str, Any]:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail='No document file provided.')
        ext = Path(file.filename).suffix.lower()
        content_type = (file.content_type or '').lower()
        if ext not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=415, detail='Unsupported format. Only PDF, JPG, and PNG permitted.')
        content = await file.read()
        if len(content) == 0 or len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail='File is empty or exceeds 5MB limit.')
        secure_filename = f'{uuid.uuid4()}{ext}'
        dest_path = UPLOAD_DIR / secure_filename
        with open(dest_path, 'wb') as f:
            f.write(content)
        return {
            'secure_filename': secure_filename,
            'original_filename': file.filename,
            'document_type': document_label,
            'file_size_bytes': len(content),
            'storage_path': str(dest_path),
            'status': 'pending'
        }

    @classmethod
    def get_document_path(cls, filename: str) -> Path:
        target = UPLOAD_DIR / os.path.basename(filename)
        if not target.exists():
            raise HTTPException(status_code=404, detail='KYC document file not found.')
        return target

document_kyc_service = DocumentVerificationService()
