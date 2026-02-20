from django.shortcuts import render, redirect
from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, Http404
from datetime import datetime
import os


def home(request):
    return render(request, "home.html")


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


def logout_view(request):  #
    logout(request)  #
    return redirect("login")


from rfr_model.pipeline import LAST_TRAINING_TIMESTAMP_PATH


def dashboard_view(request):
    if not request.user.is_authenticated:  #
        return redirect("login")

    upload_dir = os.path.join(settings.BASE_DIR, "rfr_model", "datasets")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    if request.method == "POST" and "excel_file" in request.FILES:
        file = request.FILES["excel_file"]
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, "wb+") as destination:
            for chunk in file.chunks():
                destination.write(chunk)

        try:
            import pandas as pd

            df = pd.read_excel(file_path)

            dates = []
            for col in df.columns:
                try:
                    # The user specified the format '%d/ %m/ %y', but the file shows '%d/ %m/ %Y'.
                    # I will trust the file content.
                    dates.append(pd.to_datetime(col, format="%d/ %m/ %Y"))
                except (ValueError, TypeError):
                    continue

            if dates:
                start_date = min(dates).strftime("%Y-%m-%d")
                end_date = max(dates).strftime("%Y-%m-%d")

                _, file_extension = os.path.splitext(file.name)
                new_filename = f"{start_date}_{end_date}{file_extension}"
                new_file_path = os.path.join(upload_dir, new_filename)

                os.rename(file_path, new_file_path)
                print(f"File successfully renamed to {new_filename}")
            else:
                print("No dates found in the column headers of the uploaded file.")

        except Exception as e:
            # log the error and continue with original filename
            print(f"An error occurred during file processing: {e}")
            pass

        return redirect("dashboard")

    uploaded_files = []
    with os.scandir(upload_dir) as entries:
        for entry in entries:
            if entry.is_file():
                stat = entry.stat()
                start_date, end_date = None, None
                try:
                    filename_without_ext, _ = os.path.splitext(entry.name)
                    start_date_str, end_date_str = filename_without_ext.split("_")
                    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    pass  # Keep start_date and end_date as None if parsing fails

                uploaded_files.append(
                    {
                        "name": entry.name,
                        "upload_date": datetime.fromtimestamp(stat.st_mtime),
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                )

    # Sort files by upload date, newest first
    uploaded_files.sort(key=lambda x: x["upload_date"], reverse=True)

    paginator = Paginator(uploaded_files, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Get last trained timestamp
    last_trained_timestamp = None
    if os.path.exists(LAST_TRAINING_TIMESTAMP_PATH):
        with open(LAST_TRAINING_TIMESTAMP_PATH, "r") as f:
            try:
                last_trained_timestamp = datetime.fromisoformat(f.read().strip())
            except ValueError:
                pass  # Ignore if the file is malformed

    context = {
        "uploaded_files": page_obj,
        "last_trained_timestamp": last_trained_timestamp,
    }

    return render(request, "dashboard.html", context)


def download_file(request, filename):
    upload_dir = os.path.join(settings.BASE_DIR, "rfr_model", "datasets")
    file_path = os.path.join(upload_dir, filename)

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


def delete_file(request, filename):
    upload_dir = os.path.join(settings.BASE_DIR, "rfr_model", "datasets")
    file_path = os.path.join(upload_dir, filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect("dashboard")
