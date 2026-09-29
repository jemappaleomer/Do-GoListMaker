from fastapi import APIRouter, Request, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.supabase import get_supabase_client
from app.core.dependencies import get_current_user_optional

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"user": None, "error": None}
    )

@router.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        supabase = get_supabase_client()
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if not auth_response or not auth_response.session:
            return templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={"user": None, "error": "Giriş yapılamadı. Lütfen bilgilerinizi kontrol edin."},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        access_token = auth_response.session.access_token
        response = RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
        # Store access token in HttpOnly cookie
        response.set_cookie(
            key="sb_access_token",
            value=access_token,
            httponly=True,
            max_age=60 * 60 * 24 * 7, # 7 days
            samesite="lax",
            secure=False # Set to True in production with HTTPS
        )
        return response

    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            error_msg = "E-posta veya parola hatalı."
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"user": None, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"user": None, "error": None}
    )

@router.post("/register", response_class=HTMLResponse)
async def register_action(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        supabase = get_supabase_client()
        # Sign up with metadata
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "username": username
                }
            }
        })

        if not auth_response or not auth_response.user:
            return templates.TemplateResponse(
                request=request,
                name="auth/register.html",
                context={"user": None, "error": "Kayıt işlemi başarısız oldu."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Otomatik oturum açma veya e-posta onay kontrolü
        if auth_response.session:
            response = RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                key="sb_access_token",
                value=auth_response.session.access_token,
                httponly=True,
                max_age=60 * 60 * 24 * 7,
                samesite="lax",
                secure=False
            )
            return response
        else:
            # E-posta onayı aktifse
            return templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={"user": None, "error": "Kayıt başarılı! Lütfen e-posta adresinizi onaylayıp giriş yapın."}
            )

    except Exception as e:
        error_msg = str(e)
        if "User already registered" in error_msg:
            error_msg = "Bu e-posta adresiyle zaten kayıtlı bir hesap var."
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"user": None, "error": error_msg},
            status_code=status.HTTP_400_BAD_REQUEST
        )

@router.get("/callback")
async def auth_callback(request: Request, code: Optional[str] = None):
    """Handles email confirmation link callbacks from Supabase Auth."""
    if code:
        try:
            supabase = get_supabase_client()
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res and res.session:
                response = RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
                response.set_cookie(
                    key="sb_access_token",
                    value=res.session.access_token,
                    httponly=True,
                    max_age=60 * 60 * 24 * 7,
                    samesite="lax",
                    secure=False
                )
                return response
        except Exception as e:
            print("Error in callback:", e)
    
    # Callback fails or user is redirected, send to login with success notice
    return RedirectResponse(url="/auth/login?confirmed=true", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="sb_access_token")
    return response

