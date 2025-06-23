from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from pydantic import BaseModel, Field

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, *args, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("ID inválido")
        return str(v)

class DirectorBase(BaseModel):
    director_name: str
    nationality: str
    birth_date: str
    biography: str
    website: str
    movie_ids: List[str] = []

class DirectorCreate(DirectorBase):
    pass

class DirectorOut(DirectorBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

class MovieBase(BaseModel):
    movie_title: str
    genre: str
    duration: int
    rating: str
    synopsis: str
    release_year: Optional[int] = None
    director_ids: List[str] = []
    session_ids: List[str] = []

class MovieCreate(MovieBase):
    pass

class MovieOut(MovieBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

class RoomBase(BaseModel):
    room_name: str
    capacity: int
    screen_type: str
    audio_system: str
    acessibility: bool
    session_ids: List[str] = []

class RoomCreate(RoomBase):
    pass

class RoomOut(RoomBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
         
class SessionBase(BaseModel):
    date_time: datetime
    exibition_type: str
    language_audio: str
    language_subtitles: str
    status_session: str
    room_id: str
    movie_id: str
    ticket_ids: List[str] = []

class SessionCreate(SessionBase):
    pass

class SessionOut(SessionBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True 

class PaymentDetailsBase(BaseModel):
    transaction_id: str
    payment_method: str
    final_price: float
    status: str
    payment_date: datetime
    ticket_id: str

class PaymentDetailsCreate(PaymentDetailsBase):
    pass

class PaymentDetailsOut(PaymentDetailsBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True

class TicketBase(BaseModel):
    chair_number: int
    ticket_type: str
    ticket_price: float
    purchase_date: datetime
    payment_status: str
    session_id: str 
    payment_details_id: Optional[str] = None

class TicketCreate(TicketBase):
    pass

class TicketOut(TicketBase):
    id: Optional[str] = Field(default=None, alias="_id")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True