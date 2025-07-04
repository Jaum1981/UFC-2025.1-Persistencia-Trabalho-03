from fastapi import FastAPI
from routes import directorRouter, movieRouter, roomRoute, sessionRoute, paymentDetailRouter, ticketRouter, complexQueryRouter
from middleware import LoggingMiddleware
from logger import logger

app = FastAPI(
    title="Cinema API",
    description="API para gerenciamento de cinema com sistema de logs completo",
    version="1.0.0"
)

app.add_middleware(LoggingMiddleware)

app.include_router(router=directorRouter.router)
app.include_router(router=movieRouter.router)
app.include_router(router=roomRoute.router)
app.include_router(router=sessionRoute.router)
app.include_router(router=paymentDetailRouter.router)
app.include_router(router=ticketRouter.router)
app.include_router(router=complexQueryRouter.router)