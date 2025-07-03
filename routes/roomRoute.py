from fastapi import APIRouter, HTTPException
from database import room_collection, session_collection
from models import RoomCreate, RoomOut
from typing import List, Optional
from bson import ObjectId
from logger import log_database_operation, log_business_rule_violation, logger
import time

router = APIRouter(prefix="/rooms", tags=["rooms"])

@router.post("/", response_model=RoomOut)
async def create_room(room: RoomCreate):
    logger.info(f"Iniciando criação de sala: {room.room_name}")
    
    if room.session_ids:
        logger.info(f"Validando {len(room.session_ids)} sessões para a sala")
        for session_id in room.session_ids:
            if not ObjectId.is_valid(session_id):
                log_business_rule_violation(
                    rule="INVALID_SESSION_ID",
                    details="ID de sessão inválido fornecido",
                    data={"session_id": session_id, "room_name": room.room_name}
                )
                raise HTTPException(status_code=400, detail="Invalid session ID")
            
            session = await session_collection.find_one({"_id": ObjectId(session_id)})
            if not session:
                log_business_rule_violation(
                    rule="SESSION_NOT_FOUND",
                    details="Sessão não encontrada durante criação de sala",
                    data={"session_id": session_id, "room_name": room.room_name}
                )
                raise HTTPException(status_code=404, detail="Session not found")
        logger.info(f"Todas as {len(room.session_ids)} sessões foram validadas com sucesso")
    
    room_dict = room.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await room_collection.insert_one(room_dict)
    insert_time = time.time() - start_time
    
    start_time = time.time()
    created = await room_collection.find_one({"_id": result.inserted_id})
    find_time = time.time() - start_time
    
    created["_id"] = str(created["_id"])
    
    log_database_operation(
        operation="insert",
        collection="rooms",
        operation_data={"room_name": room.room_name, "capacity": room.capacity},
        result={
            "inserted_id": str(result.inserted_id),
            "insert_time": f"{insert_time:.3f}s",
            "find_time": f"{find_time:.3f}s"
        }
    )
    logger.info(f"Sala {room.room_name} criada com sucesso. ID: {result.inserted_id}")
    return created
    
@router.get("/count")
async def get_rooms_count():
    logger.info("Consultando contagem total de salas")
    start_time = time.time()
    count = await room_collection.count_documents({})
    operation_time = time.time() - start_time
    
    log_database_operation(
        operation="count_documents",
        collection="rooms",
        result={"total_count": count, "execution_time": f"{operation_time:.3f}s"}
    )
    logger.info(f"Total de salas no sistema: {count}")
    return {"total_rooms": count}
    
@router.get("/", response_model=List[RoomOut])
async def list_all_rooms(skip: int = 0, limit: int = 10):
    logger.info(f"Listando salas com paginação: skip={skip}, limit={limit}")
    
    if limit > 100:
        log_business_rule_violation(
            rule="PAGINATION_LIMIT_EXCEEDED",
            details=f"Limite de {limit} excede o máximo permitido de 100",
            data={"requested_limit": limit, "max_allowed": 100}
        )
        limit = 100
        logger.warning(f"Limite ajustado para {limit} (máximo permitido)")
    
    start_time = time.time()
    rooms = await room_collection.find().skip(skip).limit(limit).to_list(length=limit)
    operation_time = time.time() - start_time
    
    for r in rooms:
        r["_id"] = str(r["_id"])
    
    log_database_operation(
        operation="find",
        collection="rooms",
        operation_data={"skip": skip, "limit": limit},
        result={"rooms_found": len(rooms), "execution_time": f"{operation_time:.3f}s"}
    )
    logger.info(f"Retornadas {len(rooms)} salas")
    return rooms

@router.get("/{room_id}", response_model=RoomOut)
async def find_room_by_id(room_id: str):
    logger.info(f"Buscando sala por ID: {room_id}")
    
    if not ObjectId.is_valid(room_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de sala fornecido não é um ObjectId válido",
            data={"provided_id": room_id}
        )
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    start_time = time.time()
    room = await room_collection.find_one({"_id": ObjectId(room_id)})
    operation_time = time.time() - start_time
    
    if room:
        room["_id"] = str(room["_id"])
        log_database_operation(
            operation="find_one",
            collection="rooms",
            operation_data={"room_id": room_id},
            result={"found": True, "room_name": room.get("room_name"), "execution_time": f"{operation_time:.3f}s"}
        )
        logger.info(f"Sala encontrada: {room.get('room_name')}")
        return room
    else:
        log_database_operation(
            operation="find_one",
            collection="rooms",
            operation_data={"room_id": room_id},
            result={"found": False, "execution_time": f"{operation_time:.3f}s"}
        )
        logger.warning(f"Sala não encontrada para ID: {room_id}")
        raise HTTPException(status_code=404, detail="Room not found")

