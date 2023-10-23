from __future__ import annotations

from more_itertools import all_unique
from pytest_cases import case, parametrize, parametrize_with_cases

from amltk.optuna.space import OptunaSpaceAdapter
from amltk.pipeline import Pipeline, Split, Step, split, step


@case
def case_single_step() -> Step:
    return step("a", object, space={"hp": [1, 2, 3]})


@case
def case_single_step_two_hp() -> Step:
    return step("a", object, space={"hp": [1, 2, 3], "hp2": [1, 2, 3]})


@case
def case_single_step_two_hp_different_types() -> Step:
    return step("a", object, space={"hp": [1, 2, 3], "hp2": (1, 10)})


@case
def case_joint_steps() -> Step:
    return step("a", object, space={"hp": [1, 2, 3]}) | step(
        "b",
        object,
        space={"hp2": (1, 10)},
    )


@case
def case_split_steps() -> Step:
    return split(
        "split",
        step("a", object, space={"hp": [1, 2, 3]}),
        step("b", object, space={"hp2": (1, 10)}),
    )


@case
def case_nested_splits() -> Split:
    return split(
        "split1",
        split(
            "split2",
            step("a", object, space={"hp": [1, 2, 3]}),
            step("b", object, space={"hp2": (1, 10)}),
        ),
        step("c", object, space={"hp3": (1, 10)}),
    )


@case
def case_simple_linear_pipeline() -> Pipeline:
    return Pipeline.create(
        step("a", object, space={"hp": [1, 2, 3]}),
        step("b", object, space={"hp": (1, 10)}),
        step("c", object, space={"hp": (1.0, 10.0)}),
    )


@case
def case_split_pipeline() -> Pipeline:
    return Pipeline.create(
        split(
            "split",
            step("a", object, space={"hp": [1, 2, 3]}),
            step("b", object, space={"hp": [1, 2, 3]}),
        ),
    )


@case
def case_pipeline_with_step_modules() -> Pipeline:
    return Pipeline.create(
        step("a", object, space={"hp": [1, 2, 3]}),
        step("b", object, space={"hp": (1, 10)}),
        step("c", object, space={"hp": (1.0, 10.0)}),
        modules=[
            step("d", object, space={"hp": (1.0, 10.0)}),
            step("e", object, space={"hp": (1.0, 10.0)}),
        ],
    )


@case
def case_pipeline_with_pipeline_modules() -> Pipeline:
    return Pipeline.create(
        step("a", object, space={"hp": [1, 2, 3]}),
        step("b", object, space={"hp": (1, 10)}),
        step("c", object, space={"hp": (1.0, 10.0)}),
        modules=[
            Pipeline.create(
                step("d", object, space={"hp": (1.0, 10.0)}),
                step("e", object, space={"hp": (1.0, 10.0)}),
            ),
        ],
    )


@parametrize("n", [None, 5, 10])
@parametrize_with_cases("item", cases=".", prefix="case_")
def test_sample_with_seed_returns_same_results(
    item: Pipeline | Step,
    n: int | None,
) -> None:
    configs_1 = item.sample(
        sampler=OptunaSpaceAdapter(),
        seed=1,
        n=n,
        duplicates=True,
    )
    configs_2 = item.sample(
        sampler=OptunaSpaceAdapter(),
        seed=1,
        n=n,
        duplicates=True,
    )

    assert configs_1 == configs_2


def test_sampling_no_duplicates() -> None:
    values = list(range(10))
    n = len(values)

    item: Step = step("x", object, space={"a": values})

    configs = item.sample(
        sampler=OptunaSpaceAdapter,
        n=n,
        duplicates=False,
        seed=42,
    )

    assert all_unique(configs)


def test_sampling_no_duplicates_with_seen_values() -> None:
    values = list(range(10))
    n = len(values)

    item: Step = step("x", object, space={"a": values})

    adapter = OptunaSpaceAdapter()
    seen_config = item.sample(sampler=adapter, seed=42)

    configs = item.sample(
        sampler=adapter,
        n=n - 1,
        duplicates=[seen_config],
        seed=42,
    )

    assert all_unique(configs)
    assert seen_config not in configs
