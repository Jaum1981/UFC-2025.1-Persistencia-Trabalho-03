from fastapi import APIRouter, HTTPException, Body
from database import director_collection, movie_collection
from models import DirectorCreate, DirectorOut
from typing import List, Optional
from bson import ObjectId
from logger import log_database_operation, log_business_rule_violation, logger
import time

router = APIRouter(prefix="/directors", tags=["directors"])

@router.post("/", response_model=DirectorOut)
async def create_director(director: DirectorCreate):
    logger.info(f"Iniciando criação de diretor: {director.director_name}")
    
    if director.movie_ids:
        logger.info(f"Validando {len(director.movie_ids)} filmes para o diretor")
        for movie_id in director.movie_ids:
            if not ObjectId.is_valid(movie_id):
                log_business_rule_violation(
                    rule="INVALID_MOVIE_ID",
                    details="ID de filme inválido fornecido",
                    data={"movie_id": movie_id, "director_name": director.director_name}
                )
                raise HTTPException(status_code=400, detail="Invalid ID")
            
            movie = await movie_collection.find_one({"_id": ObjectId(movie_id)}) 
            if not movie:
                log_business_rule_violation(
                    rule="MOVIE_NOT_FOUND",
                    details="Filme não encontrado durante criação de diretor",
                    data={"movie_id": movie_id, "director_name": director.director_name}
                )
                raise HTTPException(status_code=404, detail="Movie not found")
        logger.info(f"Todos os {len(director.movie_ids)} filmes foram validados com sucesso")
    
    director_dict = director.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await director_collection.insert_one(director_dict)
    insert_time = time.time() - start_time
    
    start_time = time.time()
    created = await director_collection.find_one({"_id": result.inserted_id})
    find_time = time.time() - start_time
    
    created["_id"] = str(created["_id"])
    
    log_database_operation(
        operation="insert",
        collection="directors",
        operation_data={"director_name": director.director_name, "nationality": director.nationality},
        result={
            "inserted_id": str(result.inserted_id),
            "insert_time": f"{insert_time:.3f}s",
            "find_time": f"{find_time:.3f}s"
        }
    )
    logger.info(f"Diretor '{director.director_name}' criado com sucesso. ID: {result.inserted_id}")
    return created
    
@router.get("/count")
async def get_directors_count():
    count = await director_collection.count_documents({})
    return {"total_directors": count}


@router.get("/", response_model=List[DirectorOut])
async def list_director(skip: int = 0, limit: int = 10):
    directors = await director_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for d in directors:
        d["_id"] = str(d["_id"])
    return directors

@router.get("/{director_id}", response_model=DirectorOut)
async def find_director_by_id(director_id: str):
    if not ObjectId.is_valid(director_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    director = await director_collection.find_one({"_id": ObjectId(director_id)})
    if director:
        director["_id"] = str(director["_id"])
        return director
    raise HTTPException(status_code=404, detail="Diretor not found")

@router.put("/{director_id}", response_model=DirectorOut)
async def update_director(director_id: str, director: DirectorCreate = Body(...)):
    if director.movie_ids:
        for movie_id in director.movie_ids:
            if not ObjectId.is_valid:
                raise HTTPException(status_code=400, detail="Invalid ID")
            movie = await movie_collection.find_one({"_id": ObjectId(movie_id)}) 
            if not movie:
                raise HTTPException(status_code=404, detail="Movie not found")
        update_data = director.model_dump(exclude_unset=True)
        result = await director_collection.update_one(
            {"_id": ObjectId(director_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Director not found")
        updated = await director_collection.find_one({"_id": ObjectId(director_id)})
        updated["_id"] = str(updated["_id"])
        return updated
    else:
        if not ObjectId.is_valid(director_id):
            raise HTTPException(status_code=400, detail="Invalid ID")
        update_data = director.model_dump(exclude_unset=True)
        result = await director_collection.update_one(
            {"_id": ObjectId(director_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Director not found")
        updated = await director_collection.find_one({"_id": ObjectId(director_id)})
        updated["_id"] = str(updated["_id"])
        return updated


@router.delete("/{director_id}")
async def delete_director(director_id: str):
    if not ObjectId.is_valid(director_id):
            raise HTTPException(status_code=400, detail="Invalid ID")
    delete_result = await director_collection.delete_one({"_id": ObjectId(director_id)})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Director not found")
    await movie_collection.update_many(
        {"director_ids": director_id},
        {"$pull": {"director_ids": director_id}}
    )
    return {"detail": "Director deleted successfully"}


@router.get("/filter", response_model=List[DirectorOut])
async def filter_directors(
    director_name: Optional[str] = None,
    nationality: Optional[str] = None,
    birth_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
):
    filter_query = {}
    
    if director_name:
        filter_query["director_name"] = {"$regex": director_name, "$options": "i"}
    if nationality:
        filter_query["nationality"] = {"$regex": nationality, "$options": "i"}
    if birth_date:
        filter_query["birth_date"] = {"$regex": birth_date, "$options": "i"}
    
    directors = await director_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    for d in directors:
        d["_id"] = str(d["_id"])
    return directors