from django.shortcuts import render
from django.shortcuts import render, redirect

def home(request):
    return render(request, 'home.html')

def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username == 'demo' and password == 'demo':
            # A real app would set a session variable here
            # request.session['user'] = username
            return redirect('home')
        else:
            error = 'Invalid username or password'
    return render(request, 'login.html', {'error': error})

