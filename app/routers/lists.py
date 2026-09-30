from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.core.config import TEMPLATES_DIR
from app.core.dependencies import get_current_user_required, get_current_user_optional
from app.core.supabase import get_authenticated_client, get_supabase_client

router = APIRouter(prefix="/lists", tags=["lists"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("", response_class=HTMLResponse)
async def list_index(request: Request, error: Optional[str] = None, user: dict = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    my_lists = []
    shared_lists = []

    try:
        supabase = get_authenticated_client(user["access_token"])
        
        # 1. Kullanıcının kendi sahip olduğu listeler
        my_res = supabase.table("lists").select("*").eq("owner_id", user["id"]).order("created_at", desc=True).execute()
        my_lists = my_res.data or []

        # 2. Kullanıcıyla paylaşılan ve katıldığı listeler
        perm_res = supabase.table("list_permissions").select("list_id, can_delete, lists(*)").eq("user_id", user["id"]).execute()
        if perm_res.data:
            for item in perm_res.data:
                if item.get("lists"):
                    l_data = item["lists"]
                    # Kendi listesi değilse paylaşılanlar listesine ekle
                    if l_data.get("owner_id") != user["id"]:
                        l_data["can_delete_perm"] = item.get("can_delete", False)
                        shared_lists.append(l_data)
    except Exception as e:
        print("Error fetching lists:", e)

    return templates.TemplateResponse(
        request=request,
        name="lists/index.html",
        context={
            "user": user,
            "my_lists": my_lists,
            "shared_lists": shared_lists,
            "error": error
        }
    )

@router.post("", response_class=HTMLResponse)
async def create_list(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    is_shared: bool = Form(False),
    user: dict = Depends(get_current_user_required)
):
    try:
        supabase = get_authenticated_client(user["access_token"])
        # Profilin profiles tablosunda var olduğunu kesinleştir (Foreign key hatasını engelle)
        try:
            supabase.table("profiles").upsert({
                "id": user["id"],
                "username": user.get("username", "user"),
                "email": user.get("email", "")
            }, on_conflict="id").execute()
        except Exception as pe:
            print("Ensure profile error in create_list:", pe)

        payload = {
            "title": title.strip(),
            "description": description.strip() if description else None,
            "owner_id": user["id"],
            "is_shared": is_shared
        }

        try:
            supabase.table("lists").insert(payload).execute()
        except Exception as insert_err:
            print("Initial insert failed, trying with is_public fallback:", insert_err)
            payload.pop("is_shared", None)
            payload["is_public"] = is_shared
            supabase.table("lists").insert(payload).execute()

        return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import urllib.parse
        err_str = str(e)
        print("Error creating list:", err_str)
        # Hata durumunu ekranda açıkça göster
        encoded_err = urllib.parse.quote(err_str)
        return RedirectResponse(url=f"/lists?error={encoded_err}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{list_id}", response_class=HTMLResponse)
async def get_list(list_id: str, request: Request, error: Optional[str] = None, user: dict = Depends(get_current_user_optional)):
    try:
        # Eğer giriş yapılmışsa kullanıcının kimliğiyle, yapılmamışsa anon client ile çek
        client = get_authenticated_client(user["access_token"]) if user else get_supabase_client()
        
        # Liste detayını ve sahibinin profilini çek
        list_data = None
        try:
            list_res = client.table("lists").select("*, profiles:owner_id(username)").eq("id", list_id).single().execute()
            list_data = list_res.data
        except Exception:
            list_res = client.table("lists").select("*").eq("id", list_id).single().execute()
            list_data = list_res.data

        if not list_data:
            return RedirectResponse(url="/lists" if user else "/auth/login", status_code=status.HTTP_302_FOUND)

        is_owner = user is not None and list_data.get("owner_id") == user["id"]
        is_shared = list_data.get("is_shared", False) or list_data.get("is_public", False)

        # Eğer liste gizliyse (private) ve bakan kişi sahibi değilse
        if not is_shared and not is_owner:
            # Belki özel izin verilmiştir?
            if user:
                perm_check = client.table("list_permissions").select("id").eq("list_id", list_id).eq("user_id", user["id"]).execute()
                if not perm_check.data or len(perm_check.data) == 0:
                    return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)
            else:
                return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

        # Giriş yapmış ve sahibi olmayan kullanıcı paylaşılan listeyi açtığında otomatik list_permissions'a ekle (collaborator olsun)
        can_delete = is_owner
        if user and not is_owner:
            try:
                perm_res = client.table("list_permissions").select("*").eq("list_id", list_id).eq("user_id", user["id"]).execute()
                if not perm_res.data:
                    # Yeni katılımcı olarak ekle
                    client.table("list_permissions").insert({
                        "list_id": list_id,
                        "user_id": user["id"],
                        "permission_level": "edit"
                    }).execute()
            except Exception as pe:
                print("Permission insert warning:", pe)

        # Liste maddelerini çek
        raw_items = []
        try:
            items_res = client.table("list_items").select("*, profiles:created_by(username)").eq("list_id", list_id).order("created_at", desc=False).execute()
            raw_items = items_res.data or []
        except Exception:
            try:
                items_res = client.table("list_items").select("*").eq("list_id", list_id).order("created_at", desc=False).execute()
                raw_items = items_res.data or []
            except Exception as ie:
                print("Error loading list items:", ie)

        completed_count = sum(1 for item in raw_items if item.get("is_completed"))

        # Her madde için Feedback (puan ve yorum) verilerini çek ve ortalama hesapla
        items = []
        item_ids = [item["id"] for item in raw_items]
        all_feedbacks = []
        if item_ids:
            try:
                fb_res = client.table("feedbacks").select("*, profiles:user_id(username)").in_("item_id", item_ids).order("created_at", desc=True).execute()
                all_feedbacks = fb_res.data or []
            except Exception:
                try:
                    fb_res = client.table("feedbacks").select("*").in_("item_id", item_ids).order("created_at", desc=True).execute()
                    all_feedbacks = fb_res.data or []
                except Exception as fe:
                    print("Error loading feedbacks:", fe)

        # Maddeleri feedback verileri ile zenginleştir
        for item in raw_items:
            item_fbs = [fb for fb in all_feedbacks if fb.get("item_id") == item["id"]]
            ratings = [fb["rating"] for fb in item_fbs if fb.get("rating") is not None]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
            user_feedback = next((fb for fb in item_fbs if user and fb.get("user_id") == user["id"]), None)

            item["feedbacks"] = item_fbs
            item["avg_rating"] = avg_rating
            item["rating_count"] = len(ratings)
            item["user_feedback"] = user_feedback
            items.append(item)

        # Eğer liste sahibiyse katılımcıları listele
        collaborators = []
        if is_owner:
            try:
                collab_res = client.table("list_permissions").select("id, user_id, profiles:user_id(username, email)").eq("list_id", list_id).execute()
                collaborators = collab_res.data or []
            except Exception:
                try:
                    collab_res = client.table("list_permissions").select("*").eq("list_id", list_id).execute()
                    collaborators = collab_res.data or []
                except Exception as ce:
                    print("Error loading collaborators:", ce)

        return templates.TemplateResponse(
            request=request,
            name="lists/detail.html",
            context={
                "user": user,
                "list_data": list_data,
                "items": items,
                "completed_count": completed_count,
                "is_owner": is_owner,
                "can_delete": can_delete,
                "collaborators": collaborators,
                "error": error
            }
        )
    except Exception as e:
        import urllib.parse
        err_str = str(e)
        print("Error getting list:", err_str)
        return RedirectResponse(url=f"/lists?error={urllib.parse.quote(err_str)}", status_code=status.HTTP_302_FOUND)

@router.post("/{list_id}/toggle-share")
async def toggle_share(list_id: str, user: dict = Depends(get_current_user_required)):
    """Liste sahibi için paylaşıma açma / kapama endpoint'i."""
    try:
        supabase = get_authenticated_client(user["access_token"])
        current_res = supabase.table("lists").select("is_shared, is_public").eq("id", list_id).eq("owner_id", user["id"]).single().execute()
        if current_res.data:
            curr_val = current_res.data.get("is_shared", False) or current_res.data.get("is_public", False)
            new_val = not curr_val
            try:
                supabase.table("lists").update({"is_shared": new_val, "is_public": new_val}).eq("id", list_id).execute()
            except Exception:
                try:
                    supabase.table("lists").update({"is_shared": new_val}).eq("id", list_id).execute()
                except Exception:
                    supabase.table("lists").update({"is_public": new_val}).eq("id", list_id).execute()
    except Exception as e:
        print("Error toggling share:", e)
    return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/delete")
async def delete_list(list_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("lists").delete().eq("id", list_id).eq("owner_id", user["id"]).execute()
    except Exception as e:
        print("Error deleting list:", e)
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
        clean_url = location_url.strip() if location_url else None
        if clean_url and not clean_url.startswith(("http://", "https://")):
            clean_url = "https://" + clean_url

        payload = {
            "list_id": list_id,
            "title": title.strip(),
            "location_url": clean_url,
            "is_completed": False
        }

        # created_by kolonu varsa kullan, yoksa yalın ekle
        try:
            p_full = {**payload, "created_by": user["id"]}
            supabase.table("list_items").insert(p_full).execute()
        except Exception as pe:
            print("Trying insert without created_by:", pe)
            supabase.table("list_items").insert(payload).execute()

        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import urllib.parse
        err_msg = str(e)
        print("Error adding item:", err_msg)
        return RedirectResponse(url=f"/lists/{list_id}?error={urllib.parse.quote(err_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items/{item_id}/toggle")
async def toggle_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        item_res = supabase.table("list_items").select("is_completed").eq("id", item_id).single().execute()
        if item_res.data:
            current_status = item_res.data.get("is_completed", False)
            supabase.table("list_items").update({
                "is_completed": not current_status
            }).eq("id", item_id).execute()
        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import urllib.parse
        err_msg = str(e)
        print("Error toggling item:", err_msg)
        return RedirectResponse(url=f"/lists/{list_id}?error={urllib.parse.quote(err_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items/{item_id}/delete")
async def delete_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("list_items").delete().eq("id", item_id).execute()
        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import urllib.parse
        err_msg = str(e)
        print("Error deleting item:", err_msg)
        return RedirectResponse(url=f"/lists/{list_id}?error={urllib.parse.quote(err_msg)}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{list_id}/items/{item_id}/feedback")
async def submit_feedback(
    list_id: str,
    item_id: str,
    rating: float = Form(...),
    comment: Optional[str] = Form(None),
    user: dict = Depends(get_current_user_required)
):
    try:
        rating = max(0.5, min(5.0, round(float(rating) * 2) / 2))
        supabase = get_authenticated_client(user["access_token"])
        
        existing_fb = supabase.table("feedbacks").select("id").eq("item_id", item_id).eq("user_id", user["id"]).execute()
        feedback_payload = {
            "item_id": item_id,
            "user_id": user["id"],
            "rating": rating,
            "comment": comment.strip() if comment else None
        }

        if existing_fb.data and len(existing_fb.data) > 0:
            fb_id = existing_fb.data[0]["id"]
            supabase.table("feedbacks").update({
                "rating": rating,
                "comment": comment.strip() if comment else None
            }).eq("id", fb_id).execute()
        else:
            supabase.table("feedbacks").insert(feedback_payload).execute()
        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import urllib.parse
        err_msg = str(e)
        print("Error submitting feedback:", err_msg)
        return RedirectResponse(url=f"/lists/{list_id}?error={urllib.parse.quote(err_msg)}", status_code=status.HTTP_303_SEE_OTHER)

