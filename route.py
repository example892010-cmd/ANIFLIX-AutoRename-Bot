"""Minimal HTTP health endpoint for Render web services."""

from aiohttp import web

routes = web.RouteTableDef()


@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({"status": "ok", "service": "ANIFLIX Auto-Rename Bot"})


@routes.get("/health", allow_head=True)
async def health_route_handler(request):
    return web.json_response({"status": "healthy"})


async def web_server():
    app = web.Application()
    app.add_routes(routes)
    return app
