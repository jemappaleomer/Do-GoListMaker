from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR, STATIC_DIR
from app.core.dependencies import get_current_user_optional
from app.routers import auth, lists

app = FastAPI(title="Do&Go List Maker", version="0.1.0")

# Mount static files safely
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

# Include Routers
app.include_router(auth.router)
app.include_router(lists.router)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Oturum düşmüşse JSON hata basmak yerine doğrudan login sayfasına yönlendir
        response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
        response.delete_cookie(key="sb_access_token", path="/")
        return response
    return HTMLResponse(content=f"<h1>Hata: {exc.detail}</h1>", status_code=exc.status_code)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/lists")
    return RedirectResponse(url="/auth/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
