from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from . import views
from rfr_model import views as rfr_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("logout/", views.logout_view, name="logout"),
    path("download/<int:file_id>/", views.download_file, name="download_file"),
    path("delete/<int:file_id>/", views.delete_file, name="delete_file"),
    # RFR Model URLs
    path("train/", rfr_views.start_training_view, name="start_training"),
    path("results/", rfr_views.prediction_results_view, name="prediction_results"),
    path("prediction_table/", rfr_views.prediction_table_view, name="prediction_table"),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
