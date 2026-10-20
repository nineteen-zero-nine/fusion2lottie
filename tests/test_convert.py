from pathlib import Path

import pytest

from fusion2lottie import ConversionError, check, convert, parse
from lottie_eval import find, transform_of, value_at

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def intro():
    lottie, notes = convert(parse((FIXTURES / "valhalla-intro.comp").read_text()), fps=30)
    return lottie


def test_the_intro_converts_to_a_shape_layer_over_a_solid(intro):
    assert (intro["w"], intro["h"], intro["fr"], intro["op"]) == (1024, 1024, 30, 90)
    assert [(layer["nm"], layer["ty"]) for layer in intro["layers"]] == [("Render", 4), ("Ash", 1)]
    assert intro["layers"][1]["sc"] == "#141414"


# What Fusion itself reports for these inputs in Resolve 21.1 (Tool.GetInput(name, frame)).
FUSION_FEATHER1_ROTATION = {26: 38.0, 28: 33.361, 30: 28.096, 32: 22.519, 34: 16.941, 36: 11.676, 38: 7.037,
                            40: 3.336, 42: 0.886, 44: 0.0}
FUSION_DIAMOND_SIZE = {30: 0.0, 32: 0.224, 34: 0.4807, 36: 0.7375, 38: 0.9615, 40: 1.1199, 42: 1.18, 44: 1.1519,
                       46: 1.09, 48: 1.0281, 50: 1.0}


def test_keyframes_play_back_at_fusions_values(intro):
    rotation = transform_of(find(intro, "Feather1"))["r"]
    for frame, fusion in FUSION_FEATHER1_ROTATION.items():
        assert value_at(rotation, frame) == pytest.approx(-fusion, abs=1e-3)  # Lottie turns clockwise
    scale = transform_of(find(intro, "Diamond"))["s"]
    for frame, fusion in FUSION_DIAMOND_SIZE.items():
        assert value_at(scale, frame) == pytest.approx(fusion * 100, abs=1e-2)


def test_keyframes_convert_exactly_without_sampling(intro):
    rotation = transform_of(find(intro, "Feather1"))["r"]
    assert len(rotation["k"]) == 2


def test_fusion_draws_its_highest_input_on_top(intro):
    logo = find(intro, "Logo")
    assert [item["nm"] for item in logo["it"]] == ["Wordmark", "Diamond", "RightWing", "LeftWing",
                                                   "Logo transform"]


def test_a_mirroring_stransform_scales_by_minus_one(intro):
    mirror = transform_of(find(intro, "RightWing"))
    assert mirror["s"]["k"] == [-100, 100]
    assert find(find(intro, "RightWing"), "Feather1") is not None  # one output feeding two tools: drawn twice


def test_coordinates_go_from_shape_units_to_pixels(intro):
    diamond = transform_of(find(intro, "Diamond"))
    center = (-0.000098, 0.09375)  # the Diamond's Center in the comp, in shape units
    assert diamond["p"]["k"] == pytest.approx([512 + center[0] * 1024, 512 - center[1] * 1024])


def comp_with(tools: str) -> str:
    return ("Composition { RenderRange = { 0, 9 }, GlobalRange = { 0, 9 }, Tools = {\n" + tools +
            '\nOut = Merge { Inputs = { Foreground = Input { SourceOp = "Render", Source = "Output" } } },'
            '\nMediaOut1 = Saver { Inputs = { Index = Input { Value = "0" }, '
            'Input = Input { SourceOp = "Out", Source = "Output" } } },\n} }')


def test_every_problem_is_listed_not_just_the_first():
    text = comp_with('Blob = sBlobby { },'
                     'Twist = sPolygon { Inputs = { XRotation = Input { Value = 30 }, '
                     'Polyline = Input { Value = Polyline { Closed = true, Points = { { X = 0, Y = 0 } } } } } },'
                     'Both = sMerge { Inputs = { Input1 = Input { SourceOp = "Blob", Source = "Output" }, '
                     'Input2 = Input { SourceOp = "Twist", Source = "Output" } } },'
                     'Render = sRender { Inputs = { Input = Input { SourceOp = "Both", Source = "Output" } } },')
    problems = check(parse(text))
    assert len(problems) == 2
    assert any("sBlobby" in p for p in problems) and any("Twist.XRotation" in p for p in problems)
    with pytest.raises(ConversionError) as e:
        convert(parse(text))
    assert e.value.problems == problems


def test_modifiers_other_than_keyframes_are_refused():
    text = comp_with('Spin = sPolygon { Inputs = { ZRotation = Input { SourceOp = "Wobble", Source = "Value" }, '
                     'Polyline = Input { Value = Polyline { Closed = true, Points = { { X = 0, Y = 0 } } } } } },'
                     'Wobble = Perturb { },'
                     'Render = sRender { Inputs = { Input = Input { SourceOp = "Spin", Source = "Output" } } },')
    assert check(parse(text)) == ["Wobble: Perturb modifier — only BezierSpline keyframes convert"]


def test_a_transformed_merge_is_refused():
    text = comp_with('Render = sRender { },').replace(
        'Foreground = Input', 'Size = Input { Value = 0.5 }, Foreground = Input')
    assert check(parse(text)) == ["Out.Size: scaling a Merge is not supported"]
