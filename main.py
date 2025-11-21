from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import contextlib
import uvicorn

import json
from config import settings
from gnews import mcp as gnews_mcp_server

# Create a combined  lifespan to manage the MCP session manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with gnews_mcp_server.session_manager.run():
        yield

app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create MCP server app and mount it
mcp_server = gnews_mcp_server.streamable_http_app()
# Mount the MCP server at the root path
app.mount("/", mcp_server)

def main():
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="debug",
    )

if __name__ == "__main__":
    main()


