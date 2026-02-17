from django.shortcuts import render, redirect
from django.conf import settings
import os
from datetime import datetime


def home(request):
    return render(request, "home.html")


def login_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        if username == "demo" and password == "demo":
            request.session['is_authenticated'] = True
            return redirect("dashboard")
        else:
            error = "Invalid username or password"
    return render(request, "login.html", {"error": error})


def logout_view(request):
    try:
        del request.session['is_authenticated']
    except KeyError:
        pass
    return redirect('login')


def dashboard_view(request):
    if not request.session.get('is_authenticated'):
        return redirect('login')

    upload_dir = os.path.join(settings.BASE_DIR, "datasets")
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
                    dates.append(pd.to_datetime(col, format='%d/ %m/ %Y'))
                except (ValueError, TypeError):
                    continue
            
            if dates:
                start_date = min(dates).strftime('%Y-%m-%d')
                end_date = max(dates).strftime('%Y-%m-%d')
                
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
                uploaded_files.append(
                    {
                        "name": entry.name,
                        "upload_date": datetime.fromtimestamp(stat.st_mtime),
                    }
                )

    # Sort files by upload date, newest first
    uploaded_files.sort(key=lambda x: x["upload_date"], reverse=True)

    return render(request, "dashboard.html", {"uploaded_files": uploaded_files})
