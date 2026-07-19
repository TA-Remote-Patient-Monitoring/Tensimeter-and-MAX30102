from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Profile, Note
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class NoteCreate(BaseModel):
    title: str
    content: str
    category: str = "Konsultasi"
    tags: Optional[str] = None

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None

@router.get("/patients/{uuid_or_id}/notes")
def get_notes(uuid_or_id: str, db: Session = Depends(get_db)):
    patient = db.query(Profile).filter(Profile.uuid == uuid_or_id).first()
    if not patient:
        patient = db.query(Profile).filter(Profile.id == uuid_or_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    notes = db.query(Note).filter(Note.id_profile == patient.id).order_by(Note.created_at.desc()).all()
    
    return {
        "success": True,
        "notes": [
            {
                "id": n.id,
                "patient_id": n.id_profile,
                "title": n.title,
                "content": n.content,
                "category": n.category,
                "tags": n.tags,
                "created_at": n.created_at.isoformat(),
                "updated_at": n.updated_at.isoformat()
            } for n in notes
        ]
    }


@router.post("/patients/{uuid_or_id}/notes")
def create_note(uuid_or_id: str, note_data: NoteCreate, db: Session = Depends(get_db)):
    patient = db.query(Profile).filter(Profile.uuid == uuid_or_id).first()
    if not patient:
        patient = db.query(Profile).filter(Profile.id == uuid_or_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    new_note = Note(
        id_profile=patient.id,
        title=note_data.title,
        content=note_data.content,
        category=note_data.category,
        tags=note_data.tags
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    
    return {
        "success": True,
        "message": "Note created successfully",
        "note": {
            "id": new_note.id,
            "patient_id": new_note.id_profile,
            "title": new_note.title,
            "content": new_note.content,
            "category": new_note.category,
            "created_at": new_note.created_at.isoformat()
        }
    }


@router.put("/notes/{note_id}")
def update_note(note_id: int, note_data: NoteUpdate, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    if note_data.title is not None:
        note.title = note_data.title
    if note_data.content is not None:
        note.content = note_data.content
    if note_data.category is not None:
        note.category = note_data.category
    if note_data.tags is not None:
        note.tags = note_data.tags
        
    db.commit()
    db.refresh(note)
    
    return {
        "success": True,
        "message": "Note updated successfully",
        "note": {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "category": note.category
        }
    }


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
        
    db.delete(note)
    db.commit()
    
    return {
        "success": True,
        "message": "Note deleted successfully"
    }
