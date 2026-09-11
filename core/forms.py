from django import forms

from .models import PersonReview, Review
from .widgets import StarRatingWidget


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": StarRatingWidget(choices=[(i, f"{i}") for i in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 4, "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            # New review: blank stars, not the model default.
            self.fields["rating"].initial = None


class PersonReviewForm(forms.ModelForm):
    class Meta:
        model = PersonReview
        fields = ["rating", "comment"]
        widgets = {
            "rating": StarRatingWidget(choices=[(i, f"{i}") for i in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 4, "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            # New review: blank stars, not the model default.
            self.fields["rating"].initial = None
