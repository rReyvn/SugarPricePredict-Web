from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, Http404
from datetime import datetime
import os
import joblib
from .models import UploadedFile
from rfr_model.pipeline import get_model_paths


def home(request):
    price_type = request.GET.get("price_type") or "local"
    if price_type not in ["local", "premium"]:
        price_type = "local"
    
    paths = get_model_paths(price_type)

    # Get last trained timestamp
    last_trained_timestamp = None
    if os.path.exists(paths["last_training_timestamp_path"]):
        with open(paths["last_training_timestamp_path"], "r") as f:
            try:
                last_trained_timestamp = datetime.fromisoformat(f.read().strip())
            except ValueError:
                pass

    # Get model training date range
    training_date_range = None
    if os.path.exists(paths["df_transformed_path"]):
        try:
            df_transformed = joblib.load(paths["df_transformed_path"])
            if not df_transformed.empty and "Date" in df_transformed.columns:
                min_date = df_transformed["Date"].min().strftime("%d-%m-%Y")
                max_date = df_transformed["Date"].max().strftime("%d-%m-%Y")
                training_date_range = f"{min_date} to {max_date}"
        except Exception:
            pass
    
    # Get RMSE and MAPE values
    rmse = None
    mape = None
    if os.path.exists(paths["evaluation_metrics_path"]):
        try:
            evaluation_metrics = joblib.load(paths["evaluation_metrics_path"])
            # Access the nested 'overall' dictionary
            overall_metrics = evaluation_metrics.get("overall", {})
            rmse = overall_metrics.get("RMSE")
            mape = overall_metrics.get("MAPE")
        except Exception:
            pass

    context = {
        "last_trained_timestamp": last_trained_timestamp,
        "training_date_range": training_date_range,
        "rmse": rmse,
        "mape": mape,
        "price_type": price_type,
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
        price_type_from_form = request.POST.get("price_type", "local")
        
        # Default redirect parameters
        redirect_status = "success"
        redirect_message = "Dataset uploaded successfully!"

        try:
            UploadedFile.objects.create(file=file, price_type=price_type_from_form)
        except Exception as e:
            print(f"Error uploading file: {e}")
            redirect_status = "error"
            redirect_message = f"Failed to upload dataset: {e}"

        return redirect(
            f"/dashboard/?price_type={price_type_from_form}&status={redirect_status}&message={redirect_message}"
        )

    price_type = request.GET.get("price_type") or "local"
    if price_type not in ["local", "premium"]:
        price_type = "local"

    paths = get_model_paths(price_type)
    uploaded_files_list = UploadedFile.objects.filter(price_type=price_type).order_by("-upload_date")

    paginator = Paginator(uploaded_files_list, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    last_trained_timestamp = None
    if os.path.exists(paths["last_training_timestamp_path"]):
        with open(paths["last_training_timestamp_path"], "r") as f:
            try:
                last_trained_timestamp = datetime.fromisoformat(f.read().strip())
            except ValueError:
                pass

    context = {
        "uploaded_files": page_obj,
        "last_trained_timestamp": last_trained_timestamp,
        "price_type": price_type,
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
    price_type = request.POST.get("price_type", "local")
    try:
        uploaded_file = get_object_or_404(UploadedFile, pk=file_id)
        file_name = uploaded_file.name
        uploaded_file.delete()
        message = f"Dataset '{file_name}' deleted successfully."
        status = "success"
    except Exception as e:
        message = f"Error deleting file: {e}"
        status = "error"
    
    return redirect(f"/dashboard/?price_type={price_type}&status={status}&message={message}")
