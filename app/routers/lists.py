import logging
import urllib.parse
from urllib.parse import urlparse
from typing import Optional, List
from fastapi import APIRouter, Request, Form, Depends, status, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR
from app.core.dependencies import get_current_user_required, get_current_user_optional
from app.core.supabase import get_authenticated_client, get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lists", tags=["lists"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def sanitize_url(raw_url: Optional[str]) -> Optional[str]:
    """Sadece güvenli http/https şemalarını kabul eder, XSS/javascript enjeksiyonlarını engeller."""
    if not raw_url:
        return None
    clean = raw_url.strip()
    if not clean:
        return None
    parsed = urlparse(clean)
    if not parsed.scheme:
        clean = "https://" + clean
        parsed = urlparse(clean)
    if parsed.scheme.lower() not in ("http", "https"):
        return None
    return clean


def safe_error_param(msg: str) -> str:
    """Kullanıcı dostu hata mesajını güvenli bir şekilde URL için encode eder."""
    return urllib.parse.quote(msg)


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

        # 2. Kullanıcıyla paylaşılan ve kaydedilen listeler
        # Kullanıcının list_permissions tablosundaki kayıtlarını çek.
        try:
            perm_res = supabase.table("list_permissions").select("list_id, can_delete").eq("user_id", user["id"]).execute()
            if perm_res.data:
                perm_map = {p["list_id"]: p.get("can_delete", False) for p in perm_res.data if p.get("list_id")}
                list_ids = list(perm_map.keys())
                if list_ids:
                    # Kullanıcının kendi listeleri zaten my_lists içinde, sadece diğer kullanıcıların listelerini getir
                    try:
                        lists_res = supabase.table("lists").select("*, profiles:owner_id(username)").in_("id", list_ids).execute()
                    except Exception:
                        lists_res = supabase.table("lists").select("*").in_("id", list_ids).execute()
                    
                    for l_data in (lists_res.data or []):
                        if l_data.get("owner_id") != user["id"]:
                            l_data["can_delete_perm"] = perm_map.get(l_data["id"], False)
                            shared_lists.append(l_data)
        except Exception as e_perm:
            logger.warning("Error fetching shared list permissions: %s", e_perm)
    except Exception as e:
        logger.exception("Error fetching lists: %s", e)

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
        clean_title = title.strip()
        if not clean_title:
            return RedirectResponse(url=f"/lists?error={safe_error_param('Liste başlığı boş olamaz.')}", status_code=status.HTTP_303_SEE_OTHER)

        supabase = get_authenticated_client(user["access_token"])
        
        # Profilin profiles tablosunda var olduğunu kesinleştir
        try:
            supabase.table("profiles").upsert({
                "id": user["id"],
                "username": user.get("username", "user"),
                "email": user.get("email", "")
            }, on_conflict="id").execute()
        except Exception as pe:
            logger.warning("Ensure profile error in create_list: %s", pe)

        payload = {
            "title": clean_title,
            "description": description.strip() if description else None,
            "owner_id": user["id"],
            "is_shared": is_shared
        }

        try:
            supabase.table("lists").insert(payload).execute()
        except Exception as insert_err:
            logger.info("Initial insert failed, trying with is_public fallback: %s", insert_err)
            payload.pop("is_shared", None)
            payload["is_public"] = is_shared
            supabase.table("lists").insert(payload).execute()

        return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.exception("Error creating list: %s", e)
        return RedirectResponse(url=f"/lists?error={safe_error_param('Liste oluşturulurken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{list_id}", response_class=HTMLResponse)
