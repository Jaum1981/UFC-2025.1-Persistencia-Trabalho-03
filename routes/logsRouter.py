from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import os
import glob
from datetime import datetime, timedelta
import json
from logger import logger

router = APIRouter(prefix="/logs", tags=["logs"])

@router.get("/files")
async def list_log_files():
    """Lista todos os arquivos de log disponíveis"""
    logger.info("Listando arquivos de log disponíveis")
    
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return {"log_files": [], "message": "Diretório de logs não existe ainda"}
    
    log_files = []
    for file_path in glob.glob(os.path.join(logs_dir, "*.log")):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        log_files.append({
            "filename": file_name,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "last_modified": file_modified.isoformat(),
            "type": "error" if "error" in file_name else "general"
        })
    
    log_files.sort(key=lambda x: x["last_modified"], reverse=True)
    
    logger.info(f"Encontrados {len(log_files)} arquivos de log")
    return {
        "log_files": log_files,
        "total_files": len(log_files),
        "logs_directory": logs_dir
    }

@router.get("/recent")
async def get_recent_logs(
    lines: int = Query(100, ge=1, le=1000, description="Número de linhas a retornar"),
    log_type: Optional[str] = Query(None, description="Tipo de log: 'error', 'general' ou None para todos"),
    level: Optional[str] = Query(None, description="Nível de log: 'INFO', 'WARNING', 'ERROR'")
):
    """Recupera logs recentes do arquivo de log atual"""
    logger.info(f"Recuperando {lines} linhas recentes de logs, tipo: {log_type}, nível: {level}")
    
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return {"logs": [], "message": "Nenhum log disponível ainda"}
    
    # Determina qual arquivo ler baseado no tipo
    today = datetime.now().strftime('%Y_%m_%d')
    if log_type == "error":
        log_file = os.path.join(logs_dir, f"errors_{today}.log")
    else:
        log_file = os.path.join(logs_dir, f"cinema_api_{today}.log")
    
    if not os.path.exists(log_file):
        return {"logs": [], "message": f"Arquivo de log {log_file} não encontrado"}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Pega as últimas N linhas
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Filtra por nível se especificado
        if level:
            filtered_lines = [line for line in recent_lines if f" - {level} - " in line]
            recent_lines = filtered_lines
        
        # Processa as linhas para extrair informações estruturadas
        processed_logs = []
        for line in recent_lines:
            line = line.strip()
            if line:
                try:
                    # Tenta extrair informações da linha de log
                    parts = line.split(" - ", 3)
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        name = parts[1]
                        level_found = parts[2]
                        message = parts[3]
                        
                        # Tenta extrair JSON se presente
                        json_data = None
                        if " - {" in message:
                            try:
                                json_start = message.find(" - {")
                                json_str = message[json_start + 3:]
                                json_data = json.loads(json_str)
                                message = message[:json_start]
                            except:
                                pass
                        
                        processed_logs.append({
                            "timestamp": timestamp,
                            "logger": name,
                            "level": level_found,
                            "message": message,
                            "data": json_data,
                            "raw_line": line
                        })
                    else:
                        processed_logs.append({
                            "timestamp": None,
                            "logger": None,
                            "level": None,
                            "message": line,
                            "data": None,
                            "raw_line": line
                        })
                except Exception as e:
                    processed_logs.append({
                        "timestamp": None,
                        "logger": None,
                        "level": "PARSE_ERROR",
                        "message": f"Erro ao processar linha: {str(e)}",
                        "data": None,
                        "raw_line": line
                    })
        
        return {
            "logs": processed_logs,
            "total_lines": len(processed_logs),
            "file_used": log_file,
            "filters_applied": {
                "lines": lines,
                "log_type": log_type,
                "level": level
            }
        }
    
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de log {log_file}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao ler logs: {str(e)}")

