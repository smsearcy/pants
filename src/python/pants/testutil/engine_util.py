# Copyright 2019 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re
from dataclasses import dataclass
from io import StringIO
from types import CoroutineType, GeneratorType
from typing import Any, Callable, Optional, Sequence, Type

from colors import blue, cyan, green, magenta, red, yellow

from pants.engine.internals.selectors import Params as Params  # noqa: F401
from pants.engine.rules import Get
from pants.engine.unions import UnionMembership


# TODO(#6742): Improve the type signature by using generics and type vars. `mock` should be
#  `Callable[[SubjectType], ProductType]`.
@dataclass(frozen=True)
class MockGet:
    product_type: Type
    subject_type: Type
    mock: Callable[[Any], Any]


def run_rule(
    rule,
    *,
    rule_args: Optional[Sequence[Any]] = None,
    mock_gets: Optional[Sequence[MockGet]] = None,
    union_membership: Optional[UnionMembership] = None,
):
    """A test helper function that runs an @rule with a set of arguments and mocked Get providers.

    An @rule named `my_rule` that takes one argument and makes no `Get` requests can be invoked
    like so (although you could also just invoke it directly):

    ```
    return_value = run_rule(my_rule, rule_args=[arg1])
    ```

    In the case of an @rule that makes Get requests, things get more interesting: the
    `mock_gets` argument must be provided as a sequence of `MockGet`s. Each MockGet takes the Product
    and Subject type, along with a one-argument function that takes a subject value and returns a
    product value.

    So in the case of an @rule named `my_co_rule` that takes one argument and makes Get requests
    for a product type `Listing` with subject type `Dir`, the invoke might look like:

    ```
    return_value = run_rule(
      my_co_rule,
      rule_args=[arg1],
      mock_gets=[
        MockGet(
          product_type=Listing,
          subject_type=Dir,
          mock=lambda dir_subject: Listing(..),
        ),
      ],
    )
    ```

    If any of the @rule's Get requests involve union members, you should pass a `UnionMembership`
    mapping the union base to any union members you'd like to test. For example, if your rule has
    `await Get(TestResult, TargetAdaptor, target_adaptor)`, you may pass
    `UnionMembership({TargetAdaptor: PythonTestsTargetAdaptor})` to this function.

    :returns: The return value of the completed @rule.
    """

    task_rule = getattr(rule, "rule", None)
    if task_rule is None:
        raise TypeError(f"Expected to receive a decorated `@rule`; got: {rule}")

    if rule_args is not None and len(rule_args) != len(task_rule.input_selectors):
        raise ValueError(
            f"Rule expected to receive arguments of the form: {task_rule.input_selectors}; got: {rule_args}"
        )

    if mock_gets is not None and len(mock_gets) != len(task_rule.input_gets):
        raise ValueError(
            f"Rule expected to receive Get providers for {task_rule.input_gets}; got: {mock_gets}"
        )

    res = rule(*(rule_args or ()))
    if not isinstance(res, (CoroutineType, GeneratorType)):
        return res

    def get(product, subject):
        provider = next(
            (
                mock_get.mock
                for mock_get in mock_gets
                if mock_get.product_type == product
                and (
                    mock_get.subject_type == type(subject)
                    or (
                        union_membership
                        and union_membership.is_member(mock_get.subject_type, subject)
                    )
                )
            ),
            None,
        )
        if provider is None:
            raise AssertionError(
                f"Rule requested: Get{(product, type(subject), subject)}, which cannot be satisfied."
            )
        return provider(subject)

    rule_coroutine = res
    rule_input = None
    while True:
        try:
            res = rule_coroutine.send(rule_input)
            if isinstance(res, Get):
                rule_input = get(res.product_type, res.subject)
            elif type(res) in (tuple, list):
                rule_input = [get(g.product_type, g.subject) for g in res]
            else:
                return res
        except StopIteration as e:
            if e.args:
                return e.value


class MockConsole:
    """An implementation of pants.engine.console.Console which captures output."""

    def __init__(self, use_colors=True):
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.use_colors = use_colors

    def write_stdout(self, payload):
        self.stdout.write(payload)

    def write_stderr(self, payload):
        self.stderr.write(payload)

    def print_stdout(self, payload):
        print(payload, file=self.stdout)

    def print_stderr(self, payload):
        print(payload, file=self.stderr)

    def _safe_color(self, text: str, color: Callable[[str], str]) -> str:
        return color(text) if self.use_colors else text

    def blue(self, text: str) -> str:
        return self._safe_color(text, blue)

    def cyan(self, text: str) -> str:
        return self._safe_color(text, cyan)

    def green(self, text: str) -> str:
        return self._safe_color(text, green)

    def magenta(self, text: str) -> str:
        return self._safe_color(text, magenta)

    def red(self, text: str) -> str:
        return self._safe_color(text, red)

    def yellow(self, text: str) -> str:
        return self._safe_color(text, yellow)


def assert_equal_with_printing(
    test_case, expected, actual, uniform_formatter: Optional[Callable[[str], str]] = None
):
    """Asserts equality, but also prints the values so they can be compared on failure.

    Usage:

       class FooTest(unittest.TestCase):
         assert_equal_with_printing = assert_equal_with_printing

         def test_foo(self):
           self.assert_equal_with_printing("a", "b")
    """
    str_actual = str(actual)
    print("Expected:")
    print(expected)
    print("Actual:")
    print(str_actual)

    if uniform_formatter is not None:
        expected = uniform_formatter(expected)
        str_actual = uniform_formatter(str_actual)

    test_case.assertEqual(expected, str_actual)


def remove_locations_from_traceback(trace: str) -> str:
    location_pattern = re.compile(r'"/.*", line \d+')
    address_pattern = re.compile(r"0x[0-9a-f]+")
    new_trace = location_pattern.sub("LOCATION-INFO", trace)
    new_trace = address_pattern.sub("0xEEEEEEEEE", new_trace)
    return new_trace