async def get_list(list_id: str, request: Request, error: Optional[str] = None, notice: Optional[str] = None, user: dict = Depends(get_current_user_optional)):
    try:
        client = get_authenticated_client(user["access_token"]) if user else get_supabase_client()
        
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

        # Liste gizliyse ve bakan kişi sahibi değilse
        if not is_shared and not is_owner:
            if user:
                perm_check = client.table("list_permissions").select("id").eq("list_id", list_id).eq("user_id", user["id"]).execute()
                if not perm_check.data or len(perm_check.data) == 0:
                    return RedirectResponse(url="/lists", status_code=status.HTTP_302_FOUND)
            else:
                return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

        # Ortak listeye katılım durumu (is_saved)
        # Sadece kullanıcı daha önce "Listelerime Kaydet" butonuna basmışsa True olur.
        # Linki salt görüntüleyen kullanıcılar için otomatik olarak kaydedilmez.
        is_saved = is_owner
        can_delete = is_owner
        if user and not is_owner:
            try:
                perm_res = client.table("list_permissions").select("id, can_delete").eq("list_id", list_id).eq("user_id", user["id"]).execute()
                if perm_res.data and len(perm_res.data) > 0:
                    is_saved = True
                    can_delete = perm_res.data[0].get("can_delete", False)
                else:
                    is_saved = False
                    can_delete = False
            except Exception as pe:
                logger.warning("Permission check warning in get_list: %s", pe)
                is_saved = False
                can_delete = False

        # Liste maddelerini çek (Önce position, sonra created_at)
        raw_items = []
        try:
            items_res = client.table("list_items").select("*, profiles:created_by(username)").eq("list_id", list_id).order("position", desc=False).order("created_at", desc=False).execute()
            raw_items = items_res.data or []
        except Exception:
            try:
                items_res = client.table("list_items").select("*, profiles:created_by(username)").eq("list_id", list_id).order("created_at", desc=False).execute()
                raw_items = items_res.data or []
            except Exception:
                try:
                    items_res = client.table("list_items").select("*").eq("list_id", list_id).order("created_at", desc=False).execute()
                    raw_items = items_res.data or []
                except Exception as ie:
                    logger.warning("Error loading list items: %s", ie)

        completed_count = sum(1 for item in raw_items if item.get("is_completed"))

        # Feedback ve puanları çek
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
                    logger.warning("Error loading feedbacks: %s", fe)

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

        # Katılımcıları listele
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
                    logger.warning("Error loading collaborators: %s", ce)

        return templates.TemplateResponse(
            request=request,
            name="lists/detail.html",
            context={
                "user": user,
                "list_data": list_data,
                "items": items,
                "completed_count": completed_count,
                "is_owner": is_owner,
                "is_saved": is_saved,
                "can_delete": can_delete,
                "collaborators": collaborators,
                "error": error,
                "notice": notice
            }
        )
    except Exception as e:
        logger.exception("Error getting list: %s", e)
        return RedirectResponse(url=f"/lists?error={safe_error_param('Liste yüklenirken bir hata oluştu.')}", status_code=status.HTTP_302_FOUND)


