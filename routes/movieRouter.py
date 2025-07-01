from fastapi import APIRouter, HTTPException
from database import movie_collection, director_collection
from models import MovieCreate, MovieOut
from typing import List, Optional
from bson import ObjectId
from logger import log_database_operation, log_business_rule_violation, logger
import time

router = APIRouter(prefix="/movies", tags=["movies"])

@router.post("/", response_model=MovieOut)
async def create_movie(movie: MovieCreate):
    logger.info(f"Iniciando criação de filme: {movie.movie_title}")
    
    if movie.director_ids:
        logger.info(f"Validando {len(movie.director_ids)} diretores para o filme")
        try:
            director_obj_ids = [ObjectId(d_id) for d_id in movie.director_ids]
        except Exception as e:
            log_business_rule_violation(
                rule="INVALID_DIRECTOR_ID",
                details="IDs de diretor inválidos fornecidos",
                data={"director_ids": movie.director_ids, "error": str(e)}
            )
            raise HTTPException(status_code=400, detail="Um ou mais IDs de diretor são inválidos")
        
        num_directors_found = await director_collection.count_documents({"_id": {"$in": director_obj_ids}})
        if num_directors_found != len(movie.director_ids):
            log_business_rule_violation(
                rule="DIRECTOR_NOT_FOUND",
                details=f"Esperados {len(movie.director_ids)} diretores, encontrados {num_directors_found}",
                data={"requested_directors": movie.director_ids, "found_count": num_directors_found}
            )
            raise HTTPException(status_code=404, detail="Um ou mais diretores não foram encontrados")
        
        logger.info(f"Todos os {len(movie.director_ids)} diretores foram validados com sucesso")
    
    # Inserção do filme
    movie_dict = movie.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await movie_collection.insert_one(movie_dict)
    operation_time = time.time() - start_time
    
    new_movie_id = result.inserted_id
    log_database_operation(
        operation="insert",
        collection="movies",
        operation_data={"movie_title": movie.movie_title, "genre": movie.genre},
        result={"inserted_id": str(new_movie_id), "execution_time": f"{operation_time:.3f}s"}
    )
    
    # Associação com diretores
    if movie.director_ids:
        try:
            start_time = time.time()
            await director_collection.update_many(
                {"_id": {"$in": director_obj_ids}},
                {"$push": {"movie_ids": str(new_movie_id)}}
            )
            operation_time = time.time() - start_time
            
            log_database_operation(
                operation="update_many",
                collection="directors",
                operation_data={"directors_updated": len(movie.director_ids), "movie_id": str(new_movie_id)},
                result={"execution_time": f"{operation_time:.3f}s"}
            )
            logger.info(f"Filme {movie.movie_title} associado com sucesso aos diretores")
        except Exception as e:
            logger.error(f"Erro ao associar filme aos diretores: {e}")
            # Reverter operação
            await movie_collection.delete_one({"_id": new_movie_id})
            log_database_operation(
                operation="delete",
                collection="movies",
                operation_data={"movie_id": str(new_movie_id)},
                result={"reason": "rollback_after_director_association_error"},
                error_message=str(e)
            )
            raise HTTPException(
                status_code=500, 
                detail=f"Erro ao associar filme aos diretores. Operação revertida. Erro: {e}"
            )
    
    movie_dict["_id"] = str(new_movie_id)
    logger.info(f"Filme '{movie.movie_title}' criado com sucesso. ID: {new_movie_id}")
    return movie_dict
    
@router.get("/count")
async def get_movies_count():
    logger.info("Consultando contagem total de filmes")
    start_time = time.time()
    count = await movie_collection.count_documents({})
    operation_time = time.time() - start_time
    
    log_database_operation(
        operation="count_documents",
        collection="movies",
        result={"total_count": count, "execution_time": f"{operation_time:.3f}s"}
    )
    logger.info(f"Total de filmes no sistema: {count}")
    return {"total_movies": count}

@router.get("/", response_model=List[MovieOut])
async def list_movies(skip: int = 0, limit: int = 10):
    logger.info(f"Listando filmes com paginação: skip={skip}, limit={limit}")
    
    if limit > 100:
        log_business_rule_violation(
            rule="PAGINATION_LIMIT_EXCEEDED",
            details=f"Limite de {limit} excede o máximo permitido de 100",
            data={"requested_limit": limit, "max_allowed": 100}
        )
        limit = 100
        logger.warning(f"Limite ajustado para {limit} (máximo permitido)")
    
    start_time = time.time()
    movies = await movie_collection.find().skip(skip).limit(limit).to_list(length=limit)
    operation_time = time.time() - start_time
    
    for m in movies:
        m["_id"] = str(m["_id"])
    
    log_database_operation(
        operation="find",
        collection="movies",
        operation_data={"skip": skip, "limit": limit},
        result={"movies_found": len(movies), "execution_time": f"{operation_time:.3f}s"}
    )
    logger.info(f"Retornados {len(movies)} filmes")
    return movies

