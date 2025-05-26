from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
from datetime import datetime, timezone
import logging
import traceback

from config import settings
from database.database import get_session
from models import User, Friendship

router = APIRouter()
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="تعذر التحقق من التوكن",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (await db.execute(select(User).filter_by(email=email))).scalars().first()
    if user is None:
        raise credentials_exception
    return user


@router.post('/send_request')
async def send_friend_request(
    request: Request,
    friend_username: str = Form(...),  # ← هذا التعديل المهم
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    try:
        # التحقق من وجود المستخدم
        friend = await db.execute(
            select(User).where(User.username == friend_username)
        )
        friend = friend.scalar_one_or_none()
        
        if not friend:
            raise HTTPException(status_code=404, detail="User not found")
            
        if friend.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
            
        # التحقق من عدم وجود طلب صداقة مسبق
        existing_request = await db.execute(
            select(Friendship).where(
                and_(
                    or_(
                        and_(Friendship.user_id == current_user.id, Friendship.friend_id == friend.id),
                        and_(Friendship.user_id == friend.id, Friendship.friend_id == current_user.id)
                    ),
                    Friendship.status.in_(['pending', 'accepted'])
                )
            )
        )
        
        if existing_request.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Friend request already exists")
            
            # إنشاء طلب صداقة جديد
        now = datetime.utcnow()  # بدون timezone
        new_friendship = Friendship(
            user_id=current_user.id,
            friend_id=friend.id,
            status='pending',
            created_at=now,
            updated_at=now
            )
        
        db.add(new_friendship)
        await db.commit()
        
        return {"message": "Friend request sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        
        await db.rollback()
        print("ERROR:", e)
        traceback.print_exc()  # ← هذا السطر سيطبع traceback في الطرفية
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/accept_request/{request_id}')
async def accept_friend_request(request_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    friendship = (await db.execute(
        select(Friendship).filter_by(id=request_id, friend_id=current_user.id, status='pending'))
    ).scalars().first()

    if not friendship:
        raise HTTPException(status_code=404, detail="طلب الصداقة غير موجود أو تم معالجته بالفعل")

    friendship.status = 'accepted'
    await db.commit()
    return {"message": "تم قبول طلب الصداقة بنجاح"}


@router.post('/decline_request/{request_id}')
async def decline_friend_request(request_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    friendship = (await db.execute(
        select(Friendship).filter_by(id=request_id, friend_id=current_user.id, status='pending'))
    ).scalars().first()

    if not friendship:
        raise HTTPException(status_code=404, detail="طلب الصداقة غير موجود أو تم معالجته بالفعل")

    friendship.status = 'declined'
    await db.commit()
    return {"message": "تم رفض طلب الصداقة"}


@router.post('/cancel_request/{request_id}')
async def cancel_friend_request(request_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    friendship = (await db.execute(
        select(Friendship).filter_by(id=request_id, user_id=current_user.id, status='pending'))
    ).scalars().first()

    if not friendship:
        raise HTTPException(status_code=404, detail="طلب الصداقة غير موجود أو تم معالجته بالفعل")

    await db.delete(friendship)
    await db.commit()
    return {"message": "تم إلغاء طلب الصداقة"}


@router.post('/remove_friend/{friend_id}')
async def remove_friend(friend_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    friendship = (await db.execute(
        select(Friendship).where(
            (((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend_id)) |
             ((Friendship.user_id == friend_id) & (Friendship.friend_id == current_user.id))) &
            (Friendship.status == 'accepted'))
    )).scalars().first()

    if not friendship:
        raise HTTPException(status_code=404, detail="علاقة الصداقة غير موجودة")

    await db.delete(friendship)
    await db.commit()
    return {"message": "تم إزالة الصديق بنجاح"}


@router.get('/my_friends')
async def get_friends(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    sent = (await db.execute(select(Friendship).filter_by(user_id=current_user.id, status='accepted'))).scalars().all()
    received = (await db.execute(select(Friendship).filter_by(friend_id=current_user.id, status='accepted'))).scalars().all()

    friends = []
    for f in sent:
        friend = await db.get(User, f.friend_id)
        if friend:
            friends.append({"id": friend.id, "username": friend.username, "email": friend.email})

    for f in received:
        friend = await db.get(User, f.user_id)
        if friend:
            friends.append({"id": friend.id, "username": friend.username, "email": friend.email})

    return {"friends": friends}


@router.get('/pending_requests')
async def get_pending_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    pending = (await db.execute(select(Friendship).filter_by(friend_id=current_user.id, status='pending'))).scalars().all()

    requests = []
    for f in pending:
        sender = await db.get(User, f.user_id)
        if sender:
            requests.append({
                "request_id": f.id,
                "user_id": sender.id,
                "username": sender.username,
                "email": sender.email,
                "created_at": f.created_at.isoformat() if f.created_at else None
            })

    return {"pending_requests": requests}


@router.get('/sent_requests')
async def get_sent_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    sent = (await db.execute(select(Friendship).filter_by(user_id=current_user.id, status='pending'))).scalars().all()

    requests = []
    for f in sent:
        receiver = await db.get(User, f.friend_id)
        if receiver:
            requests.append({
                "request_id": f.id,
                "user_id": receiver.id,
                "username": receiver.username,
                "email": receiver.email,
                "created_at": f.created_at.isoformat() if f.created_at else None
            })

    return {"sent_requests": requests}


@router.get("/users/search")
async def search_users(
    term: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    if not term or term.strip() == "":
        raise HTTPException(status_code=400, detail="يرجى إدخال كلمة للبحث")

    query = select(User).where(
        or_(
            User.username.ilike(f"%{term}%"),
            User.email.ilike(f"%{term}%")
        )
    ).limit(limit)

    users = (await db.execute(query)).scalars().all()

    results = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email
        } for user in users
    ]

    return results