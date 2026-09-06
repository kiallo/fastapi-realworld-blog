from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.api.dependencies.profiles import get_profile_by_username_from_path
from app.db.repositories.profiles import ProfilesRepository
from app.models.domain.profiles import Profile
from app.models.domain.users import User
from app.models.schemas.profiles import ProfileInResponse, ProfileForResponse
from app.resources import strings

router = APIRouter()


def _profile_to_response(profile: Profile) -> ProfileForResponse:
    """Profile 领域对象 → 响应 Schema"""
    return ProfileForResponse(
        username=profile.username,
        bio=profile.bio,
        image=profile.image,
        following=profile.following,
    )


@router.get("/{username}", response_model=ProfileInResponse, name="profiles:get-profile")
async def get_profile(
    profile: Profile = Depends(get_profile_by_username_from_path),
) -> ProfileInResponse:
    """获取用户资料"""
    return ProfileInResponse(profile=_profile_to_response(profile))


@router.post("/{username}/follow", response_model=ProfileInResponse, name="profiles:follow-user")
async def follow_user(
    profile: Profile = Depends(get_profile_by_username_from_path),
    current_user: User = Depends(get_current_user_authorizer()),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
) -> ProfileInResponse:
    """关注用户"""
    if current_user.username == profile.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strings.CANNOT_FOLLOW_YOURSELF,
        )

    if profile.following:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="你已经关注了该用户",
        )

    await profiles_repo.add_user_into_followers(
        target_user=profile,
        requested_user=current_user,
    )

    return ProfileInResponse(
        profile=_profile_to_response(profile.model_copy(update={"following": True}))
    )


@router.delete("/{username}/follow", response_model=ProfileInResponse, name="profiles:unfollow-user")
async def unfollow_user(
    profile: Profile = Depends(get_profile_by_username_from_path),
    current_user: User = Depends(get_current_user_authorizer()),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
) -> ProfileInResponse:
    """取消关注"""
    if current_user.username == profile.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消关注自己",
        )

    if not profile.following:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="你还没有关注该用户",
        )

    await profiles_repo.remove_user_from_followers(
        target_user=profile,
        requested_user=current_user,
    )

    return ProfileInResponse(
        profile=_profile_to_response(profile.model_copy(update={"following": False}))
    )
