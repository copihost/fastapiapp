from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from jose import jwt
from datetime import datetime, timedelta
from uuid import uuid4

# --- Database Setup ---
DATABASE_URL = "postgresql://postgres:postgres@localhost/postgres"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- JWT Setup ---
SECRET_KEY = "my_secret_key"
ALGORITHM = "HS256"

# --- Models ---
class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

class PostModel(Base):
    __tablename__ = "posts"
    id = Column(String, primary_key=True, index=True)
    username = Column(String, ForeignKey("users.username"))
    content = Column(Text)
    image = Column(String, default="")
    likes = Column(Integer, default=0)
    liked_by = Column(Text, default="")  # Can be JSON or separate table for real app

    comments = relationship("CommentModel", back_populates="post")

class CommentModel(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(String, ForeignKey("posts.id"))
    username = Column(String)
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    post = relationship("PostModel", back_populates="comments")

Base.metadata.create_all(bind=engine)

# --- Pydantic Schemas ---
class User(BaseModel):
    username: str
    password: str

class Post(BaseModel):
    content: str
    image: str = ""

class Comment(BaseModel):
    content: str

# --- App Setup ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_token(username):
    payload = {
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    return payload["username"]

@app.post("/signup")
def signup(user: User, db: Session = Depends(get_db)):
    if db.query(UserModel).filter_by(username=user.username).first():
        raise HTTPException(status_code=400, detail="Username already exists.")
    new_user = UserModel(username=user.username, password=user.password)
    db.add(new_user)
    db.commit()
    token = create_token(user.username)
    return {"token": token}

@app.post("/login")
def login(user: User, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter_by(username=user.username, password=user.password).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(user.username)
    return {"token": token}

@app.post("/posts")
def create_post(post: Post, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    username = get_current_user(credentials)
    new_post = PostModel(
        id=str(uuid4()),
        username=username,
        content=post.content,
        image=post.image,
    )
    db.add(new_post)
    db.commit()
    return new_post

@app.get("/posts")
def get_posts(db: Session = Depends(get_db)):
    posts = db.query(PostModel).all()
    return posts

@app.post("/posts/{post_id}/comments")
def add_comment(post_id: str, comment: Comment, credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    username = get_current_user(credentials)
    post = db.query(PostModel).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    new_comment = CommentModel(post_id=post_id, username=username, content=comment.content)
    db.add(new_comment)
    db.commit()
    return {"message": "Comment added"}

@app.patch("/posts/{post_id}/like")
def like_post(post_id: str, current_user: str = Depends(get_current_user), db: Session = Depends(get_db)):
    post = db.query(PostModel).filter_by(id=post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    liked_by_list = post.liked_by.split(",") if post.liked_by else []
    if current_user in liked_by_list:
        raise HTTPException(status_code=400, detail="Already liked")
    post.likes += 1
    liked_by_list.append(current_user)
    post.liked_by = ",".join(liked_by_list)
    db.commit()
    return post
# To run: uvicorn main:app --reload