@router.get("/{movie_id}", response_model=MovieOut)
async def find_movie_by_id(movie_id: str):
    logger.info(f"Buscando filme por ID: {movie_id}")
    
    if not ObjectId.is_valid(movie_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de filme fornecido não é um ObjectId válido",
            data={"provided_id": movie_id}
        )
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    start_time = time.time()
    movie = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    operation_time = time.time() - start_time
    
    if movie:
        movie["_id"] = str(movie["_id"])
        log_database_operation(
            operation="find_one",
            collection="movies",
            operation_data={"movie_id": movie_id},
            result={"found": True, "movie_title": movie.get("movie_title"), "execution_time": f"{operation_time:.3f}s"}
        )
        logger.info(f"Filme encontrado: {movie.get('movie_title')}")
        return movie
    else:
        log_database_operation(
            operation="find_one",
            collection="movies",
            operation_data={"movie_id": movie_id},
            result={"found": False, "execution_time": f"{operation_time:.3f}s"}
        )
        logger.warning(f"Filme não encontrado para ID: {movie_id}")
        raise HTTPException(status_code=404, detail="Movie not found")

@router.put("/{movie_id}", response_model=MovieOut)
async def update_movie(movie_id: str, movie: MovieCreate):
    logger.info(f"Iniciando atualização do filme ID: {movie_id}")
    
    if not ObjectId.is_valid(movie_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de filme fornecido não é um ObjectId válido",
            data={"provided_id": movie_id}
        )
        raise HTTPException(status_code=400, detail="Invalid movie ID")
    
    # Validar diretores se fornecidos
    if movie.director_ids:
        logger.info(f"Validando {len(movie.director_ids)} diretores para atualização")
        for director_id in movie.director_ids:
            if not ObjectId.is_valid(director_id):
                log_business_rule_violation(
                    rule="INVALID_DIRECTOR_ID",
                    details="ID de diretor inválido fornecido na atualização",
                    data={"director_id": director_id, "movie_id": movie_id}
                )
                raise HTTPException(status_code=400, detail="Invalid director ID")
            
            director = await director_collection.find_one({"_id": ObjectId(director_id)})
            if not director:
                log_business_rule_violation(
                    rule="DIRECTOR_NOT_FOUND",
                    details="Diretor não encontrado durante atualização",
                    data={"director_id": director_id, "movie_id": movie_id}
                )
                raise HTTPException(status_code=404, detail="Director not found")
        logger.info("Todos os diretores foram validados com sucesso")
    
    # Atualizar filme
    updated_data = movie.model_dump(exclude_unset=True)
    start_time = time.time()
    result = await movie_collection.update_one(
        {"_id": ObjectId(movie_id)},
        {"$set": updated_data}
    )
    operation_time = time.time() - start_time
    
    if result.matched_count == 0:
        log_database_operation(
            operation="update_one",
            collection="movies",
            operation_data={"movie_id": movie_id, "update_data": updated_data},
            result={"matched_count": 0, "execution_time": f"{operation_time:.3f}s"}
        )
        logger.warning(f"Nenhum filme encontrado para atualização. ID: {movie_id}")
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Buscar filme atualizado
    start_time = time.time()
    updated = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    find_time = time.time() - start_time
    
    if updated:
        updated["_id"] = str(updated["_id"])
        log_database_operation(
            operation="update_one",
            collection="movies",
            operation_data={"movie_id": movie_id, "fields_updated": list(updated_data.keys())},
            result={
                "modified_count": result.modified_count,
                "movie_title": updated.get("movie_title"),
                "execution_time": f"{operation_time:.3f}s",
                "find_time": f"{find_time:.3f}s"
            }
        )
        logger.info(f"Filme '{updated.get('movie_title')}' atualizado com sucesso")
        return updated
    else:
        logger.error(f"Falha ao recuperar filme atualizado. ID: {movie_id}")
        raise HTTPException(status_code=500, detail="Failed to update movie")

