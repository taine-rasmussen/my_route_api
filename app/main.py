from fastapi import FastAPI, HTTPException, Depends, Body, Security
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from . import models, schemas, crud
from .database import engine, Base, get_db
from dotenv import load_dotenv
import os
from datetime import timedelta, datetime 
from jose import jwt
from .schemas import UserResponse
from jose.exceptions import JWTError


app = FastAPI()

Base.metadata.create_all(bind=engine)

ALGORITHM = os.getenv("ALGORITHM")
SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_MINUTES = os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_MINUTES = os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")  
        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return {"email": username, "id": user_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")  
        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return {"email": username, "id": user_id}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")



# Routes

@app.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login/")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = crud.authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token_expires = timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data={"sub": db_user.email, "id": db_user.id},
        expires_delta=access_token_expires
    )
    
    refresh_token_expires = timedelta(minutes=int(REFRESH_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token(
        data={"sub": db_user.email, "id": db_user.id},
        expires_delta=refresh_token_expires
    )
    
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@app.post("/refresh-token/")
def refresh_token(refresh_token: str = Body(...), db: Session = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token is required.")

    try:
        # Verify the refresh token
        token_data = verify_refresh_token(refresh_token)

        # Issue new tokens
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={"sub": token_data["email"], "id": token_data["id"]},
            expires_delta=access_token_expires,
        )

        # Rotate the refresh token
        new_refresh_token = create_refresh_token(
            data={"sub": token_data["email"], "id": token_data["id"]},
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
        }

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

@app.get("/protected-route/")
def protected_route(token: str = Depends(verify_access_token)):
    return {"message": f"Hello, {token}"}

@app.get("/get_user/", response_model=UserResponse)
def get_user(id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/update_user/", response_model=UserResponse)
def update_user(
    user_id: int = Body(...),
    updates: dict = Body(...),
    db: Session = Depends(get_db),
):
    updated_user = crud.update_user(db, user_id=user_id, updates=updates)
    return updated_user

@app.post("/change_password/", response_model=dict)
def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    token: dict = Security(verify_access_token),
    db: Session = Depends(get_db)
):
    # Extract user ID from the token
    user_id = token.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Fetch the user from the database
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if the current password is correct
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=400, 
            detail="Invalid current password", 
            headers={"X-Error": "Current password is incorrect"}
        )

    # Prevent users from setting the same password
    if verify_password(new_password, user.password_hash):
        raise HTTPException(
            status_code=400, 
            detail="New password cannot be the same as the current password", 
            headers={"X-Error": "New password is the same as the current password"}
        )

    crud.change_password(db, user, current_password, new_password)

    return {"message": "Password updated successfully"}


