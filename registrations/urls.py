from django.urls import path

from . import views

app_name = "registrations"

urlpatterns = [
    path("", views.event_list, name="events"),
    path("board/", views.organizer_board, name="board"),
    path("verify/", views.verify_registrations, name="verify"),
    path("r/<int:pk>/check-in/", views.check_in_toggle, name="check_in"),
    path("ca/", views.ambassador_list, name="ca_list"),
    path("ca/create/", views.ca_create, name="ca_create"),
    path("ca/dashboard/", views.ca_dashboard, name="ca_dashboard"),
    path("ca/<int:pk>/", views.ambassador_detail, name="ca_detail"),
    path("ca/<int:pk>/review/", views.ambassador_review_upsert, name="ca_review"),
    path("ca/<int:pk>/review/delete/", views.ambassador_review_delete, name="ca_review_delete"),
    path("ca/<int:pk>/qr.png", views.ambassador_qr, name="ca_qr"),
    path("ca/<int:pk>/qr-download/", views.ambassador_qr_download, name="ca_qr_download"),
]
