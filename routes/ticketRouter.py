from fastapi import APIRouter, HTTPException
from database import ticket_collection, payment_collection, session_collection
from models import TicketCreate, TicketOut
from typing import List, Optional
from bson import ObjectId
from logger import log_database_operation, log_business_rule_violation, logger
import time

router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.post("/", response_model=TicketOut)
async def create_ticket(ticket: TicketCreate):
    logger.info(f"Iniciando criação de ticket. Assento: {ticket.seat_number}")
    
    # Validar sessão
    if ticket.session_id:
        logger.info(f"Validando sessão ID: {ticket.session_id}")
        if not ObjectId.is_valid(ticket.session_id):
            log_business_rule_violation(
                rule="INVALID_SESSION_ID",
                details="ID de sessão inválido fornecido",
                data={"session_id": ticket.session_id, "seat_number": ticket.seat_number}
            )
            raise HTTPException(status_code=400, detail="Invalid session ID")
        
        session = await session_collection.find_one({"_id": ObjectId(ticket.session_id)})
        if not session:
            log_business_rule_violation(
                rule="SESSION_NOT_FOUND",
                details="Sessão não encontrada durante criação de ticket",
                data={"session_id": ticket.session_id, "seat_number": ticket.seat_number}
            )
            raise HTTPException(status_code=404, detail="Session not found")
        logger.info("Sessão validada com sucesso")
    
    # Validar pagamento
    if ticket.payment_details_id:
        logger.info(f"Validando pagamento ID: {ticket.payment_details_id}")
        if not ObjectId.is_valid(ticket.payment_details_id):
            log_business_rule_violation(
                rule="INVALID_PAYMENT_ID",
                details="ID de pagamento inválido fornecido",
                data={"payment_id": ticket.payment_details_id, "seat_number": ticket.seat_number}
            )
            raise HTTPException(status_code=400, detail="Invalid payment ID")
        
        payment = await payment_collection.find_one({"_id": ObjectId(ticket.payment_details_id)})
        if not payment:
            log_business_rule_violation(
                rule="PAYMENT_NOT_FOUND",
                details="Pagamento não encontrado durante criação de ticket",
                data={"payment_id": ticket.payment_details_id, "seat_number": ticket.seat_number}
            )
            raise HTTPException(status_code=404, detail="Payment not found")
        logger.info("Pagamento validado com sucesso")
    
    # Criar ticket
    ticket_dict = ticket.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await ticket_collection.insert_one(ticket_dict)
    insert_time = time.time() - start_time
    
    new_ticket_id = result.inserted_id
    
    log_database_operation(
        operation="insert",
        collection="tickets",
        operation_data={
            "seat_number": ticket.seat_number,
            "session_id": ticket.session_id,
            "payment_details_id": ticket.payment_details_id
        },
        result={
            "inserted_id": str(new_ticket_id),
            "insert_time": f"{insert_time:.3f}s"
        }
    )

    # Atualizar sessão com ticket
    if ticket.session_id:
        start_time = time.time()
        await session_collection.update_one(
            {"_id": ObjectId(ticket.session_id)},
            {"$push": {"ticket_ids": str(new_ticket_id)}}
        )
        session_update_time = time.time() - start_time
        
        log_database_operation(
            operation="update_one",
            collection="sessions",
            operation_data={"session_id": ticket.session_id, "ticket_id": str(new_ticket_id)},
            result={"update_time": f"{session_update_time:.3f}s"}
        )
    
    # Atualizar pagamento com ticket
    if ticket.payment_details_id:
        start_time = time.time()
        await payment_collection.update_one(
            {"_id": ObjectId(ticket.payment_details_id)},
            {"$set": {"ticket_id": str(new_ticket_id)}}
        )
        payment_update_time = time.time() - start_time
        
        log_database_operation(
            operation="update_one",
            collection="payments",
            operation_data={"payment_id": ticket.payment_details_id, "ticket_id": str(new_ticket_id)},
            result={"update_time": f"{payment_update_time:.3f}s"}
        )

    # Buscar ticket criado
    start_time = time.time()
    created = await ticket_collection.find_one({"_id": new_ticket_id})
    find_time = time.time() - start_time
    
    if created:
        created["_id"] = str(created["_id"])
        logger.info(f"Ticket criado com sucesso. ID: {new_ticket_id}, Assento: {ticket.seat_number}")
        return created
    else:
        logger.error(f"Falha ao recuperar ticket criado. ID: {new_ticket_id}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")
    
