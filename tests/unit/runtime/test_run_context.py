"""Unit tests for the run-context seam (Story 2.4 AC 5, AC 6).

Pure by construction: no disk, no network, no clock in `run_context.py`
itself, so most of this file needs neither a built package nor CrewAI. One
test is the exception — proving the goal reaches an actual prompt, not just a
`TaskSpec.description` string nobody reads, requires a real (offline,
intercepted) CrewAI run, and is separately gated with
`pytest.importorskip("crewai")`.
"""
from __future__ import annotations

import pytest
from pydantic import SecretStr

from team_maker.keyconfig import KeyConfig
from team_maker.pipeline.runner import PipelineRunner
from team_maker.runtime.executor import run_team_package
from team_maker.runtime.run_context import RunDocument, augment_team_for_run
from tests.support.team_factories import agent_spec, generated_team, task_spec


def _team_with_two_tasks():
    return generated_team(
        [agent_spec("writer"), agent_spec("editor")],
        [
            task_spec("draft", "writer"),
            task_spec("polish", "editor", dependencies=["draft"]),
        ],
    )


def test_returns_a_new_team_object():
    team = _team_with_two_tasks()

    result = augment_team_for_run(team, "ship it")

    assert result is not team


def test_does_not_mutate_the_original_team_or_its_tasks():
    team = _team_with_two_tasks()
    original_descriptions = [task.description for task in team.tasks]

    augment_team_for_run(team, "a goal that must not leak backward")

    assert [task.description for task in team.tasks] == original_descriptions


def test_returns_new_task_objects_not_the_originals():
    team = _team_with_two_tasks()

    result = augment_team_for_run(team, "ship it")

    for original, augmented in zip(team.tasks, result.tasks):
        assert augmented is not original


def test_goal_lands_in_every_task_description_not_only_the_first():
    """Every agent sees the goal directly — crewai's `context=` wiring only
    forwards a prior task's *output*, not the original run text, so a later
    task's agent would otherwise never see it at all."""
    team = _team_with_two_tasks()

    result = augment_team_for_run(team, "a very particular goal phrase")

    assert all("a very particular goal phrase" in task.description for task in result.tasks)


def test_original_task_description_is_preserved_as_a_prefix():
    team = _team_with_two_tasks()

    result = augment_team_for_run(team, "ship it")

    for original, augmented in zip(team.tasks, result.tasks):
        assert augmented.description.startswith(original.description)


def test_no_documents_means_no_document_section():
    team = _team_with_two_tasks()

    result = augment_team_for_run(team, "ship it")

    for task in result.tasks:
        assert "Attached document" not in task.description


def test_documents_land_in_every_task_description():
    team = _team_with_two_tasks()
    documents = [
        RunDocument(name="brief.txt", text="Ship a v1 by Friday."),
        RunDocument(name="notes.txt", text="Prefer plain language."),
    ]

    result = augment_team_for_run(team, "ship it", documents=documents)

    for task in result.tasks:
        assert "brief.txt" in task.description
        assert "Ship a v1 by Friday." in task.description
        assert "notes.txt" in task.description
        assert "Prefer plain language." in task.description


def test_braces_in_the_goal_survive_verbatim():
    """The measured reason `crew.kickoff()` is called with no `inputs=` once
    the goal is injected here: with `inputs=`, crewai's own template
    interpolation raises `ValueError` on a brace with no matching key. This
    module must not reintroduce that risk by, say, `.format()`-ing the text."""
    team = _team_with_two_tasks()
    goal_with_braces = "Address {this} and a lone { brace and a } brace."

    result = augment_team_for_run(team, goal_with_braces)

    assert all(goal_with_braces in task.description for task in result.tasks)


def test_braces_in_a_document_survive_verbatim():
    team = _team_with_two_tasks()
    document = RunDocument(name="snippet.py", text="config = {'key': '{value}'}")

    result = augment_team_for_run(team, "ship it", documents=[document])

    assert all("config = {'key': '{value}'}" in task.description for task in result.tasks)


def test_documents_default_to_empty_and_are_keyword_only():
    team = _team_with_two_tasks()

    # Positional documents must not be accepted — callers passing a bare list
    # positionally is not part of the contract this signature makes.
    with pytest.raises(TypeError):
        augment_team_for_run(team, "ship it", [RunDocument("a", "b")])


def test_run_team_package_documents_parameter_is_keyword_only(tmp_path, minimal_request):
    """Task 2's contract: `run_team_package` grows a keyword-only `documents`
    parameter, so every existing positional caller is unaffected."""
    build = PipelineRunner().run(minimal_request)
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-ant-test")})

    with pytest.raises(TypeError):
        run_team_package(build.output_path, "ship it", key_config, None, [])


def test_goal_reaches_an_actual_prompt_a_task_was_run_with(monkeypatch, minimal_request):
    """AC 5's second measured claim: plumbing is not proof of effect. Proves
    the goal text is present in a message an agent's LLM was actually called
    with — not merely embedded in a `TaskSpec.description` nobody reads."""
    pytest.importorskip("crewai")
    from tests.support.crewai_interception import (
        block_all_network,
        install_call_recorder,
        warm_up_models,
    )

    build = PipelineRunner().run(minimal_request)
    key_config = KeyConfig(keys={"anthropic": SecretStr("sk-ant-test")})
    block_all_network(monkeypatch)
    calls = install_call_recorder(monkeypatch, warm_up_models(build.output_path, key_config))

    goal = "a very distinctive goal phrase xyzzy-42"
    run_team_package(build.output_path, goal, key_config)

    assert calls, "no LLM call was recorded — the probe itself is broken"
    assert any(
        goal in str(message.get("content", ""))
        for call in calls
        for message in call.messages
    ), "the goal text never appeared in any message handed to an LLM"
