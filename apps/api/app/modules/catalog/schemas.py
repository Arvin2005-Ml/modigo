from datetime import datetime
from typing import Literal
from pydantic import Field, field_validator, model_validator
from app.core.schemas import Input, Constraints, Dimension, Integer, DIMENSIONS


class Cost(Input):
    kind: Literal['free', 'estimated', 'unknown']
    min_toman: Integer | None
    max_toman: Integer | None
    basis: Literal['per_person', 'per_group']
    verified_at: datetime | None
    valid_until: datetime | None
    note: str = Field(min_length=1, max_length=240)

    @model_validator(mode='after')
    def consistency(self):
        if self.kind == 'free':
            if self.min_toman != 0 or self.max_toman != 0 or self.verified_at or self.valid_until:
                raise ValueError('free_cost_mismatch')
        elif self.kind == 'unknown':
            if any(v is not None for v in (self.min_toman, self.max_toman, self.verified_at, self.valid_until)):
                raise ValueError('unknown_cost_mismatch')
        else:
            if (self.min_toman is None or self.max_toman is None or not 0 <= self.min_toman <= self.max_toman
                    or not self.verified_at or not self.valid_until
                    or self.verified_at.tzinfo is None or self.valid_until.tzinfo is None
                    or not 0 < (self.valid_until - self.verified_at).total_seconds() <= 30 * 86400):
                raise ValueError('invalid_estimate')
        return self


class Content(Input):
    title: str = Field(min_length=5, max_length=60)
    teaser: str = Field(min_length=15, max_length=140)
    first_step: str = Field(min_length=5, max_length=180)
    steps: list[str] = Field(min_length=2, max_length=5)
    lighter_version: str = Field(min_length=10, max_length=240)
    materials_note: str = Field(min_length=1, max_length=240)
    accessibility_note: str = Field(min_length=1, max_length=240)
    conditions_note: str = Field(min_length=1, max_length=240)
    primary_dimension: Dimension
    secondary_dimensions: list[Dimension] = Field(max_length=3)
    tags: list[str] = Field(min_length=1, max_length=8)
    active_minutes: Integer = Field(ge=1)
    setup_minutes: Integer = Field(ge=0)
    travel_minutes: Integer = Field(ge=0)
    energy_required: Literal['low', 'medium', 'high']
    mobility_required: Literal['seated', 'light', 'active']
    supported_social_modes: list[Literal['solo', 'together']] = Field(min_length=1, max_length=2)
    min_people: Integer = Field(ge=1, le=12)
    max_people: Integer = Field(ge=1, le=12)
    venue: Literal['home', 'outdoor', 'indoor_public']
    required_items: list[str] = Field(max_length=50)
    requires_async_contact: bool = Field(strict=True)
    step_free: bool | None = Field(strict=True)
    quiet_compatible: bool | None = Field(strict=True)
    weather_requirement: Literal['any', 'fair']
    daylight_requirement: Literal['any', 'day']
    cost: Cost
    safety_notes: list[str] = Field(max_length=3)

    @field_validator('steps', 'safety_notes')
    @classmethod
    def step_lengths(cls, value):
        if any(not 5 <= len(s.strip()) <= 240 for s in value):
            raise ValueError('invalid_step_length')
        return [s.strip() for s in value]

    @model_validator(mode='after')
    def consistency(self):
        from app.core.schemas import TAGS, ITEMS
        if not set(self.tags) <= TAGS or not set(self.required_items) <= ITEMS:
            raise ValueError('unknown_vocabulary')
        if not 5 <= self.active_minutes + self.setup_minutes + self.travel_minutes <= 480:
            raise ValueError('invalid_total_time')
        modes = set(self.supported_social_modes)
        if (len(modes) != len(self.supported_social_modes) or self.min_people > self.max_people
                or ('solo' in modes and self.min_people != 1)
                or (modes == {'solo'} and self.max_people != 1)
                or (modes == {'together'} and self.min_people < 2)
                or ('together' in modes and self.max_people < 2)):
            raise ValueError('invalid_people')
        if self.primary_dimension in self.secondary_dimensions or len(set(self.secondary_dimensions)) != len(self.secondary_dimensions):
            raise ValueError('invalid_secondary_dimensions')
        if not any('\u0600' <= c <= '\u06ff' for c in self.title):
            raise ValueError('persian_title_required')
        return self


class DraftUpdate(Input):
    expected_draft_version: Integer = Field(ge=1)
    content: Content


class ReviewInput(Input):
    expected_draft_version: Integer = Field(ge=1)


class WithdrawInput(Input):
    reason: str = Field(min_length=5, max_length=240)


class CloneInput(Input):
    source_revision_id: str = Field(min_length=36, max_length=36)


class CookInput(Input):
    target_draft_id: str = Field(min_length=36, max_length=36)
    expected_draft_version: Integer = Field(ge=1)
    prompt_version: Literal['cook_v1'] = 'cook_v1'
    editor_constraints: str = Field(default='', max_length=500)
