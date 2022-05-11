# Copyright 2022 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
from __future__ import annotations

import re
from textwrap import dedent

import pytest

from internal_plugins.test_lockfile_fixtures.lockfile_fixture import JVMLockfileFixture
from pants.backend.java.compile.javac import rules as javac_rules
from pants.backend.java.target_types import rules as target_types_rules
from pants.backend.kotlin.compile import kotlinc, kotlinc_plugins
from pants.backend.kotlin.compile.kotlinc_test import KOTLIN_STDLIB_REQUIREMENTS
from pants.backend.kotlin.dependency_inference.rules import rules as kotlin_dep_inf_rules
from pants.backend.kotlin.subsystems.kotlin import DEFAULT_KOTLIN_VERSION
from pants.backend.kotlin.target_types import KotlinJunitTestsGeneratorTarget
from pants.backend.kotlin.test.junit import rules as kotlin_junit_rules
from pants.core.goals.test import TestResult
from pants.core.target_types import FilesGeneratorTarget, FileTarget, RelocatedFiles
from pants.core.util_rules import config_files, source_files
from pants.core.util_rules.external_tool import rules as external_tool_rules
from pants.engine.addresses import Addresses
from pants.engine.target import CoarsenedTargets
from pants.jvm import classpath
from pants.jvm.jdk_rules import rules as java_util_rules
from pants.jvm.non_jvm_dependencies import rules as non_jvm_dependencies_rules
from pants.jvm.resolve.coursier_fetch import rules as coursier_fetch_rules
from pants.jvm.resolve.coursier_setup import rules as coursier_setup_rules
from pants.jvm.target_types import JvmArtifactTarget
from pants.jvm.test.junit import JunitTestFieldSet
from pants.jvm.test.junit import rules as jvm_junit_rules
from pants.jvm.test.junit_test import run_junit_test
from pants.jvm.util_rules import rules as util_rules
from pants.testutil.rule_runner import PYTHON_BOOTSTRAP_ENV, QueryRule, RuleRunner

kotlin_test_jvm_lockfile = pytest.mark.jvm_lockfile(
    path="kotlin-test.test.lock",
    requirements=[
        "junit:junit:4.13.2",
        f"org.jetbrains.kotlin:kotlin-test-junit:{DEFAULT_KOTLIN_VERSION}",
        *KOTLIN_STDLIB_REQUIREMENTS,
    ],
)


@pytest.fixture
def rule_runner() -> RuleRunner:
    rule_runner = RuleRunner(
        preserve_tmpdirs=True,
        rules=[
            *kotlin_junit_rules(),
            *jvm_junit_rules(),
            *classpath.rules(),
            *config_files.rules(),
            *coursier_fetch_rules(),
            *coursier_setup_rules(),
            *external_tool_rules(),
            *java_util_rules(),
            *javac_rules(),
            *source_files.rules(),
            *target_types_rules(),
            *util_rules(),
            *non_jvm_dependencies_rules(),
            *kotlinc.rules(),
            *kotlinc_plugins.rules(),
            *kotlin_dep_inf_rules(),
            QueryRule(CoarsenedTargets, (Addresses,)),
            QueryRule(TestResult, (JunitTestFieldSet,)),
        ],
        target_types=[
            FileTarget,
            FilesGeneratorTarget,
            RelocatedFiles,
            JvmArtifactTarget,
            KotlinJunitTestsGeneratorTarget,
        ],
    )
    rule_runner.set_options(
        # Makes JUnit output predictable and parseable across versions (#12933):
        args=["--junit-args=['--disable-ansi-colors','--details=flat','--details-theme=ascii']"],
        env_inherit=PYTHON_BOOTSTRAP_ENV,
    )
    return rule_runner


@kotlin_test_jvm_lockfile
def test_vintage_kotlin_simple_success(
    rule_runner: RuleRunner, jvm_lockfile: JVMLockfileFixture
) -> None:
    rule_runner.write_files(
        {
            "3rdparty/jvm/default.lock": jvm_lockfile.serialized_lockfile,
            "3rdparty/jvm/BUILD": jvm_lockfile.requirements_as_jvm_artifact_targets(),
            "BUILD": dedent(
                """\
                kotlin_junit_tests(
                    name='example-test',
                )
                """
            ),
            "SimpleTest.kt": dedent(
                """
                package org.pantsbuild.example

                import kotlin.test.Test
                import kotlin.test.assertEquals

                internal class SimpleTest {
                   @Test
                   fun testHello() {
                      assertEquals("Hello!", "Hello!")
                   }
                }
                """
            ),
        }
    )

    test_result = run_junit_test(rule_runner, "example-test", "SimpleTest.kt")

    assert test_result.exit_code == 0
    assert re.search(r"Finished:\s+testHello", test_result.stdout) is not None
    assert re.search(r"1 tests successful", test_result.stdout) is not None
    assert re.search(r"1 tests found", test_result.stdout) is not None
