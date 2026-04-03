from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import UpdateView

from core.models import Business, BusinessMembership

from .forms import CompanyProfileForm, UserInfoForm
from .models import CompanyProfile


def _get_active_membership(user):
    return (
        BusinessMembership.objects.filter(user=user, is_active=True)
        .select_related("business")
        .first()
    )


class OnboardingView(LoginRequiredMixin, UpdateView):
    model = CompanyProfile
    form_class = CompanyProfileForm
    template_name = "accounts/onboarding.html"
    success_url = reverse_lazy("home")

    def get_object(self, queryset=None):
        with transaction.atomic():
            membership = (
                BusinessMembership.objects.select_for_update()
                .filter(user=self.request.user, is_active=True)
                .select_related("business")
                .first()
            )

            if not membership:
                default_name = (getattr(settings, "DEFAULT_COMPANY_NAME", "") or "").strip() or "Your Business"
                business = Business.objects.create(name=default_name)
                membership = BusinessMembership.objects.create(
                    business=business,
                    user=self.request.user,
                    role=BusinessMembership.Role.OWNER,
                    is_active=True,
                )

            business = membership.business
            profile, _ = CompanyProfile.objects.get_or_create(
                business=business,
                defaults={
                    "created_by": self.request.user,
                    "company_name": "",
                },
            )
            return profile

    def form_valid(self, form):
        self.object = form.save()
        business = self.object.business
        new_name = (self.object.company_name or "").strip()
        if new_name and business.name != new_name:
            business.name = new_name
            business.save(update_fields=["name"])
        messages.success(self.request, "Company setup saved.")
        return redirect("home")


class SettingsView(LoginRequiredMixin, View):
    template_name = "accounts/settings.html"

    def _get_profile_or_redirect(self, request):
        membership = _get_active_membership(request.user)
        if not membership:
            return None, redirect("accounts:onboarding")

        business = membership.business
        profile, _ = CompanyProfile.objects.get_or_create(
            business=business,
            defaults={"created_by": request.user, "company_name": business.name},
        )
        return profile, None

    def dispatch(self, request, *args, **kwargs):
        profile, resp = self._get_profile_or_redirect(request)
        if resp:
            return resp
        if not profile.is_complete and request.path != reverse_lazy("accounts:onboarding"):
            return redirect("accounts:onboarding")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profile, resp = self._get_profile_or_redirect(request)
        if resp:
            return resp
        return render(
            request,
            self.template_name,
            {
                "company_form": CompanyProfileForm(instance=profile, prefix="company"),
                "user_form": UserInfoForm(instance=request.user, prefix="user"),
            },
        )

    def post(self, request):
        profile, resp = self._get_profile_or_redirect(request)
        if resp:
            return resp

        company_form = CompanyProfileForm(instance=profile, prefix="company")
        user_form = UserInfoForm(instance=request.user, prefix="user")
        form_id = request.POST.get("form_id", "")

        if form_id == "company":
            company_form = CompanyProfileForm(request.POST, request.FILES, instance=profile, prefix="company")
            if company_form.is_valid():
                obj = company_form.save()
                name = (obj.company_name or "").strip()
                if name and obj.business.name != name:
                    obj.business.name = name
                    obj.business.save(update_fields=["name"])
                messages.success(request, "Company settings saved.")
                return redirect("accounts:settings")
        elif form_id == "user":
            user_form = UserInfoForm(request.POST, instance=request.user, prefix="user")
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "User info updated.")
                return redirect("accounts:settings")
        else:
            messages.error(request, "Invalid form submission.")

        return render(
            request,
            self.template_name,
            {
                "company_form": company_form,
                "user_form": user_form,
            },
        )
