import pytest

from fusion2lottie import CompSyntaxError, Table, parse


def test_typed_tables_named_fields_and_positional_values():
    comp = parse('Composition { Tools = { A = Input { Value = { 0.5, -0.25 }, }, }, }')
    assert isinstance(comp, Table) and comp.kind == "Composition"
    value = comp["Tools"]["A"]["Value"]
    assert comp["Tools"]["A"].kind == "Input"
    assert value.kind is None and value.items_ == [0.5, -0.25]


def test_a_table_of_positional_values_only_is_an_empty_dict():
    keys = parse("{ [26] = { 38, RH = { 32, 25.333333 } } }")
    handle = keys[26.0]["RH"]
    assert not handle and handle is not None  # falsy: test handles for None, never for truth
    assert handle.items_ == [32.0, 25.333333]


def test_strings_booleans_numbers_and_comments():
    t = parse('{ -- a comment\n S = "a \\"quoted\\" path", B = true, N = -1.5e-3, Z = nil, ["Key:"] = 1 }')
    assert t["S"] == 'a "quoted" path'
    assert t["B"] is True and t["N"] == -0.0015 and t["Z"] is None and t["Key:"] == 1.0


def test_dotted_input_names():
    t = parse("{ Translate.X = Input { Value = 0.1 } }")
    assert t["Translate.X"]["Value"] == 0.1


@pytest.mark.parametrize("text", ["{ A = 1", "{ A = = 1 }", "{ } }"])
def test_broken_files_are_reported(text):
    with pytest.raises(CompSyntaxError):
        parse(text)
