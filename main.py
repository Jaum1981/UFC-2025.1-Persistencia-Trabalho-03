from fastapi import FastAPI
from routes import directorRouter, movieRouter, roomRoute, sessionRoute, paymentDetailRouter, ticketRouter, complexQueryRouter, logsRouter
from middleware import LoggingMiddleware
from logger import logger

app = FastAPI(
    title="Cinema API",
    description="API para gerenciamento de cinema com sistema de logs completo",
    version="1.0.0"
)

# Adiciona o middleware de logging
app.add_middleware(LoggingMiddleware)

# Registra routers
app.include_router(router=directorRouter.router)
app.include_router(router=movieRouter.router)
app.include_router(router=roomRoute.router)
app.include_router(router=sessionRoute.router)
app.include_router(router=paymentDetailRouter.router)
app.include_router(router=ticketRouter.router)
app.include_router(router=complexQueryRouter.router)
# app.include_router(router=logsRouter.router)  # Router para gerenciar logs

# @app.on_event("startup")
# async def startup_event():
#     """Evento executado na inicialização da aplicação"""
#     logger.info("🎬 Cinema API iniciada com sistema de logs ativo")
#     logger.info("📝 Logs serão salvos no diretório 'logs/'")

# @app.on_event("shutdown")
# async def shutdown_event():
#     """Evento executado no encerramento da aplicação"""
#     logger.info("🛑 Cinema API encerrada")

# @app.get("/")
# async def root():
#     """Endpoint raiz da API"""
#     return {
#         "message": "Cinema API está funcionando!",
#         "version": "1.0.0",
#         "features": [
#             "Sistema de logs completo",
#             "Logging automático de endpoints",
#             "Métricas de performance",
#             "Logs de operações de banco"
#         ]
#     }