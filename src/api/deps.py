from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.database import get_db


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


def get_app_settings() -> Settings:
    return get_settings()
