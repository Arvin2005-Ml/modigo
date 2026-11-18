from datetime import date, datetime
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, field_validator, model_validator
from app.core.schemas import Input, Dimension, Integer, normalize_city
from app.core.outing import OUTING_DESTINATIONS, OUTING_ONE_WAY_LIMIT


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


class Place(Input):
    name: str = Field(min_length=2, max_length=160)
    city: str = Field(min_length=2, max_length=100)
    source_url: str = Field(max_length=500)
    source_name: str = Field(min_length=2, max_length=160)
    researched_on: str
    evidence_scope: Literal['place_and_activity_type_only']

    @field_validator('city', mode='before')
    @classmethod
    def clean_city(cls, value):
        return normalize_city(value) if isinstance(value, str) else value

    @field_validator('source_url', mode='before')
    @classmethod
    def public_https(cls, value):
        if not isinstance(value, str) or not value or '\\' in value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('invalid_source_url')
        parts = urlsplit(value)
        host = (parts.hostname or '').lower().rstrip('.')
        if (parts.scheme != 'https' or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443) or not host or parts.netloc.endswith(':')):
            raise ValueError('invalid_source_url')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            labels = host.encode('idna').decode('ascii').split('.')
            if (len(labels) < 2 or not labels[-1][0:1].isalpha()
                    or labels[-1] in {'localhost', 'local', 'internal', 'test', 'invalid', 'example', 'onion', 'lan'}
                    or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)):
                raise ValueError('invalid_source_url')
        else:
            if not address.is_global or address.is_multicast:
                raise ValueError('invalid_source_url')
        return value

    @field_validator('researched_on')
    @classmethod
    def research_date(cls, value):
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            raise ValueError('invalid_research_date')
        date.fromisoformat(value)
        return value


class Mechanism(Input):
    dimension: Dimension
    intent: str = Field(min_length=15, max_length=240)
    step_indexes: list[Integer] = Field(min_length=1, max_length=5)

    @field_validator('intent')
    @classmethod
    def persian(cls, value):
        if not re.search(r'[\u0621-\u063a\u0641-\u064a\u067e\u0686\u0698\u06a9\u06af\u06cc]', value):
            raise ValueError('dramma_persian_intent_required')
        return value


class Dramma(Input):
    version: Literal['dramma_v1']
    mechanisms: list[Mechanism] = Field(min_length=1, max_length=4)


class OutingDay(Input):
    morning: str = Field(min_length=10, max_length=200)
    afternoon: str = Field(min_length=10, max_length=200)
    active_minutes: Integer = Field(ge=60, le=600)
    setup_minutes: Integer = Field(ge=0, le=180)
    travel_minutes: Integer = Field(ge=0, le=390)


class Outing(Input):
    days: Integer = Field(ge=1, le=2)
    origin_city: str
    country_code: Literal['IR']
    one_way_travel_minutes: Integer = Field(ge=0, le=180)
    overnight_city: str | None = None
    itinerary: list[OutingDay] = Field(min_length=1, max_length=2)


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
    place: Place | None = None
    outing: Outing | None = Field(default=None, exclude_if=lambda value: value is None)
    requires_venue_check: bool = Field(default=False, strict=True)
    dramma: Dramma

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
        total = self.active_minutes + self.setup_minutes + self.travel_minutes
        if self.outing is None:
            if not 5 <= total <= 480:
                raise ValueError('invalid_total_time')
        else:
            outing = self.outing
            nearby = OUTING_DESTINATIONS.get(outing.origin_city, ())
            if (self.venue != 'outdoor' or not self.place or self.place.city not in nearby
                    or not self.requires_venue_check
                    or len(outing.itinerary) != outing.days
                    or not (480 < total <= 720 if outing.days == 1 else 720 < total <= 1440)
                    or not (outing.overnight_city is None if outing.days == 1 else outing.overnight_city in nearby)
                    or outing.one_way_travel_minutes > OUTING_ONE_WAY_LIMIT[outing.days]
                    or self.travel_minutes < 2 * outing.one_way_travel_minutes):
                raise ValueError('invalid_outing')
            for key in ('active_minutes', 'setup_minutes', 'travel_minutes'):
                if sum(getattr(day, key) for day in outing.itinerary) != getattr(self, key):
                    raise ValueError('outing_time_mismatch')
            if any(not 360 <= day.active_minutes + day.setup_minutes + day.travel_minutes <= 720
                   or day.travel_minutes < outing.one_way_travel_minutes for day in outing.itinerary):
                raise ValueError('invalid_outing_day_time')
        modes = set(self.supported_social_modes)
        if (len(modes) != len(self.supported_social_modes) or self.min_people > self.max_people
                or ('solo' in modes and self.min_people != 1)
                or (modes == {'solo'} and self.max_people != 1)
                or (modes == {'together'} and self.min_people < 2)
                or ('together' in modes and self.max_people < 2)):
            raise ValueError('invalid_people')
        if self.primary_dimension in self.secondary_dimensions or len(set(self.secondary_dimensions)) != len(self.secondary_dimensions):
            raise ValueError('invalid_secondary_dimensions')
        if ((self.venue == 'home' and (self.place or self.requires_venue_check))
                or (self.place is not None and not self.requires_venue_check)):
            raise ValueError('invalid_venue_attributes')
        dimensions = [m.dimension for m in self.dramma.mechanisms]
        if len(set(dimensions)) != len(dimensions) or set(dimensions) != {self.primary_dimension, *self.secondary_dimensions}:
            raise ValueError('dramma_dimensions_mismatch')
        if 'affiliation' in dimensions and modes != {'together'}:
            raise ValueError('dramma_affiliation_requires_together')
        for mechanism in self.dramma.mechanisms:
            indexes = mechanism.step_indexes
            if len(set(indexes)) != len(indexes) or any(not 1 <= i <= len(self.steps) for i in indexes):
                raise ValueError('dramma_step_index_invalid')
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
