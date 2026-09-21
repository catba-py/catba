"""CatBa route: the server boundary for the root page."""


async def GET(ctx):
    return {
        "message": "Hello, CatBa",
    }
