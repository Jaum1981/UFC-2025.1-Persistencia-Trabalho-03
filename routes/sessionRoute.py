from fastapi import APIRouter, HTTPException
from database import session_collection, room_collection, movie_collection
from models import SessionCreate, SessionOut
from typing import List, Optional
from bson import ObjectId

router = APIRouter(prefix="/sessions")

@router.post("/", response_model=SessionCreate)
async def create_session(session: SessionCreate):
    if not ObjectId.is_valid(session.movie_id):
        raise HTTPException(status_code=400, detail="Invalid movie ID")
    movie = await movie_collection.find_one({"_id": ObjectId(session.movie_id)})
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    if not ObjectId.is_valid(session.room_id):
        raise HTTPException(status_code=400, detail="Invalid room ID")
    room = await room_collection.find_one({"_id": ObjectId(session.room_id)})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    session_dict = session.model_dump(exclude_unset=True)
    result = await session_collection.insert_one(session_dict)
    new_session_id = str(result.inserted_id)

    await movie_collection.update_one(
        {"_id": ObjectId(session.movie_id)},
        {"$push": {"session_ids": new_session_id}}
    )

    await room_collection.update_one(
        {"_id": ObjectId(session.room_id)},
        {"$push": {"session_ids": new_session_id}}
    )

    created_session = await session_collection.find_one({"_id": result.inserted_id})
    created_session["_id"] = str(created_session["_id"])
    return created_session

@router.get("/count")
async def get_sessions_count():
    count = await session_collection.count_documents({})
    return {"total_sessions": count}

@router.get("/", response_model=List[SessionOut])
async def list_all_sessions(skip: int = 0, limit: int = 10):
    sessions = await session_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for s in sessions:
        s["_id"] = str(s["_id"])
    return sessions

@router.get("/{session_id}", response_model=SessionOut)
async def get_session_by_id(session_id: str):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invali ID")
    session = await session_collection.find_one({"_id": ObjectId(session_id)})
    if session:
        session["_id"] = str(session["_id"])
        return session
    raise HTTPException(status_code=404, detail="Session not found")

@router.put("/{session_id}", response_model=SessionOut)
async def update_session(session_id: str, session: SessionCreate):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    if session.movie_id and not await movie_collection.find_one({"_id": ObjectId(session.movie_id)}):
        raise HTTPException(status_code=404, detail=f"Filme com ID {session.movie_id} não encontrado")
    if session.room_id and not await room_collection.find_one({"_id": ObjectId(session.room_id)}):
        raise HTTPException(status_code=404, detail=f"Sala com ID {session.room_id} não encontrada")
    updated_data = session.model_dump(exclude_unset=True)
    result = await session_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": updated_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.movie_id:
        await movie_collection.update_one(
            {"_id": ObjectId(session.movie_id)},
            {"$addToSet": {"session_ids": session_id}}
        )
    if session.room_id:
        await room_collection.update_one(
            {"_id": ObjectId(session.room_id)},
            {"$addToSet": {"session_ids": session_id}}
        )

    updated_session = await session_collection.find_one({"_id": ObjectId(session_id)})
    updated_session["_id"] = str(updated_session["_id"])
    return updated_session

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    exist = await session_collection.find_one({"_id": ObjectId(session_id)})
    if not exist:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await session_collection.delete_one({"_id": ObjectId(session_id)})
    
    await movie_collection.update_one(
        {"session_ids": session_id},
        {"$pull": {"session_ids": session_id}}
    )
    
    await room_collection.update_one(
        {"session_ids": session_id},
        {"$pull": {"session_ids": session_id}}
    )
    
    return {"detail": "Session deleted successfully"}



@router.get("/filter", response_model=List[SessionOut])
async def filter_sessions(
    exibition_type: Optional[str] = None,
    language_audio: Optional[str] = None,
    language_subtitles: Optional[str] = None,
    status_session: Optional[str] = None,
    room_id: Optional[str] = None,
    movie_id: Optional[str] = None,
    date_from: Optional[str] = None,  # formato: YYYY-MM-DD
    date_to: Optional[str] = None,    # formato: YYYY-MM-DD
    skip: int = 0,
    limit: int = 10
):
    filter_query = {}
    
    if exibition_type:
        filter_query["exibition_type"] = {"$regex": exibition_type, "$options": "i"}
    if language_audio:
        filter_query["language_audio"] = {"$regex": language_audio, "$options": "i"}
    if language_subtitles:
        filter_query["language_subtitles"] = {"$regex": language_subtitles, "$options": "i"}
    if status_session:
        filter_query["status_session"] = {"$regex": status_session, "$options": "i"}
    if room_id:
        if ObjectId.is_valid(room_id):
            filter_query["room_id"] = room_id
        else:
            raise HTTPException(status_code=400, detail="Invalid room ID")
    if movie_id:
        if ObjectId.is_valid(movie_id):
            filter_query["movie_id"] = movie_id
        else:
            raise HTTPException(status_code=400, detail="Invalid movie ID")
    
    # Filtro por data
    if date_from or date_to:
        date_filter = {}
        if date_from:
            try:
                from datetime import datetime
                date_filter["$gte"] = datetime.fromisoformat(date_from + "T00:00:00")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        if date_to:
            try:
                from datetime import datetime
                date_filter["$lte"] = datetime.fromisoformat(date_to + "T23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        filter_query["date_time"] = date_filter
    
    sessions = await session_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    for s in sessions:
        s["_id"] = str(s["_id"])
    return sessions