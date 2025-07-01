from fastapi import APIRouter, HTTPException
from database import room_collection, session_collection
from models import RoomCreate, RoomOut
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/rooms")

@router.post("/", response_model=RoomOut)
async def create_room(room: RoomCreate):
    if room.session_ids:
        for session_id in room.session_ids:
            if not ObjectId.is_valid(session_id):
                raise HTTPException(status_code=400, detail="Invalid session ID")
            session = await session_collection.find_one({"_id": ObjectId(session_id)})
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
    room_dict = room.model_dump(exclude_unset=True)
    result = await room_collection.insert_one(room_dict)
    created = await room_collection.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created
    
    
@router.get("/", response_model=List[RoomOut])
async def list_all_rooms(skip: int = 0, limit: int = 10):
    rooms = await room_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for r in rooms:
        r["_id"] = str(r["_id"])
    return rooms

@router.get("/{room_id}", response_model=RoomOut)
async def find_room_by_id(room_id: str):
    if not ObjectId.is_valid(room_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    room = await room_collection.find_one({"_id": ObjectId(room_id)})
    if room:
        room["_id"] = str(room["_id"])
        return room
    raise HTTPException(status_code=404, detail="Room not found")

@router.put("/{room_id}", response_model=RoomOut)
async def update_room(room_id: str, room: RoomCreate):
    if not ObjectId.is_valid(room_id):
        raise HTTPException(status_code=400, detail="Invalid room ID")
    if room.session_ids:
        for session_id in room.session_ids:
            if not ObjectId.is_valid(session_id):
                raise HTTPException(status_code=400, detail="Invalid session ID")
            session = await session_collection.find_one({"_id": ObjectId(session_id)})
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
    
    updated_data = room.model_dump(exclude_unset=True)
    result = await room_collection.update_one(
        {"_id": ObjectId(room_id)},
        {"$set": updated_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room not found")
    updated = await room_collection.find_one({"_id": ObjectId(room_id)})
    updated["_id"] = str(updated["_id"])
    return updated
    
@router.delete("/{room_id}")
async def delete_room(room_id: str):
    if not ObjectId.is_valid(room_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    exists = await room_collection.find_one({"_id": ObjectId(room_id)})
    if not exists:
        raise HTTPException(status_code=404, detail="Room not found")
    
    await room_collection.delete_one({"_id": ObjectId(room_id)})
    return {
        "detail": "Room deleted successfully"
    }