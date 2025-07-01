from fastapi import APIRouter, HTTPException, Query
from database import (
    movie_collection, 
    director_collection, 
    session_collection, 
    room_collection, 
    ticket_collection, 
    payment_collection
)
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
from utils import serialize_mongo_result
from logger import log_database_operation, log_business_rule_violation, logger, log_performance_metric
import time

router = APIRouter(prefix="/complex-queries", tags=["complex-queries"])

@router.get("/cinema-revenue-report")
async def get_cinema_revenue_report(
    date_from: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    room_id: Optional[str] = Query(None, description="ID da sala específica")
):
    """
    Consulta complexa que retorna relatório de faturamento do cinema
    Envolve 5 coleções: Sessions, Movies, Directors, Rooms, Tickets, Payments
    """
    filters = {"date_from": date_from, "date_to": date_to, "room_id": room_id}
    active_filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.info(f"Iniciando consulta complexa de relatório de faturamento com filtros: {active_filters}")
    
    try:
        # Validar room_id se fornecido
        if room_id and not ObjectId.is_valid(room_id):
            log_business_rule_violation(
                rule="INVALID_ROOM_ID",
                details="ID de sala inválido fornecido para relatório",
                data={"room_id": room_id, "filters": active_filters}
            )
            raise HTTPException(status_code=400, detail="Invalid room ID")
        
        start_time = time.time()
        
        # Pipeline de agregação complexa
        pipeline = [
            # Estágio 1: Filtrar sessões por data e sala (se especificado)
            {
                "$match": {
                    **({
                        "date_time": {
                            "$gte": datetime.fromisoformat(date_from + "T00:00:00") if date_from else datetime.min,
                            "$lte": datetime.fromisoformat(date_to + "T23:59:59") if date_to else datetime.max
                        }
                    } if date_from or date_to else {}),
                    **({"room_id": room_id} if room_id else {})
                }
            },
            
            # Estágio 2: Lookup para obter informações do filme
            {
                "$lookup": {
                    "from": "movies",
                    "let": {"movie_id": {"$toObjectId": "$movie_id"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$movie_id"]}}},
                        {
                            "$lookup": {
                                "from": "directors",
                                "let": {"director_ids": {"$map": {"input": "$director_ids", "as": "id", "in": {"$toObjectId": "$$id"}}}},
                                "pipeline": [
                                    {"$match": {"$expr": {"$in": ["$_id", "$$director_ids"]}}}
                                ],
                                "as": "directors"
                            }
                        }
                    ],
                    "as": "movie"
                }
            },
            
            # Estágio 3: Lookup para obter informações da sala
            {
                "$lookup": {
                    "from": "rooms",
                    "let": {"room_id": {"$toObjectId": "$room_id"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$room_id"]}}}
                    ],
                    "as": "room"
                }
            },
            
            # Estágio 4: Lookup para obter tickets da sessão
            {
                "$lookup": {
                    "from": "tickets",
                    "let": {"session_id": {"$toString": "$_id"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$session_id", "$$session_id"]}}},
                        {
                            "$lookup": {
                                "from": "payments",
                                "let": {"payment_id": {"$toObjectId": "$payment_details_id"}},
                                "pipeline": [
                                    {"$match": {"$expr": {"$eq": ["$_id", "$$payment_id"]}}}
                                ],
                                "as": "payment"
                            }
                        }
                    ],
                    "as": "tickets"
                }
            },
            
            # Estágio 5: Descompactar arrays
            {"$unwind": {"path": "$movie", "preserveNullAndEmptyArrays": True}},
            {"$unwind": {"path": "$room", "preserveNullAndEmptyArrays": True}},
            
            # Estágio 6: Calcular estatísticas
            {
                "$project": {
                    "_id": 1,
                    "session_date": "$date_time",
                    "movie_title": "$movie.movie_title",
                    "movie_genre": "$movie.genre",
                    "directors": "$movie.directors.director_name",
                    "room_name": "$room.room_name",
                    "room_capacity": "$room.capacity",
                    "total_tickets": {"$size": "$tickets"},
                    "tickets_sold": {
                        "$size": {
                            "$filter": {
                                "input": "$tickets",
                                "cond": {"$eq": ["$$this.payment_status", "pago"]}
                            }
                        }
                    },
                    "total_revenue": {
                        "$sum": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": "$tickets",
                                        "cond": {"$eq": ["$$this.payment_status", "pago"]}
                                    }
                                },
                                "as": "ticket",
                                "in": "$$ticket.ticket_price"
                            }
                        }
                    },
                    "occupancy_rate": {
                        "$multiply": [
                            {
                                "$divide": [
                                    {
                                        "$size": {
                                            "$filter": {
                                                "input": "$tickets",
                                                "cond": {"$eq": ["$$this.payment_status", "pago"]}
                                            }
                                        }
                                    },
                                    "$room.capacity"
                                ]
                            },
                            100
                        ]
                    }
                }
            },
            
            # Estágio 7: Ordenar por data
            {"$sort": {"session_date": -1}}
        ]
        
        result = await session_collection.aggregate(pipeline).to_list(length=None)
        
        # Converter ObjectId para string recursivamente
        result = serialize_mongo_result(result)
        
        # Calcular totais gerais
        total_revenue = sum(session.get("total_revenue", 0) for session in result)
        total_tickets_sold = sum(session.get("tickets_sold", 0) for session in result)
        average_occupancy = (
            sum(session.get("occupancy_rate", 0) for session in result) / len(result)
            if result else 0
        )
        
        return {
            "summary": {
                "total_sessions": len(result),
                "total_revenue": total_revenue,
                "total_tickets_sold": total_tickets_sold,
                "average_occupancy_rate": round(average_occupancy, 2)
            },
            "sessions": result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de data inválido: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


@router.get("/director-performance-analysis")
async def get_director_performance_analysis(
    min_movies: Optional[int] = Query(1, description="Número mínimo de filmes"),
    year_from: Optional[int] = Query(None, description="Ano inicial"),
    year_to: Optional[int] = Query(None, description="Ano final")
):
    """
    Consulta complexa que analisa a performance dos diretores
    Envolve 6 coleções: Directors, Movies, Sessions, Rooms, Tickets, Payments
    """
    try:
        # Pipeline de agregação para análise de diretores
        pipeline = [
            # Estágio 1: Filtrar filmes por ano (se especificado)
            {
                "$match": {
                    **({"release_year": {"$gte": year_from, "$lte": year_to}} if year_from or year_to else {})
                }
            },
            
            # Estágio 2: Lookup para obter sessões do filme
            {
                "$lookup": {
                    "from": "sessions",
                    "let": {"movie_id": {"$toString": "$_id"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$movie_id", "$$movie_id"]}}},
                        {
                            "$lookup": {
                                "from": "rooms",
                                "let": {"room_id": {"$toObjectId": "$room_id"}},
                                "pipeline": [
                                    {"$match": {"$expr": {"$eq": ["$_id", "$$room_id"]}}}
                                ],
                                "as": "room"
                            }
                        },
                        {"$unwind": "$room"},
                        {
                            "$lookup": {
                                "from": "tickets",
                                "let": {"session_id": {"$toString": "$_id"}},
                                "pipeline": [
                                    {"$match": {"$expr": {"$eq": ["$session_id", "$$session_id"]}}},
                                    {
                                        "$lookup": {
                                            "from": "payments",
                                            "let": {"payment_id": {"$toObjectId": "$payment_details_id"}},
                                            "pipeline": [
                                                {"$match": {"$expr": {"$eq": ["$_id", "$$payment_id"]}}}
                                            ],
                                            "as": "payment"
                                        }
                                    }
                                ],
                                "as": "tickets"
                            }
                        }
                    ],
                    "as": "sessions"
                }
            },
            
            # Estágio 3: Calcular métricas por filme
            {
                "$project": {
                    "movie_title": 1,
                    "genre": 1,
                    "release_year": 1,
                    "director_ids": 1,
                    "total_sessions": {"$size": "$sessions"},
                    "total_tickets_sold": {
                        "$sum": {
                            "$map": {
                                "input": "$sessions",
                                "as": "session",
                                "in": {
                                    "$size": {
                                        "$filter": {
                                            "input": "$$session.tickets",
                                            "cond": {"$eq": ["$$this.payment_status", "pago"]}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "total_revenue": {
                        "$sum": {
                            "$map": {
                                "input": "$sessions",
                                "as": "session",
                                "in": {
                                    "$sum": {
                                        "$map": {
                                            "input": {
                                                "$filter": {
                                                    "input": "$$session.tickets",
                                                    "cond": {"$eq": ["$$this.payment_status", "pago"]}
                                                }
                                            },
                                            "as": "ticket",
                                            "in": "$$ticket.ticket_price"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "average_occupancy": {
                        "$avg": {
                            "$map": {
                                "input": "$sessions",
                                "as": "session",
                                "in": {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                {
                                                    "$size": {
                                                        "$filter": {
                                                            "input": "$$session.tickets",
                                                            "cond": {"$eq": ["$$this.payment_status", "pago"]}
                                                        }
                                                    }
                                                },
                                                "$$session.room.capacity"
                                            ]
                                        },
                                        100
                                    ]
                                }
                            }
                        }
                    }
                }
            },
            
            # Estágio 4: Expandir director_ids para criar um documento por diretor
            {"$unwind": "$director_ids"},
            
            # Estágio 5: Lookup para obter informações do diretor
            {
                "$lookup": {
                    "from": "directors",
                    "let": {"director_id": {"$toObjectId": "$director_ids"}},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$_id", "$$director_id"]}}}
                    ],
                    "as": "director"
                }
            },
            {"$unwind": "$director"},
            
            # Estágio 6: Agrupar por diretor e calcular métricas
            {
                "$group": {
                    "_id": "$director._id",
                    "director_name": {"$first": "$director.director_name"},
                    "nationality": {"$first": "$director.nationality"},
                    "birth_date": {"$first": "$director.birth_date"},
                    "total_movies": {"$sum": 1},
                    "total_sessions": {"$sum": "$total_sessions"},
                    "total_tickets_sold": {"$sum": "$total_tickets_sold"},
                    "total_revenue": {"$sum": "$total_revenue"},
                    "average_occupancy": {"$avg": "$average_occupancy"},
                    "movies": {
                        "$push": {
                            "title": "$movie_title",
                            "genre": "$genre",
                            "release_year": "$release_year",
                            "sessions": "$total_sessions",
                            "tickets_sold": "$total_tickets_sold",
                            "revenue": "$total_revenue",
                            "occupancy": "$average_occupancy"
                        }
                    }
                }
            },
            
            # Estágio 7: Filtrar por número mínimo de filmes
            {"$match": {"total_movies": {"$gte": min_movies}}},
            
            # Estágio 8: Calcular métricas adicionais
            {
                "$project": {
                    "_id": 0,
                    "director_id": {"$toString": "$_id"},
                    "director_name": 1,
                    "nationality": 1,
                    "birth_date": 1,
                    "total_movies": 1,
                    "total_sessions": 1,
                    "total_tickets_sold": 1,
                    "total_revenue": {"$round": ["$total_revenue", 2]},
                    "average_occupancy": {"$round": ["$average_occupancy", 2]},
                    "revenue_per_movie": {"$round": [{"$divide": ["$total_revenue", "$total_movies"]}, 2]},
                    "tickets_per_movie": {"$round": [{"$divide": ["$total_tickets_sold", "$total_movies"]}, 2]},
                    "movies": 1
                }
            },
            
            # Estágio 9: Ordenar por receita total (descendente)
            {"$sort": {"total_revenue": -1}}
        ]
        
        result = await movie_collection.aggregate(pipeline).to_list(length=None)
        
        # Converter ObjectId para string recursivamente
        result = serialize_mongo_result(result)
        
        # Calcular estatísticas gerais
        total_directors = len(result)
        total_revenue_all = sum(director.get("total_revenue", 0) for director in result)
        total_tickets_all = sum(director.get("total_tickets_sold", 0) for director in result)
        
        return {
            "summary": {
                "total_directors_analyzed": total_directors,
                "total_revenue_generated": round(total_revenue_all, 2),
                "total_tickets_sold": total_tickets_all,
                "average_revenue_per_director": round(total_revenue_all / total_directors if total_directors > 0 else 0, 2)
            },
            "directors": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
