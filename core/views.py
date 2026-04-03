from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import BusinessOnboardingForm
from .models import BusinessMembership


@login_required
def onboarding(request):
    existing = (
        BusinessMembership.objects.filter(user=request.user, is_active=True)
        .select_related("business")
        .first()
    )
    if existing:
        return redirect("home")

    if request.method == "POST":
        form = BusinessOnboardingForm(request.POST)
        if form.is_valid():
            business = form.save()
            BusinessMembership.objects.create(
                business=business,
                user=request.user,
                role=BusinessMembership.Role.OWNER,
                is_active=True,
            )
            messages.success(request, "Business created successfully.")
            return redirect("home")
    else:
        form = BusinessOnboardingForm()

    return render(request, "core/business_onboarding.html", {"form": form})
