from pathlib import Path

import pytest

from fusion2lottie import ConversionError, check, convert, needs_samples, parse
from lottie_eval import find, transform_of, value_at, vertex_at

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
    # Size scales the diamond's polyline (not its group, which would also scale an outline's width).
    path = next(item for item in find(intro, "Diamond")["it"] if item["ty"] == "sh")["ks"]
    full = vertex_at(path, 50)  # Size is 1 from frame 50
    for frame, fusion in FUSION_DIAMOND_SIZE.items():
        v = vertex_at(path, frame)
        assert v[0] == pytest.approx(full[0] * fusion, abs=1e-2) and v[1] == pytest.approx(full[1] * fusion, abs=1e-2)
    assert len(path["k"]) == 3  # still the three keyframes Fusion has, not sampled


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


SPIN = ('Spin = sPolygon { Inputs = { ZRotation = Input { SourceOp = "Wobble", Source = "Value" }, '
        'Center = Input { Value = { 0.1, 0 }, Expression = "Point(time / 100, 0)" }, '
        'Polyline = Input { Value = Polyline { Closed = true, Points = { { X = 0, Y = 0 }, { X = 0.1, Y = 0 }, '
        '{ X = 0, Y = 0.1 } } } } } },'
        'Wobble = Perturb { },'
        'Render = sRender { Inputs = { Input = Input { SourceOp = "Spin", Source = "Output" } } },')


def test_expressions_and_modifiers_need_fusions_values():
    comp = parse(comp_with(SPIN))
    assert sorted(needs_samples(comp)) == ["Spin.Center", "Spin.ZRotation"]
    problems = sorted(check(comp))
    assert problems[0].startswith("Spin.Center: driven by the expression `Point(time / 100, 0)`")
    assert problems[1].startswith("Spin.ZRotation: driven by Wobble (Perturb), which only Fusion can evaluate")


def test_sampled_values_become_a_keyframe_per_frame():
    samples = {"Spin.ZRotation": [f * 3.0 for f in range(10)], "Spin.Center": [[f / 100, 0.0] for f in range(10)]}
    lottie, _ = convert(parse(comp_with(SPIN)), samples=samples)
    tr = transform_of(find(lottie, "Spin"))
    assert len(tr["r"]["k"]) == 10
    assert value_at(tr["r"], 4) == pytest.approx(-12.0)
    assert value_at(tr["p"], 5) == pytest.approx(1920 / 2 + 0.05 * 1920)  # a comp without a frame format is 1920 wide


def test_samples_must_cover_every_frame():
    samples = {"Spin.ZRotation": [0.0] * 3, "Spin.Center": [[0.0, 0.0]] * 10}
    assert check(parse(comp_with(SPIN)), samples=samples) == ["Spin.ZRotation: 3 samples for 10 frames"]


def test_a_transformed_merge_is_refused():
    text = comp_with('Render = sRender { },').replace(
        'Foreground = Input', 'Size = Input { Value = 0.5 }, Foreground = Input')
    assert check(parse(text)) == ["Out.Size: scaling a Merge is not supported"]


@pytest.fixture(scope="module")
def primitives():
    return {name: convert(parse((FIXTURES / f"{name}.comp").read_text()), fps=30)[0]
            for name in ("rectangles", "ellipses", "stars", "outlines", "write-on")}


def path_of(lottie, name):
    return next(item for item in find(lottie, name)["it"] if item["ty"] == "sh")["ks"]


def test_a_size_animated_by_one_input_stays_keyframed(primitives):
    assert len(path_of(primitives["rectangles"], "Growing")["k"]) == 2  # Width eases from 0.05 to 0.6
    assert len(path_of(primitives["ellipses"], "Breathing")["k"]) == 3
    assert len(path_of(primitives["stars"], "Pulsing")["k"]) == 2  # Depth


def test_rotation_and_position_go_to_the_group_not_the_path(primitives):
    growing = transform_of(find(primitives["rectangles"], "Growing"))
    assert growing["r"]["a"] == 1 and growing["p"]["k"] == pytest.approx([256, 256 + 0.2 * 512])


def test_outlines_keep_fusions_joins_caps_and_width(primitives):
    def outline(name):
        return next(item for item in find(primitives["outlines"], name)["it"] if item["ty"] == "st")

    assert (outline("Bevel")["lj"], outline("Bevel")["lc"]) == (3, 1)  # bevel join, butt cap
    assert (outline("Round")["lj"], outline("Round")["lc"]) == (1, 3)  # miter join, square cap
    assert (outline("Thick")["lj"], outline("Thick")["lc"]) == (2, 2)  # round join, round cap
    assert outline("Frame")["w"]["k"] == pytest.approx(0.02 * 512)


def test_write_on_becomes_a_trim(primitives):
    trim = next(item for item in find(primitives["write-on"], "Sliding")["it"] if item["ty"] == "tm")
    assert trim["o"]["a"] == 1 and trim["e"]["k"] == pytest.approx(0.3 * (100 - 0.01) + 0.01)
