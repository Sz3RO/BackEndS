from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import router as api_router

app = FastAPI(
    title="Fashion Shop API",
    description="API cho shop thời trang",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",   # ✅ chấp nhận mọi domain
    allow_credentials=True,    # ✅ cho phép cookie
    allow_methods=["*"],       # cho phép mọi phương thức (GET, POST, PUT, DELETE, ...)
    allow_headers=["*"],       # cho phép mọi header
)

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Fashion Shop API đang chạy!"}
