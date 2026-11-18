"""Closed HTTP and generated-output contracts for the activity assistant."""
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from app.core.schemas import Input

LINK_OR_CODE = re.compile(r'https?://|www\.|[<>\x60]', re.I)
PERSIAN_LETTER = re.compile(r'[\u0621-\u063a\u0641-\u064a\u067e\u0686\u0698\u06a9\u06af\u06cc]')


def plain_persian(value: str) -> str:
    if LINK_OR_CODE.search(value) or not PERSIAN_LETTER.search(value):
        raise ValueError('plain_persian_required')
    return value


ShortText = Annotated[str, Field(min_length=5, max_length=240), AfterValidator(plain_persian)]
Mode = Literal['demo', 'gapgpt']
AssetKind = Literal['guide', 'image']
AssetStatus = Literal['idle', 'pending', 'ready', 'failed', 'disabled']


class GuideText(Input):
    intro: ShortText
    first_step: ShortText
    steps: list[ShortText] = Field(min_length=2, max_length=5)
    tips: list[ShortText] = Field(max_length=3)
    lighter_version: ShortText


class Guide(Input):
    # Catalog text has its own editorial validation and can contain borrowed words.
    intro: str
    first_step: str
    steps: list[str]
    tips: list[str]
    lighter_version: str
    source: Literal['catalog', 'gapgpt']


class ImageRef(Input):
    url: str
    alt: str
    source: Literal['gapgpt'] = 'gapgpt'


class AssistantState(Input):
    revision_id: str
    mode: Mode
    guide_status: AssetStatus
    guide: Guide
    guide_retry_after_seconds: int | None = None
    image_status: AssetStatus
    image: ImageRef | None = None
    image_retry_after_seconds: int | None = None


class ChatMessage(Input):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=1600)


class ChatInput(Input):
    messages: list[ChatMessage] = Field(min_length=1, max_length=9)

    @model_validator(mode='after')
    def alternating(self):
        if len(self.messages) % 2 == 0:
            raise ValueError('conversation_must_end_with_user')
        for index, message in enumerate(self.messages):
            role = 'assistant' if index % 2 else 'user'
            if message.role != role or (role == 'user' and len(message.content) > 600):
                raise ValueError('invalid_conversation_turn')
        if sum(len(m.content) for m in self.messages) > 6000:
            raise ValueError('conversation_too_long')
        return self


class ChatReply(Input):
    revision_id: str
    source: Mode
    reply: Annotated[str, Field(min_length=5, max_length=1600), AfterValidator(plain_persian)]
