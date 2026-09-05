from app.models.auth import User
from app.repositories.users import UserRepository
from app.schemas.auth import ProfileUpdateRequest, UserRead


class ProfileService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    @staticmethod
    def serialize(user: User) -> UserRead:
        roles = sorted({role.code or str(role.name) for role in user.roles})
        permissions = {permission.code for role in user.roles for permission in role.permissions} | {permission.code for permission in user.direct_permissions}
        if "OWNER" in roles:
            permissions.add("*")
        return UserRead(
            id=user.id,
            name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            status=user.status,
            roles=roles,
            permissions=sorted(permissions),
            assigned_store_id=user.assigned_store_id,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            preferred_language=user.preferred_language,
            timezone=user.timezone,
        )

    async def update(self, user: User, payload: ProfileUpdateRequest) -> UserRead:
        values = payload.model_dump(exclude_unset=True)
        if "name" in values:
            values["full_name"] = values.pop("name")
        updated = await self.users.update_profile(user, values)
        return self.serialize(updated)
