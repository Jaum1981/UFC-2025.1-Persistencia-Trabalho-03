from fastapi import APIRouter, HTTPException
from database import movie_collection, director_collection
from models import MovieCreate, MovieOut
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/movies")

@router.post("/", response_model=MovieOut)
async def create_movie(movie: MovieCreate):
    if movie.director_ids:
        for director_id in movie.director_ids:
            if not ObjectId.is_valid:
                raise HTTPException(status_code=400, detail="Invalid ID")
            director = await director_collection.find_one({"_id": ObjectId(director_id)})
            if not director:
                raise HTTPException(status_code=404, detail="Director not found")
        movie_dict = movie.model_dump(exclude_unset=True)
        result = await movie_collection.insert_one(movie_dict)

        created = await movie_collection.find_one({"_id": result.inserted_id})
        created["_id"] = str(created["_id"])
        return created

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
    if movie.director_ids:
        for director_id in movie.director_ids:
            if not ObjectId.is_valid:
                raise HTTPException(status_code=400, detail="Invalid ID")
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
        updated["_id"] = str(updated["_id"])
        return updated

@router.delete("/{movie_id}")
async def delete_movie(movie_id: str):
    exist = await movie_collection.find_one(
        {
            '_id': ObjectId(movie_id)
        }
    )
    if exist:
        if not ObjectId.is_valid(movie_id):
            raise HTTPException(status_code=400, detail="Invalid ID")
        await movie_collection.delete_one({"_id": ObjectId(movie_id)})
        return {
            "detail": "Movie deleted successfully"
        }
    else:
        raise HTTPException(status_code=404, detail="Movie not found")