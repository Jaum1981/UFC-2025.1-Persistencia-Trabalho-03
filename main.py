from fastapi import FastAPI
from routes import directorRouter, movieRouter

app = FastAPI()

app.include_router(router=directorRouter.router)
app.include_router(router=movieRouter.router)