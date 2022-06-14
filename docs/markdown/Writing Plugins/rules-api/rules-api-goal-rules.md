---
title: "Goal rules"
slug: "rules-api-goal-rules"
excerpt: "How to create new goals."
hidden: false
createdAt: "2020-05-07T22:38:43.975Z"
updatedAt: "2022-04-07T14:45:07.539Z"
---
For many [plugin tasks](doc:common-plugin-tasks), you will be extending existing goals, such as adding a new linter to the `lint` goal. However, you may instead want to create a new goal, such as a `publish` goal. This page explains how to create a new goal.

As explained in [Concepts](doc:rules-api-concepts), `@goal_rule`s are the entry-point into the rule graph. When a user runs `./pants my-goal`, the Pants engine will look for the respective `@goal_rule`. That `@goal_rule` will usually request other types, either as parameters in the `@goal_rule` signature or through `await Get`. But unlike a `@rule`, a `@goal_rule` may also trigger side-effects (such as running interactive processes, writing to the filesystem, etc) via `await Effect`.

Often, you can keep all of your logic inline in the `@goal_rule`. As your `@goal_rule` gets more complex, you may end up factoring out helper `@rule`s, but you do not need to start with writing helper `@rule`s.
[block:api-header]
{
  "title": "How to register a new goal"
}
[/block]
There are four steps to creating a new [goal](doc:goals) with Pants:

1. Define a subclass of `GoalSubsystem`. This is the API to your goal.
    1. Set the class property `name` to the name of your goal.
    2. Set the class property `help`, which is used by `./pants help`.
    3. You may register options through attributes of `pants.option.option_types` types. See [Options and subsystems](doc:subsystems).
2. Define a subclass of `Goal`. When a user runs `./pants my-goal`, the engine will request your subclass, which is what causes the `@goal_rule` to run.
     1. Set the class property `subsystem_cls` to the `GoalSubsystem` from the previous step.
     2. A `Goal` takes a single argument in its constructor, `exit_code: int`. Pants will use this to determine what its own exit code should be.
3. Define an `@goal_rule`, which must return the `Goal` from the previous step and set its `exit_code`.
     1. For most goals, simply return `MyGoal(exit_code=0)`. Some goals like `lint` and `test` will instead propagate the error code from the tools they run. 
4. Register the `@goal_rule` in a `register.py` file.
[block:code]
{
  "codes": [
    {
      "code": "from pants.engine.goal import Goal, GoalSubsystem\nfrom pants.engine.rules import collect_rules, goal_rule\n\n\nclass HelloWorldSubsystem(GoalSubsystem):\n    name = \"hello-world\"\n    help = \"An example goal.\"\n\n\nclass HelloWorld(Goal):\n    subsystem_cls = HelloWorldSubsystem\n\n\n@goal_rule\nasync def hello_world() -> HelloWorld:\n    return HelloWorld(exit_code=1)\n \n\ndef rules():\n    return collect_rules()",
      "language": "python",
      "name": "pants-plugins/example/hello_world.py"
    },
    {
      "code": "from example import hello_world\n\ndef rules():\n    return [*hello_world.rules()]",
      "language": "python",
      "name": "pants-plugins/example/register.py"
    }
  ]
}
[/block]
You may now run `./pants hello-world`, which should cause Pants to return with an error code of 1 (run `echo $?` to verify). Precisely, this causes the engine to request the type `HelloWorld`, which results in running the `@goal_rule` `hello_world`.
[block:api-header]
{
  "title": "`Console`: output to stdout/stderr"
}
[/block]
To output to the user, request the type `Console` as a parameter in your `@goal_rule`. This is a special type that may only be requested in `@goal_rules` and allows you to output to stdout and stderr.

```python
from pants.engine.console import Console
...

@goal_rule
async def hello_world(console: Console) -> HelloWorld:
    console.print_stdout("Hello!")
    console.print_stderr("Uh oh, an error.")
    return HelloWorld(exit_code=1)
```

### Using colors

You may output in color by using the methods `.blue()`, `.cyan()`, `.green()`, `.magenta()`, `.red()`, and `.yellow()`. The colors will only be used if the global option `--colors` is True.

```python
console.print_stderr(f"{console.red('𐄂')} Error encountered.")
```

