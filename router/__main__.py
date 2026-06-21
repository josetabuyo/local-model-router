"""Entry point: uv run router  or  python -m router"""
import uvicorn


def main():
    uvicorn.run("router.server:app", host="0.0.0.0", port=11435, reload=False)


if __name__ == "__main__":
    main()
