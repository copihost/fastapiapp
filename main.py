from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
from fastapi import Request
from uuid import uuid4
from datetime import datetime, timedelta
from pydantic import BaseModel

SECRET_KEY = "my_secret_key"
ALGORITHM = "HS256"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Comment(BaseModel):
    content: str

class User(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

security = HTTPBearer()

def load_users():
    with open("users.json") as f:
        return json.load(f)

def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    print(token)
    payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
    return payload["username"]

from fastapi import Request
from uuid import uuid4

class Post(BaseModel):
    content: str
    image: str = ""
    likes: int = 0

def create_token(username):
    payload = {
        "username": username,
        "exp": datetime.utcnow() + timedelta(hours=1)  # Optional expiration
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

@app.post("/posts/{post_id}/comments")
def add_comment(post_id: str, comment: Comment, credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
        username = payload.get("username")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    with open("posts.json") as f:
        posts = json.load(f)

    for post in posts:
        if post["id"] == post_id:
            if "comments" not in post:
                post["comments"] = []
            post["comments"].append({
                "username": username,
                "content": comment.content,
                "timestamp": datetime.utcnow().isoformat()
            })
            break
    else:
        raise HTTPException(status_code=404, detail="Post not found")

    with open("posts.json", "w") as f:
        json.dump(posts, f, indent=2)

    return {"message": "Comment added"}

@app.get("/posts")
def get_posts():
    with open("posts.json") as f:
        posts = json.load(f)
    return posts

@app.post("/posts")
def create_post(post: Post, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")  # Use 'username' instead of 'sub'
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    with open("posts.json") as f:
        posts = json.load(f)

    new_post = {
        "id": str(uuid4()),
        "username": username,
        "content": post.content,
        "image": post.image,
        "likes": 0
    }

    posts.insert(0, new_post)

    with open("posts.json", "w") as f:
        json.dump(posts, f, indent=2)

    return new_post


@app.patch("/posts/{post_id}/like")
def like_post(post_id: str, current_user: str = Depends(get_current_user)):
    with open("posts.json", "r") as f:
        posts = json.load(f)

    for post in posts:
        if post["id"] == post_id:
            if "liked_by" not in post:
                post["liked_by"] = []

            if current_user in post["liked_by"]:
                raise HTTPException(status_code=400, detail="Already liked")

            post["likes"] += 1
            post["liked_by"].append(current_user)

            with open("posts.json", "w") as f:
                json.dump(posts, f, indent=2)
            return post

    raise HTTPException(status_code=404, detail="Post not found")

@app.post("/signup")
def signup(user: User):
    with open("users.json") as f:
        users = json.load(f)

    if any(u["username"] == user.username for u in users):
        raise HTTPException(status_code=400, detail="Username already exists.")

    new_user = {"username": user.username, "password": user.password}
    users.append(new_user)

    with open("users.json", "w") as f:
        json.dump(users, f, indent=2)

    # Return token just like login
    token = create_token(user.username)
    return {"token": token}

@app.post("/login")
def login(user: User):
    with open("users.json", "r") as f:
        users = json.load(f)

    for u in users:
        if u["username"] == user.username and u["password"] == user.password:
            token = create_token(user.username)
            return {"token": token}  # ✅ THIS SHOULD BE RETURNED

    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/protected")
def protected_route(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        return { "message": f"Hello, {username}! You are authenticated." }
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

application = app
# To run: uvicorn main:app --reload
