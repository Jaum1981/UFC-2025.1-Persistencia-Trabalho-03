from fastapi import APIRouter, HTTPException
from database import movie_collection, director_collection
from models import MovieCreate, MovieOut
from typing import List, Optional
from bson import ObjectId

router = APIRouter(prefix="/movies")

@router.post("/", response_model=MovieOut)
async def create_movie(movie: MovieCreate):
    if movie.director_ids:
        try:
            director_obj_ids = [ObjectId(d_id) for d_id in movie.director_ids]
        except Exception:
            raise HTTPException(status_code=400, detail="Um ou mais IDs de diretor são inválidos")
        num_directors_found = await director_collection.count_documents({"_id": {"$in": director_obj_ids}})
        if num_directors_found != len(movie.director_ids):
            raise HTTPException(status_code=404, detail="Um ou mais diretores não foram encontrados")
    
    movie_dict = movie.model_dump(exclude_unset=True)
    result = await movie_collection.insert_one(movie_dict)
    new_movie_id = result.inserted_id
    if movie.director_ids:
        try:
            await director_collection.update_many(
                {"_id": {"$in": director_obj_ids}},
                {"$push": {"movie_ids": str(new_movie_id)}}
            )
        except Exception as e:
            await movie_collection.delete_one({"_id": new_movie_id})
            raise HTTPException(
                status_code=500, 
                detail=f"Erro ao associar filme aos diretores. Operação revertida. Erro: {e}"
            )
    movie_dict["_id"] = str(new_movie_id)
    return movie_dict
    
@router.get("/count")
async def get_movies_count():
    count = await movie_collection.count_documents({})
    return {"total_movies": count}

@router.get("/", response_model=List[MovieOut])
async def list_movies(skip: int = 0, limit: int = 10):
    movies = await movie_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for m in movies:
        m["_id"] = str(m["_id"])
    return movies

@router.get("/{movie_id}", response_model=MovieOut)
async def find_movie_by_id(movie_id: str):
    if not ObjectId.is_valid(movie_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    if movie:
        movie["_id"] = str(movie["_id"])
        return movie
    raise HTTPException(status_code=404, detail="Movie not found")

@router.put("/{movie_id}", response_model=MovieOut)
async def update_movie(movie_id: str, movie: MovieCreate):
    if not ObjectId.is_valid(movie_id):
        raise HTTPException(status_code=400, detail="Invalid movie ID")
    
    if movie.director_ids:
        for director_id in movie.director_ids:
            if not ObjectId.is_valid(director_id):
                raise HTTPException(status_code=400, detail="Invalid director ID")
            director = await director_collection.find_one({"_id": ObjectId(director_id)})
            if not director:
                raise HTTPException(status_code=404, detail="Director not found")
    
    updated_data = movie.model_dump(exclude_unset=True)
    result = await movie_collection.update_one(
        {"_id": ObjectId(movie_id)},
        {"$set": updated_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    updated = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    if updated:
        updated["_id"] = str(updated["_id"])
        return updated
    else:
        raise HTTPException(status_code=500, detail="Failed to update movie")

@router.delete("/{movie_id}")
async def delete_movie(movie_id: str):
    if not ObjectId.is_valid(movie_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    exist = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    if exist:
        if exist.get("director_ids"):
            for director_id in exist["director_ids"]:
                if ObjectId.is_valid(director_id):
                    await director_collection.update_one(
                        {"_id": ObjectId(director_id)},
                        {"$pull": {"movie_ids": movie_id}}
                    )
        
        await movie_collection.delete_one({"_id": ObjectId(movie_id)})
        return {"detail": "Movie deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Movie not found")



@router.get("/filter", response_model=List[MovieOut])
async def filter_movies(
    movie_title: Optional[str] = None,
    genre: Optional[str] = None,
    rating: Optional[str] = None,
    release_year: Optional[int] = None,
    director_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
):
    filter_query = {}
    
    if movie_title:
        filter_query["movie_title"] = {"$regex": movie_title, "$options": "i"}
    if genre:
        filter_query["genre"] = {"$regex": genre, "$options": "i"}
    if rating:
        filter_query["rating"] = {"$regex": rating, "$options": "i"}
    if release_year is not None:
        filter_query["release_year"] = release_year
    if director_id:
        if ObjectId.is_valid(director_id):
            filter_query["director_ids"] = {"$in": [director_id]}
        else:
            raise HTTPException(status_code=400, detail="Invalid director ID")
    
    movies = await movie_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    for m in movies:
        m["_id"] = str(m["_id"])
    return movies