### `Outputting` mixin (optional)

If your goal's purpose is to emit output, it may be helpful to use the mixin `Outputting`. This mixin will register the output `--output-file`, which allows the user to redirect the goal's stdout.

```python
from pants.engine.goal import Goal, GoalSubsystem, Outputting
from pants.engine.rules import goal_rule

class HelloWorldSubsystem(Outputting, GoalSubystem):
    name = "hello-world"
    help = "An example goal."

...

@goal_rule
async def hello_world(
    console: Console, hello_world_subsystem: HelloWorldSubsystem
) -> HelloWorld:
    with hello_world_subsystem.output(console) as write_stdout:
        write_stdout("Hello world!")
    return HelloWorld(exit_code=0)
```

### `LineOriented` mixin (optional)

If your goal's purpose is to emit output—and that output is naturally split by new lines—it may be helpful to use the mixin `LineOriented`. This subclasses `Outputting`, so will register both the options `--output-file` and `--sep`, which allows the user to change the separator to not be `\n`.

```python
from pants.engine.goal import Goal, GoalSubsystem, LineOriented
from pants.engine.rules import goal_rule

class HelloWorldSubsystem(LineOriented, GoalSubystem):
    name = "hello-world"
    help = "An example goal."""

...

@goal_rule
async def hello_world(
    console: Console, hello_world_subsystem: HelloWorldSubsystem
) -> HelloWorld:
    with hello_world_subsystem.line_oriented(console) as print_stdout:
        print_stdout("0")
        print_stdout("1")
    return HelloWorld(exit_code=0)
```
[block:api-header]
{
  "title": "How to operate on Targets"
}
[/block]
Most goals will want to operate on targets. To do this, specify `Targets` as a parameter of your goal rule.

```python
from pants.engine.target import Targets
...

@goal_rule
async def hello_world(console: Console, targets: Targets) -> HelloWorld:
    for target in targets:
        console.print_stdout(target.address.spec)
    return HelloWorld(exit_code=0)
```

This example will print the address of any targets specified by the user, just as the `list` goal behaves.

```bash
$ ./pants hello-world helloworld/util::
helloworld/util
helloworld/util:tests
``` 

See [Rules and the Target API](doc:rules-api-and-target-api)  for detailed information on how to use these targets in your rules, including accessing the metadata specified in BUILD files.
[block:callout]
{
  "type": "warning",
  "title": "Common mistake: requesting the type of target you want in the `@goal_rule` signature",
  "body": "For example, if you are writing a `publish` goal, and you expect to operate on `python_distribution` targets, you might think to request `PythonDistribution` in your `@goal_rule` signature:\n\n```python\n@goal_rule\ndef publish(distribution: PythonDistribution, console: Console) -> Publish:\n   ...\n```\n\nThis will not work because the engine has no path in the rule graph to resolve a `PythonDistribution` type given the initial input types to the rule graph (the \"roots\").\n\nInstead, request `Targets`, which will give you all of the targets that the user specified on the command line. The engine knows how to resolve this type because it can go from `AddressSpecs + FilesystemSpecs` -> `Specs` -> `Addresses` -> `Targets`.\n\nFrom here, filter out the relevant targets you want using the Target API (see [Rules and the Target API](doc:rules-api-and-target-api).\n\n```python\nfrom pants.engine.target import Targets\n\n@goal_rule\ndef publish(targets: Targets, console: Console) -> Publish:\n   relevant_targets = [\n       tgt for tgt in targets\n       if tgt.has_field(PythonPublishDestination)\n    ]\n```"
}
[/block]
### Only care about source files?

If you only care about files, and you don't need any metadata from BUILD files, then you can request `SpecsSnapshot` instead of `Targets`.

```python
from pants.engine.fs import SpecsSnapshot
...

@goal_rule
async def hello_world(console: Console, specs_snapshot: SpecsSnapshot) -> HelloWorld:
    for f in specs_snapshot.snapshot.files:
        console.print_stdout(f)
    return HelloWorld(exit_code=0)
```

When users use address arguments like `::`, you will get all the sources belonging to the matched targets. When users use file arguments like `'**'`, you will get all matching files, even if the file doesn't have any owning target.