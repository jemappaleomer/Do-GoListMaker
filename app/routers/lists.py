from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.dependencies import get_current_user_required, get_current_user_optional
from app.core.supabase import get_authenticated_client, get_supabase_client

router = APIRouter(prefix="/lists", tags=["lists"])
templates = Jinja2Templates(directory="templates")

@router.get("", response_class=HTMLResponse)
async def list_index(request: Request, user: dict = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    try:
        supabase = get_authenticated_client(user["access_token"])
        response = supabase.table("lists").select("*").order("created_at", desc=True).execute()
        lists_data = response.data or []
    except Exception as e:
        lists_data = []

    return templates.TemplateResponse(
        request=request,
        name="lists/index.html",
        context={
            "user": user,
            "lists": lists_data,
            "error": None
        }
    )

@router.post("", response_class=HTMLResponse)
async def create_list(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    user: dict = Depends(get_current_user_required)
):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("lists").insert({
            "title": title.strip(),
            "description": description.strip() if description else None,
            "owner_id": user["id"],
            "is_shared": False
        }).execute()
        return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{list_id}", response_class=HTMLResponse)
async def get_list(list_id: str, request: Request, user: dict = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    try:
        supabase = get_authenticated_client(user["access_token"])
        # Fetch list details
        list_res = supabase.table("lists").select("*").eq("id", list_id).single().execute()
        list_data = list_res.data

        if not list_data:
            return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)

        # Fetch items
        items_res = supabase.table("list_items").select("*").eq("list_id", list_id).order("created_at", desc=False).execute()
        items = items_res.data or []
        completed_count = sum(1 for item in items if item.get("is_completed"))

        is_owner = list_data.get("owner_id") == user["id"]

        return templates.TemplateResponse(
            request=request,
            name="lists/detail.html",
            context={
                "user": user,
                "list_data": list_data,
                "items": items,
                "completed_count": completed_count,
                "is_owner": is_owner
            }
        )
    except Exception as e:
        return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)

@router.post("/{list_id}/delete")
async def delete_list(list_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("lists").delete().eq("id", list_id).eq("owner_id", user["id"]).execute()
    except Exception:
        pass
    return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items")
async def add_item(
    list_id: str,
    title: str = Form(...),
    location_url: Optional[str] = Form(None),
    user: dict = Depends(get_current_user_required)
):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("list_items").insert({
            "list_id": list_id,
            "title": title.strip(),
            "location_url": location_url.strip() if location_url else None,
            "is_completed": False,
            "created_by": user["id"]
        }).execute()
    except Exception:
        pass
    return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items/{item_id}/toggle")
async def toggle_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        # Get current completion status
        item_res = supabase.table("list_items").select("is_completed").eq("id", item_id).single().execute()
        if item_res.data:
            current_status = item_res.data.get("is_completed", False)
            supabase.table("list_items").update({
                "is_completed": not current_status
            }).eq("id", item_id).execute()
    except Exception:
        pass
    return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items/{item_id}/delete")
async def delete_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("list_items").delete().eq("id", item_id).execute()
    except Exception:
        pass
    return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
