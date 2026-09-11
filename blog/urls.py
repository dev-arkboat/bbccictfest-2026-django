from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("<slug:slug>/", views.post_detail, name="detail"),
    path("<slug:slug>/comment/", views.post_comment, name="comment"),
    path("<slug:slug>/like/", views.post_like, name="like"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
]
