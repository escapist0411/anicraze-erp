from uuid import UUID, uuid4


def new_uuid() -> UUID:
    return uuid4()


def uuid_to_str(value: UUID) -> str:
    return str(value)