@router.get("/count")
async def get_tickets_count():
    count = await ticket_collection.count_documents({})
    return {"total_tickets": count}

@router.get("/", response_model=List[TicketOut])
async def list_all_tickets(skip: int = 0, limit: int = 10):
    tickets = await ticket_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for t in tickets:
        t["_id"] = str(t["_id"])
    return tickets

@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket_by_id(ticket_id: str):
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    ticket = await ticket_collection.find_one({"_id": ObjectId(ticket_id)})
    if ticket:
        ticket["_id"] = str(ticket["_id"])
        return ticket
    raise HTTPException(status_code=404, detail="Ticket not found")

@router.put("/{ticket_id}", response_model=TicketOut)
async def update_ticket(ticket_id: str, ticket: TicketCreate):
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=400, detail="Invalid ticket ID")
    
    if ticket.session_id:
        if not ObjectId.is_valid(ticket.session_id):
            raise HTTPException(status_code=400, detail="Invalid session ID")
        session = await session_collection.find_one({"_id": ObjectId(ticket.session_id)})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    
    if ticket.payment_details_id:
        if not ObjectId.is_valid(ticket.payment_details_id):
            raise HTTPException(status_code=400, detail="Invalid payment ID")
        payment = await payment_collection.find_one({"_id": ObjectId(ticket.payment_details_id)})
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
    
    updated_data = ticket.model_dump(exclude_unset=True)
    result = await ticket_collection.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": updated_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    updated = await ticket_collection.find_one({"_id": ObjectId(ticket_id)})
    if updated:
        updated["_id"] = str(updated["_id"])
        return updated
    else:
        raise HTTPException(status_code=500, detail="Failed to update ticket")

@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: str):
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    # Buscar o ticket para obter as referências antes de deletar
    ticket = await ticket_collection.find_one({"_id": ObjectId(ticket_id)})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Deletar o ticket
    delete_result = await ticket_collection.delete_one({"_id": ObjectId(ticket_id)})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Remover referência do ticket da sessão
    if ticket.get("session_id"):
        await session_collection.update_one(
            {"_id": ObjectId(ticket["session_id"])},
            {"$pull": {"ticket_ids": ticket_id}}
        )
    
    # Deletar o pagamento associado ao ticket (se existir)
    if ticket.get("payment_details_id"):
        await payment_collection.delete_one(
            {"_id": ObjectId(ticket["payment_details_id"])}
        )
    
    return {"detail": "Ticket and associated payment deleted successfully"}



@router.get("/filter", response_model=List[TicketOut])
async def filter_tickets(
    chair_number: Optional[int] = None,
    ticket_type: Optional[str] = None,
    payment_status: Optional[str] = None,
    session_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
):
    filter_query = {}
    
    if chair_number is not None:
        filter_query["chair_number"] = chair_number
    if ticket_type:
        filter_query["ticket_type"] = {"$regex": ticket_type, "$options": "i"}
    if payment_status:
        filter_query["payment_status"] = {"$regex": payment_status, "$options": "i"}
    if session_id:
        if ObjectId.is_valid(session_id):
            filter_query["session_id"] = session_id
        else:
            raise HTTPException(status_code=400, detail="Invalid session ID")
    
    tickets = await ticket_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    for t in tickets:
        t["_id"] = str(t["_id"])
    return tickets
