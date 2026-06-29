"""Entry point: uv run router  or  python -m router"""
import uvicorn

from router.server import app


def main():
    uvicorn.run(app, host="0.0.0.0", port=9002, reload=False)


if __name__ == "__main__":
    main()
