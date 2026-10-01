# Copied VERBATIM from the private generator repo (demo/public_schema.py).
# It is the single source of truth for the bundle format: do not edit here,
# change it at the origin and copy it again.
"""The PUBLIC demo bundle's schema: the format the public site serves.

`demo/export_public.py` turns an internal bundle into one of these; the site
copies THIS MODULE VERBATIM and loads the bundle through `load_bundle`, so a
bundle that validates here is a bundle the site can serve. It imports nothing
but pydantic and the standard library.

It is a strict subset of what the generator knows. Nothing in it names a
private module, function, clock pin or internal tool, and none of it has a
field that could carry one: every model forbids unknown fields.

Layout of a bundle directory:

    manifest.json                     Manifest
    tree.json                         Tree
    people/<A>/overview.json          Overview
    people/<A>/qa.json                QA   (scope "person")
    goals/<A1>/interview.json         Interview
    goals/<A1>/plan.json              Plan
    goals/<A1>/qa.json                QA   (scope "goal")
    goals/<A1>/today.json             Today (the iPhone app's Today screen for
                                      each day of the plan week; optional)
    goals/<A1>/briefs.json            Briefs (the app's morning brief and
                                      evening review for the pinned day; optional)

The rule the demo exists to show is encoded in the shape: an `Answer` carries
the text a model narrated AND the `facts` Python computed, side by side. No
number in a bundle originates in a model.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import (AfterValidator, BaseModel, ConfigDict, Field,
                      ValidationError, field_validator, model_validator)

# 2 = the public format (1 was the generator's internal one).
SCHEMA_VERSION = 2

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERSON_ID = re.compile(r"^[A-Z]$")
_GOAL_ID = re.compile(r"^[A-Z][0-9]$")
_PUBLIC_SHA = re.compile(r"^[0-9a-f]{7,40}$")


class _Model(BaseModel):
    """Strict: an unknown field is a bug in the exporter, not data to carry."""
    model_config = ConfigDict(extra="forbid")


def _check_day(value: str) -> str:
    if not _ISO_DAY.match(value):
        raise ValueError(f"not an ISO day: {value!r}")
    return value


def _check_optional_day(value: str | None) -> str | None:
    return None if value is None else _check_day(value)


# A calendar day as YYYY-MM-DD text (dates are strings on the wire).
Day = Annotated[str, AfterValidator(_check_day)]
OptDay = Annotated[str | None, AfterValidator(_check_optional_day)]


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
class LeafRecord(_Model):
    """When one leaf (a person or a goal) was generated, and how many model
    calls it took."""
    leaf_id: str
    kind: Literal["person", "goal"]
    generated_at: str
    model_calls: int = Field(ge=0)


class ModelSettings(_Model):
    """The models that wrote the wording. Names only."""
    backend: str
    model: str
    plan_model: str
    providers: str
    plan_providers: str
    reasoning: str


class Manifest(_Model):
    schema_version: int = SCHEMA_VERSION
    generated_at: str
    end_date: Day
    dry_run: bool
    # The engine repository is public; this is its revision, hex only.
    engine_sha: str
    model: ModelSettings
    leaves: dict[str, LeafRecord]

    @field_validator("engine_sha")
    @classmethod
    def _sha(cls, value: str) -> str:
        if not _PUBLIC_SHA.match(value):
            raise ValueError(f"engine_sha must be a bare hex revision: {value!r}")
        return value


# --------------------------------------------------------------------------- #
# tree
# --------------------------------------------------------------------------- #
class GoalNode(_Model):
    id: str
    label: str
    blurb: str

    @field_validator("id")
    @classmethod
    def _goal_id(cls, value: str) -> str:
        if not _GOAL_ID.match(value):
            raise ValueError(f"goal id must look like 'A1': {value!r}")
        return value


class PersonNode(_Model):
    id: str
    label: str
    blurb: str
    goals: list[GoalNode]

    @field_validator("id")
    @classmethod
    def _person_id(cls, value: str) -> str:
        if not _PERSON_ID.match(value):
            raise ValueError(f"person id must look like 'A': {value!r}")
        return value


class Tree(_Model):
    end_date: Day
    people: list[PersonNode]


# --------------------------------------------------------------------------- #
# person overview (no model)
# --------------------------------------------------------------------------- #
class SeriesPoint(_Model):
    """One Monday-to-Sunday week (the first and last may be partial)."""
    start: Day
    end: Day
    value: float | None
    n_days: int = Field(ge=0)
    partial: bool


class Headline(_Model):
    """The last complete week's value, picked and formatted by Python. The
    site shows `display` and `unit` as they are."""
    week_start: Day
    week_end: Day
    value: float
    unit: str
    display: str
    n_days: int = Field(ge=0)


class Series(_Model):
    metric: str
    label: str
    unit: str
    aggregation: Literal["weekly_total", "weekly_mean"]
    points: list[SeriesPoint]
    # One sentence, composed in Python from `points`.
    summary: str
    # None only when the series has no complete week with a value.
    headline: Headline | None = None


class Overview(_Model):
    person_id: str
    end_date: Day
    days: int = Field(gt=0)
    series: list[Series]


# --------------------------------------------------------------------------- #
# answers
# --------------------------------------------------------------------------- #
class Fact(_Model):
    """One number Python computed and put in front of the model. `source` is a
    plain-language name for what produced it ("metric summary")."""
    label: str
    value: str
    unit: str | None = None
    source: str


class Figure(_Model):
    """A figure the answer states, joined to what computed it."""
    display: str
    unit: str | None = None
    label: str
    source: str | None = None


class Window(_Model):
    start: Day
    end: Day


class Source(_Model):
    """One kind of computation that supplied a figure the answer states."""
    title: str
    blurb: str | None = None
    windows: list[Window] = Field(default_factory=list)


class Verification(_Model):
    ok: bool
    reason: str | None = None
    cause: str | None = None
    figures_verified: int = Field(default=0, ge=0)
    figures_total: int = Field(default=0, ge=0)
    retry: bool = False


class Answer(_Model):
    question: str
    text: str
    # "fallback" = Python's own template text, shown because the model's draft
    # failed verification.
    mode: Literal["narration", "fallback"]
    # True for the questions about the goal's plan (the ones every goal
    # shares), False for every other question.
    plan_question: bool
    # True when at least one fact in the panel came from reading the plan.
    has_plan_facts: bool
    figures: list[Figure]
    facts: list[Fact]
    sources: list[Source] = Field(default_factory=list)
    verification: Verification


class QA(_Model):
    scope: Literal["person", "goal"]
    id: str
    answers: list[Answer]


# --------------------------------------------------------------------------- #
# interview
# --------------------------------------------------------------------------- #
def _numbers_without_display(data: Any, display: Any, where: str = "") -> list[str]:
    """Paths of every number in `data` that has no string at the same path in
    `display` (the mirror a card carries beside its raw values)."""
    missing: list[str] = []
    if isinstance(data, dict):
        for key, child in data.items():
            missing += _numbers_without_display(
                child, display.get(key) if isinstance(display, dict) else None,
                f"{where}.{key}" if where else str(key))
    elif isinstance(data, list):
        for index, child in enumerate(data):
            shown = display[index] if isinstance(display, list) and index < len(display) else None
            missing += _numbers_without_display(child, shown, f"{where}[{index}]")
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        if not (isinstance(display, str) and display.strip()):
            missing.append(where)
    return missing


def _display_leaves_are_strings(display: Any) -> bool:
    if isinstance(display, dict):
        return all(_display_leaves_are_strings(child) for child in display.values())
    if isinstance(display, list):
        return all(_display_leaves_are_strings(child) for child in display)
    return display is None or isinstance(display, str)


class Card(_Model):
    """A deterministic, Python-rendered card that accompanied a coach turn.

    `display` (#566) mirrors `data`: the same keys and nesting, with the
    string a reader sees wherever `data` holds a number ("1.161" -> "± 1 h
    10 m"). Python decided it (`demo/card_display.py`); a consumer prints it
    as is and never rounds, formats or pluralises the raw value.
    """
    kind: Literal["history", "availability", "constraints", "structure"]
    data: dict[str, Any]
    display: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _display_covers_every_number(self) -> "Card":
        if self.display is not None and not _display_leaves_are_strings(self.display):
            raise ValueError("a card's display holds strings (or null) only")
        if self.kind in ("history", "structure"):
            missing = _numbers_without_display(self.data, self.display)
            if missing:
                raise ValueError("a %s card's numbers have no display string: %s"
                                 % (self.kind, ", ".join(missing)))
        return self


class Turn(_Model):
    role: Literal["coach", "user"]
    text: str
    card: Card | None = None


class Interview(_Model):
    goal_id: str
    transcript: list[Turn]


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #
class OutlineWeek(BaseModel):
    """One outline week as the plan model wrote it (its wording, Python-gated)."""
    model_config = ConfigDict(extra="allow")

    week: int
    intent: str | None = None
    jog_minutes_target: float | None = None
    key_session: str | None = None


class SessionLine(_Model):
    text: str
    detail: str | None = None


class DaySession(_Model):
    modality: str | None = None
    label: str | None = None
    title: str | None = None
    impact: str | None = None
    lines: list[SessionLine] = Field(default_factory=list)


class WeekDay(_Model):
    date: Day
    weekday: str
    title: str
    is_rest_day: bool
    sessions: list[DaySession] = Field(default_factory=list)


class WeekTable(_Model):
    week_start: Day
    window_start: OptDay = None
    window_end: OptDay = None
    title: str | None = None
    days: list[WeekDay]
    planned_sessions: int = Field(default=0, ge=0)


class LongPlanWeek(_Model):
    """One week of the long plan, as the plan view (`GET /v1/plan/long`) gives it.

    Everything here is Python's except `intent`, the one sentence the plan
    model wrote (stored, gated, and checked to state no training amount). The
    index, dates, phase and session labels and both flags are Python's; a
    withheld week (a stored row that failed re-validation) carries no text.
    """
    index: int = Field(ge=1)
    start: Day
    end: Day
    withheld: bool = False
    phase_label: str | None = None
    intent: str | None = None
    key_session_label: str | None = None
    is_current: bool = False
    is_past: bool = False


class LongPlan(_Model):
    """The long-horizon plan as of the demo's pinned day (weeks 2+ carry no
    training amounts: words, Python's week labels and dates only)."""
    as_of: Day
    weeks_total: int = Field(ge=1)
    current_index: int | None = None
    # Python's own label for the current week ("Week 1 of 12"), None outside it.
    position_label: str | None = None
    weeks: list[LongPlanWeek]


class Plan(_Model):
    goal_id: str
    status: str
    accepted: bool
    explanation: str | None = None
    attempts: int = Field(ge=0)
    outline: list[OutlineWeek]
    warnings: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    week: WeekTable | None = None
    # #554: the long plan, absent for a plan built without one.
    long_plan: LongPlan | None = None


# --------------------------------------------------------------------------- #
# today (the iPhone app's Today screen, #566)
# --------------------------------------------------------------------------- #
# What the app shows for each day of the plan week, as the engine returned it
# (every `display` string was rendered by Python; the site shows it as is).
# Left out: the grading spec (`session`), the claim vocabulary (`facts`),
# `freshness.metrics`, the plan's `week_file`, a session's `phase` and a
# workout's `workout_key`. `impact` stays: the plan's week table carries the
# same field.
class TodayFigure(_Model):
    value: float
    unit: str
    display: str


class TodayRefusal(_Model):
    """A designed refusal or absence: a reason code, a sentence and an
    optional remedy sentence. The site shows `detail` and `remedy`."""
    status: Literal["empty", "unavailable"]
    reason: str
    detail: str
    remedy: str | None = None


class TodayBullet(_Model):
    text: str
    detail: str | None = None


class TodaySessionLine(_Model):
    text: str
    detail: str | None = None
    kind: str


class TodaySession(_Model):
    modality: str | None = None
    label: str | None = None
    title: str | None = None
    status: str | None = None
    impact: str | None = None
    lines: list[TodaySessionLine] = Field(default_factory=list)


class TodayPlanOk(_Model):
    status: Literal["ok"]
    session_title: str
    is_rest_day: bool
    session_lines: list[TodayBullet] = Field(default_factory=list)
    sessions: list[TodaySession] = Field(default_factory=list)
    anchors: list[TodayBullet] = Field(default_factory=list)


class TodayReadinessComponents(_Model):
    hrv: TodayFigure
    rhr: TodayFigure


class TodayReadinessOk(_Model):
    status: Literal["ok", "partial"]
    score: TodayFigure
    band: str | None = None
    note: str | None = None
    components: TodayReadinessComponents


class TodayWorkout(_Model):
    type: str | None = None
    duration_min: TodayFigure | None = None
    distance_mi: TodayFigure | None = None
    pace_min_per_mi: TodayFigure | None = None
    avg_heart_rate: TodayFigure | None = None


class TodayGradeOk(_Model):
    status: Literal["ok"]
    date: Day
    outcome: str
    credited: list[str] = Field(default_factory=list)
    substituted: list[str] = Field(default_factory=list)
    workouts: list[TodayWorkout] = Field(default_factory=list)


TodayPlanSection = Annotated[Union[TodayPlanOk, TodayRefusal], Field(discriminator="status")]
TodayReadinessSection = Annotated[Union[TodayReadinessOk, TodayRefusal],
                                  Field(discriminator="status")]
TodayYesterdaySection = Annotated[Union[TodayGradeOk, TodayRefusal],
                                  Field(discriminator="status")]


class TodayFreshness(_Model):
    as_of: Day
    data_through: OptDay = None


class TodayDay(_Model):
    date: Day
    is_today: bool
    is_future: bool
    freshness: TodayFreshness
    plan: TodayPlanSection
    readiness: TodayReadinessSection
    yesterday: TodayYesterdaySection


class Today(_Model):
    as_of: Day
    days: list[TodayDay]


# --------------------------------------------------------------------------- #
# briefs (the app's morning brief and evening review, #566)
# --------------------------------------------------------------------------- #
# What the app shows for a brief, as the product wrote and stored it. `label`
# is the app's card label, `written_at` the instant behind its "Written ..."
# line, `text` the whole stored brief (Python's facts block, a blank line, the
# closing paragraph) and `narration` that closing paragraph on its own, which
# is the one part the Today screen shows. `facts` is everything Python
# published for the model to narrate from; the site shows it beside the text.
class BriefEntry(_Model):
    date: Day
    kind: Literal["morning", "evening"]
    # "Morning brief" / "Evening brief", decided in Python.
    label: str
    written_at: str
    text: str
    narration: str | None = None
    # "fallback" = Python's own fixed sentence closes the brief, because the
    # model's paragraph failed verification.
    mode: Literal["narration", "fallback"]
    verification: Verification
    facts: list[Fact]


class Briefs(_Model):
    as_of: Day
    entries: list[BriefEntry]


# --------------------------------------------------------------------------- #
# the bundle as a whole
# --------------------------------------------------------------------------- #
PERSON_FILES: dict[str, type[BaseModel]] = {
    "overview.json": Overview, "qa.json": QA,
}
GOAL_FILES: dict[str, type[BaseModel]] = {
    "interview.json": Interview, "plan.json": Plan, "qa.json": QA,
}
# Present for a goal whose plan was accepted, in a bundle generated after #566.
GOAL_OPTIONAL_FILES: dict[str, type[BaseModel]] = {
    "today.json": Today,
    "briefs.json": Briefs,
}


class BundleError(Exception):
    """One or more files failed to load; `problems` names every one."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


class Bundle(_Model):
    manifest: Manifest
    tree: Tree
    overviews: dict[str, Overview]
    person_qa: dict[str, QA]
    interviews: dict[str, Interview]
    plans: dict[str, Plan]
    goal_qa: dict[str, QA]
    # Only the goals that carry a today.json.
    today: dict[str, Today] = Field(default_factory=dict)
    # Only the goals that carry a briefs.json.
    briefs: dict[str, Briefs] = Field(default_factory=dict)


def expected_files(tree: Tree) -> list[tuple[str, type[BaseModel]]]:
    """Every path a bundle for this tree must contain, with its model."""
    files: list[tuple[str, type[BaseModel]]] = [
        ("manifest.json", Manifest), ("tree.json", Tree)]
    for person in tree.people:
        for name, model in PERSON_FILES.items():
            files.append((f"people/{person.id}/{name}", model))
        for goal in person.goals:
            for name, model in GOAL_FILES.items():
                files.append((f"goals/{goal.id}/{name}", model))
    return files


def _load(path: Path, model: type[BaseModel], problems: list[str], rel: str):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"{rel}: missing")
        return None
    except (OSError, ValueError) as exc:
        problems.append(f"{rel}: unreadable ({type(exc).__name__}: {exc})")
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        problems.append(f"{rel}: schema ({exc.error_count()} error(s); "
                        f"first at {where}: {first['msg']})")
        return None


def load_bundle(root: str | Path) -> Bundle:
    """Load and validate a whole bundle, or raise `BundleError` naming every
    file that is missing or invalid. Cross-file rules: ids in the files match
    the tree, and the manifest records a leaf for every person and goal."""
    root = Path(root)
    problems: list[str] = []
    tree = _load(root / "tree.json", Tree, problems, "tree.json")
    manifest = _load(root / "manifest.json", Manifest, problems, "manifest.json")
    if tree is None:
        raise BundleError(problems)
    loaded: dict[str, Any] = {}
    for rel, model in expected_files(tree)[2:]:
        loaded[rel] = _load(root / rel, model, problems, rel)
    overviews, person_qa, interviews, plans, goal_qa = {}, {}, {}, {}, {}
    optional: dict[str, dict[str, Any]] = {name: {} for name in GOAL_OPTIONAL_FILES}
    for person in tree.people:
        ov = loaded.get(f"people/{person.id}/overview.json")
        qa = loaded.get(f"people/{person.id}/qa.json")
        if ov is not None:
            overviews[person.id] = ov
            if ov.person_id != person.id:
                problems.append(f"people/{person.id}/overview.json: person_id "
                                f"{ov.person_id!r} does not match its folder")
        if qa is not None:
            person_qa[person.id] = qa
            if qa.scope != "person" or qa.id != person.id:
                problems.append(f"people/{person.id}/qa.json: scope/id mismatch")
            if any(answer.plan_question for answer in qa.answers):
                problems.append(f"people/{person.id}/qa.json: a person question "
                                "cannot be a plan question")
        for goal in person.goals:
            base = f"goals/{goal.id}"
            iv, pl, gq = (loaded.get(f"{base}/interview.json"),
                          loaded.get(f"{base}/plan.json"),
                          loaded.get(f"{base}/qa.json"))
            if iv is not None:
                interviews[goal.id] = iv
                if iv.goal_id != goal.id:
                    problems.append(f"{base}/interview.json: goal_id mismatch")
            if pl is not None:
                plans[goal.id] = pl
                if pl.goal_id != goal.id:
                    problems.append(f"{base}/plan.json: goal_id mismatch")
            if gq is not None:
                goal_qa[goal.id] = gq
                if gq.scope != "goal" or gq.id != goal.id:
                    problems.append(f"{base}/qa.json: scope/id mismatch")
            for name, model in GOAL_OPTIONAL_FILES.items():
                if (root / base / name).exists():
                    loaded_optional = _load(root / base / name, model, problems,
                                            f"{base}/{name}")
                    if loaded_optional is not None:
                        optional[name][goal.id] = loaded_optional
    if manifest is not None:
        for person in tree.people:
            for leaf in (person.id, *[goal.id for goal in person.goals]):
                if leaf not in manifest.leaves:
                    problems.append(f"manifest.json: no record for leaf {leaf}")
    if problems or manifest is None:
        raise BundleError(problems)
    return Bundle(manifest=manifest, tree=tree, overviews=overviews,
                  person_qa=person_qa, interviews=interviews, plans=plans,
                  goal_qa=goal_qa, today=optional["today.json"],
                  briefs=optional["briefs.json"])
