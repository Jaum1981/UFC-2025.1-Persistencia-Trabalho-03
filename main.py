from fastapi import FastAPI
from routes import directorRouter

app = FastAPI()

app.include_router(router=directorRouter.router)