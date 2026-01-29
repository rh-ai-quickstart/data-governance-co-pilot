import uvicorn


def main():
    """Run the FastAPI backend service"""
    uvicorn.run(
        "copilot.service:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        timeout_keep_alive=650,  # Keep connections alive for 10+ minutes (matches route timeout)
        timeout_graceful_shutdown=30  # Allow 30s for graceful shutdown
    )


if __name__ == "__main__":
    main()