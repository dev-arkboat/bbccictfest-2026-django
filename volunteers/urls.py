from django.urls import path

from . import views

app_name = "volunteers"

urlpatterns = [
    path("", views.volunteer_list, name="list"),
    path("<int:pk>/", views.volunteer_detail, name="detail"),
    path("<int:pk>/review/", views.volunteer_review_upsert, name="review"),
    path("<int:pk>/review/delete/", views.volunteer_review_delete, name="review_delete"),
    path("<int:pk>/qr.png", views.volunteer_qr, name="qr"),
    path("<int:pk>/qr-download/", views.volunteer_qr_download, name="qr_download"),
]