@router.post("/{list_id}/save")
async def save_shared_list(list_id: str, user: dict = Depends(get_current_user_required)):
    """Kullanıcının paylaşılan bir ortak listeyi kendi listelerine kaydetmesi."""
    try:
        supabase = get_authenticated_client(user["access_token"])
        
        # Listenin paylaşıma açık olduğunu ve varlığını doğrula (authenticated istemci ile)
        list_res = supabase.table("lists").select("id, owner_id, is_shared, is_public").eq("id", list_id).execute()
        if not list_res.data:
            # Fallback service client ile kontrol
            try:
                service_client = get_supabase_client()
                list_res = service_client.table("lists").select("id, owner_id, is_shared, is_public").eq("id", list_id).execute()
            except Exception:
                pass

        if not list_res.data:
            return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)

        l_data = list_res.data[0]
        if l_data.get("owner_id") == user["id"]:
            return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)

        # Profil kaydını profiles tablosunda sağla (authenticated kullanıcı kendi profilini ekleyebilir/güncelleyebilir)
        try:
            supabase.table("profiles").upsert({
                "id": user["id"],
                "username": user.get("username", "user"),
                "email": user.get("email", "")
            }, on_conflict="id").execute()
        except Exception as pe:
            logger.debug("Profile upsert in save_shared_list: %s", pe)

        # list_permissions tablosuna önceden eklenmiş mi kontrol et
        try:
            perm_check = supabase.table("list_permissions").select("id").eq("list_id", list_id).eq("user_id", user["id"]).execute()
            if not perm_check.data:
                supabase.table("list_permissions").insert({
                    "list_id": list_id,
                    "user_id": user["id"],
                    "permission_level": "edit"
                }).execute()
        except Exception as perm_err:
            logger.warning("Error inserting list_permissions with auth client: %s", perm_err)
            # Alternatif fallback (eğer RLS izin verirse)
            try:
                service_client = get_supabase_client()
                service_client.table("list_permissions").upsert({
                    "list_id": list_id,
                    "user_id": user["id"],
                    "permission_level": "edit"
                }, on_conflict="list_id,user_id").execute()
            except Exception as se:
                logger.error("Fallback permission upsert failed: %s", se)
                raise se

        return RedirectResponse(
            url=f"/lists/{list_id}?notice={safe_error_param('Ortak liste başarıyla listelerinize kaydedildi!')}", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    except Exception as e:
        logger.exception("Error saving shared list: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Liste kaydedilirken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


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
        logger.exception("Error toggling share: %s", e)
    return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/delete")
async def delete_list(list_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        supabase.table("lists").delete().eq("id", list_id).eq("owner_id", user["id"]).execute()
    except Exception as e:
        logger.exception("Error deleting list: %s", e)
    return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/items")
async def add_item(
    list_id: str,
    title: str = Form(...),
    list_type: str = Form("GO"),
    tag: str = Form("cafe"),
    media_platform: Optional[str] = Form(None),
    market_name: Optional[str] = Form(None),
    location_url: Optional[str] = Form(None),
    user: dict = Depends(get_current_user_required)
):
    try:
        clean_title = title.strip()
        if not clean_title:
            return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe başlığı boş olamaz.')}", status_code=status.HTTP_303_SEE_OTHER)

        safe_loc_url = sanitize_url(location_url)
        clean_platform = media_platform.strip() if media_platform and media_platform.strip() != "None" else None
        clean_market = market_name.strip() if market_name else None

        supabase = get_authenticated_client(user["access_token"])
        payload = {
            "list_id": list_id,
            "title": clean_title,
            "list_type": list_type,
            "tag": tag,
            "media_platform": clean_platform,
            "market_name": clean_market,
            "location_url": safe_loc_url,
            "is_completed": False
        }

        # 1. Tüm dinamik alanlarla + created_by ile eklemeyi dene
        try:
            p_full = {**payload, "created_by": user["id"]}
            supabase.table("list_items").insert(p_full).execute()
        except Exception as e1:
            logger.info("Insert full failed, trying without created_by: %s", e1)
            try:
                # 2. created_by olmadan dinamik alanlarla dene
                supabase.table("list_items").insert(payload).execute()
            except Exception as e2:
                logger.info("Insert with dynamic fields failed, falling back to basic columns: %s", e2)
                # 3. Eski şema uyumluluğu için sadece temel alanlarla ekle
                basic_payload = {
                    "list_id": list_id,
                    "title": clean_title,
                    "location_url": safe_loc_url,
                    "is_completed": False
                }
                supabase.table("list_items").insert(basic_payload).execute()

        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.exception("Error adding item: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe eklenirken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/items/{item_id}/toggle")
async def toggle_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    try:
        supabase = get_authenticated_client(user["access_token"])
        item_res = supabase.table("list_items").select("is_completed").eq("id", item_id).eq("list_id", list_id).single().execute()
        if item_res.data:
            current_status = item_res.data.get("is_completed", False)
            supabase.table("list_items").update({
                "is_completed": not current_status
            }).eq("id", item_id).eq("list_id", list_id).execute()
        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.exception("Error toggling item: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe durumu güncellenirken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/items/{item_id}/delete")
async def delete_item(list_id: str, item_id: str, user: dict = Depends(get_current_user_required)):
    """IDOR / BOLA koruması: Sadece liste sahibi veya silme yetkili ortak silebilir."""
    try:
        supabase = get_authenticated_client(user["access_token"])
        
        # 1. Listenin sahibini kontrol et
        list_res = supabase.table("lists").select("owner_id").eq("id", list_id).single().execute()
        if not list_res.data:
            return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)

        is_owner = list_res.data.get("owner_id") == user["id"]
        
        # 2. Sahip değilse katılımcı silme yetkisini doğrula
        has_perm = False
        if not is_owner:
            perm_res = supabase.table("list_permissions").select("can_delete").eq("list_id", list_id).eq("user_id", user["id"]).execute()
            has_perm = bool(perm_res.data and perm_res.data[0].get("can_delete", False))

        if not is_owner and not has_perm:
            logger.warning("Unauthorized item deletion attempt by user %s on list %s", user["id"], list_id)
            return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Bu öğeyi silme yetkiniz bulunmuyor.')}", status_code=status.HTTP_303_SEE_OTHER)

        # Doğrulanmış silme
        supabase.table("list_items").delete().eq("id", item_id).eq("list_id", list_id).execute()
        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.exception("Error deleting item: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe silinirken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


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
        logger.exception("Error submitting feedback: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Puan kaydedilirken bir sorun oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/items/{item_id}/edit")
async def edit_item(
    list_id: str,
    item_id: str,
    title: str = Form(...),
    list_type: str = Form("GO"),
    tag: str = Form("cafe"),
    media_platform: Optional[str] = Form(None),
    market_name: Optional[str] = Form(None),
    location_url: Optional[str] = Form(None),
    user: dict = Depends(get_current_user_required)
):
    """Kullanıcının yanlış kategori/etiket veya başlık girdiği öğeleri düzenlemesi."""
    try:
        clean_title = title.strip()
        if not clean_title:
            return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe başlığı boş olamaz.')}", status_code=status.HTTP_303_SEE_OTHER)

        safe_loc_url = sanitize_url(location_url)
        clean_platform = media_platform.strip() if media_platform and media_platform.strip() != "None" else None
        clean_market = market_name.strip() if market_name else None

        supabase = get_authenticated_client(user["access_token"])

        # Yetki kontrolü (liste sahibi veya izinli kullanıcı)
        list_res = supabase.table("lists").select("owner_id").eq("id", list_id).single().execute()
        if not list_res.data:
            return RedirectResponse(url="/lists", status_code=status.HTTP_303_SEE_OTHER)

        is_owner = list_res.data.get("owner_id") == user["id"]
        if not is_owner:
            perm_res = supabase.table("list_permissions").select("id").eq("list_id", list_id).eq("user_id", user["id"]).execute()
            if not perm_res.data:
                return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Bu öğeyi düzenleme yetkiniz yok.')}", status_code=status.HTTP_303_SEE_OTHER)

        # Güncelleme yükü
        update_payload = {
            "title": clean_title,
            "list_type": list_type,
            "tag": tag,
            "media_platform": clean_platform,
            "market_name": clean_market,
            "location_url": safe_loc_url
        }

        try:
            supabase.table("list_items").update(update_payload).eq("id", item_id).eq("list_id", list_id).execute()
        except Exception as u1:
            logger.info("Update with all fields failed, trying basic update: %s", u1)
            # Eski DB sütunları uyumluluk fallback'i
            basic_update = {
                "title": clean_title,
                "location_url": safe_loc_url
            }
            supabase.table("list_items").update(basic_update).eq("id", item_id).eq("list_id", list_id).execute()

        return RedirectResponse(url=f"/lists/{list_id}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.exception("Error editing item: %s", e)
        return RedirectResponse(url=f"/lists/{list_id}?error={safe_error_param('Öğe düzenlenirken bir hata oluştu.')}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{list_id}/items/reorder")
async def reorder_items(
    list_id: str,
    payload: dict = Body(...),
    user: dict = Depends(get_current_user_required)
):
    """Sürükle-bırak (drag and drop) sonrası öğe sıralamasını güncelleme."""
    try:
        ordered_ids = payload.get("item_ids", [])
        if not isinstance(ordered_ids, list) or not ordered_ids:
            return JSONResponse(status_code=400, content={"error": "Geçersiz öğe listesi."})

        supabase = get_authenticated_client(user["access_token"])

        # Yetki kontrolü (liste sahibi veya katılımcı)
        list_res = supabase.table("lists").select("owner_id").eq("id", list_id).single().execute()
        if not list_res.data:
            return JSONResponse(status_code=404, content={"error": "Liste bulunamadı."})

        is_owner = list_res.data.get("owner_id") == user["id"]
        if not is_owner:
            perm_res = supabase.table("list_permissions").select("id").eq("list_id", list_id).eq("user_id", user["id"]).execute()
            if not perm_res.data:
                return JSONResponse(status_code=403, content={"error": "Yetkiniz bulunmuyor."})

        # Her öğenin position değerini güncelle
        for idx, item_id in enumerate(ordered_ids):
            try:
                supabase.table("list_items").update({"position": idx}).eq("id", item_id).eq("list_id", list_id).execute()
            except Exception as pe:
                logger.info("Position update ignored for item %s: %s", item_id, pe)

        return JSONResponse(status_code=200, content={"success": True, "message": "Sıralama kaydedildi."})
    except Exception as e:
        logger.exception("Error reordering items: %s", e)
        return JSONResponse(status_code=500, content={"error": "Sıralama güncellenemedi."})
