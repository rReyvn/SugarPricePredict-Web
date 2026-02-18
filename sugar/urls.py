"""
URL configuration for sugar project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from . import views
from rfr_model import views as rfr_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('download/<str:filename>/', views.download_file, name='download_file'),
    path('delete/<str:filename>/', views.delete_file, name='delete_file'),

    # RFR Model URLs
    path('train/', rfr_views.start_training_view, name='start_training'),
    path('results/', rfr_views.prediction_results_view, name='prediction_results'),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]