from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR, STATIC_DIR
from app.core.dependencies import get_current_user_optional
from app.routers import auth, lists, public

app = FastAPI(
    title="Do&Go List Maker",
    version="1.0.0",
    description="Arkadaş grupları için mekan, etkinlik ve seyahat planlama platformu."
)

# Mount static files safely
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include Routers
app.include_router(public.router)
app.include_router(auth.router)
app.include_router(lists.router)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # 401 Unauthorized: Oturum bittiğinde login'e yönlendir ve süresi dolmuş çerezi sil
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
        response.delete_cookie(key="sb_access_token", path="/")
        return response

    # 404 Not Found: Özel kullanıcı dostu 404 sayfasını render et
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        user = await get_current_user_optional(request)
        return templates.TemplateResponse(
            request=request,
            name="errors/404.html",
            context={"user": user},
            status_code=status.HTTP_404_NOT_FOUND
        )

    return HTMLResponse(content=f"<h1>Hata: {exc.detail}</h1>", status_code=exc.status_code)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"user": user},
        status_code=status.HTTP_404_NOT_FOUND
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav_path = STATIC_DIR / "favicon.svg"
    if fav_path.exists():
        return FileResponse(fav_path, media_type="image/svg+xml")
    return HTMLResponse(content="", status_code=204)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/lists")
    return RedirectResponse(url="/auth/login")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
