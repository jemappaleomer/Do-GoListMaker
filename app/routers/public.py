from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR
from app.core.dependencies import get_current_user_optional

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="legal/privacy.html",
        context={"user": user}
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="legal/terms.html",
        context={"user": user}
    )


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="legal/faq.html",
        context={"user": user}
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    content = f"""User-agent: *
Allow: /
Allow: /privacy
Allow: /terms
Allow: /faq
Disallow: /api/
Disallow: /static/

Sitemap: {base_url}/sitemap.xml
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@router.get("/sitemap.xml")
def sitemap_xml(request: Request):
    base_url = str(request.base_url).rstrip("/")
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/faq</loc>
        <changefreq>weekly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>{base_url}/privacy</loc>
        <changefreq>monthly</changefreq>
        <priority>0.5</priority>
    </url>
    <url>
        <loc>{base_url}/terms</loc>
        <changefreq>monthly</changefreq>
        <priority>0.5</priority>
    </url>
</urlset>
"""
    return Response(content=xml_content, media_type="application/xml")


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    content = f"""# Do&Go List Maker
> Collaborative List & Activity Planner with Granular Ratings and Location Tracking

## Overview
Do&Go List Maker is a modern, responsive web application designed for friends and groups to collaboratively create, share, and manage activity, travel, and task lists.

## Key Features
- Collaborative Lists: Real-time public/shared lists with granular permissions (view, edit, delete).
- Granular 0.5-Star Rating System: Rate visited venues and activities from 0.5 to 5.0 stars with cumulative visual stars.
- Location Tracking: Direct integration with Google Maps URLs for quick navigation.
- Secure Authentication: HttpOnly session cookie handling integrated with Supabase PostgreSQL and Row Level Security (RLS).

## Public Endpoints
- Homepage: {base_url}/
- Frequently Asked Questions: {base_url}/faq
- Privacy Policy: {base_url}/privacy
- Terms of Service: {base_url}/terms
- Sitemap: {base_url}/sitemap.xml
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@router.get("/manifest.json")
def manifest_json():
    manifest = {
        "name": "Do&Go List Maker",
        "short_name": "Do&Go",
        "description": "Arkadaşlarla organize olmanın en kolay yolu.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#10b981",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    import json
    return Response(content=json.dumps(manifest), media_type="application/manifest+json")
