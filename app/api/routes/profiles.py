from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies.database import get_repository
from app.api.dependencies.authentication import get_current_user_authorizer
from app.db.repositories.profiles import ProfilesRepository
from app.db.queries.queries import queries
from app.models.domain.users import UserInDB
from app.models.schemas.profiles import ProfileForResponse, ProfileInResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/{username}", response_model=ProfileInResponse)
async def get_profile(
    username: str,
    current_user: UserInDB = Depends(get_current_user_authorizer(required=False)),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
):
    """获取用户资料"""
    current_user_id = current_user.id if current_user else None
    profile = await profiles_repo.get_profile_by_username(
        username=username, current_user_id=current_user_id,
    )
    return ProfileInResponse(
        profile=ProfileForResponse(
            username=profile.username,
            bio=profile.bio,
            image=profile.image,
            following=profile.following,
        )
    )


@router.post("/{username}/follow", response_model=ProfileInResponse)
async def follow_user(
    username: str,
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
):
    """关注用户"""
    profile = await profiles_repo.get_profile_by_username(
        username=username, current_user_id=current_user.id,
    )

    if profile.username == current_user.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能关注自己",
        )

    from app.db.repositories.users import UsersRepository
    users_repo = UsersRepository(profiles_repo.connection)
    target = await users_repo.get_user_by_username(username=username)

    await queries.follow_user( # type: ignore
        profiles_repo.connection,
        follower_id=current_user.id,
        following_id=target.id,
    )

    profile.following = True
    return ProfileInResponse(
        profile=ProfileForResponse(
            username=profile.username,
            bio=profile.bio,
            image=profile.image,
            following=True,
        )
    )


@router.delete("/{username}/follow", response_model=ProfileInResponse)
async def unfollow_user(
    username: str,
    current_user: UserInDB = Depends(get_current_user_authorizer()),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
):
    """取消关注"""
    from app.db.repositories.users import UsersRepository
    users_repo = UsersRepository(profiles_repo.connection)
    target = await users_repo.get_user_by_username(username=username)

    await queries.unfollow_user( # type: ignore
        profiles_repo.connection,
        follower_id=current_user.id,
        following_id=target.id,
    )

    profile = await profiles_repo.get_profile_by_username(
        username=username, current_user_id=current_user.id,
    )
    return ProfileInResponse(
        profile=ProfileForResponse(
            username=profile.username,
            bio=profile.bio,
            image=profile.image,
            following=False,
        )
    )