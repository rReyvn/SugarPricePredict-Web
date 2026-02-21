from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, Http404
from datetime import datetime
import os
import joblib
from .models import UploadedFile
from rfr_model.pipeline import LAST_TRAINING_TIMESTAMP_PATH, DF_TRANSFORMED_PATH, EVALUATION_METRICS_PATH


def home(request):
    # Get last trained timestamp
    last_trained_timestamp = None
    if os.path.exists(LAST_TRAINING_TIMESTAMP_PATH):
        with open(LAST_TRAINING_TIMESTAMP_PATH, "r") as f:
            try:
                last_trained_timestamp = datetime.fromisoformat(f.read().strip())
            except ValueError:
                pass

    # Get model training date range
    training_date_range = None
    if os.path.exists(DF_TRANSFORMED_PATH):
        try:
            df_transformed = joblib.load(DF_TRANSFORMED_PATH)
            if not df_transformed.empty and "Date" in df_transformed.columns:
                min_date = df_transformed["Date"].min().strftime("%d-%m-%Y")
                max_date = df_transformed["Date"].max().strftime("%d-%m-%Y")
                training_date_range = f"{min_date} to {max_date}"
        except Exception:
            pass
    
    # Get RMSE and MAPE values
    rmse = None
    mape = None
    if os.path.exists(EVALUATION_METRICS_PATH):
        try:
            evaluation_metrics = joblib.load(EVALUATION_METRICS_PATH)
            rmse = evaluation_metrics.get("RMSE")
            mape = evaluation_metrics.get("MAPE")
        except Exception:
            pass

    context = {
        "last_trained_timestamp": last_trained_timestamp,
        "training_date_range": training_date_range,
        "rmse": rmse,
        "mape": mape,
    }
    return render(request, "home.html", context)


def login_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            error = "Invalid username or password"
    return render(request, "login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST" and "excel_file" in request.FILES:
        file = request.FILES["excel_file"]
        # The save method of the model will handle the processing
        UploadedFile.objects.create(file=file)
        return redirect("dashboard")

    uploaded_files_list = UploadedFile.objects.all().order_by("-upload_date")

    paginator = Paginator(uploaded_files_list, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get last trained timestamp
    last_trained_timestamp = None
    if os.path.exists(LAST_TRAINING_TIMESTAMP_PATH):
        with open(LAST_TRAINING_TIMESTAMP_PATH, "r") as f:
            try:
                last_trained_timestamp = datetime.fromisoformat(f.read().strip())
            except ValueError:
                pass

    context = {
        "uploaded_files": page_obj,
        "last_trained_timestamp": last_trained_timestamp,
    }

    return render(request, "dashboard.html", context)


def download_file(request, file_id):
    uploaded_file = get_object_or_404(UploadedFile, pk=file_id)
    file_path = uploaded_file.file.path

    if os.path.exists(file_path):
        with open(file_path, "rb") as fh:
            response = HttpResponse(
                fh.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "inline; filename=" + os.path.basename(
                file_path
            )
            return response
    raise Http404


def delete_file(request, file_id):
    uploaded_file = get_object_or_404(UploadedFile, pk=file_id)
    uploaded_file.delete()
    return redirect("dashboard")
