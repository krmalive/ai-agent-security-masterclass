from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from insecure_agent import perform_file_ops as insecure_file_ops
from secure_agent import perform_file_ops as secure_file_ops

app = FastAPI(title="MCP Tool Allowlisting Demo")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def insecure_route(request: Request):
    """Insecure route - default route with neutral/blue theme"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "route_type": "insecure",
            "title": "Insecure Route",
            "description": "This is the default insecure route",
            "response": None,
        },
    )


@app.post("/", response_class=HTMLResponse)
async def insecure_route_post(request: Request, prompt: str = Form(...)):
    """Handle POST request for insecure route"""
    # Call the insecure agent to process the prompt
    response = await insecure_file_ops(prompt)
    
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "route_type": "insecure",
            "title": "Insecure Route",
            "description": "This is the default insecure route",
            "prompt": prompt,
            "response": response,
        },
    )


@app.get("/secure", response_class=HTMLResponse)
async def secure_route(request: Request):
    """Secure route - with green security-oriented theme"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "route_type": "secure",
            "title": "Secure Route",
            "description": "This is the secure route with allowlisted tools",
            "response": None,
        },
    )


@app.post("/secure", response_class=HTMLResponse)
async def secure_route_post(request: Request, prompt: str = Form(...)):
    """Handle POST request for secure route"""
    # Call the secure agent to process the prompt with allowlisted tools
    response = await secure_file_ops(prompt)
    
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "route_type": "secure",
            "title": "Secure Route",
            "description": "This is the secure route with allowlisted tools",
            "prompt": prompt,
            "response": response,
        },
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8443, reload=True)
