from fastapi import APIRouter, HTTPException
from database import payment_collection, ticket_collection
from models import PaymentDetailsCreate, PaymentDetailsOut
from typing import List, Optional
from bson import ObjectId
from logger import log_database_operation, log_business_rule_violation, logger
import time

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/", response_model=PaymentDetailsOut)
async def create_payment_detail(payment: PaymentDetailsCreate):
    logger.info(f"Iniciando criação de pagamento. Método: {payment.payment_method}, Valor: {payment.final_price}")
    
    if payment.ticket_id:
        logger.info(f"Validando ticket ID: {payment.ticket_id}")
        if not ObjectId.is_valid(payment.ticket_id):
            log_business_rule_violation(
                rule="INVALID_TICKET_ID",
                details="ID de ticket inválido fornecido",
                data={"ticket_id": payment.ticket_id, "payment_method": payment.payment_method}
            )
            raise HTTPException(status_code=400, detail="Invalid ID")
        
        ticket = await ticket_collection.find_one({"_id": ObjectId(payment.ticket_id)})
        if not ticket:
            log_business_rule_violation(
                rule="TICKET_NOT_FOUND",
                details="Ticket não encontrado durante criação de pagamento",
                data={"ticket_id": payment.ticket_id, "payment_method": payment.payment_method}
            )
            raise HTTPException(status_code=404, detail="Ticket not found")
        logger.info(f"Ticket validado com sucesso: {ticket.get('seat_number')}")
    
    payment_dict = payment.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await payment_collection.insert_one(payment_dict)
    insert_time = time.time() - start_time
    
    new_payment_id = result.inserted_id
    
    log_database_operation(
        operation="insert",
        collection="payments",
        operation_data={
            "payment_method": payment.payment_method,
            "final_price": payment.final_price,
            "ticket_id": payment.ticket_id
        },
        result={
            "inserted_id": str(new_payment_id),
            "insert_time": f"{insert_time:.3f}s"
        }
    )
    
    # Atualizar ticket com pagamento
    if payment.ticket_id:
        start_time = time.time()
        await ticket_collection.update_one(
            {"_id": ObjectId(payment.ticket_id)},
            {"$set": {"payment_details_id": str(new_payment_id)}}
        )
        update_time = time.time() - start_time
        
        log_database_operation(
            operation="update_one",
            collection="tickets",
            operation_data={"ticket_id": payment.ticket_id, "payment_id": str(new_payment_id)},
            result={"update_time": f"{update_time:.3f}s"}
        )
    
    # Buscar pagamento criado
    start_time = time.time()
    created = await payment_collection.find_one({"_id": new_payment_id})
    find_time = time.time() - start_time
    
    if created:
        created["_id"] = str(created["_id"])
        logger.info(f"Pagamento criado com sucesso. ID: {new_payment_id}, Método: {payment.payment_method}, Valor: {payment.final_price}")
        return created
    else:
        logger.error(f"Falha ao recuperar pagamento criado. ID: {new_payment_id}")
        raise HTTPException(status_code=500, detail="Failed to create payment")
        
@router.get("/count")
async def get_payments_count():
    count = await payment_collection.count_documents({})
    return {"total_payments": count}

@router.get("/", response_model=List[PaymentDetailsOut])
async def list_all_payments(skip: int = 0, limit: int = 10):
    payments = await payment_collection.find().skip(skip).limit(limit).to_list(length=limit)
    for p in payments:
        p["_id"] = str(p["_id"])
    return payments

@router.get("/{payment_id}", response_model=PaymentDetailsOut)
async def get_payment_by_id(payment_id: str):
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    payment = await payment_collection.find_one({"_id": ObjectId(payment_id)})
    if payment:
        payment["_id"] = str(payment["_id"])
        return payment
    raise HTTPException(status_code=404, detail="Payment not found")
    
@router.put("/{payment_id}", response_model=PaymentDetailsOut)
async def update_payment(payment_id: str, payment: PaymentDetailsCreate):
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid payment ID")
    
    if payment.ticket_id:
        if not ObjectId.is_valid(payment.ticket_id):
            raise HTTPException(status_code=400, detail="Invalid Ticket ID")
        ticket = await ticket_collection.find_one({"_id": ObjectId(payment.ticket_id)})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
    
    updated_data = payment.model_dump(exclude_unset=True)
    result = await payment_collection.update_one(
        {"_id": ObjectId(payment_id)},
        {"$set": updated_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    updated = await payment_collection.find_one({"_id": ObjectId(payment_id)})
    if updated:
        updated["_id"] = str(updated["_id"])
        return updated
    else:
        raise HTTPException(status_code=500, detail="Failed to update payment")

@router.delete("/{payment_id}")
async def delete_payment(payment_id: str):
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    payment = await payment_collection.find_one({"_id": ObjectId(payment_id)})
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    delete_result = await payment_collection.delete_one({"_id": ObjectId(payment_id)})
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.get("ticket_id"):
        await ticket_collection.update_one(
            {"_id": ObjectId(payment["ticket_id"])},
            {"$unset": {"payment_details_id": ""}}
        )
    
    return {"detail": "Payment deleted successfully"}


@router.get("/filter", response_model=List[PaymentDetailsOut])
async def filter_payments(
    transaction_id: Optional[str] = None,
    payment_method: Optional[str] = None,
    status: Optional[str] = None,
    ticket_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    date_from: Optional[str] = None,  # formato: YYYY-MM-DD
    date_to: Optional[str] = None,    # formato: YYYY-MM-DD
    skip: int = 0,
    limit: int = 10
):
    filter_query = {}
    
    if transaction_id:
        filter_query["transaction_id"] = {"$regex": transaction_id, "$options": "i"}
    if payment_method:
        filter_query["payment_method"] = {"$regex": payment_method, "$options": "i"}
    if status:
        filter_query["status"] = {"$regex": status, "$options": "i"}
    if ticket_id:
        if ObjectId.is_valid(ticket_id):
            filter_query["ticket_id"] = ticket_id
        else:
            raise HTTPException(status_code=400, detail="Invalid ticket ID")
    
    # Filtro por preço
    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filter_query["final_price"] = price_filter
    
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
        filter_query["payment_date"] = date_filter
    
    payments = await payment_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    for p in payments:
        p["_id"] = str(p["_id"])
    return payments