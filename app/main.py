# app/main.py


from app.monitor_integration import app
# Load environment variables

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)