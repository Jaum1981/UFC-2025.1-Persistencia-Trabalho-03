from fastapi import FastAPI
from routes import directorRouter, movieRouter, roomRoute, sessionRoute, paymentDetailRouter, ticketRouter, complexQueryRouter

app = FastAPI()

app.include_router(router=directorRouter.router)
app.include_router(router=movieRouter.router)
app.include_router(router=roomRoute.router)
app.include_router(router=sessionRoute.router)
app.include_router(router=paymentDetailRouter.router)
app.include_router(router=ticketRouter.router)
app.include_router(router=complexQueryRouter.router)