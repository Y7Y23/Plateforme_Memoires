from django.shortcuts import render
from accounts.decorators import responsable_required

@responsable_required
def dashboard(request):
    return render(request, "responsable/dashboard.html")