@router.put("/{room_id}", response_model=RoomOut)
async def update_room(room_id: str, room: RoomCreate):
    logger.info(f"Iniciando atualização da sala ID: {room_id}")
    
    if not ObjectId.is_valid(room_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de sala fornecido não é um ObjectId válido",
            data={"provided_id": room_id}
        )
        raise HTTPException(status_code=400, detail="Invalid room ID")
    
    if room.session_ids:
        logger.info(f"Validando {len(room.session_ids)} sessões para atualização")
        for session_id in room.session_ids:
            if not ObjectId.is_valid(session_id):
                log_business_rule_violation(
                    rule="INVALID_SESSION_ID",
                    details="ID de sessão inválido fornecido na atualização",
                    data={"session_id": session_id, "room_id": room_id}
                )
                raise HTTPException(status_code=400, detail="Invalid session ID")
            
            session = await session_collection.find_one({"_id": ObjectId(session_id)})
            if not session:
                log_business_rule_violation(
                    rule="SESSION_NOT_FOUND",
                    details="Sessão não encontrada durante atualização",
                    data={"session_id": session_id, "room_id": room_id}
                )
                raise HTTPException(status_code=404, detail="Session not found")
        logger.info("Todas as sessões foram validadas com sucesso")
    
    updated_data = room.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await room_collection.update_one(
        {"_id": ObjectId(room_id)},
        {"$set": updated_data}
    )
    operation_time = time.time() - start_time
    
    if result.matched_count == 0:
        log_database_operation(
            operation="update_one",
            collection="rooms",
            operation_data={"room_id": room_id, "update_data": updated_data},
            result={"matched_count": 0, "execution_time": f"{operation_time:.3f}s"}
        )
        logger.warning(f"Nenhuma sala encontrada para atualização. ID: {room_id}")
        raise HTTPException(status_code=404, detail="Room not found")
    
    start_time = time.time()
    updated = await room_collection.find_one({"_id": ObjectId(room_id)})
    find_time = time.time() - start_time
    
    updated["_id"] = str(updated["_id"])
    
    log_database_operation(
        operation="update_one",
        collection="rooms",
        operation_data={"room_id": room_id, "fields_updated": list(updated_data.keys())},
        result={
            "modified_count": result.modified_count,
            "room_name": updated.get("room_name"),
            "execution_time": f"{operation_time:.3f}s",
            "find_time": f"{find_time:.3f}s"
        }
    )
    logger.info(f"Sala {updated.get('room_name')} atualizada com sucesso")
    return updated
    
@router.delete("/{room_id}")
async def delete_room(room_id: str):
    logger.info(f"Iniciando exclusão da sala ID: {room_id}")
    
    if not ObjectId.is_valid(room_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de sala fornecido não é um ObjectId válido",
            data={"provided_id": room_id}
        )
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    start_time = time.time()
    exists = await room_collection.find_one({"_id": ObjectId(room_id)})
    find_time = time.time() - start_time
    
    if not exists:
        log_database_operation(
            operation="delete_one",
            collection="rooms",
            operation_data={"room_id": room_id},
            result={"deleted": False, "reason": "not_found", "find_time": f"{find_time:.3f}s"}
        )
        logger.warning(f"Tentativa de excluir sala inexistente. ID: {room_id}")
        raise HTTPException(status_code=404, detail="Room not found")
    
    room_name = exists.get("room_name", "Número não disponível")
    logger.info(f"Sala encontrada para exclusão: {room_name}")
    
    start_time = time.time()
    await room_collection.delete_one({"_id": ObjectId(room_id)})
    delete_time = time.time() - start_time
    
    log_database_operation(
        operation="delete_one",
        collection="rooms",
        operation_data={"room_id": room_id, "room_name": room_name},
        result={
            "deleted": True,
            "find_time": f"{find_time:.3f}s",
            "delete_time": f"{delete_time:.3f}s"
        }
    )
    logger.info(f"Sala {room_name} excluída com sucesso")
    return {"detail": "Room deleted successfully"}



@router.get("/filter", response_model=List[RoomOut])
async def filter_rooms(
    room_name: Optional[str] = None,
    screen_type: Optional[str] = None,
    audio_system: Optional[str] = None,
    accessibility: Optional[bool] = None,
    min_capacity: Optional[int] = None,
    max_capacity: Optional[int] = None,
    skip: int = 0,
    limit: int = 10
):
    filters = {
        "room_name": room_name,
        "screen_type": screen_type,
        "audio_system": audio_system,
        "accessibility": accessibility,
        "min_capacity": min_capacity,
        "max_capacity": max_capacity
    }
    active_filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.info(f"Filtrando salas com critérios: {active_filters}, skip={skip}, limit={limit}")
    
    if limit > 100:
        log_business_rule_violation(
            rule="PAGINATION_LIMIT_EXCEEDED",
            details=f"Limite de {limit} excede o máximo permitido de 100 para filtros",
            data={"requested_limit": limit, "max_allowed": 100, "filters": active_filters}
        )
        limit = 100
        logger.warning(f"Limite ajustado para {limit} (máximo permitido)")
    
    filter_query = {}
    
    if room_name:
        filter_query["room_name"] = {"$regex": room_name, "$options": "i"}
    if screen_type:
        filter_query["screen_type"] = {"$regex": screen_type, "$options": "i"}
    if audio_system:
        filter_query["audio_system"] = {"$regex": audio_system, "$options": "i"}
    if accessibility is not None:
        filter_query["acessibility"] = accessibility
    if min_capacity is not None or max_capacity is not None:
        capacity_filter = {}
        if min_capacity is not None:
            capacity_filter["$gte"] = min_capacity
        if max_capacity is not None:
            capacity_filter["$lte"] = max_capacity
        filter_query["capacity"] = capacity_filter
    
    start_time = time.time()
    rooms = await room_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    operation_time = time.time() - start_time
    
    for r in rooms:
        r["_id"] = str(r["_id"])
    
    log_database_operation(
        operation="find_with_filter",
        collection="rooms",
        operation_data={
            "filter_query": filter_query,
            "skip": skip,
            "limit": limit,
            "active_filters_count": len(active_filters)
        },
        result={
            "rooms_found": len(rooms),
            "execution_time": f"{operation_time:.3f}s"
        }
    )
    logger.info(f"Filtro retornou {len(rooms)} salas com {len(active_filters)} critérios aplicados")
    return rooms