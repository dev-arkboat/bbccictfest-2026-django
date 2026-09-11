from django.urls import path

from . import views

app_name = "registrations"

urlpatterns = [
    path("", views.event_list, name="events"),
    path("my/", views.my_registrations, name="my"),
    path("board/", views.organizer_board, name="board"),
    path("verify/", views.verify_registrations, name="verify"),
    path("r/<int:pk>/check-in/", views.check_in_toggle, name="check_in"),
    path("lookup/", views.registration_lookup, name="lookup"),
    path("ca/apply/", views.ca_apply, name="ca_apply"),
    path("ca/", views.ambassador_list, name="ca_list"),
    path("ca/dashboard/", views.ca_dashboard, name="ca_dashboard"),
    path("ca/<int:pk>/", views.ambassador_detail, name="ca_detail"),
    path("ca/<int:pk>/review/", views.ambassador_review_upsert, name="ca_review"),
    path("ca/<int:pk>/review/delete/", views.ambassador_review_delete, name="ca_review_delete"),
    path("ca/<int:pk>/qr.png", views.ambassador_qr, name="ca_qr"),
    path("ca/<int:pk>/qr-download/", views.ambassador_qr_download, name="ca_qr_download"),
    path("pay/callback/", views.bkash_callback, name="bkash_callback"),
    path("<slug:slug>/register/", views.register, name="register"),
    path("r/<int:pk>/", views.registration_detail, name="detail"),
    path("r/<int:pk>/receipt/", views.registration_receipt, name="receipt"),
    path("r/<int:pk>/pay/", views.pay, name="pay"),
    path("r/<int:pk>/refresh/", views.refresh_status, name="refresh"),
    path("r/<int:pk>/success/", views.payment_success, name="success"),
    path("r/<int:pk>/failed/", views.payment_failed, name="failed"),
]
