"""Closed, normalized request contracts shared by HTTP and application services."""
import re
import unicodedata
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIMENSIONS = ('detachment', 'relaxation', 'autonomy', 'mastery', 'meaning', 'affiliation')
TAGS = set('observation sensory imagination play nature walking music listening reading writing drawing photography craft puzzles language rhythm movement dance rest reflection storytelling memory gratitude kindness community culture family friendship conversation cooperation food gardening discovery choice creativity mindfulness science games design humor outdoors indoors no_screen digital'.split())
ITEMS = set('paper pen colored_pencils scissors glue tape cardboard yarn needle fabric clay phone internet headphones speaker book camera board_game playing_cards dice ball bicycle yoga_mat plant pot soil kitchen food_ingredients towel blanket cushion musical_instrument computer puzzle binoculars'.split())
Mobility = Literal['seated', 'light', 'active']
Goal = Literal['unwind', 'switch_off', 'learn', 'connect', 'meaning', 'choose', 'any']
Dimension = Literal['detachment', 'relaxation', 'autonomy', 'mastery', 'meaning', 'affiliation']
Integer = Annotated[int, Field(strict=True)]


def normalize_city(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', value).translate(str.maketrans('كيى\u200c', 'کیی ')).split())


def city_key(value: str) -> str:
    return normalize_city(value).replace(' ', '').replace('\u200c', '').casefold()


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)

    @field_validator('*', mode='before')
    @classmethod
    def normalize_text(cls, value, info):
        # Passwords are opaque: never trim, normalize or silently modify them.
        if isinstance(value, str) and info.field_name not in ('password', 'new_password', 'current_password'):
            return unicodedata.normalize('NFC', value)
        return value


class Credentials(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('invalid_email')
        return value

    @field_validator('password', mode='before')
    @classmethod
    def opaque_password(cls, value):
        # Override global strip behavior for this field using an opaque str subtype is unnecessary:
        # disable str stripping in Credentials instead.
        return value

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False, validate_default=True)


class Signup(Credentials):
    display_name: str = Field(default='', max_length=60)
    adult_confirmed: Literal[True]

    @field_validator('adult_confirmed', mode='before')
    @classmethod
    def explicit_adult_consent(cls, value):
        if value is not True:
            raise ValueError('adult_confirmation_required')
        return value


class Token(Input):
    token: str = Field(min_length=32, max_length=128)


class Empty(Input):
    pass


class Budget(Input):
    mode: Literal['free', 'cap', 'flexible']
    cap_toman: Integer | None = None

    @model_validator(mode='after')
    def consistency(self):
        if self.mode == 'cap' and (self.cap_toman is None or not 1 <= self.cap_toman <= 100_000_000):
            raise ValueError('invalid_cap')
        self.cap_toman = 0 if self.mode == 'free' else self.cap_toman if self.mode == 'cap' else None
        return self


class Constraints(Input):
    owned_items: list[str] = Field(default_factory=list, max_length=50)
    liked_tags: list[str] = Field(default_factory=list, max_length=50)
    blocked_tags: list[str] = Field(default_factory=list, max_length=50)
    max_mobility: Mobility = 'active'
    requires_step_free: bool = Field(default=False, strict=True)
    requires_quiet: bool = Field(default=False, strict=True)
    allow_async_contact: bool = Field(default=False, strict=True)

    @field_validator('owned_items', 'liked_tags', 'blocked_tags')
    @classmethod
    def vocabulary(cls, value, info):
        if not set(value) <= (ITEMS if info.field_name == 'owned_items' else TAGS):
            raise ValueError('unknown_vocabulary')
        return sorted(set(value))


class Preferences(Constraints):
    default_goal: Goal = 'any'
    show_gamification: bool = Field(default=True, strict=True)
    analytics_opt_in: bool = Field(default=False, strict=True)
    analytics_policy_version: str | None = None

    @model_validator(mode='after')
    def consent(self):
        if self.analytics_opt_in:
            raise ValueError('analytics_not_enabled_in_this_slice')
        self.analytics_policy_version = None
        return self


class PreferencesUpdate(Input):
    version: Integer = Field(ge=1)
    preferences: Preferences


class Context(Constraints):
    available_minutes: Integer = Field(ge=5, le=480)
    energy: Literal['low', 'medium', 'high', 'unknown']
    social_mode: Literal['solo', 'together', 'either']
    party_size: Integer = Field(ge=1, le=12)
    venue: Literal['home', 'away_from_home', 'any', 'outdoor', 'indoor_public']
    budget: Budget
    city: str | None = Field(default=None, max_length=100, strict=True)
    allow_venue_planning: bool = Field(default=False, strict=True)
    activity_intent: Goal | None = None
    mood: Literal['tired', 'restless', 'bored', 'low', 'okay', 'skip'] = 'skip'
    goal: Goal = 'any'
    need_now: Goal = 'any'
    desired_outcome: Goal = 'any'
    weather: Literal['fair', 'adverse', 'unknown'] = 'unknown'
    daylight: Literal['day', 'night', 'unknown'] = 'unknown'

    @field_validator('city', mode='before')
    @classmethod
    def clean_city(cls, value):
        return normalize_city(value) or None if isinstance(value, str) else value

    @field_validator('available_minutes', 'party_size', mode='before')
    @classmethod
    def integer_digits(cls, value):
        if isinstance(value, str) and value.isdecimal() and len(value) <= 9:
            return int(value)
        return value

    @model_validator(mode='after')
    def social(self):
        if self.social_mode == 'solo' and self.party_size != 1:
            raise ValueError('solo_requires_one_person')
        if self.social_mode == 'together' and self.party_size < 2:
            raise ValueError('group_requires_companion')
        return self


class SlateInput(Input):
    check_in_id: str = Field(min_length=36, max_length=36)


class ReplaceInput(Input):
    expected_version: Integer = Field(ge=1)


class NavigateInput(ReplaceInput):
    direction: Literal['previous', 'next']


class StartInput(Input):
    recommendation_session_id: str = Field(min_length=36, max_length=36)
    slot_id: str = Field(min_length=36, max_length=36)
    revision_id: str = Field(min_length=36, max_length=36)


class Feedback(Input):
    rating: Literal['liked', 'neutral', 'disliked']
    reason: Literal['time', 'cost', 'interest', 'access', 'too_hard', 'repeated'] | None = None


def merge_constraints(context: dict, preferences: dict, supplied: set | None = None):
    result = dict(context)
    supplied = supplied if supplied is not None else set(context)
    for key in ('owned_items', 'liked_tags', 'allow_async_contact'):
        if key not in supplied:
            result[key] = preferences[key]
    if 'goal' not in supplied:
        result['goal'] = preferences['default_goal']
    result['blocked_tags'] = sorted(set(context['blocked_tags']) | set(preferences['blocked_tags']))
    for key in ('requires_step_free', 'requires_quiet'):
        result[key] = context[key] or preferences[key]
    order = {'seated': 0, 'light': 1, 'active': 2}
    result['max_mobility'] = min((context['max_mobility'], preferences['max_mobility']), key=order.get)
    return result


class AccountEmail(Input):
    email: str = Field(min_length=3, max_length=254)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        return Credentials.valid_email(value)


class ResetPassword(Token):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordConfirm(Input):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    password: str = Field(min_length=12, max_length=128)


class ChangePassword(Input):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
