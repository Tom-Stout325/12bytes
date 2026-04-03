from django.shortcuts import redirect

from .models import BusinessMembership


class ActiveBusinessMiddleware:
    allow_prefixes = (
        "/admin/",
        "/accounts/",
        "/static/",
        "/media/",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or "/"
        request.business = None

        if request.user.is_authenticated:
            membership = (
                BusinessMembership.objects.filter(user=request.user, is_active=True)
                .select_related("business")
                .first()
            )
            if membership:
                request.business = membership.business

        if any(path.startswith(prefix) for prefix in self.allow_prefixes):
            return self.get_response(request)

        if request.user.is_authenticated and request.business is None and path != "/core/onboarding/":
            return redirect("core:onboarding")

        return self.get_response(request)
