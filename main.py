from datetime import datetime, timedelta
import json
import os

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import bcrypt
from pydantic import BaseModel
from sqlalchemy import Boolean, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

# Banco: usa DATABASE_URL (Postgres no Render) e cai para SQLite local se nao existir.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./kendo.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
JWT_SECRET = os.getenv("JWT_SECRET", "kendo-rpg-development-secret")
JWT_ALGORITHM = "HS256"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    xp: Mapped[int] = mapped_column(Integer, default=0)

    mission_progress: Mapped[list["MissionProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(30))
    xp: Mapped[int] = mapped_column(Integer)
    level_required: Mapped[int] = mapped_column(Integer, default=1)


class MissionProgress(Base):
    __tablename__ = "mission_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id"))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="mission_progress")


Base.metadata.create_all(engine)

app = FastAPI(title="Kendo RPG Status")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class AuthPayload(BaseModel):
    username: str
    password: str


def db_session():
    with Session(engine) as session:
        yield session


def level_for_xp(xp: int) -> int:
    if xp < 250:
        return 1
    if xp < 500:
        return 2
    if xp < 750:
        return 3
    if xp < 1000:
        return 4
    if xp < 1250:
        return 5
    return 6


def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_user(authorization: str = Header(default=""), session: Session = Depends(db_session)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token não informado")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def seed_missions(session: Session):
    with open("misoes.json", "r", encoding="utf-8") as mission_file:
        mission_module = json.load(mission_file)

    mission_entries = [
        mission
        for level in mission_module["levels"]
        for mission in level["missions"]
    ]

    if len(mission_entries) != 29:
        raise RuntimeError(f"Esperadas 29 missões no misoes.json, encontradas {len(mission_entries)}")

    # Atualiza pelo titulo e cria so o que falta. Nunca apaga missoes nem o progresso dos usuarios.
    existing = {mission.title: mission for mission in session.scalars(select(Mission)).all()}

    for index, mission in enumerate(mission_entries):
        level_required = (index // 5) + 1
        objective = mission["objective"]
        instructions = mission["instructions"]
        description = f"{objective}\n\n{instructions}\n\nComplemento: {mission['strength_complement']}"

        current = existing.get(mission["title"])
        if current:
            current.description = description
            current.category = "KENDO"
            current.xp = 50
            current.level_required = level_required
        else:
            new_mission = Mission(
                title=mission["title"],
                description=description,
                category="KENDO",
                xp=50,
                level_required=level_required,
            )
            session.add(new_mission)
            existing[mission["title"]] = new_mission

    session.commit()


with Session(engine) as startup_session:
    seed_missions(startup_session)


@app.post("/api/register")
def register(payload: AuthPayload, session: Session = Depends(db_session)):
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Usuário precisa ter pelo menos 3 caracteres")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Senha precisa ter pelo menos 6 caracteres")
    if session.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=409, detail="Usuário já existe")

    user = User(username=username, password_hash=hash_password(payload.password), xp=0)
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"token": create_token(user.id)}


@app.post("/api/login")
def login(payload: AuthPayload, session: Session = Depends(db_session)):
    user = session.scalar(select(User).where(User.username == payload.username.strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    return {"token": create_token(user.id)}


@app.get("/api/me")
def me(user: User = Depends(current_user), session: Session = Depends(db_session)):
    return {
        "id": user.id,
        "username": user.username,
        "xp": user.xp,
        "level": level_for_xp(user.xp),
    }


def mission_details(title: str):
    with open("misoes.json", "r", encoding="utf-8") as mission_file:
        mission_module = json.load(mission_file)
    for level in mission_module["levels"]:
        for mission in level["missions"]:
            if mission["title"] == title:
                mission_number = mission["mission_number"]
                image_number = mission_number if mission_number < 9 else mission_number - 1
                return {
                    "objective": mission["objective"],
                    "strength_complement": mission["strength_complement"],
                    "image": f"/static/mission_images/{image_number}.jpg",
                }
    return {"objective": "", "strength_complement": "", "image": ""}


@app.get("/api/missions")
def missions(user: User = Depends(current_user), session: Session = Depends(db_session)):
    mission_rows = session.scalars(select(Mission).order_by(Mission.level_required, Mission.id)).all()
    level = level_for_xp(user.xp)
    completed_ids = {
        progress.mission_id
        for progress in session.scalars(select(MissionProgress).where(MissionProgress.user_id == user.id, MissionProgress.completed.is_(True))).all()
    }
    return [
        {
            "id": mission.id,
            "title": mission.title,
            "description": mission.description,
            "objective": mission_details(mission.title)["objective"],
            "strength_complement": mission_details(mission.title)["strength_complement"],
            "image": mission_details(mission.title)["image"],
            "category": mission.category,
            "xp": mission.xp,
            "level_required": mission.level_required,
            "locked": mission.level_required > level,
            "completed": mission.id in completed_ids,
        }
        for mission in mission_rows
    ]


@app.post("/api/missions/{mission_id}/complete")
def complete_mission(mission_id: int, user: User = Depends(current_user), session: Session = Depends(db_session)):
    mission = session.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Missão não encontrada")

    level = level_for_xp(user.xp)
    if level < mission.level_required:
        raise HTTPException(status_code=403, detail="Nível insuficiente para esta missão")

    progress = session.scalar(
        select(MissionProgress).where(
            MissionProgress.user_id == user.id,
            MissionProgress.mission_id == mission.id,
        )
    )
    if progress and progress.completed:
        raise HTTPException(status_code=409, detail="Missão já concluída")

    if progress:
        progress.completed = True
    else:
        session.add(MissionProgress(user_id=user.id, mission_id=mission.id, completed=True))

    user.xp += mission.xp
    session.commit()
    session.refresh(user)
    return {"xp": user.xp, "level": level_for_xp(user.xp)}


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"page": "dashboard"})


@app.get("/missions", response_class=HTMLResponse)
def missions_page(request: Request):
    return templates.TemplateResponse(request=request, name="missions.html", context={"page": "missions"})


@app.get("/rank", response_class=HTMLResponse)
def rank_page(request: Request):
    return templates.TemplateResponse(request=request, name="rank.html", context={"page": "rank"})


@app.get("/auth", response_class=HTMLResponse)
def auth_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth.html", context={"page": "auth"})
