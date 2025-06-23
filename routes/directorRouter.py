from fastapi import APIRouter, HTTPException
from database import director_collection
from models import DirectorCreate, DirectorOut
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/directors")

@router.post("/", response_model=DirectorOut)
async def create_director(director: DirectorCreate):
    director_dict = director.model_dump(exclude_unset=True)
    result = await director_collection.insert_one(director_dict)
    created = await director_collection.find_one(
        {
            '_id': result.inserted_id
        }
    )
    created["_id"] = str(created["_id"])
    return created

@router.get("/", response_model=List[DirectorOut])
async def list_director(skip: int = 0, limit: int = 10):
    directors = await director_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for d in directors:
        d["_id"] = str(d["_id"])
    return directors

@router.get("/{director_id}", response_model=DirectorOut)
async def find_director_by_id(director_id: str):
    if not ObjectId.is_valid(director_id):
        raise HTTPException(status_code=400, detail="ID inválido")
    director = await director_collection.find_one({"_id": ObjectId(director_id)})
    if director:
        director["_id"] = str(director["_id"])
        return director
    raise HTTPException(status_code=404, detail="Diretor não encontrado")

@router.delete("/{director_id}")
async def delete_director(director_id: str):
    exist = await director_collection.find_one(
        {
            '_id': ObjectId(director_id)
        }
    )
    if exist:
        if not ObjectId.is_valid(director_id):
            raise HTTPException(status_code=400, detail="ID inválido")
        await director_collection.delete_one({"_id": ObjectId(director_id)})
        return {
            "detail": "Diretor apagado com sucesso"
        }
    else:
        raise HTTPException(status_code=404, detail="Diretor não encontrado")