@router.get("/stats")
async def get_log_statistics():
    """Retorna estatísticas dos logs"""
    logger.info("Calculando estatísticas dos logs")
    
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return {"message": "Nenhum log disponível ainda"}
    
    stats = {
        "total_files": 0,
        "total_size_mb": 0,
        "by_level": {"INFO": 0, "WARNING": 0, "ERROR": 0},
        "by_endpoint": {},
        "by_day": {},
        "recent_errors": []
    }
    
    # Analisa todos os arquivos de log
    for file_path in glob.glob(os.path.join(logs_dir, "*.log")):
        stats["total_files"] += 1
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        stats["total_size_mb"] += file_size_mb
        
        # Extrai data do nome do arquivo
        file_name = os.path.basename(file_path)
        if "cinema_api_" in file_name:
            date_part = file_name.replace("cinema_api_", "").replace(".log", "")
            stats["by_day"][date_part] = stats["by_day"].get(date_part, 0)
        
        # Analisa conteúdo do arquivo (apenas arquivos pequenos para não sobrecarregar)
        if file_size_mb < 10:  # Apenas arquivos menores que 10MB
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Conta por nível
                        for level in ["INFO", "WARNING", "ERROR"]:
                            if f" - {level} - " in line:
                                stats["by_level"][level] += 1
                                break
                        
                        # Conta por endpoint
                        if " [GET] " in line or " [POST] " in line or " [PUT] " in line or " [DELETE] " in line:
                            for method in ["GET", "POST", "PUT", "DELETE"]:
                                if f" [{method}] " in line:
                                    # Extrai endpoint
                                    try:
                                        endpoint_start = line.find(f" [{method}] ") + len(f" [{method}] ")
                                        endpoint_end = line.find(" - Status:", endpoint_start)
                                        if endpoint_end > endpoint_start:
                                            endpoint = line[endpoint_start:endpoint_end]
                                            endpoint_key = f"{method} {endpoint}"
                                            stats["by_endpoint"][endpoint_key] = stats["by_endpoint"].get(endpoint_key, 0) + 1
                                    except:
                                        pass
                        
                        # Coleta erros recentes
                        if " - ERROR - " in line and len(stats["recent_errors"]) < 10:
                            stats["recent_errors"].append(line.strip())
            
            except Exception as e:
                logger.warning(f"Erro ao analisar arquivo {file_path}: {e}")
    
    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    
    return stats

@router.delete("/clean")
async def clean_old_logs(
    days_older_than: int = Query(7, ge=1, description="Excluir logs mais antigos que N dias")
):
    """Remove logs antigos"""
    logger.info(f"Iniciando limpeza de logs mais antigos que {days_older_than} dias")
    
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        return {"message": "Diretório de logs não existe"}
    
    cutoff_date = datetime.now() - timedelta(days=days_older_than)
    deleted_files = []
    total_size_deleted = 0
    
    for file_path in glob.glob(os.path.join(logs_dir, "*.log")):
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        if file_modified < cutoff_date:
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            
            try:
                os.remove(file_path)
                deleted_files.append({
                    "filename": file_name,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "last_modified": file_modified.isoformat()
                })
                total_size_deleted += file_size
                logger.info(f"Arquivo de log removido: {file_name}")
            except Exception as e:
                logger.error(f"Erro ao remover arquivo {file_name}: {e}")
    
    return {
        "deleted_files": deleted_files,
        "total_deleted": len(deleted_files),
        "total_size_deleted_mb": round(total_size_deleted / (1024 * 1024), 2),
        "cutoff_date": cutoff_date.isoformat()
    }
    
@router.get("/health")
async def log_system_health():
    """Verifica a saúde do sistema de logs"""
    logger.info("Verificando saúde do sistema de logs")
    
    health_status = {
        "status": "healthy",
        "issues": [],
        "logs_directory_exists": False,
        "logs_writable": False,
        "current_log_size_mb": 0,
        "total_logs_size_mb": 0
    }
    
    logs_dir = "logs"
    
    # Verifica se o diretório existe
    if os.path.exists(logs_dir):
        health_status["logs_directory_exists"] = True
        
        # Verifica se é possível escrever
        try:
            test_file = os.path.join(logs_dir, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            health_status["logs_writable"] = True
        except Exception as e:
            health_status["logs_writable"] = False
            health_status["issues"].append(f"Não é possível escrever no diretório de logs: {e}")
        
        # Calcula tamanho dos logs
        today = datetime.now().strftime('%Y_%m_%d')
        current_log = os.path.join(logs_dir, f"cinema_api_{today}.log")
        if os.path.exists(current_log):
            health_status["current_log_size_mb"] = round(os.path.getsize(current_log) / (1024 * 1024), 2)
        
        total_size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(logs_dir, "*.log")))
        health_status["total_logs_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        # Verifica se os logs estão muito grandes
        if health_status["total_logs_size_mb"] > 100:  # Mais de 100MB
            health_status["issues"].append("Logs ocupando muito espaço (>100MB)")
        
        if health_status["current_log_size_mb"] > 50:  # Log atual > 50MB
            health_status["issues"].append("Log atual muito grande (>50MB)")
    
    else:
        health_status["issues"].append("Diretório de logs não existe")
    
    if health_status["issues"]:
        health_status["status"] = "warning" if len(health_status["issues"]) == 1 else "error"
    
    return health_status
