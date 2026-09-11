from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("reviews/", views.reviews_list, name="reviews"),
    path("reviews/write/", views.review_upsert, name="review_write"),
    path("reviews/delete/", views.review_delete, name="review_delete"),
    path("games/", views.arcade_index, name="arcade"),
    path("games/<slug:slug>/", views.game_play, name="game_play"),
    path("robots.txt", views.robots_txt, name="robots"),
]
