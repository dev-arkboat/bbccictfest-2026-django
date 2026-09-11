from django import forms


class StarRatingWidget(forms.RadioSelect):
    """5 clickable stars (1-5) instead of plain radio buttons.

    Renders ``<input type=radio>`` + ``<label>★</label>`` sibling pairs
    (highest value first), so pure CSS (row-reverse flexbox + ``~`` sibling
    selectors) fills stars on hover / when checked — no JavaScript needed,
    and the real radio inputs keep keyboard + screen-reader support.
    """

    template_name = "forms/star_rating.html"
    option_template_name = "forms/star_rating_option.html"
