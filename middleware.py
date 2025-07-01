from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
from logger import log_endpoint_access, log_performance_metric
from typing import Callable

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para logging automático de todas as requisições"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Registra o início da requisição
        start_time = time.time()
        
        # Captura dados da requisição
        method = request.method
        url = str(request.url)
        endpoint = request.url.path
        
        # Tenta capturar o body da requisição (se houver)
        request_data = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Reconstrói o request para que possa ser usado pelos endpoints
                    request._body = body
                    try:
                        request_data = json.loads(body.decode('utf-8'))
                        # Remove dados sensíveis se existirem
                        if isinstance(request_data, dict):
                            # Lista de campos que devem ser mascarados nos logs
                            sensitive_fields = ['password', 'token', 'secret', 'key']
                            for field in sensitive_fields:
                                if field in request_data:
                                    request_data[field] = "***MASKED***"
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_data = {"note": "Non-JSON or binary data"}
            except Exception:
                request_data = {"note": "Could not capture request data"}
        
        # Processa a requisição
        response = await call_next(request)
        
        # Calcula o tempo de execução
        execution_time = time.time() - start_time
        
        # Captura dados da resposta (limitado para não sobrecarregar os logs)
        response_data = None
        status_code = response.status_code
        
        # Para respostas de sucesso, captura informações básicas
        if 200 <= status_code < 300:
            if hasattr(response, 'headers'):
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    response_data = {"content_type": "application/json", "status": "success"}
                else:
                    response_data = {"content_type": content_type, "status": "success"}
        
        # Para erros, tenta capturar mais detalhes
        error_message = None
        if status_code >= 400:
            error_message = f"HTTP {status_code} error"
            if hasattr(response, 'headers'):
                content_type = response.headers.get('content-type', '')
                response_data = {"content_type": content_type, "status": "error"}
        
        # Registra o acesso ao endpoint
        log_endpoint_access(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            execution_time=execution_time,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message
        )
        
        # Registra métricas de performance se necessário
        if execution_time > 1.0:  # Log performance para operações > 1 segundo
            log_performance_metric(
                operation=f"{method} {endpoint}",
                execution_time=execution_time,
                details={"status_code": status_code}
            )
        
        return response
