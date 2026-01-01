from django.shortcuts import render
from accounts.decorators import etudiant_required

@etudiant_required
def dashboard(request):
    return render(request, "etudiant/dashboard.html")
