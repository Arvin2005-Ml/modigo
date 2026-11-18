from datetime import datetime, date
from typing import Literal
from urllib.parse import urlsplit
import ipaddress
from pydantic import Field, field_validator, model_validator
from app.core.schemas import Input, Constraints, Dimension, Integer, DIMENSIONS


class Place(Input):
    name: str = Field(min_length=3, max_length=100)
    city: str = Field(min_length=2, max_length=60)
    source_url: str = Field(min_length=10, max_length=1000)
    source_name: str = Field(min_length=2, max_length=160)
    researched_on: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    evidence_scope: Literal['place_and_activity_type_only']

    @field_validator('researched_on')
    @classmethod
    def research_date(cls, value):
        date.fromisoformat(value)
        return value

    @field_validator('city', mode='before')
    @classmethod
    def city_name(cls, value):
        from app.core.schemas import normalize_city
        return normalize_city(value) if isinstance(value, str) else value

    @field_validator('source_url')
    @classmethod
    def public_source(cls, value):
        # These links are rendered for people; the server never fetches them.
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ''
            if (parsed.scheme != 'https' or not host or '.' not in host or parsed.username
                    or parsed.password or parsed.port not in (None, 443)
                    or host.endswith(('.local', '.localhost', '.test', '.internal'))
                    or any(char.isspace() or ord(char) < 32 for char in value)):
                raise ValueError
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError
        except ValueError:
            raise ValueError('public_https_source_required') from None
        return value


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


class DrammaMechanism(Input):
    dimension: Dimension
    intent: str = Field(min_length=15, max_length=240)
    step_indexes: list[Integer] = Field(min_length=1, max_length=5)

    @field_validator('intent')
    @classmethod
    def concrete_intent(cls, value):
        value = value.strip()
        if len(value) < 15:
            raise ValueError('dramma_intent_required')
        return value


class DrammaAlignment(Input):
    version: Literal['dramma_v1']
    mechanisms: list[DrammaMechanism] = Field(min_length=1, max_length=4)


class Content(Input):
    title: str = Field(min_length=5, max_length=60)
    teaser: str = Field(min_length=15, max_length=140)
    first_step: str = Field(min_length=5, max_length=180)
    steps: list[str] = Field(min_length=2, max_length=5)
    lighter_version: str = Field(min_length=10, max_length=240)
    materials_note: str = Field(min_length=1, max_length=240)
    accessibility_note: str = Field(min_length=1, max_length=240)
    conditions_note: str = Field(min_length=1, max_length=240)
    requires_venue_check: bool = Field(default=False, strict=True)
    place: Place | None = None
    primary_dimension: Dimension
    secondary_dimensions: list[Dimension] = Field(max_length=3)
    dramma: DrammaAlignment
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
        if self.place and (not self.requires_venue_check or self.venue == 'home'):
            raise ValueError('place_requires_public_venue_check')
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
        mechanisms = self.dramma.mechanisms
        dimensions = [mechanism.dimension for mechanism in mechanisms]
        if (len(dimensions) != len(set(dimensions))
                or set(dimensions) != {self.primary_dimension, *self.secondary_dimensions}):
            raise ValueError('dramma_dimension_mismatch')
        for mechanism in mechanisms:
            if (len(mechanism.step_indexes) != len(set(mechanism.step_indexes))
                    or any(index < 1 or index > len(self.steps) for index in mechanism.step_indexes)):
                raise ValueError('dramma_step_reference_invalid')
            if mechanism.dimension == 'affiliation' and (
                    'solo' in self.supported_social_modes or 'together' not in self.supported_social_modes):
                # A solo execution cannot promise the shared action this edition
                # labels affiliation. Async interaction needs its own reviewed variant.
                raise ValueError('dramma_affiliation_requires_shared_execution')
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
