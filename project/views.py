from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def home(request):
    if request.user.is_authenticated:
        business = getattr(request, 'business', None)
        if business is None:
            return redirect('accounts:onboarding')
        profile = getattr(business, 'company_profile', None)
        if not profile or not getattr(profile, 'is_complete', False):
            return redirect('accounts:onboarding')
        return redirect('dashboard_home')
    return render(request, 'home.html')


@login_required
def dashboard_home(request):
    business = getattr(request, 'business', None)
    if business is None:
        return redirect('accounts:onboarding')

    profile = getattr(business, 'company_profile', None)
    if not profile or not getattr(profile, 'is_complete', False):
        return redirect('accounts:onboarding')

    return render(
        request,
        'dashboard/home.html',
        {
            'business': business,
            'company_profile': profile,
        },
    )
