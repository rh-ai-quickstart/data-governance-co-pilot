import uvicorn


def main():
    """Run the FastAPI backend service"""
    uvicorn.run(
        "copilot.service:app",
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )


if __name__ == "__main__":
    main()