from fastapi import APIRouter, HTTPException, Query
from database import session_collection, movie_collection, director_collection
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/movies-with-directors-and-sessions")
async def get_movies_with_directors_and_sessions():
    """
    Retorna uma lista de filmes com informações dos diretores e sessões agendadas.
    """
    pipeline = [
        # 1. Converte director_ids de string para ObjectId
        {
            "$addFields": {
                "director_object_ids": {
                    "$map": {
                        "input": "$director_ids",
                        "as": "directorId",
                        "in": {"$toObjectId": "$$directorId"}
                    }
                }
            }
        },
        
        # 2. Junta com a coleção de diretores
        {
            "$lookup": {
                "from": "directors",
                "localField": "director_object_ids",
                "foreignField": "_id",
                "as": "directors"
            }
        },
        
        # 3. Junta com a coleção de sessões (converte movie_id para ObjectId)
        {
            "$lookup": {
                "from": "sessions",
                "let": {"movie_id": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$eq": [{"$toObjectId": "$movie_id"}, "$$movie_id"]
                            }
                        }
                    }
                ],
                "as": "sessions"
            }
        },
        
        # 4. Projeta os campos desejados
        {
            "$project": {
                "_id": 0,
                "movie_id": {"$toString": "$_id"},
                "movie_title": 1,
                "genre": 1,
                "duration": 1,
                "release_year": 1,
                "directors": {
                    "$map": {
                        "input": "$directors",
                        "as": "director",
                        "in": {
                            "name": "$$director.director_name",
                            "nationality": "$$director.nationality"
                        }
                    }
                },
                "total_sessions": {"$size": "$sessions"},
                "upcoming_sessions": {
                    "$size": {
                        "$filter": {
                            "input": "$sessions",
                            "as": "session",
                            "cond": {"$gte": ["$$session.date_time", "$$NOW"]}
                        }
                    }
                }
            }
        },
        
        # 5. Ordena por título do filme
        {"$sort": {"movie_title": 1}}
    ]
    
    movies = await movie_collection.aggregate(pipeline).to_list(length=None)
    return movies

@router.get("/revenue-report")
async def get_revenue_report(
    date_from: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)")
):
    match_filter = {}
    if date_from or date_to:
        date_filter = {}
        if date_from:
            try:
                date_filter["$gte"] = datetime.fromisoformat(date_from + "T00:00:00")
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
        if date_to:
            try:
                date_filter["$lte"] = datetime.fromisoformat(date_to + "T23:59:59")
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
        match_filter["date_time"] = date_filter

    pipeline = [
        # 1. Filtra as sessões pelo período desejado(é tipo um WHERE do SQL)
        {"$match": match_filter},
        
        # 2. Converte os `ticket_ids` de string para ObjectId para o lookup
        {
            "$addFields": {
                "ticket_object_ids": {
                    "$map": {
                        "input": "$ticket_ids",
                        "as": "ticketId",
                        "in": {"$toObjectId": "$$ticketId"}
                    }
                }
            }
        },

        # 3. Junta com a coleção de tickets(é tipo o LEFT JOIN)
        {
            "$lookup": {
                "from": "tickets",
                "localField": "ticket_object_ids",
                "foreignField": "_id",
                "as": "ticket_details"
            }
        },
        
        # 4. Junta com a coleção de filmes
        {
            "$lookup": {
                "from": "movies",
                "localField": "movie_id",
                "foreignField": "_id",
                "as": "movie_info"
            }
        },
        
        # 5. Junta com a coleção de salas
        {
            "$lookup": {
                "from": "rooms",
                "localField": "room_id",
                "foreignField": "_id",
                "as": "room_info"
            }
        },
        
        # 6. Desconstrói os arrays resultantes para facilitar o acesso
        {"$unwind": {"path": "$movie_info", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$room_info", "preserveNullAndEmptyArrays": True}},
        
        # 7. Projeta os campos finais e CALCULA a receita
        {
            "$project": {
                "_id": 0,
                "session_id": {"$toString": "$_id"},
                "session_date": "$date_time",
                "movie_title": "$movie_info.movie_title",
                "room_name": "$room_info.room_name",
                "tickets_sold": {"$size": "$ticket_details"},
                "total_revenue": {"$sum": "$ticket_details.ticket_price"}
            }
        },
        
        {"$sort": {"session_date": 1}}
    ]

    sessions = await session_collection.aggregate(pipeline).to_list(length=None)
    return sessions