@router.delete("/{movie_id}")
async def delete_movie(movie_id: str):
    logger.info(f"Iniciando exclusão do filme ID: {movie_id}")
    
    if not ObjectId.is_valid(movie_id):
        log_business_rule_violation(
            rule="INVALID_OBJECT_ID",
            details="ID de filme fornecido não é um ObjectId válido",
            data={"provided_id": movie_id}
        )
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    # Verificar se o filme existe antes de excluir
    start_time = time.time()
    exist = await movie_collection.find_one({"_id": ObjectId(movie_id)})
    find_time = time.time() - start_time
    
    if exist:
        movie_title = exist.get("movie_title", "Título não disponível")
        logger.info(f"Filme encontrado para exclusão: {movie_title}")
        
        # Remover associações com diretores
        if exist.get("director_ids"):
            logger.info(f"Removendo associações com {len(exist['director_ids'])} diretores")
            for director_id in exist["director_ids"]:
                if ObjectId.is_valid(director_id):
                    start_time = time.time()
                    await director_collection.update_one(
                        {"_id": ObjectId(director_id)},
                        {"$pull": {"movie_ids": movie_id}}
                    )
                    operation_time = time.time() - start_time
                    
                    log_database_operation(
                        operation="update_one",
                        collection="directors",
                        operation_data={"director_id": director_id, "removed_movie_id": movie_id},
                        result={"execution_time": f"{operation_time:.3f}s"}
                    )
            logger.info("Todas as associações com diretores foram removidas")
        
        # Excluir o filme
        start_time = time.time()
        await movie_collection.delete_one({"_id": ObjectId(movie_id)})
        delete_time = time.time() - start_time
        
        log_database_operation(
            operation="delete_one",
            collection="movies",
            operation_data={"movie_id": movie_id, "movie_title": movie_title},
            result={
                "deleted": True,
                "find_time": f"{find_time:.3f}s",
                "delete_time": f"{delete_time:.3f}s"
            }
        )
        logger.info(f"Filme '{movie_title}' excluído com sucesso")
        return {"detail": "Movie deleted successfully"}
    else:
        log_database_operation(
            operation="delete_one",
            collection="movies",
            operation_data={"movie_id": movie_id},
            result={"deleted": False, "reason": "not_found", "find_time": f"{find_time:.3f}s"}
        )
        logger.warning(f"Tentativa de excluir filme inexistente. ID: {movie_id}")
        raise HTTPException(status_code=404, detail="Movie not found")



@router.get("/filter", response_model=List[MovieOut])
async def filter_movies(
    movie_title: Optional[str] = None,
    genre: Optional[str] = None,
    rating: Optional[str] = None,
    release_year: Optional[int] = None,
    director_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 10
):
    filters = {
        "movie_title": movie_title,
        "genre": genre,
        "rating": rating,
        "release_year": release_year,
        "director_id": director_id
    }
    active_filters = {k: v for k, v in filters.items() if v is not None}
    
    logger.info(f"Filtrando filmes com critérios: {active_filters}, skip={skip}, limit={limit}")
    
    if limit > 100:
        log_business_rule_violation(
            rule="PAGINATION_LIMIT_EXCEEDED",
            details=f"Limite de {limit} excede o máximo permitido de 100 para filtros",
            data={"requested_limit": limit, "max_allowed": 100, "filters": active_filters}
        )
        limit = 100
        logger.warning(f"Limite ajustado para {limit} (máximo permitido)")
    
    filter_query = {}
    
    if movie_title:
        filter_query["movie_title"] = {"$regex": movie_title, "$options": "i"}
    if genre:
        filter_query["genre"] = {"$regex": genre, "$options": "i"}
    if rating:
        filter_query["rating"] = {"$regex": rating, "$options": "i"}
    if release_year is not None:
        filter_query["release_year"] = release_year
    if director_id:
        if ObjectId.is_valid(director_id):
            filter_query["director_ids"] = {"$in": [director_id]}
        else:
            log_business_rule_violation(
                rule="INVALID_DIRECTOR_ID",
                details="ID de diretor inválido no filtro",
                data={"director_id": director_id, "other_filters": active_filters}
            )
            raise HTTPException(status_code=400, detail="Invalid director ID")
    
    start_time = time.time()
    movies = await movie_collection.find(filter_query).skip(skip).limit(limit).to_list(length=limit)
    operation_time = time.time() - start_time
    
    for m in movies:
        m["_id"] = str(m["_id"])
    
    log_database_operation(
        operation="find_with_filter",
        collection="movies",
        operation_data={
            "filter_query": filter_query,
            "skip": skip,
            "limit": limit,
            "active_filters_count": len(active_filters)
        },
        result={
            "movies_found": len(movies),
            "execution_time": f"{operation_time:.3f}s"
        }
    )
    logger.info(f"Filtro retornou {len(movies)} filmes com {len(active_filters)} critérios aplicados")
    return movies