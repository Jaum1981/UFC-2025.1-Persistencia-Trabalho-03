from fastapi import APIRouter, HTTPException
from database import payment_collection, ticket_collection
from models import PaymentDetailsCreate, PaymentDetailsOut
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/payments")

@router.post("/", response_model=PaymentDetailsOut)
async def create_payment_detail(payment: PaymentDetailsCreate):
    if payment.ticket_id:
        if not ObjectId.is_valid(payment.ticket_id):
            raise HTTPException(status_code=400, detail="Invalid ID")
        ticket = await ticket_collection.find_one({"_id": ObjectId(payment.ticket_id)})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
    
    payment_dict = payment.model_dump(exclude_unset=True)
    result = await payment_collection.insert_one(payment_dict)
    new_payment_id = result.inserted_id
    
    if payment.ticket_id:
        await ticket_collection.update_one(
            {"_id": ObjectId(payment.ticket_id)},
            {"$set": {"payment_details_id": str(new_payment_id)}}
        )
    
    created = await payment_collection.find_one({"_id": new_payment_id})
    if created:
        created["_id"] = str(created["_id"])
        return created
    else:
        raise HTTPException(status_code=500, detail="Failed to create payment")
        
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