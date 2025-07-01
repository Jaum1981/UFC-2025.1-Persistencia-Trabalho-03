from fastapi import APIRouter, HTTPException
from database import ticket_collection, payment_collection, session_collection
from models import TicketCreate, TicketOut
from typing import List, Optional
from bson import ObjectId

router = APIRouter(prefix="/tickets")

@router.post("/", response_model=TicketOut)
async def create_ticket(ticket: TicketCreate):
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
    
    ticket_dict = ticket.model_dump(exclude_unset=True)
    result = await ticket_collection.insert_one(ticket_dict)
    new_ticket_id = result.inserted_id

    if ticket.session_id:
        await session_collection.update_one(
            {"_id": ObjectId(ticket.session_id)},
            {"$push": {"ticket_ids": str(new_ticket_id)}}
        )
    if ticket.payment_details_id:
        await payment_collection.update_one(
            {"_id": ObjectId(ticket.payment_details_id)},
            {"$set": {"ticket_id": str(new_ticket_id)}}
        )

    created = await ticket_collection.find_one({"_id": new_ticket_id})
    if created:
        created["_id"] = str(created["_id"])
        return created
    else:
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
