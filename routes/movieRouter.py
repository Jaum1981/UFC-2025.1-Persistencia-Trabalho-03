from fastapi import APIRouter, HTTPException
from database import movie_collection
from models import MovieCreate, MovieOut
from typing import List
from bson import ObjectId

router = APIRouter(prefix="/movies")