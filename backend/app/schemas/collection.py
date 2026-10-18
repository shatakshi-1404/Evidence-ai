import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CollectionName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class CollectionCreate(BaseModel):
    name: CollectionName
    description: str | None = Field(default=None, max_length=1000)


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
