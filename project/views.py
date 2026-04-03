from django.http import HttpResponse


def home(request):
    return HttpResponse("12bytes is ready. Core is installed.")
