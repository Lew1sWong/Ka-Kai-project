from __future__ import annotations

import json
import os
import hashlib
import hmac
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from mirrorquant_demo.database import Base, DATABASE_URL, SessionLocal, engine, get_session
from mirrorquant_demo.schemas import HeroCreate, SearchRunCreate, LoginRequest, RegisterRequest
from mirrorquant_demo.models import User
from mirrorquant_demo.search_service import (
    create_or_update_hero,
    get_saved_hero,
    get_search_run,
    list_saved_heroes,
    list_search_runs_for_hero,
    run_search_for_hero,
    seed_sample_heroes,
    validate_hero_window,
    archive_hero,
)

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_DIR = BACKEND_DIR.parent
LEGACY_PACKAGE_DIR = REPO_DIR / "mirrorquant_demo"
DATA_DIR = LEGACY_PACKAGE_DIR / "data"
LEGACY_STATIC_DIR = LEGACY_PACKAGE_DIR / "static"
FRONTEND_APP_URL = os.getenv("MIRRORQUANT_FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")
PRICES_PATH = DATA_DIR / "prices.csv"
MARKET_WATCH_PRICES_PATH = DATA_DIR / "market_watch_prices.csv"
MARKET_WATCH_SYMBOLS = {
    "SPY": "US Equities",
    "QQQ": "Growth Leadership",
    "IWM": "Small-Cap Breadth",
    "TLT": "Duration / Rates",
    "HYG": "Credit Appetite",
}
DEV_FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
SESSION_SECRET = os.getenv("MIRRORQUANT_SESSION_SECRET", "dev-secret-change-me")
DEV_USER_EMAIL = os.getenv("MIRRORQUANT_DEV_EMAIL", "local-dev@mirrorquant.app").strip().lower()
DEV_USER_PASSWORD = os.getenv("MIRRORQUANT_DEV_PASSWORD", "mirrorquant123")
PASSWORD_HASH_ITERATIONS = int(os.getenv("MIRRORQUANT_PASSWORD_HASH_ITERATIONS", "390000"))
VERIFICATION_TTL_HOURS = int(os.getenv("MIRRORQUANT_VERIFICATION_TTL_HOURS", "24"))
SMTP_HOST = os.getenv("MIRRORQUANT_SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("MIRRORQUANT_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("MIRRORQUANT_SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("MIRRORQUANT_SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("MIRRORQUANT_SMTP_FROM_EMAIL", "no-reply@mirrorquant.app").strip()
SMTP_USE_TLS = os.getenv("MIRRORQUANT_SMTP_USE_TLS", "true").strip().lower() == "true"
SMTP_USE_SSL = os.getenv("MIRRORQUANT_SMTP_USE_SSL", "false").strip().lower() == "true"
LEGACY_PASSWORD_HASHES = {"temporary-dev-password-hash"}

# Helper functions 
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${derived_key.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations_raw, salt, expected_hash = password_hash.split("$", 3)
            iterations = int(iterations_raw)
        except ValueError:
            return False

        candidate_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(candidate_hash, expected_hash)

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(password_hash, legacy_hash)


def _needs_password_upgrade(password_hash: str) -> bool:
    return not password_hash.startswith("pbkdf2_sha256$")


def _hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _serialize_user(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "verified_at": user.verified_at.isoformat() if user.verified_at else None,
    }


def _get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(User.email == email.lower())
    )


def _create_user(session: Session, email: str, password: str) -> User:
    existing = _get_user_by_email(session, email)
    if existing is not None:
        raise ValueError("An account with that email already exists.")

    user = User(
        email=email.lower(),
        password_hash=_hash_password(password),
        is_verified=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _build_verification_url(token: str) -> str:
    return f"{FRONTEND_APP_URL}/verify-email?token={quote(token)}"


def _issue_verification_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.verification_token_hash = _hash_verification_token(token)
    user.verification_token_expires_at = _utcnow() + timedelta(hours=VERIFICATION_TTL_HOURS)
    user.verification_sent_at = _utcnow()
    return token


def _send_email(message: EmailMessage) -> bool:
    if not SMTP_HOST:
        return False

    try:
        if SMTP_USE_SSL:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                if SMTP_USERNAME:
                    smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
                smtp.send_message(message)
            return True

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception as exc:
        print(f"[mirrorquant] smtp delivery failed: {exc}")
        return False


def _send_verification_email(user: User, verification_url: str) -> str:
    message = EmailMessage()
    message["Subject"] = "Verify your MirrorQuant email"
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = user.email
    message.set_content(
        "\n".join(
            [
                "Welcome to MirrorQuant.",
                "",
                "Verify your email by opening this link:",
                verification_url,
                "",
                f"This link expires in {VERIFICATION_TTL_HOURS} hours.",
            ]
        )
    )

    if _send_email(message):
        return "smtp"

    print(f"[mirrorquant] verification link for {user.email}: {verification_url}")
    return "dev-link"


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = session.get(User, user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_verified:
        raise HTTPException(status_code=403, detail="Verify your email before using MirrorQuant.")
    return current_user

def _load_json(filename: str):
    with (DATA_DIR / filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_prices(path: Path = PRICES_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    return df.sort_values(["ticker", "date"]).copy()


def _get_price_window(
    df: pd.DataFrame,
    ticker: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    return df[
        (df["ticker"] == ticker.upper())
        & (df["date"] >= pd.to_datetime(start_date))
        & (df["date"] <= pd.to_datetime(end_date))
    ].sort_values("date").copy()


def _serialize_close_series(window_df: pd.DataFrame) -> list[dict[str, str | float]]:
    return [
        {
            "date": row.date.strftime("%Y-%m-%d"),
            "close": float(row.close),
        }
        for row in window_df.itertuples(index=False)
    ]


def _trend_status(change_pct: float) -> str:
    if change_pct >= 0.05:
        return "Uptrend"
    if change_pct <= -0.05:
        return "Drawdown"
    return "Range-bound"


def _market_watch_headline(changes: dict[str, float]) -> str:
    positive_count = sum(change > 0 for change in changes.values())
    if (
        changes.get("SPY", 0) > 0
        and changes.get("QQQ", 0) > 0
        and changes.get("HYG", 0) > 0
    ):
        return "Risk-on with broad support"
    if positive_count <= 1 and changes.get("TLT", 0) < 0:
        return "Risk-off with rate pressure"
    return "Mixed tape with selective leadership"


def _build_live_market_watch() -> dict | None:
    if not MARKET_WATCH_PRICES_PATH.exists():
        return None

    df = _load_prices(MARKET_WATCH_PRICES_PATH)
    indicators = []
    changes: dict[str, float] = {}

    for ticker, label in MARKET_WATCH_SYMBOLS.items():
        window_df = df[df["ticker"] == ticker].sort_values("date").tail(40).copy()
        if len(window_df) < 2:
            continue

        first_close = float(window_df["close"].iloc[0])
        last_close = float(window_df["close"].iloc[-1])
        change_pct = (last_close / first_close) - 1.0
        changes[ticker] = change_pct

        indicators.append(
            {
                "symbol": ticker,
                "name": label,
                "value": f"{last_close:.2f}",
                "status": _trend_status(change_pct),
                "insight": (
                    f"{ticker} moved {change_pct * 100:+.1f}% over the latest "
                    f"{len(window_df)} sessions, giving a live read on {label.lower()}."
                ),
                "series": _serialize_close_series(window_df),
                "change_pct": round(change_pct * 100, 2),
                "as_of": window_df["date"].iloc[-1].strftime("%Y-%m-%d"),
            }
        )

    if not indicators:
        return None

    as_of = max(indicator["as_of"] for indicator in indicators)
    return {
        "as_of": as_of,
        "headline_regime": _market_watch_headline(changes),
        "indicators": indicators,
    }


def _frontend_asset(path: Path) -> FileResponse:
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Frontend asset not found")
    return FileResponse(path)


def _frontend_redirect(path: str = "") -> RedirectResponse:
    cleaned_path = path.lstrip("/")
    target = FRONTEND_APP_URL if not cleaned_path else f"{FRONTEND_APP_URL}/{cleaned_path}"
    return RedirectResponse(target, status_code=307)

# Returns ID of admin account
def _ensure_dev_user(session: Session) -> int:
    user = _get_user_by_email(session, DEV_USER_EMAIL)
    if user is None:
        user = User(
            email=DEV_USER_EMAIL,
            password_hash=_hash_password(DEV_USER_PASSWORD),
            is_verified=True,
            verified_at=_utcnow(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id

    if user.password_hash in LEGACY_PASSWORD_HASHES or not user.is_verified:
        user.password_hash = _hash_password(DEV_USER_PASSWORD)
        user.is_verified = True
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        user.verification_sent_at = None
        user.verified_at = user.verified_at or _utcnow()
        session.commit()
        session.refresh(user)

    return user.id

app = FastAPI(
    title="MirrorQuant API",
    version="0.2.0",
    description="API for the MirrorQuant product workflow.",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,  # local dev only
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    if DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        user_id = _ensure_dev_user(session)
        seed_sample_heroes(session, user_id)


@app.get("/", include_in_schema=False)
async def index():
    return _frontend_redirect()


@app.get("/static/{asset_path:path}", include_in_schema=False)
async def legacy_static_files(asset_path: str):
    return _frontend_asset(LEGACY_STATIC_DIR / asset_path)


@app.get("/health")
async def health():
    return {"status": "ok", "app": "mirrorquant"}


@app.get("/api/heroes")
async def list_heroes(
    current_user: User = Depends(get_current_verified_user),
    session: Session = Depends(get_session)
):
    return {"heroes": list_saved_heroes(session, current_user.id)}


@app.post("/api/heroes")
async def create_hero(
    payload: HeroCreate, 
    current_user: User = Depends(get_current_verified_user),
    session: Session = Depends(get_session)
):
    try:
        return create_or_update_hero(session, payload, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/heroes/{hero_id}")
async def get_hero(
    hero_id: int,
    current_user: User = Depends(get_current_verified_user),    
    session: Session = Depends(get_session)
):
    hero = get_saved_hero(session, hero_id, current_user.id)
    if hero is None:
        raise HTTPException(status_code=404, detail=f"Hero {hero_id} was not found")
    return hero


@app.get("/api/heroes/{hero_id}/search-runs")
async def list_hero_search_runs(
    hero_id: int, 
    current_user: User = Depends(get_current_verified_user),
    session: Session = Depends(get_session)
):
    hero = get_saved_hero(session, hero_id, current_user.id)
    if hero is None:
        raise HTTPException(status_code=404, detail=f"Hero {hero_id} was not found")
    return {"search_runs": list_search_runs_for_hero(session, hero_id, current_user.id)}


@app.post("/api/heroes/{hero_id}/search-runs")
async def create_search_run(
    hero_id: int,
    payload: SearchRunCreate,
    current_user: User = Depends(get_current_verified_user),
    session: Session = Depends(get_session),
):
    try:
        return run_search_for_hero(session, hero_id, payload.mode, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/search-runs/{search_run_id}")
async def get_saved_search_run(
    search_run_id: int, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
):
    run = get_search_run(session, search_run_id, current_user.id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Search run {search_run_id} was not found",
        )
    return run


@app.get("/api/price-series")
async def get_price_series(ticker: str, start_date: str, end_date: str):
    try:
        validate_hero_window(
            ticker=ticker.upper(),
            start_date=pd.to_datetime(start_date).date(),
            end_date=pd.to_datetime(end_date).date(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    df = _load_prices()
    ticker_df = df[df["ticker"] == ticker.upper()].sort_values("date").copy()
    window_df = _get_price_window(df, ticker, start_date, end_date)

    return {
        "ticker": ticker.upper(),
        "available_start_date": ticker_df["date"].iloc[0].strftime("%Y-%m-%d"),
        "available_end_date": ticker_df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "start_date": start_date,
        "end_date": end_date,
        "series": _serialize_close_series(ticker_df),
        "window_series": _serialize_close_series(window_df),
    }


@app.get("/api/market-watch")
async def get_market_watch():
    live_market_watch = _build_live_market_watch()
    if live_market_watch is not None:
        return live_market_watch
    return _load_json("market_watch.json")


@app.get("/api/industry-chain/{ticker}")
async def get_industry_chain(ticker: str):
    chain_data = _load_json("industry_chain.json")
    normalized = ticker.upper()
    return {"ticker": normalized, "relationships": chain_data.get(normalized, [])}


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str, request: Request):
    if full_path.startswith("api/") or full_path == "health":
        raise HTTPException(status_code=404, detail="Route not found")
    redirect_path = full_path
    if request.url.query:
        redirect_path = f"{redirect_path}?{request.url.query}"
    return _frontend_redirect(redirect_path)


@app.post("/api/heroes/{hero_id}/archive")
async def archive_saved_hero(
    hero_id: int,
    current_user: User = Depends(get_current_verified_user), 
    session: Session = Depends(get_session)):
    try:
        return archive_hero(session, hero_id, current_user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@app.post("/api/auth/login")
async def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    user = _get_user_by_email(session, payload.email)
    if user is None or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if _needs_password_upgrade(user.password_hash):
        user.password_hash = _hash_password(payload.password)
        session.commit()

    request.session["user_id"] = user.id
    return {"user": _serialize_user(user)}


@app.post("/api/auth/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    try:
        user = _create_user(session, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    token = _issue_verification_token(user)
    session.commit()
    session.refresh(user)
    verification_url = _build_verification_url(token)
    delivery = _send_verification_email(user, verification_url)

    request.session["user_id"] = user.id
    response = {
        "user": _serialize_user(user),
        "verification_delivery": delivery,
    }
    if delivery == "dev-link":
        response["verification_url"] = verification_url
    return response


@app.get("/api/auth/verify-email")
async def verify_email(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
):
    hashed_token = _hash_verification_token(token)
    user = session.scalar(
        select(User).where(User.verification_token_hash == hashed_token)
    )
    if user is None:
        raise HTTPException(status_code=400, detail="Verification link is invalid.")

    if user.verification_token_expires_at is None or user.verification_token_expires_at < _utcnow():
        raise HTTPException(status_code=400, detail="Verification link has expired.")

    user.is_verified = True
    user.verified_at = _utcnow()
    user.verification_token_hash = None
    user.verification_token_expires_at = None
    session.commit()
    session.refresh(user)
    request.session["user_id"] = user.id
    return {"ok": True, "user": _serialize_user(user)}


@app.post("/api/auth/resend-verification")
async def resend_verification(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if current_user.is_verified:
        return {"ok": True, "user": _serialize_user(current_user), "already_verified": True}

    token = _issue_verification_token(current_user)
    session.commit()
    session.refresh(current_user)
    verification_url = _build_verification_url(token)
    delivery = _send_verification_email(current_user, verification_url)

    response = {
        "ok": True,
        "user": _serialize_user(current_user),
        "verification_delivery": delivery,
    }
    if delivery == "dev-link":
        response["verification_url"] = verification_url
    return response


@app.post("/api/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"user": _serialize_user(current_user)}
