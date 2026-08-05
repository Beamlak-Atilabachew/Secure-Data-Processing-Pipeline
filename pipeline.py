
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Any

A = TypeVar("A")
B = TypeVar("B")


# ======================================================================
# 1. THE FUNCTOR / MONAD: Result[A]
# ======================================================================
class Result(ABC, Generic[A]):
    @abstractmethod
    def map(self, f: Callable[[A], B]) -> "Result[B]":
        """FUNCTOR operation. Lift f: A -> B into Result[A] -> Result[B]."""
        ...

    @abstractmethod
    def bind(self, f: Callable[[A], "Result[B]"]) -> "Result[B]":
        """MONAD operation (a.k.a. flatMap / >>=).
        Chains a step that itself returns a Result, flattening instead
        of nesting. This is where failure short-circuiting happens."""
        ...

    @abstractmethod
    def is_success(self) -> bool:
        ...

    def __rshift__(self, f: Callable[[A], "Result[B]"]) -> "Result[B]":
        """Syntax sugar: r >> f   ==   r.bind(f)
        This mimics the Kleisli composition operator from category theory."""
        return self.bind(f)


@dataclass
class Success(Result[A]):
    value: A

    def map(self, f: Callable[[A], B]) -> "Result[B]":
        return Success(f(self.value))

    def bind(self, f: Callable[[A], "Result[B]"]) -> "Result[B]":
        return f(self.value)

    def is_success(self) -> bool:
        return True

    def __repr__(self) -> str:
        return f"Success({self.value!r})"


@dataclass
class Failure(Result[Any]):
    error: str
    stage: str = "unknown"

    def map(self, f: Callable[[A], B]) -> "Result[B]":
        return self  # Functor law: preserve structure, don't touch the error

    def bind(self, f: Callable[[A], "Result[B]"]) -> "Result[B]":
        return self  # Monad short-circuit: skip every later step

    def is_success(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"Failure(stage={self.stage!r}, error={self.error!r})"


# ======================================================================
# 2. MORPHISMS (the actual pipeline steps)
#    Each is a plain function: dict -> Result[dict]  (or dict -> dict)
# ======================================================================
def parse_record(raw: dict) -> Result[dict]:
    """A -> Result[A]. Checks required keys exist. Can fail -> use bind."""
    required = {"name", "age", "email"}
    missing = required - raw.keys()
    if missing:
        return Failure(f"missing fields: {missing}", stage="parse_record")
    return Success(raw)


def validate_age(record: dict) -> Result[dict]:
    """Can fail -> use bind."""
    age = record.get("age")
    if not isinstance(age, int) or not (0 <= age <= 120):
        return Failure(f"invalid age: {age!r}", stage="validate_age")
    return Success(record)


def validate_email(record: dict) -> Result[dict]:
    """Can fail -> use bind."""
    email = record.get("email", "")
    if "@" not in email or "." not in email.split("@")[-1]:
        return Failure(f"invalid email: {email!r}", stage="validate_email")
    return Success(record)

def sanitize_name(record: dict) -> dict:
    """CANNOT fail -> pure transformation -> used with .map, not .bind."""
    cleaned = dict(record)
    cleaned["name"] = cleaned["name"].strip().title()
    return cleaned


def mask_email(record: dict) -> dict:
    """CANNOT fail -> pure transformation -> used with .map."""
    cleaned = dict(record)
    user, domain = cleaned["email"].split("@")
    cleaned["email"] = user[0] + "***@" + domain
    return cleaned

# ======================================================================
# 3. THE PIPELINE CLASS
#    Composes morphisms in order, using bind for fallible steps
#    and map for pure ones. This IS Kleisli composition.
# ======================================================================
class SecureDataPipeline:
    """
    Represents composition of morphisms in our category:
        parse_record  >>  validate_age  >>  validate_email
             .map(sanitize_name).map(mask_email)

    The pipeline itself never inspects whether a step failed -- that
    logic lives entirely inside Result. This is the payoff of using
    a Monad: business logic stays clean, error-plumbing is automatic.
    """

    def __init__(self) -> None:
        self._steps: list[Callable[[dict], Result[dict]]] = []

    def then(self, step: Callable[[dict], Result[dict]]) -> "SecureDataPipeline":
        """Register a fallible step (A -> Result[A])."""
        self._steps.append(step)
        return self

    def then_pure(self, step: Callable[[dict], dict]) -> "SecureDataPipeline":
        """Register a pure step (A -> A) by wrapping it as a .map call."""
        self._steps.append(lambda record: Success(record).map(step))
        return self

    def run(self, raw: dict) -> Result[dict]:
        result: Result[dict] = Success(raw)
        for step in self._steps:
            result = result.bind(step)
        return result
# ======================================================================
# 4. DEMO
# ======================================================================
if __name__ == "__main__":
    pipeline = (
        SecureDataPipeline()
        .then(parse_record)
        .then(validate_age)
        .then(validate_email)
        .then_pure(sanitize_name)
        .then_pure(mask_email)
    )

    good_record = {"name": "  Abemelek  ", "age": 36, "email": "abemelek@math.org"}
    bad_age_record = {"name": "Melaku Ture ", "age": -67, "email": "melak@cs.org"}
    missing_field_record = {"name": "Keleme Elias", "age": 65}

    for label, record in [
        ("GOOD RECORD", good_record),
        ("BAD AGE", bad_age_record),
        ("MISSING FIELD", missing_field_record),
    ]:
        print(f"--- {label} ---")
        print("input :", record)
        print("output:", pipeline.run(record))
        print()
