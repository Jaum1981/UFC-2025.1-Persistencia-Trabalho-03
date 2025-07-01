import logging
import os
from datetime import datetime
from typing import Optional
import json

# Configuração do diretório de logs
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Configuração do logger principal
def setup_logger():
    """Configura e retorna o logger principal da aplicação"""
    logger = logging.getLogger("cinema_api")
    logger.setLevel(logging.INFO)
    
    # Remove handlers existentes para evitar duplicação
    if logger.handlers:
        logger.handlers.clear()
    
    # Formatter para os logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para arquivo geral
    file_handler = logging.FileHandler(
        os.path.join(LOGS_DIR, f"cinema_api_{datetime.now().strftime('%Y_%m_%d')}.log"),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Handler para erros (arquivo separado)
    error_handler = logging.FileHandler(
        os.path.join(LOGS_DIR, f"errors_{datetime.now().strftime('%Y_%m_%d')}.log"),
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    
    return logger

# Logger global
logger = setup_logger()

def log_endpoint_access(
    method: str,
    endpoint: str,
    status_code: int,
    user_id: Optional[str] = None,
    execution_time: Optional[float] = None,
    request_data: Optional[dict] = None,
    response_data: Optional[dict] = None,
    error_message: Optional[str] = None
):
    """
    Registra o acesso a um endpoint
    
    Args:
        method: Método HTTP (GET, POST, PUT, DELETE)
        endpoint: Caminho do endpoint
        status_code: Código de status HTTP
        user_id: ID do usuário (se disponível)
        execution_time: Tempo de execução em segundos
        request_data: Dados da requisição
        response_data: Dados da resposta (resumido)
        error_message: Mensagem de erro (se houver)
    """
    log_data = {
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "execution_time": f"{execution_time:.3f}s" if execution_time else None,
        "request_data": request_data,
        "response_data": response_data,
        "error_message": error_message
    }
    
    # Remove campos None para manter o log limpo
    log_data = {k: v for k, v in log_data.items() if v is not None}
    
    if status_code >= 400:
        logger.error(f"[{method}] {endpoint} - Status: {status_code} - {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"[{method}] {endpoint} - Status: {status_code} - {json.dumps(log_data, ensure_ascii=False)}")

def log_database_operation(
    operation: str,
    collection: str,
    operation_data: Optional[dict] = None,
    result: Optional[dict] = None,
    error_message: Optional[str] = None
):
    """
    Registra operações no banco de dados
    
    Args:
        operation: Tipo de operação (insert, update, delete, find)
        collection: Nome da coleção
        operation_data: Dados da operação
        result: Resultado da operação
        error_message: Mensagem de erro (se houver)
    """
    log_data = {
        "operation": operation,
        "collection": collection,
        "timestamp": datetime.now().isoformat(),
        "operation_data": operation_data,
        "result": result,
        "error_message": error_message
    }
    
    # Remove campos None
    log_data = {k: v for k, v in log_data.items() if v is not None}
    
    if error_message:
        logger.error(f"DB_ERROR [{operation}] {collection} - {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"DB_OPERATION [{operation}] {collection} - {json.dumps(log_data, ensure_ascii=False)}")

def log_business_rule_violation(
    rule: str,
    details: str,
    data: Optional[dict] = None
):
    """
    Registra violações de regras de negócio
    
    Args:
        rule: Nome da regra violada
        details: Detalhes da violação
        data: Dados relacionados à violação
    """
    log_data = {
        "rule": rule,
        "details": details,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    logger.warning(f"BUSINESS_RULE_VIOLATION - {rule}: {details} - {json.dumps(log_data, ensure_ascii=False)}")

def log_performance_metric(
    operation: str,
    execution_time: float,
    details: Optional[dict] = None
):
    """
    Registra métricas de performance
    
    Args:
        operation: Nome da operação
        execution_time: Tempo de execução em segundos
        details: Detalhes adicionais
    """
    log_data = {
        "operation": operation,
        "execution_time": f"{execution_time:.3f}s",
        "timestamp": datetime.now().isoformat(),
        "details": details
    }
    
    # Log de warning se a operação for muito lenta (>5 segundos)
    if execution_time > 5.0:
        logger.warning(f"SLOW_OPERATION - {operation} took {execution_time:.3f}s - {json.dumps(log_data, ensure_ascii=False)}")
    else:
        logger.info(f"PERFORMANCE - {operation} - {json.dumps(log_data, ensure_ascii=False)}")
