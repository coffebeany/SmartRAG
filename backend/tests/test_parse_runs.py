from app.services.parse_runs import _paginate_elements


def test_paginate_elements_defaults_and_slices() -> None:
    elements = [{"index": index} for index in range(80)]

    page = _paginate_elements(elements)

    assert page.total == 80
    assert page.offset == 0
    assert page.limit == 50
    assert len(page.items) == 50
    assert page.items[0] == {"index": 0}
    assert page.items[-1] == {"index": 49}


def test_paginate_elements_clamps_limit_and_offset() -> None:
    elements = [{"index": index} for index in range(600)]

    page = _paginate_elements(elements, offset=-10, limit=900)

    assert page.offset == 0
    assert page.limit == 500
    assert len(page.items) == 500
